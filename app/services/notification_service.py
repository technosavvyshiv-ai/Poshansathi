"""In-app notification service (Phase 12).

The notification centre is entirely in-app: this module creates, lists and
updates the read/status state of :class:`app.models.notification.Notification`
rows for a user, and provides the deterministic data-driven generation used by
the ``/notifications/scan`` action.

There is deliberately **no** SMS/WhatsApp/email/external integration.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import abort
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Beneficiary,
    Child,
    HomeVisit,
    Inventory,
    MaternalHealthRecord,
    Mother,
    Notification,
    Vaccination,
)
from app.services import alert_service, dashboard_service
from app.utils.constants import (
    UserRole,
    VaccinationStatus,
    VisitStatus,
)
from app.utils.notification_rules import NotificationCategory, VACCINATION_DUE_WINDOW_DAYS


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------
def _add(user, *, title, message=None, category, related_type=None, related_id=None):
    notification = Notification(
        user_id=user.id,
        title=title,
        message=message,
        category=category,
        related_type=related_type,
        related_id=related_id,
        is_read=False,
    )
    db.session.add(notification)
    return notification


def create_notification(
    user, *, title, message=None, category=NotificationCategory.GENERAL,
    related_type=None, related_id=None
) -> Notification:
    """Create and persist a single notification for ``user``."""
    notification = _add(
        user,
        title=title,
        message=message,
        category=category,
        related_type=related_type,
        related_id=related_id,
    )
    db.session.commit()
    return notification


def _already_notified(user, *, title, category, related_type, related_id) -> bool:
    query = Notification.query.filter_by(
        user_id=user.id,
        title=title,
        category=category,
        related_type=related_type,
        related_id=related_id,
    )
    return query.first() is not None


def _create_once(
    user, *, title, message=None, category, related_type=None, related_id=None
) -> bool:
    """Add a notification unless an identical one already exists."""
    if _already_notified(
        user,
        title=title,
        category=category,
        related_type=related_type,
        related_id=related_id,
    ):
        return False
    _add(
        user,
        title=title,
        message=message,
        category=category,
        related_type=related_type,
        related_id=related_id,
    )
    return True


# ---------------------------------------------------------------------------
# Queries / status
# ---------------------------------------------------------------------------
def list_for_user(user, *, is_read=None, category=None, search=None):
    """Return a user's notifications, newest first, with optional filters."""
    query = Notification.query.filter(Notification.user_id == user.id)
    if is_read is not None:
        query = query.filter(Notification.is_read.is_(is_read))
    if category:
        query = query.filter(Notification.category == category)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            or_(Notification.title.ilike(like), Notification.message.ilike(like))
        )
    return query.order_by(
        Notification.created_at.desc(), Notification.id.desc()
    ).all()


def unread_count(user) -> int:
    """Return the number of unread notifications for ``user``."""
    return Notification.query.filter_by(user_id=user.id, is_read=False).count()


def status_counts(user) -> dict:
    """Return read/unread/total counts for a user."""
    notifications = list_for_user(user)
    unread = sum(1 for item in notifications if not item.is_read)
    total = len(notifications)
    return {"unread": unread, "read": total - unread, "total": total}


def get_notification(notification_id: int) -> Notification:
    """Return a notification or raise 404."""
    notification = db.session.get(Notification, notification_id)
    if notification is None:
        abort(404)
    return notification


def mark_read(notification: Notification) -> Notification:
    """Mark a notification as read (stamps ``read_at``)."""
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.session.commit()
    return notification


def mark_unread(notification: Notification) -> Notification:
    """Mark a notification as unread (clears ``read_at``)."""
    notification.is_read = False
    notification.read_at = None
    db.session.commit()
    return notification


def mark_all_read(user) -> int:
    """Mark every unread notification for ``user`` as read; returns the count."""
    unread = Notification.query.filter_by(user_id=user.id, is_read=False).all()
    now = datetime.utcnow()
    for notification in unread:
        notification.is_read = True
        notification.read_at = now
    db.session.commit()
    return len(unread)


# ---------------------------------------------------------------------------
# Deterministic data-driven generation
# ---------------------------------------------------------------------------
def _centre_id_for(user):
    """AWWs are scoped to their own centre; other roles cover all centres."""
    if user.role == UserRole.AWW and user.centre_id:
        return user.centre_id
    return None


def _generate_vaccination(user, centre_id) -> int:
    today = date.today()
    horizon = today + timedelta(days=VACCINATION_DUE_WINDOW_DAYS)
    query = (
        Vaccination.query.join(Child, Vaccination.child_id == Child.id)
        .join(Beneficiary, Child.beneficiary_id == Beneficiary.id)
        .filter(
            Vaccination.status.in_(
                [VaccinationStatus.UPCOMING, VaccinationStatus.DUE]
            ),
            Vaccination.scheduled_date.isnot(None),
            Vaccination.scheduled_date <= horizon,
        )
    )
    if centre_id is not None:
        query = query.filter(Beneficiary.centre_id == centre_id)

    created = 0
    for record in query.all():
        child = record.child
        name = child.beneficiary.full_name if child and child.beneficiary else "Child"
        title = f"Vaccination due: {record.vaccine_name} (dose {record.dose_number})"
        message = (
            f"{name} is due/overdue for {record.vaccine_name} dose "
            f"{record.dose_number} on "
            f"{record.scheduled_date.strftime('%d %b %Y')}."
        )
        if _create_once(
            user,
            title=title,
            message=message,
            category=NotificationCategory.VACCINATION,
            related_type="Vaccination",
            related_id=record.id,
        ):
            created += 1
    return created


def _generate_maternal(user, centre_id) -> int:
    today = date.today()
    query = (
        MaternalHealthRecord.query.join(
            Mother, MaternalHealthRecord.mother_id == Mother.id
        )
        .join(Beneficiary, Mother.beneficiary_id == Beneficiary.id)
        .filter(
            MaternalHealthRecord.next_follow_up_date.isnot(None),
            MaternalHealthRecord.next_follow_up_date <= today,
        )
    )
    if centre_id is not None:
        query = query.filter(Beneficiary.centre_id == centre_id)

    created = 0
    for record in query.all():
        mother_beneficiary = record.mother.beneficiary
        name = mother_beneficiary.full_name if mother_beneficiary else "Mother"
        title = "Maternal follow-up due"
        message = (
            f"{name} has an ANC follow-up due/overdue on "
            f"{record.next_follow_up_date.strftime('%d %b %Y')}."
        )
        if _create_once(
            user,
            title=title,
            message=message,
            category=NotificationCategory.MATERNAL_FOLLOW_UP,
            related_type="MaternalHealthRecord",
            related_id=record.id,
        ):
            created += 1
    return created


def _generate_visits(user, centre_id) -> int:
    today = date.today()
    query = HomeVisit.query.filter(
        HomeVisit.status == VisitStatus.SCHEDULED,
        HomeVisit.scheduled_date <= today,
    )
    if centre_id is not None:
        query = query.filter(HomeVisit.centre_id == centre_id)

    created = 0
    for visit in query.all():
        name = visit.beneficiary.full_name if visit.beneficiary else "Beneficiary"
        title = "Home visit due"
        message = (
            f"Scheduled home visit for {name} was due on "
            f"{visit.scheduled_date.strftime('%d %b %Y')}."
        )
        if _create_once(
            user,
            title=title,
            message=message,
            category=NotificationCategory.HOME_VISIT,
            related_type="HomeVisit",
            related_id=visit.id,
        ):
            created += 1
    return created


def _generate_low_stock(user, centre_id) -> int:
    query = Inventory.query
    if centre_id is not None:
        query = query.filter(Inventory.centre_id == centre_id)

    created = 0
    for inventory in query.all():
        if not dashboard_service.is_low_stock(inventory):
            continue
        title = f"Low stock: {inventory.item.name}"
        message = (
            f"{inventory.item.name} at {inventory.centre.name} is "
            f"{inventory.available_quantity} {inventory.unit} "
            f"(minimum {inventory.minimum_stock})."
        )
        if _create_once(
            user,
            title=title,
            message=message,
            category=NotificationCategory.LOW_STOCK,
            related_type="Inventory",
            related_id=inventory.id,
        ):
            created += 1
    return created


def _generate_alerts(user, centre_id) -> int:
    alerts = alert_service.list_alerts(
        scope_centre_id=centre_id, statuses=alert_service.ACTIVE_STATUSES
    )
    created = 0
    for alert in alerts:
        name = alert.beneficiary.full_name if alert.beneficiary else None
        subject = name or "Nutrition stock"
        title = f"Unresolved alert: {alert.alert_type.value.replace('_', ' ').title()}"
        message = f"{subject} — {alert.message}"
        if _create_once(
            user,
            title=title,
            message=message,
            category=NotificationCategory.ALERT,
            related_type="Alert",
            related_id=alert.id,
        ):
            created += 1
    return created


def generate_for_user(user) -> dict:
    """Run every deterministic notification rule for ``user`` (idempotent)."""
    centre_id = _centre_id_for(user)
    created = {
        "vaccination": _generate_vaccination(user, centre_id),
        "maternal": _generate_maternal(user, centre_id),
        "home_visit": _generate_visits(user, centre_id),
        "low_stock": _generate_low_stock(user, centre_id),
        "alert": _generate_alerts(user, centre_id),
    }
    db.session.commit()
    created["total"] = sum(created.values())
    return created


__all__ = [
    "create_notification",
    "generate_for_user",
    "get_notification",
    "list_for_user",
    "mark_all_read",
    "mark_read",
    "mark_unread",
    "status_counts",
    "unread_count",
]
