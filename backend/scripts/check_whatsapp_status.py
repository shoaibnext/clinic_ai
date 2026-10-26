"""Live-check the WhatsApp connection: GET /whatsapp/status only.

This makes a REAL call to graph.facebook.com using the configured
WHATSAPP_* credentials and prints the diagnostic result. It never sends
messages — use POST /whatsapp/test for that with a real recipient.

Usage (from backend/):
    python scripts/check_whatsapp_status.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    with TestClient(app) as client:
        res = client.get("/whatsapp/status")
        print("status_code:", res.status_code)
        print(res.json())


if __name__ == "__main__":
    main()