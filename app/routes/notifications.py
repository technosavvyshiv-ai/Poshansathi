"""In-app notification routes (Phase 12).

An in-app notification centre only — no SMS/WhatsApp/email.  A user may list,
filter and change the read state of **their own** notifications.  Mutating
another user's notification is forbidden (403).
"""

from __future__ import annotations

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.services import notification_service
from app.utils.decorators import login_required
from app.utils.helpers import current_user
from app.utils.notification_rules import (
    ALL_CATEGORIES,
    CATEGORY_BADGES,
    CATEGORY_LABELS,
)

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


def _owned(notification):
    """Abort 403 unless the notification belongs to the current user."""
    if notification.user_id != current_user().id:
        abort(403)
    return notification


@bp.get("/")
@login_required
def index():
    """List the current user's notifications with filters."""
    user = current_user()
    status = (request.args.get("status") or "all").strip()
    category = (request.args.get("category") or "").strip()
    search = (request.args.get("q") or "").strip()

    is_read = {"unread": False, "read": True}.get(status)
    notifications = notification_service.list_for_user(
        user,
        is_read=is_read,
        category=category or None,
        search=search or None,
    )
    return render_template(
        "notifications/index.html",
        notifications=notifications,
        summary=notification_service.status_counts(user),
        categories=ALL_CATEGORIES,
        category_labels=CATEGORY_LABELS,
        category_badges=CATEGORY_BADGES,
        status=status,
        category=category,
        search=search,
    )


@bp.post("/<int:notification_id>/read")
@login_required
def mark_read(notification_id):
    """Mark one of the current user's notifications as read."""
    notification = _owned(notification_service.get_notification(notification_id))
    notification_service.mark_read(notification)
    flash("Notification marked as read.", "success")
    return redirect(url_for("notifications.index"))


@bp.post("/<int:notification_id>/unread")
@login_required
def mark_unread(notification_id):
    """Mark one of the current user's notifications as unread."""
    notification = _owned(notification_service.get_notification(notification_id))
    notification_service.mark_unread(notification)
    flash("Notification marked as unread.", "info")
    return redirect(url_for("notifications.index"))


@bp.post("/read-all")
@login_required
def mark_all_read():
    """Mark every unread notification for the current user as read."""
    count = notification_service.mark_all_read(current_user())
    if count:
        flash(f"Marked {count} notification(s) as read.", "success")
    else:
        flash("No unread notifications.", "info")
    return redirect(url_for("notifications.index"))


@bp.post("/scan")
@login_required
def scan():
    """Generate notifications from stored data (deterministic, in-app)."""
    created = notification_service.generate_for_user(current_user())
    flash(
        f"Notification scan complete: {created['total']} new notification(s).",
        "success",
    )
    return redirect(url_for("notifications.index"))


__all__ = ["bp"]
