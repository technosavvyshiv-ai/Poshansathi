"""Maternal health business logic (Phase 6).

Responsibilities:

* list / retrieve a mother's antenatal-care (ANC) records;
* validate submitted data via :mod:`app.utils.validators` (broad data-integrity
  guards only — no clinical thresholds or risk decisions are invented);
* create and update records while preventing duplicate visit dates;
* expose a deterministic follow-up highlight and risk badge using the
  documented demo rule in :mod:`app.utils.maternal_rules`.

Access control (roles and centre scoping) is enforced by the route layer via
the existing decorators and :func:`app.utils.helpers.ensure_beneficiary_access`.
"""

from __future__ import annotations

from datetime import date

from flask import abort

from app.extensions import db
from app.models import MaternalHealthRecord
from app.utils.maternal_rules import (
    FollowUpStatus,
    follow_up_badge,
    follow_up_label,
    follow_up_status,
    risk_badge,
    risk_label,
)
from app.utils.validators import (
    ValidationError,
    validate_maternal_health_fields,
)


# ---------------------------------------------------------------------------
# Queries / view models
# ---------------------------------------------------------------------------
def records_for_mother(mother, *, newest_first: bool = True):
    """Return every ANC record for ``mother`` ordered by visit date."""
    order = (
        MaternalHealthRecord.visit_date.desc()
        if newest_first
        else MaternalHealthRecord.visit_date.asc()
    )
    return (
        MaternalHealthRecord.query.filter_by(mother_id=mother.id)
        .order_by(order, MaternalHealthRecord.id.desc())
        .all()
    )


def get_record(mother, record_id: int) -> MaternalHealthRecord:
    """Return an ANC record that belongs to ``mother`` or raise 404."""
    record = db.session.get(MaternalHealthRecord, record_id)
    if record is None or record.mother_id != mother.id:
        abort(404)
    return record


def latest_record(mother) -> MaternalHealthRecord | None:
    """Return the most recent ANC record for ``mother``."""
    return (
        MaternalHealthRecord.query.filter_by(mother_id=mother.id)
        .order_by(
            MaternalHealthRecord.visit_date.desc(),
            MaternalHealthRecord.id.desc(),
        )
        .first()
    )


def serialize_record(record) -> dict:
    """Build a display model for one ANC record."""
    status = follow_up_status(record)
    return {
        "record": record,
        "follow_up_status": status.value,
        "follow_up_label": follow_up_label(status),
        "follow_up_badge": follow_up_badge(status),
        "risk_label": risk_label(record.risk_category),
        "risk_badge": risk_badge(record.risk_category),
    }


def build_history(mother) -> list[dict]:
    """Return display models for every ANC record, newest first."""
    return [serialize_record(record) for record in records_for_mother(mother)]


def pending_follow_up(mother, today: date | None = None) -> dict | None:
    """Return the most relevant configured follow-up for ``mother``.

    Deterministic selection based only on stored follow-up dates: an overdue
    follow-up is highlighted first, then a due-today one, then the soonest
    upcoming one.  Returns ``None`` when no record has a follow-up date.
    """
    today = today or date.today()
    candidates = [
        record
        for record in records_for_mother(mother)
        if record.next_follow_up_date is not None
    ]
    if not candidates:
        return None

    priority = {
        FollowUpStatus.OVERDUE: 0,
        FollowUpStatus.DUE: 1,
        FollowUpStatus.UPCOMING: 2,
    }

    def sort_key(record):
        status = follow_up_status(record, today)
        return (priority.get(status, 3), record.next_follow_up_date)

    record = sorted(candidates, key=sort_key)[0]
    status = follow_up_status(record, today)
    return {
        "record": record,
        "date": record.next_follow_up_date,
        "status": status.value,
        "label": follow_up_label(status),
        "badge": follow_up_badge(status),
        "overdue": status == FollowUpStatus.OVERDUE,
    }


def summary(mother) -> dict:
    """Return the deterministic summary used by the profile/history header."""
    records = records_for_mother(mother)
    latest = records[0] if records else None
    return {
        "total": len(records),
        "latest": latest,
        "latest_risk_label": risk_label(latest.risk_category) if latest else "—",
        "latest_risk_badge": risk_badge(latest.risk_category) if latest else "text-bg-secondary",
        "pending_follow_up": pending_follow_up(mother),
    }


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------
def _duplicate_record(mother, visit_date, *, exclude_id=None):
    """Return an existing record for ``visit_date`` or ``None``."""
    query = MaternalHealthRecord.query.filter_by(
        mother_id=mother.id, visit_date=visit_date
    )
    if exclude_id is not None:
        query = query.filter(MaternalHealthRecord.id != exclude_id)
    return query.first()


def _apply_record(
    record: MaternalHealthRecord, cleaned: dict, *, recorded_by
) -> None:
    """Copy validated values onto ``record`` and set the recorder."""
    for key in (
        "visit_date",
        "pregnancy_month",
        "weight_kg",
        "haemoglobin",
        "systolic_bp",
        "diastolic_bp",
        "risk_category",
        "next_follow_up_date",
        "notes",
    ):
        setattr(record, key, cleaned.get(key))
    if recorded_by is not None:
        record.recorded_by = recorded_by


def create_maternal_health(mother, form, *, recorded_by=None) -> MaternalHealthRecord:
    """Validate, check for duplicates and store a new ANC record."""
    cleaned, errors = validate_maternal_health_fields(form, mother)
    if errors:
        raise ValidationError(errors)

    existing = _duplicate_record(mother, cleaned["visit_date"])
    if existing is not None:
        raise ValidationError(
            {
                "visit_date": (
                    "An ANC record for this visit date already exists. "
                    "Edit the existing record instead."
                )
            }
        )

    record = MaternalHealthRecord(mother=mother)
    _apply_record(record, cleaned, recorded_by=recorded_by)
    db.session.add(record)
    db.session.commit()
    return record


def update_maternal_health(
    mother, record: MaternalHealthRecord, form, *, recorded_by=None
) -> MaternalHealthRecord:
    """Validate and update an existing ANC record."""
    cleaned, errors = validate_maternal_health_fields(form, mother)
    if errors:
        raise ValidationError(errors)

    conflict = _duplicate_record(
        mother, cleaned["visit_date"], exclude_id=record.id
    )
    if conflict is not None:
        raise ValidationError(
            {
                "visit_date": (
                    "Another ANC record already exists for this visit date."
                )
            }
        )

    _apply_record(record, cleaned, recorded_by=recorded_by)
    db.session.commit()
    return record


__all__ = [
    "build_history",
    "create_maternal_health",
    "get_record",
    "latest_record",
    "pending_follow_up",
    "records_for_mother",
    "serialize_record",
    "summary",
    "update_maternal_health",
]
