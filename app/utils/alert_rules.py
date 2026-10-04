"""Deterministic alert rules (Phase 9) — DEMONSTRATION RULES ONLY.

This module is the single, documented source of the **explicit project rules**
that turn stored records into follow-up alerts.  There is deliberately no LLM,
no external clinical reference and no invented medical threshold here: every
rule is a plain, testable condition over data the project already stores.

Rule set
--------
========================  ====================================================
Rule id                   Condition (deterministic)
========================  ====================================================
``growth``                The child's most recent growth classification is
                          ``UNDERWEIGHT`` or ``SEVERE_UNDERWEIGHT`` (per the
                          documented demo rule in ``growth_rules``).
``vaccination``           The child has at least one ``MISSED`` or ``OVERDUE``
                          vaccine dose (per ``vaccination_rules``).
``maternal``              The mother's most recent ANC record is ``HIGH`` risk,
                          or an ANC follow-up date is overdue.
``attendance``            The child has at least
                          :data:`ATTENDANCE_ABSENCE_THRESHOLD` absences within
                          the last :data:`ATTENDANCE_WINDOW_DAYS` days.
``home_visit``            The beneficiary has a ``SCHEDULED`` home visit whose
                          scheduled date is in the past.
``low_stock``             An inventory row has reached its **configured**
                          minimum stock (``minimum_stock > 0`` and
                          ``available <= minimum``).
========================  ====================================================

Each rule maps to an :class:`app.utils.constants.AlertType`.  Alert severity is
also deterministic and is listed below.  Bump a rule id whenever its condition
or thresholds change so tests and history stay meaningful.
"""

from __future__ import annotations

from app.utils.constants import AlertSeverity, AlertType

#: Rule identifiers (versioned).
GROWTH_RULE_ID = "poshansathi-demo-alert/growth/1"
VACCINATION_RULE_ID = "poshansathi-demo-alert/vaccination/1"
MATERNAL_RULE_ID = "poshansathi-demo-alert/maternal/1"
ATTENDANCE_RULE_ID = "poshansathi-demo-alert/attendance/1"
HOME_VISIT_RULE_ID = "poshansathi-demo-alert/home-visit/1"
LOW_STOCK_RULE_ID = "poshansathi-demo-alert/low-stock/1"

#: Attendance rule thresholds (project-defined demonstration values).
ATTENDANCE_WINDOW_DAYS = 30
ATTENDANCE_ABSENCE_THRESHOLD = 3

#: Alert types managed by the automatic rule engine.  Alerts of other types are
#: never auto-resolved by a scan.
MANAGED_TYPES = (
    AlertType.GROWTH_FOLLOW_UP,
    AlertType.VACCINATION_FOLLOW_UP,
    AlertType.MATERNAL_FOLLOW_UP,
    AlertType.ATTENDANCE,
    AlertType.HOME_VISIT_PENDING,
    AlertType.LOW_NUTRITION_STOCK,
)

#: Severity produced by each rule.
GROWTH_SEVERE = AlertSeverity.HIGH
GROWTH_UNDERWEIGHT = AlertSeverity.MEDIUM
VACCINATION_MISSED = AlertSeverity.HIGH
VACCINATION_OVERDUE = AlertSeverity.MEDIUM
MATERNAL_HIGH_RISK = AlertSeverity.HIGH
MATERNAL_OVERDUE = AlertSeverity.MEDIUM
ATTENDANCE_SEVERITY = AlertSeverity.MEDIUM
HOME_VISIT_SEVERITY = AlertSeverity.MEDIUM
LOW_STOCK_EMPTY = AlertSeverity.HIGH
LOW_STOCK_REACHED = AlertSeverity.MEDIUM

#: Human-readable labels for the UI.
RULE_LABELS = {
    AlertType.GROWTH_FOLLOW_UP: "Growth follow-up",
    AlertType.VACCINATION_FOLLOW_UP: "Vaccination follow-up",
    AlertType.MATERNAL_FOLLOW_UP: "Maternal follow-up",
    AlertType.ATTENDANCE: "Attendance follow-up",
    AlertType.HOME_VISIT_PENDING: "Home visit pending",
    AlertType.LOW_NUTRITION_STOCK: "Low nutrition stock",
    AlertType.GENERAL: "General",
}

__all__ = [
    "ATTENDANCE_ABSENCE_THRESHOLD",
    "ATTENDANCE_RULE_ID",
    "ATTENDANCE_SEVERITY",
    "ATTENDANCE_WINDOW_DAYS",
    "GROWTH_RULE_ID",
    "GROWTH_SEVERE",
    "GROWTH_UNDERWEIGHT",
    "HOME_VISIT_RULE_ID",
    "HOME_VISIT_SEVERITY",
    "LOW_STOCK_EMPTY",
    "LOW_STOCK_REACHED",
    "LOW_STOCK_RULE_ID",
    "MANAGED_TYPES",
    "MATERNAL_HIGH_RISK",
    "MATERNAL_OVERDUE",
    "MATERNAL_RULE_ID",
    "RULE_LABELS",
    "VACCINATION_MISSED",
    "VACCINATION_OVERDUE",
    "VACCINATION_RULE_ID",
]