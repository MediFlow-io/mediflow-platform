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
| `POST /ai/risk-score` | internal token | NEWS2 early-warning score from vital signs, with the points per parameter and what's missing |
| `POST /ai/wait-time` | internal token | Expected wait with an 80% range for one or more queues, from recent consultation times |
| `POST /ai/bottleneck` | internal token | Where flow is stuck (waiting, called-to-seen, consultation, targets, demand), from aggregate numbers |
| `GET /ai/health` | none | Liveness + model version |
| `GET /metrics` | none (not publicly routed) | Prometheus metrics |
| `GET /docs` | none | Interactive OpenAPI docs |

## Risk score (NEWS2)

`app/news2.py` implements the Royal College of Physicians' NEWS2 chart (2017): respiration rate, SpO₂
(scale 1), supplemental oxygen, systolic BP, pulse, consciousness (AVPU or new confusion) and
temperature. Bands: 0–4 low, a single red parameter (3) low-medium, 5–6 medium, 7+ high. Missing
vitals score nothing, so the response marks the score incomplete (`complete: false`, shown as "6+")
and lists what's missing. It is a published bedside score, not a trained model, so every point can be
checked by hand.

## Flow insights

`app/flow_insights.py` works on aggregate numbers only (counts and averages; Django computes them
and never sends patient data). Wait estimates: people ahead × mean consultation time ÷ clinicians,
with an 80% range from the spread of recent consultations; fewer than 5 recent consultations falls back
to a 15-minute default and says so. Bottlenecks: transparent rules (e.g. waiting ≥ 2× consultation
time and ≥ 20 min, called-to-seen ≥ 10 min, < 70% seen within target), each finding stating the numbers
behind it. Departments with fewer than 5 visits are skipped.

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
