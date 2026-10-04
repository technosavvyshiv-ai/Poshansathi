"""Vaccination tracking business logic (Phase 5).

Responsibilities:

* list / retrieve a child's vaccination records;
* validate submitted data via :mod:`app.utils.validators` (no clinical
  schedule is invented — the stored ``Vaccination.status`` and dates are the
  source of truth);
* create and update records while preventing duplicates and inconsistent
  status/date combinations;
* expose a deterministic display status using the documented demo rule in
  :mod:`app.utils.vaccination_rules`.

Access control (roles and centre scoping) is enforced by the route layer via
the existing decorators and :func:`app.utils.helpers.ensure_beneficiary_access`.
"""

from __future__ import annotations

from flask import abort
from sqlalchemy import func

from app.extensions import db
from app.models import Vaccination
from app.utils.constants import VaccinationStatus
from app.utils.validators import ValidationError, validate_vaccination_fields
from app.utils.vaccination_rules import (
    DEMO_RULE_ID,
    VaccinationDisplayStatus,
    display_badge,
    display_label,
    display_status,
)


# ---------------------------------------------------------------------------
# Queries / view models
# ---------------------------------------------------------------------------
def records_for_child(child, *, newest_first: bool = True):
    """Return every vaccination record for ``child`` ordered by scheduled date."""
    order = (
        Vaccination.scheduled_date.desc()
        if newest_first
        else Vaccination.scheduled_date.asc()
    )
    return (
        Vaccination.query.filter_by(child_id=child.id)
        .order_by(order, Vaccination.id.desc())
        .all()
    )


def get_record(child, record_id: int) -> Vaccination:
    """Return a vaccination record that belongs to ``child`` or raise 404."""
    record = db.session.get(Vaccination, record_id)
    if record is None or record.child_id != child.id:
        abort(404)
    return record


def serialize_record(child, record: Vaccination) -> dict:  # noqa: ARG001
    """Build a display model for one vaccination record."""
    view_status = display_status(record)
    return {
        "record": record,
        "display_status": view_status.value,
        "display_label": display_label(view_status),
        "display_badge": display_badge(view_status),
    }


def build_history(child) -> list[dict]:
    """Return display models for every vaccination record, newest first."""
    return [serialize_record(child, record) for record in records_for_child(child)]


def summary(child) -> dict:
    """Return deterministic counts used by the child-profile vaccination card."""
    counts = {status.value: 0 for status in VaccinationDisplayStatus}
    total = 0
    for record in records_for_child(child):
        counts[display_status(record).value] += 1
        total += 1
    completed = counts[VaccinationDisplayStatus.COMPLETED.value]
    pending = counts[VaccinationDisplayStatus.DUE.value] + counts[
        VaccinationDisplayStatus.UPCOMING.value
    ]
    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "overdue": counts[VaccinationDisplayStatus.OVERDUE.value],
        "missed": counts[VaccinationDisplayStatus.MISSED.value],
    }


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------
def _duplicate_record(child, vaccine_name: str, dose_number: int, *, exclude_id=None):
    """Return an existing matching record (case-insensitive) or ``None``.

    The database enforces ``UNIQUE (child_id, vaccine_name, dose_number)``.
    The service performs an explicit, case-insensitive check as well so users
    receive a friendly message instead of an integrity error, and so the same
    rule holds across SQLite (tests) and MySQL (collation differs).
    """
    query = Vaccination.query.filter(
        Vaccination.child_id == child.id,
        func.lower(Vaccination.vaccine_name) == vaccine_name.lower(),
        Vaccination.dose_number == dose_number,
    )
    if exclude_id is not None:
        query = query.filter(Vaccination.id != exclude_id)
    return query.first()


def _apply_record(record: Vaccination, cleaned: dict, *, recorded_by) -> None:
    """Copy validated values onto ``record`` and set the administrator."""
    record.vaccine_name = cleaned["vaccine_name"]
    record.dose_number = cleaned["dose_number"]
    record.scheduled_date = cleaned.get("scheduled_date")
    record.administered_date = cleaned.get("administered_date")
    record.status = cleaned["status"]
    record.notes = cleaned.get("notes")
    if cleaned["status"] == VaccinationStatus.COMPLETED and cleaned.get(
        "administered_date"
    ):
        record.administered_by = recorded_by
    else:
        record.administered_by = None


def create_vaccination(child, form, *, recorded_by=None) -> Vaccination:
    """Validate, check for duplicates and store a new vaccination record."""
    cleaned, errors = validate_vaccination_fields(form, child)
    if errors:
        raise ValidationError(errors)

    existing = _duplicate_record(
        child, cleaned["vaccine_name"], cleaned["dose_number"]
    )
    if existing is not None:
        raise ValidationError(
            {
                "vaccine_name": (
                    f"Vaccination {cleaned['vaccine_name']} (dose "
                    f"{cleaned['dose_number']}) already exists for this child. "
                    "Edit the existing record instead."
                )
            }
        )

    record = Vaccination(child=child)
    _apply_record(record, cleaned, recorded_by=recorded_by)
    db.session.add(record)
    db.session.commit()
    return record


def update_vaccination(
    child, record: Vaccination, form, *, recorded_by=None
) -> Vaccination:
    """Validate and update an existing vaccination record."""
    cleaned, errors = validate_vaccination_fields(form, child)
    if errors:
        raise ValidationError(errors)

    conflict = _duplicate_record(
        child,
        cleaned["vaccine_name"],
        cleaned["dose_number"],
        exclude_id=record.id,
    )
    if conflict is not None:
        raise ValidationError(
            {
                "vaccine_name": (
                    f"Another vaccination record for {cleaned['vaccine_name']} "
                    f"(dose {cleaned['dose_number']}) already exists for this "
                    "child."
                )
            }
        )

    _apply_record(record, cleaned, recorded_by=recorded_by)
    db.session.commit()
    return record


__all__ = [
    "DEMO_RULE_ID",
    "build_history",
    "create_vaccination",
    "get_record",
    "records_for_child",
    "serialize_record",
    "summary",
    "update_vaccination",
]
