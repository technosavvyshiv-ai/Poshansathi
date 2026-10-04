"""Authentication routes: login and logout.

Uses Flask's signed client-side session with Werkzeug password hashing (the
``User.set_password`` / ``User.check_password`` helpers defined in Phase 1).
No password is ever stored or compared in plain text.
"""

from __future__ import annotations

from datetime import datetime

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.extensions import db
from app.models import User
from app.utils.decorators import login_required
from app.utils.helpers import current_user

bp = Blueprint("auth", __name__)


def _safe_redirect_target(target: str | None) -> str | None:
    """Only allow same-site, absolute *path* redirects (no open redirects)."""
    if not target:
        return None
    if not target.startswith("/") or target.startswith("//"):
        return None
    if "\\" in target:
        return None
    return target


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Show the login form and authenticate submitted credentials."""
    # Already signed in: skip the form.
    if current_user() is not None:
        return redirect(url_for("dashboard.index"))

    username = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        user = User.query.filter_by(username=username).first()

        # Same generic message for unknown user and wrong password.
        if user is None or not user.check_password(password):
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html", username=username), 401

        if not user.is_active:
            flash(
                "This account is inactive. Please contact an administrator.",
                "warning",
            )
            return render_template("auth/login.html", username=username), 403

        # Start a clean session to avoid fixation, then record the user.
        session.clear()
        session["user_id"] = user.id
        session.permanent = request.form.get("remember") == "on"

        user.last_login_at = datetime.utcnow()
        db.session.commit()

        flash(f"Welcome back, {user.full_name}.", "success")
        destination = (
            _safe_redirect_target(request.form.get("next"))
            or url_for("dashboard.index")
        )
        return redirect(destination)

    return render_template("auth/login.html", username=username)


@bp.post("/logout")
@login_required
def logout():
    """Clear the session and return to the login page."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
