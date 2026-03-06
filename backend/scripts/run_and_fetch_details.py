"""
Trigger a pipeline run, wait for completion, then print run details and findings.
Run from backend/ with: python scripts/run_and_fetch_details.py
Requires the API server to be running on http://localhost:8000
"""

import json
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE = "http://localhost:8000"
CONNECT_RETRIES = 5
CONNECT_RETRY_DELAY = 2


def req(method: str, path: str, data: dict | None = None) -> dict:
    url = f"{BASE}{path}"
    body = json.dumps(data).encode("utf-8") if data else None
    r = Request(url, data=body, method=method)
    if body:
        r.add_header("Content-Type", "application/json")
    try:
        with urlopen(r, timeout=300) as resp:
            return json.loads(resp.read().decode())
    except (URLError, HTTPError) as e:
        err_msg = str(e)
        print(f"Request failed: {err_msg}", file=sys.stderr)
        if "refused" in err_msg.lower() or "10061" in err_msg:
            print(
                f"\nCannot connect to {BASE}. Start the API server first in another terminal:\n"
                "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000\n",
                file=sys.stderr,
            )
        sys.exit(1)


def wait_for_server() -> None:
    """Retry connecting to the API a few times (server may still be starting)."""
    for attempt in range(1, CONNECT_RETRIES + 1):
        try:
            r = Request(f"{BASE}/health", method="GET")
            with urlopen(r, timeout=5) as resp:
                if getattr(resp, "status", resp.getcode()) == 200:
                    return
        except (URLError, HTTPError, OSError):
            if attempt == CONNECT_RETRIES:
                print(
                    f"Cannot connect to {BASE} after {CONNECT_RETRIES} attempts.\n"
                    "Start the API server in another terminal:\n"
                    "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000\n",
                    file=sys.stderr,
                )
                sys.exit(1)
            time.sleep(CONNECT_RETRY_DELAY)


def main():
    wait_for_server()
    print("Triggering run...")
    run = req("POST", "/api/runs/", {"trigger": "manual"})
    run_id = run["id"]
    print(f"Run ID: {run_id}, status: {run['status']}\n")

    print("Waiting for run to complete (polling every 3s)...")
    for _ in range(120):
        run = req("GET", f"/api/runs/{run_id}")
        status = run["status"]
        print(f"  status={status}")
        if status in ("success", "partial", "failed", "cancelled"):
            break
        time.sleep(3)
    else:
        print("Timeout waiting for run to finish.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("RUN DETAILS")
    print("=" * 60)
    print(json.dumps(run, indent=2, default=str))

    findings = req("GET", f"/api/findings/?run_id={run_id}&limit=100")
    print("\n" + "=" * 60)
    print(f"FINDINGS ({len(findings)} total)")
    print("=" * 60)
    for i, f in enumerate(findings, 1):
        print(f"\n--- Finding {i} ---")
        print(json.dumps(f, indent=2, default=str))

    if run.get("digest_id"):
        print("\n" + "=" * 60)
        print("DIGEST")
        print("=" * 60)
        digest = req("GET", f"/api/digests/{run['digest_id']}")
        print(json.dumps(digest, indent=2, default=str))

    print("\nDone.")


if __name__ == "__main__":
    main()
