"""Welfare scheme routes (Phase 10).

* scheme catalogue with search / category filter and an ADMIN-managed create /
  edit form;
* scheme detail page (information + linked beneficiaries);
* beneficiary <-> scheme associations: link, update the recorded status/notes,
  unlink, and a beneficiary-focused scheme history page that also shows
  "potentially relevant" schemes from the project's demo rules.

Read access is available to every authenticated role.  Beneficiary-scheme links
are written by ADMIN (global) and AWW (their own centre).  The scheme catalogue
itself is ADMIN-managed.  Recommendations never claim official eligibility.
"""

from __future__ import annotations

from datetime import date

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.extensions import db
from app.models import Beneficiary, WelfareScheme
from app.services import scheme_service
from app.utils.constants import SchemeStatus, UserRole
from app.utils.decorators import login_required, role_required
from app.utils.helpers import current_user, ensure_beneficiary_access, scope_centre_id
from app.utils.scheme_rules import DISCLAIMER, RULE_ID
from app.utils.validators import ValidationError

bp = Blueprint("schemes", __name__)

READ_ROLES = (
    UserRole.ADMIN,
    UserRole.AWW,
    UserRole.SUPERVISOR,
    UserRole.OFFICER,
)
WRITE_ROLES = (UserRole.ADMIN, UserRole.AWW)
MANAGE_ROLES = (UserRole.ADMIN,)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_beneficiary(beneficiary_id: int) -> Beneficiary:
    """Load a beneficiary and enforce centre access for the current user."""
    beneficiary = db.get_or_404(Beneficiary, beneficiary_id)
    ensure_beneficiary_access(current_user(), beneficiary)
    return beneficiary


def _get_scheme(scheme_id: int) -> WelfareScheme:
    return scheme_service.get_scheme(scheme_id)


def _get_link(beneficiary, link_id: int):
    link = scheme_service.get_link(link_id)
    if link.beneficiary_id != beneficiary.id:
        abort(404)
    return link


def _status_counts(links) -> dict:
    counts = {status.value: 0 for status in SchemeStatus}
    for link in links:
        counts[link.status.value] += 1
    counts["TOTAL"] = len(links)
    return counts


def _flash_first(exc: ValidationError) -> None:
    flash(next(iter(exc.errors.values())), "danger")


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------
@bp.get("/schemes/")
@login_required
@role_required(*READ_ROLES)
def index():
    """Show the scheme catalogue."""
    user = current_user()
    scope = scope_centre_id(user)
    search = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()

    schemes = scheme_service.schemes_query(
        search=search, category=category, active_only=True
    )
    return render_template(
        "schemes/index.html",
        schemes=schemes,
        categories=scheme_service.categories(),
        search=search,
        category=category,
        summary=scheme_service.summary(scope_centre_id=scope),
        scope_centre_id=scope,
        can_manage=user.role in MANAGE_ROLES,
    )


@bp.route("/schemes/new", methods=["GET", "POST"])
@login_required
@role_required(*MANAGE_ROLES)
def create():
    """Create a catalogue scheme (ADMIN)."""
    errors: dict[str, str] = {}
    if request.method == "POST":
        try:
            scheme = scheme_service.create_scheme(request.form)
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash(f"Created scheme {scheme.name}.", "success")
            return redirect(url_for("schemes.index"))
        form = request.form
    else:
        form = {"is_active": "on"}

    return (
        render_template("schemes/form.html", mode="create", scheme=None, form=form, errors=errors),
        400 if errors else 200,
    )


@bp.route("/schemes/<int:scheme_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*MANAGE_ROLES)
def edit(scheme_id):
    """Edit a catalogue scheme (ADMIN)."""
    scheme = _get_scheme(scheme_id)
    errors: dict[str, str] = {}

    if request.method == "POST":
        try:
            scheme_service.update_scheme(scheme, request.form)
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash(f"Updated scheme {scheme.name}.", "success")
            return redirect(url_for("schemes.detail", scheme_id=scheme.id))
        form = request.form
    else:
        form = {
            "name": scheme.name or "",
            "category": scheme.category or "",
            "description": scheme.description or "",
            "target_group": scheme.target_group or "",
            "benefits": scheme.benefits or "",
            "eligibility": scheme.eligibility or "",
            "required_documents": scheme.required_documents or "",
            "application_info": scheme.application_info or "",
            "is_active": "on" if scheme.is_active else "",
        }

    return (
        render_template("schemes/form.html", mode="edit", scheme=scheme, form=form, errors=errors),
        400 if errors else 200,
    )


@bp.get("/schemes/<int:scheme_id>")
@login_required
@role_required(*READ_ROLES)
def detail(scheme_id):
    """Show one scheme and its linked beneficiaries."""
    user = current_user()
    scope = scope_centre_id(user)
    scheme = _get_scheme(scheme_id)
    links = scheme_service.beneficiaries_for_scheme(
        scheme, scope_centre_id=scope
    )
    return render_template(
        "schemes/detail.html",
        scheme=scheme,
        links=links,
        counts=_status_counts(links),
        scope_centre_id=scope,
        can_manage=user.role in MANAGE_ROLES,
        can_write=user.role in WRITE_ROLES,
    )


# ---------------------------------------------------------------------------
# Beneficiary scheme history + associations
# ---------------------------------------------------------------------------
@bp.get("/beneficiaries/<int:beneficiary_id>/schemes")
@login_required
@role_required(*READ_ROLES)
def beneficiary_schemes(beneficiary_id):
    """Show a beneficiary's scheme history and potentially relevant schemes."""
    user = current_user()
    beneficiary = _get_beneficiary(beneficiary_id)
    links = scheme_service.links_for_beneficiary(beneficiary)
    return render_template(
        "schemes/beneficiary.html",
        beneficiary=beneficiary,
        links=links,
        recommended=scheme_service.relevant_schemes(beneficiary),
        schemes=scheme_service.active_schemes(),
        counts=_status_counts(links),
        relevance_rule_id=RULE_ID,
        disclaimer=DISCLAIMER,
        can_write=user.role in WRITE_ROLES,
        SchemeStatus=SchemeStatus,
    )


@bp.post("/beneficiaries/<int:beneficiary_id>/schemes/link")
@login_required
@role_required(*WRITE_ROLES)
def link_create(beneficiary_id):
    """Record a beneficiary <-> scheme association."""
    beneficiary = _get_beneficiary(beneficiary_id)

    raw = (request.form.get("scheme_id") or "").strip()
    scheme = db.session.get(WelfareScheme, int(raw)) if raw.isdigit() else None
    if scheme is None:
        flash("Please select a valid scheme.", "danger")
        return redirect(
            url_for("schemes.beneficiary_schemes", beneficiary_id=beneficiary.id)
        )

    try:
        scheme_service.link_scheme(beneficiary, scheme, request.form)
    except ValidationError as exc:
        _flash_first(exc)
    else:
        flash(f"Linked scheme {scheme.name} to {beneficiary.full_name}.", "success")

    return redirect(
        url_for("schemes.beneficiary_schemes", beneficiary_id=beneficiary.id)
    )


@bp.post("/beneficiaries/<int:beneficiary_id>/schemes/<int:link_id>/update")
@login_required
@role_required(*WRITE_ROLES)
def link_update(beneficiary_id, link_id):
    """Update an association's recorded status / notes / applied date."""
    beneficiary = _get_beneficiary(beneficiary_id)
    link = _get_link(beneficiary, link_id)

    try:
        scheme_service.update_link(link, request.form)
    except ValidationError as exc:
        _flash_first(exc)
    else:
        flash("Scheme status updated.", "success")

    return redirect(
        url_for("schemes.beneficiary_schemes", beneficiary_id=beneficiary.id)
    )


@bp.post("/beneficiaries/<int:beneficiary_id>/schemes/<int:link_id>/unlink")
@login_required
@role_required(*WRITE_ROLES)
def link_delete(beneficiary_id, link_id):
    """Remove an association."""
    beneficiary = _get_beneficiary(beneficiary_id)
    link = _get_link(beneficiary, link_id)
    scheme_service.unlink(link)
    flash("Scheme link removed.", "info")
    return redirect(
        url_for("schemes.beneficiary_schemes", beneficiary_id=beneficiary.id)
    )


__all__ = ["bp"]