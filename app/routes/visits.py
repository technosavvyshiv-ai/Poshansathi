"""Home visit and intervention routes (Phase 9).

Covers the plan's home-visit workflow:

* list / filter home visits;
* schedule and edit a visit;
* complete or cancel a visit;
* record and edit interventions (with optional follow-up and alert resolution).

Write access is limited to ADMIN and AWW; every authenticated role may read,
but an AWW only reaches beneficiaries of their own centre.
"""

from __future__ import annotations

from datetime import date

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import or_

from app.extensions import db
from app.models import AnganwadiCentre, Beneficiary, User
from app.services import visit_service
from app.utils.constants import (
    RecordStatus,
    UserRole,
    VisitStatus,
    VisitType,
)
from app.utils.decorators import login_required, role_required
from app.utils.helpers import current_user, ensure_beneficiary_access, scope_centre_id
from app.utils.validators import ValidationError

bp = Blueprint("visits", __name__, url_prefix="/visits")

READ_ROLES = (
    UserRole.ADMIN,
    UserRole.AWW,
    UserRole.SUPERVISOR,
    UserRole.OFFICER,
)
WRITE_ROLES = (UserRole.ADMIN, UserRole.AWW)

INTERVENTION_TYPES = (
    "Nutrition counselling",
    "Health counselling",
    "Immunisation follow-up",
    "Growth monitoring follow-up",
    "Maternal care follow-up",
    "Referral",
    "Supplementary nutrition",
    "Other",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_visit(visit_id: int):
    visit = visit_service.get_visit(visit_id)
    ensure_beneficiary_access(current_user(), visit.beneficiary)
    return visit


def _get_intervention(intervention_id: int):
    intervention = visit_service.get_intervention(intervention_id)
    ensure_beneficiary_access(current_user(), intervention.beneficiary)
    return intervention


def _active_centres():
    return (
        AnganwadiCentre.query.filter_by(is_active=True)
        .order_by(AnganwadiCentre.name.asc())
        .all()
    )


def _beneficiary_choices(user):
    query = Beneficiary.query.filter_by(status=RecordStatus.ACTIVE)
    scope = scope_centre_id(user)
    if scope is not None:
        query = query.filter(Beneficiary.centre_id == scope)
    return query.order_by(
        Beneficiary.centre_id.asc(), Beneficiary.full_name.asc()
    ).all()


def _worker_choices(user):
    query = User.query.filter(
        User.is_active.is_(True),
        User.role.in_([UserRole.AWW, UserRole.ADMIN]),
    )
    scope = scope_centre_id(user)
    if scope is not None:
        query = query.filter(
            or_(User.centre_id == scope, User.role == UserRole.ADMIN)
        )
    return query.order_by(User.full_name.asc()).all()


def _resolve_beneficiary(form, user):
    raw = (form.get("beneficiary_id") or "").strip()
    if not raw:
        return None, "Please select a beneficiary."
    if not raw.isdigit():
        return None, "Selected beneficiary is not valid."
    beneficiary = db.session.get(Beneficiary, int(raw))
    if beneficiary is None:
        return None, "Selected beneficiary was not found."
    if beneficiary.status != RecordStatus.ACTIVE:
        return None, "Selected beneficiary is inactive."
    ensure_beneficiary_access(user, beneficiary)
    return beneficiary, None


def _resolve_worker(form, default_user):
    raw = (form.get("assigned_worker_id") or "").strip()
    if not raw:
        return default_user, None
    if not raw.isdigit():
        return None, "Selected worker is not valid."
    worker = db.session.get(User, int(raw))
    if worker is None or not worker.is_active:
        return None, "Selected worker was not found."
    return worker, None


def _enum_arg(raw, enum_cls):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return enum_cls(raw)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@bp.get("/")
@login_required
@role_required(*READ_ROLES)
def index():
    """Show a filterable list of home visits."""
    user = current_user()
    scope = scope_centre_id(user)

    centre_raw = (request.args.get("centre") or "").strip()
    status = _enum_arg(request.args.get("status"), VisitStatus)
    visit_type = _enum_arg(request.args.get("type"), VisitType)
    beneficiary_raw = (request.args.get("beneficiary") or "").strip()
    follow_up_raw = (request.args.get("follow_up") or "").strip()
    follow_up = True if follow_up_raw in ("1", "true", "on", "yes") else None

    centre_id = None if scope is not None else (
        int(centre_raw) if centre_raw.isdigit() else None
    )

    visits = visit_service.visits_query(
        scope_centre_id=scope,
        centre_id=centre_id,
        status=status,
        visit_type=visit_type,
        beneficiary_id=(
            int(beneficiary_raw) if beneficiary_raw.isdigit() else None
        ),
        follow_up_required=follow_up,
    )
    return render_template(
        "visits/index.html",
        visits=visits,
        summary=visit_service.summary(scope_centre_id=scope),
        centres=_active_centres(),
        centre_raw=centre_raw,
        status_raw=(request.args.get("status") or "").strip(),
        type_raw=(request.args.get("type") or "").strip(),
        beneficiary_raw=beneficiary_raw,
        follow_up_raw=follow_up_raw,
        scope_centre_id=scope,
        can_write=user.role in WRITE_ROLES,
        VisitStatus=VisitStatus,
        VisitType=VisitType,
    )


# ---------------------------------------------------------------------------
# Schedule / edit
# ---------------------------------------------------------------------------
@bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def create():
    """Schedule a new home visit."""
    user = current_user()
    errors: dict[str, str] = {}
    beneficiaries = _beneficiary_choices(user)
    workers = _worker_choices(user)

    if request.method == "POST":
        form = request.form
        beneficiary, beneficiary_error = _resolve_beneficiary(form, user)
        worker, worker_error = _resolve_worker(form, user)
        if beneficiary_error:
            errors["beneficiary_id"] = beneficiary_error
        if worker_error:
            errors["assigned_worker_id"] = worker_error

        if not errors:
            try:
                visit = visit_service.create_visit(
                    beneficiary, worker, form, actor=user
                )
            except ValidationError as exc:
                errors = exc.errors
            else:
                flash("Home visit scheduled.", "success")
                return redirect(url_for("visits.detail", visit_id=visit.id))
        if errors:
            flash("Please correct the highlighted fields.", "danger")
    else:
        form = {
            "beneficiary_id": (request.args.get("beneficiary") or "").strip(),
            "scheduled_date": date.today().isoformat(),
            "visit_type": VisitType.ROUTINE.value,
            "assigned_worker_id": str(user.id),
        }

    return (
        render_template(
            "visits/form.html",
            mode="create",
            visit=None,
            form=form,
            errors=errors,
            beneficiaries=beneficiaries,
            workers=workers,
        ),
        400 if errors else 200,
    )


@bp.route("/<int:visit_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def edit(visit_id):
    """Edit an existing home visit."""
    user = current_user()
    visit = _get_visit(visit_id)
    errors: dict[str, str] = {}
    beneficiaries = _beneficiary_choices(user)
    workers = _worker_choices(user)

    if request.method == "POST":
        form = request.form
        beneficiary, beneficiary_error = _resolve_beneficiary(form, user)
        worker, worker_error = _resolve_worker(form, user)
        if beneficiary_error:
            errors["beneficiary_id"] = beneficiary_error
        if worker_error:
            errors["assigned_worker_id"] = worker_error

        if not errors:
            try:
                visit_service.update_visit(
                    visit, beneficiary, worker, form, actor=user
                )
            except ValidationError as exc:
                errors = exc.errors
            else:
                flash("Home visit updated.", "success")
                return redirect(url_for("visits.detail", visit_id=visit.id))
        if errors:
            flash("Please correct the highlighted fields.", "danger")
    else:
        form = {
            "beneficiary_id": str(visit.beneficiary_id),
            "visit_type": (
                visit.visit_type.value if visit.visit_type else VisitType.ROUTINE.value
            ),
            "assigned_worker_id": (
                str(visit.assigned_worker_id) if visit.assigned_worker_id else ""
            ),
            "scheduled_date": (
                visit.scheduled_date.isoformat() if visit.scheduled_date else ""
            ),
            "visit_notes": visit.visit_notes or "",
        }

    return (
        render_template(
            "visits/form.html",
            mode="edit",
            visit=visit,
            form=form,
            errors=errors,
            beneficiaries=beneficiaries,
            workers=workers,
        ),
        400 if errors else 200,
    )


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------
@bp.get("/<int:visit_id>")
@login_required
@role_required(*READ_ROLES)
def detail(visit_id):
    """Show one home visit and its interventions."""
    visit = _get_visit(visit_id)
    return render_template(
        "visits/detail.html",
        visit=visit,
        beneficiary=visit.beneficiary,
        interventions=visit_service.interventions_for_visit(visit),
        open_alerts=visit_service.open_alerts_for_beneficiary(visit.beneficiary),
        can_write=current_user().role in WRITE_ROLES,
        VisitStatus=VisitStatus,
    )


# ---------------------------------------------------------------------------
# Complete / cancel
# ---------------------------------------------------------------------------
@bp.post("/<int:visit_id>/complete")
@login_required
@role_required(*WRITE_ROLES)
def complete(visit_id):
    """Mark a visit completed."""
    visit = _get_visit(visit_id)
    try:
        visit_service.complete_visit(visit, request.form, actor=current_user())
    except ValidationError as exc:
        flash(next(iter(exc.errors.values())), "danger")
    else:
        flash("Home visit completed.", "success")
    return redirect(url_for("visits.detail", visit_id=visit.id))


@bp.post("/<int:visit_id>/cancel")
@login_required
@role_required(*WRITE_ROLES)
def cancel(visit_id):
    """Cancel a visit."""
    visit = _get_visit(visit_id)
    try:
        visit_service.cancel_visit(visit, actor=current_user())
    except ValidationError as exc:
        flash(next(iter(exc.errors.values())), "danger")
    else:
        flash("Home visit cancelled.", "info")
    return redirect(url_for("visits.detail", visit_id=visit.id))


# ---------------------------------------------------------------------------
# Interventions
# ---------------------------------------------------------------------------
@bp.route("/<int:visit_id>/interventions/new", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def intervention_create(visit_id):
    """Record an intervention for a visit."""
    visit = _get_visit(visit_id)
    errors: dict[str, str] = {}

    if request.method == "POST":
        try:
            visit_service.record_intervention(
                visit, request.form, actor=current_user()
            )
        except ValidationError as exc:
            errors = exc.errors
            flash(
                exc.errors.get("visit", "Please correct the highlighted fields."),
                "danger",
            )
        else:
            flash("Intervention recorded.", "success")
            return redirect(url_for("visits.detail", visit_id=visit.id))
        form = request.form
    else:
        form = {
            "intervention_date": date.today().isoformat(),
            "follow_up_required": "",
        }

    return (
        render_template(
            "visits/intervention_form.html",
            mode="create",
            visit=visit,
            intervention=None,
            form=form,
            errors=errors,
            open_alerts=visit_service.open_alerts_for_beneficiary(
                visit.beneficiary
            ),
            intervention_types=INTERVENTION_TYPES,
        ),
        400 if errors else 200,
    )


@bp.route("/interventions/<int:intervention_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def intervention_edit(intervention_id):
    """Edit an existing intervention."""
    intervention = _get_intervention(intervention_id)
    visit = intervention.home_visit
    errors: dict[str, str] = {}

    if request.method == "POST":
        try:
            visit_service.update_intervention(
                intervention, request.form, actor=current_user()
            )
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash("Intervention updated.", "success")
            if visit is not None:
                return redirect(url_for("visits.detail", visit_id=visit.id))
            return redirect(
                url_for(
                    "beneficiaries.detail",
                    beneficiary_id=intervention.beneficiary_id,
                )
            )
        form = request.form
    else:
        form = {
            "intervention_type": intervention.intervention_type or "",
            "description": intervention.description or "",
            "outcome": intervention.outcome or "",
            "intervention_date": (
                intervention.intervention_date.isoformat()
                if intervention.intervention_date
                else ""
            ),
            "follow_up_required": "on" if intervention.follow_up_required else "",
            "follow_up_date": (
                intervention.follow_up_date.isoformat()
                if intervention.follow_up_date
                else ""
            ),
        }

    return (
        render_template(
            "visits/intervention_form.html",
            mode="edit",
            visit=visit,
            intervention=intervention,
            form=form,
            errors=errors,
            open_alerts=visit_service.open_alerts_for_beneficiary(
                intervention.beneficiary
            ),
            intervention_types=INTERVENTION_TYPES,
        ),
        400 if errors else 200,
    )


__all__ = ["bp"]