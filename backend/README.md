# Clinic AI Receptionist API

Multi-tenant WhatsApp AI receptionist for clinics. Built with FastAPI, SQLAlchemy 2.0,
Groq/OpenAI/Azure (provider-agnostic LLM client), and a React + Vite admin dashboard.

- Patients message the clinic's WhatsApp number
- AI answers clinic questions (RAG over the clinic's knowledge base)
- Multi-turn booking flow: intent → availability → confirmation → appointment
- Safety layer: never diagnoses or prescribes; escalates emergencies/handoffs to staff
- Staff dashboard and REST API for patients, appointments, doctors, services,
  conversations, leads, and the knowledge base

## Tech stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.0, Pydantic v2
- **AI**: provider-agnostic client — Groq (free tier, default), OpenAI, or Azure OpenAI
- **RAG**: embeddings + cosine similarity over uploaded clinic documents (tenant-isolated)
- **Database**: SQLite (local dev) / PostgreSQL + pgvector (deployment)
- **Messaging**: Meta WhatsApp Cloud API
- **Frontend**: React + Vite admin dashboard

## Getting started

### Prerequisites

- Python 3.12+
- Node.js 18+ (frontend only)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# 1. Set a main LLM key: GROQ_API_KEY (or OPENAI_API_KEY / AZURE_OPENAI_*)
# 2. Set SECRET_KEY (JWT signing) and the admin API key if used
# 3. WhatsApp credentials when going live:
#    WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_ACCESS_TOKEN, WHATSAPP_WEBHOOK_VERIFY_TOKEN
#    and WHATSAPP_APP_SECRET (App Secret from the Meta app dashboard). When the
#    app secret is set, every webhook is authenticated via X-Hub-Signature-256.

# Optional: PostgreSQL for deployment
docker compose -f ../docker/docker-compose.yml up -d

# Run the server
uvicorn app.main:app --reload
```

### Database migrations

Migrations use [Alembic](https://alembic.sqlalchemy.org). The migration engine
reads the same `DATABASE_URL` from `.env` as the app (see `alembic/env.py`).

```bash
cd backend

# Apply the initial (and any pending) migrations:
python -m alembic upgrade head

# After changing a model, generate a new migration and review it:
python -m alembic revision --autogenerate -m "describe your change"
python -m alembic upgrade head

# Verify the migrations match the models (no drift):
python -m alembic check
```

Open http://127.0.0.1:8000/docs for Swagger UI.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev   # http://localhost:5173, proxies /api to :8000
```

Sign in with the clinic admin credentials created during onboarding
(`POST /clinics`).

### Tests

```bash
cd backend
python -m pytest
```

The suite runs against an in-memory SQLite database and mocks the LLM/embeddings,
so it passes without network or API keys.

## Connect WhatsApp (Meta Cloud API)

The app speaks to WhatsApp through Meta's WhatsApp Cloud API: inbound messages
arrive on `POST /whatsapp/webhook`, outbound replies go directly to Graph API.
Everything is coded — you just need to fill in credentials and point Meta at
your webhook.

### 1. Get credentials from Meta (once, ~10 minutes)

1. Go to <https://developers.facebook.com> and create a **Meta business app**,
   then add the **WhatsApp** product.
2. In **WhatsApp → API Setup**:
   - **Phone number id** — copy it (this is the `WHATSAPP_PHONE_NUMBER_ID`).
   - **Temporary access token** — generate, then convert it to a **permanent**
     system-user token (Business settings → System users → Generate token,
     scoped to *WhatsApp* and *whatsapp_business_messaging* +
     *whatsapp_business_management*). Use the permanent one in `.env`.
   - **Whitelisted senders** — in development/test mode, add every phone number
     you want to test with.
3. In **App settings → Basic** copy the **App secret** — `WHATSAPP_APP_SECRET`.

### 2. Fill `backend/.env`

```dotenv
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_WEBHOOK_VERIFY_TOKEN=<your-own-secret>   # or: python scripts/generate_webhook_token.py
WHATSAPP_APP_SECRET=
```

Then restart the API and run the built-in connection checks:

```bash
# 1) How it's configured + does the access token pass Graph API validation?
curl http://127.0.0.1:8000/whatsapp/status

# 2) Send a real outbound test message to a whitelisted number
curl -X POST http://127.0.0.1:8000/whatsapp/test \
     -H "Content-Type: application/json" \
     -d '{"to_phone": "+15550101111", "text": "Hello from Clinic AI!"}'
```

If `/whatsapp/status` shows `"configured": true` and `"ok": true`, the app can
send WhatsApp messages.

### 3. Point Meta at your webhook

Meta only calls public **HTTPS** URLs, so expose the backend with a tunnel for
local development:

```bash
ngrok http 8000        # e.g. https://abc123.ngrok-free.app -> localhost:8000
```

Then in **WhatsApp → Configuration → Webhook**:

| Field | Value |
|-------|-------|
| Callback URL | `https://<your-public-url>/whatsapp/webhook` |
| Verify token | the exact `WHATSAPP_WEBHOOK_VERIFY_TOKEN` you set |
| Webhook fields | subscribe to **messages** |

Click *Verify and save* — Meta GETs your callback with `hub.mode`, `hub.verify_token`
and `hub.challenge`; the app answers with the challenge number. Now text your
clinic's WhatsApp number and the AI receptionist replies.

### Production go-live checklist

- [ ] `WHATSAPP_APP_SECRET` is set (webhook signature verification becomes mandatory)
- [ ] Business verification + phone number verification **approved** by Meta (24h)
- [ ] The webhook callback URL is the production HTTPS host (not ngrok)
- [ ] Recipients in production must reply **"join"** once to the number (24h window)

## API

Authentication is **multi-tenant**:

- `POST /clinics` (onboarding) returns the clinic `api_key` once
- `X-API-Key: <clinic api key>` header, **or**
- `Authorization: Bearer <jwt>` from `POST /auth/login`

Admin endpoints resolve the tenant (clinic) from the header; every query is scoped
to that clinic.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | — | Service info |
| GET | `/health` | — | Health check |
| POST | `/clinics` | — | Onboard a clinic (returns API key) |
| GET | `/clinics/me` | API key/JWT | Current clinic |
| POST | `/clinics/{id}/whatsapp-phone` | — | Set WhatsApp phone-number-id |
| POST | `/auth/login` | — | Staff login → JWT |
| GET/POST | `/doctors`; `/doctors/{id}`; `/doctors/{id}/services` | API key/JWT | Doctors |
| GET/POST | `/services`; `/services/{id}` | API key/JWT | Services |
| GET/POST/PATCH/DELETE | `/patients`; `/patients/{id}` | API key/JWT | Patients |
| GET/POST/PATCH/DELETE | `/appointments`; `/appointments/{id}` | API key/JWT | Appointments |
| GET/POST/PATCH | `/leads`; `/leads/{id}` | API key/JWT | Leads |
| GET/PATCH | `/conversations`; `/conversations/{id}` | API key/JWT | Conversations |
| GET/POST | `/availability`; GET `/availability/slots` | API key/JWT | Availability/slots |
| POST | `/knowledge/bases`; POST/GET/DELETE `/knowledge/documents`; POST `/knowledge/search` | API key/JWT | Knowledge base / RAG |
| GET | `/whatsapp/webhook` | — | Meta webhook verification |
| POST | `/whatsapp/webhook` | — | Inbound WhatsApp handler (AI receptionist loop); verifies `X-Hub-Signature-256` when `WHATSAPP_APP_SECRET` is set |
| GET | `/whatsapp/status` | — | WhatsApp connection diagnostic — which credentials are set (never echoes secrets) + live Graph API validation of the token/number ID |
| POST | `/whatsapp/test` | — | Send a live outbound test message to a phone number (`{"to_phone": "+15550101111", "text": "hi"}`) |
| POST | `/test-chat` | — | Level-1 plain LLM chat (dev) |
| GET | `/ai/test` | — | LLM provider connectivity check |
| POST | `/ai/chat` | — | Full receptionist loop for a clinic/patient/conversation |

## Project structure

```
backend/
├── app/
│   ├── ai/              # LLM client, intent detection, safety, RAG, state, validation, events
│   ├── api/             # Routers: clinics, auth, doctors, services, patients, appointments,
│   │                    #   leads, conversations, availability, knowledge, whatsapp, ai, health
│   ├── core/            # Config (pydantic-settings), security (JWT + bcrypt), logging
│   ├── database/        # SQLAlchemy engine/session + 16 models (all registered in models/__init__)
│   ├── schemas/         # Pydantic request/response schemas
│   ├── services/        # Business logic per domain
│   └── main.py          # FastAPI app entry point
├── tests/               # pytest suite (in-memory SQLite, mocked AI) — 188 tests
├── requirements.txt
└── .env.example

frontend/
├── src/
│   ├── api.js           # API client (JWT + API-key auth)
│   ├── App.jsx          # Routing + sidebar shell
│   ├── pages/           # Login, Dashboard, Appointments, Patients, Doctors, Services,
│   │                    #   Conversations, Leads, Knowledge
│   └── main.jsx
├── vite.config.js       # dev proxy /api -> :8000
└── package.json
```
