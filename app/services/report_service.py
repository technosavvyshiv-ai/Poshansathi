"""Report data builders and CSV serialisers (Phase 12).

Reuses the existing Phase 4–11 services (growth, vaccination, maternal,
nutrition, attendance, schemes, visits) so a report is always the same data the
module pages show.  Each ``*_report`` function returns a plain dict the route
renders (printable HTML) or passes to the matching ``*_csv`` function.

CSV uses only the standard library (``csv``/``io``) — no new dependency.
PDF/XLSX are intentionally omitted: they would require new third-party packages
for no functional gain over printable HTML + CSV.
"""

from __future__ import annotations

import csv
import io
from calendar import monthrange
from datetime import date

from app.extensions import db
from app.models import (
    Attendance,
    Beneficiary,
    BeneficiaryScheme,
    Child,
    GrowthRecord,
    MaternalHealthRecord,
    Mother,
    NutritionDistribution,
    Vaccination,
)
from app.services import (
    alert_service,
    attendance_service,
    growth_service,
    maternal_service,
    nutrition_service,
    scheme_service,
    vaccination_service,
    visit_service,
)
from app.utils.constants import (
    AttendanceStatus,
    SchemeStatus,
    VaccinationStatus,
    VisitStatus,
)


# ---------------------------------------------------------------------------
# CSV helper
# ---------------------------------------------------------------------------
def rows_to_csv(headers, rows) -> str:
    """Serialise ``headers`` + ``rows`` to a CSV string."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def _in_range(value, start, end) -> bool:
    if value is None:
        return False
    if start is not None and value < start:
        return False
    if end is not None and value > end:
        return False
    return True


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return the first and last day of ``year``/``month``."""
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


# ---------------------------------------------------------------------------
# Child profile report
# ---------------------------------------------------------------------------
def child_profile_report(beneficiary: Beneficiary) -> dict:
    """Aggregate a beneficiary's profile and related records."""
    child = beneficiary.child
    return {
        "beneficiary": beneficiary,
        "child": child,
        "growth": growth_service.build_history(child) if child else [],
        "vaccination": vaccination_service.build_history(child) if child else [],
        "vaccination_summary": (
            vaccination_service.summary(child) if child else None
        ),
        "attendance_summary": (
            attendance_service.child_summary(child) if child else None
        ),
        "schemes": scheme_service.links_for_beneficiary(beneficiary),
        "alerts": list(beneficiary.alerts),
        "visits": visit_service.visits_for_beneficiary(beneficiary),
        "interventions": visit_service.interventions_for_beneficiary(
            beneficiary
        ),
    }


def child_profile_csv(report: dict) -> str:
    beneficiary = report["beneficiary"]
    rows = [
        ["Beneficiary", "Full name", beneficiary.full_name],
        ["Beneficiary", "Type", beneficiary.beneficiary_type.value],
        ["Beneficiary", "Date of birth", beneficiary.date_of_birth],
        ["Beneficiary", "Gender", beneficiary.gender.value if beneficiary.gender else ""],
        ["Beneficiary", "Centre", beneficiary.centre.name if beneficiary.centre else ""],
        ["Beneficiary", "Guardian", beneficiary.guardian_name or ""],
        ["Beneficiary", "Contact", beneficiary.contact or ""],
        ["Beneficiary", "Status", beneficiary.status.value],
    ]
    if report["vaccination_summary"]:
        summary = report["vaccination_summary"]
        rows.append(["Vaccination", "Completed", summary["completed"]])
        rows.append(["Vaccination", "Pending", summary["pending"]])
        rows.append(["Vaccination", "Missed", summary["missed"]])
    if report["attendance_summary"]:
        summary = report["attendance_summary"]
        rows.append(["Attendance", "Present", summary["present"]])
        rows.append(["Attendance", "Absent", summary["absent"]])
        rows.append(
            ["Attendance", "Percentage", summary["attendance_percentage"]]
        )
    rows.append(["Schemes", "Linked schemes", len(report["schemes"])])
    rows.append(["Alerts", "Total alerts", len(report["alerts"])])
    rows.append(["Visits", "Home visits", len(report["visits"])])
    rows.append(["Interventions", "Recorded", len(report["interventions"])])
    return rows_to_csv(["Section", "Field", "Value"], rows)


# ---------------------------------------------------------------------------
# Growth report
# ---------------------------------------------------------------------------
def growth_report(child: Child, *, start=None, end=None) -> dict:
    records = [
        record
        for record in growth_service.records_for_child(child, newest_first=False)
        if _in_range(record.measurement_date, start, end)
    ]
    history = [growth_service.serialize_record(child, record) for record in records]
    return {
        "child": child,
        "beneficiary": child.beneficiary,
        "history": history,
        "concerning": sum(1 for item in history if item["concerning"]),
        "rule_id": growth_service.DEMO_RULE_ID,
        "start": start,
        "end": end,
    }


def growth_csv(report: dict) -> str:
    rows = [
        [
            item["record"].measurement_date,
            item["age_label"],
            item["record"].weight_kg,
            item["record"].height_cm,
            item["record"].muac_cm,
            item["status"].value if item["status"] else "",
            item["record"].notes or "",
        ]
        for item in report["history"]
    ]
    return rows_to_csv(
        ["Date", "Age", "Weight (kg)", "Height (cm)", "MUAC (cm)", "Status", "Notes"],
        rows,
    )


# ---------------------------------------------------------------------------
# Vaccination report
# ---------------------------------------------------------------------------
def vaccination_report(
    child: Child, *, status=None, start=None, end=None
) -> dict:
    items = []
    for item in vaccination_service.build_history(child):
        record = item["record"]
        if status and item["display_status"] != status:
            continue
        when = record.administered_date or record.scheduled_date
        if (start or end) and not _in_range(when, start, end):
            continue
        items.append(item)
    return {
        "child": child,
        "beneficiary": child.beneficiary,
        "history": items,
        "summary": vaccination_service.summary(child),
        "status": status,
        "start": start,
        "end": end,
    }


def vaccination_csv(report: dict) -> str:
    rows = [
        [
            item["record"].vaccine_name,
            item["record"].dose_number,
            item["record"].scheduled_date,
            item["record"].administered_date,
            item["display_label"],
            item["record"].notes or "",
        ]
        for item in report["history"]
    ]
    return rows_to_csv(
        ["Vaccine", "Dose", "Scheduled", "Administered", "Status", "Notes"], rows
    )


# ---------------------------------------------------------------------------
# Maternal health report
# ---------------------------------------------------------------------------
def maternal_report(mother: Mother, *, start=None, end=None) -> dict:
    items = [
        item
        for item in maternal_service.build_history(mother)
        if _in_range(item["record"].visit_date, start, end)
    ]
    return {
        "mother": mother,
        "beneficiary": mother.beneficiary,
        "history": items,
        "summary": maternal_service.summary(mother),
        "start": start,
        "end": end,
    }


def maternal_csv(report: dict) -> str:
    rows = [
        [
            item["record"].visit_date,
            item["record"].pregnancy_month,
            item["record"].weight_kg,
            item["record"].haemoglobin,
            item["record"].systolic_bp,
            item["record"].diastolic_bp,
            item["risk_label"],
            item["record"].next_follow_up_date,
            item["record"].notes or "",
        ]
        for item in report["history"]
    ]
    return rows_to_csv(
        [
            "Visit date", "Pregnancy month", "Weight (kg)", "Haemoglobin",
            "Systolic", "Diastolic", "Risk", "Next follow-up", "Notes",
        ],
        rows,
    )


# ---------------------------------------------------------------------------
# Nutrition distribution report
# ---------------------------------------------------------------------------
def nutrition_report(
    *, centre_id=None, item_id=None, beneficiary_id=None, start=None, end=None
) -> dict:
    rows = nutrition_service.distributions_query(
        scope_centre_id=centre_id,
        item_id=item_id,
        beneficiary_id=beneficiary_id,
    )
    rows = [
        row for row in rows if _in_range(row.distribution_date, start, end)
    ]
    total_quantity = round(sum(float(row.quantity or 0) for row in rows), 2)
    return {
        "rows": rows,
        "count": len(rows),
        "total_quantity": total_quantity,
        "centre_id": centre_id,
        "item_id": item_id,
        "beneficiary_id": beneficiary_id,
        "start": start,
        "end": end,
    }


def nutrition_csv(report: dict) -> str:
    rows = [
        [
            row.distribution_date,
            row.beneficiary.full_name if row.beneficiary else "",
            row.centre.name if row.centre else "",
            row.item.name if row.item else "",
            row.quantity,
            row.item.unit if row.item else "",
            row.worker.full_name if row.worker else "",
            row.notes or "",
        ]
        for row in report["rows"]
    ]
    return rows_to_csv(
        [
            "Date", "Beneficiary", "Centre", "Item", "Quantity", "Unit",
            "Worker", "Notes",
        ],
        rows,
    )


# ---------------------------------------------------------------------------
# Monthly centre report
# ---------------------------------------------------------------------------
def monthly_centre_report(centre, year: int, month: int) -> dict:
    start, end = month_bounds(year, month)
    centre_id = centre.id

    attendance_rows = (
        db.session.query(Attendance.status)
        .filter(
            Attendance.centre_id == centre_id,
            Attendance.attendance_date >= start,
            Attendance.attendance_date <= end,
        )
        .all()
    )
    present = sum(
        1 for (status,) in attendance_rows if status == AttendanceStatus.PRESENT
    )
    absent = len(attendance_rows) - present

    distributions = (
        NutritionDistribution.query.filter(
            NutritionDistribution.centre_id == centre_id,
            NutritionDistribution.distribution_date >= start,
            NutritionDistribution.distribution_date <= end,
        )
        .all()
    )

    alerts = [
        alert
        for alert in alert_service.list_alerts(scope_centre_id=centre_id)
        if alert.created_at and start <= alert.created_at.date() <= end
    ]

    visits = visit_service.visits_query(centre_id=centre_id)

    vaccinations_administered = (
        Vaccination.query.join(Child, Vaccination.child_id == Child.id)
        .join(Beneficiary, Child.beneficiary_id == Beneficiary.id)
        .filter(
            Beneficiary.centre_id == centre_id,
            Vaccination.status == VaccinationStatus.COMPLETED,
            Vaccination.administered_date >= start,
            Vaccination.administered_date <= end,
        )
        .count()
    )
    growth_records = (
        GrowthRecord.query.join(Child, GrowthRecord.child_id == Child.id)
        .join(Beneficiary, Child.beneficiary_id == Beneficiary.id)
        .filter(
            Beneficiary.centre_id == centre_id,
            GrowthRecord.measurement_date >= start,
            GrowthRecord.measurement_date <= end,
        )
        .count()
    )
    maternal_records = (
        MaternalHealthRecord.query.join(
            Mother, MaternalHealthRecord.mother_id == Mother.id
        )
        .join(Beneficiary, Mother.beneficiary_id == Beneficiary.id)
        .filter(
            Beneficiary.centre_id == centre_id,
            MaternalHealthRecord.visit_date >= start,
            MaternalHealthRecord.visit_date <= end,
        )
        .count()
    )

    metrics = [
        ("New registrations", Beneficiary.query.filter(
            Beneficiary.centre_id == centre_id,
            Beneficiary.registration_date >= start,
            Beneficiary.registration_date <= end,
        ).count()),
        ("Total beneficiaries", Beneficiary.query.filter_by(centre_id=centre_id).count()),
        ("Growth measurements", growth_records),
        ("Vaccinations administered", vaccinations_administered),
        ("Maternal (ANC) records", maternal_records),
        ("Attendance present", present),
        ("Attendance absent", absent),
        ("Attendance %", round(present / (present + absent) * 100, 1) if (present + absent) else None),
        ("Nutrition distributions", len(distributions)),
        ("Quantity distributed", round(sum(float(d.quantity or 0) for d in distributions), 2)),
        ("Alerts raised", len(alerts)),
        ("Alerts resolved", sum(1 for a in alerts if a.status.value == "RESOLVED")),
        ("Home visits scheduled", sum(1 for v in visits if start <= v.scheduled_date <= end)),
        ("Home visits completed", sum(
            1 for v in visits
            if v.completed_date and start <= v.completed_date <= end
        )),
    ]
    return {
        "centre": centre,
        "year": year,
        "month": month,
        "start": start,
        "end": end,
        "metrics": metrics,
    }


def monthly_centre_csv(report: dict) -> str:
    return rows_to_csv(
        ["Centre", "Month", "Metric", "Value"],
        [
            [report["centre"].name, f"{report['year']:04d}-{report['month']:02d}", name, value]
            for name, value in report["metrics"]
        ],
    )


# ---------------------------------------------------------------------------
# Scheme report
# ---------------------------------------------------------------------------
def scheme_report(*, centre_id=None, scheme_id=None, status=None) -> dict:
    query = BeneficiaryScheme.query.join(
        Beneficiary, BeneficiaryScheme.beneficiary_id == Beneficiary.id
    )
    if centre_id is not None:
        query = query.filter(Beneficiary.centre_id == centre_id)
    if scheme_id is not None:
        query = query.filter(BeneficiaryScheme.scheme_id == scheme_id)
    if status is not None:
        query = query.filter(BeneficiaryScheme.status == status)

    rows = query.order_by(
        Beneficiary.full_name.asc(), BeneficiaryScheme.id.asc()
    ).all()
    counts = {scheme_status.value: 0 for scheme_status in SchemeStatus}
    for link in rows:
        counts[link.status.value] += 1
    counts["TOTAL"] = len(rows)
    return {
        "rows": rows,
        "counts": counts,
        "centre_id": centre_id,
        "scheme_id": scheme_id,
        "status": status,
    }


def scheme_csv(report: dict) -> str:
    rows = [
        [
            link.beneficiary.full_name if link.beneficiary else "",
            link.beneficiary.centre.name if link.beneficiary and link.beneficiary.centre else "",
            link.scheme.name if link.scheme else "",
            link.scheme.category if link.scheme else "",
            link.status.value,
            link.applied_date,
            link.notes or "",
        ]
        for link in report["rows"]
    ]
    return rows_to_csv(
        [
            "Beneficiary", "Centre", "Scheme", "Category", "Status",
            "Applied date", "Notes",
        ],
        rows,
    )


__all__ = [
    "child_profile_csv",
    "child_profile_report",
    "growth_csv",
    "growth_report",
    "maternal_csv",
    "maternal_report",
    "month_bounds",
    "monthly_centre_csv",
    "monthly_centre_report",
    "nutrition_csv",
    "nutrition_report",
    "rows_to_csv",
    "scheme_csv",
    "scheme_report",
    "vaccination_csv",
    "vaccination_report",
]
