"""Growth tracking business logic (Phase 4).

Responsibilities:

* record and update child growth measurements (weight, height, MUAC, date);
* validate via :mod:`app.utils.validators`;
* classify status using the **documented demo rules** in
  :mod:`app.utils.growth_rules` (never invented clinical thresholds);
* keep a single open ``GROWTH_FOLLOW_UP`` alert in sync with the latest
  concerning status.

The full alert lifecycle (assignment, manual status changes, home visits) is
built in Phase 9; this module only performs the scoped growth integration so a
measurement can raise or clear a follow-up flag.
"""

from __future__ import annotations

from flask import abort, current_app

from app.extensions import db
from app.models import GrowthRecord
from app.services import alert_service
from app.utils.constants import AlertType
from app.utils.growth_rules import (
    DEFAULT_RULES,
    DEMO_RULE_ID,
    GrowthDemoRules,
    age_in_months,
    classify,
    explanation,
    is_concerning,
)
from app.utils.validators import ValidationError, validate_growth_fields


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def current_rules() -> GrowthDemoRules:
    """Return the configured demo rules (or the built-in default)."""
    try:
        configured = current_app.config.get("GROWTH_DEMO_RULES")
    except RuntimeError:  # no application context
        configured = None
    if isinstance(configured, GrowthDemoRules):
        return configured
    return DEFAULT_RULES


# ---------------------------------------------------------------------------
# Queries / view models
# ---------------------------------------------------------------------------
def records_for_child(child, *, newest_first: bool = True):
    """Return all growth records for ``child`` ordered by date."""
    order = GrowthRecord.measurement_date.desc() if newest_first else GrowthRecord.measurement_date.asc()
    return (
        GrowthRecord.query.filter_by(child_id=child.id)
        .order_by(order, GrowthRecord.id.desc())
        .all()
    )


def get_record(child, record_id: int) -> GrowthRecord:
    """Return a growth record that belongs to ``child`` or raise 404."""
    record = db.session.get(GrowthRecord, record_id)
    if record is None or record.child_id != child.id:
        abort(404)
    return record


def latest_record(child) -> GrowthRecord | None:
    """Return the most recent growth record for ``child``."""
    return (
        GrowthRecord.query.filter_by(child_id=child.id)
        .order_by(GrowthRecord.measurement_date.desc(), GrowthRecord.id.desc())
        .first()
    )


def _age_label(months: int) -> str:
    if months < 24:
        return f"{months} month{'s' if months != 1 else ''}"
    years, remaining = divmod(months, 12)
    return f"{years}y {remaining}m"


def serialize_record(child, record: GrowthRecord) -> dict:
    """Build a display model for one growth record."""
    dob = child.beneficiary.date_of_birth
    months = age_in_months(dob, record.measurement_date)
    status = record.nutritional_status
    ratio = None
    text = None
    if status is not None:
        rules = current_rules()
        _, ratio = classify(record.weight_kg, months, rules)
        text = explanation(status, ratio, months, rules)
    return {
        "record": record,
        "age_months": months,
        "age_label": _age_label(months),
        "status": status,
        "ratio": ratio,
        "explanation": text,
        "concerning": is_concerning(status) if status else False,
    }


def build_history(child) -> list[dict]:
    """Return display models for every record, newest first."""
    return [serialize_record(child, record) for record in records_for_child(child)]


def chart_data(child) -> dict:
    """Return Chart.js-ready series (chronological) for ``child``."""
    records = records_for_child(child, newest_first=False)
    history = [serialize_record(child, record) for record in records]
    return {
        "labels": [item["record"].measurement_date.isoformat() for item in history],
        "weight": [
            float(item["record"].weight_kg) if item["record"].weight_kg is not None else None
            for item in history
        ],
        "height": [
            float(item["record"].height_cm) if item["record"].height_cm is not None else None
            for item in history
        ],
        "muac": [
            float(item["record"].muac_cm) if item["record"].muac_cm is not None else None
            for item in history
        ],
    }


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------
def record_growth(child, form, *, recorded_by=None) -> GrowthRecord:
    """Validate, classify and store a new growth measurement."""
    cleaned, errors = validate_growth_fields(form, child)
    if errors:
        raise ValidationError(errors)

    existing = GrowthRecord.query.filter_by(
        child_id=child.id, measurement_date=cleaned["measurement_date"]
    ).first()
    if existing is not None:
        raise ValidationError(
            {
                "measurement_date": (
                    "A growth record for this date already exists. "
                    "Edit the existing record instead."
                )
            }
        )

    record = _apply_classification(child, cleaned)
    record.child = child
    record.recorded_by = recorded_by
    db.session.add(record)
    _sync_growth_alert(child, record, actor=recorded_by)
    db.session.commit()
    return record


def update_growth(child, record: GrowthRecord, form, *, recorded_by=None) -> GrowthRecord:
    """Validate, reclassify and update an existing growth measurement."""
    cleaned, errors = validate_growth_fields(form, child)
    if errors:
        raise ValidationError(errors)

    conflict = (
        GrowthRecord.query.filter_by(
            child_id=child.id, measurement_date=cleaned["measurement_date"]
        )
        .filter(GrowthRecord.id != record.id)
        .first()
    )
    if conflict is not None:
        raise ValidationError(
            {
                "measurement_date": (
                    "Another growth record already exists for this date."
                )
            }
        )

    classified = _apply_classification(child, cleaned)
    for key in ("measurement_date", "weight_kg", "height_cm", "muac_cm", "notes"):
        setattr(record, key, getattr(classified, key))
    record.nutritional_status = classified.nutritional_status
    if recorded_by is not None:
        record.recorded_by = recorded_by

    _sync_growth_alert(child, record, actor=recorded_by)
    db.session.commit()
    return record


def _apply_classification(child, cleaned: dict) -> GrowthRecord:
    """Build a transient record carrying the demo classification."""
    dob = child.beneficiary.date_of_birth
    months = age_in_months(dob, cleaned["measurement_date"])
    status, _ratio = classify(cleaned["weight_kg"], months, current_rules())
    return GrowthRecord(
        measurement_date=cleaned["measurement_date"],
        weight_kg=cleaned["weight_kg"],
        height_cm=cleaned.get("height_cm"),
        muac_cm=cleaned.get("muac_cm"),
        notes=cleaned.get("notes"),
        nutritional_status=status,
    )


# ---------------------------------------------------------------------------
# Growth alert synchronisation (scoped integration point for Phase 9)
# ---------------------------------------------------------------------------
def open_growth_alert(child):
    """Return the current active growth alert for ``child``, if any.

    Thin wrapper kept for backwards compatibility; the rule itself lives in
    :mod:`app.services.alert_service`.
    """
    return alert_service.open_alert(AlertType.GROWTH_FOLLOW_UP, child=child)


def _sync_growth_alert(child, record: GrowthRecord, *, actor=None):
    """Create or clear the growth follow-up alert for a measurement."""
    return alert_service.sync_growth_alert(child, record, actor=actor)


__all__ = [
    "build_history",
    "chart_data",
    "current_rules",
    "get_record",
    "latest_record",
    "open_growth_alert",
    "record_growth",
    "records_for_child",
    "serialize_record",
    "update_growth",
]
