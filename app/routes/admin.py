"""Administrator-only placeholder area.

This exists in Phase 2 to demonstrate role-based access control end to end
(``role_required``) and role-aware navigation.  Actual user/centre/scheme
management is implemented in later phases.
"""

from __future__ import annotations

from flask import Blueprint, render_template

from app.utils.constants import UserRole
from app.utils.decorators import login_required, role_required

bp = Blueprint("admin", __name__)


@bp.get("/admin")
@login_required
@role_required(UserRole.ADMIN)
def index():
    """Render the protected administrator area."""
    return render_template("admin/index.html")
