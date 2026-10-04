"""Anganwadi centre management routes (Phase 3).

Centre administration (create/update/deactivate) is restricted to ADMIN.
Every authenticated role may browse centre details because beneficiaries are
organised by centre.
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.services import centre_service
from app.utils.constants import UserRole
from app.utils.decorators import login_required, role_required
from app.utils.helpers import current_user
from app.utils.validators import ValidationError

bp = Blueprint("centres", __name__, url_prefix="/centres")

READ_ROLES = (
    UserRole.ADMIN,
    UserRole.AWW,
    UserRole.SUPERVISOR,
    UserRole.OFFICER,
)
MANAGE_ROLES = (UserRole.ADMIN,)


# ---------------------------------------------------------------------------
# List / search
# ---------------------------------------------------------------------------
@bp.get("/")
@login_required
@role_required(*READ_ROLES)
def index():
    q = (request.args.get("q") or "").strip()
    active_only = request.args.get("active") == "1"
    page = request.args.get("page", 1, type=int) or 1

    pagination = centre_service.search_centres(
        q=q, active_only=active_only, page=page, per_page=10
    )
    return render_template(
        "centres/index.html",
        pagination=pagination,
        q=q,
        active_only=active_only,
        can_manage=current_user().role == UserRole.ADMIN,
    )


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------
@bp.get("/<int:centre_id>")
@login_required
@role_required(*READ_ROLES)
def detail(centre_id):
    centre = centre_service.get_centre(centre_id)
    stats = centre_service.centre_statistics(centre)
    return render_template(
        "centres/detail.html",
        centre=centre,
        stats=stats,
        can_manage=current_user().role == UserRole.ADMIN,
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
@bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required(*MANAGE_ROLES)
def create():
    errors: dict[str, str] = {}
    form = request.form if request.method == "POST" else {"is_active": "on"}

    if request.method == "POST":
        try:
            centre = centre_service.create_centre(form)
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash(f"Created {centre.name}.", "success")
            return redirect(url_for("centres.detail", centre_id=centre.id))

    return (
        render_template(
            "centres/form.html",
            mode="create",
            centre=None,
            form=form,
            errors=errors,
        ),
        400 if errors else 200,
    )


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------
@bp.route("/<int:centre_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*MANAGE_ROLES)
def edit(centre_id):
    centre = centre_service.get_centre(centre_id)
    errors: dict[str, str] = {}

    if request.method == "POST":
        form = request.form
        try:
            centre_service.update_centre(centre, form)
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash(f"Updated {centre.name}.", "success")
            return redirect(url_for("centres.detail", centre_id=centre.id))
    else:
        form = {
            "name": centre.name or "",
            "code": centre.code or "",
            "address": centre.address or "",
            "village": centre.village or "",
            "district": centre.district or "",
            "state": centre.state or "",
            "pincode": centre.pincode or "",
            "phone": centre.phone or "",
            "is_active": "on" if centre.is_active else "",
        }

    return (
        render_template(
            "centres/form.html",
            mode="edit",
            centre=centre,
            form=form,
            errors=errors,
        ),
        400 if errors else 200,
    )


# ---------------------------------------------------------------------------
# Deactivate / reactivate
# ---------------------------------------------------------------------------
@bp.post("/<int:centre_id>/deactivate")
@login_required
@role_required(*MANAGE_ROLES)
def deactivate(centre_id):
    centre = centre_service.get_centre(centre_id)
    centre_service.set_active(centre, False)
    flash(f"Deactivated {centre.name}.", "info")
    return redirect(url_for("centres.detail", centre_id=centre.id))


@bp.post("/<int:centre_id>/activate")
@login_required
@role_required(*MANAGE_ROLES)
def activate(centre_id):
    centre = centre_service.get_centre(centre_id)
    centre_service.set_active(centre, True)
    flash(f"Reactivated {centre.name}.", "success")
    return redirect(url_for("centres.detail", centre_id=centre.id))


__all__ = ["bp"]
