# 🏥 Clinic AI Receptionist

> Multi-tenant AI WhatsApp receptionist for clinics. Patients message a clinic's
> WhatsApp number and an LLM-powered assistant answers questions, books
> appointments, and hands off complex cases to staff — with a React dashboard
> for clinic teams.

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)
![React](https://img.shields.io/badge/React-18-61DAFB)
![Tests](https://img.shields.io/badge/tests-188%20passing-brightgreen)
[![CI](https://github.com/shoaibnext/clinic_ai/actions/workflows/ci.yml/badge.svg)](https://github.com/shoaibnext/clinic_ai/actions/workflows/ci.yml)

---

## ✨ Features

- **Multi-tenant by design** — one deployment, many clinics, fully isolated data
  and API keys per tenant.
- **AI WhatsApp receptionist** — built on Meta's WhatsApp Cloud API (inbound
  webhook + outbound replies, HMAC-signed webhooks).
- **Provider-agnostic LLM client** — Groq (default), OpenAI, Azure OpenAI, or
  OpenRouter, with model fallbacks for free-tier resilience.
- **RAG over clinic knowledge bases** — upload documents, ask questions, get
  grounded answers (works with a local, key-free embeddings fallback).
- **Guided booking flow** — intent detection → availability → confirmation →
  appointment, with a **safety layer** that never diagnoses or prescribes and
  escalates emergencies to staff.
- **Admin dashboard (React + Vite)** — appointments, patients, doctors,
  services, conversations, leads, knowledge base, and WhatsApp diagnostics.
- **Production-ready tooling** — Alembic migrations, Docker Compose
  (PostgreSQL + backend + frontend), and a 188-test suite that runs without
  network or API keys.

## 🧱 Architecture

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 |
| AI | Groq / OpenAI / Azure OpenAI / OpenRouter · RAG · tool calling |
| Database | SQLite (dev) · PostgreSQL + pgvector (prod) |
| Messaging | Meta WhatsApp Cloud API |
| Frontend | React 18 · Vite · react-router |
| Deployment | Docker · Docker Compose |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design.

## 🚀 Quick start

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env         # set GROQ_API_KEY (and optionally SECRET_KEY)
python -m alembic upgrade head
uvicorn app.main:app --reload
```

Swagger UI is available at http://127.0.0.1:8000/docs.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev                  # http://localhost:5173 (proxies /api to :8000)
```

### Full stack with Docker

```bash
cp backend/.env.example backend/.env   # add GROQ_API_KEY, WHATSAPP_* etc.
docker compose -f docker/docker-compose.yml up --build
```

## 💬 Connect WhatsApp (Meta Cloud API)

All WhatsApp code is in place — connecting means filling in credentials and
pointing Meta at your webhook. The step-by-step guide in
[backend/README.md](backend/README.md#connect-whatsapp-meta-cloud-api) covers
getting your phone number ID, permanent access token, and app secret, verifying
with `GET /whatsapp/status` and `POST /whatsapp/test`, and registering the
webhook callback URL.

## 🧪 Testing

```bash
cd backend
python -m pytest
```

The suite uses an in-memory SQLite database and mocks the LLM/embeddings, so it
passes without any network or API keys.

## 📚 Documentation

- [API reference & setup](backend/README.md) — full endpoint table, auth, env
  vars, migrations, WhatsApp setup.
- [Architecture](docs/ARCHITECTURE.md) — system design and multi-tenant model.

## 📦 Repo layout

```
├── backend/     # FastAPI app (AI orchestration, WhatsApp webhook, RAG, REST API, tests)
├── frontend/    # React + Vite admin dashboard
├── docker/      # Docker Compose stack (PostgreSQL + backend + frontend)
├── docs/        # Architecture documentation
└── .github/     # CI workflow, issue/PR templates, Dependabot
```

## 🤝 Contributing

Contributions are welcome! Please read
[CONTRIBUTING.md](CONTRIBUTING.md) and our
[Code of Conduct](CODE_OF_CONDUCT.md), and check the
[Security Policy](SECURITY.md) before reporting a vulnerability.

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

> **Heads up for contributors:** all secrets live in `backend/.env` (gitignored)
> — see `backend/.env.example` for the expected variables. Never commit real
> credentials.

