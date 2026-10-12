from .models import AuditLog


def record(actor, action: str, entity_type: str, entity_id="", **details) -> None:
    """Append an audit entry. Never pass passwords, tokens, or clinical free text in details."""
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    AuditLog.objects.create(actor=actor, action=action, entity_type=entity_type,
                            entity_id=str(entity_id), details=details)
