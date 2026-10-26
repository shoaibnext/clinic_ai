# Security Policy

## Supported versions

| Version | Supported          |
|---------|--------------------|
| main    | :white_check_mark: |

Only the latest version on `main` receives security updates.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report them privately via one of:

1. **GitHub private security advisory** — go to the repository's
   *Security → Advisories → New advisory* (recommended).
2. **Email** — <shoaib000yt@gmail.com> with the subject
   `[Clinic AI Security] <short description>`.

When reporting, please include:

- The affected endpoint/module and version (commit hash if possible).
- Steps to reproduce.
- Impact — what an attacker could do.
- Any suggested fix, if you have one.

We aim to acknowledge reports within 3 business days and to send a detailed
response within 10 business days.

## Security considerations for this project

- **Never commit secrets.** All credentials (LLM API keys, WhatsApp tokens,
  `SECRET_KEY`, database URLs) belong in `backend/.env`, which is gitignored.
  See `.env.example` for the full list of expected variables.
- **Rotate leaked credentials immediately.** If a token ever appears in logs,
  a public URL, or git history, treat it as compromised, rotate it, and remove
  it from history (e.g. with `git filter-repo`) before pushing.
- **Webhook security.** When `WHATSAPP_APP_SECRET` is configured, every
  inbound WhatsApp webhook is verified with `X-Hub-Signature-256`. Keep the
  app secret set in production.
- **Deployments.** Use the provided Docker Compose stack with PostgreSQL; never
  run with `APP_DEBUG=True` or default `SECRET_KEY` in production.
