"""Phase 11 dashboard tests: metric calculations and role-specific access."""

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
    Mother,
    NutritionDistribution,
    NutritionItem,
    User,
    Vaccination,
    WelfareScheme,
)
from app.services import dashboard_service
from app.utils.constants import (
    AlertSeverity,
    AlertStatus,
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


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def centre(db):
    centre = AnganwadiCentre(name="Dash Centre A", code="DCA-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def other_centre(db):
    centre = AnganwadiCentre(name="Dash Centre B", code="DCB-001", is_active=True)
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


@pytest.fixture()
def make_child(db):
    def make(centre, name="Dash Child", age_years=2, registered=None):
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=BeneficiaryType.CHILD,
            full_name=name,
            date_of_birth=date.today() - timedelta(days=365 * age_years),
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=registered or date.today(),
        )
        child = Child(beneficiary=beneficiary)
        db.session.add(child)
        db.session.commit()
        return child

    return make


@pytest.fixture()
def make_mother(db):
    def make(centre, name="Dash Mother", mother_type=BeneficiaryType.PREGNANT_WOMAN):
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=mother_type,
            full_name=name,
            date_of_birth=date.today() - timedelta(days=365 * 25),
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=date.today(),
        )
        mother = Mother(beneficiary=beneficiary)
        db.session.add(mother)
        db.session.commit()
        return mother

    return make


@pytest.fixture()
def make_item(db):
    def make(name="Dash Ration", unit="kg"):
        item = NutritionItem(name=name, unit=unit, is_active=True)
        db.session.add(item)
        db.session.commit()
        return item

    return make


@pytest.fixture()
def make_inventory(db):
    def make(centre, item, opening=0, received=0, distributed=0, minimum=0):
        inventory = Inventory(
            centre=centre,
            item=item,
            opening_stock=Decimal(str(opening)),
            received_quantity=Decimal(str(received)),
            distributed_quantity=Decimal(str(distributed)),
            minimum_stock=Decimal(str(minimum)),
            unit=item.unit,
        )
        db.session.add(inventory)
        db.session.commit()
        return inventory

    return make


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


# ---------------------------------------------------------------------------
# Metric unit tests
# ---------------------------------------------------------------------------
def test_beneficiary_counts(db, centre, other_centre, make_child, make_mother):
    make_child(centre, "One")
    make_child(centre, "Two")
    make_mother(centre, "Pregnant")
    make_mother(
        centre, "Lactating", mother_type=BeneficiaryType.LACTATING_MOTHER
    )
    make_child(other_centre, "Other")

    counts = dashboard_service.beneficiary_counts(centre.id)
    assert counts["children"] == 2
    assert counts["pregnant"] == 1
    assert counts["lactating"] == 1
    assert counts["mothers"] == 2
    assert counts["total"] == 4
    assert counts["active"] == 4

    all_counts = dashboard_service.beneficiary_counts()
    assert all_counts["children"] == 3
    assert all_counts["total"] == 5


def test_beneficiary_counts_active_and_inactive(db, centre, make_child):
    child = make_child(centre)
    child.beneficiary.status = RecordStatus.INACTIVE
    db.session.commit()

    counts = dashboard_service.beneficiary_counts(centre.id)
    assert counts["active"] == 0
    assert counts["inactive"] == 1
    assert counts["total"] == 1


def test_alert_counts_and_resolution_rate(db, centre, make_child):
    child = make_child(centre)
    beneficiary = child.beneficiary
    for status in (AlertStatus.OPEN, AlertStatus.OPEN,
                   AlertStatus.IN_PROGRESS, AlertStatus.RESOLVED):
        db.session.add(
            Alert(
                beneficiary=beneficiary,
                child=child,
                alert_type=AlertType.GROWTH_FOLLOW_UP,
                severity=AlertSeverity.MEDIUM,
                message="Dashboard alert.",
                status=status,
            )
        )
    db.session.commit()

    counts = dashboard_service.alert_counts(centre.id)
    assert counts["OPEN"] == 2
    assert counts["IN_PROGRESS"] == 1
    assert counts["RESOLVED"] == 1
    assert counts["ACTIVE"] == 3
    assert counts["TOTAL"] == 4
    # Resolution = resolved / (open + in-progress + resolved).
    assert counts["RESOLUTION_RATE"] == 25.0


def test_alert_counts_include_centre_low_stock_alerts(db, centre, other_centre):
    db.session.add(
        Alert(
            alert_type=AlertType.LOW_NUTRITION_STOCK,
            severity=AlertSeverity.HIGH,
            message=f"[inventory:{centre.id}:1] Low stock.",
            status=AlertStatus.OPEN,
        )
    )
    db.session.commit()

    assert dashboard_service.alert_counts(centre.id)["ACTIVE"] == 1
    assert dashboard_service.alert_counts(other_centre.id)["ACTIVE"] == 0


def test_visit_metrics_pending_and_overdue(db, centre, make_child, make_mother):
    child = make_child(centre)
    mother = make_mother(centre)
    today = date.today()

    db.session.add_all(
        [
            HomeVisit(
                beneficiary_id=child.beneficiary_id, centre_id=centre.id,
                visit_type=VisitType.ROUTINE, scheduled_date=today,
                status=VisitStatus.SCHEDULED,
            ),
            HomeVisit(
                beneficiary_id=mother.beneficiary_id, centre_id=centre.id,
                visit_type=VisitType.ROUTINE,
                scheduled_date=today - timedelta(days=3),
                status=VisitStatus.SCHEDULED,
            ),
            HomeVisit(
                beneficiary_id=mother.beneficiary_id, centre_id=centre.id,
                visit_type=VisitType.ROUTINE,
                scheduled_date=today - timedelta(days=5),
                status=VisitStatus.COMPLETED, completed_date=today,
            ),
        ]
    )
    db.session.commit()

    metrics = dashboard_service.visit_metrics(centre.id)
    assert metrics["PENDING"] == 2
    assert metrics["OVERDUE"] == 1
    assert metrics["COMPLETED"] == 1
    assert metrics["TOTAL"] == 3


def test_vaccination_metrics_coverage(db, centre, make_child):
    child = make_child(centre)
    today = date.today()

    db.session.add_all(
        [
            Vaccination(
                child=child, vaccine_name="BCG", dose_number=1,
                scheduled_date=today - timedelta(days=60),
                administered_date=today - timedelta(days=58),
                status=VaccinationStatus.COMPLETED,
            ),
            Vaccination(
                child=child, vaccine_name="OPV", dose_number=1,
                scheduled_date=today + timedelta(days=10),
                status=VaccinationStatus.UPCOMING,
            ),
            Vaccination(
                child=child, vaccine_name="Pentavalent", dose_number=1,
                scheduled_date=today - timedelta(days=10),
                status=VaccinationStatus.DUE,
            ),
            Vaccination(
                child=child, vaccine_name="Measles", dose_number=1,
                scheduled_date=today - timedelta(days=40),
                status=VaccinationStatus.MISSED,
            ),
        ]
    )
    db.session.commit()

    metrics = dashboard_service.vaccination_metrics(centre.id, days=30)
    assert metrics["total"] == 4
    assert metrics["completed"] == 1
    assert metrics["upcoming"] == 1  # DUE with past date counts as overdue
    assert metrics["overdue"] == 1
    assert metrics["missed"] == 1
    assert metrics["coverage"] == 25.0
    assert metrics["breakdown"][VaccinationStatus.COMPLETED.value] == 1


def test_upcoming_vaccinations_window(db, centre, make_child):
    child = make_child(centre)
    today = date.today()
    db.session.add_all(
        [
            Vaccination(
                child=child, vaccine_name="Soon", dose_number=1,
                scheduled_date=today + timedelta(days=5),
                status=VaccinationStatus.UPCOMING,
            ),
            Vaccination(
                child=child, vaccine_name="Later", dose_number=1,
                scheduled_date=today + timedelta(days=90),
                status=VaccinationStatus.UPCOMING,
            ),
        ]
    )
    db.session.commit()

    rows = dashboard_service.upcoming_vaccinations(centre.id, days=30)
    assert [row.vaccine_name for row in rows] == ["Soon"]


def test_attendance_metrics_percentage(db, centre, make_child):
    child = make_child(centre)
    today = date.today()
    for offset in range(4):
        db.session.add(
            Attendance(
                child_id=child.id,
                centre_id=centre.id,
                attendance_date=today - timedelta(days=offset),
                status=(
                    AttendanceStatus.PRESENT if offset < 3
                    else AttendanceStatus.ABSENT
                ),
            )
        )
    db.session.commit()

    metrics = dashboard_service.attendance_metrics(centre.id, days=30)
    assert metrics["present"] == 3
    assert metrics["absent"] == 1
    assert metrics["total"] == 4
    assert metrics["percentage"] == 75.0


def test_attendance_trend_series(db, centre, make_child):
    child = make_child(centre)
    today = date.today()
    db.session.add_all(
        [
            Attendance(
                child_id=child.id, centre_id=centre.id,
                attendance_date=today, status=AttendanceStatus.PRESENT,
            ),
            Attendance(
                child_id=child.id, centre_id=centre.id,
                attendance_date=today - timedelta(days=1),
                status=AttendanceStatus.ABSENT,
            ),
        ]
    )
    db.session.commit()

    trend = dashboard_service.attendance_trend(centre.id, days=14)
    assert len(trend["labels"]) == 14
    assert trend["labels"][-1] == today.isoformat()
    assert trend["present"][-1] == 1
    assert trend["absent"][-1] == 0
    assert trend["absent"][-2] == 1
    assert sum(trend["present"]) == 1
    assert sum(trend["absent"]) == 1


def test_nutrition_metrics(db, centre, make_item, make_inventory, make_child):
    item = make_item()
    make_inventory(centre, item, received=5, distributed=2, minimum=25)
    child = make_child(centre)
    db.session.add(
        NutritionDistribution(
            beneficiary=child.beneficiary, item=item, centre=centre,
            quantity=Decimal("2.5"), distribution_date=date.today(),
        )
    )
    db.session.commit()

    metrics = dashboard_service.nutrition_metrics(centre.id, days=30)
    assert metrics["inventory_rows"] == 1
    assert metrics["low_stock_count"] == 1
    assert metrics["distribution_count"] == 1
    assert metrics["distributed_quantity"] == 2.5
    assert metrics["top_items"] == [("Dash Ration", 2.5)]


def test_scheme_metrics(db, centre, other_centre, make_child):
    child = make_child(centre)
    outsider = make_child(other_centre, "Other Child")
    db.session.add_all(
        [
            WelfareScheme(name="Dash Scheme", is_active=True),
            WelfareScheme(name="Inactive Scheme", is_active=False),
        ]
    )
    db.session.commit()
    scheme = WelfareScheme.query.filter_by(name="Dash Scheme").one()

    db.session.add_all(
        [
            BeneficiaryScheme(
                beneficiary_id=child.beneficiary_id, scheme_id=scheme.id,
                status=SchemeStatus.ENROLLED,
            ),
            BeneficiaryScheme(
                beneficiary_id=outsider.beneficiary_id, scheme_id=scheme.id,
                status=SchemeStatus.ENROLLED,
            ),
        ]
    )
    db.session.commit()

    metrics = dashboard_service.scheme_metrics(centre.id)
    assert metrics["ACTIVE_SCHEMES"] == 1
    assert metrics["TOTAL"] == 1
    assert metrics["ENROLLED"] == 1

    all_metrics = dashboard_service.scheme_metrics()
    assert all_metrics["TOTAL"] == 2


def test_user_metrics(db, centre, make_user):
    make_user("aww_one", role=UserRole.AWW, centre=centre)
    make_user("aww_two", role=UserRole.AWW, centre=centre)
    make_user("admin_one", role=UserRole.ADMIN)
    make_user("ghost", role=UserRole.OFFICER, is_active=False)

    counts = dashboard_service.user_metrics()
    assert counts["AWW"] == 2
    assert counts["ADMIN"] == 1
    assert counts["OFFICER"] == 0  # inactive users excluded
    assert counts["TOTAL"] == 3


def test_centre_comparison_rows(db, centre, other_centre, make_child):
    make_child(centre, "A Child")
    make_child(centre, "B Child")
    make_child(other_centre, "C Child")

    rows = dashboard_service.centre_comparison()
    by_name = {row["centre"].name: row for row in rows}
    assert by_name["Dash Centre A"]["children"] == 2
    assert by_name["Dash Centre B"]["children"] == 1


def test_recent_registrations_window(db, centre, make_child):
    make_child(centre, "Recent Child", registered=date.today())
    make_child(
        centre, "Old Child", registered=date.today() - timedelta(days=90)
    )

    rows = dashboard_service.recent_registrations(centre_id=centre.id, days=30)
    assert [row.full_name for row in rows] == ["Recent Child"]


# ---------------------------------------------------------------------------
# Role dashboards (builders)
# ---------------------------------------------------------------------------
def test_aww_dashboard_contains_centre(db, centre, make_child):
    make_child(centre, "Aww Dash Child")
    context = dashboard_service.aww_dashboard(centre.id)

    assert context["centre"].id == centre.id
    assert context["beneficiaries"]["children"] == 1
    assert "attendance_trend" in context
    assert "nutrition" in context


def test_supervisor_dashboard_comparison(db, centre, other_centre, make_child):
    make_child(centre, "Sup Child")
    make_child(other_centre, "Other Sup Child")

    context = dashboard_service.supervisor_dashboard()
    assert context["total_centres"]["active"] == 2
    assert len(context["comparison"]) == 2
    assert context["comparison_chart"]["labels"] == [
        "Dash Centre A", "Dash Centre B",
    ]


def test_supervisor_dashboard_centre_filter(
    db, centre, other_centre, make_child
):
    make_child(centre, "Filtered Child")
    context = dashboard_service.supervisor_dashboard(centre.id)
    assert context["beneficiaries"]["children"] == 1
    assert len(context["comparison"]) == 1


def test_admin_dashboard_totals(db, centre, make_child, make_user):
    make_child(centre, "Admin Dash Child")
    make_user("aww_admin", role=UserRole.AWW, centre=centre)

    context = dashboard_service.admin_dashboard()
    assert context["users"]["AWW"] == 1
    assert context["beneficiaries"]["children"] == 1
    assert len(context["comparison"]) >= 1


# ---------------------------------------------------------------------------
# Route / role-specific access
# ---------------------------------------------------------------------------
def test_dashboard_requires_login(client, db):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize(
    "role",
    [UserRole.ADMIN, UserRole.AWW, UserRole.SUPERVISOR, UserRole.OFFICER],
)
def test_every_role_renders_a_dashboard(client, db, make_user, role):
    make_user(f"user_{role.value.lower()}", role=role)
    login(client, f"user_{role.value.lower()}")

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert b"Welcome," in response.data


def test_aww_dashboard_is_centre_scoped(
    client, db, centre, other_centre, make_user, make_child
):
    make_child(centre, "Own Centre Child")
    make_child(other_centre, "Other Centre Child")
    make_user("aww_dash", role=UserRole.AWW, centre=centre)
    login(client, "aww_dash")

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert b"Own Centre Child" in response.data
    assert b"Other Centre Child" not in response.data


def test_aww_dashboard_shows_required_sections(
    client, db, centre, make_user, make_child
):
    make_child(centre)
    make_user("aww_dash", role=UserRole.AWW, centre=centre)
    login(client, "aww_dash")

    response = client.get("/dashboard")
    body = response.data

    assert b"Children" in body
    assert b"Pregnant women" in body
    assert b"Lactating mothers" in body
    assert b"Open alerts" in body
    assert b"Pending visits" in body
    assert b"Upcoming vaccinations" in body
    assert b"Recent registrations" in body
    assert b"Attendance" in body
    assert b"Nutrition stock status" in body
    assert b"attendance-chart-data" in body  # Chart.js payload present


def test_supervisor_dashboard_shows_comparison(
    client, db, centre, other_centre, make_user, make_child
):
    make_child(centre, "Sup A Child")
    make_child(other_centre, "Sup B Child")
    make_user("supervisor_dash", role=UserRole.SUPERVISOR)
    login(client, "supervisor_dash")

    response = client.get("/dashboard")
    body = response.data

    assert response.status_code == 200
    assert b"Centre comparison" in body
    assert b"Vaccination coverage" in body
    assert b"centre-chart-data" in body
    assert b"Dash Centre A" in body
    assert b"Dash Centre B" in body


def test_supervisor_dashboard_centre_filter_route(
    client, db, centre, other_centre, make_user, make_child
):
    make_child(centre, "Filtered Sup Child")
    make_child(other_centre, "Unfiltered Sup Child")
    make_user("supervisor_dash", role=UserRole.SUPERVISOR)
    login(client, "supervisor_dash")

    response = client.get("/dashboard?centre=" + str(centre.id))

    assert response.status_code == 200
    # The comparison chart payload (JSON) is narrowed to the filtered centre;
    # the filter dropdown itself still lists every centre for switching back.
    assert b'"Dash Centre A"' in response.data
    assert b'"Dash Centre B"' not in response.data


def test_officer_dashboard_is_read_only_aggregate(
    client, db, centre, other_centre, make_user, make_child
):
    make_child(centre, "Officer A Child")
    make_child(other_centre, "Officer B Child")
    make_user("officer_dash", role=UserRole.OFFICER)
    login(client, "officer_dash")

    response = client.get("/dashboard")
    body = response.data

    assert response.status_code == 200
    assert b"aggregated overview" in body
    assert b"centre-chart-data" in body
    assert b"Officer A Child" not in body  # officer sees aggregates only
    assert b"Dash Centre A" in body
    assert b"Dash Centre B" in body


def test_admin_dashboard_shows_users_and_centres(
    client, db, centre, make_user, make_child
):
    make_child(centre, "Admin Route Child")
    make_user("aww_admin_route", role=UserRole.AWW, centre=centre)
    make_user("admin_dash", role=UserRole.ADMIN)
    login(client, "admin_dash")

    response = client.get("/dashboard")
    body = response.data

    assert response.status_code == 200
    assert b"Users by role" in body
    assert b"Active centres" in body
    assert b"Admin Route Child" in response.data
    assert b"centre-chart-data" in body


def test_dashboard_metrics_match_database(
    client, db, centre, make_user, make_child, make_mother
):
    """Rendered numbers must equal real database counts (no hardcoding)."""
    for index in range(3):
        make_child(centre, f"Counted Child {index}")
    make_mother(centre, "Counted Mother")
    make_user("aww_dash", role=UserRole.AWW, centre=centre)
    login(client, "aww_dash")

    response = client.get("/dashboard")

    assert response.status_code == 200
    # Children metric card (3) and pregnant-women metric card (1) rendered
    # from the database — no hardcoded numbers.
    assert b'href="/beneficiaries/?type=CHILD">3</a>' in response.data
    assert b'href="/beneficiaries/?type=PREGNANT_WOMAN">1</a>' in response.data
