# MediFlow AI Guide

## Purpose and safety boundary

The AI feature is decision support and first-aid education only. It must not
diagnose, prescribe, triage autonomously, or replace emergency services or a
qualified clinician. The UI must make this boundary clear.

## Current implementation

The current AI layer is a safe, built-in rule-based responder in:

```text
FE/FUTA Health Centre Project/server.js
```

`aiAnswer(question)` matches basic terms such as bleeding, cut, burn,
choking, fainting, and unconsciousness. It returns general first-aid guidance
and a medical disclaimer. It is not a diagnosis or a replacement for a
clinician.

The browser integrations are:

- `ai-assistant.js`: inline AI help on the public page and dashboard.
- `ai-widget.js`: authenticated bottom-right “AI help” notification box.

Both send:

```http
POST /api/ai/ask
Content-Type: application/json

{ "question": "What should I do for a burn?" }
```

Successful response:

```json
{ "answer": "General first-aid guidance..." }
```

Invalid requests return `400`; a missing session returns `401`; unexpected
provider or server failures must return an error rather than an invented
answer. The current built-in responder does not call an external model.

## Request handling requirements

- Limit questions to the documented maximum length.
- Normalize and validate input before sending it to another service.
- Do not include patient names, IDs, diagnoses, or full records unless a
  formally reviewed clinical workflow explicitly requires it.
- Keep provider credentials on the server.
- Apply authentication, rate limiting, timeouts, and response-size limits.
- Log operational metadata only; redact prompts and health information by
  default.

## Response quality requirements

Answers should be plain language, actionable, cautious, and time-bounded where
appropriate. They should identify emergency warning signs and recommend local
emergency services for urgent situations. Avoid certainty, personalized
diagnosis, medication dosing, and instructions outside the system's approved
scope.

## Replacing the built-in responder

When a real AI service is ready:

1. Keep `/api/ai/ask` as the browser-facing contract.
2. Add a server-side client in `server.js` or, preferably, a dedicated AI
   service module.
3. Keep provider keys server-side in environment variables.
4. Set request timeouts, input limits, rate limits, and audit logging.
5. Never send unnecessary patient identifiers or full medical records.
6. Treat model output as decision support only.
7. Preserve the disclaimer and emergency escalation wording.
8. Update `ARCHITECTURE.yml` with the provider/service boundary.

Before enabling a model, define an evaluation set covering common first-aid
questions, unsafe requests, ambiguous symptoms, prompt injection attempts,
missing context, and service failures. Record expected safe behavior and
review model changes before release.

## Recommended future AI service

The root project README describes a future FastAPI inference service. When it
exists, the Node/Django gateway should authenticate the caller, validate the
request, call FastAPI over a private network, and return a stable response to
the browser. The browser must not call the model provider directly.

## AI change checklist

- Does the answer avoid diagnosis and certainty claims?
- Does it recommend emergency services for urgent symptoms?
- Are prompts and responses length-limited?
- Are secrets kept out of HTML, JavaScript, and git?
- Are failures shown clearly without pretending that an answer was generated?
- Were the widget and inline assistant both tested?
- Was the response evaluated for unsafe medical certainty?
- Were privacy, retention, and provider terms reviewed?
- Is there a rollback path to the built-in safe response?
