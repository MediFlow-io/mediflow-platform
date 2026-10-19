"""Aggregate flow numbers for the AI insights endpoint. Counts and averages only: no patient data."""
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from apps.clinic.models import QueueSettings
from apps.patients.models import Department, Visit

PERIOD_DAYS = 14


def _minutes(start, end):
    return (end - start).total_seconds() / 60 if start and end and end >= start else None


def _avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def flow_numbers() -> dict:
    now = timezone.now()
    settings = QueueSettings.load()
    targets = {1: settings.esi1_target_minutes, 2: settings.esi2_target_minutes, 3: settings.esi3_target_minutes,
               4: settings.esi4_target_minutes, 5: settings.esi5_target_minutes}
    visits = (Visit.objects.filter(checked_in_at__gte=now - timedelta(days=PERIOD_DAYS))
              .select_related("department").only("department__name", "esi", "status", "checked_in_at", "called_at",
                                                  "started_at", "completed_at"))
    per_dept = defaultdict(lambda: {"check_ins": 0, "waits": [], "calls": [], "consults": [], "in_target": 0, "seen": 0})
    per_hour = defaultdict(lambda: {"check_ins": 0, "waits": []})
    for v in visits:
        d = per_dept[v.department.name]
        d["check_ins"] += 1
        seen = v.called_at or v.started_at
        wait = _minutes(v.checked_in_at, seen)
        d["waits"].append(wait)
        if wait is not None:
            d["seen"] += 1
            d["in_target"] += wait <= targets.get(v.esi, 0)
        d["calls"].append(_minutes(v.called_at, v.started_at))
        if v.status == Visit.Status.COMPLETED:
            d["consults"].append(_minutes(v.started_at, v.completed_at))
        h = per_hour[timezone.localtime(v.checked_in_at).hour]
        h["check_ins"] += 1
        h["waits"].append(wait)

    active = Visit.objects.filter(status__in=[Visit.Status.WAITING, Visit.Status.IN_PROGRESS]).values_list("department__name", "status")
    waiting, consulting = defaultdict(int), defaultdict(int)
    for name, status in active:
        (waiting if status == Visit.Status.WAITING else consulting)[name] += 1

    departments = []
    for dept in Department.objects.filter(active=True).order_by("name"):
        d = per_dept[dept.name]
        departments.append({
            "name": dept.name, "check_ins": d["check_ins"], "waiting_now": waiting[dept.name],
            "clinicians_now": max(1, consulting[dept.name]),
            "avg_wait_minutes": _avg(d["waits"]), "avg_call_to_start_minutes": _avg(d["calls"]),
            "avg_consult_minutes": _avg(d["consults"]),
            "seen_within_target_percent": round(100 * d["in_target"] / d["seen"], 1) if d["seen"] else None,
        })
    service = {name: [round(m, 1) for m in d["consults"] if m is not None][-200:] for name, d in per_dept.items()}
    hours = [{"hour": hour, "check_ins": h["check_ins"], "avg_wait_minutes": _avg(h["waits"])} for hour, h in sorted(per_hour.items())]
    # The AI service's schemas don't take clinicians_now for bottlenecks.
    bottleneck_departments = [{k: v for k, v in d.items() if k != "clinicians_now"} for d in departments]
    return {"period_days": PERIOD_DAYS, "generated_at": now.isoformat(), "departments": departments,
            "bottleneck_departments": bottleneck_departments, "hours": hours, "service_minutes": service}
