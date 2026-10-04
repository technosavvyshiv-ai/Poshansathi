"""Anganwadi centre business logic (Phase 3).

Centre management is required by the beneficiary phase because every
beneficiary belongs to a centre.  This module provides listing, creation,
updating and soft activation/deactivation.
"""

from __future__ import annotations

from sqlalchemy import or_

from app.extensions import db
from app.models import AnganwadiCentre, Beneficiary, User
from app.utils.validators import ValidationError, validate_centre_fields


def search_centres(
    *,
    q: str = "",
    active_only: bool = False,
    page: int = 1,
    per_page: int = 10,
):
    """Return a paginated, filtered centre query."""
    query = AnganwadiCentre.query

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                AnganwadiCentre.name.ilike(like),
                AnganwadiCentre.code.ilike(like),
                AnganwadiCentre.village.ilike(like),
                AnganwadiCentre.district.ilike(like),
            )
        )

    if active_only:
        query = query.filter(AnganwadiCentre.is_active.is_(True))

    query = query.order_by(AnganwadiCentre.name.asc())
    return query.paginate(page=page, per_page=per_page, error_out=False)


def get_centre(centre_id: int) -> AnganwadiCentre:
    """Return a centre or raise a 404 error."""
    return db.get_or_404(AnganwadiCentre, centre_id)


def create_centre(form) -> AnganwadiCentre:
    """Validate and create a centre."""
    cleaned, errors = validate_centre_fields(form)
    errors.update(_uniqueness_errors(cleaned))
    if errors:
        raise ValidationError(errors)

    centre = AnganwadiCentre(**cleaned)
    db.session.add(centre)
    db.session.commit()
    return centre


def update_centre(centre: AnganwadiCentre, form) -> AnganwadiCentre:
    """Validate and apply edits to a centre."""
    cleaned, errors = validate_centre_fields(form)
    errors.update(_uniqueness_errors(cleaned, exclude_id=centre.id))
    if errors:
        raise ValidationError(errors)

    for key, value in cleaned.items():
        setattr(centre, key, value)
    db.session.commit()
    return centre


def set_active(centre: AnganwadiCentre, active: bool) -> AnganwadiCentre:
    """Soft-activate or deactivate a centre."""
    centre.is_active = active
    db.session.commit()
    return centre


def centre_statistics(centre: AnganwadiCentre) -> dict[str, int]:
    """Simple read-only counts used on the centre detail page."""
    return {
        "beneficiaries": Beneficiary.query.filter_by(centre_id=centre.id).count(),
        "active_beneficiaries": Beneficiary.query.filter_by(
            centre_id=centre.id, status="ACTIVE"
        ).count(),
        "users": User.query.filter_by(centre_id=centre.id).count(),
    }


def _uniqueness_errors(cleaned: dict, exclude_id: int | None = None) -> dict[str, str]:
    """Return field errors for duplicate centre name or code."""
    errors: dict[str, str] = {}

    name_query = AnganwadiCentre.query.filter(
        db.func.lower(AnganwadiCentre.name) == (cleaned.get("name") or "").lower()
    )
    code_query = AnganwadiCentre.query.filter(
        db.func.lower(AnganwadiCentre.code) == (cleaned.get("code") or "").lower()
    )
    if exclude_id is not None:
        name_query = name_query.filter(AnganwadiCentre.id != exclude_id)
        code_query = code_query.filter(AnganwadiCentre.id != exclude_id)

    if cleaned.get("name") and name_query.first() is not None:
        errors["name"] = "A centre with this name already exists."
    if cleaned.get("code") and code_query.first() is not None:
        errors["code"] = "A centre with this code already exists."
    return errors


__all__ = [
    "centre_statistics",
    "create_centre",
    "get_centre",
    "search_centres",
    "set_active",
    "update_centre",
]
