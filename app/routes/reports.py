"""Report routes (Phase 12).

Printable HTML reports with optional CSV export (``?format=csv``):

* child profile / growth / vaccination;
* maternal health;
* nutrition distribution;
* monthly centre;
* scheme.

Every value comes from the existing Phase 4–11 services.  Filters are read from
the query string.  Read access is open to every authenticated role; an AWW is
scoped to their own centre.
"""

from __future__ import annotations

from datetime import date, datetime

from flask import (
    Blueprint,
    Response,
    abort,
    redirect,
    render_template,
    request,
    url_for,
)

from app.extensions import db
from app.models import AnganwadiCentre, Beneficiary, Mother
from app.services import (
    nutrition_service,
    report_service,
    scheme_service,
)
from app.utils.constants import SchemeStatus, UserRole
from app.utils.decorators import login_required, role_required
from app.utils.helpers import current_user, ensure_beneficiary_access, scope_centre_id

bp = Blueprint("reports", __name__, url_prefix="/reports")

READ_ROLES = (
    UserRole.ADMIN,
    UserRole.AWW,
    UserRole.SUPERVISOR,
    UserRole.OFFICER,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _scope():
    return scope_centre_id(current_user())


def _parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _month_arg(value):
    value = (value or "").strip()
    try:
        parsed = datetime.strptime(value, "%Y-%m")
        return parsed.year, parsed.month
    except ValueError:
        today = date.today()
        return today.year, today.month


def _centre_arg(raw, scope):
    """Resolve a centre filter, honouring AWW scoping."""
    if scope is not None:
        return scope
    raw = (raw or "").strip()
    return int(raw) if raw.isdigit() else None


def _csv_response(filename: str, text: str) -> Response:
    return Response(
        text,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _wants_csv() -> bool:
    return (request.args.get("format") or "").lower() == "csv"


def _get_beneficiary(beneficiary_id: int) -> Beneficiary:
    beneficiary = db.get_or_404(Beneficiary, beneficiary_id)
    ensure_beneficiary_access(current_user(), beneficiary)
    return beneficiary


# ---------------------------------------------------------------------------
# Hub
# ---------------------------------------------------------------------------
@bp.get("/")
@login_required
@role_required(*READ_ROLES)
def index():
    """List the available reports and their filters."""
    user = current_user()
    scope = _scope()
    centres = nutrition_service.active_centres()
    if scope is not None:
        centres = [centre for centre in centres if centre.id == scope]
    return render_template(
        "reports/index.html",
        centres=centres,
        scope_centre_id=scope,
        items=nutrition_service.active_items(),
        schemes=scheme_service.active_schemes(),
        scheme_statuses=list(SchemeStatus),
        today=date.today(),
        can_write=user.role in (UserRole.ADMIN, UserRole.AWW),
    )


# ---------------------------------------------------------------------------
# Child profile
# ---------------------------------------------------------------------------
@bp.get("/beneficiary")
@login_required
@role_required(*READ_ROLES)
def beneficiary_lookup():
    """Redirect a numeric beneficiary lookup to their profile report."""
    raw = (request.args.get("beneficiary") or "").strip()
    if not raw.isdigit():
        abort(400)
    return redirect(
        url_for("reports.child_profile", beneficiary_id=int(raw))
    )


@bp.get("/child/<int:beneficiary_id>")
@login_required
@role_required(*READ_ROLES)
def child_profile(beneficiary_id):
    """Child (or mother) profile report."""
    beneficiary = _get_beneficiary(beneficiary_id)
    report = report_service.child_profile_report(beneficiary)
    if _wants_csv():
        return _csv_response(
            f"child_profile_{beneficiary.id}.csv",
            report_service.child_profile_csv(report),
        )
    return render_template("reports/child_profile.html", report=report)


# ---------------------------------------------------------------------------
# Growth
# ---------------------------------------------------------------------------
@bp.get("/child/<int:beneficiary_id>/growth")
@login_required
@role_required(*READ_ROLES)
def growth(beneficiary_id):
    """Child growth report with an optional measurement-date range."""
    beneficiary = _get_beneficiary(beneficiary_id)
    if beneficiary.child is None:
        abort(404)
    start = _parse_date(request.args.get("start"))
    end = _parse_date(request.args.get("end"))
    report = report_service.growth_report(beneficiary.child, start=start, end=end)
    if _wants_csv():
        return _csv_response(
            f"growth_{beneficiary.id}.csv", report_service.growth_csv(report)
        )
    return render_template(
        "reports/growth.html",
        report=report,
        beneficiary=beneficiary,
        start_raw=(request.args.get("start") or "").strip(),
        end_raw=(request.args.get("end") or "").strip(),
    )


# ---------------------------------------------------------------------------
# Vaccination
# ---------------------------------------------------------------------------
@bp.get("/child/<int:beneficiary_id>/vaccination")
@login_required
@role_required(*READ_ROLES)
def vaccination(beneficiary_id):
    """Child vaccination report with status/date filters."""
    beneficiary = _get_beneficiary(beneficiary_id)
    if beneficiary.child is None:
        abort(404)
    status = (request.args.get("status") or "").strip() or None
    start = _parse_date(request.args.get("start"))
    end = _parse_date(request.args.get("end"))
    report = report_service.vaccination_report(
        beneficiary.child, status=status, start=start, end=end
    )
    if _wants_csv():
        return _csv_response(
            f"vaccination_{beneficiary.id}.csv",
            report_service.vaccination_csv(report),
        )
    return render_template(
        "reports/vaccination.html",
        report=report,
        beneficiary=beneficiary,
        status_raw=status or "",
        start_raw=(request.args.get("start") or "").strip(),
        end_raw=(request.args.get("end") or "").strip(),
        statuses=["COMPLETED", "MISSED", "OVERDUE", "DUE", "UPCOMING"],
    )


# ---------------------------------------------------------------------------
# Maternal health
# ---------------------------------------------------------------------------
@bp.get("/mother/<int:mother_id>/maternal")
@login_required
@role_required(*READ_ROLES)
def maternal(mother_id):
    """Maternal (ANC) health report."""
    mother = db.get_or_404(Mother, mother_id)
    ensure_beneficiary_access(current_user(), mother.beneficiary)
    start = _parse_date(request.args.get("start"))
    end = _parse_date(request.args.get("end"))
    report = report_service.maternal_report(mother, start=start, end=end)
    if _wants_csv():
        return _csv_response(
            f"maternal_{mother.id}.csv", report_service.maternal_csv(report)
        )
    return render_template(
        "reports/maternal.html",
        report=report,
        beneficiary=mother.beneficiary,
        start_raw=(request.args.get("start") or "").strip(),
        end_raw=(request.args.get("end") or "").strip(),
    )


# ---------------------------------------------------------------------------
# Nutrition distribution
# ---------------------------------------------------------------------------
@bp.get("/nutrition")
@login_required
@role_required(*READ_ROLES)
def nutrition():
    """Nutrition distribution report with centre/item/beneficiary/date filters."""
    scope = _scope()
    centre_id = _centre_arg(request.args.get("centre"), scope)
    item_raw = (request.args.get("item") or "").strip()
    beneficiary_raw = (request.args.get("beneficiary") or "").strip()
    item_id = int(item_raw) if item_raw.isdigit() else None
    beneficiary_id = int(beneficiary_raw) if beneficiary_raw.isdigit() else None

    if beneficiary_id is not None:
        beneficiary = db.session.get(Beneficiary, beneficiary_id)
        if beneficiary is not None:
            ensure_beneficiary_access(current_user(), beneficiary)

    report = report_service.nutrition_report(
        centre_id=centre_id,
        item_id=item_id,
        beneficiary_id=beneficiary_id,
        start=_parse_date(request.args.get("start")),
        end=_parse_date(request.args.get("end")),
    )
    if _wants_csv():
        return _csv_response(
            "nutrition_distributions.csv", report_service.nutrition_csv(report)
        )
    return render_template(
        "reports/nutrition.html",
        report=report,
        centres=nutrition_service.active_centres(),
        items=nutrition_service.active_items(),
        centre_raw=(request.args.get("centre") or "").strip(),
        item_raw=item_raw,
        beneficiary_raw=beneficiary_raw,
        start_raw=(request.args.get("start") or "").strip(),
        end_raw=(request.args.get("end") or "").strip(),
        scope_centre_id=scope,
    )


@bp.get("/centre")
@login_required
@role_required(*READ_ROLES)
def centre_lookup():
    """Redirect a centre/month lookup to the monthly centre report."""
    raw = (request.args.get("centre") or "").strip()
    if not raw.isdigit():
        abort(400)
    return redirect(
        url_for(
            "reports.monthly_centre",
            centre_id=int(raw),
            month=(request.args.get("month") or "").strip(),
        )
    )


# ---------------------------------------------------------------------------
# Monthly centre
# ---------------------------------------------------------------------------
@bp.get("/centre/<int:centre_id>/monthly")
@login_required
@role_required(*READ_ROLES)
def monthly_centre(centre_id):
    """Monthly centre report (one calendar month)."""
    scope = _scope()
    if scope is not None and centre_id != scope:
        abort(403)
    centre = db.get_or_404(AnganwadiCentre, centre_id)
    year, month = _month_arg(request.args.get("month"))
    report = report_service.monthly_centre_report(centre, year, month)
    if _wants_csv():
        return _csv_response(
            f"monthly_centre_{centre_id}_{year:04d}-{month:02d}.csv",
            report_service.monthly_centre_csv(report),
        )
    return render_template(
        "reports/monthly_centre.html",
        report=report,
        centre=centre,
        month_value=f"{year:04d}-{month:02d}",
        scope_centre_id=scope,
    )


# ---------------------------------------------------------------------------
# Schemes
# ---------------------------------------------------------------------------
@bp.get("/schemes")
@login_required
@role_required(*READ_ROLES)
def schemes():
    """Scheme association report with centre/scheme/status filters."""
    scope = _scope()
    centre_id = _centre_arg(request.args.get("centre"), scope)
    scheme_raw = (request.args.get("scheme") or "").strip()
    status_raw = (request.args.get("status") or "").strip()
    scheme_id = int(scheme_raw) if scheme_raw.isdigit() else None
    status = None
    if status_raw in {item.value for item in SchemeStatus}:
        status = SchemeStatus(status_raw)

    report = report_service.scheme_report(
        centre_id=centre_id, scheme_id=scheme_id, status=status
    )
    if _wants_csv():
        return _csv_response(
            "scheme_report.csv", report_service.scheme_csv(report)
        )
    return render_template(
        "reports/schemes.html",
        report=report,
        centres=nutrition_service.active_centres(),
        schemes=scheme_service.active_schemes(),
        centre_raw=(request.args.get("centre") or "").strip(),
        scheme_raw=scheme_raw,
        status_raw=status_raw,
        statuses=list(SchemeStatus),
        scope_centre_id=scope,
    )


__all__ = ["bp"]
