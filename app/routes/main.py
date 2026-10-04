"""Foundation routes: landing page and health check.

The landing page is public.  Authenticated users are sent to their dashboard;
anonymous visitors see the project introduction with a login link.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, url_for

from app.utils.helpers import current_user

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    """Public landing page, or redirect to the dashboard when signed in."""
    if current_user() is not None:
        return redirect(url_for("dashboard.index"))
    return render_template("index.html")


@bp.get("/healthz")
def healthz():
    """Lightweight health check used by sanity tests and deployments."""
    return jsonify(status="ok", app="PoshanSathi", phase="3")
