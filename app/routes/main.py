"""Foundation routes: landing page and health check.

The landing page is public.  Authenticated users are sent to their dashboard;
anonymous visitors see the project introduction with a login link.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, redirect, url_for



bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    """Redirect visitors directly to the login page."""
    return redirect(url_for("auth.login"))


@bp.get("/healthz")
def healthz():
    """Lightweight health check used by sanity tests and deployments."""
    return jsonify(status="ok", app="PoshanSathi", phase="11")
