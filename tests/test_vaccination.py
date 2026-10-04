"""Phase 5 vaccination tests: creation, history, edit, validation, permissions."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import AnganwadiCentre, Beneficiary, Child, User, Vaccination
from app.services import vaccination_service
from app.utils.constants import (
    BeneficiaryType,
    Gender,
    RecordStatus,
    UserRole,
    VaccinationStatus,
)
from app.utils.vaccination_rules import (
    VaccinationDisplayStatus,
    display_status,
    is_overdue,
)

PASSWORD = "password123"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def centre(db):
    centre = AnganwadiCentre(name="Vaccine Centre A", code="VCA-001", is_active=True)
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def other_centre(db):
    centre = AnganwadiCentre(name="Vaccine Centre B", code="VCB-001", is_active=True)
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
    def make(centre, name="Vaccine Child", dob=None):
        two_years_ago = date.today().replace(year=date.today().year - 2)
        beneficiary = Beneficiary(
            centre=centre,
            beneficiary_type=BeneficiaryType.CHILD,
            full_name=name,
            date_of_birth=dob or two_years_ago,
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
def make_vaccination(db):
    def make(child, vaccine_name="BCG", dose_number=1, **overrides):
        data = {
            "vaccine_name": vaccine_name,
            "dose_number": dose_number,
            "scheduled_date": date.today() - timedelta(days=10),
            "administered_date": date.today() - timedelta(days=8),
            "status": VaccinationStatus.COMPLETED,
        }
        data.update(overrides)
        vaccination = Vaccination(child=child, **data)
        db.session.add(vaccination)
        db.session.commit()
        return vaccination

    return make


def login(client, username, password=PASSWORD):
    return client.post("/login", data={"username": username, "password": password})


def vaccination_form(**overrides):
    data = {
        "vaccine_name": "BCG",
        "dose_number": "1",
        "scheduled_date": (date.today() - timedelta(days=10)).isoformat(),
        "administered_date": (date.today() - timedelta(days=8)).isoformat(),
        "status": "COMPLETED",
        "notes": "Routine demo vaccination.",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Display-rule unit tests
# ---------------------------------------------------------------------------
class _Record:
    """Tiny stand-in so display rules can be tested without the database."""

    def __init__(self, status, scheduled_date=None):
        self.status = status
        self.scheduled_date = scheduled_date


def test_display_status_completed_and_missed():
    assert (
        display_status(_Record(VaccinationStatus.COMPLETED))
        == VaccinationDisplayStatus.COMPLETED
    )
    assert (
        display_status(_Record(VaccinationStatus.MISSED))
        == VaccinationDisplayStatus.MISSED
    )


def test_display_status_overdue_is_derived_only_from_stored_dates():
    past = date.today() - timedelta(days=1)
    future = date.today() + timedelta(days=1)

    assert (
        display_status(_Record(VaccinationStatus.DUE, past))
        == VaccinationDisplayStatus.OVERDUE
    )
    assert (
        display_status(_Record(VaccinationStatus.UPCOMING, past))
        == VaccinationDisplayStatus.OVERDUE
    )
    assert (
        display_status(_Record(VaccinationStatus.DUE, future))
        == VaccinationDisplayStatus.DUE
    )
    assert (
        display_status(_Record(VaccinationStatus.UPCOMING, future))
        == VaccinationDisplayStatus.UPCOMING
    )
    # No scheduled date means it can never become overdue.
    assert (
        display_status(_Record(VaccinationStatus.UPCOMING, None))
        == VaccinationDisplayStatus.UPCOMING
    )
    assert is_overdue(_Record(VaccinationStatus.DUE, past)) is True
    assert is_overdue(_Record(VaccinationStatus.COMPLETED, past)) is False


# ---------------------------------------------------------------------------
# Create / history
# ---------------------------------------------------------------------------
def test_aww_can_record_vaccination(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")

    response = client.post(
        f"/children/{child.id}/vaccinations/new", data=vaccination_form()
    )

    assert response.status_code == 302
    record = Vaccination.query.filter_by(child_id=child.id).one()
    assert record.vaccine_name == "BCG"
    assert record.dose_number == 1
    assert record.status == VaccinationStatus.COMPLETED
    assert record.administered_by is not None
    assert response.headers["Location"].endswith(f"/children/{child.id}/vaccinations")


def test_admin_can_record_vaccination(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("admin_vac", role=UserRole.ADMIN)
    login(client, "admin_vac")

    response = client.post(
        f"/children/{child.id}/vaccinations/new", data=vaccination_form()
    )

    assert response.status_code == 302
    assert Vaccination.query.count() == 1


def test_history_page_renders(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")
    client.post(f"/children/{child.id}/vaccinations/new", data=vaccination_form())

    response = client.get(f"/children/{child.id}/vaccinations")

    assert response.status_code == 200
    assert b"Vaccination history" in response.data
    assert b"Vaccine Child" in response.data
    assert b"Completed" in response.data
    assert b"BCG" in response.data


def test_history_empty_state(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")

    response = client.get(f"/children/{child.id}/vaccinations")

    assert response.status_code == 200
    assert b"No vaccination records found" in response.data


def test_history_shows_demo_disclaimer(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")
    client.post(f"/children/{child.id}/vaccinations/new", data=vaccination_form())

    response = client.get(f"/children/{child.id}/vaccinations")

    assert b"project-defined demo view" in response.data.lower()
    assert b"not medical guidance" in response.data.lower()


def test_summary_counts_and_history_order(client, db, centre, make_user, make_child, make_vaccination):
    child = make_child(centre)
    make_vaccination(child, "BCG", 1, status=VaccinationStatus.COMPLETED)
    make_vaccination(
        child,
        "OPV",
        1,
        status=VaccinationStatus.DUE,
        scheduled_date=date.today() - timedelta(days=2),
        administered_date=None,
    )
    make_vaccination(
        child,
        "Measles",
        1,
        status=VaccinationStatus.UPCOMING,
        scheduled_date=date.today() + timedelta(days=30),
        administered_date=None,
    )

    data = vaccination_service.summary(child)
    assert data["total"] == 3
    assert data["completed"] == 1
    assert data["overdue"] == 1
    assert data["pending"] == 1

    history = vaccination_service.build_history(child)
    dates = [item["record"].scheduled_date for item in history]
    assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
def test_edit_vaccination_record(client, db, centre, make_user, make_child, make_vaccination):
    child = make_child(centre)
    record = make_vaccination(child, "BCG", 1)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")

    response = client.post(
        f"/children/{child.id}/vaccinations/{record.id}/edit",
        data=vaccination_form(status="MISSED", administered_date=""),
    )

    assert response.status_code == 302
    db.session.refresh(record)
    assert record.status == VaccinationStatus.MISSED
    assert record.administered_date is None
    assert record.administered_by is None


def test_edit_form_is_prefilled(client, db, centre, make_user, make_child, make_vaccination):
    child = make_child(centre)
    record = make_vaccination(child, "OPV", 2)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")

    response = client.get(
        f"/children/{child.id}/vaccinations/{record.id}/edit"
    )

    assert response.status_code == 200
    assert b'value="OPV"' in response.data
    assert b'value="2"' in response.data


def test_edit_record_of_another_child_is_404(
    client, db, centre, make_user, make_child, make_vaccination
):
    child = make_child(centre, name="Child One")
    other = make_child(centre, name="Child Two")
    record = make_vaccination(other, "BCG", 1)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")

    response = client.get(f"/children/{child.id}/vaccinations/{record.id}/edit")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "override, expected",
    [
        ({"vaccine_name": ""}, b"Vaccine name is required"),
        ({"dose_number": ""}, b"Dose number is required"),
        ({"dose_number": "0"}, b"at least"),
        ({"scheduled_date": "not-a-date"}, b"valid date"),
        ({"status": ""}, b"Status is required"),
        (
            {"status": "COMPLETED", "administered_date": ""},
            b"Administered date is required",
        ),
        (
            {"status": "UPCOMING"},
            b"Clear the administered date",
        ),
        (
            {"administered_date": (date.today() + timedelta(days=1)).isoformat()},
            b"cannot be in the future",
        ),
        (
            {
                "scheduled_date": (date.today() - timedelta(days=20)).isoformat(),
                "administered_date": (date.today() - timedelta(days=25)).isoformat(),
            },
            b"before the scheduled date",
        ),
    ],
)
def test_vaccination_validation_errors(
    client, db, centre, make_user, make_child, override, expected
):
    child = make_child(centre)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")

    response = client.post(
        f"/children/{child.id}/vaccinations/new", data=vaccination_form(**override)
    )

    assert response.status_code == 400
    assert expected in response.data
    assert Vaccination.query.count() == 0


def test_scheduled_date_before_birth_rejected(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")

    early = date.today() - timedelta(days=2 * 365 + 60)
    response = client.post(
        f"/children/{child.id}/vaccinations/new",
        data=vaccination_form(scheduled_date=early.isoformat()),
    )

    assert response.status_code == 400
    assert b"before the child" in response.data


# ---------------------------------------------------------------------------
# Duplicate handling
# ---------------------------------------------------------------------------
def test_duplicate_vaccine_dose_rejected(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")
    client.post(f"/children/{child.id}/vaccinations/new", data=vaccination_form())

    response = client.post(
        f"/children/{child.id}/vaccinations/new", data=vaccination_form()
    )

    assert response.status_code == 400
    assert b"already exists" in response.data
    assert Vaccination.query.count() == 1


def test_duplicate_check_is_case_insensitive(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")
    client.post(
        f"/children/{child.id}/vaccinations/new",
        data=vaccination_form(vaccine_name="BCG"),
    )

    response = client.post(
        f"/children/{child.id}/vaccinations/new",
        data=vaccination_form(vaccine_name="bcg"),
    )

    assert response.status_code == 400
    assert b"already exists" in response.data
    assert Vaccination.query.count() == 1


def test_edit_into_duplicate_rejected(
    client, db, centre, make_user, make_child, make_vaccination
):
    child = make_child(centre)
    make_vaccination(child, "BCG", 1)
    record = make_vaccination(child, "OPV", 1)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")

    response = client.post(
        f"/children/{child.id}/vaccinations/{record.id}/edit",
        data=vaccination_form(vaccine_name="BCG", dose_number="1"),
    )

    assert response.status_code == 400
    assert b"already exists" in response.data
    assert Vaccination.query.count() == 2


# ---------------------------------------------------------------------------
# Role permissions / centre scoping
# ---------------------------------------------------------------------------
def test_vaccination_requires_login(client, db, centre, make_child):
    child = make_child(centre)
    response = client.get(f"/children/{child.id}/vaccinations")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize("role", [UserRole.SUPERVISOR, UserRole.OFFICER])
def test_read_only_roles_can_view_but_not_modify(
    client, db, centre, make_user, make_child, role
):
    child = make_child(centre)
    make_user("reader", role=role)
    login(client, "reader")

    assert client.get(f"/children/{child.id}/vaccinations").status_code == 200
    assert (
        client.post(
            f"/children/{child.id}/vaccinations/new", data=vaccination_form()
        ).status_code
        == 403
    )
    assert Vaccination.query.count() == 0


def test_aww_cannot_access_other_centres_child(
    client, db, centre, other_centre, make_user, make_child, make_vaccination
):
    child = make_child(other_centre, name="Other Centre Child")
    record = make_vaccination(child, "BCG", 1)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")

    assert client.get(f"/children/{child.id}/vaccinations").status_code == 403
    assert (
        client.post(
            f"/children/{child.id}/vaccinations/new", data=vaccination_form()
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/children/{child.id}/vaccinations/{record.id}/edit"
        ).status_code
        == 403
    )


# ---------------------------------------------------------------------------
# Child profile integration
# ---------------------------------------------------------------------------
def test_child_profile_links_to_vaccination(client, db, centre, make_user, make_child):
    child = make_child(centre)
    make_user("aww_vac", role=UserRole.AWW, centre=centre)
    login(client, "aww_vac")

    response = client.get(f"/beneficiaries/{child.beneficiary_id}")

    assert response.status_code == 200
    assert b"View vaccination history" in response.data
    assert f"/children/{child.id}/vaccinations".encode() in response.data
