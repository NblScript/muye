#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal Muye API smoke check")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Muye backend base URL")
    parser.add_argument("--history-limit", type=int, default=3, help="History query limit")
    args = parser.parse_args()

    endpoints = [
        ("health", "/api/health"),
        ("dashboard_context", "/api/dashboard/context"),
        ("workflow_state", "/api/workflow/state"),
        ("workflow_history", f"/api/workflow/history?{urllib.parse.urlencode({'limit': args.history_limit})}"),
    ]

    try:
        for name, path in endpoints:
            url = f"{args.base_url}{path}"
            payload = fetch_json(url)
            print(f"[ok] {name}: {json.dumps(payload, ensure_ascii=False)[:400]}")
    except urllib.error.URLError as exc:
        print(f"[error] request failed: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"[error] invalid json: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
