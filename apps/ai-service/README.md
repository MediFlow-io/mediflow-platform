# MediFlow AI service (FastAPI)

Internal decision-support service. **Only the Django core API calls it.** Browsers use
`/api/ai/*` on Django, which handles login, roles, rate limits and audit, then forwards
the request with a shared `X-Internal-Token`.

> Decision support only. It never diagnoses, prescribes, or sets a patient's ESI level.
> A clinician reviews every suggestion.

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /ai/triage` | internal token | Suggest an ESI level (1–5) from vitals and complaint, with the reasons |
| `POST /ai/ask` | internal token | General first-aid answer (contract from `Mediflow-Doc/AI.md`) |
| `GET /ai/health` | none | Liveness + model version |
| `GET /metrics` | none (not publicly routed) | Prometheus metrics |
| `GET /docs` | none | Interactive OpenAPI docs |

## How triage works

`app/triage.py` follows the ESI v4 steps: life-threat → high-risk or danger-zone vitals
(age-adjusted) → expected resources. Every response lists the rules that fired.

Deliberate safety choices:
- Uncertainty rounds toward **more** urgent. Negation is not parsed, so "no chest pain" still flags.
- With no vitals, nothing is suggested below ESI 3.
- **No confidence score.** Rules have no calibrated probability, and a made-up number would mislead.

The model version is `rules-esi-2026.10`. A trained model can replace `suggest_esi()` later
without changing the API, once a dataset, evaluation and bias review exist.

## Run

```bash
cd apps/ai-service
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8001 --reload
pytest -q
```

| Variable | Default | Notes |
|---|---|---|
| `AI_SERVICE_TOKEN` | `mediflow-dev-internal-token` | Must match Django. Refused outside development. |
| `AI_ENV` | `development` | Any other value requires a real token |
| `EMERGENCY_NUMBER` | `112` | Used in emergency answers |
