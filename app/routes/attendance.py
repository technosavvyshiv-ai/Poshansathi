"""Child attendance routes (Phase 8).

The phase covers the plan's attendance module:

* a per-centre **daily register** (record or update a whole day in one screen);
* a single-child attendance **history** with monthly summaries;
* a filterable **attendance history** across a centre;
* a **frequent absence** view for follow-up.

Write access is limited to ADMIN and AWW; every authenticated role may read,
but an AWW only sees their own centre.
"""

from __future__ import annotations

from datetime import date, datetime

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
from app.models import AnganwadiCentre, Child
from app.services import attendance_service
from app.utils.constants import AttendanceStatus, UserRole
from app.utils.decorators import login_required, role_required
from app.utils.helpers import current_user, ensure_beneficiary_access, scope_centre_id
from app.utils.validators import ValidationError

bp = Blueprint("attendance", __name__)

READ_ROLES = (
    UserRole.ADMIN,
    UserRole.AWW,
    UserRole.SUPERVISOR,
    UserRole.OFFICER,
)
WRITE_ROLES = (UserRole.ADMIN, UserRole.AWW)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _active_centres():
    """Return active centres ordered by name (for filter/dropdown use)."""
    return (
        AnganwadiCentre.query.filter_by(is_active=True)
        .order_by(AnganwadiCentre.name.asc())
        .all()
    )


def _query_date(value, default=None):
    """Parse a ``YYYY-MM-DD`` query value, falling back to ``default``."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default or date.today()


def _optional_date(value):
    """Parse a ``YYYY-MM-DD`` filter value, or ``None`` when blank/invalid."""
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _query_month(value, default=None):
    """Parse a ``YYYY-MM`` query value into ``(year, month)``."""
    try:
        parsed = datetime.strptime(value, "%Y-%m")
        return parsed.year, parsed.month
    except (TypeError, ValueError):
        fallback = default or date.today()
        return fallback.year, fallback.month


def _int_arg(value):
    """Return ``value`` as an int when it is a positive integer, else ``None``."""
    raw = (value or "").strip()
    return int(raw) if raw.isdigit() else None


def _get_child(child_id: int) -> Child:
    """Load a child and enforce centre access for the current user."""
    child = db.get_or_404(Child, child_id)
    ensure_beneficiary_access(current_user(), child.beneficiary)
    return child


def _resolve_centre(user, raw):
    """Return the centre a user is allowed to work with for ``raw`` id.

    An AWW is always pinned to their own centre; other roles use the supplied
    id (falling back to the first active centre).
    """
    scope = scope_centre_id(user)
    if scope is not None:
        return db.session.get(AnganwadiCentre, scope)

    centre_id = _int_arg(raw)
    if centre_id is not None:
        return db.session.get(AnganwadiCentre, centre_id)

    centres = _active_centres()
    return centres[0] if centres else None


# ---------------------------------------------------------------------------
# Daily register
# ---------------------------------------------------------------------------
@bp.get("/attendance/")
@login_required
@role_required(*READ_ROLES)
def index():
    """Show the daily register for a centre and date, with a summary."""
    user = current_user()
    scope = scope_centre_id(user)
    centre = _resolve_centre(user, request.args.get("centre"))
    on_date = _query_date(request.args.get("date"))

    register = attendance_service.daily_register(centre.id, on_date) if centre else []
    summary = (
        attendance_service.daily_summary(centre.id, on_date)
        if centre
        else {"present": 0, "absent": 0, "total": 0, "attendance_percentage": None}
    )

    return render_template(
        "attendance/index.html",
        centre=centre,
        on_date=on_date,
        register=register,
        summary=summary,
        centres=_active_centres(),
        scope_centre_id=scope,
        can_write=user.role in WRITE_ROLES,
        AttendanceStatus=AttendanceStatus,
    )


@bp.post("/attendance/daily")
@login_required
@role_required(*WRITE_ROLES)
def daily_mark():
    """Record or update a whole day's attendance for one centre."""
    user = current_user()
    centre = _resolve_centre(user, request.form.get("centre_id"))
    if centre is None:
        abort(400)

    date_raw = (request.form.get("attendance_date") or "").strip()
    on_date = None
    if date_raw:
        try:
            on_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        except ValueError:
            on_date = None
    if date_raw and on_date is None:
        flash("Please provide a valid attendance date.", "danger")
        return redirect(url_for("attendance.index", centre=centre.id))
    if on_date is None:
        on_date = date.today()

    entries = []
    for child in attendance_service.children_for_centre(centre.id):
        entries.append(
            {
                "child": child,
                "status_raw": request.form.get(f"status_{child.id}"),
                "note": request.form.get(f"note_{child.id}"),
            }
        )

    result = attendance_service.mark_daily_attendance(
        centre, on_date, entries, recorded_by=user
    )

    if result["created"] or result["updated"]:
        flash(
            f"Attendance saved for {centre.name} on "
            f"{on_date.strftime('%d %b %Y')} "
            f"({result['created']} new, {result['updated']} updated).",
            "success",
        )
    else:
        flash("No attendance changes were submitted.", "info")

    return redirect(
        url_for("attendance.index", centre=centre.id, date=on_date.isoformat())
    )


# ---------------------------------------------------------------------------
# Attendance history
# ---------------------------------------------------------------------------
@bp.get("/attendance/history")
@login_required
@role_required(*READ_ROLES)
def history():
    """Show a filterable list of attendance records with a summary."""
    user = current_user()
    scope = scope_centre_id(user)

    centre_raw = (request.args.get("centre") or "").strip()
    status_raw = (request.args.get("status") or "").strip()
    child_id = _int_arg(request.args.get("child"))
    start_raw = (request.args.get("start") or "").strip()
    end_raw = (request.args.get("end") or "").strip()

    centre_id = scope if scope is not None else _int_arg(centre_raw)
    status = None
    if status_raw in (AttendanceStatus.PRESENT.value, AttendanceStatus.ABSENT.value):
        status = AttendanceStatus(status_raw)
    start_date = _optional_date(start_raw)
    end_date = _optional_date(end_raw)

    rows = attendance_service.attendance_query(
        centre_id=centre_id,
        child_id=child_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )
    summary = attendance_service.summary_for_scope(
        centre_id=centre_id, child_id=child_id,
        start_date=start_date, end_date=end_date,
    )
    return render_template(
        "attendance/history.html",
        records=[attendance_service.serialize_record(row) for row in rows],
        summary=summary,
        centres=_active_centres(),
        centre_raw=centre_raw,
        status_raw=status_raw,
        child_raw=(request.args.get("child") or "").strip(),
        start_raw=start_raw,
        end_raw=end_raw,
        scope_centre_id=scope,
        can_write=user.role in WRITE_ROLES,
    )


# ---------------------------------------------------------------------------
# Frequent absences
# ---------------------------------------------------------------------------
@bp.get("/attendance/frequent-absences")
@login_required
@role_required(*READ_ROLES)
def frequent_absences():
    """Show the children with the most absences for a centre and month."""
    user = current_user()
    scope = scope_centre_id(user)
    centre = _resolve_centre(user, request.args.get("centre"))
    year, month = _query_month(request.args.get("month"))

    rows = attendance_service.frequent_absences(
        centre_id=centre.id if centre else None, year=year, month=month, limit=25
    )
    return render_template(
        "attendance/frequent_absences.html",
        rows=rows,
        centre=centre,
        year=year,
        month=month,
        month_value=f"{year:04d}-{month:02d}",
        centres=_active_centres(),
        scope_centre_id=scope,
    )


# ---------------------------------------------------------------------------
# Per-child attendance
# ---------------------------------------------------------------------------
@bp.get("/children/<int:child_id>/attendance")
@login_required
@role_required(*READ_ROLES)
def child_history(child_id):
    """Show a child's attendance history and monthly summary."""
    child = _get_child(child_id)
    year, month = _query_month(request.args.get("month"))
    return render_template(
        "attendance/child_history.html",
        child=child,
        beneficiary=child.beneficiary,
        history=attendance_service.build_history(child),
        summary=attendance_service.child_summary(child),
        monthly=attendance_service.monthly_summary(child, year, month),
        recent_months=attendance_service.recent_monthly_summaries(child, months=6),
        month_value=f"{year:04d}-{month:02d}",
        can_write=current_user().role in WRITE_ROLES,
    )


@bp.route("/children/<int:child_id>/attendance/new", methods=["GET", "POST"])
@login_required
@role_required(*WRITE_ROLES)
def create(child_id):
    """Record a single attendance entry for a child."""
    child = _get_child(child_id)
    errors: dict[str, str] = {}

    if request.method == "POST":
        try:
            attendance_service.record_attendance(
                child, request.form, recorded_by=current_user()
            )
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash("Attendance recorded.", "success")
            return redirect(url_for("attendance.child_history", child_id=child.id))
        form = request.form
    else:
        form = {"attendance_date": date.today().isoformat(), "status": "PRESENT"}

    return (
        render_template(
            "attendance/form.html",
            mode="create",
            child=child,
            beneficiary=child.beneficiary,
            record=None,
            form=form,
            errors=errors,
        ),
        400 if errors else 200,
    )


@bp.route(
    "/children/<int:child_id>/attendance/<int:record_id>/edit",
    methods=["GET", "POST"],
)
@login_required
@role_required(*WRITE_ROLES)
def edit(child_id, record_id):
    """Edit an existing attendance entry for a child."""
    child = _get_child(child_id)
    record = attendance_service.get_record(child, record_id)
    errors: dict[str, str] = {}

    if request.method == "POST":
        try:
            attendance_service.update_attendance(
                child, record, request.form, recorded_by=current_user()
            )
        except ValidationError as exc:
            errors = exc.errors
            flash("Please correct the highlighted fields.", "danger")
        else:
            flash("Attendance updated.", "success")
            return redirect(url_for("attendance.child_history", child_id=child.id))
        form = request.form
    else:
        form = {
            "attendance_date": record.attendance_date.isoformat(),
            "status": record.status.value if record.status else "PRESENT",
            "note": record.note or "",
        }

    return (
        render_template(
            "attendance/form.html",
            mode="edit",
            child=child,
            beneficiary=child.beneficiary,
            record=record,
            form=form,
            errors=errors,
        ),
        400 if errors else 200,
    )


__all__ = ["bp"]
