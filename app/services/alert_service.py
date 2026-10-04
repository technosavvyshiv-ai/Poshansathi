"""Centralized alert engine and lifecycle (Phase 9).

This module owns **all** rule-based alert creation, updating, resolution and
manual lifecycle changes.  Feature services (growth, vaccination, maternal,
nutrition, attendance, home visits) call the ``sync_*`` helpers here instead of
creating alerts themselves, so the rules live in exactly one place.

Design
------
* :mod:`app.utils.alert_rules` documents the deterministic, project-defined
  conditions and thresholds.  No LLM or external clinical reference is used.
* ``sync_*`` helpers are **idempotent**: for a given subject + alert type there
  is at most one *active* (OPEN/IN_PROGRESS) alert.  A still-true condition
  updates the existing alert; a cleared condition resolves it automatically.
* Manual lifecycle actions (assign, status change, resolve, dismiss, reopen)
  are validated against :data:`VALID_TRANSITIONS` and are the only functions
  that commit immediately.

The alert table has no centre/item columns, so the low-stock rule keeps its
stable ``[inventory:<centre_id>:<item_id>]`` message marker for identity.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import abort
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Alert,
    Attendance,
    Beneficiary,
    GrowthRecord,
    HomeVisit,
    Inventory,
    MaternalHealthRecord,
    User,
    Vaccination,
)
from app.utils import alert_rules
from app.utils.constants import (
    AlertStatus,
    AlertType,
    AttendanceStatus,
    RiskLevel,
    UserRole,
    VisitStatus,
)
from app.utils.growth_rules import is_concerning
from app.utils.helpers import scope_centre_id
from app.utils.maternal_rules import FollowUpStatus, follow_up_status
from app.utils.validators import ValidationError
from app.utils.vaccination_rules import (
    VaccinationDisplayStatus,
    display_status,
)

#: Statuses that mean "still being worked on".
ACTIVE_STATUSES = (AlertStatus.OPEN, AlertStatus.IN_PROGRESS)

#: Statuses that end the active lifecycle.
TERMINAL_STATUSES = (AlertStatus.RESOLVED, AlertStatus.DISMISSED)

#: Roles an alert may be assigned to.  ADMIN/SUPERVISOR are global; an AWW is
#: centre-bound (see :func:`assign_alert`).
ASSIGN_ROLES = (UserRole.ADMIN, UserRole.AWW, UserRole.SUPERVISOR)

#: Allowed manual status transitions (same-status updates are always allowed).
VALID_TRANSITIONS = {
    AlertStatus.OPEN: {
        AlertStatus.IN_PROGRESS,
        AlertStatus.RESOLVED,
        AlertStatus.DISMISSED,
    },
    AlertStatus.IN_PROGRESS: {
        AlertStatus.OPEN,
        AlertStatus.RESOLVED,
        AlertStatus.DISMISSED,
    },
    AlertStatus.RESOLVED: {AlertStatus.OPEN},
    AlertStatus.DISMISSED: {AlertStatus.OPEN},
}


# ---------------------------------------------------------------------------
# Low-level primitives
# ---------------------------------------------------------------------------
def _active_query(alert_type, *, child=None, beneficiary=None, marker=None):
    """Return a query for active alerts of ``alert_type`` for a subject."""
    query = Alert.query.filter(
        Alert.alert_type == alert_type, Alert.status.in_(ACTIVE_STATUSES)
    )
    if child is not None:
        query = query.filter(Alert.child_id == child.id)
    if beneficiary is not None:
        query = query.filter(Alert.beneficiary_id == beneficiary.id)
    if marker is not None:
        query = query.filter(Alert.message.like(f"{marker} %"))
    return query.order_by(Alert.created_at.desc(), Alert.id.desc())


def open_alert(alert_type, *, child=None, beneficiary=None, marker=None) -> Alert | None:
    """Return the current active alert for a subject/type, or ``None``."""
    return _active_query(
        alert_type, child=child, beneficiary=beneficiary, marker=marker
    ).first()


def upsert_alert(
    *,
    alert_type,
    severity,
    message,
    child=None,
    beneficiary=None,
    marker=None,
    assigned_to=None,
    actor=None,
):
    """Create or update the active alert for a subject/type.

    :returns: ``(alert, created)`` where ``created`` is True for a new row.
    """
    existing = open_alert(
        alert_type, child=child, beneficiary=beneficiary, marker=marker
    )
    if existing is not None:
        existing.severity = severity
        existing.message = message
        return existing, False

    alert = Alert(
        alert_type=alert_type,
        severity=severity,
        message=message,
        status=AlertStatus.OPEN,
        beneficiary_id=beneficiary.id if beneficiary is not None else None,
        child_id=child.id if child is not None else None,
        assigned_to=assigned_to if assigned_to is not None else actor,
        created_by=actor,
    )
    db.session.add(alert)
    return alert, True


def _resolve(alert: Alert, notes=None) -> Alert:
    """Resolve an alert without transition validation (rule cleared)."""
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.utcnow()
    alert.resolution_notes = notes
    return alert


def resolve_alert_type(
    alert_type, *, child=None, beneficiary=None, marker=None, notes=None
) -> list[Alert]:
    """Resolve every active alert of ``alert_type`` for a subject."""
    resolved = []
    for alert in _active_query(
        alert_type, child=child, beneficiary=beneficiary, marker=marker
    ).all():
        _resolve(alert, notes)
        resolved.append(alert)
    return resolved


# ---------------------------------------------------------------------------
# Deterministic rule sync (one function per rule)
# ---------------------------------------------------------------------------
def _inventory_is_low_stock(inventory: Inventory) -> bool:
    """True only when a *configured* minimum (> 0) has been reached."""
    minimum = inventory.minimum_stock or 0
    return minimum > 0 and inventory.is_low_stock


def sync_low_stock_alert(inventory: Inventory, *, actor=None) -> Alert | None:
    """Low-stock rule: inventory reached its configured minimum."""
    marker = f"[inventory:{inventory.centre_id}:{inventory.item_id}]"
    if _inventory_is_low_stock(inventory):
        available = inventory.available_quantity
        severity = (
            alert_rules.LOW_STOCK_EMPTY
            if available <= 0
            else alert_rules.LOW_STOCK_REACHED
        )
        message = (
            f"{marker} Low stock: {inventory.item.name} at "
            f"{inventory.centre.name} is {available} {inventory.unit} "
            f"(configured minimum {inventory.minimum_stock}) "
            f"({alert_rules.LOW_STOCK_RULE_ID})."
        )
        alert, _ = upsert_alert(
            alert_type=AlertType.LOW_NUTRITION_STOCK,
            severity=severity,
            message=message,
            marker=marker,
            actor=actor,
        )
        return alert

    resolve_alert_type(
        AlertType.LOW_NUTRITION_STOCK,
        marker=marker,
        notes=(
            f"Stock replenished to {inventory.available_quantity} "
            f"{inventory.unit}."
        ),
    )
    return None


def sync_growth_alert(child, record: GrowthRecord, *, actor=None) -> Alert | None:
    """Growth rule: latest classification is underweight/severe-underweight."""
    status = record.nutritional_status
    if status is not None and is_concerning(status):
        severity = (
            alert_rules.GROWTH_SEVERE
            if status.value == "SEVERE_UNDERWEIGHT"
            else alert_rules.GROWTH_UNDERWEIGHT
        )
        message = (
            f"Growth follow-up: {child.beneficiary.full_name} classified "
            f"{status.value} on {record.measurement_date.isoformat()} "
            f"({alert_rules.GROWTH_RULE_ID})."
        )
        alert, _ = upsert_alert(
            alert_type=AlertType.GROWTH_FOLLOW_UP,
            severity=severity,
            message=message,
            child=child,
            beneficiary=child.beneficiary,
            actor=actor,
        )
        return alert

    label = status.value if status is not None else "NO_DATA"
    resolve_alert_type(
        AlertType.GROWTH_FOLLOW_UP,
        child=child,
        notes=(
            f"Growth status {label} on "
            f"{record.measurement_date.isoformat()} "
            f"({alert_rules.GROWTH_RULE_ID})."
        ),
    )
    return None


def sync_growth_from_latest(child, *, actor=None) -> Alert | None:
    """Evaluate the growth rule from the child's most recent measurement."""
    latest = (
        GrowthRecord.query.filter_by(child_id=child.id)
        .order_by(GrowthRecord.measurement_date.desc(), GrowthRecord.id.desc())
        .first()
    )
    if latest is None:
        resolve_alert_type(
            AlertType.GROWTH_FOLLOW_UP,
            child=child,
            notes="No growth records on file.",
        )
        return None
    return sync_growth_alert(child, latest, actor=actor)


def sync_vaccination_alert(child, *, actor=None) -> Alert | None:
    """Vaccination rule: at least one MISSED or OVERDUE dose."""
    records = Vaccination.query.filter_by(child_id=child.id).all()
    missed = [
        record
        for record in records
        if display_status(record) == VaccinationDisplayStatus.MISSED
    ]
    overdue = [
        record
        for record in records
        if display_status(record) == VaccinationDisplayStatus.OVERDUE
    ]

    if missed or overdue:
        severity = (
            alert_rules.VACCINATION_MISSED
            if missed
            else alert_rules.VACCINATION_OVERDUE
        )
        message = (
            f"Vaccination follow-up: {child.beneficiary.full_name} has "
            f"{len(missed)} missed and {len(overdue)} overdue dose(s) "
            f"({alert_rules.VACCINATION_RULE_ID})."
        )
        alert, _ = upsert_alert(
            alert_type=AlertType.VACCINATION_FOLLOW_UP,
            severity=severity,
            message=message,
            child=child,
            beneficiary=child.beneficiary,
            actor=actor,
        )
        return alert

    resolve_alert_type(
        AlertType.VACCINATION_FOLLOW_UP,
        child=child,
        notes="No missed or overdue vaccine doses.",
    )
    return None


def sync_maternal_alert(mother, *, actor=None) -> Alert | None:
    """Maternal rule: latest ANC record is HIGH risk, or a follow-up is overdue."""
    records = (
        MaternalHealthRecord.query.filter_by(mother_id=mother.id)
        .order_by(
            MaternalHealthRecord.visit_date.desc(),
            MaternalHealthRecord.id.desc(),
        )
        .all()
    )
    latest = records[0] if records else None
    high_risk = latest is not None and latest.risk_category == RiskLevel.HIGH
    overdue = [
        record
        for record in records
        if follow_up_status(record) == FollowUpStatus.OVERDUE
    ]

    if high_risk or overdue:
        severity = (
            alert_rules.MATERNAL_HIGH_RISK
            if high_risk
            else alert_rules.MATERNAL_OVERDUE
        )
        reasons = []
        if high_risk:
            reasons.append(
                f"latest ANC record on {latest.visit_date.isoformat()} is HIGH risk"
            )
        if overdue:
            reasons.append(f"{len(overdue)} ANC follow-up(s) overdue")
        message = (
            f"Maternal follow-up: {mother.beneficiary.full_name} — "
            + "; ".join(reasons)
            + f" ({alert_rules.MATERNAL_RULE_ID})."
        )
        alert, _ = upsert_alert(
            alert_type=AlertType.MATERNAL_FOLLOW_UP,
            severity=severity,
            message=message,
            beneficiary=mother.beneficiary,
            actor=actor,
        )
        return alert

    resolve_alert_type(
        AlertType.MATERNAL_FOLLOW_UP,
        beneficiary=mother.beneficiary,
        notes="No high-risk or overdue maternal follow-up.",
    )
    return None


def sync_attendance_alert(child, *, actor=None, today: date | None = None) -> Alert | None:
    """Attendance rule: too many absences in the configured recent window."""
    today = today or date.today()
    window_start = today - timedelta(days=alert_rules.ATTENDANCE_WINDOW_DAYS)
    records = Attendance.query.filter(
        Attendance.child_id == child.id,
        Attendance.attendance_date >= window_start,
        Attendance.attendance_date <= today,
    ).all()
    absent = sum(
        1 for record in records if record.status == AttendanceStatus.ABSENT
    )

    if absent >= alert_rules.ATTENDANCE_ABSENCE_THRESHOLD:
        message = (
            f"Attendance follow-up: {child.beneficiary.full_name} has "
            f"{absent} absences in the last "
            f"{alert_rules.ATTENDANCE_WINDOW_DAYS} days "
            f"({alert_rules.ATTENDANCE_RULE_ID})."
        )
        alert, _ = upsert_alert(
            alert_type=AlertType.ATTENDANCE,
            severity=alert_rules.ATTENDANCE_SEVERITY,
            message=message,
            child=child,
            beneficiary=child.beneficiary,
            actor=actor,
        )
        return alert

    resolve_alert_type(
        AlertType.ATTENDANCE,
        child=child,
        notes=(
            f"{absent} absence(s) in the last "
            f"{alert_rules.ATTENDANCE_WINDOW_DAYS} days (within threshold)."
        ),
    )
    return None


def sync_home_visit_pending(
    beneficiary, *, actor=None, today: date | None = None
) -> Alert | None:
    """Home-visit rule: a scheduled visit is past its scheduled date."""
    today = today or date.today()
    overdue = (
        HomeVisit.query.filter_by(
            beneficiary_id=beneficiary.id, status=VisitStatus.SCHEDULED
        )
        .filter(HomeVisit.scheduled_date < today)
        .order_by(HomeVisit.scheduled_date.asc(), HomeVisit.id.asc())
        .all()
    )

    if overdue:
        earliest = overdue[0]
        message = (
            f"Home visit pending: scheduled visit for "
            f"{beneficiary.full_name} was due on "
            f"{earliest.scheduled_date.isoformat()} "
            f"({alert_rules.HOME_VISIT_RULE_ID})."
        )
        alert, _ = upsert_alert(
            alert_type=AlertType.HOME_VISIT_PENDING,
            severity=alert_rules.HOME_VISIT_SEVERITY,
            message=message,
            beneficiary=beneficiary,
            actor=actor,
        )
        return alert

    resolve_alert_type(
        AlertType.HOME_VISIT_PENDING,
        beneficiary=beneficiary,
        notes="No overdue scheduled home visit.",
    )
    return None


# ---------------------------------------------------------------------------
# Evaluation entry points
# ---------------------------------------------------------------------------
def evaluate_child(child, *, actor=None) -> None:
    """Run every child-scoped rule (growth, vaccination, attendance)."""
    sync_growth_from_latest(child, actor=actor)
    sync_vaccination_alert(child, actor=actor)
    sync_attendance_alert(child, actor=actor)


def evaluate_beneficiary(beneficiary, *, actor=None) -> None:
    """Run the rules that apply to a beneficiary (child/mother + visits)."""
    if beneficiary.child is not None:
        evaluate_child(beneficiary.child, actor=actor)
    elif beneficiary.mother is not None:
        sync_maternal_alert(beneficiary.mother, actor=actor)
    sync_home_visit_pending(beneficiary, actor=actor)


def evaluate_inventory(centre=None, *, actor=None) -> None:
    """Run the low-stock rule for one centre (or every centre)."""
    query = Inventory.query
    if centre is not None:
        query = query.filter(Inventory.centre_id == centre.id)
    for inventory in query.all():
        sync_low_stock_alert(inventory, actor=actor)


def evaluate_all(*, centre=None, actor=None) -> dict:
    """Run every deterministic rule across a centre (or all centres).

    Intended for the explicit ``/alerts/scan`` action and the ``scan-alerts``
    CLI command.  Commits once and returns a small summary.
    """
    query = Beneficiary.query
    if centre is not None:
        query = query.filter(Beneficiary.centre_id == centre.id)
    beneficiaries = query.all()
    for beneficiary in beneficiaries:
        evaluate_beneficiary(beneficiary, actor=actor)
    evaluate_inventory(centre, actor=actor)
    db.session.commit()

    scope_centre_id = centre.id if centre is not None else None
    counts = status_counts(scope_centre_id=scope_centre_id)
    return {
        "beneficiaries": len(beneficiaries),
        "active_alerts": counts["ACTIVE"],
    }


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def list_alerts(
    *,
    scope_centre_id=None,
    statuses=None,
    alert_type=None,
    severity=None,
    assigned_to_id=None,
    beneficiary_id=None,
    child_id=None,
    search=None,
) -> list[Alert]:
    """Return alerts matching the supplied filters, newest first.

    ``scope_centre_id`` limits the result to alerts belonging to a centre's
    beneficiaries plus that centre's low-stock alerts (identified by the
    ``[inventory:<centre_id>:`` message marker).
    """
    query = Alert.query.outerjoin(
        Beneficiary, Alert.beneficiary_id == Beneficiary.id
    )
    if scope_centre_id is not None:
        marker = f"%[inventory:{scope_centre_id}:%"
        query = query.filter(
            or_(
                Beneficiary.centre_id == scope_centre_id,
                Alert.message.like(marker),
            )
        )
    if statuses:
        query = query.filter(Alert.status.in_(tuple(statuses)))
    if alert_type is not None:
        query = query.filter(Alert.alert_type == alert_type)
    if severity is not None:
        query = query.filter(Alert.severity == severity)
    if assigned_to_id is not None:
        query = query.filter(Alert.assigned_to_id == assigned_to_id)
    if beneficiary_id is not None:
        query = query.filter(Alert.beneficiary_id == beneficiary_id)
    if child_id is not None:
        query = query.filter(Alert.child_id == child_id)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            or_(Alert.message.ilike(like), Beneficiary.full_name.ilike(like))
        )
    return query.order_by(Alert.created_at.desc(), Alert.id.desc()).all()


def status_counts(*, scope_centre_id=None) -> dict:
    """Return alert counts by status plus ACTIVE/TOTAL convenience totals."""
    alerts = list_alerts(scope_centre_id=scope_centre_id)
    counts = {status.value: 0 for status in AlertStatus}
    for alert in alerts:
        counts[alert.status.value] += 1
    counts["TOTAL"] = len(alerts)
    counts["ACTIVE"] = sum(
        1 for alert in alerts if alert.status in ACTIVE_STATUSES
    )
    return counts


def get_alert(alert_id: int) -> Alert:
    """Return an alert or raise 404."""
    alert = db.session.get(Alert, alert_id)
    if alert is None:
        abort(404)
    return alert


def assignable_users(*, scope_centre_id=None) -> list[User]:
    """Return active users that may be assigned an alert.

    When ``scope_centre_id`` is supplied (an AWW's centre), centre-bound AWWs
    from other centres are excluded; ADMIN and SUPERVISOR remain available
    because they are global roles.
    """
    query = User.query.filter(
        User.is_active.is_(True),
        User.role.in_(ASSIGN_ROLES),
    )
    if scope_centre_id is not None:
        query = query.filter(
            or_(
                User.role != UserRole.AWW,
                User.centre_id == scope_centre_id,
            )
        )
    return query.order_by(User.full_name.asc()).all()


# ---------------------------------------------------------------------------
# Manual lifecycle
# ---------------------------------------------------------------------------
def assign_alert(alert: Alert, user: User, *, actor=None) -> Alert:
    """Assign (or reassign) an alert to ``user``.

    Server-side validation (independent of the UI dropdown) ensures the target
    is an active user with an allowed role, and that a centre-scoped AWW cannot
    assign an alert to a worker from another centre.  ADMIN/SUPERVISOR are
    global.
    """
    if alert.status in TERMINAL_STATUSES:
        raise ValidationError(
            {"assigned_to_id": "Reopen the alert before assigning it."}
        )
    if user is None or not user.is_active:
        raise ValidationError(
            {"assigned_to_id": "Selected user was not found or is inactive."}
        )
    if user.role not in ASSIGN_ROLES:
        raise ValidationError(
            {
                "assigned_to_id": (
                    "Alerts can only be assigned to an administrator, an "
                    "Anganwadi worker or a supervisor."
                )
            }
        )

    scope = scope_centre_id(actor) if actor is not None else None
    if (
        scope is not None
        and user.role == UserRole.AWW
        and user.centre_id != scope
    ):
        raise ValidationError(
            {
                "assigned_to_id": (
                    "You can only assign alerts to workers in your own centre."
                )
            }
        )

    alert.assigned_to = user
    db.session.commit()
    return alert


def set_alert_status(
    alert: Alert, new_status, *, notes=None, actor=None
) -> Alert:
    """Validate and apply a manual status change."""
    try:
        target = AlertStatus(new_status)
    except ValueError:
        raise ValidationError({"status": "Selected status is not valid."})

    if target != alert.status and target not in VALID_TRANSITIONS.get(
        alert.status, set()
    ):
        raise ValidationError(
            {
                "status": (
                    f"Cannot move an alert from {alert.status.value} "
                    f"to {target.value}."
                )
            }
        )

    alert.status = target
    if target in TERMINAL_STATUSES:
        alert.resolved_at = alert.resolved_at or datetime.utcnow()
        if notes is not None:
            alert.resolution_notes = notes
    else:
        alert.resolved_at = None
        alert.resolution_notes = None
    db.session.commit()
    return alert


def resolve_alert(alert: Alert, *, notes=None, actor=None) -> Alert:
    """Resolve an alert with optional resolution notes."""
    return set_alert_status(alert, AlertStatus.RESOLVED, notes=notes, actor=actor)


def dismiss_alert(alert: Alert, *, notes=None, actor=None) -> Alert:
    """Dismiss an alert with optional notes."""
    return set_alert_status(alert, AlertStatus.DISMISSED, notes=notes, actor=actor)


def reopen_alert(alert: Alert, *, actor=None) -> Alert:
    """Reopen a resolved/dismissed alert."""
    return set_alert_status(alert, AlertStatus.OPEN, actor=actor)


__all__ = [
    "ACTIVE_STATUSES",
    "TERMINAL_STATUSES",
    "VALID_TRANSITIONS",
    "assign_alert",
    "assignable_users",
    "dismiss_alert",
    "evaluate_all",
    "evaluate_beneficiary",
    "evaluate_child",
    "evaluate_inventory",
    "get_alert",
    "list_alerts",
    "open_alert",
    "reopen_alert",
    "resolve_alert",
    "resolve_alert_type",
    "set_alert_status",
    "status_counts",
    "sync_attendance_alert",
    "sync_growth_alert",
    "sync_growth_from_latest",
    "sync_home_visit_pending",
    "sync_low_stock_alert",
    "sync_maternal_alert",
    "sync_vaccination_alert",
    "upsert_alert",
]