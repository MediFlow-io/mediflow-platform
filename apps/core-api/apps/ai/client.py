"""HTTP client for the internal FastAPI AI service. Standard library only."""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)


class AIUnavailable(Exception):
    """The AI service could not produce an answer. Never substitute an invented one."""


class AIRejected(Exception):
    """The AI service rejected the input (validation error)."""


def call(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        settings.AI_SERVICE_URL.rstrip("/") + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Internal-Token": settings.AI_SERVICE_TOKEN},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.AI_SERVICE_TIMEOUT) as response:
            return json.loads(response.read(64 * 1024))
    except urllib.error.HTTPError as error:
        if error.code == 422:
            raise AIRejected("Invalid input for the AI service.") from error
        log.warning("AI service returned HTTP %s for %s", error.code, path)  # no request body: may hold PHI
        raise AIUnavailable from error
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        log.warning("AI service unreachable for %s: %s", path, type(error).__name__)
        raise AIUnavailable from error
