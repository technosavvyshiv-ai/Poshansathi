"""Vaccination status display rules (Phase 5) — DEMONSTRATION RULES ONLY.

PoshanSathi does **not** encode an official national/WHO/ICDS immunisation
schedule.  PROJECT_PLAN.md section 10.4 is explicit: *"Do not invent an official
immunization schedule. Store a verified schedule/configuration supplied by the
project team."*

The stored :class:`~app.models.vaccination.Vaccination` row is therefore the
single source of truth:

* ``status``            — ``UPCOMING`` / ``DUE`` / ``COMPLETED`` / ``MISSED``
  (selected by the user, validated server-side);
* ``scheduled_date``    — optional project-entered due date;
* ``administered_date`` — optional actual administration date.

This module provides one small, deterministic helper that turns the *stored*
status plus the stored dates into a **display status** for the UI.  It never
invents a schedule and never guesses a clinical due date.  An ``OVERDUE`` view
status simply means *"this row is still UPCOMING or DUE and its own stored
scheduled date has passed"* — a presentation rule, not medical guidance.

``KNOWN_VACCINE_NAMES`` mirrors the synthetic :data:`VACCINE_SCHEDULE` already
used by ``database/seed.py``.  It exists only as a convenience suggestion list
for the form (an HTML ``<datalist>``); vaccine names remain free text.  It is
**not** an official immunisation schedule.
"""

from __future__ import annotations

import enum
from datetime import date

from app.utils.constants import VaccinationStatus

#: Identifier for the configured demo display rule set (bump on any change).
DEMO_RULE_ID = "poshansathi-demo-vaccination/status-view/1"

#: Human-readable label shown next to the status view in the UI.
DEMO_RULE_LABEL = "Project-defined demo status view — not medical guidance"


class VaccinationDisplayStatus(str, enum.Enum):
    """Deterministic view status shown in the vaccination history.

    ``COMPLETED`` and ``MISSED`` come straight from the stored enum.  ``DUE``
    and ``UPCOMING`` come from the stored enum.  ``OVERDUE`` is *derived* from a
    stored ``DUE``/``UPCOMING`` status whose own ``scheduled_date`` is past.
    """

    COMPLETED = "COMPLETED"
    MISSED = "MISSED"
    OVERDUE = "OVERDUE"
    DUE = "DUE"
    UPCOMING = "UPCOMING"


#: Short labels for the display statuses (used by the templates).
DISPLAY_LABELS = {
    VaccinationDisplayStatus.COMPLETED: "Completed",
    VaccinationDisplayStatus.MISSED: "Missed",
    VaccinationDisplayStatus.OVERDUE: "Overdue",
    VaccinationDisplayStatus.DUE: "Due",
    VaccinationDisplayStatus.UPCOMING: "Upcoming",
}

#: Bootstrap 5 badge classes for the display statuses.
DISPLAY_BADGES = {
    VaccinationDisplayStatus.COMPLETED: "text-bg-success",
    VaccinationDisplayStatus.MISSED: "text-bg-danger",
    VaccinationDisplayStatus.OVERDUE: "text-bg-warning",
    VaccinationDisplayStatus.DUE: "text-bg-info",
    VaccinationDisplayStatus.UPCOMING: "text-bg-secondary",
}

#: Vaccine names already present in the synthetic demo seed data.  Used only to
#: populate an optional form suggestion list — NOT an official schedule.
KNOWN_VACCINE_NAMES = (
    "BCG",
    "Hepatitis B",
    "OPV",
    "Pentavalent",
    "Measles",
)


def display_status(record, today: date | None = None) -> VaccinationDisplayStatus:
    """Return the deterministic display status for a vaccination ``record``.

    The result depends only on the stored ``status`` and ``scheduled_date``.
    """
    today = today or date.today()
    status = record.status
    if status == VaccinationStatus.COMPLETED:
        return VaccinationDisplayStatus.COMPLETED
    if status == VaccinationStatus.MISSED:
        return VaccinationDisplayStatus.MISSED
    if record.scheduled_date and record.scheduled_date < today:
        return VaccinationDisplayStatus.OVERDUE
    if status == VaccinationStatus.DUE:
        return VaccinationDisplayStatus.DUE
    return VaccinationDisplayStatus.UPCOMING


def is_overdue(record, today: date | None = None) -> bool:
    """Return True when ``record`` is a pending dose past its stored due date."""
    return display_status(record, today) == VaccinationDisplayStatus.OVERDUE


def display_label(status: VaccinationDisplayStatus | str) -> str:
    """Return the human label for a :class:`VaccinationDisplayStatus`."""
    try:
        key = VaccinationDisplayStatus(status)
    except ValueError:
        return str(status)
    return DISPLAY_LABELS.get(key, key.value)


def display_badge(status: VaccinationDisplayStatus | str) -> str:
    """Return the Bootstrap badge class for a display status."""
    try:
        key = VaccinationDisplayStatus(status)
    except ValueError:
        return "text-bg-secondary"
    return DISPLAY_BADGES.get(key, "text-bg-secondary")


__all__ = [
    "DEMO_RULE_ID",
    "DEMO_RULE_LABEL",
    "DISPLAY_BADGES",
    "DISPLAY_LABELS",
    "KNOWN_VACCINE_NAMES",
    "VaccinationDisplayStatus",
    "display_badge",
    "display_label",
    "display_status",
    "is_overdue",
]
