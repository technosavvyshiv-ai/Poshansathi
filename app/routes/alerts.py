"""Alert routes (Phase 9).

Exposes the centralized, deterministic alert engine and its manual lifecycle:

* list / filter alerts and view an alert with its related follow-ups;
* run the explicit rule scan (``/alerts/scan``);
* assign an alert;
* change status (open / in progress / resolved / dismissed) and reopen.

Read access is available to every authenticated role; manual lifecycle changes
are limited to ADMIN, AWW and SUPERVISOR.  An AWW only sees alerts for their
own centre's beneficiaries (and their centre's low-stock alerts).
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

from app.extensions import db
from app.models import AnganwadiCentre, User
from app.services import alert_service, visit_service
from app.utils import alert_rules
from app.utils.constants import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    UserRole,
)
from app.utils.decorators import login_required, role_required
from app.utils.helpers import current_user, ensure_beneficiary_access, scope_centre_id
from app.utils.validators import ValidationError

bp = Blueprint("alerts", __name__, url_prefix="/alerts")

READ_ROLES = (
    UserRole.ADMIN,
    UserRole.AWW,
    UserRole.SUPERVISOR,
    UserRole.OFFICER,
)
MANAGE_ROLES = (UserRole.ADMIN, UserRole.AWW, UserRole.SUPERVISOR)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ensure_alert_access(alert) -> None:
    """Abort 403 when an AWW requests an alert outside their centre."""
    user = current_user()
    scope = scope_centre_id(user)
    if scope is None:
        return
    if alert.beneficiary is not None:
        ensure_beneficiary_access(user, alert.beneficiary)
        return
    if f"[inventory:{scope}:" in (alert.message or ""):
        return
    abort(403)


def _enum_arg(raw, enum_cls):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return enum_cls(raw)
    except ValueError:
        return None


def _parse_statuses(value):
    mapping = {
        "active": alert_service.ACTIVE_STATUSES,
        "open": (AlertStatus.OPEN,),
        "in_progress": (AlertStatus.IN_PROGRESS,),
        "resolved": (AlertStatus.RESOLVED,),
        "dismissed": (AlertStatus.DISMISSED,),
        "all": None,
    }
    return mapping.get(value, alert_service.ACTIVE_STATUSES)


def _flash_validation(exc: ValidationError) -> None:
    flash(next(iter(exc.errors.values())), "danger")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@bp.get("/")
@login_required
@role_required(*READ_ROLES)
def index():
    """Show a filterable alert list, defaulting to active alerts."""
    user = current_user()
    scope = scope_centre_id(user)

    status_filter = (request.args.get("status") or "active").strip()
    alert_type = _enum_arg(request.args.get("type"), AlertType)
    severity = _enum_arg(request.args.get("severity"), AlertSeverity)
    assigned_raw = (request.args.get("assigned") or "").strip()
    beneficiary_raw = (request.args.get("beneficiary") or "").strip()
    search = (request.args.get("q") or "").strip()

    alerts = alert_service.list_alerts(
        scope_centre_id=scope,
        statuses=_parse_statuses(status_filter),
        alert_type=alert_type,
        severity=severity,
        assigned_to_id=int(assigned_raw) if assigned_raw.isdigit() else None,
        beneficiary_id=(
            int(beneficiary_raw) if beneficiary_raw.isdigit() else None
        ),
        search=search,
    )

    return render_template(
        "alerts/index.html",
        alerts=alerts,
        summary=alert_service.status_counts(scope_centre_id=scope),
        status_filter=status_filter,
        type_raw=(request.args.get("type") or "").strip(),
        severity_raw=(request.args.get("severity") or "").strip(),
        assigned_raw=assigned_raw,
        beneficiary_raw=beneficiary_raw,
        search=search,
        assignees=alert_service.assignable_users(scope_centre_id=scope),
        rule_labels=alert_rules.RULE_LABELS,
        scope_centre_id=scope,
        can_manage=user.role in MANAGE_ROLES,
        can_scan=user.role in MANAGE_ROLES,
        AlertStatus=AlertStatus,
        AlertType=AlertType,
        AlertSeverity=AlertSeverity,
    )


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------
@bp.get("/<int:alert_id>")
@login_required
@role_required(*READ_ROLES)
def detail(alert_id):
    """Show one alert with its beneficiary's visits and interventions."""
    user = current_user()
    scope = scope_centre_id(user)
    alert = alert_service.get_alert(alert_id)
    _ensure_alert_access(alert)

    beneficiary = alert.beneficiary
    return render_template(
        "alerts/detail.html",
        alert=alert,
        beneficiary=beneficiary,
        child=alert.child,
        visits=(
            visit_service.visits_for_beneficiary(beneficiary)
            if beneficiary
            else []
        ),
        interventions=(
            visit_service.interventions_for_beneficiary(beneficiary)
            if beneficiary
            else []
        ),
        assignees=alert_service.assignable_users(scope_centre_id=scope),
        allowed_statuses=alert_service.VALID_TRANSITIONS.get(alert.status, set()),
        rule_labels=alert_rules.RULE_LABELS,
        can_manage=user.role in MANAGE_ROLES,
        AlertStatus=AlertStatus,
        AlertType=AlertType,
    )


# ---------------------------------------------------------------------------
# Manual lifecycle
# ---------------------------------------------------------------------------
@bp.post("/<int:alert_id>/assign")
@login_required
@role_required(*MANAGE_ROLES)
def assign(alert_id):
    """Assign or reassign an alert."""
    alert = alert_service.get_alert(alert_id)
    _ensure_alert_access(alert)

    raw = (request.form.get("assigned_to_id") or "").strip()
    user = db.session.get(User, int(raw)) if raw.isdigit() else None
    if user is None or not user.is_active:
        flash("Please select a valid assignee.", "danger")
        return redirect(url_for("alerts.detail", alert_id=alert.id))

    try:
        alert_service.assign_alert(alert, user, actor=current_user())
    except ValidationError as exc:
        _flash_validation(exc)
    else:
        flash(f"Alert assigned to {user.full_name}.", "success")
    return redirect(url_for("alerts.detail", alert_id=alert.id))


@bp.post("/<int:alert_id>/status")
@login_required
@role_required(*MANAGE_ROLES)
def update_status(alert_id):
    """Apply an explicit status change."""
    alert = alert_service.get_alert(alert_id)
    _ensure_alert_access(alert)

    notes = (request.form.get("resolution_notes") or "").strip() or None
    try:
        alert_service.set_alert_status(
            alert, request.form.get("status"), notes=notes, actor=current_user()
        )
    except ValidationError as exc:
        _flash_validation(exc)
    else:
        flash("Alert status updated.", "success")
    return redirect(url_for("alerts.detail", alert_id=alert.id))


@bp.post("/<int:alert_id>/resolve")
@login_required
@role_required(*MANAGE_ROLES)
def resolve(alert_id):
    """Resolve an alert."""
    alert = alert_service.get_alert(alert_id)
    _ensure_alert_access(alert)
    notes = (request.form.get("resolution_notes") or "").strip() or None
    try:
        alert_service.resolve_alert(alert, notes=notes, actor=current_user())
    except ValidationError as exc:
        _flash_validation(exc)
    else:
        flash("Alert resolved.", "success")
    return redirect(url_for("alerts.detail", alert_id=alert.id))


@bp.post("/<int:alert_id>/dismiss")
@login_required
@role_required(*MANAGE_ROLES)
def dismiss(alert_id):
    """Dismiss an alert."""
    alert = alert_service.get_alert(alert_id)
    _ensure_alert_access(alert)
    notes = (request.form.get("resolution_notes") or "").strip() or None
    try:
        alert_service.dismiss_alert(alert, notes=notes, actor=current_user())
    except ValidationError as exc:
        _flash_validation(exc)
    else:
        flash("Alert dismissed.", "info")
    return redirect(url_for("alerts.detail", alert_id=alert.id))


@bp.post("/<int:alert_id>/reopen")
@login_required
@role_required(*MANAGE_ROLES)
def reopen(alert_id):
    """Reopen a resolved/dismissed alert."""
    alert = alert_service.get_alert(alert_id)
    _ensure_alert_access(alert)
    try:
        alert_service.reopen_alert(alert, actor=current_user())
    except ValidationError as exc:
        _flash_validation(exc)
    else:
        flash("Alert reopened.", "warning")
    return redirect(url_for("alerts.detail", alert_id=alert.id))


# ---------------------------------------------------------------------------
# Deterministic rule scan
# ---------------------------------------------------------------------------
@bp.post("/scan")
@login_required
@role_required(*MANAGE_ROLES)
def scan():
    """Run the explicit deterministic rules over stored data."""
    user = current_user()
    scope = scope_centre_id(user)

    centre = None
    if scope is not None:
        centre = db.session.get(AnganwadiCentre, scope)
    else:
        raw = (request.form.get("centre_id") or "").strip()
        if raw.isdigit():
            centre = db.session.get(AnganwadiCentre, int(raw))

    result = alert_service.evaluate_all(centre=centre, actor=user)
    flash(
        "Rule scan complete: evaluated "
        f"{result['beneficiaries']} beneficiaries; "
        f"{result['active_alerts']} active alert(s).",
        "success",
    )
    return redirect(url_for("alerts.index"))


__all__ = ["bp"]