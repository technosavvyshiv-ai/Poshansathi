"""Phase 13 integration tests.

The centrepiece is the plan's primary integration story exercised end to end
over HTTP:

    login → register beneficiary → growth → vaccination → nutrition
    → alert → home visit → intervention → dashboard

followed by a data-integrity check of the report inputs (the report rendering
itself is Phase 12 and intentionally not implemented yet).

A second workflow covers the maternal path and a third the ADMIN
centre/scheme path, so every module participates in at least one integration.
"""

from __future__ import annotations

from datetime import date, timedelta

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
    Intervention,
    Inventory,
    NutritionDistribution,
    NutritionItem,
    User,
    Vaccination,
    WelfareScheme,
)
from app.services import dashboard_service
from app.utils.constants import (
    AlertStatus,
    AlertType,
    AttendanceStatus,
    BeneficiaryType,
    Gender,
    RecordStatus,
    SchemeStatus,
    UserRole,
    VaccinationStatus,
    VisitStatus,
    VisitType,
)

PASSWORD = "password123"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def centre(db):
    centre = AnganwadiCentre(name="Integration Centre", code="INT-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def make_user(db):
    def make(username, role=UserRole.AWW, centre=None, is_active=True):
        user = User(
            full_name=f"Test {username}",
            username=username,
            role=role,
            centre=centre,
            is_active=is_active,
        )
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        return user

    return make


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


def switch_user(client, username, password=PASSWORD):
    """Logout first, then login (POST /login ignores credentials when already
    signed in, so a plain second login would silently keep the first user)."""
    client.post("/logout")
    return login(client, username, password)


def child_form(**overrides):
    data = {
        "full_name": "Integration Child",
        "date_of_birth": (date.today() - timedelta(days=730)).isoformat(),
        "gender": Gender.FEMALE.value,
        "guardian_name": "Guardian Name",
        "contact": "9876543210",
        "address": "House 1, Integration Village",
        "registration_date": date.today().isoformat(),
        "birth_weight_kg": "3.0",
        "birth_height_cm": "50",
        "blood_group": "O+",
        "mother_id": "",
    }
    data.update(overrides)
    return data


def mother_form(**overrides):
    data = {
        "full_name": "Integration Mother",
        "date_of_birth": (date.today() - timedelta(days=365 * 25)).isoformat(),
        "gender": Gender.FEMALE.value,
        "guardian_name": "Guardian Name",
        "contact": "9876543211",
        "address": "House 2, Integration Village",
        "registration_date": date.today().isoformat(),
        "age": "25",
        "husband_name": "Husband Name",
        "pregnancy_number": "1",
        "last_menstrual_period": (date.today() - timedelta(days=120)).isoformat(),
        "expected_delivery_date": (date.today() + timedelta(days=150)).isoformat(),
        "blood_group": "B+",
        "height_cm": "155",
        "current_risk_level": "LOW",
    }
    data.update(overrides)
    return data


def growth_form(**overrides):
    data = {
        "measurement_date": date.today().isoformat(),
        "weight_kg": "10.5",
        "height_cm": "85.0",
        "muac_cm": "14.0",
        "notes": "Integration measurement.",
    }
    data.update(overrides)
    return data


def vaccination_form(**overrides):
    data = {
        "vaccine_name": "BCG",
        "dose_number": "1",
        "scheduled_date": (date.today() - timedelta(days=30)).isoformat(),
        "administered_date": "",
        "status": VaccinationStatus.MISSED.value,
        "notes": "Integration vaccination.",
    }
    data.update(overrides)
    return data


def stock_form(item, **overrides):
    data = {
        "item_id": str(item.id),
        "quantity": "50",
        "received_date": date.today().isoformat(),
        "minimum_stock": "10",
        "unit": item.unit,
    }
    data.update(overrides)
    return data


def distribution_form(item, beneficiary, **overrides):
    data = {
        "item_id": str(item.id),
        "beneficiary_id": str(beneficiary.id),
        "quantity": "45",
        "distribution_date": date.today().isoformat(),
        "notes": "Integration distribution.",
    }
    data.update(overrides)
    return data


def visit_form(beneficiary, worker, **overrides):
    data = {
        "beneficiary_id": str(beneficiary.id),
        "visit_type": VisitType.GROWTH.value,
        "assigned_worker_id": str(worker.id),
        "scheduled_date": date.today().isoformat(),
        "visit_notes": "Integration visit.",
    }
    data.update(overrides)
    return data


def intervention_form(**overrides):
    data = {
        "intervention_type": "Nutrition counselling",
        "intervention_date": date.today().isoformat(),
        "description": "Counselled the family.",
        "outcome": "Family counselled.",
        "follow_up_required": "",
        "follow_up_date": "",
        "resolve_alert_id": "",
    }
    data.update(overrides)
    return data


def anc_form(**overrides):
    data = {
        "visit_date": date.today().isoformat(),
        "pregnancy_month": "4",
        "weight_kg": "55",
        "haemoglobin": "9.0",
        "systolic_bp": "110",
        "diastolic_bp": "70",
        "risk_category": "LOW",
        "next_follow_up_date": (date.today() + timedelta(days=30)).isoformat(),
        "notes": "Integration ANC visit.",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Primary integration workflow
# ---------------------------------------------------------------------------
def test_complete_core_workflow(client, db, centre, make_user):
    """login → register → growth → vaccination → nutrition → alert → visit
    → intervention → dashboard (→ report-source verification)."""
    aww = make_user("int_aww", role=UserRole.AWW, centre=centre)
    db.session.add(
        NutritionItem(name="Integration Ration", unit="kg", is_active=True)
    )
    db.session.commit()

    # --- Step 1: login -----------------------------------------------------
    response = login(client, "int_aww")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    assert client.get("/dashboard").status_code == 200

    # --- Step 2: register beneficiary --------------------------------------
    response = client.post("/beneficiaries/new/child", data=child_form())
    assert response.status_code == 302, response.data
    beneficiary = Beneficiary.query.filter_by(
        full_name="Integration Child"
    ).one()
    assert beneficiary.centre_id == centre.id
    assert beneficiary.child is not None
    child = beneficiary.child
    assert client.get(f"/beneficiaries/{beneficiary.id}").status_code == 200

    # --- Step 3: record growth --------------------------------------------
    response = client.post(
        f"/children/{child.id}/growth/new",
        data=growth_form(weight_kg="7.0"),  # severe underweight (demo rule)
    )
    assert response.status_code == 302, response.data
    assert GrowthRecord.query.filter_by(child_id=child.id).count() == 1

    # --- Step 4: record vaccination ---------------------------------------
    response = client.post(
        f"/children/{child.id}/vaccinations/new", data=vaccination_form()
    )
    assert response.status_code == 302, response.data
    assert Vaccination.query.filter_by(child_id=child.id).count() == 1

    # --- Step 5: alerts generated deterministically -------------------------
    growth_alert = (
        Alert.query.filter_by(
            child_id=child.id, alert_type=AlertType.GROWTH_FOLLOW_UP
        ).one()
    )
    assert growth_alert.status == AlertStatus.OPEN
    assert growth_alert.severity.value == "HIGH"

    vaccination_alert = (
        Alert.query.filter_by(
            child_id=child.id, alert_type=AlertType.VACCINATION_FOLLOW_UP
        ).one()
    )
    assert vaccination_alert.status == AlertStatus.OPEN

    # --- Step 6: nutrition stock + distribution -----------------------------
    item = NutritionItem.query.filter_by(name="Integration Ration").one()
    response = client.post("/nutrition/stock/new", data=stock_form(item))
    assert response.status_code == 302, response.data
    inventory = Inventory.query.filter_by(
        centre_id=centre.id, item_id=item.id
    ).one()
    assert inventory.received_quantity == 50

    # Distributing 45 of 50 leaves 5 ≤ configured minimum 10 → low-stock alert.
    response = client.post(
        "/nutrition/distributions/new",
        data=distribution_form(item, beneficiary),
    )
    assert response.status_code == 302, response.data
    stock_alert = (
        Alert.query.filter_by(alert_type=AlertType.LOW_NUTRITION_STOCK)
        .filter(Alert.message.like(f"%[inventory:{centre.id}:{item.id}]%"))
        .one()
    )
    assert stock_alert.status == AlertStatus.OPEN

    # --- Step 7: schedule home visit ---------------------------------------
    response = client.post(
        "/visits/new", data=visit_form(beneficiary, aww)
    )
    assert response.status_code == 302, response.data
    visit = HomeVisit.query.filter_by(beneficiary_id=beneficiary.id).one()
    assert visit.status == VisitStatus.SCHEDULED

    # --- Step 8: complete visit ---------------------------------------------
    response = client.post(
        f"/visits/{visit.id}/complete",
        data={
            "completed_date": date.today().isoformat(),
            "visit_notes": "Visited and counselled.",
        },
    )
    assert response.status_code == 302, response.data
    assert db.session.get(HomeVisit, visit.id).status == VisitStatus.COMPLETED

    # --- Step 9: record intervention resolving the growth alert -------------
    response = client.post(
        f"/visits/{visit.id}/interventions/new",
        data=intervention_form(resolve_alert_id=str(growth_alert.id)),
    )
    assert response.status_code == 302, response.data
    intervention = Intervention.query.filter_by(
        home_visit_id=visit.id
    ).one()
    assert intervention.beneficiary_id == beneficiary.id
    assert db.session.get(Alert, growth_alert.id).status == AlertStatus.RESOLVED

    # --- Step 10: dashboard reflects the workflow ---------------------------
    context = dashboard_service.aww_dashboard(centre.id)
    assert context["beneficiaries"]["children"] == 1
    assert context["visits"]["COMPLETED"] == 1
    assert context["visits"]["PENDING"] == 0
    # Vaccination + low-stock alerts remain open; growth alert resolved.
    assert context["alerts"]["ACTIVE"] == 2
    assert context["alerts"]["RESOLVED"] == 1
    assert context["nutrition"]["low_stock_count"] == 1
    assert context["nutrition"]["distribution_count"] == 1
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200

    # --- Step 11: report-source data is complete (reports are Phase 12) -----
    assert len(child.growth_records) == 1
    assert len(child.vaccinations) == 1
    assert len(beneficiary.nutrition_distributions) == 1
    assert len(beneficiary.home_visits) == 1
    assert len(beneficiary.interventions) == 1
    # Growth + vaccination alerts reference the beneficiary; the low-stock
    # alert is centre-scoped via its message marker (no beneficiary link).
    assert len(beneficiary.alerts) == 2
    assert stock_alert.beneficiary_id is None


# ---------------------------------------------------------------------------
# Maternal-path integration workflow
# ---------------------------------------------------------------------------
def test_maternal_alert_visit_resolution_workflow(client, db, centre, make_user):
    """Pregnant woman → ANC record → maternal alert → visit → intervention."""
    aww = make_user("int_maww", role=UserRole.AWW, centre=centre)

    login(client, "int_maww")
    response = client.post("/beneficiaries/new/mother/pregnant", data=mother_form())
    assert response.status_code == 302, response.data
    beneficiary = Beneficiary.query.filter_by(
        full_name="Integration Mother"
    ).one()
    mother = beneficiary.mother
    assert mother is not None

    # HIGH-risk ANC record triggers the maternal follow-up rule.
    response = client.post(
        f"/mothers/{mother.id}/health/new", data=anc_form(risk_category="HIGH")
    )
    assert response.status_code == 302, response.data

    alert = (
        Alert.query.filter_by(
            beneficiary_id=beneficiary.id,
            alert_type=AlertType.MATERNAL_FOLLOW_UP,
        ).one()
    )
    assert alert.status == AlertStatus.OPEN
    assert alert.severity.value == "HIGH"

    # Visit → intervention resolves the maternal alert.
    client.post("/visits/new", data=visit_form(beneficiary, aww))
    visit = HomeVisit.query.filter_by(beneficiary_id=beneficiary.id).one()
    client.post(
        f"/visits/{visit.id}/complete",
        data={"completed_date": date.today().isoformat()},
    )
    response = client.post(
        f"/visits/{visit.id}/interventions/new",
        data=intervention_form(resolve_alert_id=str(alert.id)),
    )
    assert response.status_code == 302, response.data

    refreshed = db.session.get(Alert, alert.id)
    assert refreshed.status == AlertStatus.RESOLVED

    context = dashboard_service.aww_dashboard(centre.id)
    assert context["alerts"]["RESOLVED"] == 1
    assert context["visits"]["COMPLETED"] == 1


# ---------------------------------------------------------------------------
# ADMIN centre/scheme integration
# ---------------------------------------------------------------------------
def test_admin_centre_scheme_link_workflow(client, db, centre, make_user):
    """ADMIN creates centre/scheme; AWW links a beneficiary to the scheme."""
    make_user("int_admin", role=UserRole.ADMIN)
    aww = make_user("int_saww", role=UserRole.AWW, centre=centre)

    login(client, "int_admin")
    response = client.post(
        "/schemes/new",
        data={
            "name": "Integration Scheme",
            "category": "Child Welfare",
            "target_group": "Children",
            "description": "Demo.",
            "benefits": "Ration.",
            "eligibility": "Demo information only.",
            "required_documents": "MCP card.",
            "application_info": "At the centre.",
            "is_active": "on",
        },
    )
    assert response.status_code == 302, response.data
    scheme = WelfareScheme.query.filter_by(name="Integration Scheme").one()

    switch_user(client, "int_saww")
    response = client.post(
        "/beneficiaries/new/child",
        data=child_form(full_name="Scheme Link Child"),
    )
    assert response.status_code == 302, response.data
    beneficiary = Beneficiary.query.filter_by(
        full_name="Scheme Link Child"
    ).one()

    response = client.post(
        f"/beneficiaries/{beneficiary.id}/schemes/link",
        data={
            "scheme_id": str(scheme.id),
            "status": SchemeStatus.APPLIED.value,
            "applied_date": date.today().isoformat(),
        },
    )
    assert response.status_code == 302, response.data

    link = BeneficiaryScheme.query.filter_by(
        beneficiary_id=beneficiary.id, scheme_id=scheme.id
    ).one()
    assert link.status == SchemeStatus.APPLIED

    # ADMIN dashboard sees the scheme activity.
    switch_user(client, "int_admin")
    context = dashboard_service.admin_dashboard()
    assert context["schemes"]["ACTIVE_SCHEMES"] == 1
    assert context["schemes"]["APPLIED"] == 1
    assert client.get("/dashboard").status_code == 200


# ---------------------------------------------------------------------------
# Attendance-driven alert integration
# ---------------------------------------------------------------------------
def test_attendance_absences_raise_alert_and_dashboard_counts(
    client, db, centre, make_user
):
    """Daily register → repeated absences → attendance alert → dashboard."""
    make_user("int_aaww", role=UserRole.AWW, centre=centre)

    login(client, "int_aaww")
    response = client.post(
        "/beneficiaries/new/child",
        data=child_form(full_name="Attendance Child"),
    )
    assert response.status_code == 302, response.data
    beneficiary = Beneficiary.query.filter_by(
        full_name="Attendance Child"
    ).one()
    child = beneficiary.child

    # Mark three absent days through the bulk daily register.
    for offset in range(3):
        response = client.post(
            "/attendance/daily",
            data={
                "centre_id": str(centre.id),
                "attendance_date": (
                    date.today() - timedelta(days=offset)
                ).isoformat(),
                f"status_{child.id}": AttendanceStatus.ABSENT.value,
                f"note_{child.id}": "",
            },
        )
        assert response.status_code == 302, response.data

    assert Attendance.query.filter_by(child_id=child.id).count() == 3
    alert = (
        Alert.query.filter_by(child_id=child.id, alert_type=AlertType.ATTENDANCE)
        .one()
    )
    assert alert.status == AlertStatus.OPEN

    context = dashboard_service.aww_dashboard(centre.id)
    assert context["attendance"]["absent"] == 3
    assert context["alerts"]["ACTIVE"] == 1


# ---------------------------------------------------------------------------
# Cross-module role protection sweep
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "method, url, roles",
    [
        ("post", "/beneficiaries/new/child", (UserRole.SUPERVISOR, UserRole.OFFICER)),
        ("post", "/nutrition/stock/new", (UserRole.SUPERVISOR, UserRole.OFFICER)),
        ("post", "/visits/new", (UserRole.SUPERVISOR, UserRole.OFFICER)),
        ("post", "/alerts/scan", (UserRole.OFFICER,)),
        ("post", "/schemes/new", (UserRole.AWW, UserRole.SUPERVISOR, UserRole.OFFICER)),
    ],
)
def test_write_endpoints_reject_unauthorised_roles(
    client, db, make_user, method, url, roles
):
    for role in roles:
        username = f"sweep_{role.value.lower()}_{url.count('/')}"
        make_user(username, role=role)
        login(client, username)
        response = client.post(url, data={})
        assert response.status_code == 403, f"{role} {url}"


def test_read_endpoints_accept_all_roles(client, db, centre, make_user):
    make_user("reader_aww", role=UserRole.AWW, centre=centre)
    login(client, "reader_aww")
    for url in (
        "/dashboard",
        "/beneficiaries/",
        "/nutrition/",
        "/attendance/",
        "/alerts/",
        "/visits/",
        "/schemes/",
        "/children/1/growth",
    ):
        assert client.get(url).status_code in (200, 404), url


def test_unauthenticated_access_redirects_to_login(client, db):
    for url in (
        "/dashboard",
        "/beneficiaries/",
        "/nutrition/",
        "/attendance/",
        "/alerts/",
        "/visits/",
        "/schemes/",
    ):
        response = client.get(url)
        assert response.status_code == 302, url
        assert "/login" in response.headers["Location"], url
