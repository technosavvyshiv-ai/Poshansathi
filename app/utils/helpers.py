"""Authentication helpers.

Small functions shared by the auth routes, decorators, templates and tests.
The logged-in user is resolved once per request by :func:`load_logged_in_user`
and cached on Flask's ``g`` object.
"""

from __future__ import annotations

from datetime import date

from flask import g, session

from app.extensions import db
from app.models import User


def load_logged_in_user() -> None:
    """Populate ``g.user`` from the session for the current request.

    Registered as an application ``before_request`` hook.  If the session
    references a missing or deactivated user the session is cleared, which
    invalidates the login safely.
    """
    g.user = None
    user_id = session.get("user_id")
    if user_id is None:
        return

    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        session.clear()
        return

    g.user = user


def current_user() -> User | None:
    """Return the currently authenticated user, or ``None``."""
    return g.get("user")


def user_has_role(*roles) -> bool:
    """Return True when the current user's role is one of ``roles``."""
    user = current_user()
    return user is not None and user.role in roles


def age_years(date_of_birth) -> int | None:
    """Return completed years for a date of birth, or ``None``.

    Registered as a Jinja filter (``|age_years``) so templates can display a
    beneficiary's age without embedding arithmetic in the markup.
    """
    if not date_of_birth:
        return None
    today = date.today()
    return (
        today.year
        - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )
