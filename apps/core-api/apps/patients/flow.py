"""Visit lifecycle: the only way a visit's status changes.

waiting ──call──▶ called ──start──▶ in_progress ──complete──▶ completed
   │                 │                   │
   └──────start──────┘                   │
   └─────────────cancel──────────────────┴──▶ cancelled
"""
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User

from .models import Visit

Role, Status = User.Role, Visit.Status
FRONT_DESK = frozenset({Role.ADMIN, Role.DOCTOR, Role.NURSE, Role.RECEPTION})
CLINICAL = frozenset({Role.ADMIN, Role.DOCTOR, Role.NURSE})


@dataclass(frozen=True)
class Transition:
    sources: frozenset
    target: str
    roles: frozenset
    timestamp: str | None  # Visit field stamped when the transition happens


TRANSITIONS = {
    "call": Transition(frozenset({Status.WAITING}), Status.CALLED, FRONT_DESK, "called_at"),
    "start": Transition(frozenset({Status.WAITING, Status.CALLED}), Status.IN_PROGRESS, CLINICAL, "started_at"),
    "complete": Transition(frozenset({Status.IN_PROGRESS}), Status.COMPLETED, CLINICAL, "completed_at"),
    "cancel": Transition(frozenset(Visit.ACTIVE_STATUSES), Status.CANCELLED, FRONT_DESK, "completed_at"),
}


class TransitionError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def apply_transition(visit_id: int, action: str, user) -> Visit:
    """Move a visit to its next status atomically. Raises TransitionError on any refusal."""
    transition = TRANSITIONS[action]
    if user.role not in transition.roles:
        raise TransitionError(f"Your role cannot {action} a visit.", 403)
    with transaction.atomic():
        # Row lock: two staff clicking "call" at once cannot both succeed.
        visit = Visit.objects.select_for_update().get(pk=visit_id)
        if visit.status not in transition.sources:
            raise TransitionError(f"Cannot {action} a visit that is {visit.get_status_display().lower()}.", 409)
        visit.status = transition.target
        update = ["status"]
        if transition.timestamp:
            setattr(visit, transition.timestamp, timezone.now())
            update.append(transition.timestamp)
        if action == "start" and visit.assigned_clinician_id is None:
            visit.assigned_clinician = user
            update.append("assigned_clinician")
        visit.save(update_fields=update)
    return visit
