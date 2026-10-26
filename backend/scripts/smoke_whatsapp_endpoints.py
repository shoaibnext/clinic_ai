"""Smoke-test the WhatsApp connection endpoints.

GET /whatsapp/status is always safe (validates credentials against Graph API).
POST /whatsapp/test sends a REAL message, so it's opt-in with --to:

    python scripts/smoke_whatsapp_endpoints.py
    python scripts/smoke_whatsapp_endpoints.py --to +15550101111 "hi from Clinic AI"

Use --to only with a phone number allowed by Meta (whitelisted in test mode,
or a customer who replied "join" in production).
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", help="Recipient (E.164) to send the real test message to")
    parser.add_argument("text", nargs="?", default="Hello from Clinic AI!")
    args = parser.parse_args()

    with TestClient(app) as client:
        res = client.get("/whatsapp/status")
        print("GET /whatsapp/status ->", res.status_code, res.json())

        if args.to:
            res = client.post("/whatsapp/test", json={"to_phone": args.to, "text": args.text})
            print("POST /whatsapp/test  ->", res.status_code, res.json())
        else:
            print("POST /whatsapp/test skipped (pass --to <phone> to send a real message)")


if __name__ == "__main__":
    main()