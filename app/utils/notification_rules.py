"""In-app notification categories and deterministic generation rules (Phase 12).

The notification centre is **in-app only** (no SMS/WhatsApp/email).  This module
documents the categories and the explicit, testable rules used to turn stored
data into notifications.

Generation rules (per user, scoped to the user's centre for an AWW)
------------------------------------------------------------------
============================  =============================================
Category                      Created when…
============================  =============================================
``VACCINATION``               a child has a ``UPCOMING``/``DUE`` dose whose
                              scheduled date is within the due window.
``MATERNAL_FOLLOW_UP``        an ANC record's follow-up date is due/overdue.
``HOME_VISIT``                a ``SCHEDULED`` home visit is due/overdue.
``LOW_STOCK``                 inventory has reached its configured minimum.
``ALERT``                     an alert is open / in progress.
``GENERAL``                   manually created.
============================  =============================================

Generation is idempotent: an existing notification with the same user,
category, related record and title is never duplicated.
"""

from __future__ import annotations


class NotificationCategory:
    """String categories stored on :class:`app.models.notification.Notification`."""

    VACCINATION = "VACCINATION"
    MATERNAL_FOLLOW_UP = "MATERNAL_FOLLOW_UP"
    HOME_VISIT = "HOME_VISIT"
    LOW_STOCK = "LOW_STOCK"
    ALERT = "ALERT"
    GENERAL = "GENERAL"


ALL_CATEGORIES = (
    NotificationCategory.VACCINATION,
    NotificationCategory.MATERNAL_FOLLOW_UP,
    NotificationCategory.HOME_VISIT,
    NotificationCategory.LOW_STOCK,
    NotificationCategory.ALERT,
    NotificationCategory.GENERAL,
)

CATEGORY_LABELS = {
    NotificationCategory.VACCINATION: "Vaccination",
    NotificationCategory.MATERNAL_FOLLOW_UP: "Maternal follow-up",
    NotificationCategory.HOME_VISIT: "Home visit",
    NotificationCategory.LOW_STOCK: "Low stock",
    NotificationCategory.ALERT: "Alert",
    NotificationCategory.GENERAL: "General",
}

CATEGORY_BADGES = {
    NotificationCategory.VACCINATION: "text-bg-info",
    NotificationCategory.MATERNAL_FOLLOW_UP: "text-bg-warning",
    NotificationCategory.HOME_VISIT: "text-bg-primary",
    NotificationCategory.LOW_STOCK: "text-bg-danger",
    NotificationCategory.ALERT: "text-bg-danger",
    NotificationCategory.GENERAL: "text-bg-secondary",
}

#: Vaccination doses due within this many days (or already overdue) notify.
VACCINATION_DUE_WINDOW_DAYS = 7

__all__ = [
    "ALL_CATEGORIES",
    "CATEGORY_BADGES",
    "CATEGORY_LABELS",
    "NotificationCategory",
    "VACCINATION_DUE_WINDOW_DAYS",
]
