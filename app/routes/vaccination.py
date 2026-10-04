"""Child vaccination tracking routes (Phase 5).

Scoped to a child so the history and forms always belong to one beneficiary:

* view vaccination history
* record a vaccination
* edit an existing vaccination

Write access is limited to ADMIN and AWW; every authenticated role may read,
but an AWW only reaches children of their own centre.
"""

from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Child
from app.services import vaccination_service
from app.utils.constants import UserRole
from app.utils.decorators import login_required, role_required
from app.utils.helpers import current_user, ensure_beneficiary_access
from app.utils.validators import ValidationError
from app.utils.vaccination_rules import (
    DEMO_RULE_ID,
    KNOWN_VACCINE_NAMES,
)

bp = Blueprint("vaccination", __name__, url_prefix="/children")

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
# History / vaccination view
# ---------------------------------------------------------------------------
@bp.get("/<int:child_id>/vaccinations")
@login_required
@role_required(*READ_ROLES)
def history(child_id):
    """Show the vaccination history and a deterministic status summary."""
    child = _get_child(child_id)
    return render_template(
        "vaccination/history.html",
        child=child,
        beneficiary=child.beneficiary,
        history=vaccination_service.build_history(child),
        summary=vaccination_service.summary(child),
        rule_id=DEMO_RULE_ID,
        can_write=current_user().role in WRITE_ROLES,
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
@bp.route("/<int:child_id>/vaccinations/new", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def create(child_id):
    child = _get_child(child_id)
    errors: dict[str, str] = {}

    if request.method == "POST":
        try:
            vaccination_service.create_vaccination(
                child, request.form, recorded_by=current_user()
            )
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash("Vaccination record saved.", "success")
            return redirect(url_for("vaccination.history", child_id=child.id))
        form = request.form
    else:
        form = {"status": "UPCOMING", "dose_number": "1"}

    return (
        render_template(
            "vaccination/form.html",
            mode="create",
            child=child,
            beneficiary=child.beneficiary,
            record=None,
            form=form,
            errors=errors,
            vaccine_names=KNOWN_VACCINE_NAMES,
        ),
        400 if errors else 200,
    )


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------
@bp.route(
    "/<int:child_id>/vaccinations/<int:record_id>/edit",
    methods=["GET", "POST"],
)
@login_required
@role_required(*WRITE_ROLES)
def edit(child_id, record_id):
    child = _get_child(child_id)
    record = vaccination_service.get_record(child, record_id)
    errors: dict[str, str] = {}

    if request.method == "POST":
        try:
            vaccination_service.update_vaccination(
                child, record, request.form, recorded_by=current_user()
            )
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash("Vaccination record updated.", "success")
            return redirect(url_for("vaccination.history", child_id=child.id))
        form = request.form
    else:
        form = {
            "vaccine_name": record.vaccine_name or "",
            "dose_number": "" if record.dose_number is None else str(record.dose_number),
            "scheduled_date": _date_str(record.scheduled_date),
            "administered_date": _date_str(record.administered_date),
            "status": record.status.value if record.status else "UPCOMING",
            "notes": record.notes or "",
        }

    return (
        render_template(
            "vaccination/form.html",
            mode="edit",
            child=child,
            beneficiary=child.beneficiary,
            record=record,
            form=form,
            errors=errors,
            vaccine_names=KNOWN_VACCINE_NAMES,
        ),
        400 if errors else 200,
    )


__all__ = ["bp"]
