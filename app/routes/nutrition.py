"""Nutrition and inventory routes (Phase 7).

Covers the plan's nutrition module:

* item catalogue (list + ADMIN-managed create/edit);
* per-centre inventory with low-stock highlighting;
* stock received entries;
* beneficiary distributions (stock usage) and distribution history.

Write access is limited to ADMIN and AWW (the item catalogue to ADMIN); every
authenticated role may read, but an AWW only sees their own centre.
"""

from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import AnganwadiCentre, Beneficiary, NutritionItem
from app.services import nutrition_service
from app.utils.constants import RecordStatus, UserRole
from app.utils.decorators import login_required, role_required
from app.utils.helpers import (
    current_user,
    ensure_beneficiary_access,
    scope_centre_id,
)
from app.utils.validators import ValidationError

bp = Blueprint("nutrition", __name__)

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


def _resolve_item(form):
    """Return ``(item, error)`` for the submitted nutrition item."""
    raw = (form.get("item_id") or "").strip() if form else ""
    if not raw:
        return None, "Please select a nutrition item."
    if not raw.isdigit():
        return None, "Selected item is not valid."
    item = db.session.get(NutritionItem, int(raw))
    if item is None:
        return None, "Selected item was not found."
    if not item.is_active:
        return None, "Selected item is inactive."
    return item, None


def _beneficiary_choices(user):
    """Active beneficiaries available to the current user (centred for AWW)."""
    query = Beneficiary.query.filter_by(status=RecordStatus.ACTIVE)
    scope = scope_centre_id(user)
    if scope is not None:
        query = query.filter(Beneficiary.centre_id == scope)
    return query.order_by(
        Beneficiary.centre_id.asc(), Beneficiary.full_name.asc()
    ).all()


def _num_str(value) -> str:
    return "" if value is None else str(value)


# ---------------------------------------------------------------------------
# Overview: catalogue + inventory
# ---------------------------------------------------------------------------
@bp.get("/nutrition/")
@login_required
@role_required(*READ_ROLES)
def index():
    """Show the item catalogue and the scoped inventory position."""
    user = current_user()
    scope = scope_centre_id(user)
    centre_raw = (request.args.get("centre") or "").strip()
    centre_id = int(centre_raw) if centre_raw.isdigit() else None
    if scope is not None:
        centre_id = None

    inventory = nutrition_service.inventory_list(
        scope_centre_id=scope, centre_id=centre_id
    )
    return render_template(
        "nutrition/index.html",
        items=nutrition_service.active_items(),
        inventory=inventory,
        low_stock=[row for row in inventory if nutrition_service.is_low_stock(row)],
        summary=nutrition_service.summary(scope_centre_id=scope),
        centres=nutrition_service.active_centres(),
        centre_raw=centre_raw,
        scope_centre_id=scope,
        can_write=user.role in WRITE_ROLES,
        can_manage_items=user.role in MANAGE_ROLES,
    )


# ---------------------------------------------------------------------------
# Item catalogue management (ADMIN)
# ---------------------------------------------------------------------------
@bp.route("/nutrition/items/new", methods=["GET", "POST"])
@login_required
@role_required(*MANAGE_ROLES)
def item_create():
    errors: dict[str, str] = {}
    if request.method == "POST":
        try:
            item = nutrition_service.create_item(request.form)
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash(f"Created nutrition item {item.name}.", "success")
            return redirect(url_for("nutrition.index"))
        form = request.form
    else:
        form = {"is_active": "on", "unit": "kg"}

    return (
        render_template(
            "nutrition/item_form.html",
            mode="create",
            item=None,
            form=form,
            errors=errors,
        ),
        400 if errors else 200,
    )


@bp.route("/nutrition/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*MANAGE_ROLES)
def item_edit(item_id):
    item = nutrition_service.get_item(item_id)
    errors: dict[str, str] = {}

    if request.method == "POST":
        try:
            nutrition_service.update_item(item, request.form)
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash(f"Updated nutrition item {item.name}.", "success")
            return redirect(url_for("nutrition.index"))
        form = request.form
    else:
        form = {
            "name": item.name or "",
            "category": item.category or "",
            "unit": item.unit or "",
            "description": item.description or "",
            "is_active": "on" if item.is_active else "",
        }

    return (
        render_template(
            "nutrition/item_form.html",
            mode="edit",
            item=item,
            form=form,
            errors=errors,
        ),
        400 if errors else 200,
    )


# ---------------------------------------------------------------------------
# Stock received
# ---------------------------------------------------------------------------
@bp.route("/nutrition/stock/new", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def stock_new():
    user = current_user()
    errors: dict[str, str] = {}
    items = nutrition_service.active_items()
    centres = nutrition_service.active_centres()
    scope = scope_centre_id(user)

    if request.method == "POST":
        form = request.form
        centre, centre_error = _resolve_centre(user, form)
        item, item_error = _resolve_item(form)
        if centre_error:
            errors["centre_id"] = centre_error
        if item_error:
            errors["item_id"] = item_error

        if not errors:
            try:
                inventory = nutrition_service.record_stock_received(
                    centre, item, form, actor=user
                )
            except ValidationError as exc:
                errors = exc.errors
            else:
                flash(
                    f"Stock received for {item.name} at {inventory.centre.name}.",
                    "success",
                )
                return redirect(url_for("nutrition.index"))
        if errors:
            flash("Please correct the highlighted fields.", "danger")
    else:
        form = {
            "received_date": date.today().isoformat(),
            "unit": "",
            "centre_id": str(scope) if scope else "",
        }

    return (
        render_template(
            "nutrition/stock_form.html",
            form=form,
            errors=errors,
            items=items,
            centres=centres,
            scope_centre_id=scope,
        ),
        400 if errors else 200,
    )


# ---------------------------------------------------------------------------
# Distribution history
# ---------------------------------------------------------------------------
@bp.get("/nutrition/distributions")
@login_required
@role_required(*READ_ROLES)
def distributions():
    user = current_user()
    scope = scope_centre_id(user)
    centre_raw = (request.args.get("centre") or "").strip()
    item_raw = (request.args.get("item") or "").strip()
    beneficiary_raw = (request.args.get("beneficiary") or "").strip()

    centre_id = int(centre_raw) if centre_raw.isdigit() else None
    item_id = int(item_raw) if item_raw.isdigit() else None
    beneficiary_id = int(beneficiary_raw) if beneficiary_raw.isdigit() else None
    if scope is not None:
        centre_id = None

    rows = nutrition_service.distributions_query(
        scope_centre_id=scope,
        centre_id=centre_id,
        item_id=item_id,
        beneficiary_id=beneficiary_id,
    )
    return render_template(
        "nutrition/distributions.html",
        distributions=rows,
        items=nutrition_service.active_items(),
        centres=nutrition_service.active_centres(),
        centre_raw=centre_raw,
        item_raw=item_raw,
        beneficiary_raw=beneficiary_raw,
        scope_centre_id=scope,
        can_write=user.role in WRITE_ROLES,
    )


# ---------------------------------------------------------------------------
# Record distribution
# ---------------------------------------------------------------------------
@bp.route("/nutrition/distributions/new", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def distribution_create():
    user = current_user()
    errors: dict[str, str] = {}
    items = nutrition_service.active_items()
    beneficiaries = _beneficiary_choices(user)

    if request.method == "POST":
        form = request.form
        beneficiary = None
        beneficiary_raw = (form.get("beneficiary_id") or "").strip()
        if not beneficiary_raw:
            errors["beneficiary_id"] = "Please select a beneficiary."
        elif not beneficiary_raw.isdigit():
            errors["beneficiary_id"] = "Selected beneficiary is not valid."
        else:
            beneficiary = db.session.get(Beneficiary, int(beneficiary_raw))
            if beneficiary is None:
                errors["beneficiary_id"] = "Selected beneficiary was not found."
            else:
                # Aborts with 403 for an AWW selecting another centre's child.
                ensure_beneficiary_access(user, beneficiary)

        item, item_error = _resolve_item(form)
        if item_error:
            errors["item_id"] = item_error

        if not errors:
            try:
                nutrition_service.record_distribution(
                    beneficiary, item, form, actor=user
                )
            except ValidationError as exc:
                errors = exc.errors
            else:
                flash(
                    f"Recorded {item.name} distribution for "
                    f"{beneficiary.full_name}.",
                    "success",
                )
                return redirect(url_for("nutrition.distributions"))
        if errors:
            flash("Please correct the highlighted fields.", "danger")
    else:
        form = {"distribution_date": date.today().isoformat()}

    return (
        render_template(
            "nutrition/distribution_form.html",
            form=form,
            errors=errors,
            items=items,
            beneficiaries=beneficiaries,
        ),
        400 if errors else 200,
    )


# ---------------------------------------------------------------------------
# Per-beneficiary nutrition history
# ---------------------------------------------------------------------------
@bp.get("/beneficiaries/<int:beneficiary_id>/nutrition")
@login_required
@role_required(*READ_ROLES)
def beneficiary_history(beneficiary_id):
    beneficiary = db.get_or_404(Beneficiary, beneficiary_id)
    ensure_beneficiary_access(current_user(), beneficiary)
    rows = nutrition_service.distributions_for_beneficiary(beneficiary)
    return render_template(
        "nutrition/beneficiary_history.html",
        beneficiary=beneficiary,
        distributions=rows,
        total_quantity=sum((row.quantity or 0) for row in rows),
    )


__all__ = ["bp"]
