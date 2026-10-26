"""Generate a strong WHATSAPP_WEBHOOK_VERIFY_TOKEN in backend/.env.

The webhook verify token is a shared secret between THIS backend and the Meta
App Dashboard. Meta sends it back on webhook verification (GET
/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=...) — the backend
compares it before answering the challenge.

Usage (from backend/):
    python scripts/generate_webhook_token.py
"""

import pathlib
import secrets

ENV_PATH = pathlib.Path(__file__).resolve().parent.parent / ".env"
KEY = "WHATSAPP_WEBHOOK_VERIFY_TOKEN"


def main() -> str:
    token = f"wv_{secrets.token_urlsafe(24)}"
    text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    lines = text.splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{KEY}="):
            lines[i] = f"{KEY}={token}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{KEY}={token}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return token


if __name__ == "__main__":
    print(main())