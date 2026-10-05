"""Phase 9 home-visit / intervention tests + cross-module integration."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import (
    Alert,
    AnganwadiCentre,
    Beneficiary,
    Child,
    HomeVisit,
    Intervention,
    User,
)
from app.services import alert_service, visit_service
from app.utils.constants import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    BeneficiaryType,
    Gender,
    RecordStatus,
    UserRole,
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
    centre = AnganwadiCentre(name="Visit Centre A", code="VSA-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def other_centre(db):
    centre = AnganwadiCentre(name="Visit Centre B", code="VSB-001", is_active=True)
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
    def make(centre, name="Visit Child"):
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
def make_visit(db):
    def make(beneficiary, centre, worker=None, status=VisitStatus.SCHEDULED, **overrides):
        data = {
            "beneficiary_id": beneficiary.id,
            "centre_id": centre.id,
            "visit_type": VisitType.ROUTINE,
            "assigned_worker": worker,
            "scheduled_date": date.today(),
            "status": status,
        }
        data.update(overrides)
        visit = HomeVisit(**data)
        db.session.add(visit)
        db.session.commit()
        return visit

    return make


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


def visit_form(beneficiary, worker=None, **overrides):
    data = {
        "beneficiary_id": str(beneficiary.id),
        "visit_type": VisitType.ROUTINE.value,
        "scheduled_date": date.today().isoformat(),
        "visit_notes": "Routine demo visit.",
    }
    if worker is not None:
        data["assigned_worker_id"] = str(worker.id)
    data.update(overrides)
    return data


def intervention_form(**overrides):
    data = {
        "intervention_type": "Nutrition counselling",
        "intervention_date": date.today().isoformat(),
        "description": "Counselled the family on feeding.",
        "outcome": "Family counselled.",
    }
    data.update(overrides)
    return data


def growth_form(**overrides):
    data = {
        "measurement_date": date.today().isoformat(),
        "weight_kg": "10.0",
        "height_cm": "85.0",
        "muac_cm": "14.5",
        "notes": "Routine demo measurement.",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Scheduling / editing
# ---------------------------------------------------------------------------
def test_visits_require_login(client, db):
    response = client.get("/visits/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_aww_can_schedule_visit(client, db, centre, make_user, make_child):
    child = make_child(centre)
    worker = make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post("/visits/new", data=visit_form(child.beneficiary, worker))

    assert response.status_code == 302
    visit = HomeVisit.query.filter_by(beneficiary_id=child.beneficiary_id).one()
    assert visit.status == VisitStatus.SCHEDULED
    assert visit.centre_id == centre.id
    assert visit.assigned_worker_id == worker.id


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"beneficiary_id": ""}, b"Please select a beneficiary"),
        ({"scheduled_date": ""}, b"Scheduled date is required"),
    ],
)
def test_visit_validation(
    client, db, centre, make_user, make_child, override, expected
):
    child = make_child(centre)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(
        "/visits/new", data=visit_form(child.beneficiary, **override)
    )

    assert response.status_code == 400
    assert expected in response.data
    assert HomeVisit.query.count() == 0


def test_edit_visit(client, db, centre, make_user, make_child, make_visit):
    child = make_child(centre)
    visit = make_visit(child.beneficiary, centre)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(
        f"/visits/{visit.id}/edit",
        data=visit_form(
            child.beneficiary,
            visit_type=VisitType.GROWTH.value,
            visit_notes="Changed notes.",
        ),
    )

    assert response.status_code == 302
    refreshed = db.session.get(HomeVisit, visit.id)
    assert refreshed.visit_type == VisitType.GROWTH
    assert refreshed.visit_notes == "Changed notes."


# ---------------------------------------------------------------------------
# Complete / cancel
# ---------------------------------------------------------------------------
def test_complete_visit(client, db, centre, make_user, make_child, make_visit):
    child = make_child(centre)
    visit = make_visit(child.beneficiary, centre)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(
        f"/visits/{visit.id}/complete",
        data={
            "completed_date": date.today().isoformat(),
            "visit_notes": "Visited the household.",
        },
    )

    assert response.status_code == 302
    refreshed = db.session.get(HomeVisit, visit.id)
    assert refreshed.status == VisitStatus.COMPLETED
    assert refreshed.completed_date == date.today()


def test_cancel_visit(client, db, centre, make_user, make_child, make_visit):
    child = make_child(centre)
    visit = make_visit(child.beneficiary, centre)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(f"/visits/{visit.id}/cancel")

    assert response.status_code == 302
    assert db.session.get(HomeVisit, visit.id).status == VisitStatus.CANCELLED


# ---------------------------------------------------------------------------
# Interventions
# ---------------------------------------------------------------------------
def test_record_intervention(
    client, db, centre, make_user, make_child, make_visit
):
    child = make_child(centre)
    visit = make_visit(child.beneficiary, centre, status=VisitStatus.COMPLETED)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(
        f"/visits/{visit.id}/interventions/new",
        data=intervention_form(
            follow_up_required="on",
            follow_up_date=(date.today() + timedelta(days=10)).isoformat(),
        ),
    )

    assert response.status_code == 302
    intervention = Intervention.query.filter_by(beneficiary_id=child.beneficiary_id).one()
    assert intervention.intervention_type == "Nutrition counselling"
    refreshed = db.session.get(HomeVisit, visit.id)
    assert refreshed.follow_up_required is True
    assert refreshed.follow_up_date == date.today() + timedelta(days=10)


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"intervention_type": ""}, b"Intervention type is required"),
        (
            {"follow_up_required": "on", "follow_up_date": ""},
            b"Follow-up date is required",
        ),
        (
            {
                "intervention_date": (date.today() + timedelta(days=1)).isoformat(),
            },
            b"cannot be in the future",
        ),
    ],
)
def test_intervention_validation(
    client, db, centre, make_user, make_child, make_visit, override, expected
):
    child = make_child(centre)
    visit = make_visit(child.beneficiary, centre, status=VisitStatus.COMPLETED)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(
        f"/visits/{visit.id}/interventions/new",
        data=intervention_form(**override),
    )

    assert response.status_code == 400
    assert expected in response.data
    assert Intervention.query.count() == 0


def test_intervention_resolves_alert(
    client, db, centre, make_user, make_child, make_visit
):
    child = make_child(centre)
    alert, _ = alert_service.upsert_alert(
        alert_type=AlertType.GROWTH_FOLLOW_UP,
        severity=AlertSeverity.HIGH,
        message="Resolve me after the visit.",
        beneficiary=child.beneficiary,
        child=child,
    )
    db.session.commit()
    visit = make_visit(child.beneficiary, centre, status=VisitStatus.COMPLETED)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(
        f"/visits/{visit.id}/interventions/new",
        data=intervention_form(resolve_alert_id=str(alert.id)),
    )

    assert response.status_code == 302
    refreshed = db.session.get(Alert, alert.id)
    assert refreshed.status == AlertStatus.RESOLVED
    assert refreshed.resolution_notes is not None


# ---------------------------------------------------------------------------
# Permissions / scoping
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role", [UserRole.SUPERVISOR, UserRole.OFFICER])
def test_read_only_roles_cannot_write_visits(
    client, db, centre, make_user, make_child, role
):
    child = make_child(centre)
    make_user("reader", role=role)
    login(client, "reader")

    assert client.get("/visits/").status_code == 200
    assert (
        client.post("/visits/new", data=visit_form(child.beneficiary)).status_code
        == 403
    )


def test_aww_cannot_view_other_centre_visit(
    client, db, centre, other_centre, make_user, make_child, make_visit
):
    other = make_child(other_centre, name="Other Visit Child")
    visit = make_visit(other.beneficiary, other_centre)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    assert client.get(f"/visits/{visit.id}").status_code == 403


def test_follow_up_filter_lists_only_follow_ups(
    client, db, centre, make_user, make_child, make_visit
):
    child = make_child(centre, name="Follow Up Child")
    other = make_child(centre, name="Routine Child")
    make_visit(
        child.beneficiary,
        centre,
        follow_up_required=True,
        follow_up_date=date.today() + timedelta(days=5),
    )
    make_visit(other.beneficiary, centre)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.get("/visits/?follow_up=1")

    assert response.status_code == 200
    assert b"Follow Up Child" in response.data
    assert b"Routine Child" not in response.data


def test_visit_index_is_centre_scoped(
    client, db, centre, other_centre, make_user, make_child, make_visit
):
    own = make_child(centre, name="Own Visit Child")
    other = make_child(other_centre, name="Other Visit Child")
    make_visit(own.beneficiary, centre)
    make_visit(other.beneficiary, other_centre)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.get("/visits/")

    assert response.status_code == 200
    assert b"Own Visit Child" in response.data
    assert b"Other Visit Child" not in response.data


# ---------------------------------------------------------------------------
# Rule integration (visit <-> alert)
# ---------------------------------------------------------------------------
def test_overdue_visit_creates_and_completion_resolves_alert(
    client, db, centre, make_user, make_child
):
    child = make_child(centre)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    # Schedule an overdue visit directly (bypassing the form date rules).
    visit = HomeVisit(
        beneficiary=child.beneficiary,
        centre=centre,
        visit_type=VisitType.ROUTINE,
        scheduled_date=date.today() - timedelta(days=3),
        status=VisitStatus.SCHEDULED,
    )
    db.session.add(visit)
    db.session.commit()
    alert_service.sync_home_visit_pending(child.beneficiary)
    db.session.commit()
    assert (
        alert_service.open_alert(
            AlertType.HOME_VISIT_PENDING, beneficiary=child.beneficiary
        )
        is not None
    )

    client.post(
        f"/visits/{visit.id}/complete",
        data={"completed_date": date.today().isoformat()},
    )

    assert (
        alert_service.open_alert(
            AlertType.HOME_VISIT_PENDING, beneficiary=child.beneficiary
        )
        is None
    )


# ---------------------------------------------------------------------------
# Cross-module integration: growth -> alert -> visit -> intervention -> resolve
# ---------------------------------------------------------------------------
def test_full_alert_to_resolution_workflow(client, db, centre, make_user, make_child):
    child = make_child(centre, name="Workflow Child")
    worker = make_user("aww_flow", role=UserRole.AWW, centre=centre)
    login(client, "aww_flow")

    # 1. A concerning growth record generates a deterministic alert.
    client.post(f"/children/{child.id}/growth/new", data=growth_form(weight_kg="7.0"))
    alert = Alert.query.filter_by(
        child_id=child.id, alert_type=AlertType.GROWTH_FOLLOW_UP
    ).one()
    assert alert.status == AlertStatus.OPEN

    # 2. Schedule a home visit for the child.
    response = client.post("/visits/new", data=visit_form(child.beneficiary, worker))
    assert response.status_code == 302
    visit = HomeVisit.query.filter_by(beneficiary_id=child.beneficiary_id).one()

    # 3. Complete the visit.
    client.post(
        f"/visits/{visit.id}/complete",
        data={
            "completed_date": date.today().isoformat(),
            "visit_notes": "Home visit completed.",
        },
    )
    assert db.session.get(HomeVisit, visit.id).status == VisitStatus.COMPLETED

    # 4. Record an intervention that resolves the alert.
    response = client.post(
        f"/visits/{visit.id}/interventions/new",
        data=intervention_form(
            description="Provided counselling and a nutrition demonstration.",
            outcome="Caregiver understood the guidance.",
            resolve_alert_id=str(alert.id),
        ),
    )
    assert response.status_code == 302

    refreshed = db.session.get(Alert, alert.id)
    assert refreshed.status == AlertStatus.RESOLVED
    assert alert_service.open_alert(AlertType.GROWTH_FOLLOW_UP, child=child) is None
    assert Intervention.query.filter_by(beneficiary_id=child.beneficiary_id).count() == 1


# ---------------------------------------------------------------------------
# Backend validation: intervention requires a completed visit
# ---------------------------------------------------------------------------
def test_intervention_rejected_for_scheduled_visit(
    client, db, centre, make_user, make_child, make_visit
):
    child = make_child(centre)
    visit = make_visit(child.beneficiary, centre, status=VisitStatus.SCHEDULED)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(
        f"/visits/{visit.id}/interventions/new", data=intervention_form()
    )

    assert response.status_code == 400
    assert b"only be recorded for a completed visit" in response.data
    assert Intervention.query.count() == 0


def test_service_rejects_intervention_for_non_completed_visit(
    db, centre, make_child, make_visit
):
    child = make_child(centre)
    visit = make_visit(child.beneficiary, centre, status=VisitStatus.SCHEDULED)

    with pytest.raises(ValidationError) as excinfo:
        visit_service.record_intervention(visit, intervention_form())

    assert "visit" in excinfo.value.errors
    assert Intervention.query.count() == 0


# ---------------------------------------------------------------------------
# Backend validation: assigned worker role / centre
# ---------------------------------------------------------------------------
def test_visit_rejects_non_worker_role(
    client, db, centre, make_user, make_child
):
    child = make_child(centre)
    officer = make_user("officer_visit", role=UserRole.OFFICER, centre=centre)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(
        "/visits/new", data=visit_form(child.beneficiary, worker=officer)
    )

    assert response.status_code == 400
    assert HomeVisit.query.count() == 0


def test_service_rejects_non_worker_role(db, centre, make_child, make_user):
    child = make_child(centre)
    officer = make_user("officer_visit", role=UserRole.OFFICER, centre=centre)

    with pytest.raises(ValidationError) as excinfo:
        visit_service.create_visit(child.beneficiary, officer, visit_form(child.beneficiary))

    assert "assigned_worker_id" in excinfo.value.errors
    assert HomeVisit.query.count() == 0


def test_aww_cannot_assign_worker_from_another_centre(
    client, db, centre, other_centre, make_user, make_child
):
    child = make_child(centre)
    outsider = make_user("outside_aww", role=UserRole.AWW, centre=other_centre)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(
        "/visits/new", data=visit_form(child.beneficiary, worker=outsider)
    )

    assert response.status_code == 400
    assert HomeVisit.query.count() == 0


def test_admin_can_assign_worker_from_another_centre(
    client, db, centre, other_centre, make_user, make_child
):
    child = make_child(centre)
    outsider = make_user("outside_aww", role=UserRole.AWW, centre=other_centre)
    make_user("admin_visit", role=UserRole.ADMIN)
    login(client, "admin_visit")

    response = client.post(
        "/visits/new", data=visit_form(child.beneficiary, worker=outsider)
    )

    assert response.status_code == 302
    visit = HomeVisit.query.filter_by(beneficiary_id=child.beneficiary_id).one()
    assert visit.assigned_worker_id == outsider.id


def test_inactive_worker_rejected(client, db, centre, make_user, make_child):
    child = make_child(centre)
    inactive = make_user(
        "inactive_aww", role=UserRole.AWW, centre=centre, is_active=False
    )
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(
        "/visits/new", data=visit_form(child.beneficiary, worker=inactive)
    )

    assert response.status_code == 400
    assert HomeVisit.query.count() == 0


# ---------------------------------------------------------------------------
# Backend validation: visit state machine (Scheduled → Completed)
# ---------------------------------------------------------------------------
def test_cannot_complete_a_cancelled_visit(
    client, db, centre, make_user, make_child, make_visit
):
    child = make_child(centre)
    visit = make_visit(child.beneficiary, centre, status=VisitStatus.CANCELLED)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(
        f"/visits/{visit.id}/complete",
        data={"completed_date": date.today().isoformat()},
    )

    assert response.status_code == 302
    refreshed = db.session.get(HomeVisit, visit.id)
    assert refreshed.status == VisitStatus.CANCELLED
    assert refreshed.completed_date is None


def test_service_rejects_completing_a_cancelled_visit(
    db, centre, make_child, make_visit
):
    child = make_child(centre)
    visit = make_visit(child.beneficiary, centre, status=VisitStatus.CANCELLED)

    with pytest.raises(ValidationError) as excinfo:
        visit_service.complete_visit(
            visit, {"completed_date": date.today().isoformat()}
        )

    assert "visit" in excinfo.value.errors
    assert visit.status == VisitStatus.CANCELLED


def test_cannot_cancel_a_completed_visit(
    client, db, centre, make_user, make_child, make_visit
):
    child = make_child(centre)
    visit = make_visit(
        child.beneficiary,
        centre,
        status=VisitStatus.COMPLETED,
        completed_date=date.today(),
    )
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.post(f"/visits/{visit.id}/cancel")

    assert response.status_code == 302
    refreshed = db.session.get(HomeVisit, visit.id)
    assert refreshed.status == VisitStatus.COMPLETED
    assert refreshed.completed_date == date.today()


def test_service_rejects_cancelling_a_completed_visit(
    db, centre, make_child, make_visit
):
    child = make_child(centre)
    visit = make_visit(
        child.beneficiary,
        centre,
        status=VisitStatus.COMPLETED,
        completed_date=date.today(),
    )

    with pytest.raises(ValidationError):
        visit_service.cancel_visit(visit)

    assert visit.status == VisitStatus.COMPLETED


def test_recompleting_a_completed_visit_does_not_backdate(
    db, centre, make_child, make_visit
):
    """A completed visit cannot be re-completed with an arbitrary date."""
    child = make_child(centre)
    completed = date.today() - timedelta(days=2)
    visit = make_visit(
        child.beneficiary,
        centre,
        status=VisitStatus.COMPLETED,
        completed_date=completed,
    )

    with pytest.raises(ValidationError):
        visit_service.complete_visit(
            visit, {"completed_date": "2020-01-01"}
        )

    assert visit.completed_date == completed


# ---------------------------------------------------------------------------
# Beneficiary profile integration
# ---------------------------------------------------------------------------
def test_beneficiary_profile_links_to_visits_and_alerts(
    client, db, centre, make_user, make_child
):
    child = make_child(centre)
    make_user("aww_visit", role=UserRole.AWW, centre=centre)
    login(client, "aww_visit")

    response = client.get(f"/beneficiaries/{child.beneficiary_id}")

    assert response.status_code == 200
    assert f"/visits/?beneficiary={child.beneficiary_id}".encode() in response.data
    assert f"/alerts/?beneficiary={child.beneficiary_id}".encode() in response.data
