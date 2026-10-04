"""Route protection decorators.

``login_required`` blocks anonymous access and remembers where the user was
heading.  ``role_required`` additionally enforces role-based access control and
returns HTTP 403 for authenticated users with the wrong role.
"""

from __future__ import annotations

from functools import wraps

from flask import abort, flash, redirect, request, url_for

from app.utils.helpers import current_user


def _login_redirect():
    """Redirect to the login page, preserving the requested path."""
    target = request.full_path if request.query_string else request.path
    flash("Please log in to continue.", "warning")
    return redirect(url_for("auth.login", next=target))


def login_required(view):
    """Require an authenticated user."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return _login_redirect()
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    """Require an authenticated user whose role is one of ``roles``."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                return _login_redirect()
            if user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
