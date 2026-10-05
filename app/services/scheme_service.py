"""Welfare-scheme business logic (Phase 10).

Responsibilities:

* the scheme catalogue (list / filter / create / update; ADMIN-managed);
* beneficiary <-> scheme associations (link, status, applied date, notes,
  unlink) with duplicate prevention;
* the deterministic, project-configured **relevance** rules from
  :mod:`app.utils.scheme_rules`, surfaced as "potentially relevant" schemes;
* scheme history (a beneficiary's associations and a scheme's linked
  beneficiaries) and deterministic counts.

No function here claims official government eligibility: relevance is always a
project demo rule, and association status is a value recorded by the worker.
"""

from __future__ import annotations

from datetime import date

from flask import abort
from sqlalchemy import or_

from app.extensions import db
from app.models import Beneficiary, BeneficiaryScheme, WelfareScheme
from app.utils.constants import RecordStatus, SchemeStatus
from app.utils.growth_rules import age_in_months
from app.utils.helpers import age_years
from app.utils.scheme_rules import BeneficiaryProfile, evaluate
from app.utils.validators import (
    ValidationError,
    validate_beneficiary_scheme_fields,
    validate_scheme_fields,
)


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------
def all_schemes() -> list[WelfareScheme]:
    """Return every scheme ordered by name."""
    return WelfareScheme.query.order_by(WelfareScheme.name.asc()).all()


def active_schemes() -> list[WelfareScheme]:
    """Return active schemes ordered by name."""
    return (
        WelfareScheme.query.filter_by(is_active=True)
        .order_by(WelfareScheme.name.asc())
        .all()
    )


def get_scheme(scheme_id: int) -> WelfareScheme:
    """Return a scheme or raise 404."""
    return db.get_or_404(WelfareScheme, scheme_id)


def categories() -> list[str]:
    """Return the distinct configured scheme categories."""
    rows = (
        db.session.query(WelfareScheme.category)
        .filter(
            WelfareScheme.category.isnot(None),
            WelfareScheme.category != "",
        )
        .distinct()
        .order_by(WelfareScheme.category.asc())
        .all()
    )
    return [row[0] for row in rows]


def schemes_query(
    *, search: str | None = None, category: str | None = None,
    active_only: bool = True,
) -> list[WelfareScheme]:
    """Return schemes with optional text/category filters."""
    query = WelfareScheme.query
    if active_only:
        query = query.filter(WelfareScheme.is_active.is_(True))
    if category:
        query = query.filter(WelfareScheme.category == category)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            or_(
                WelfareScheme.name.ilike(like),
                WelfareScheme.target_group.ilike(like),
                WelfareScheme.description.ilike(like),
            )
        )
    return query.order_by(WelfareScheme.name.asc()).all()


def _name_exists(name: str, *, exclude_id=None) -> bool:
    query = WelfareScheme.query.filter(
        db.func.lower(WelfareScheme.name) == name.lower()
    )
    if exclude_id is not None:
        query = query.filter(WelfareScheme.id != exclude_id)
    return query.first() is not None


def create_scheme(form) -> WelfareScheme:
    """Validate and create a catalogue scheme."""
    cleaned, errors = validate_scheme_fields(form)
    if cleaned.get("name") and _name_exists(cleaned["name"]):
        errors["name"] = "A scheme with this name already exists."
    if errors:
        raise ValidationError(errors)

    scheme = WelfareScheme(**cleaned)
    db.session.add(scheme)
    db.session.commit()
    return scheme


def update_scheme(scheme: WelfareScheme, form) -> WelfareScheme:
    """Validate and update a catalogue scheme."""
    cleaned, errors = validate_scheme_fields(form)
    if cleaned.get("name") and _name_exists(
        cleaned["name"], exclude_id=scheme.id
    ):
        errors["name"] = "Another scheme with this name already exists."
    if errors:
        raise ValidationError(errors)

    for key, value in cleaned.items():
        setattr(scheme, key, value)
    db.session.commit()
    return scheme


# ---------------------------------------------------------------------------
# Beneficiary links / history
# ---------------------------------------------------------------------------
def links_for_beneficiary(beneficiary) -> list[BeneficiaryScheme]:
    """Return a beneficiary's scheme history, newest applied first."""
    return (
        BeneficiaryScheme.query.filter_by(beneficiary_id=beneficiary.id)
        .order_by(
            BeneficiaryScheme.applied_date.desc(),
            BeneficiaryScheme.id.desc(),
        )
        .all()
    )


def link_for(beneficiary, scheme) -> BeneficiaryScheme | None:
    """Return an existing association or ``None``."""
    return BeneficiaryScheme.query.filter_by(
        beneficiary_id=beneficiary.id, scheme_id=scheme.id
    ).first()


def get_link(link_id: int) -> BeneficiaryScheme:
    """Return an association or raise 404."""
    link = db.session.get(BeneficiaryScheme, link_id)
    if link is None:
        abort(404)
    return link


def beneficiaries_for_scheme(
    scheme: WelfareScheme, *, scope_centre_id=None
) -> list[BeneficiaryScheme]:
    """Return a scheme's links, newest applied first (optionally scoped)."""
    query = BeneficiaryScheme.query.join(Beneficiary).filter(
        BeneficiaryScheme.scheme_id == scheme.id
    )
    if scope_centre_id is not None:
        query = query.filter(Beneficiary.centre_id == scope_centre_id)
    return query.order_by(
        BeneficiaryScheme.applied_date.desc(),
        BeneficiaryScheme.id.desc(),
    ).all()


def link_scheme(beneficiary, scheme, form) -> BeneficiaryScheme:
    """Validate and create a beneficiary <-> scheme association.

    A deactivated beneficiary cannot be linked (matching the home-visit rule).
    """
    if beneficiary.status != RecordStatus.ACTIVE:
        raise ValidationError(
            {"beneficiary_id": "This beneficiary is inactive and cannot be linked."}
        )

    cleaned, errors = validate_beneficiary_scheme_fields(form)
    if errors:
        raise ValidationError(errors)

    if link_for(beneficiary, scheme) is not None:
        raise ValidationError(
            {"scheme_id": "This scheme is already linked to the beneficiary."}
        )

    link = BeneficiaryScheme(
        beneficiary_id=beneficiary.id,
        scheme_id=scheme.id,
        status=cleaned["status"],
        applied_date=cleaned.get("applied_date"),
        notes=cleaned.get("notes"),
    )
    db.session.add(link)
    db.session.commit()
    return link


def update_link(link: BeneficiaryScheme, form) -> BeneficiaryScheme:
    """Validate and update an association's recorded status/notes."""
    cleaned, errors = validate_beneficiary_scheme_fields(form)
    if errors:
        raise ValidationError(errors)

    link.status = cleaned["status"]
    link.applied_date = cleaned.get("applied_date")
    link.notes = cleaned.get("notes")
    db.session.commit()
    return link


def unlink(link: BeneficiaryScheme) -> None:
    """Remove an association."""
    db.session.delete(link)
    db.session.commit()


# ---------------------------------------------------------------------------
# Relevance ("potentially relevant" recommendations)
# ---------------------------------------------------------------------------
def profile_for(beneficiary) -> BeneficiaryProfile:
    """Build the deterministic profile used by the relevance rules."""
    dob = beneficiary.date_of_birth
    today = date.today()
    return BeneficiaryProfile(
        beneficiary_type=beneficiary.beneficiary_type,
        age_years=age_years(dob) if dob else None,
        age_months=age_in_months(dob, today) if dob else None,
    )


def relevance_for(beneficiary, scheme):
    """Return the :class:`Relevance` of ``scheme`` for ``beneficiary``."""
    return evaluate(profile_for(beneficiary), scheme.category)


def relevant_schemes(beneficiary) -> list[dict]:
    """Active, matching schemes the beneficiary is not already linked to.

    Results are labelled *potentially relevant* — never an eligibility claim.
    """
    linked_ids = {link.scheme_id for link in links_for_beneficiary(beneficiary)}
    rows: list[dict] = []
    for scheme in active_schemes():
        if scheme.id in linked_ids:
            continue
        relevance = relevance_for(beneficiary, scheme)
        if relevance.matched:
            rows.append({"scheme": scheme, "relevance": relevance})
    return rows


# ---------------------------------------------------------------------------
# Counts
# ---------------------------------------------------------------------------
def status_counts(*, scope_centre_id=None) -> dict:
    """Return association counts by recorded status (optionally scoped)."""
    query = BeneficiaryScheme.query.join(Beneficiary)
    if scope_centre_id is not None:
        query = query.filter(Beneficiary.centre_id == scope_centre_id)
    counts = {status.value: 0 for status in SchemeStatus}
    links = query.all()
    for link in links:
        counts[link.status.value] += 1
    counts["TOTAL"] = len(links)
    return counts


def summary(*, scope_centre_id=None) -> dict:
    """Return deterministic catalogue/association counts."""
    return {
        "scheme_count": len(active_schemes()),
        "category_count": len(categories()),
        "status_counts": status_counts(scope_centre_id=scope_centre_id),
    }


__all__ = [
    "active_schemes",
    "all_schemes",
    "beneficiaries_for_scheme",
    "categories",
    "create_scheme",
    "get_link",
    "get_scheme",
    "link_for",
    "link_scheme",
    "links_for_beneficiary",
    "profile_for",
    "relevance_for",
    "relevant_schemes",
    "schemes_query",
    "status_counts",
    "summary",
    "unlink",
    "update_link",
    "update_scheme",
]