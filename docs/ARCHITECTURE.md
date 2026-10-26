# Clinic AI Receptionist — Architecture

## Overview

Multi-tenant SaaS: each clinic is a tenant with its own data, staff users,
WhatsApp number, and knowledge base. Patients interact through WhatsApp; the AI
receptionist answers questions, captures leads, and books/reschedules/cancels
appointments. Clinic staff manage everything via the admin dashboard / REST API.

```
Patient ── WhatsApp ──> POST /whatsapp/webhook ──> handle_message()
                                                        │
                    ┌───────────────────────────────────▼──────────────────────┐
                    │  webhook auth (X-Hub-Signature-256 when secret set)      │
                    │  safety pre-check (emergency / medical / handoff)         │
                    │  intent detection (structured JSON via LLM)               │
                    │  RAG search over the clinic's knowledge base              │
                    │  booking / cancel / reschedule / availability flows        │
                    │  validated backend tools (create appointment, lead, ...)   │
                    │  response validated against DB truth                       │
                    └───────────────────────────────────────────────────────────┘
                                                        │
                                        reply ──> WhatsApp + persisted messages
```

**Webhook security:** the inbound handler reads the raw request body and, when
`WHATSAPP_APP_SECRET` is configured, verifies Meta's `X-Hub-Signature-256`
header (HMAC-SHA256 of the raw body, constant-time compare). Requests with a
missing or invalid signature are rejected with 403. Without a configured
secret (local dev) verification is skipped and a warning is logged.

**Connection diagnostics:** `GET /whatsapp/status` reports which credentials
are configured (without echoing secrets) and, when present, validates the
access token against the Graph API (`GET /{api_version}/{phone_number_id}`).
`POST /whatsapp/test` sends a live outbound message to a given number — the
two endpoints together confirm the app can talk to WhatsApp before the webhook
is wired up. `backend/scripts/generate_webhook_token.py` creates a strong
webhook verify token in `.env`.

## Backend (FastAPI)

| Layer | Location | Responsibility |
|-------|----------|----------------|
| Routers | `app/api/` | HTTP layer, auth via `app/api/dependencies.py` (tenant resolution) |
| Schemas | `app/schemas/` | Pydantic request/response models |
| Services | `app/services/` | Business logic per domain (clinic, doctor, service, patient, appointment, availability, lead, conversation, knowledge, auth, whatsapp) |
| AI module | `app/ai/` | LLM client, intent detection, safety, state machine, tools, validation, events, RAG |
| Models | `app/database/models/` | SQLAlchemy 2.0 mapped classes (16 tables) |
| Migrations | `alembic/` | Versioned schema; `env.py` reads `DATABASE_URL` from settings |
| Config | `app/core/config.py` | pydantic-settings reading `.env` |

### Tenant isolation

Every authenticated request resolves the active clinic:

1. `Authorization: Bearer <jwt>` → `clinic_id` claim, or
2. `X-API-Key: <clinic api key>` → lookup by `api_key`

All service queries filter by `clinic_id`; cross-tenant access is rejected at
the service layer (covered by tests).

### AI orchestration (`app/ai/orchestrator.py`)

The conversation loop, per inbound message:

1. **Load state** — persisted JSON on the `Conversation` row (`app/ai/state.py`)
2. **Safety pre-check** — emergency terms → immediate guidance + human handoff;
   medical-advice terms → refuse to diagnose (`app/ai/safety.py`)
3. **Intent detection** — LLM returns `{intent, confidence, entities}` as JSON
   (`app/ai/intent.py`); entities are merged into the working state
4. **Route** — booking (collect service → date → time → name → confirm),
   cancel, reschedule, availability, FAQ (RAG), handoff, unknown
5. **Execute tools** — mutations always run through validated service functions
   (`app/ai/tools.py`): `create_appointment`, `cancel_appointment`,
   `reschedule_appointment`, `create_lead`, `handoff_to_human`
6. **Validate response** — if the LLM claims a booking/cancellation that the DB
   doesn't show, replace the reply with an honest fallback (`app/ai/validation.py`)
7. **Persist** — state, patient name, AI event log (`app/ai/events.py`)

### RAG (`app/ai/rag.py`)

- Documents are chunked (`app/services/knowledge_service.py`) and embedded at
  ingest time (provider: OpenAI/Azure embeddings, configurable)
- Retrieval embeds the query and ranks chunks by cosine similarity
- **Tenant isolation is mandatory**: chunks are always filtered by `clinic_id`
- Embeddings are stored as JSON (works on SQLite + Postgres); pgvector is the
  documented scale-path

### LLM client (`app/ai/client.py`)

Provider-agnostic: Groq (default, free tier), OpenAI, Azure OpenAI, or OpenRouter
(an OpenAI-compatible aggregator), driven by `LLM_PROVIDER` + related env vars.
`get_llm()` returns a lazy singleton; OpenRouter gets the HTTP-Referer/X-Title
attribution headers. Embeddings: OpenAI/Azure when a key is configured, otherwise
a deterministic local hashing embedder (MD5-based) so RAG works with no extra key.

## Frontend (React + Vite)

- `src/pages/` — one component per admin screen; `src/api.js` wraps fetch with
  JWT/API-key auth and query-string building
- Dev: Vite proxies `/api` → `http://localhost:8000`
- Production: nginx serves the built static files and proxies `/api/` to the
  backend (see `frontend/Dockerfile` + `frontend/nginx.conf`)

## Data model (16 tables)

`clinics`, `users`, `patients`, `doctors`, `services`, `doctor_services`,
`appointments`, `leads`, `conversations`, `messages`, `availabilities`,
`knowledge_bases`, `documents`, `document_chunks`, `ai_events`.

## Deployment

See `docker/docker-compose.yml`: Postgres (health-checked) + backend (runs
`alembic upgrade head` then uvicorn) + frontend (nginx). Environments are
injected via `.env` (`GROQ_API_KEY`, `WHATSAPP_*`, `SECRET_KEY`, ...).

## Tests

`backend/tests/` — 188 pytest cases: API CRUD + tenant isolation per domain,
AI unit tests (state, safety, intent, validation, RAG), and full conversation
flows (booking E2E, handoff, emergency, reschedule) with the LLM mocked.
In-memory SQLite + `fastapi.testclient`; requires no network or API keys.

## Development commands (from `backend/`)

```bash
python -m alembic upgrade head          # apply migrations
python -m pytest                        # run the suite
python scripts/seed_clinic.py           # create a demo clinic (idempotent)
uvicorn app.main:app --reload           # run the API
```