"""Growth classification rules (Phase 4) — DEMONSTRATION RULES ONLY.

.. warning::

   The thresholds in this module are **not clinical thresholds** and must not
   be presented as medical guidance, as WHO/ICDS references, or as a
   diagnosis.  They exist only so the PoshanSathi college demo can produce a
   deterministic growth status and a follow-up alert from a fixed, documented,
   project-defined rule set.

   PROJECT_PLAN.md section 10.3 explicitly allows this: *"For the college demo,
   the alert engine may initially use clearly documented demo rules, labelled
   as demonstration rules."*

Rule set
--------
A simple **weight-for-age ratio** rule:

1. Look up a project-defined *expected weight* for the child's completed age in
   months (see :data:`EXPECTED_WEIGHT_KG`).
2. Compute ``ratio = measured_weight / expected_weight``.
3. Classify:

   =========================  ==============================
   Condition                  ``NutritionalStatus``
   =========================  ==============================
   ``ratio < 0.70``           ``SEVERE_UNDERWEIGHT``
   ``0.70 <= ratio < 0.85``   ``UNDERWEIGHT``
   ``0.85 <= ratio <= 1.30``  ``NORMAL``
   ``ratio > 1.30``           ``OVERWEIGHT``
   =========================  ==============================

Version / source
----------------
``DEMO_RULE_ID = "poshansathi-demo-growth/weight-for-age/1"`` — an internal
project rule, **not** an external reference.  Change the version whenever the
values below change.

All values can be overridden by the application configuration key
``GROWTH_DEMO_RULES`` (see ``config.py``) so the rule set is genuinely
*configured* rather than hard-coded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.utils.constants import NutritionalStatus

#: Identifier for the configured demo rule set (bump on any value change).
DEMO_RULE_ID = "poshansathi-demo-growth/weight-for-age/1"

#: Short, user-facing label shown in the UI next to every classification.
DEMO_RULE_LABEL = "Demonstration rule (weight-for-age) — not medical advice"

#: Maximum age (completed months) covered by the demo table.
MAX_TABLE_AGE_MONTHS = 72


@dataclass(frozen=True)
class GrowthDemoRules:
    """A fully documented, project-defined (non-clinical) demo rule set."""

    #: (max completed age in months inclusive, expected weight kg)
    expected_weight_kg: tuple[tuple[int, float], ...] = (
        (6, 6.0),
        (12, 8.5),
        (24, 11.0),
        (36, 13.0),
        (48, 15.0),
        (60, 17.5),
        (72, 20.0),
    )
    severe_ratio: float = 0.70
    under_ratio: float = 0.85
    over_ratio: float = 1.30

    def expected_weight(self, age_months: int) -> float:
        """Return the configured expected weight for ``age_months``."""
        for max_months, weight in self.expected_weight_kg:
            if age_months <= max_months:
                return weight
        # Older than the table: use the last configured band.
        return self.expected_weight_kg[-1][1]


#: Default rule set used when the application configuration is not available.
DEFAULT_RULES = GrowthDemoRules()


def age_in_months(date_of_birth: date, on_date: date) -> int:
    """Return completed months between ``date_of_birth`` and ``on_date``.

    Returns ``0`` when ``on_date`` precedes the date of birth (validation
    rejects that case before classification runs).
    """
    if date_of_birth is None or on_date is None or on_date < date_of_birth:
        return 0
    months = (on_date.year - date_of_birth.year) * 12 + (
        on_date.month - date_of_birth.month
    )
    if on_date.day < date_of_birth.day:
        months -= 1
    return max(months, 0)


def classify(
    weight_kg: Decimal | float,
    age_months: int,
    rules: GrowthDemoRules | None = None,
) -> tuple[NutritionalStatus, float]:
    """Classify ``weight_kg`` for ``age_months`` using the demo rule set.

    :returns: ``(status, ratio)`` where ``ratio`` is the measured/expected
        weight ratio used to make the decision.
    """
    rules = rules or DEFAULT_RULES
    expected = rules.expected_weight(age_months)
    ratio = float(weight_kg) / expected if expected else 0.0

    if ratio < rules.severe_ratio:
        status = NutritionalStatus.SEVERE_UNDERWEIGHT
    elif ratio < rules.under_ratio:
        status = NutritionalStatus.UNDERWEIGHT
    elif ratio > rules.over_ratio:
        status = NutritionalStatus.OVERWEIGHT
    else:
        status = NutritionalStatus.NORMAL
    return status, ratio


def is_concerning(status: NutritionalStatus) -> bool:
    """Return True when ``status`` should raise a growth follow-up alert."""
    return status in (
        NutritionalStatus.UNDERWEIGHT,
        NutritionalStatus.SEVERE_UNDERWEIGHT,
    )


def explanation(
    status: NutritionalStatus,
    ratio: float,
    age_months: int,
    rules: GrowthDemoRules | None = None,
) -> str:
    """Human-readable explanation of a demo classification."""
    rules = rules or DEFAULT_RULES
    expected = rules.expected_weight(age_months)
    return (
        f"Demo rule {DEMO_RULE_ID}: weight is {ratio * 100:.0f}% of the "
        f"configured expected {expected:.1f} kg for {age_months} month(s) "
        f"→ {status.value}."
    )


__all__ = [
    "DEFAULT_RULES",
    "DEMO_RULE_ID",
    "DEMO_RULE_LABEL",
    "GrowthDemoRules",
    "MAX_TABLE_AGE_MONTHS",
    "age_in_months",
    "classify",
    "explanation",
    "is_concerning",
]
