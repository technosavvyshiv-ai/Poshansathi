"""Beneficiary management routes (Phase 3).

Handles child, pregnant-woman and lactating-mother registration and profiles:

* list / search / filter
* create (type selection + type-specific forms)
* detail
* edit
* soft deactivate / reactivate

Write access is limited to ADMIN and AWW.  Every authenticated role may read,
but an AWW only sees beneficiaries of their own centre.
"""

from __future__ import annotations

from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import AnganwadiCentre, Beneficiary, Mother
from app.services import beneficiary_service
from app.utils.constants import BeneficiaryType, RecordStatus, UserRole
from app.utils.decorators import login_required, role_required
from app.utils.helpers import (
    current_user,
    ensure_beneficiary_access,
    scope_centre_id,
)
from app.utils.validators import ValidationError

bp = Blueprint("beneficiaries", __name__, url_prefix="/beneficiaries")

READ_ROLES = (
    UserRole.ADMIN,
    UserRole.AWW,
    UserRole.SUPERVISOR,
    UserRole.OFFICER,
)
WRITE_ROLES = (UserRole.ADMIN, UserRole.AWW)

#: URL segment -> beneficiary type for mother registration.
MOTHER_KINDS = {
    "pregnant": BeneficiaryType.PREGNANT_WOMAN,
    "lactating": BeneficiaryType.LACTATING_MOTHER,
}

MOTHER_KIND_LABELS = {
    BeneficiaryType.PREGNANT_WOMAN: "pregnant woman",
    BeneficiaryType.LACTATING_MOTHER: "lactating mother",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _scope_centre_id(user) -> int | None:
    """Restrict an AWW to their own centre; other roles are unscoped."""
    return scope_centre_id(user)


def _ensure_access(user, beneficiary) -> None:
    """Abort with 403 when an AWW requests another centre's beneficiary."""
    ensure_beneficiary_access(user, beneficiary)


def _resolve_centre(user, form):
    """Return ``(centre, error)`` for the submitted/derived centre."""
    if user.role == UserRole.AWW and user.centre_id:
        return user.centre, None

    raw = (form.get("centre_id") or "").strip() if form else ""
    if not raw:
        return None, "Please select an Anganwadi centre."
    if not raw.isdigit():
        return None, "Selected centre is not valid."
    centre = db.session.get(AnganwadiCentre, int(raw))
    if centre is None:
        return None, "Selected centre was not found."
    if not centre.is_active:
        return None, "Selected centre is inactive."
    return centre, None


def _safe_enum(enum_cls, value):
    if not value:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        return None


def _date_str(value) -> str:
    return value.isoformat() if value else ""


def _num_str(value) -> str:
    return "" if value is None else str(value)


def _form_from_beneficiary(beneficiary) -> dict[str, str]:
    """Build a form-shaped mapping so create/edit share one template."""
    data = {
        "full_name": beneficiary.full_name or "",
        "date_of_birth": _date_str(beneficiary.date_of_birth),
        "gender": beneficiary.gender.value if beneficiary.gender else "",
        "guardian_name": beneficiary.guardian_name or "",
        "contact": beneficiary.contact or "",
        "address": beneficiary.address or "",
        "registration_date": _date_str(beneficiary.registration_date),
        "centre_id": str(beneficiary.centre_id or ""),
    }

    if beneficiary.beneficiary_type == BeneficiaryType.CHILD and beneficiary.child:
        child = beneficiary.child
        data.update(
            {
                "birth_weight_kg": _num_str(child.birth_weight_kg),
                "birth_height_cm": _num_str(child.birth_height_cm),
                "blood_group": child.blood_group or "",
                "mother_id": str(child.mother_id) if child.mother_id else "",
            }
        )
    elif beneficiary.mother:
        mother = beneficiary.mother
        data.update(
            {
                "age": "" if mother.age is None else str(mother.age),
                "husband_name": mother.husband_name or "",
                "pregnancy_number": (
                    "" if mother.pregnancy_number is None
                    else str(mother.pregnancy_number)
                ),
                "last_menstrual_period": _date_str(mother.last_menstrual_period),
                "expected_delivery_date": _date_str(mother.expected_delivery_date),
                "delivery_date": _date_str(mother.delivery_date),
                "blood_group": mother.blood_group or "",
                "height_cm": _num_str(mother.height_cm),
                "current_risk_level": (
                    mother.current_risk_level.value
                    if mother.current_risk_level else "LOW"
                ),
            }
        )
    return data


def _mother_choices(user):
    """Lactating mothers available for linking to a child (same centre)."""
    scope = _scope_centre_id(user)
    query = Mother.query.join(Beneficiary).filter(
        Beneficiary.beneficiary_type == BeneficiaryType.LACTATING_MOTHER
    )
    if scope is not None:
        query = query.filter(Beneficiary.centre_id == scope)
    return query.order_by(Beneficiary.full_name.asc()).all()


# ---------------------------------------------------------------------------
# List / search
# ---------------------------------------------------------------------------
@bp.get("/")
@login_required
@role_required(*READ_ROLES)
def index():
    """List, search and filter beneficiaries."""
    user = current_user()
    q = (request.args.get("q") or "").strip()
    type_raw = (request.args.get("type") or "").strip()
    centre_raw = (request.args.get("centre") or "").strip()
    status_raw = (request.args.get("status") or "").strip()
    page = request.args.get("page", 1, type=int) or 1

    beneficiary_type = _safe_enum(BeneficiaryType, type_raw)
    status = _safe_enum(RecordStatus, status_raw)
    centre_id = int(centre_raw) if centre_raw.isdigit() else None

    scope = _scope_centre_id(user)
    if scope is not None:
        # Lock the filter to the AWW's centre (prevents cross-centre probing).
        centre_id = None

    pagination = beneficiary_service.search_beneficiaries(
        q=q,
        beneficiary_type=beneficiary_type,
        centre_id=centre_id,
        status=status,
        page=page,
        per_page=10,
        scope_centre_id=scope,
    )

    return render_template(
        "beneficiaries/index.html",
        pagination=pagination,
        q=q,
        type_raw=type_raw,
        centre_raw=centre_raw,
        status_raw=status_raw,
        centres=beneficiary_service.active_centres(),
        scope_centre_id=scope,
        can_write=user.role in WRITE_ROLES,
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
@bp.get("/new")
@login_required
@role_required(*WRITE_ROLES)
def new():
    """Choose which type of beneficiary to register."""
    return render_template("beneficiaries/new.html")


@bp.route("/new/child", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def create_child():
    return _handle_create(BeneficiaryType.CHILD)


@bp.route("/new/mother/<kind>", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def create_mother(kind):
    if kind not in MOTHER_KINDS:
        abort(404)
    return _handle_create(MOTHER_KINDS[kind])


def _handle_create(beneficiary_type: BeneficiaryType):
    user = current_user()
    centres = beneficiary_service.active_centres()
    mothers = _mother_choices(user)
    errors: dict[str, str] = {}

    if request.method == "POST":
        form = request.form
        centre, centre_error = _resolve_centre(user, form)
        if centre_error:
            errors["centre_id"] = centre_error
        else:
            try:
                beneficiary = beneficiary_service.create_beneficiary(
                    beneficiary_type, form, centre=centre, created_by=user
                )
            except ValidationError as exc:
                errors = exc.errors
            else:
                flash(f"Registered {beneficiary.full_name}.", "success")
                return redirect(
                    url_for("beneficiaries.detail", beneficiary_id=beneficiary.id)
                )
        flash("Please correct the highlighted fields.", "danger")
        form = request.form
    else:
        form = {
            "registration_date": date.today().isoformat(),
        }

    template = (
        "beneficiaries/form_child.html"
        if beneficiary_type == BeneficiaryType.CHILD
        else "beneficiaries/form_mother.html"
    )
    return (
        render_template(
            template,
            mode="create",
            beneficiary=None,
            beneficiary_type=beneficiary_type,
            form=form,
            errors=errors,
            centres=centres,
            mothers=mothers,
            kind_label=MOTHER_KIND_LABELS.get(beneficiary_type, "beneficiary"),
        ),
        400 if errors else 200,
    )


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------
@bp.get("/<int:beneficiary_id>")
@login_required
@role_required(*READ_ROLES)
def detail(beneficiary_id):
    beneficiary = beneficiary_service.get_beneficiary(beneficiary_id)
    _ensure_access(current_user(), beneficiary)
    return render_template("beneficiaries/detail.html", beneficiary=beneficiary)


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------
@bp.route("/<int:beneficiary_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def edit(beneficiary_id):
    user = current_user()
    beneficiary = beneficiary_service.get_beneficiary(beneficiary_id)
    _ensure_access(user, beneficiary)
    centres = beneficiary_service.active_centres()
    mothers = _mother_choices(user)
    errors: dict[str, str] = {}

    if request.method == "POST":
        form = request.form
        centre, centre_error = _resolve_centre(user, form)
        if centre_error:
            errors["centre_id"] = centre_error
        else:
            try:
                beneficiary_service.update_beneficiary(
                    beneficiary, form, centre=centre
                )
            except ValidationError as exc:
                errors = exc.errors
            else:
                flash(f"Updated {beneficiary.full_name}.", "success")
                return redirect(
                    url_for("beneficiaries.detail", beneficiary_id=beneficiary.id)
                )
        flash("Please correct the highlighted fields.", "danger")
    else:
        form = _form_from_beneficiary(beneficiary)

    template = (
        "beneficiaries/form_child.html"
        if beneficiary.beneficiary_type == BeneficiaryType.CHILD
        else "beneficiaries/form_mother.html"
    )
    return (
        render_template(
            template,
            mode="edit",
            beneficiary=beneficiary,
            beneficiary_type=beneficiary.beneficiary_type,
            form=form,
            errors=errors,
            centres=centres,
            mothers=mothers,
            kind_label=MOTHER_KIND_LABELS.get(beneficiary.beneficiary_type, "beneficiary"),
        ),
        400 if errors else 200,
    )


# ---------------------------------------------------------------------------
# Deactivate / reactivate
# ---------------------------------------------------------------------------
@bp.post("/<int:beneficiary_id>/deactivate")
@login_required
@role_required(*WRITE_ROLES)
def deactivate(beneficiary_id):
    beneficiary = beneficiary_service.get_beneficiary(beneficiary_id)
    _ensure_access(current_user(), beneficiary)
    beneficiary_service.deactivate(beneficiary)
    flash(f"Deactivated {beneficiary.full_name}.", "info")
    return redirect(url_for("beneficiaries.detail", beneficiary_id=beneficiary.id))


@bp.post("/<int:beneficiary_id>/activate")
@login_required
@role_required(*WRITE_ROLES)
def activate(beneficiary_id):
    beneficiary = beneficiary_service.get_beneficiary(beneficiary_id)
    _ensure_access(current_user(), beneficiary)
    beneficiary_service.activate(beneficiary)
    flash(f"Reactivated {beneficiary.full_name}.", "success")
    return redirect(url_for("beneficiaries.detail", beneficiary_id=beneficiary.id))


__all__ = ["bp"]
