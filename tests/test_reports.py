"""Phase 12 report tests: data builders, filters, CSV export and scoping."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    Alert,
    AnganwadiCentre,
    Attendance,
    Beneficiary,
    BeneficiaryScheme,
    Child,
    GrowthRecord,
    HomeVisit,
    Inventory,
    MaternalHealthRecord,
    Mother,
    NutritionDistribution,
    NutritionItem,
    User,
    Vaccination,
    WelfareScheme,
)
from app.services import report_service
from app.utils.constants import (
    AlertSeverity,
    AlertType,
    AttendanceStatus,
    BeneficiaryType,
    Gender,
    NutritionalStatus,
    RecordStatus,
    SchemeStatus,
    UserRole,
    VaccinationStatus,
    VisitStatus,
    VisitType,
)

PASSWORD = "password123"
TODAY = date.today()


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def centre(db):
    centre = AnganwadiCentre(name="Report Centre A", code="RPA-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def other_centre(db):
    centre = AnganwadiCentre(name="Report Centre B", code="RPB-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def make_user(db):
    def make(username, role=UserRole.AWW, centre=None):
        user = User(
            full_name=f"Test {username}",
            username=username,
            role=role,
            centre=centre,
            is_active=True,
        )
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        return user

    return make


@pytest.fixture()
def make_child(db):
    def make(centre, name="Report Child", registered=None):
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=BeneficiaryType.CHILD,
            full_name=name,
            date_of_birth=TODAY - timedelta(days=730),
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=registered or TODAY,
        )
        child = Child(beneficiary=beneficiary)
        db.session.add(child)
        db.session.commit()
        return child

    return make


@pytest.fixture()
def make_mother(db):
    def make(centre, name="Report Mother"):
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=BeneficiaryType.PREGNANT_WOMAN,
            full_name=name,
            date_of_birth=TODAY - timedelta(days=365 * 25),
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=TODAY,
        )
        mother = Mother(beneficiary=beneficiary)
        db.session.add(mother)
        db.session.commit()
        return mother

    return make


@pytest.fixture()
def make_item(db):
    def make(name="Report Ration", unit="kg"):
        item = NutritionItem(name=name, unit=unit, is_active=True)
        db.session.add(item)
        db.session.commit()
        return item

    return make


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


# ---------------------------------------------------------------------------
# Data-builder unit tests
# ---------------------------------------------------------------------------
def test_child_profile_report_aggregates(db, centre, make_child):
    child = make_child(centre)
    db.session.add_all(
        [
            GrowthRecord(
                child_id=child.id, measurement_date=TODAY, weight_kg=Decimal("10.0")
            ),
            Vaccination(
                child_id=child.id, vaccine_name="BCG", dose_number=1,
                scheduled_date=TODAY, status=VaccinationStatus.UPCOMING,
            ),
            Attendance(
                child_id=child.id, centre_id=centre.id,
                attendance_date=TODAY, status=AttendanceStatus.PRESENT,
            ),
        ]
    )
    db.session.commit()

    report = report_service.child_profile_report(child.beneficiary)
    assert report["child"].id == child.id
    assert len(report["growth"]) == 1
    assert len(report["vaccination"]) == 1
    assert report["attendance_summary"]["present"] == 1
    assert report["vaccination_summary"]["total"] == 1


def test_growth_report_filters_by_date(db, centre, make_child):
    child = make_child(centre)
    db.session.add_all(
        [
            GrowthRecord(
                child_id=child.id, measurement_date=TODAY, weight_kg=Decimal("10.0")
            ),
            GrowthRecord(
                child_id=child.id,
                measurement_date=TODAY - timedelta(days=60),
                weight_kg=Decimal("9.0"),
            ),
        ]
    )
    db.session.commit()

    full = report_service.growth_report(child)
    assert len(full["history"]) == 2

    recent = report_service.growth_report(
        child, start=TODAY - timedelta(days=7)
    )
    assert len(recent["history"]) == 1
    assert recent["history"][0]["record"].measurement_date == TODAY


def test_vaccination_report_filters_by_status(db, centre, make_child):
    child = make_child(centre)
    db.session.add_all(
        [
            Vaccination(
                child_id=child.id, vaccine_name="BCG", dose_number=1,
                scheduled_date=TODAY - timedelta(days=30),
                administered_date=TODAY - timedelta(days=29),
                status=VaccinationStatus.COMPLETED,
            ),
            Vaccination(
                child_id=child.id, vaccine_name="OPV", dose_number=1,
                scheduled_date=TODAY - timedelta(days=10),
                status=VaccinationStatus.MISSED,
            ),
        ]
    )
    db.session.commit()

    completed = report_service.vaccination_report(child, status="COMPLETED")
    assert len(completed["history"]) == 1
    assert completed["history"][0]["record"].vaccine_name == "BCG"

    missed = report_service.vaccination_report(child, status="MISSED")
    assert len(missed["history"]) == 1

    all_items = report_service.vaccination_report(child)
    assert len(all_items["history"]) == 2


def test_maternal_report_filters_by_date(db, centre, make_mother):
    mother = make_mother(centre)
    db.session.add_all(
        [
            MaternalHealthRecord(
                mother_id=mother.id, visit_date=TODAY,
                risk_category="LOW",
            ),
            MaternalHealthRecord(
                mother_id=mother.id, visit_date=TODAY - timedelta(days=90),
                risk_category="HIGH",
            ),
        ]
    )
    db.session.commit()

    report = report_service.maternal_report(
        mother, start=TODAY - timedelta(days=7)
    )
    assert len(report["history"]) == 1
    assert report["history"][0]["record"].visit_date == TODAY


def test_nutrition_report_filters_and_totals(db, centre, make_item, make_child):
    item = make_item()
    child = make_child(centre)
    db.session.add_all(
        [
            NutritionDistribution(
                beneficiary_id=child.beneficiary_id, item_id=item.id, centre_id=centre.id,
                quantity=Decimal("3.5"), distribution_date=TODAY,
            ),
            NutritionDistribution(
                beneficiary_id=child.beneficiary_id, item_id=item.id, centre_id=centre.id,
                quantity=Decimal("1.5"),
                distribution_date=TODAY - timedelta(days=45),
            ),
        ]
    )
    db.session.commit()

    report = report_service.nutrition_report(
        centre_id=centre.id, start=TODAY - timedelta(days=7)
    )
    assert report["count"] == 1
    assert report["total_quantity"] == 3.5

    all_report = report_service.nutrition_report(centre_id=centre.id)
    assert all_report["count"] == 2
    assert all_report["total_quantity"] == 5.0


def test_monthly_centre_report_counts(db, centre, make_child, make_mother, make_item):
    child = make_child(centre)
    mother = make_mother(centre)
    item = make_item()
    db.session.add_all(
        [
            GrowthRecord(child_id=child.id, measurement_date=TODAY, weight_kg=Decimal("10")),
            Vaccination(
                child_id=child.id, vaccine_name="BCG", dose_number=1,
                scheduled_date=TODAY, administered_date=TODAY,
                status=VaccinationStatus.COMPLETED,
            ),
            MaternalHealthRecord(
                mother_id=mother.id, visit_date=TODAY, risk_category="LOW"
            ),
            Attendance(
                child_id=child.id, centre_id=centre.id,
                attendance_date=TODAY, status=AttendanceStatus.PRESENT,
            ),
            NutritionDistribution(
                beneficiary_id=child.beneficiary_id, item_id=item.id, centre_id=centre.id,
                quantity=Decimal("2.0"), distribution_date=TODAY,
            ),
        ]
    )
    db.session.commit()

    report = report_service.monthly_centre_report(centre, TODAY.year, TODAY.month)
    metrics = dict(report["metrics"])
    assert metrics["New registrations"] == 2  # child + mother
    assert metrics["Growth measurements"] == 1
    assert metrics["Vaccinations administered"] == 1
    assert metrics["Maternal (ANC) records"] == 1
    assert metrics["Attendance present"] == 1
    assert metrics["Nutrition distributions"] == 1
    assert metrics["Quantity distributed"] == 2.0


def test_scheme_report_filters(db, centre, make_child):
    child = make_child(centre)
    scheme = WelfareScheme(name="Report Scheme", category="Child Welfare", is_active=True)
    db.session.add(scheme)
    db.session.flush()
    db.session.add(
        BeneficiaryScheme(
            beneficiary_id=child.beneficiary_id, scheme_id=scheme.id,
            status=SchemeStatus.ENROLLED,
        )
    )
    db.session.commit()

    report = report_service.scheme_report(centre_id=centre.id)
    assert report["counts"]["TOTAL"] == 1
    assert report["counts"]["ENROLLED"] == 1

    filtered = report_service.scheme_report(status=SchemeStatus.APPLIED)
    assert filtered["counts"]["TOTAL"] == 0


def test_rows_to_csv_serialises():
    text = report_service.rows_to_csv(
        ["A", "B"], [[1, "x"], [2, "y"]]
    )
    assert text.splitlines()[0] == "A,B"
    assert len(text.splitlines()) == 3


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------
def test_reports_require_login(client, db):
    response = client.get("/reports/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize(
    "role",
    [UserRole.ADMIN, UserRole.AWW, UserRole.SUPERVISOR, UserRole.OFFICER],
)
def test_reports_index_all_roles(client, db, make_user, role):
    make_user(f"reporter_{role.value.lower()}", role=role)
    login(client, f"reporter_{role.value.lower()}")
    response = client.get("/reports/")
    assert response.status_code == 200
    assert b"Reports" in response.data


def test_child_profile_report_route(client, db, centre, make_user, make_child):
    child = make_child(centre, name="Profile Report Child")
    make_user("aww_report", role=UserRole.AWW, centre=centre)
    login(client, "aww_report")

    response = client.get(f"/reports/child/{child.beneficiary_id}")
    assert response.status_code == 200
    assert b"Profile Report Child" in response.data

    csv = client.get(f"/reports/child/{child.beneficiary_id}?format=csv")
    assert csv.status_code == 200
    assert csv.headers["Content-Type"].startswith("text/csv")
    assert b"attachment" in csv.headers["Content-Disposition"].encode()


def test_growth_report_route_and_filter(client, db, centre, make_user, make_child):
    child = make_child(centre)
    db.session.add(
        GrowthRecord(child_id=child.id, measurement_date=TODAY, weight_kg=Decimal("10"))
    )
    db.session.commit()
    make_user("aww_report", role=UserRole.AWW, centre=centre)
    login(client, "aww_report")

    response = client.get(f"/reports/child/{child.beneficiary_id}/growth")
    assert response.status_code == 200

    # A future range excludes the record.
    filtered = client.get(
        f"/reports/child/{child.beneficiary_id}/growth"
        f"?start={(TODAY + timedelta(days=10)).isoformat()}"
    )
    assert b"No growth records in this range" in filtered.data


def test_vaccination_report_route_status_filter(client, db, centre, make_user, make_child):
    child = make_child(centre)
    db.session.add(
        Vaccination(
            child_id=child.id, vaccine_name="Measles", dose_number=1,
            scheduled_date=TODAY, status=VaccinationStatus.MISSED,
        )
    )
    db.session.commit()
    make_user("aww_report", role=UserRole.AWW, centre=centre)
    login(client, "aww_report")

    response = client.get(
        f"/reports/child/{child.beneficiary_id}/vaccination?status=COMPLETED"
    )
    assert response.status_code == 200
    assert b"No vaccination records match the filter" in response.data


def test_maternal_report_route(client, db, centre, make_user, make_mother):
    mother = make_mother(centre)
    make_user("aww_report", role=UserRole.AWW, centre=centre)
    login(client, "aww_report")
    response = client.get(f"/reports/mother/{mother.id}/maternal")
    assert response.status_code == 200


def test_nutrition_report_route_csv(client, db, centre, make_user, make_item, make_child):
    item = make_item()
    child = make_child(centre)
    db.session.add(
        NutritionDistribution(
            beneficiary_id=child.beneficiary_id, item_id=item.id, centre_id=centre.id,
            quantity=Decimal("4"), distribution_date=TODAY,
        )
    )
    db.session.commit()
    make_user("aww_report", role=UserRole.AWW, centre=centre)
    login(client, "aww_report")

    page = client.get("/reports/nutrition?item=" + str(item.id))
    assert page.status_code == 200
    assert b"Nutrition distribution report" in page.data

    csv = client.get("/reports/nutrition?format=csv")
    assert csv.status_code == 200
    assert csv.headers["Content-Type"].startswith("text/csv")


def test_monthly_centre_report_route(client, db, centre, make_user):
    make_user("aww_report", role=UserRole.AWW, centre=centre)
    login(client, "aww_report")
    response = client.get(
        f"/reports/centre/{centre.id}/monthly"
        f"?month={TODAY.year:04d}-{TODAY.month:02d}"
    )
    assert response.status_code == 200
    assert b"Monthly centre report" in response.data

    csv = client.get(
        f"/reports/centre/{centre.id}/monthly?format=csv"
        f"&month={TODAY.year:04d}-{TODAY.month:02d}"
    )
    assert csv.status_code == 200
    assert csv.headers["Content-Type"].startswith("text/csv")


def test_scheme_report_route(client, db, centre, make_user, make_child):
    child = make_child(centre)
    scheme = WelfareScheme(name="Report Scheme 2", is_active=True)
    db.session.add(scheme)
    db.session.flush()
    db.session.add(
        BeneficiaryScheme(
            beneficiary_id=child.beneficiary_id, scheme_id=scheme.id,
            status=SchemeStatus.APPLIED,
        )
    )
    db.session.commit()
    make_user("aww_report", role=UserRole.AWW, centre=centre)
    login(client, "aww_report")

    response = client.get("/reports/schemes?status=APPLIED")
    assert response.status_code == 200
    assert b"Report Scheme 2" in response.data

    csv = client.get("/reports/schemes?format=csv")
    assert csv.status_code == 200
    assert csv.headers["Content-Type"].startswith("text/csv")


# ---------------------------------------------------------------------------
# Authorization / scoping
# ---------------------------------------------------------------------------
def test_aww_cannot_view_other_centre_child_report(
    client, db, centre, other_centre, make_user, make_child
):
    other = make_child(other_centre, name="Other Centre Report Child")
    make_user("aww_report", role=UserRole.AWW, centre=centre)
    login(client, "aww_report")

    assert client.get(f"/reports/child/{other.beneficiary_id}").status_code == 403


def test_aww_cannot_view_other_centre_monthly_report(
    client, db, centre, other_centre, make_user
):
    make_user("aww_report", role=UserRole.AWW, centre=centre)
    login(client, "aww_report")

    response = client.get(f"/reports/centre/{other_centre.id}/monthly")
    assert response.status_code == 403


def test_aww_nutrition_report_is_centre_scoped(
    client, db, centre, other_centre, make_user, make_item, make_child
):
    item = make_item()
    own = make_child(centre, name="Own Nutrition Child")
    other = make_child(other_centre, name="Other Nutrition Child")
    db.session.add_all(
        [
            NutritionDistribution(
                beneficiary_id=own.beneficiary_id, item_id=item.id, centre_id=centre.id,
                quantity=Decimal("1"), distribution_date=TODAY,
            ),
            NutritionDistribution(
                beneficiary_id=other.beneficiary_id, item_id=item.id, centre_id=other_centre.id,
                quantity=Decimal("1"), distribution_date=TODAY,
            ),
        ]
    )
    db.session.commit()
    make_user("aww_report", role=UserRole.AWW, centre=centre)
    login(client, "aww_report")

    response = client.get("/reports/nutrition")
    assert response.status_code == 200
    assert b"Own Nutrition Child" in response.data
    assert b"Other Nutrition Child" not in response.data


def test_beneficiary_lookup_redirects(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_report", role=UserRole.AWW, centre=centre)
    login(client, "aww_report")
    response = client.get(f"/reports/beneficiary?beneficiary={child.beneficiary_id}")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/reports/child/{child.beneficiary_id}"
    )
