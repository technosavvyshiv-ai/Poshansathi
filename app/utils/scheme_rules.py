"""Welfare-scheme relevance rules (Phase 10) — DEMONSTRATION RULES ONLY.

This module defines the **explicit, project-defined** rules that decide whether
a scheme is *potentially relevant* to a beneficiary.  It never claims official
government eligibility.

.. warning::

   A ``matched`` result means only *"this beneficiary's stored profile fits the
   project's configured demo rule for this scheme category"*.  It is **not** an
   eligibility determination, an entitlement, or a guarantee.  Real eligibility
   always depends on the relevant government department's own criteria and
   verification.

How matching works
------------------
Rules are keyed by the scheme's configured ``category`` (a project-managed
field).  A scheme whose category has no configured rule is simply not
recommended — the system never guesses.

======================  ===========================================
Category                Potentially relevant when…
======================  ===========================================
``Child Welfare``       child, pregnant woman or lactating mother
``Maternity Benefit``   pregnant woman or lactating mother
``Nutrition Mission``   child, pregnant woman or lactating mother
``School Nutrition``    child aged 3 years or older
``Health``              child
======================  ===========================================

``RULE_ID`` identifies the configured rule set; bump it whenever the behaviour
below changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.utils.constants import BeneficiaryType

#: Identifier for the configured relevance rule set (bump on any change).
RULE_ID = "poshansathi-demo-scheme/relevance/1"

#: Shown wherever recommendations are displayed.
DISCLAIMER = (
    "Potentially relevant based on project-configured demonstration rules — "
    "not an official eligibility determination."
)

#: Shorter inline label for badges/tables.
SHORT_DISCLAIMER = "Potentially relevant (demo rule)"


@dataclass(frozen=True)
class BeneficiaryProfile:
    """The minimal, deterministic profile a relevance rule may inspect."""

    beneficiary_type: BeneficiaryType
    age_years: int | None = None
    age_months: int | None = None


@dataclass(frozen=True)
class Relevance:
    """Outcome of evaluating one scheme category against a profile."""

    matched: bool
    rule_id: str
    reason: str


# ---------------------------------------------------------------------------
# Per-category rules (return a reason string when matched, else None)
# ---------------------------------------------------------------------------
def _child_welfare(profile: BeneficiaryProfile) -> str | None:
    if profile.beneficiary_type == BeneficiaryType.CHILD:
        return "Child under 6 years"
    if profile.beneficiary_type in (
        BeneficiaryType.PREGNANT_WOMAN,
        BeneficiaryType.LACTATING_MOTHER,
    ):
        return "Pregnant or lactating mother"
    return None


def _maternity_benefit(profile: BeneficiaryProfile) -> str | None:
    if profile.beneficiary_type in (
        BeneficiaryType.PREGNANT_WOMAN,
        BeneficiaryType.LACTATING_MOTHER,
    ):
        return "Pregnant or lactating mother"
    return None


def _nutrition_mission(profile: BeneficiaryProfile) -> str | None:
    if profile.beneficiary_type in (
        BeneficiaryType.CHILD,
        BeneficiaryType.PREGNANT_WOMAN,
        BeneficiaryType.LACTATING_MOTHER,
    ):
        return "Child, pregnant woman or lactating mother"
    return None


def _school_nutrition(profile: BeneficiaryProfile) -> str | None:
    if (
        profile.beneficiary_type == BeneficiaryType.CHILD
        and profile.age_years is not None
        and profile.age_years >= 3
    ):
        return "Child aged 3 years or older"
    return None


def _health(profile: BeneficiaryProfile) -> str | None:
    if profile.beneficiary_type == BeneficiaryType.CHILD:
        return "Infant/child immunisation target group"
    return None


#: Configured category -> rule mapping.  Unknown categories never match.
CATEGORY_RULES = {
    "Child Welfare": _child_welfare,
    "Maternity Benefit": _maternity_benefit,
    "Nutrition Mission": _nutrition_mission,
    "School Nutrition": _school_nutrition,
    "Health": _health,
}


def evaluate(profile: BeneficiaryProfile, category: str | None) -> Relevance:
    """Return the deterministic relevance of ``category`` for ``profile``."""
    key = (category or "").strip()
    rule = CATEGORY_RULES.get(key)
    if rule is None:
        return Relevance(
            matched=False,
            rule_id=RULE_ID,
            reason="No configured relevance rule for this scheme category.",
        )

    reason = rule(profile)
    if reason:
        return Relevance(matched=True, rule_id=RULE_ID, reason=reason)
    return Relevance(
        matched=False,
        rule_id=RULE_ID,
        reason="Profile does not match the configured demo rule.",
    )


__all__ = [
    "BeneficiaryProfile",
    "CATEGORY_RULES",
    "DISCLAIMER",
    "Relevance",
    "RULE_ID",
    "SHORT_DISCLAIMER",
    "evaluate",
]