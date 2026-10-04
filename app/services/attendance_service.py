"""Attendance business logic (Phase 8).

Responsibilities:

* record and update a child's daily attendance (present / absent + note);
* prevent more than one record per child and date (enforced by the unique
  constraint and also checked here so users get a friendly message);
* build the daily register for a centre and the per-child history;
* calculate deterministic attendance summaries (daily, monthly, overall);
* list frequent absences for a centre/month.

Access control (roles and centre scoping) is enforced by the route layer via
the existing decorators and :func:`app.utils.helpers.ensure_beneficiary_access`.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date

from flask import abort

from app.extensions import db
from app.models import Attendance, Beneficiary, Child
from app.services import alert_service
from app.utils.constants import AttendanceStatus, RecordStatus
from app.utils.validators import ValidationError, validate_attendance_fields


#: Badge classes used by the templates for the two stored statuses.
STATUS_BADGES = {
    AttendanceStatus.PRESENT: "text-bg-success",
    AttendanceStatus.ABSENT: "text-bg-danger",
}

STATUS_LABELS = {
    AttendanceStatus.PRESENT: "Present",
    AttendanceStatus.ABSENT: "Absent",
}


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------
def children_for_centre(centre_id, *, active_only: bool = True):
    """Return children registered at ``centre_id`` ordered by name."""
    query = Child.query.join(Beneficiary)
    if centre_id is not None:
        query = query.filter(Beneficiary.centre_id == centre_id)
    if active_only:
        query = query.filter(Beneficiary.status == RecordStatus.ACTIVE)
    return query.order_by(Beneficiary.full_name.asc()).all()


# ---------------------------------------------------------------------------
# Queries / view models
# ---------------------------------------------------------------------------
def attendance_query(
    *,
    centre_id=None,
    child_id=None,
    status=None,
    start_date=None,
    end_date=None,
    newest_first: bool = True,
):
    """Return attendance records with optional filters, ordered by date."""
    query = Attendance.query
    if centre_id is not None:
        query = query.filter(Attendance.centre_id == centre_id)
    if child_id is not None:
        query = query.filter(Attendance.child_id == child_id)
    if status is not None:
        query = query.filter(Attendance.status == status)
    if start_date is not None:
        query = query.filter(Attendance.attendance_date >= start_date)
    if end_date is not None:
        query = query.filter(Attendance.attendance_date <= end_date)

    order = (
        Attendance.attendance_date.desc()
        if newest_first
        else Attendance.attendance_date.asc()
    )
    return query.order_by(order, Attendance.id.desc()).all()


def records_for_child(child, *, newest_first: bool = True):
    """Return every attendance record for ``child`` backed by the query helper."""
    return attendance_query(child_id=child.id, newest_first=newest_first)


def get_record(child, record_id: int) -> Attendance:
    """Return an attendance record that belongs to ``child`` or raise 404."""
    record = db.session.get(Attendance, record_id)
    if record is None or record.child_id != child.id:
        abort(404)
    return record


def record_for_date(child, on_date) -> Attendance | None:
    """Return ``child``'s attendance record for ``on_date``, if any."""
    return Attendance.query.filter_by(
        child_id=child.id, attendance_date=on_date
    ).first()


def serialize_record(record: Attendance) -> dict:
    """Build a small display model for one attendance record."""
    status = record.status
    return {
        "record": record,
        "status": status,
        "status_label": STATUS_LABELS.get(status, status.value if status else "—"),
        "status_badge": STATUS_BADGES.get(status, "text-bg-secondary"),
    }


def build_history(child) -> list[dict]:
    """Return display models for a child's records, newest first."""
    return [serialize_record(record) for record in records_for_child(child)]


# ---------------------------------------------------------------------------
# Daily register
# ---------------------------------------------------------------------------
def daily_register(centre_id, on_date) -> list[dict]:
    """Return one row per active child for the daily register.

    Each row carries the child's existing record (if any) so the template can
    pre-fill the status and note.
    """
    children = children_for_centre(centre_id)
    existing = {
        record.child_id: record
        for record in Attendance.query.filter_by(
            centre_id=centre_id, attendance_date=on_date
        ).all()
    }
    rows: list[dict] = []
    for child in children:
        record = existing.get(child.id)
        rows.append(
            {
                "child": child,
                "beneficiary": child.beneficiary,
                "record": record,
                "status": record.status if record else None,
                "note": record.note if record else "",
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------
def _percentage(present: int, total: int):
    if not total:
        return None
    return round(present / total * 100, 1)


def _count(records) -> dict:
    present = sum(1 for record in records if record.status == AttendanceStatus.PRESENT)
    absent = sum(1 for record in records if record.status == AttendanceStatus.ABSENT)
    total = len(records)
    return {
        "present": present,
        "absent": absent,
        "total": total,
        "attendance_percentage": _percentage(present, total),
    }


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return the first and last day of ``year``/``month``."""
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def daily_summary(centre_id, on_date) -> dict:
    """Return present/absent counts for one centre on one day."""
    records = Attendance.query.filter_by(
        centre_id=centre_id, attendance_date=on_date
    ).all()
    summary = _count(records)
    summary["date"] = on_date
    return summary


def summary_for_scope(
    *, centre_id=None, child_id=None, start_date=None, end_date=None
) -> dict:
    """Return present/absent counts for a filtered set of records."""
    records = attendance_query(
        centre_id=centre_id,
        child_id=child_id,
        start_date=start_date,
        end_date=end_date,
    )
    return _count(records)


def child_summary(child) -> dict:
    """Return the overall attendance summary for ``child``."""
    return _count(records_for_child(child))


def monthly_summary(child, year: int, month: int) -> dict:
    """Return ``child``'s attendance summary for one calendar month."""
    start, end = month_bounds(year, month)
    records = attendance_query(
        child_id=child.id, start_date=start, end_date=end
    )
    summary = _count(records)
    summary.update({"year": year, "month": month, "start": start, "end": end})
    return summary


def recent_monthly_summaries(child, *, months: int = 6) -> list[dict]:
    """Return ``child``'s last ``months`` calendar-month summaries, newest first."""
    today = date.today()
    summaries: list[dict] = []
    year, month = today.year, today.month
    for _ in range(max(0, months)):
        summaries.append(monthly_summary(child, year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return summaries


def frequent_absences(
    *, centre_id=None, year=None, month=None, limit: int | None = 25
) -> list[dict]:
    """Return children with the most absences for a centre/period.

    The list is ordered by absence count (descending) and then by attendance
    percentage (ascending), so the children needing follow-up appear first.
    Children with no absences in the period are omitted.
    """
    start_date = end_date = None
    if year is not None and month is not None:
        start_date, end_date = month_bounds(year, month)

    records = attendance_query(
        centre_id=centre_id, start_date=start_date, end_date=end_date
    )

    buckets: dict[int, dict] = {}
    for record in records:
        bucket = buckets.setdefault(
            record.child_id,
            {
                "child": record.child,
                "beneficiary": record.child.beneficiary if record.child else None,
                "present": 0,
                "absent": 0,
                "total": 0,
            },
        )
        bucket["total"] += 1
        if record.status == AttendanceStatus.ABSENT:
            bucket["absent"] += 1
        else:
            bucket["present"] += 1

    rows = []
    for bucket in buckets.values():
        if bucket["absent"] == 0:
            continue
        bucket["attendance_percentage"] = _percentage(
            bucket["present"], bucket["total"]
        )
        rows.append(bucket)

    rows.sort(
        key=lambda row: (-row["absent"], row["attendance_percentage"] or 0.0)
    )
    if limit is not None:
        return rows[:limit]
    return rows


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------
def _apply(record: Attendance, child, cleaned: dict, recorded_by) -> None:
    """Copy validated values onto ``record``.

    Foreign keys are assigned directly (rather than through the relationship)
    so a brand-new, not-yet-flushed record does not trigger a back-population
    warning on ``Child.attendance_records``.
    """
    record.child_id = child.id
    record.centre_id = child.beneficiary.centre_id
    record.attendance_date = cleaned["attendance_date"]
    record.status = cleaned["status"]
    record.note = cleaned.get("note")
    if recorded_by is not None:
        record.recorded_by = recorded_by


def record_attendance(
    child, form, *, recorded_by=None, allow_update: bool = False
) -> Attendance:
    """Validate and store a daily attendance record.

    When ``allow_update`` is False (the single-record form) a second record for
    the same child and date is rejected.  The bulk daily register passes
    ``allow_update=True`` so re-submitting a day updates the existing row
    instead of creating a duplicate — the explicitly allowed update path.
    """
    cleaned, errors = validate_attendance_fields(form, child)
    if errors:
        raise ValidationError(errors)

    existing = record_for_date(child, cleaned["attendance_date"])
    if existing is not None:
        if not allow_update:
            raise ValidationError(
                {
                    "attendance_date": (
                        "Attendance for this child and date already exists. "
                        "Edit the existing record instead."
                    )
                }
            )
        _apply(existing, child, cleaned, recorded_by)
        alert_service.sync_attendance_alert(child, actor=recorded_by)
        db.session.commit()
        return existing

    record = Attendance()
    _apply(record, child, cleaned, recorded_by)
    db.session.add(record)
    alert_service.sync_attendance_alert(child, actor=recorded_by)
    db.session.commit()
    return record


def update_attendance(child, record: Attendance, form, *, recorded_by=None) -> Attendance:
    """Validate and update an existing attendance record."""
    cleaned, errors = validate_attendance_fields(form, child)
    if errors:
        raise ValidationError(errors)

    conflict = (
        Attendance.query.filter_by(
            child_id=child.id, attendance_date=cleaned["attendance_date"]
        )
        .filter(Attendance.id != record.id)
        .first()
    )
    if conflict is not None:
        raise ValidationError(
            {
                "attendance_date": (
                    "Another attendance record already exists for this date."
                )
            }
        )

    _apply(record, child, cleaned, recorded_by)
    alert_service.sync_attendance_alert(child, actor=recorded_by)
    db.session.commit()
    return record


def mark_daily_attendance(centre, on_date, entries, *, recorded_by=None) -> dict:
    """Upsert attendance for many children in one centre/date transaction.

    ``entries`` is an iterable of ``{"child", "status_raw", "note"}`` mappings.
    A blank status leaves any existing record untouched.  Returns a small
    ``{"created", "updated", "skipped", "invalid"}`` result for the flash
    message.
    """
    existing = {
        record.child_id: record
        for record in Attendance.query.filter_by(
            centre_id=centre.id, attendance_date=on_date
        ).all()
    }

    created = updated = skipped = invalid = 0
    affected: dict[int, object] = {}
    for entry in entries:
        child = entry["child"]
        status_raw = (entry.get("status_raw") or "").strip()

        if not status_raw:
            skipped += 1
            continue
        try:
            status = AttendanceStatus(status_raw)
        except ValueError:
            invalid += 1
            continue

        note = (entry.get("note") or "").strip() or None
        record = existing.get(child.id)
        if record is None:
            record = Attendance(
                child_id=child.id,
                centre_id=centre.id,
                attendance_date=on_date,
                recorded_by=recorded_by,
            )
            db.session.add(record)
            existing[child.id] = record
            created += 1
        else:
            updated += 1

        record.status = status
        record.note = note
        if recorded_by is not None:
            record.recorded_by = recorded_by
        affected[child.id] = child

    for child in affected.values():
        alert_service.sync_attendance_alert(child, actor=recorded_by)

    db.session.commit()
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "invalid": invalid,
    }


__all__ = [
    "STATUS_BADGES",
    "STATUS_LABELS",
    "attendance_query",
    "build_history",
    "child_summary",
    "children_for_centre",
    "daily_register",
    "daily_summary",
    "frequent_absences",
    "get_record",
    "mark_daily_attendance",
    "month_bounds",
    "monthly_summary",
    "recent_monthly_summaries",
    "record_attendance",
    "record_for_date",
    "records_for_child",
    "serialize_record",
    "summary_for_scope",
    "update_attendance",
]
