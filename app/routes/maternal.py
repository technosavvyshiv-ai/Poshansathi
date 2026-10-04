"""Maternal health (ANC) routes (Phase 6).

Scoped to a mother so the history and forms always belong to one beneficiary:

* view maternal health history
* record an ANC visit
* edit an existing ANC record

Write access is limited to ADMIN and AWW; every authenticated role may read,
but an AWW only reaches mothers of their own centre.
"""

from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Mother
from app.services import maternal_service
from app.utils.constants import UserRole
from app.utils.decorators import login_required, role_required
from app.utils.helpers import current_user, ensure_beneficiary_access
from app.utils.maternal_rules import DEMO_RULE_ID
from app.utils.validators import ValidationError

bp = Blueprint("maternal", __name__, url_prefix="/mothers")

READ_ROLES = (
    UserRole.ADMIN,
    UserRole.AWW,
    UserRole.SUPERVISOR,
    UserRole.OFFICER,
)
WRITE_ROLES = (UserRole.ADMIN, UserRole.AWW)


def _get_mother(mother_id: int) -> Mother:
    """Load a mother and enforce centre access for the current user."""
    mother = db.get_or_404(Mother, mother_id)
    ensure_beneficiary_access(current_user(), mother.beneficiary)
    return mother


def _date_str(value) -> str:
    return value.isoformat() if value else ""


def _num_str(value) -> str:
    return "" if value is None else str(value)


# ---------------------------------------------------------------------------
# History / maternal health view
# ---------------------------------------------------------------------------
@bp.get("/<int:mother_id>/health")
@login_required
@role_required(*READ_ROLES)
def history(mother_id):
    """Show the ANC history, latest status and configured follow-up."""
    mother = _get_mother(mother_id)
    return render_template(
        "maternal/history.html",
        mother=mother,
        beneficiary=mother.beneficiary,
        history=maternal_service.build_history(mother),
        summary=maternal_service.summary(mother),
        rule_id=DEMO_RULE_ID,
        can_write=current_user().role in WRITE_ROLES,
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
@bp.route("/<int:mother_id>/health/new", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def create(mother_id):
    mother = _get_mother(mother_id)
    errors: dict[str, str] = {}

    if request.method == "POST":
        try:
            maternal_service.create_maternal_health(
                mother, request.form, recorded_by=current_user()
            )
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash("ANC record saved.", "success")
            return redirect(url_for("maternal.history", mother_id=mother.id))
        form = request.form
    else:
        form = {"visit_date": date.today().isoformat(), "risk_category": "LOW"}

    return (
        render_template(
            "maternal/form.html",
            mode="create",
            mother=mother,
            beneficiary=mother.beneficiary,
            record=None,
            form=form,
            errors=errors,
        ),
        400 if errors else 200,
    )


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------
@bp.route(
    "/<int:mother_id>/health/<int:record_id>/edit",
    methods=["GET", "POST"],
)
@login_required
@role_required(*WRITE_ROLES)
def edit(mother_id, record_id):
    mother = _get_mother(mother_id)
    record = maternal_service.get_record(mother, record_id)
    errors: dict[str, str] = {}

    if request.method == "POST":
        try:
            maternal_service.update_maternal_health(
                mother, record, request.form, recorded_by=current_user()
            )
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash("ANC record updated.", "success")
            return redirect(url_for("maternal.history", mother_id=mother.id))
        form = request.form
    else:
        form = {
            "visit_date": _date_str(record.visit_date),
            "pregnancy_month": (
                "" if record.pregnancy_month is None else str(record.pregnancy_month)
            ),
            "weight_kg": _num_str(record.weight_kg),
            "haemoglobin": _num_str(record.haemoglobin),
            "systolic_bp": "" if record.systolic_bp is None else str(record.systolic_bp),
            "diastolic_bp": (
                "" if record.diastolic_bp is None else str(record.diastolic_bp)
            ),
            "risk_category": (
                record.risk_category.value if record.risk_category else "LOW"
            ),
            "next_follow_up_date": _date_str(record.next_follow_up_date),
            "notes": record.notes or "",
        }

    return (
        render_template(
            "maternal/form.html",
            mode="edit",
            mother=mother,
            beneficiary=mother.beneficiary,
            record=record,
            form=form,
            errors=errors,
        ),
        400 if errors else 200,
    )


__all__ = ["bp"]
