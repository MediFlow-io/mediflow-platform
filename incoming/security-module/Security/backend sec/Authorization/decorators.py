"""Authorization decorators for Flask routes.

Example:
    >>> @app.route('/appointments', methods=['POST'])
    ... @require_auth
    ... @require_permission(Permission.APPOINTMENT_CREATE)
    ... def create_appointment():
    ...     return jsonify({"status": "ok"})
    >>> @app.route('/records/<int:record_id>')
    ... @require_auth
    ... @require_owner(lambda: Record.query.get_or_404(record_id))
    ... def view_record(record_id):
    ...     return jsonify({"status": "ok"})
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import g, jsonify, request

from security.authorization.rbac import Permission, Role, has_permission
from security.middleware.audit_logger import log_security_event


LOGGER = logging.getLogger(__name__)


def _deny_response(message: str, status_code: int):
    """Return a consistent JSON denial payload without exposing internal details."""
    return jsonify({"error": message}), status_code


def _audit_denial(event: str, *, user_id: str | None = None, path: str | None = None, reason: str = "denied") -> None:
    """Write an audit record for authorization denials."""
    log_security_event(
        event_name=event,
        user_id=user_id,
        path=path,
        detail={"reason": reason},
    )


def require_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    """Ensure a valid authenticated user is present before the route runs."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        user = getattr(g, "current_user", None)
        if user is None:
            _audit_denial("authorization_denied", path=request.path, reason="unauthenticated")
            return _deny_response("Authentication required.", 401)
        return func(*args, **kwargs)

    return wrapper


def require_role(*roles: Role) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require the authenticated user to have one of the listed roles."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            user = getattr(g, "current_user", None)
            if user is None:
                _audit_denial("authorization_denied", path=request.path, reason="unauthenticated")
                return _deny_response("Authentication required.", 401)

            user_role = getattr(user, "role", None)
            if user_role not in roles:
                _audit_denial(
                    "authorization_denied",
                    user_id=getattr(user, "id", None),
                    path=request.path,
                    reason=f"missing_role:{[role.value for role in roles]}",
                )
                return _deny_response("Forbidden.", 403)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_permission(permission: Permission) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require the authenticated user to hold the named permission."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            user = getattr(g, "current_user", None)
            if user is None:
                _audit_denial("authorization_denied", path=request.path, reason="unauthenticated")
                return _deny_response("Authentication required.", 401)

            user_role = getattr(user, "role", None)
            if not isinstance(user_role, Role):
                _audit_denial(
                    "authorization_denied",
                    user_id=getattr(user, "id", None),
                    path=request.path,
                    reason=f"invalid_role:{user_role}",
                )
                return _deny_response("Forbidden.", 403)

            if not has_permission(user_role, permission):
                _audit_denial(
                    "authorization_denied",
                    user_id=getattr(user, "id", None),
                    path=request.path,
                    reason=f"missing_permission:{permission.value}",
                )
                return _deny_response("Forbidden.", 403)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_owner(resource_getter: Callable[..., Any]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require the user to own the target resource before access is permitted."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            user = getattr(g, "current_user", None)
            if user is None:
                _audit_denial("authorization_denied", path=request.path, reason="unauthenticated")
                return _deny_response("Authentication required.", 401)

            resource = resource_getter(*args, **kwargs)
            if resource is None:
                _audit_denial(
                    "authorization_denied",
                    user_id=getattr(user, "id", None),
                    path=request.path,
                    reason="resource_not_found",
                )
                return _deny_response("Not found.", 404)

            owner_id = getattr(resource, "user_id", None)
            current_user_id = getattr(user, "id", None)
            if owner_id != current_user_id:
                _audit_denial(
                    "authorization_denied",
                    user_id=current_user_id,
                    path=request.path,
                    reason="ownership_mismatch",
                )
                return _deny_response("Forbidden.", 403)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def rate_limit(limit: str, key: str = "ip") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wrap a Flask route with a Flask-Limiter rate limit policy."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            try:
                from flask_limiter import Limiter
                from flask_limiter.util import get_remote_address
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("Flask-Limiter must be installed to use rate_limit") from exc

            limiter = getattr(request, "limiter", None)
            if limiter is None:
                limiter = Limiter(
                    key_func=get_remote_address if key == "ip" else lambda: key,
                    default_limits=[]
                )

            return limiter.limit(limit)(func)(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "require_auth",
    "require_role",
    "require_permission",
    "require_owner",
    "rate_limit",
]
