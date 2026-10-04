"""Phase 3 Anganwadi centre management tests: CRUD, validation and roles."""

from __future__ import annotations

import pytest

from app.models import AnganwadiCentre, User
from app.utils.constants import UserRole

PASSWORD = "password123"


@pytest.fixture()
def make_user(db):
    def make(username, role=UserRole.ADMIN):
        user = User(
            full_name=f"Test {username}",
            username=username,
            role=role,
            is_active=True,
        )
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        return user

    return make


def login(client, username, password=PASSWORD):
    return client.post(
        "/login", data={"username": username, "password": password}
    )


def centre_form(**overrides):
    data = {
        "name": "New Centre",
        "code": "NC-001",
        "address": "Main Road",
        "village": "New Village",
        "district": "Testdistrict",
        "state": "Teststate",
        "pincode": "462011",
        "phone": "9876509999",
        "is_active": "on",
    }
    data.update(overrides)
    return data


def test_centres_require_login(client):
    response = client.get("/centres/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_admin_can_create_centre(client, db, make_user):
    make_user("admin")
    login(client, "admin")

    response = client.post("/centres/new", data=centre_form())

    assert response.status_code == 302
    centre = AnganwadiCentre.query.filter_by(code="NC-001").one()
    assert centre.name == "New Centre"
    assert centre.is_active is True
    assert response.headers["Location"].endswith(f"/centres/{centre.id}")


def test_admin_can_update_centre(client, db, make_user):
    make_user("admin")
    login(client, "admin")
    client.post("/centres/new", data=centre_form())
    centre = AnganwadiCentre.query.filter_by(code="NC-001").one()

    response = client.post(
        f"/centres/{centre.id}/edit", data=centre_form(name="Renamed Centre")
    )

    assert response.status_code == 302
    db.session.refresh(centre)
    assert centre.name == "Renamed Centre"


def test_admin_can_deactivate_centre(client, db, make_user):
    make_user("admin")
    login(client, "admin")
    client.post("/centres/new", data=centre_form())
    centre = AnganwadiCentre.query.filter_by(code="NC-001").one()

    response = client.post(f"/centres/{centre.id}/deactivate")

    assert response.status_code == 302
    db.session.refresh(centre)
    assert centre.is_active is False


def test_non_admin_cannot_create_centre(client, db, make_user):
    make_user("aww", role=UserRole.AWW)
    login(client, "aww")

    response = client.post("/centres/new", data=centre_form())

    assert response.status_code == 403
    assert AnganwadiCentre.query.count() == 0


def test_supervisor_can_view_centres(client, db, make_user):
    make_user("supervisor", role=UserRole.SUPERVISOR)
    login(client, "supervisor")

    response = client.get("/centres/")

    assert response.status_code == 200


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"name": ""}, b"Centre name is required"),
        ({"code": ""}, b"Centre code is required"),
        ({"pincode": "12"}, b"6-digit PIN"),
        ({"phone": "abc"}, b"10-digit mobile"),
    ],
)
def test_centre_validation(client, db, make_user, override, expected):
    make_user("admin")
    login(client, "admin")

    response = client.post("/centres/new", data=centre_form(**override))

    assert response.status_code == 400
    assert expected in response.data
    assert AnganwadiCentre.query.count() == 0


def test_centre_code_must_be_unique(client, db, make_user):
    make_user("admin")
    login(client, "admin")
    client.post("/centres/new", data=centre_form())

    response = client.post(
        "/centres/new", data=centre_form(name="Another Centre")
    )

    assert response.status_code == 400
    assert b"already exists" in response.data
    assert AnganwadiCentre.query.count() == 1
