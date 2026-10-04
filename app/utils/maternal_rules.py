"""Maternal health display rules (Phase 6) — DEMONSTRATION RULES ONLY.

.. warning::

   Nothing in this module makes a clinical decision.  The stored
   :attr:`~app.models.maternal_health.MaternalHealthRecord.risk_category` is
   selected and stored by the health worker; PoshanSathi never computes a
   medical risk.  PROJECT_PLAN.md section 10.5 is explicit: *"Do not use an LLM
   to make clinical risk decisions."*  Likewise no clinical thresholds are
   invented here.

This module only provides deterministic presentation helpers over stored data:

* **Follow-up highlighting** derived solely from the record's own stored
  ``next_follow_up_date`` (``OVERDUE`` / ``DUE`` / ``UPCOMING``).  This is a
  project-defined demo view, not medical guidance.
* **Risk badges/labels** for the stored ``RiskLevel`` value.

``DEMO_RULE_ID`` identifies the configured demo rule set; bump it whenever the
behaviour below changes.
"""

from __future__ import annotations

import enum
from datetime import date

from app.utils.constants import RiskLevel

#: Identifier for the configured demo display rule set (bump on any change).
DEMO_RULE_ID = "poshansathi-demo-maternal/follow-up-view/1"

#: Short, user-facing label shown in the UI.
DEMO_RULE_LABEL = "Project-defined demo follow-up view — not medical guidance"


class FollowUpStatus(str, enum.Enum):
    """Deterministic view status for a stored ``next_follow_up_date``."""

    NONE = "NONE"
    OVERDUE = "OVERDUE"
    DUE = "DUE"
    UPCOMING = "UPCOMING"


FOLLOW_UP_LABELS = {
    FollowUpStatus.NONE: "Not scheduled",
    FollowUpStatus.OVERDUE: "Follow-up overdue",
    FollowUpStatus.DUE: "Follow-up due today",
    FollowUpStatus.UPCOMING: "Follow-up scheduled",
}

FOLLOW_UP_BADGES = {
    FollowUpStatus.NONE: "text-bg-secondary",
    FollowUpStatus.OVERDUE: "text-bg-danger",
    FollowUpStatus.DUE: "text-bg-warning",
    FollowUpStatus.UPCOMING: "text-bg-info",
}

RISK_LABELS = {
    RiskLevel.LOW: "Low",
    RiskLevel.MODERATE: "Moderate",
    RiskLevel.HIGH: "High",
}

RISK_BADGES = {
    RiskLevel.LOW: "text-bg-success",
    RiskLevel.MODERATE: "text-bg-warning",
    RiskLevel.HIGH: "text-bg-danger",
}


def follow_up_status(record, today: date | None = None) -> FollowUpStatus:
    """Return the deterministic follow-up status for a health ``record``.

    Depends only on the stored ``next_follow_up_date``.
    """
    today = today or date.today()
    follow_up = getattr(record, "next_follow_up_date", None)
    if follow_up is None:
        return FollowUpStatus.NONE
    if follow_up < today:
        return FollowUpStatus.OVERDUE
    if follow_up == today:
        return FollowUpStatus.DUE
    return FollowUpStatus.UPCOMING


def follow_up_label(status: FollowUpStatus | str) -> str:
    """Return a human label for a :class:`FollowUpStatus`."""
    try:
        key = FollowUpStatus(status)
    except ValueError:
        return str(status)
    return FOLLOW_UP_LABELS.get(key, key.value)


def follow_up_badge(status: FollowUpStatus | str) -> str:
    """Return the Bootstrap badge class for a follow-up status."""
    try:
        key = FollowUpStatus(status)
    except ValueError:
        return "text-bg-secondary"
    return FOLLOW_UP_BADGES.get(key, "text-bg-secondary")


def risk_label(value) -> str:
    """Return a human label for a stored risk category."""
    if value is None:
        return "—"
    try:
        key = RiskLevel(value)
    except ValueError:
        return str(value)
    return RISK_LABELS.get(key, key.value)


def risk_badge(value) -> str:
    """Return the Bootstrap badge class for a stored risk category."""
    if value is None:
        return "text-bg-secondary"
    try:
        key = RiskLevel(value)
    except ValueError:
        return "text-bg-secondary"
    return RISK_BADGES.get(key, "text-bg-secondary")


__all__ = [
    "DEMO_RULE_ID",
    "DEMO_RULE_LABEL",
    "FOLLOW_UP_BADGES",
    "FOLLOW_UP_LABELS",
    "FollowUpStatus",
    "RISK_BADGES",
    "RISK_LABELS",
    "follow_up_badge",
    "follow_up_label",
    "follow_up_status",
    "risk_badge",
    "risk_label",
]
