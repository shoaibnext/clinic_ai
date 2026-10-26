"""Live LLM smoke test against the real Groq API (key loaded from backend/.env).

Boots uvicorn with a throwaway SQLite DB, seeds a clinic + one service, then
exercises the LLM-backed endpoints. No secrets are printed.
"""
import datetime
import os
import subprocess
import sys
import time
import urllib.request

# Ensure the backend root is importable (scripts/ is on sys.path when run directly).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "sqlite:///./live_llm.db"

import httpx  # noqa: E402

BASE = "http://127.0.0.1:8766"


def wait_healthy(timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(f"{BASE}/health", timeout=2)
            if r.status == 200:
                return True
        except Exception:
            time.sleep(0.4)
    return False


def main() -> int:
    # The Windows console uses cp1252 which can't print some Unicode chars
    # (e.g. \u2011 from model replies). Reconfigure stdout to UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    results = []
    err_file = open("live_llm_server.log", "w", encoding="utf-8")
    # Run uvicorn from the backend root (parent of scripts/) so `app` is importable.
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8766"],
        cwd=backend_root,
        stdout=subprocess.DEVNULL,
        stderr=err_file,
    )
    try:
        if not wait_healthy():
            print("FAIL: server did not become healthy")
            return 1

        with httpx.Client(base_url=BASE, timeout=90) as c:
            def check(label, resp, expect=200):
                ok = resp.status_code == expect
                results.append((label, ok))
                print(f"[{'OK' if ok else 'FAIL'}] {label} -> {resp.status_code}")
                if not ok:
                    print(f"      body: {resp.text[:300]!r}")

            # 1. Provider connectivity (no LLM call, just client construction + config)
            r = c.get("/ai/test")
            check("GET /ai/test (provider check)", r)
            print("      ai/test body:", r.json())

            # 2. Seed clinic + service via API
            r = c.post("/clinics", json={
                "name": "Live LLM Clinic", "slug": "live-llm-clinic",
                "admin_email": "live@test.dev", "admin_password": "Live1234!",
            })
            check("POST /clinics (onboard)", r, 201)
            headers = {"X-API-Key": r.json()["api_key"]}
            r = c.post("/services", headers=headers, json={
                "name": "Consultation", "duration_minutes": 30, "price": "1500",
            })
            check("POST /services", r, 201)
            service_id = r.json()["id"]

            # 3. Level-1 plain LLM chat
            #    With a VALID Groq key this returns 200; with a missing/invalid key
            #    the endpoint must return a clean 502 + readable message (not a raw 500).
            r = c.post("/test-chat", json={
                "clinic_name": "Live LLM Clinic",
                "message": "Hello, what services does the clinic offer?",
            })
            ok_llm = r.status_code in (200, 502)
            results.append(("POST /test-chat (LLM)", ok_llm))
            print(f"[{'OK' if ok_llm else 'FAIL'}] POST /test-chat -> {r.status_code}")
            if not ok_llm:
                print(f"      body: {r.text[:300]!r}")
            if r.status_code == 200:
                print(f"      reply[:160]: {r.json().get('response', '')[:160]!r}")
            elif r.status_code == 502:
                print(f"      graceful 502 detail: {r.json().get('detail', '')[:160]!r}")

            # 4. Full receptionist loop - booking intent
            r = c.post("/ai/chat", json={
                "clinic_slug": "live-llm-clinic",
                "message": "I want to book a consultation tomorrow",
            })
            ok_ai = r.status_code in (200, 502)
            results.append(("POST /ai/chat (booking)", ok_ai))
            print(f"[{'OK' if ok_ai else 'FAIL'}] POST /ai/chat (booking) -> {r.status_code}")
            if r.status_code == 200:
                body = r.json()
                print(f"      intent={body.get('intent')} confidence={body.get('confidence')}")
                print(f"      reply[:200]: {body.get('reply', '')[:200]!r}")
            elif r.status_code == 502:
                print(f"      graceful 502 detail: {r.json().get('detail', '')[:160]!r}")

            # 5. Full receptionist loop - FAQ intent (fallback path, no embeddings)
            r = c.post("/ai/chat", json={
                "clinic_slug": "live-llm-clinic",
                "message": "What are your opening hours?",
            })
            ok_faq = r.status_code in (200, 502)
            results.append(("POST /ai/chat (faq)", ok_faq))
            print(f"[{'OK' if ok_faq else 'FAIL'}] POST /ai/chat (faq) -> {r.status_code}")
            if r.status_code == 200:
                body2 = r.json()
                print(f"      intent={body2.get('intent')} reply[:160]: {body2.get('reply', '')[:160]!r}")
            elif r.status_code == 502:
                print(f"      graceful 502 detail: {r.json().get('detail', '')[:160]!r}")

        failed = [label for label, ok in results if not ok]
        print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
        return 1 if failed else 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        for fname in ("live_llm.db",):
            if os.path.exists(fname):
                os.remove(fname)


if __name__ == "__main__":
    raise SystemExit(main())