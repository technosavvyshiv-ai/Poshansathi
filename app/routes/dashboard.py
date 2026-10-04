"""Authenticated landing page.

Phase 2 only proves the authenticated layout and role-aware navigation.  The
real role dashboards (metrics, charts) are built in Phase 11.
"""

from __future__ import annotations

from flask import Blueprint, render_template

from app.utils.decorators import login_required

bp = Blueprint("dashboard", __name__)


@bp.get("/dashboard")
@login_required
def index():
    """Render the authenticated home page for the current user."""
    return render_template("dashboard/index.html")
