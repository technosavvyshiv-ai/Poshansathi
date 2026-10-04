"""Beneficiary business logic (Phase 3).

Encapsulates beneficiary search/filter, creation of child and mother records,
updating, and soft deactivation.  Routes call these functions; templates render
the results.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Beneficiary, Child, Mother
from app.utils.constants import BeneficiaryType, RecordStatus
from app.utils.validators import (
    ValidationError,
    validate_beneficiary_fields,
    validate_child_fields,
    validate_mother_fields,
)

#: Beneficiary types that carry a ``Mother`` profile.
MOTHER_TYPES = (
    BeneficiaryType.PREGNANT_WOMAN,
    BeneficiaryType.LACTATING_MOTHER,
)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def search_beneficiaries(
    *,
    q: str = "",
    beneficiary_type: BeneficiaryType | None = None,
    centre_id: int | None = None,
    status: RecordStatus | None = None,
    page: int = 1,
    per_page: int = 10,
    scope_centre_id: int | None = None,
):
    """Return a paginated, filtered beneficiary query.

    :param q: free-text match on name, guardian name or contact.
    :param scope_centre_id: when set, restrict results to this centre (used to
        keep an AWW's view limited to their own centre).
    """
    query = Beneficiary.query.options(
        joinedload(Beneficiary.centre),
        joinedload(Beneficiary.child),
        joinedload(Beneficiary.mother),
    )

    if scope_centre_id is not None:
        query = query.filter(Beneficiary.centre_id == scope_centre_id)

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Beneficiary.full_name.ilike(like),
                Beneficiary.guardian_name.ilike(like),
                Beneficiary.contact.ilike(like),
            )
        )

    if beneficiary_type is not None:
        query = query.filter(Beneficiary.beneficiary_type == beneficiary_type)

    if centre_id is not None:
        query = query.filter(Beneficiary.centre_id == centre_id)

    if status is not None:
        query = query.filter(Beneficiary.status == status)

    query = query.order_by(Beneficiary.created_at.desc(), Beneficiary.id.desc())
    return query.paginate(page=page, per_page=per_page, error_out=False)


def get_beneficiary(beneficiary_id: int) -> Beneficiary:
    """Return a beneficiary or raise a 404 error."""
    return db.get_or_404(Beneficiary, beneficiary_id)


def active_centres():
    """Return all active centres ordered by name (for form dropdowns)."""
    from app.models import AnganwadiCentre

    return (
        AnganwadiCentre.query.filter_by(is_active=True)
        .order_by(AnganwadiCentre.name.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------
def _duplicate_exists(
    *, full_name: str, date_of_birth, centre_id: int, beneficiary_type, exclude_id=None
) -> bool:
    """True when the same person is already registered at the centre."""
    if not full_name or date_of_birth is None or centre_id is None:
        return False
    query = Beneficiary.query.filter(
        db.func.lower(Beneficiary.full_name) == full_name.lower(),
        Beneficiary.date_of_birth == date_of_birth,
        Beneficiary.centre_id == centre_id,
        Beneficiary.beneficiary_type == beneficiary_type,
    )
    if exclude_id is not None:
        query = query.filter(Beneficiary.id != exclude_id)
    return query.first() is not None


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def create_beneficiary(
    beneficiary_type: BeneficiaryType,
    form,
    *,
    centre,
    created_by=None,
) -> Beneficiary:
    """Validate ``form`` and create a beneficiary plus its profile.

    Raises :class:`ValidationError` when any field is invalid.
    """
    cleaned, errors = validate_beneficiary_fields(form, beneficiary_type)

    if beneficiary_type == BeneficiaryType.CHILD:
        profile_cleaned, profile_errors = validate_child_fields(form)
        errors.update(profile_errors)
        profile = Child
    elif beneficiary_type in MOTHER_TYPES:
        profile_cleaned, profile_errors = validate_mother_fields(
            form, beneficiary_type
        )
        errors.update(profile_errors)
        profile = Mother
    else:  # pragma: no cover - defensive
        raise ValidationError({"beneficiary_type": "Unknown beneficiary type."})

    if errors:
        raise ValidationError(errors)

    if _duplicate_exists(
        full_name=cleaned["full_name"],
        date_of_birth=cleaned["date_of_birth"],
        centre_id=centre.id,
        beneficiary_type=beneficiary_type,
    ):
        raise ValidationError(
            {

                "full_name": (
                    "A beneficiary with the same name and date of birth is "
                    "already registered at this centre."
                )
            }
        )

    beneficiary = Beneficiary(
        centre=centre,
        beneficiary_type=beneficiary_type,
        status=RecordStatus.ACTIVE,
        **cleaned,
    )

    if profile is Child:
        _validate_mother_link(profile_cleaned, centre, errors)
        if errors:
            raise ValidationError(errors)
        beneficiary.child = Child(**profile_cleaned)
    else:
        beneficiary.mother = Mother(**profile_cleaned)

    db.session.add(beneficiary)
    db.session.commit()
    return beneficiary


def _validate_mother_link(profile_cleaned: dict[str, Any], centre, errors) -> None:
    """Ensure a linked child's mother exists and belongs to the same centre."""
    mother_id = profile_cleaned.get("mother_id")
    if not mother_id:
        return
    mother = db.session.get(Mother, mother_id)
    if mother is None or mother.beneficiary.centre_id != centre.id:
        errors["mother_id"] = "Selected mother was not found at this centre."


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
def update_beneficiary(beneficiary: Beneficiary, form, *, centre=None) -> Beneficiary:
    """Validate and apply edits to a beneficiary and its profile."""
    beneficiary_type = beneficiary.beneficiary_type
    cleaned, errors = validate_beneficiary_fields(form, beneficiary_type)

    if beneficiary_type == BeneficiaryType.CHILD:
        profile_cleaned, profile_errors = validate_child_fields(form)
        errors.update(profile_errors)
        profile = beneficiary.child
    elif beneficiary_type in MOTHER_TYPES:
        profile_cleaned, profile_errors = validate_mother_fields(
            form, beneficiary_type
        )
        errors.update(profile_errors)
        profile = beneficiary.mother
    else:  # pragma: no cover - defensive
        raise ValidationError({"beneficiary_type": "Unknown beneficiary type."})

    target_centre = centre or beneficiary.centre
    if errors:
        raise ValidationError(errors)

    if _duplicate_exists(
        full_name=cleaned["full_name"],
        date_of_birth=cleaned["date_of_birth"],
        centre_id=target_centre.id,
        beneficiary_type=beneficiary_type,
        exclude_id=beneficiary.id,
    ):
        raise ValidationError(
            {
                "full_name": (
                    "Another beneficiary with the same name and date of birth "
                    "already exists at this centre."
                )
            }
        )

    if profile is None:  # pragma: no cover - defensive repair path
        profile = (
            Child(beneficiary=beneficiary)
            if beneficiary_type == BeneficiaryType.CHILD
            else Mother(beneficiary=beneficiary)
        )

    if beneficiary_type == BeneficiaryType.CHILD:
        _validate_mother_link(profile_cleaned, target_centre, errors)
        if errors:  # pragma: no cover - defensive
            raise ValidationError(errors)

    beneficiary.centre = target_centre
    for key, value in cleaned.items():
        setattr(beneficiary, key, value)
    for key, value in profile_cleaned.items():
        setattr(profile, key, value)

    db.session.commit()
    return beneficiary


# ---------------------------------------------------------------------------
# Status changes (soft deactivate / reactivate)
# ---------------------------------------------------------------------------
def set_status(beneficiary: Beneficiary, status: RecordStatus) -> Beneficiary:
    """Soft-deactivate or reactivate a beneficiary."""
    beneficiary.status = status
    db.session.commit()
    return beneficiary


def deactivate(beneficiary: Beneficiary) -> Beneficiary:
    return set_status(beneficiary, RecordStatus.INACTIVE)


def activate(beneficiary: Beneficiary) -> Beneficiary:
    return set_status(beneficiary, RecordStatus.ACTIVE)


__all__ = [
    "MOTHER_TYPES",
    "activate",
    "active_centres",
    "create_beneficiary",
    "deactivate",
    "get_beneficiary",
    "search_beneficiaries",
    "set_status",
    "update_beneficiary",
]
