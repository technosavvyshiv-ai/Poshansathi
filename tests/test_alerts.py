"""Phase 9 alert tests: deterministic rules, lifecycle, routes, scoping."""

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
    Child,
    GrowthRecord,
    HomeVisit,
    MaternalHealthRecord,
    Mother,
    User,
    Vaccination,
)
from app.services import alert_service
from app.utils.constants import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    AttendanceStatus,
    BeneficiaryType,
    Gender,
    NutritionalStatus,
    RecordStatus,
    RiskLevel,
    UserRole,
    VaccinationStatus,
    VisitStatus,
    VisitType,
)
from app.utils.validators import ValidationError

PASSWORD = "password123"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def centre(db):
    centre = AnganwadiCentre(name="Alert Centre A", code="ALA-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def other_centre(db):
    centre = AnganwadiCentre(name="Alert Centre B", code="ALB-001", is_active=True)
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
    def make(centre, name="Alert Child"):
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=BeneficiaryType.CHILD,
            full_name=name,
            date_of_birth=date.today() - timedelta(days=730),
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=date.today(),
        )
        child = Child(beneficiary=beneficiary)
        db.session.add(child)
        db.session.commit()
        return child

    return make


@pytest.fixture()
def make_mother(db):
    def make(centre, name="Alert Mother", risk=RiskLevel.LOW):
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=BeneficiaryType.PREGNANT_WOMAN,
            full_name=name,
            date_of_birth=date.today() - timedelta(days=365 * 25),
            gender=Gender.FEMALE,
            status=RecordStatus.ACTIVE,
            registration_date=date.today(),
        )
        mother = Mother(beneficiary=beneficiary, current_risk_level=risk)
        db.session.add(mother)
        db.session.commit()
        return mother

    return make


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


# ---------------------------------------------------------------------------
# Deterministic rule unit tests
# ---------------------------------------------------------------------------
def test_growth_rule_creates_and_resolves(db, centre, make_child):
    child = make_child(centre)
    concerning = GrowthRecord(
        child=child,
        measurement_date=date.today() - timedelta(days=10),
        weight_kg=Decimal("7.0"),
        nutritional_status=NutritionalStatus.SEVERE_UNDERWEIGHT,
    )
    db.session.add(concerning)
    db.session.commit()

    alert = alert_service.sync_growth_alert(child, concerning)
    db.session.commit()
    assert alert.alert_type == AlertType.GROWTH_FOLLOW_UP
    assert alert.severity == AlertSeverity.HIGH
    assert alert.status == AlertStatus.OPEN

    normal = GrowthRecord(
        child=child,
        measurement_date=date.today(),
        weight_kg=Decimal("12.0"),
        nutritional_status=NutritionalStatus.NORMAL,
    )
    db.session.add(normal)
    db.session.commit()
    alert_service.sync_growth_alert(child, normal)
    db.session.commit()

    assert alert_service.open_alert(AlertType.GROWTH_FOLLOW_UP, child=child) is None


def test_vaccination_rule_missed_and_overdue(db, centre, make_child):
    child = make_child(centre)
    missed = Vaccination(
        child=child,
        vaccine_name="Measles",
        dose_number=1,
        scheduled_date=date.today() - timedelta(days=40),
        status=VaccinationStatus.MISSED,
    )
    overdue = Vaccination(
        child=child,
        vaccine_name="OPV",
        dose_number=2,
        scheduled_date=date.today() - timedelta(days=10),
        status=VaccinationStatus.DUE,
    )
    db.session.add_all([missed, overdue])
    db.session.commit()

    alert = alert_service.sync_vaccination_alert(child)
    db.session.commit()
    assert alert.alert_type == AlertType.VACCINATION_FOLLOW_UP
    assert alert.severity == AlertSeverity.HIGH  # missed present

    # Completing the missed dose but leaving the overdue one downgrades severity.
    missed.status = VaccinationStatus.COMPLETED
    missed.administered_date = date.today()
    db.session.commit()
    alert_service.sync_vaccination_alert(child)
    db.session.commit()
    updated = alert_service.open_alert(AlertType.VACCINATION_FOLLOW_UP, child=child)
    assert updated is not None
    assert updated.severity == AlertSeverity.MEDIUM

    # Completing everything resolves the alert.
    overdue.status = VaccinationStatus.COMPLETED
    overdue.administered_date = date.today()
    db.session.commit()
    alert_service.sync_vaccination_alert(child)
    db.session.commit()
    assert alert_service.open_alert(AlertType.VACCINATION_FOLLOW_UP, child=child) is None


def test_maternal_rule_high_risk_and_overdue(db, centre, make_mother):
    mother = make_mother(centre)
    record = MaternalHealthRecord(
        mother=mother,
        visit_date=date.today() - timedelta(days=20),
        risk_category=RiskLevel.HIGH,
        next_follow_up_date=date.today() - timedelta(days=5),
    )
    db.session.add(record)
    db.session.commit()

    alert = alert_service.sync_maternal_alert(mother)
    db.session.commit()
    assert alert.alert_type == AlertType.MATERNAL_FOLLOW_UP
    assert alert.severity == AlertSeverity.HIGH
    assert alert.beneficiary_id == mother.beneficiary_id

    record.risk_category = RiskLevel.LOW
    record.next_follow_up_date = date.today() + timedelta(days=5)
    db.session.commit()
    alert_service.sync_maternal_alert(mother)
    db.session.commit()
    assert (
        alert_service.open_alert(
            AlertType.MATERNAL_FOLLOW_UP, beneficiary=mother.beneficiary
        )
        is None
    )


def test_attendance_rule_threshold(db, centre, make_child):
    child = make_child(centre)
    for day in range(3):
        db.session.add(
            Attendance(
                child_id=child.id,
                centre_id=centre.id,
                attendance_date=date.today() - timedelta(days=day),
                status=AttendanceStatus.ABSENT,
            )
        )
    db.session.commit()

    alert = alert_service.sync_attendance_alert(child)
    db.session.commit()
    assert alert.alert_type == AlertType.ATTENDANCE
    assert alert.severity == AlertSeverity.MEDIUM

    # Only two absences remain in the window -> below threshold -> resolved.
    oldest = (
        Attendance.query.filter_by(child_id=child.id)
        .order_by(Attendance.attendance_date.asc())
        .first()
    )
    oldest.attendance_date = date.today() - timedelta(days=90)
    db.session.commit()
    alert_service.sync_attendance_alert(child)
    db.session.commit()
    assert alert_service.open_alert(AlertType.ATTENDANCE, child=child) is None


def test_home_visit_rule_overdue(db, centre, make_child):
    child = make_child(centre)
    visit = HomeVisit(
        beneficiary=child.beneficiary,
        centre=centre,
        visit_type=VisitType.ROUTINE,
        scheduled_date=date.today() - timedelta(days=2),
        status=VisitStatus.SCHEDULED,
    )
    db.session.add(visit)
    db.session.commit()

    alert = alert_service.sync_home_visit_pending(child.beneficiary)
    db.session.commit()
    assert alert.alert_type == AlertType.HOME_VISIT_PENDING

    visit.status = VisitStatus.COMPLETED
    visit.completed_date = date.today()
    db.session.commit()
    alert_service.sync_home_visit_pending(child.beneficiary)
    db.session.commit()
    assert (
        alert_service.open_alert(
            AlertType.HOME_VISIT_PENDING, beneficiary=child.beneficiary
        )
        is None
    )


def test_rule_sync_is_idempotent(db, centre, make_child):
    child = make_child(centre)
    record = GrowthRecord(
        child=child,
        measurement_date=date.today(),
        weight_kg=Decimal("7.0"),
        nutritional_status=NutritionalStatus.UNDERWEIGHT,
    )
    db.session.add(record)
    db.session.commit()

    alert_service.sync_growth_alert(child, record)
    alert_service.sync_growth_alert(child, record)
    db.session.commit()

    assert Alert.query.filter_by(alert_type=AlertType.GROWTH_FOLLOW_UP).count() == 1


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
def test_alert_lifecycle_transitions(db, centre, make_child):
    child = make_child(centre)
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GENERAL,
        severity=AlertSeverity.LOW,
        message="Manual demo alert.",
        beneficiary=child.beneficiary,
    )
    db.session.commit()

    alert_service.set_alert_status(alert, AlertStatus.IN_PROGRESS)
    assert alert.status == AlertStatus.IN_PROGRESS

    alert_service.resolve_alert(alert, notes="Handled.")
    assert alert.status == AlertStatus.RESOLVED
    assert alert.resolved_at is not None
    assert alert.resolution_notes == "Handled."

    alert_service.reopen_alert(alert)
    assert alert.status == AlertStatus.OPEN
    assert alert.resolved_at is None

    alert_service.dismiss_alert(alert, notes="Not needed.")
    assert alert.status == AlertStatus.DISMISSED

    # A terminal alert cannot jump straight back to in-progress.
    with pytest.raises(Exception):
        alert_service.set_alert_status(alert, AlertStatus.IN_PROGRESS)


def test_assign_alert(db, centre, make_child, make_user):
    child = make_child(centre)
    worker = make_user("assign_worker", role=UserRole.AWW, centre=centre)
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GENERAL,
        severity=AlertSeverity.LOW,
        message="Assignable.",
        beneficiary=child.beneficiary,
    )
    db.session.commit()

    alert_service.assign_alert(alert, worker)
    assert alert.assigned_to_id == worker.id


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def test_alerts_require_login(client, db):
    response = client.get("/alerts/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_alert_index_and_detail(client, db, centre, make_user, make_child):
    child = make_child(centre, name="Index Alert Child")
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GROWTH_FOLLOW_UP,
        severity=AlertSeverity.HIGH,
        message="Growth follow-up demo.",
        beneficiary=child.beneficiary,
        child=child,
    )
    db.session.commit()
    make_user("aww_alert", role=UserRole.AWW, centre=centre)
    login(client, "aww_alert")

    index = client.get("/alerts/")
    assert index.status_code == 200
    assert b"Index Alert Child" in index.data

    detail = client.get(f"/alerts/{alert.id}")
    assert detail.status_code == 200
    assert b"Growth follow" in detail.data


def test_alert_status_routes(client, db, centre, make_user, make_child):
    child = make_child(centre)
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GENERAL,
        severity=AlertSeverity.MEDIUM,
        message="Resolve me.",
        beneficiary=child.beneficiary,
    )
    db.session.commit()
    make_user("aww_alert", role=UserRole.AWW, centre=centre)
    login(client, "aww_alert")

    response = client.post(
        f"/alerts/{alert.id}/resolve",
        data={"resolution_notes": "Done in the field."},
    )
    assert response.status_code == 302
    refreshed = db.session.get(Alert, alert.id)
    assert refreshed.status == AlertStatus.RESOLVED
    assert refreshed.resolution_notes == "Done in the field."

    client.post(f"/alerts/{alert.id}/reopen")
    assert db.session.get(Alert, alert.id).status == AlertStatus.OPEN


def test_alert_assignment_route(client, db, centre, make_user, make_child):
    child = make_child(centre)
    worker = make_user("assignee", role=UserRole.AWW, centre=centre)
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GENERAL,
        severity=AlertSeverity.LOW,
        message="Assign via route.",
        beneficiary=child.beneficiary,
    )
    db.session.commit()
    make_user("aww_alert", role=UserRole.AWW, centre=centre)
    login(client, "aww_alert")

    response = client.post(
        f"/alerts/{alert.id}/assign", data={"assigned_to_id": str(worker.id)}
    )
    assert response.status_code == 302
    assert db.session.get(Alert, alert.id).assigned_to_id == worker.id


def test_scan_route_generates_alerts(client, db, centre, make_user, make_child):
    child = make_child(centre)
    db.session.add(
        Vaccination(
            child=child,
            vaccine_name="BCG",
            dose_number=1,
            scheduled_date=date.today() - timedelta(days=30),
            status=VaccinationStatus.MISSED,
        )
    )
    db.session.commit()
    make_user("aww_alert", role=UserRole.AWW, centre=centre)
    login(client, "aww_alert")

    response = client.post("/alerts/scan")

    assert response.status_code == 302
    assert (
        Alert.query.filter_by(
            alert_type=AlertType.VACCINATION_FOLLOW_UP,
            child_id=child.id,
        ).count()
        == 1
    )


def test_alert_centre_scoping(
    client, db, centre, other_centre, make_user, make_child
):
    other = make_child(other_centre, name="Other Alert Child")
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GENERAL,
        severity=AlertSeverity.LOW,
        message="Other centre alert.",
        beneficiary=other.beneficiary,
    )
    db.session.commit()
    make_user("aww_alert", role=UserRole.AWW, centre=centre)
    login(client, "aww_alert")

    assert client.get(f"/alerts/{alert.id}").status_code == 403
    index = client.get("/alerts/")
    assert index.status_code == 200
    assert b"Other Alert Child" not in index.data


def test_officer_cannot_manage_alerts(
    client, db, centre, make_user, make_child
):
    role = UserRole.OFFICER
    child = make_child(centre)
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GENERAL,
        severity=AlertSeverity.LOW,
        message="Read only.",
        beneficiary=child.beneficiary,
    )
    db.session.commit()
    make_user("reader", role=role)
    login(client, "reader")

    assert client.get("/alerts/").status_code == 200
    assert client.post(f"/alerts/{alert.id}/reopen").status_code == 403
    assert client.post("/alerts/scan").status_code == 403


# ---------------------------------------------------------------------------
# Backend validation: alert assignment
# ---------------------------------------------------------------------------
def test_service_rejects_invalid_assignee_role(
    db, centre, make_child, make_user
):
    child = make_child(centre)
    officer = make_user("officer_assign", role=UserRole.OFFICER, centre=centre)
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GENERAL,
        severity=AlertSeverity.LOW,
        message="Assign validation.",
        beneficiary=child.beneficiary,
    )
    db.session.commit()

    with pytest.raises(ValidationError) as excinfo:
        alert_service.assign_alert(alert, officer)

    assert "assigned_to_id" in excinfo.value.errors
    assert db.session.get(Alert, alert.id).assigned_to_id is None


def test_service_rejects_inactive_assignee(db, centre, make_child, make_user):
    child = make_child(centre)
    inactive = make_user(
        "inactive_user", role=UserRole.AWW, centre=centre, is_active=False
    )
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GENERAL,
        severity=AlertSeverity.LOW,
        message="Inactive assignee.",
        beneficiary=child.beneficiary,
    )
    db.session.commit()

    with pytest.raises(ValidationError):
        alert_service.assign_alert(alert, inactive)
    assert db.session.get(Alert, alert.id).assigned_to_id is None


def test_route_rejects_invalid_assignee_role(
    client, db, centre, make_user, make_child
):
    child = make_child(centre)
    officer = make_user("officer_assign", role=UserRole.OFFICER, centre=centre)
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GENERAL,
        severity=AlertSeverity.LOW,
        message="Route assign validation.",
        beneficiary=child.beneficiary,
    )
    db.session.commit()
    make_user("aww_alert", role=UserRole.AWW, centre=centre)
    login(client, "aww_alert")

    response = client.post(
        f"/alerts/{alert.id}/assign", data={"assigned_to_id": str(officer.id)}
    )

    assert response.status_code == 302
    assert db.session.get(Alert, alert.id).assigned_to_id is None


def test_aww_cannot_assign_alert_to_other_centre_worker(
    client, db, centre, other_centre, make_user, make_child
):
    child = make_child(centre)
    outsider = make_user("outside_aww", role=UserRole.AWW, centre=other_centre)
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GENERAL,
        severity=AlertSeverity.LOW,
        message="Cross-centre assignment.",
        beneficiary=child.beneficiary,
    )
    db.session.commit()
    make_user("aww_alert", role=UserRole.AWW, centre=centre)
    login(client, "aww_alert")

    response = client.post(
        f"/alerts/{alert.id}/assign", data={"assigned_to_id": str(outsider.id)}
    )

    assert response.status_code == 302
    assert db.session.get(Alert, alert.id).assigned_to_id is None


def test_admin_can_assign_alert_to_any_worker(
    client, db, centre, other_centre, make_user, make_child
):
    child = make_child(centre)
    outsider = make_user("outside_aww", role=UserRole.AWW, centre=other_centre)
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GENERAL,
        severity=AlertSeverity.LOW,
        message="Global assignment.",
        beneficiary=child.beneficiary,
    )
    db.session.commit()
    make_user("admin_alert", role=UserRole.ADMIN)
    login(client, "admin_alert")

    response = client.post(
        f"/alerts/{alert.id}/assign", data={"assigned_to_id": str(outsider.id)}
    )

    assert response.status_code == 302
    assert db.session.get(Alert, alert.id).assigned_to_id == outsider.id


def test_assignable_users_are_centre_scoped_for_aww(
    db, centre, other_centre, make_user
):
    own = make_user("own_aww", role=UserRole.AWW, centre=centre)
    outsider = make_user("outside_aww", role=UserRole.AWW, centre=other_centre)
    admin = make_user("admin_user", role=UserRole.ADMIN)
    supervisor = make_user("supervisor_user", role=UserRole.SUPERVISOR)

    scoped = alert_service.assignable_users(scope_centre_id=centre.id)
    ids = {user.id for user in scoped}

    assert own.id in ids
    assert admin.id in ids
    assert supervisor.id in ids
    assert outsider.id not in ids