"""Role dashboards (Phase 11).

``/dashboard`` renders a role-appropriate view whose metrics, charts and
summaries are all calculated from the database by
:mod:`app.services.dashboard_service`:

* **AWW**        — own-centre operational view (beneficiaries, alerts, visits,
  upcoming vaccinations, recent registrations, attendance, nutrition stock);
* **SUPERVISOR** — multi-centre monitoring with vaccination coverage, nutrition
  distribution, alert resolution and a centre comparison;
* **OFFICER**    — aggregated multi-centre overview (read-only, comparison);
* **ADMIN**      — whole-system overview incl. users, centres and schemes.

An optional ``?centre=<id>`` filter narrows the supervisor/officer views; an
AWW is always pinned to their own centre.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request

from app.services import dashboard_service
from app.utils.constants import UserRole
from app.utils.decorators import login_required
from app.utils.helpers import current_user, scope_centre_id

bp = Blueprint("dashboard", __name__)


@bp.get("/dashboard")
@login_required
def index():
    """Render the authenticated home page for the current user's role."""
    user = current_user()
    scope = scope_centre_id(user)

    centre_id = scope
    if scope is None:
        raw = (request.args.get("centre") or "").strip()
        centre_id = int(raw) if raw.isdigit() else None
    selected_centre = dashboard_service.get_centre(centre_id)

    if user.role == UserRole.ADMIN:
        context = dashboard_service.admin_dashboard()
        template = "dashboard/admin.html"
    elif user.role == UserRole.AWW:
        context = dashboard_service.aww_dashboard(scope)
        template = "dashboard/aww.html"
    elif user.role == UserRole.SUPERVISOR:
        context = dashboard_service.supervisor_dashboard(centre_id)
        template = "dashboard/supervisor.html"
    else:
        context = dashboard_service.supervisor_dashboard(centre_id)
        template = "dashboard/officer.html"

    return render_template(
        template,
        selected_centre=selected_centre,
        selected_centre_id=centre_id,
        scope_centre_id=scope,
        **context,
    )


__all__ = ["bp"]
