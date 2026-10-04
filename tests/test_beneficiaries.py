"""Phase 3 beneficiary management tests: CRUD, validation, search and roles."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models import AnganwadiCentre, Beneficiary, Child, Mother, User
from app.utils.constants import (
    BeneficiaryType,
    Gender,
    RecordStatus,
    RiskLevel,
    UserRole,
)

PASSWORD = "password123"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def centre(db):
    centre = AnganwadiCentre(
        name="Test Centre Alpha",
        code="TCA-001",
        village="Alpha",
        district="Testdistrict",
        state="Teststate",
        pincode="462001",
        phone="9876543210",
        is_active=True,
    )
    db.session.add(centre)
    db.session.commit()
    return centre


@pytest.fixture()
def other_centre(db):
    centre = AnganwadiCentre(
        name="Test Centre Beta",
        code="TCB-001",
        village="Beta",
        district="Testdistrict",
        state="Teststate",
        is_active=True,
    )
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


def login(client, username, password=PASSWORD):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def child_form(**overrides):
    data = {
        "full_name": "Demo Child",
        "date_of_birth": (date.today() - timedelta(days=730)).isoformat(),
        "gender": "FEMALE",
        "guardian_name": "Demo Guardian",
        "contact": "9876501234",
        "address": "House 1, Alpha",
        "registration_date": date.today().isoformat(),
        "birth_weight_kg": "2.80",
        "birth_height_cm": "48.0",
        "blood_group": "O+",
    }
    data.update(overrides)
    return data


def mother_form(kind="pregnant", **overrides):
    data = {
        "full_name": "Demo Mother",
        "date_of_birth": (date.today() - timedelta(days=25 * 365)).isoformat(),
        "age": "25",
        "husband_name": "Demo Husband",
        "pregnancy_number": "2",
        "blood_group": "B+",
        "height_cm": "155.0",
        "current_risk_level": "LOW",
        "contact": "9876505678",
        "address": "House 9, Alpha",
        "registration_date": date.today().isoformat(),
    }
    if kind == "pregnant":
        data["last_menstrual_period"] = (date.today() - timedelta(days=90)).isoformat()
        data["expected_delivery_date"] = (date.today() + timedelta(days=180)).isoformat()
    else:
        data["delivery_date"] = (date.today() - timedelta(days=30)).isoformat()
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def test_aww_can_register_child(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")

    response = client.post("/beneficiaries/new/child", data=child_form())

    assert response.status_code == 302
    beneficiary = Beneficiary.query.filter_by(full_name="Demo Child").one()
    assert beneficiary.beneficiary_type == BeneficiaryType.CHILD
    assert beneficiary.centre_id == centre.id
    assert beneficiary.child is not None
    assert beneficiary.child.birth_weight_kg == Decimal("2.80")
    assert response.headers["Location"].endswith(f"/beneficiaries/{beneficiary.id}")


def test_register_pregnant_woman(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")

    response = client.post(
        "/beneficiaries/new/mother/pregnant", data=mother_form("pregnant")
    )

    assert response.status_code == 302
    mother = Mother.query.filter_by(age=25).one()
    assert mother.beneficiary.beneficiary_type == BeneficiaryType.PREGNANT_WOMAN
    assert mother.expected_delivery_date is not None


def test_register_lactating_mother(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")

    response = client.post(
        "/beneficiaries/new/mother/lactating", data=mother_form("lactating")
    )

    assert response.status_code == 302
    mother = Mother.query.filter(Mother.delivery_date.isnot(None)).one()
    assert mother.beneficiary.beneficiary_type == BeneficiaryType.LACTATING_MOTHER


def test_admin_can_select_centre(client, db, centre, make_user):
    make_user("admin", role=UserRole.ADMIN)
    login(client, "admin")

    response = client.post(
        "/beneficiaries/new/child",
        data=child_form(centre_id=str(centre.id)),
    )

    assert response.status_code == 302
    beneficiary = Beneficiary.query.filter_by(full_name="Demo Child").one()
    assert beneficiary.centre_id == centre.id


# ---------------------------------------------------------------------------
# Read / list / search
# ---------------------------------------------------------------------------
def test_list_renders(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")
    client.post("/beneficiaries/new/child", data=child_form())

    response = client.get("/beneficiaries/")

    assert response.status_code == 200
    assert b"Demo Child" in response.data
    assert b"Beneficiaries" in response.data


def test_search_filters_by_name(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")
    client.post(
        "/beneficiaries/new/child",
        data=child_form(full_name="Aarav Sharma"),
        follow_redirects=True,
    )
    client.post(
        "/beneficiaries/new/child",
        data=child_form(full_name="Diya Verma", date_of_birth=(date.today() - timedelta(days=900)).isoformat()),
        follow_redirects=True,
    )

    response = client.get("/beneficiaries/?q=Aarav")

    assert response.status_code == 200
    assert b"Aarav Sharma" in response.data
    assert b"Diya Verma" not in response.data


def test_search_filters_by_type(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")
    client.post(
        "/beneficiaries/new/child",
        data=child_form(full_name="Only Child"),
        follow_redirects=True,
    )
    client.post(
        "/beneficiaries/new/mother/pregnant",
        data=mother_form("pregnant", full_name="Only Mother"),
        follow_redirects=True,
    )

    response = client.get("/beneficiaries/?type=PREGNANT_WOMAN")

    assert response.status_code == 200
    assert b"Only Mother" in response.data
    assert b"Only Child" not in response.data


def test_pagination_renders_multiple_pages(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")
    for index in range(12):
        client.post(
            "/beneficiaries/new/child",
            data=child_form(
                full_name=f"Paged Child {index}",
                date_of_birth=(date.today() - timedelta(days=300 + index)).isoformat(),
            ),
        )

    response = client.get("/beneficiaries/")

    assert response.status_code == 200
    assert b"page=2" in response.data


def test_detail_page_shows_profile(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")
    client.post("/beneficiaries/new/child", data=child_form())
    beneficiary = Beneficiary.query.filter_by(full_name="Demo Child").one()

    response = client.get(f"/beneficiaries/{beneficiary.id}")

    assert response.status_code == 200
    assert b"Demo Child" in response.data
    assert b"Child profile" in response.data


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
def test_update_child_profile(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")
    client.post("/beneficiaries/new/child", data=child_form())
    beneficiary = Beneficiary.query.filter_by(full_name="Demo Child").one()

    response = client.post(
        f"/beneficiaries/{beneficiary.id}/edit",
        data=child_form(full_name="Updated Child", birth_weight_kg="3.10"),
    )

    assert response.status_code == 302
    db.session.refresh(beneficiary)
    assert beneficiary.full_name == "Updated Child"
    assert beneficiary.child.birth_weight_kg == Decimal("3.10")


def test_edit_form_is_prefilled(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")
    client.post("/beneficiaries/new/child", data=child_form())
    beneficiary = Beneficiary.query.filter_by(full_name="Demo Child").one()

    response = client.get(f"/beneficiaries/{beneficiary.id}/edit")

    assert response.status_code == 200
    assert b'value="Demo Child"' in response.data


def test_deactivate_and_reactivate(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")
    client.post("/beneficiaries/new/child", data=child_form())
    beneficiary = Beneficiary.query.filter_by(full_name="Demo Child").one()

    response = client.post(f"/beneficiaries/{beneficiary.id}/deactivate")
    assert response.status_code == 302
    db.session.refresh(beneficiary)
    assert beneficiary.status == RecordStatus.INACTIVE

    response = client.post(f"/beneficiaries/{beneficiary.id}/activate")
    assert response.status_code == 302
    db.session.refresh(beneficiary)
    assert beneficiary.status == RecordStatus.ACTIVE


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "override, expected",
    [
        ({"full_name": ""}, b"Full name is required"),
        ({"gender": ""}, b"Gender is required"),
        ({"date_of_birth": (date.today() + timedelta(days=5)).isoformat()}, b"cannot be in the future"),
        ({"date_of_birth": (date.today() - timedelta(days=8 * 365)).isoformat()}, b"under 6 years"),
        ({"contact": "12345"}, b"10-digit mobile"),
        ({"birth_weight_kg": "99"}, b"at most"),
    ],
)
def test_child_validation_errors(client, db, centre, make_user, override, expected):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")

    response = client.post("/beneficiaries/new/child", data=child_form(**override))

    assert response.status_code == 400
    assert expected in response.data
    assert Beneficiary.query.count() == 0


def test_duplicate_beneficiary_rejected(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")
    client.post("/beneficiaries/new/child", data=child_form())

    response = client.post("/beneficiaries/new/child", data=child_form())

    assert response.status_code == 400
    assert b"already registered" in response.data
    assert Beneficiary.query.count() == 1


def test_mother_validation_rejects_bad_age(client, db, centre, make_user):
    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")

    response = client.post(
        "/beneficiaries/new/mother/pregnant",
        data=mother_form("pregnant", age="5"),
    )

    assert response.status_code == 400
    assert b"at least 12" in response.data


# ---------------------------------------------------------------------------
# Role permissions
# ---------------------------------------------------------------------------
def test_beneficiaries_require_login(client):
    response = client.get("/beneficiaries/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize("role", [UserRole.SUPERVISOR, UserRole.OFFICER])
def test_read_only_roles_cannot_open_create_form(client, make_user, role):
    make_user("reader", role=role)
    login(client, "reader")

    response = client.get("/beneficiaries/new")

    assert response.status_code == 403


@pytest.mark.parametrize("role", [UserRole.SUPERVISOR, UserRole.OFFICER])
def test_read_only_roles_cannot_create(client, centre, make_user, role):
    make_user("reader", role=role)
    login(client, "reader")

    response = client.post(
        "/beneficiaries/new/child",
        data=child_form(centre_id=str(centre.id)),
    )

    assert response.status_code == 403


def test_supervisor_can_view_beneficiaries(client, db, centre, make_user):
    make_user("supervisor", role=UserRole.SUPERVISOR)
    login(client, "supervisor")
    assert client.get("/beneficiaries/").status_code == 200


def test_aww_cannot_access_another_centres_beneficiary(
    client, db, centre, other_centre, make_user
):
    make_user("admin", role=UserRole.ADMIN)
    login(client, "admin")
    client.post(
        "/beneficiaries/new/child",
        data=child_form(full_name="Beta Child", centre_id=str(other_centre.id)),
    )
    beneficiary = Beneficiary.query.filter_by(full_name="Beta Child").one()
    client.post("/logout")

    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")

    response = client.get(f"/beneficiaries/{beneficiary.id}")

    assert response.status_code == 403


def test_aww_list_is_scoped_to_own_centre(client, db, centre, other_centre, make_user):
    make_user("admin", role=UserRole.ADMIN)
    login(client, "admin")
    client.post(
        "/beneficiaries/new/child",
        data=child_form(full_name="Alpha Child", centre_id=str(centre.id)),
    )
    client.post(
        "/beneficiaries/new/child",
        data=child_form(
            full_name="Beta Child",
            date_of_birth=(date.today() - timedelta(days=800)).isoformat(),
            centre_id=str(other_centre.id),
        ),
    )
    client.post("/logout")

    make_user("aww_alpha", role=UserRole.AWW, centre=centre)
    login(client, "aww_alpha")

    response = client.get("/beneficiaries/")

    assert response.status_code == 200
    assert b"Alpha Child" in response.data
    assert b"Beta Child" not in response.data
