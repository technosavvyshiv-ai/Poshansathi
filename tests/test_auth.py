"""Phase 2 authentication tests: login, logout, sessions and role checks."""

from __future__ import annotations

import pytest

from app.models import User
from app.utils.constants import UserRole

PASSWORD = "password123"


@pytest.fixture()
def user_factory(db):
    """Create and persist a user with a hashed password."""

    def make(
        username: str,
        role: UserRole = UserRole.AWW,
        password: str = PASSWORD,
        active: bool = True,
    ) -> User:
        user = User(
            full_name=f"Test {username}",
            username=username,
            role=role,
            is_active=active,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    return make


def _login(client, username="aww1", password=PASSWORD, follow_redirects=False,
           **form_extra):
    data = {"username": username, "password": password, **form_extra}
    return client.post("/login", data=data, follow_redirects=follow_redirects)


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------
def test_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Sign in to PoshanSathi" in response.data


def test_login_page_redirects_when_authenticated(client, user_factory):
    user_factory("aww1")
    _login(client)
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def test_login_with_valid_credentials(client, user_factory):
    user = user_factory("aww1")
    response = _login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    with client.session_transaction() as sess:
        assert sess["user_id"] == user.id

    # last_login_at is stamped.
    assert user.last_login_at is not None


def test_login_success_message_after_redirect(client, user_factory):
    user_factory("aww1")
    response = _login(client, follow_redirects=True)
    assert response.status_code == 200
    assert b"Welcome back" in response.data


def test_login_with_invalid_password(client, user_factory):
    user_factory("aww1")
    response = _login(client, password="wrong-password")
    assert response.status_code == 401
    assert b"Invalid username or password" in response.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_with_unknown_user(client):
    response = _login(client, username="ghost")
    assert response.status_code == 401
    assert b"Invalid username or password" in response.data


def test_login_with_inactive_user(client, user_factory):
    user_factory("aww1", active=False)
    response = _login(client)
    assert response.status_code == 403
    assert b"inactive" in response.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
def test_logout_clears_session(client, user_factory):
    user_factory("aww1")
    _login(client)
    response = client.post("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_protected_route_unreachable_after_logout(client, user_factory):
    user_factory("aww1")
    _login(client)
    client.post("/logout")
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Protected routes / unauthorized access
# ---------------------------------------------------------------------------
def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert "next=/dashboard" in response.headers["Location"]


def test_dashboard_accessible_after_login(client, user_factory):
    user_factory("aww1")
    _login(client)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"Test aww1" in response.data


def test_index_redirects_authenticated_user(client, user_factory):
    user_factory("aww1")
    _login(client)
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_index_public_when_anonymous(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"PoshanSathi" in response.data


def test_login_preserves_next_after_redirect(client, user_factory):
    user_factory("aww1")
    # Hit a protected page first to get the ?next= parameter.
    redirect_response = client.get("/admin")
    location = redirect_response.headers["Location"]

    response = client.post(
        "/login",
        data={"username": "aww1", "password": PASSWORD, "next": "/admin"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin")
    assert "next" in location


def test_open_redirect_is_rejected(client, user_factory):
    user_factory("aww1")
    response = client.post(
        "/login",
        data={
            "username": "aww1",
            "password": PASSWORD,
            "next": "https://evil.example/phish",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    assert "evil.example" not in response.headers["Location"]


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------
def test_admin_route_requires_login(client):
    response = client.get("/admin")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_admin_route_forbidden_for_aww(client, user_factory):
    user_factory("aww1", role=UserRole.AWW)
    _login(client, "aww1")
    response = client.get("/admin")
    assert response.status_code == 403
    assert b"Access denied" in response.data


@pytest.mark.parametrize(
    "role", [UserRole.SUPERVISOR, UserRole.OFFICER]
)
def test_admin_route_forbidden_for_non_admin_roles(client, user_factory, role):
    user_factory("someone", role=role)
    _login(client, "someone")
    response = client.get("/admin")
    assert response.status_code == 403


def test_admin_route_allowed_for_admin(client, user_factory):
    user_factory("admin", role=UserRole.ADMIN)
    _login(client, "admin")
    response = client.get("/admin")
    assert response.status_code == 200
    assert b"Administration" in response.data


@pytest.mark.parametrize(
    "role",
    [UserRole.ADMIN, UserRole.AWW, UserRole.SUPERVISOR, UserRole.OFFICER],
)
def test_every_role_can_access_dashboard(client, user_factory, role):
    user_factory(f"user_{role.value.lower()}", role=role)
    _login(client, f"user_{role.value.lower()}")
    response = client.get("/dashboard")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Role-aware navigation
# ---------------------------------------------------------------------------
def test_admin_navigation_shows_administration_link(client, user_factory):
    user_factory("admin", role=UserRole.ADMIN)
    response = _login(client, "admin", follow_redirects=True)
    assert b"Administration" in response.data
    assert b"/admin" in response.data


def test_aww_navigation_hides_administration_link(client, user_factory):
    user_factory("aww1", role=UserRole.AWW)
    response = _login(client, "aww1", follow_redirects=True)
    assert b"Administration" not in response.data


def test_login_link_visible_to_anonymous(client):
    response = client.get("/")
    assert b"Sign in" in response.data


def test_logout_button_visible_when_authenticated(client, user_factory):
    user_factory("aww1")
    response = _login(client, follow_redirects=True)
    assert b"Logout" in response.data


def test_logout_rejects_get(client, user_factory):
    user_factory("aww1")
    _login(client)
    response = client.get("/logout")
    assert response.status_code == 405
