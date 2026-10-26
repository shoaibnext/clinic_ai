# Contributing to Clinic AI Receptionist

Thanks for your interest in contributing! Please take a moment to read this
guide before opening an issue or pull request.

## Code of conduct

This project and everyone participating in it is governed by the
[Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to
uphold this code.

## How to contribute

### Reporting bugs

1. Search the [issues](../../issues) to see if the problem has already been
   reported.
2. If not, open a bug report using the
   [bug report template](.github/ISSUE_TEMPLATE/bug_report.md). Include:
   - Steps to reproduce.
   - Expected vs. actual behaviour.
   - Environment (OS, Python/Node versions, provider used).
   - Any relevant logs (with secrets redacted).

### Requesting features

Open a feature request using the
[feature request template](.github/ISSUE_TEMPLATE/feature_request.md). Describe
the problem you are solving and, if possible, how you would expect it to work.

### Submitting a pull request

1. Fork the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
2. Make your changes. Keep them focused and well-tested.
3. Run the backend test suite:
   ```bash
   cd backend
   python -m pytest
   ```
4. Make sure the frontend still builds:
   ```bash
   cd frontend
   npm ci
   npm run build
   ```
5. Commit with a clear message, e.g. `feat(api): add endpoint X`.
   We follow [Conventional Commits](https://www.conventionalcommits.org/).
6. Push and open a pull request against `main` using the
   [pull request template](.github/PULL_REQUEST_TEMPLATE.md).

## Development environment

See [README.md](README.md#quick-start) and
[backend/README.md](backend/README.md) for full setup instructions.

## Security

Found a security issue? Do **not** open a public issue. Follow the disclosure
process in [SECURITY.md](SECURITY.md).

## Project structure

- `backend/` — FastAPI application (AI orchestration, WhatsApp webhook, RAG,
  REST API, migrations, tests).
- `frontend/` — React + Vite admin dashboard.
- `docker/` — Docker Compose deployment (PostgreSQL + backend + frontend).
- `docs/` — architecture documentation.

## Licensing

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
