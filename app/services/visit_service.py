"""Home visit and intervention business logic (Phase 9).

Covers the plan's home-visit workflow::

    Scheduled → Completed → Intervention Recorded → Follow-up / Resolved

* schedule / edit a home visit (beneficiary, type, assigned worker, date);
* complete or cancel a visit;
* record and edit interventions (the action taken after a visit), with an
  optional follow-up date and an optional link that resolves a related alert;
* keep the deterministic ``HOME_VISIT_PENDING`` alert in sync via
  :mod:`app.services.alert_service`.

Access control (roles and centre scoping) is enforced by the route layer.
"""

from __future__ import annotations

from datetime import datetime

from flask import abort

from app.extensions import db
from app.models import Alert, Beneficiary, HomeVisit, Intervention
from app.services import alert_service
from app.utils.constants import AlertStatus, UserRole, VisitStatus
from app.utils.helpers import scope_centre_id
from app.utils.validators import (
    ValidationError,
    validate_home_visit_fields,
    validate_intervention_fields,
    validate_visit_completion_fields,
)

#: Roles that may be assigned a home visit.  ADMIN is global (any centre);
#: AWW is centre-bound (see :func:`_validate_assigned_worker`).
WORKER_ROLES = (UserRole.AWW, UserRole.ADMIN)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def visits_query(
    *,
    scope_centre_id=None,
    centre_id=None,
    status=None,
    visit_type=None,
    assigned_worker_id=None,
    beneficiary_id=None,
    follow_up_required=None,
    start_date=None,
    end_date=None,
):
    """Return home visits with optional filters, newest scheduled first."""
    query = HomeVisit.query
    if scope_centre_id is not None:
        query = query.filter(HomeVisit.centre_id == scope_centre_id)
    elif centre_id is not None:
        query = query.filter(HomeVisit.centre_id == centre_id)
    if status is not None:
        query = query.filter(HomeVisit.status == status)
    if visit_type is not None:
        query = query.filter(HomeVisit.visit_type == visit_type)
    if assigned_worker_id is not None:
        query = query.filter(HomeVisit.assigned_worker_id == assigned_worker_id)
    if beneficiary_id is not None:
        query = query.filter(HomeVisit.beneficiary_id == beneficiary_id)
    if follow_up_required is not None:
        query = query.filter(
            HomeVisit.follow_up_required.is_(follow_up_required)
        )
    if start_date is not None:
        query = query.filter(HomeVisit.scheduled_date >= start_date)
    if end_date is not None:
        query = query.filter(HomeVisit.scheduled_date <= end_date)
    return query.order_by(
        HomeVisit.scheduled_date.desc(), HomeVisit.id.desc()
    ).all()


def visits_for_beneficiary(beneficiary) -> list[HomeVisit]:
    """Return a beneficiary's home visits, newest scheduled first."""
    return visits_query(beneficiary_id=beneficiary.id)


def interventions_for_beneficiary(beneficiary) -> list[Intervention]:
    """Return a beneficiary's interventions, newest first."""
    return (
        Intervention.query.filter_by(beneficiary_id=beneficiary.id)
        .order_by(Intervention.intervention_date.desc(), Intervention.id.desc())
        .all()
    )


def interventions_for_visit(visit) -> list[Intervention]:
    """Return the interventions recorded for a visit, newest first."""
    return (
        Intervention.query.filter_by(home_visit_id=visit.id)
        .order_by(Intervention.intervention_date.desc(), Intervention.id.desc())
        .all()
    )


def get_visit(visit_id: int) -> HomeVisit:
    """Return a home visit or raise 404."""
    visit = db.session.get(HomeVisit, visit_id)
    if visit is None:
        abort(404)
    return visit


def get_intervention(intervention_id: int) -> Intervention:
    """Return an intervention or raise 404."""
    intervention = db.session.get(Intervention, intervention_id)
    if intervention is None:
        abort(404)
    return intervention


def summary(*, scope_centre_id=None) -> dict:
    """Return deterministic visit counts for the list header."""
    visits = visits_query(scope_centre_id=scope_centre_id)
    counts = {status.value: 0 for status in VisitStatus}
    for visit in visits:
        counts[visit.status.value] += 1
    counts["TOTAL"] = len(visits)
    counts["PENDING"] = counts[VisitStatus.SCHEDULED.value]
    return counts


def open_alerts_for_beneficiary(beneficiary) -> list[Alert]:
    """Return a beneficiary's active alerts (for the intervention form)."""
    return (
        Alert.query.filter(
            Alert.beneficiary_id == beneficiary.id,
            Alert.status.in_(alert_service.ACTIVE_STATUSES),
        )
        .order_by(Alert.created_at.desc(), Alert.id.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Scheduling / editing
# ---------------------------------------------------------------------------
def _validate_assigned_worker(worker, actor) -> None:
    """Validate the worker a visit is being assigned to (defence in depth).

    Enforced server-side so crafted POST data cannot assign a visit to an
    inactive user, a non-worker role, or (for a centre-scoped AWW) a worker
    from another centre.  ADMIN assignment remains global.
    """
    if worker is None:
        raise ValidationError(
            {"assigned_worker_id": "Please select an assigned worker."}
        )
    if not worker.is_active:
        raise ValidationError(
            {"assigned_worker_id": "The selected worker is inactive."}
        )
    if worker.role not in WORKER_ROLES:
        raise ValidationError(
            {
                "assigned_worker_id": (
                    "Home visits can only be assigned to an Anganwadi worker "
                    "or an administrator."
                )
            }
        )

    scope = scope_centre_id(actor) if actor is not None else None
    if (
        scope is not None
        and worker.role == UserRole.AWW
        and worker.centre_id != scope
    ):
        raise ValidationError(
            {
                "assigned_worker_id": (
                    "You can only assign visits to workers in your own centre."
                )
            }
        )


def create_visit(beneficiary, assigned_worker, form, *, actor=None) -> HomeVisit:
    """Validate and schedule a new home visit for ``beneficiary``."""
    cleaned, errors = validate_home_visit_fields(form)
    if errors:
        raise ValidationError(errors)
    _validate_assigned_worker(assigned_worker, actor)

    visit = HomeVisit(
        beneficiary_id=beneficiary.id,
        centre_id=beneficiary.centre_id,
        visit_type=cleaned["visit_type"],
        assigned_worker=assigned_worker,
        created_by=actor,
        scheduled_date=cleaned["scheduled_date"],
        status=VisitStatus.SCHEDULED,
        visit_notes=cleaned.get("visit_notes"),
    )
    db.session.add(visit)
    alert_service.sync_home_visit_pending(beneficiary, actor=actor)
    db.session.commit()
    return visit


def update_visit(
    visit: HomeVisit, beneficiary, assigned_worker, form, *, actor=None
) -> HomeVisit:
    """Validate and update a scheduled/edited home visit."""
    cleaned, errors = validate_home_visit_fields(form)
    if errors:
        raise ValidationError(errors)
    _validate_assigned_worker(assigned_worker, actor)

    previous_beneficiary = visit.beneficiary
    visit.beneficiary_id = beneficiary.id
    visit.centre_id = beneficiary.centre_id
    visit.visit_type = cleaned["visit_type"]
    visit.assigned_worker = assigned_worker
    visit.scheduled_date = cleaned["scheduled_date"]
    visit.visit_notes = cleaned.get("visit_notes")

    if (
        previous_beneficiary is not None
        and previous_beneficiary.id != beneficiary.id
    ):
        alert_service.sync_home_visit_pending(previous_beneficiary, actor=actor)
    alert_service.sync_home_visit_pending(beneficiary, actor=actor)
    db.session.commit()
    return visit


def complete_visit(visit: HomeVisit, form, *, actor=None) -> HomeVisit:
    """Mark a visit completed and record its completion date/notes."""
    cleaned, errors = validate_visit_completion_fields(form)
    if errors:
        raise ValidationError(errors)

    visit.completed_date = cleaned["completed_date"]
    visit.status = VisitStatus.COMPLETED
    if cleaned.get("visit_notes") is not None:
        visit.visit_notes = cleaned.get("visit_notes")

    alert_service.sync_home_visit_pending(visit.beneficiary, actor=actor)
    db.session.commit()
    return visit


def cancel_visit(visit: HomeVisit, *, actor=None) -> HomeVisit:
    """Cancel a visit (it no longer counts as a pending visit)."""
    visit.status = VisitStatus.CANCELLED
    alert_service.sync_home_visit_pending(visit.beneficiary, actor=actor)
    db.session.commit()
    return visit


# ---------------------------------------------------------------------------
# Interventions
# ---------------------------------------------------------------------------
def _maybe_resolve_alert(beneficiary, alert_id, *, actor=None) -> Alert | None:
    """Resolve an optional alert referenced by an intervention (no commit)."""
    if not alert_id:
        return None

    alert = db.session.get(Alert, alert_id)
    if alert is None:
        raise ValidationError(
            {"resolve_alert_id": "Selected alert was not found."}
        )
    if alert.beneficiary_id != beneficiary.id:
        raise ValidationError(
            {
                "resolve_alert_id": (
                    "Selected alert does not belong to this beneficiary."
                )
            }
        )
    if alert.status not in alert_service.ACTIVE_STATUSES:
        raise ValidationError(
            {"resolve_alert_id": "Selected alert is already closed."}
        )

    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.utcnow()
    alert.resolution_notes = (
        f"Resolved after home visit intervention"
        f"{f' by {actor.full_name}' if actor is not None else ''}."
    )
    return alert


def record_intervention(visit: HomeVisit, form, *, actor=None) -> Intervention:
    """Validate and record an intervention for a completed visit.

    The workflow requires the visit to be ``COMPLETED`` first; this is enforced
    here (not just hidden in the UI) so crafted POSTs cannot record an
    intervention against a scheduled/cancelled visit.
    """
    if visit.status != VisitStatus.COMPLETED:
        raise ValidationError(
            {
                "visit": (
                    "Interventions can only be recorded for a completed visit."
                )
            }
        )

    cleaned, errors = validate_intervention_fields(form)
    if errors:
        raise ValidationError(errors)

    follow_up_required = cleaned["follow_up_required"]
    follow_up_date = cleaned.get("follow_up_date") if follow_up_required else None

    # Validate/resolve the optional alert first so a bad selection cannot leave
    # a partially-flushed intervention behind.
    _maybe_resolve_alert(
        visit.beneficiary, cleaned.get("resolve_alert_id"), actor=actor
    )

    intervention = Intervention(
        home_visit_id=visit.id,
        beneficiary_id=visit.beneficiary_id,
        recorded_by=actor,
        intervention_type=cleaned["intervention_type"],
        description=cleaned.get("description"),
        outcome=cleaned.get("outcome"),
        intervention_date=cleaned["intervention_date"],
        follow_up_date=follow_up_date,
    )
    db.session.add(intervention)

    visit.follow_up_required = follow_up_required
    visit.follow_up_date = follow_up_date

    alert_service.sync_home_visit_pending(visit.beneficiary, actor=actor)
    db.session.commit()
    return intervention


def update_intervention(
    intervention: Intervention, form, *, actor=None
) -> Intervention:
    """Validate and update an existing intervention."""
    cleaned, errors = validate_intervention_fields(form)
    if errors:
        raise ValidationError(errors)

    follow_up_required = cleaned["follow_up_required"]
    follow_up_date = cleaned.get("follow_up_date") if follow_up_required else None

    intervention.intervention_type = cleaned["intervention_type"]
    intervention.description = cleaned.get("description")
    intervention.outcome = cleaned.get("outcome")
    intervention.intervention_date = cleaned["intervention_date"]
    intervention.follow_up_date = follow_up_date

    if intervention.home_visit is not None:
        intervention.home_visit.follow_up_required = follow_up_required
        intervention.home_visit.follow_up_date = follow_up_date

    _maybe_resolve_alert(
        intervention.beneficiary,
        cleaned.get("resolve_alert_id"),
        actor=actor,
    )
    db.session.commit()
    return intervention


__all__ = [
    "cancel_visit",
    "complete_visit",
    "create_visit",
    "get_intervention",
    "get_visit",
    "interventions_for_beneficiary",
    "interventions_for_visit",
    "open_alerts_for_beneficiary",
    "record_intervention",
    "summary",
    "update_intervention",
    "update_visit",
    "visits_for_beneficiary",
    "visits_query",
]