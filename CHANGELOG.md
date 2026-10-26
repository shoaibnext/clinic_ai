# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-26

### Added

- Multi-tenant FastAPI backend: clinics, auth (API key + JWT), doctors,
  services, patients, appointments, leads, conversations, availability, and a
  RAG knowledge base.
- Provider-agnostic LLM client (Groq, OpenAI, Azure OpenAI, OpenRouter) with
  fallback model lists for free-tier resilience.
- WhatsApp Cloud API integration: inbound webhook (HMAC-signed when
  `WHATSAPP_APP_SECRET` is set), outbound replies, `/status` and `/test`
  diagnostics.
- AI receptionist loop: intent detection, safety guardrails, multi-turn
  appointment booking flow, and human handoff.
- RAG over uploaded clinic documents with a local, key-free embeddings
  fallback.
- React + Vite admin dashboard (login, dashboard, appointments, patients,
  doctors, services, conversations, leads, knowledge, WhatsApp).
- Alembic migrations and a Docker Compose stack (PostgreSQL + backend +
  frontend).
- Test suite (188 tests) that runs without network or API keys.
