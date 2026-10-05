"""Dashboard business logic (Phase 11).

Every metric here is calculated from the database — nothing is hard-coded.
The module exposes one builder per role plus a reusable **centre comparison**
and the chart-ready series used by the templates:

* :func:`aww_dashboard` — one centre's operational view;
* :func:`supervisor_dashboard` — multi-centre monitoring (also used by OFFICER);
* :func:`admin_dashboard` — whole-system overview.

All list/aggregate helpers accept ``centre_id`` so an AWW's results are scoped
to their own centre, while a centre filter can be applied for the supervisor /
officer views (``None`` = all centres).
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, or_

from app.extensions import db
from app.models import (
    Alert,
    AnganwadiCentre,
    Attendance,
    Beneficiary,
    BeneficiaryScheme,
    Child,
    HomeVisit,
    Inventory,
    Mother,
    NutritionDistribution,
    User,
    Vaccination,
    WelfareScheme,
)
from app.utils.constants import (
    AlertStatus,
    AttendanceStatus,
    BeneficiaryType,
    RecordStatus,
    SchemeStatus,
    UserRole,
    VaccinationStatus,
    VisitStatus,
)


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------
def _beneficiary_query(centre_id=None):
    query = Beneficiary.query
    if centre_id is not None:
        query = query.filter(Beneficiary.centre_id == centre_id)
    return query


def _vaccination_query(centre_id=None):
    """Vaccinations joined to the child's centre."""
    query = Vaccination.query.join(
        Child, Vaccination.child_id == Child.id
    ).join(Beneficiary, Child.beneficiary_id == Beneficiary.id)
    if centre_id is not None:
        query = query.filter(Beneficiary.centre_id == centre_id)
    return query


def _attendance_query(centre_id=None):
    query = Attendance.query
    if centre_id is not None:
        query = query.filter(Attendance.centre_id == centre_id)
    return query


def _visit_query(centre_id=None):
    query = HomeVisit.query
    if centre_id is not None:
        query = query.filter(HomeVisit.centre_id == centre_id)
    return query


def _inventory_query(centre_id=None):
    query = Inventory.query
    if centre_id is not None:
        query = query.filter(Inventory.centre_id == centre_id)
    return query


def _distribution_query(centre_id=None):
    query = NutritionDistribution.query
    if centre_id is not None:
        query = query.filter(NutritionDistribution.centre_id == centre_id)
    return query


def _alert_query(centre_id=None):
    """Alerts scoped to a centre's beneficiaries plus its low-stock alerts."""
    query = Alert.query.outerjoin(
        Beneficiary, Alert.beneficiary_id == Beneficiary.id
    )
    if centre_id is not None:
        marker = f"%[inventory:{centre_id}:%"
        query = query.filter(
            or_(
                Beneficiary.centre_id == centre_id,
                Alert.message.like(marker),
            )
        )
    return query


def is_low_stock(inventory: Inventory) -> bool:
    """True only when a *configured* minimum (> 0) has been reached."""
    minimum = inventory.minimum_stock or 0
    return minimum > 0 and inventory.is_low_stock


# ---------------------------------------------------------------------------
# Beneficiaries
# ---------------------------------------------------------------------------
def beneficiary_counts(centre_id=None) -> dict:
    query = _beneficiary_query(centre_id)
    children = query.filter(
        Beneficiary.beneficiary_type == BeneficiaryType.CHILD
    ).count()
    pregnant = query.filter(
        Beneficiary.beneficiary_type == BeneficiaryType.PREGNANT_WOMAN
    ).count()
    lactating = query.filter(
        Beneficiary.beneficiary_type == BeneficiaryType.LACTATING_MOTHER
    ).count()
    total = query.count()
    active = query.filter(Beneficiary.status == RecordStatus.ACTIVE).count()
    return {
        "children": children,
        "pregnant": pregnant,
        "lactating": lactating,
        "mothers": pregnant + lactating,
        "total": total,
        "active": active,
        "inactive": total - active,
    }


def recent_registrations(*, centre_id=None, days: int = 30, limit: int = 8):
    """Beneficiaries registered in the last ``days``, newest first."""
    since = date.today() - timedelta(days=days)
    return (
        _beneficiary_query(centre_id)
        .filter(Beneficiary.registration_date >= since)
        .order_by(
            Beneficiary.registration_date.desc(), Beneficiary.id.desc()
        )
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
def alert_counts(centre_id=None) -> dict:
    rows = (
        _alert_query(centre_id)
        .with_entities(Alert.status, func.count(Alert.id))
        .group_by(Alert.status)
        .all()
    )
    counts = {status.value: 0 for status in AlertStatus}
    for status, count in rows:
        counts[status.value] = count
    counts["TOTAL"] = sum(counts.values())
    counts["ACTIVE"] = (
        counts[AlertStatus.OPEN.value]
        + counts[AlertStatus.IN_PROGRESS.value]
    )
    # "Alert resolution": resolved / (resolved + dismissed + active).
    handled = counts["TOTAL"] - counts[AlertStatus.DISMISSED.value]
    counts["RESOLUTION_RATE"] = _percentage(counts[AlertStatus.RESOLVED.value], handled)
    return counts


def open_alerts(centre_id=None, *, limit: int = 8):
    """Active alerts for the dashboard's recent-alerts card."""
    return (
        _alert_query(centre_id)
        .filter(Alert.status.in_([AlertStatus.OPEN, AlertStatus.IN_PROGRESS]))
        .order_by(Alert.created_at.desc(), Alert.id.desc())
        .limit(limit)
        .all()
    )


def _percentage(part: int, whole: int):
    return round(part / whole * 100, 1) if whole else None


# ---------------------------------------------------------------------------
# Visits
# ---------------------------------------------------------------------------
def visit_metrics(centre_id=None) -> dict:
    rows = (
        _visit_query(centre_id)
        .with_entities(HomeVisit.status, func.count(HomeVisit.id))
        .group_by(HomeVisit.status)
        .all()
    )
    counts = {status.value: 0 for status in VisitStatus}
    for status, count in rows:
        counts[status.value] = count
    counts["TOTAL"] = sum(counts.values())
    counts["PENDING"] = counts[VisitStatus.SCHEDULED.value]

    overdue = (
        _visit_query(centre_id)
        .filter(
            HomeVisit.status == VisitStatus.SCHEDULED,
            HomeVisit.scheduled_date < date.today(),
        )
        .count()
    )
    counts["OVERDUE"] = overdue
    return counts


def pending_visits_list(centre_id=None, *, limit: int = 6):
    """Upcoming/overdue scheduled visits, soonest first."""
    return (
        _visit_query(centre_id)
        .filter(HomeVisit.status == VisitStatus.SCHEDULED)
        .order_by(HomeVisit.scheduled_date.asc(), HomeVisit.id.asc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Vaccination
# ---------------------------------------------------------------------------
def vaccination_metrics(centre_id=None, *, days: int = 30) -> dict:
    base = _vaccination_query(centre_id)
    today = date.today()
    horizon = today + timedelta(days=days)

    total = base.count()
    completed = base.filter(
        Vaccination.status == VaccinationStatus.COMPLETED
    ).count()
    missed = base.filter(Vaccination.status == VaccinationStatus.MISSED).count()
    upcoming = base.filter(
        Vaccination.status.in_(
            [VaccinationStatus.UPCOMING, VaccinationStatus.DUE]
        ),
        Vaccination.scheduled_date >= today,
        Vaccination.scheduled_date <= horizon,
    ).count()
    overdue = base.filter(
        Vaccination.status.in_(
            [VaccinationStatus.UPCOMING, VaccinationStatus.DUE]
        ),
        Vaccination.scheduled_date < today,
    ).count()

    rows = (
        base.with_entities(Vaccination.status, func.count(Vaccination.id))
        .group_by(Vaccination.status)
        .all()
    )
    breakdown = {status.value: 0 for status in VaccinationStatus}
    for status, count in rows:
        breakdown[status.value] = count

    return {
        "total": total,
        "completed": completed,
        "missed": missed,
        "upcoming": upcoming,
        "overdue": overdue,
        "coverage": _percentage(completed, total),
        "breakdown": breakdown,
    }


def upcoming_vaccinations(centre_id=None, *, days: int = 30, limit: int = 8):
    """Doses scheduled within the next ``days`` (UPCOMING/DUE), soonest first."""
    today = date.today()
    horizon = today + timedelta(days=days)
    return (
        _vaccination_query(centre_id)
        .filter(
            Vaccination.status.in_(
                [VaccinationStatus.UPCOMING, VaccinationStatus.DUE]
            ),
            Vaccination.scheduled_date >= today,
            Vaccination.scheduled_date <= horizon,
        )
        .order_by(Vaccination.scheduled_date.asc(), Vaccination.id.asc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
def attendance_metrics(centre_id=None, *, days: int = 30) -> dict:
    today = date.today()
    start = today - timedelta(days=days - 1)
    query = _attendance_query(centre_id).filter(
        Attendance.attendance_date >= start,
        Attendance.attendance_date <= today,
    )
    rows = (
        query.with_entities(Attendance.status, func.count(Attendance.id))
        .group_by(Attendance.status)
        .all()
    )
    counts = {status.value: 0 for status in AttendanceStatus}
    for status, count in rows:
        counts[status.value] = count
    present = counts[AttendanceStatus.PRESENT.value]
    absent = counts[AttendanceStatus.ABSENT.value]
    total = present + absent
    return {
        "present": present,
        "absent": absent,
        "total": total,
        "percentage": _percentage(present, total),
    }


def attendance_trend(centre_id=None, *, days: int = 14) -> dict:
    """Chart-ready daily present/absent series for the last ``days`` days."""
    today = date.today()
    start = today - timedelta(days=days - 1)
    rows = (
        _attendance_query(centre_id)
        .filter(
            Attendance.attendance_date >= start,
            Attendance.attendance_date <= today,
        )
        .with_entities(
            Attendance.attendance_date,
            Attendance.status,
            func.count(Attendance.id),
        )
        .group_by(Attendance.attendance_date, Attendance.status)
        .all()
    )

    lookup: dict[date, dict[str, int]] = {}
    for day, status, count in rows:
        lookup.setdefault(day, {"present": 0, "absent": 0})
        key = (
            "present"
            if status == AttendanceStatus.PRESENT
            else "absent"
        )
        lookup[day][key] = count

    labels, present, absent = [], [], []
    for offset in range(days):
        day = start + timedelta(days=offset)
        labels.append(day.isoformat())
        present.append(lookup.get(day, {}).get("present", 0))
        absent.append(lookup.get(day, {}).get("absent", 0))
    return {"labels": labels, "present": present, "absent": absent}


# ---------------------------------------------------------------------------
# Nutrition
# ---------------------------------------------------------------------------
def nutrition_metrics(centre_id=None, *, days: int = 30) -> dict:
    inventory = _inventory_query(centre_id).all()
    low_stock = [row for row in inventory if is_low_stock(row)]

    today = date.today()
    since = today - timedelta(days=days)
    distributions = (
        _distribution_query(centre_id)
        .filter(NutritionDistribution.distribution_date >= since)
        .all()
    )
    total_quantity = sum(float(d.quantity or 0) for d in distributions)

    by_item: dict[str, float] = {}
    for distribution in distributions:
        name = distribution.item.name if distribution.item else "Unknown"
        by_item[name] = by_item.get(name, 0) + float(distribution.quantity or 0)
    top_items = sorted(by_item.items(), key=lambda row: (-row[1], row[0]))

    return {
        "inventory_rows": len(inventory),
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock[:8],
        "distribution_count": len(distributions),
        "distributed_quantity": round(total_quantity, 2),
        "top_items": top_items[:8],
    }


# ---------------------------------------------------------------------------
# Schemes
# ---------------------------------------------------------------------------
def scheme_metrics(centre_id=None) -> dict:
    query = BeneficiaryScheme.query.join(
        Beneficiary, BeneficiaryScheme.beneficiary_id == Beneficiary.id
    )
    if centre_id is not None:
        query = query.filter(Beneficiary.centre_id == centre_id)
    rows = (
        query.with_entities(
            BeneficiaryScheme.status, func.count(BeneficiaryScheme.id)
        )
        .group_by(BeneficiaryScheme.status)
        .all()
    )
    counts = {status.value: 0 for status in SchemeStatus}
    for status, count in rows:
        counts[status.value] = count
    counts["TOTAL"] = sum(counts.values())
    counts["ACTIVE_SCHEMES"] = WelfareScheme.query.filter_by(
        is_active=True
    ).count()
    return counts


# ---------------------------------------------------------------------------
# Users / centres (ADMIN)
# ---------------------------------------------------------------------------
def user_metrics() -> dict:
    rows = (
        User.query.filter(User.is_active.is_(True))
        .with_entities(User.role, func.count(User.id))
        .group_by(User.role)
        .all()
    )
    counts = {role.value: 0 for role in UserRole}
    for role, count in rows:
        counts[role.value] = count
    counts["TOTAL"] = sum(counts.values())
    return counts


def centre_metrics() -> dict:
    total = AnganwadiCentre.query.count()
    active = AnganwadiCentre.query.filter_by(is_active=True).count()
    return {"total": total, "active": active, "inactive": total - active}


def active_centres():
    """Active centres for the filter dropdown / comparison rows."""
    return (
        AnganwadiCentre.query.filter_by(is_active=True)
        .order_by(AnganwadiCentre.name.asc())
        .all()
    )


def get_centre(centre_id):
    """Return a centre by id or ``None`` (also used by the route filter)."""
    if centre_id is None:
        return None
    return db.session.get(AnganwadiCentre, centre_id)


# ---------------------------------------------------------------------------
# Centre comparison
# ---------------------------------------------------------------------------
def centre_comparison(centres=None) -> list[dict]:
    """One deterministic metrics row per centre, ordered by name."""
    centres = centres if centres is not None else active_centres()
    rows = []
    for centre in centres:
        beneficiaries = beneficiary_counts(centre.id)
        vaccination = vaccination_metrics(centre.id)
        attendance = attendance_metrics(centre.id)
        alerts = alert_counts(centre.id)
        visits = visit_metrics(centre.id)
        nutrition = nutrition_metrics(centre.id)
        rows.append(
            {
                "centre": centre,
                "children": beneficiaries["children"],
                "mothers": beneficiaries["mothers"],
                "open_alerts": alerts["ACTIVE"],
                "vaccination_coverage": vaccination["coverage"],
                "distributions": nutrition["distribution_count"],
                "pending_visits": visits["PENDING"],
                "attendance_percentage": attendance["percentage"],
                "low_stock": nutrition["low_stock_count"],
            }
        )
    return rows


def comparison_chart(comparison: list[dict]) -> dict:
    """Chart.js-ready children/mothers series for the comparison rows."""
    return {
        "labels": [row["centre"].name for row in comparison],
        "children": [row["children"] for row in comparison],
        "mothers": [row["mothers"] for row in comparison],
        "coverage": [row["vaccination_coverage"] for row in comparison],
    }


# ---------------------------------------------------------------------------
# Role dashboards
# ---------------------------------------------------------------------------
def aww_dashboard(centre_id=None) -> dict:
    """Operational view for one centre (the AWW's own centre)."""
    centre = get_centre(centre_id)
    return {
        "centre": centre,
        "centres": active_centres(),
        "beneficiaries": beneficiary_counts(centre_id),
        "alerts": alert_counts(centre_id),
        "open_alerts": open_alerts(centre_id),
        "visits": visit_metrics(centre_id),
        "pending_visits": pending_visits_list(centre_id),
        "vaccination": vaccination_metrics(centre_id),
        "upcoming_vaccinations": upcoming_vaccinations(centre_id),
        "attendance": attendance_metrics(centre_id),
        "attendance_trend": attendance_trend(centre_id),
        "nutrition": nutrition_metrics(centre_id),
        "recent": recent_registrations(centre_id=centre_id),
        "schemes": scheme_metrics(centre_id),
    }


def supervisor_dashboard(centre_id=None) -> dict:
    """Multi-centre monitoring (used by SUPERVISOR and OFFICER)."""
    centres = active_centres()
    scope_centres = (
        [centre for centre in centres if centre.id == centre_id]
        if centre_id is not None
        else centres
    )
    comparison = centre_comparison(scope_centres)
    return {
        "centres": centres,
        "total_centres": centre_metrics(),
        "beneficiaries": beneficiary_counts(centre_id),
        "alerts": alert_counts(centre_id),
        "open_alerts": open_alerts(centre_id),
        "visits": visit_metrics(centre_id),
        "pending_visits": pending_visits_list(centre_id),
        "vaccination": vaccination_metrics(centre_id),
        "attendance": attendance_metrics(centre_id),
        "attendance_trend": attendance_trend(centre_id),
        "nutrition": nutrition_metrics(centre_id),
        "schemes": scheme_metrics(centre_id),
        "comparison": comparison,
        "comparison_chart": comparison_chart(comparison),
        "recent": recent_registrations(centre_id=centre_id),
    }


def admin_dashboard() -> dict:
    """Whole-system overview for the administrator."""
    centres = active_centres()
    comparison = centre_comparison(centres)
    return {
        "centres": centres,
        "total_centres": centre_metrics(),
        "users": user_metrics(),
        "beneficiaries": beneficiary_counts(),
        "alerts": alert_counts(),
        "open_alerts": open_alerts(),
        "visits": visit_metrics(),
        "pending_visits": pending_visits_list(),
        "vaccination": vaccination_metrics(),
        "attendance": attendance_metrics(),
        "attendance_trend": attendance_trend(),
        "nutrition": nutrition_metrics(),
        "schemes": scheme_metrics(),
        "comparison": comparison,
        "comparison_chart": comparison_chart(comparison),
        "recent": recent_registrations(),
    }


__all__ = [
    "admin_dashboard",
    "attendance_metrics",
    "attendance_trend",
    "alert_counts",
    "aww_dashboard",
    "beneficiary_counts",
    "centre_comparison",
    "centre_metrics",
    "comparison_chart",
    "get_centre",
    "is_low_stock",
    "nutrition_metrics",
    "open_alerts",
    "pending_visits_list",
    "recent_registrations",
    "scheme_metrics",
    "supervisor_dashboard",
    "upcoming_vaccinations",
    "user_metrics",
    "vaccination_metrics",
    "visit_metrics",
    "active_centres",
]
