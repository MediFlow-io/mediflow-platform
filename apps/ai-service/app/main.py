"""MediFlow AI inference service (FastAPI).

Internal only: Django authenticates and authorises the user, then calls this
service with a shared X-Internal-Token. Never expose it through the public proxy.
Request bodies are never logged because they can contain health information.
"""
import hmac
import json
import logging
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from .config import load_settings
from .first_aid import answer_question
from .schemas import AskRequest, AskResponse, TriageRequest, TriageResponse
from .triage import MODEL_VERSION, suggest_esi


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record), "level": record.levelname, "logger": record.name,
                   "msg": record.getMessage()}
        payload.update(getattr(record, "extra_fields", {}))
        return json.dumps(payload)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
log = logging.getLogger("mediflow.ai")
log.addHandler(handler)
log.setLevel(logging.INFO)
log.propagate = False

settings = load_settings()
ASK_DISCLAIMER = ("General first-aid information only, not medical advice or a diagnosis. "
                  "If you are unsure, contact the health centre.")
app = FastAPI(title="MediFlow AI", version=MODEL_VERSION,
              description="Decision support only. Internal service; called by the Django core API.")

REQUESTS = Counter("mediflow_ai_requests_total", "AI requests", ["path", "status"])
LATENCY = Histogram("mediflow_ai_request_seconds", "AI request latency", ["path"])
SUGGESTED_ESI = Counter("mediflow_ai_triage_suggestions_total", "Triage suggestions by ESI", ["esi"])


@app.middleware("http")
async def observe(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    route = request.scope.get("route")
    path = route.path if route else "unmatched"  # bounded label set, even for random 404 paths
    REQUESTS.labels(path, str(response.status_code)).inc()
    LATENCY.labels(path).observe(elapsed)
    log.info("request", extra={"extra_fields": {"path": path, "method": request.method,
                                                "status": response.status_code, "ms": round(elapsed * 1000, 1)}})
    return response


def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_token.encode(), settings.internal_token.encode()):
        raise HTTPException(status_code=401, detail="Invalid internal token.")


@app.get("/ai/health")
def health() -> dict:
    return {"status": "ok", "model_version": MODEL_VERSION}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/ai/triage", response_model=TriageResponse, dependencies=[Depends(require_internal_token)])
def triage(body: TriageRequest) -> TriageResponse:
    result = suggest_esi(body)
    SUGGESTED_ESI.labels(str(result.suggested_esi)).inc()
    return TriageResponse(
        suggested_esi=result.suggested_esi, risk_level=result.risk_level, reasons=result.reasons,
        recommendation=result.recommendation, missing_vitals=result.missing_vitals, model_version=MODEL_VERSION,
    )


@app.post("/ai/ask", response_model=AskResponse, dependencies=[Depends(require_internal_token)])
def ask(body: AskRequest) -> AskResponse:
    answer, topic, emergency = answer_question(body.question, settings.emergency_number)
    return AskResponse(answer=answer, topic=topic, emergency=emergency,
                       disclaimer=ASK_DISCLAIMER)
