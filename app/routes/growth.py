"""Child growth tracking routes (Phase 4).

Scoped to a child so the history, entry form and chart always belong to one
beneficiary:

* view growth history + chart
* record a new measurement
* edit an existing measurement

Write access is limited to ADMIN and AWW; every authenticated role may read,
but an AWW only reaches children of their own centre.
"""

from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Child
from app.services import growth_service
from app.utils.constants import UserRole
from app.utils.decorators import login_required, role_required
from app.utils.helpers import current_user, ensure_beneficiary_access
from app.utils.validators import ValidationError

bp = Blueprint("growth", __name__, url_prefix="/children")

READ_ROLES = (
    UserRole.ADMIN,
    UserRole.AWW,
    UserRole.SUPERVISOR,
    UserRole.OFFICER,
)
WRITE_ROLES = (UserRole.ADMIN, UserRole.AWW)


def _get_child(child_id: int) -> Child:
    """Load a child and enforce centre access for the current user."""
    child = db.get_or_404(Child, child_id)
    ensure_beneficiary_access(current_user(), child.beneficiary)
    return child


def _date_str(value) -> str:
    return value.isoformat() if value else ""


# ---------------------------------------------------------------------------
# History / growth view
# ---------------------------------------------------------------------------
@bp.get("/<int:child_id>/growth")
@login_required
@role_required(*READ_ROLES)
def history(child_id):
    """Show the growth history, current status and trend chart."""
    child = _get_child(child_id)
    history_items = growth_service.build_history(child)
    latest = history_items[0] if history_items else None
    return render_template(
        "growth/history.html",
        child=child,
        beneficiary=child.beneficiary,
        history=history_items,
        latest=latest,
        chart=growth_service.chart_data(child),
        current_rules=growth_service.current_rules(),
        rule_id=growth_service.DEMO_RULE_ID,
        can_write=current_user().role in WRITE_ROLES,
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
@bp.route("/<int:child_id>/growth/new", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def create(child_id):
    child = _get_child(child_id)
    errors: dict[str, str] = {}

    if request.method == "POST":
        try:
            record = growth_service.record_growth(
                child, request.form, recorded_by=current_user()
            )
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash("Growth measurement recorded.", "success")
            return redirect(url_for("growth.history", child_id=child.id))
        form = request.form
    else:
        form = {"measurement_date": date.today().isoformat()}

    return (
        render_template(
            "growth/form.html",
            mode="create",
            child=child,
            beneficiary=child.beneficiary,
            record=None,
            form=form,
            errors=errors,
        ),
        400 if errors else 200,
    )


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------
@bp.route("/<int:child_id>/growth/<int:record_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def edit(child_id, record_id):
    child = _get_child(child_id)
    record = growth_service.get_record(child, record_id)
    errors: dict[str, str] = {}

    if request.method == "POST":
        try:
            growth_service.update_growth(
                child, record, request.form, recorded_by=current_user()
            )
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash("Growth measurement updated.", "success")
            return redirect(url_for("growth.history", child_id=child.id))
        form = request.form
    else:
        form = {
            "measurement_date": _date_str(record.measurement_date),
            "weight_kg": "" if record.weight_kg is None else str(record.weight_kg),
            "height_cm": "" if record.height_cm is None else str(record.height_cm),
            "muac_cm": "" if record.muac_cm is None else str(record.muac_cm),
            "notes": record.notes or "",
        }

    return (
        render_template(
            "growth/form.html",
            mode="edit",
            child=child,
            beneficiary=child.beneficiary,
            record=record,
            form=form,
            errors=errors,
        ),
        400 if errors else 200,
    )


__all__ = ["bp"]
