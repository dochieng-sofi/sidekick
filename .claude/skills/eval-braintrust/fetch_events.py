#!/usr/bin/env python3
# Run with Python 3.12: PYENV_VERSION=3.12.0 python3 fetch_events.py
# Python 3.14 rejects the SoFi corporate CA cert due to strict Basic Constraints enforcement.
"""
Fetch all events from a Braintrust experiment, handling S3 303 redirect and cursor pagination.

Usage:
  python3 fetch_events.py --exp-id <UUID> [--output /tmp/bt_events.json]

Environment:
  BRAINTRUST_API_KEY — required (load with: set -a && source .env && set +a)

Notes:
  - Large responses return HTTP 303 -> S3 signed URL. The pagination cursor is in the
    x-bt-cursor header on the ORIGINAL response (before redirect). follow_redirects must
    be False on the first request; then follow the Location manually.
  - Cursor values contain + signs that must be URL-encoded (%2B). Pass through
    quote(cursor, safe='') — do NOT pass raw or you get HTTP 400 "Invalid cursor".
  - Rate limit: 20 req/60s. Sleeps 3.5s between pages, backs off 15s on 429.
"""
import argparse
import json
import os
import time
from urllib.parse import quote

import httpx

# SoFi corporate proxy uses a custom CA. Use it if present; otherwise default.
_SOFI_CA = "/Library/SoFi/PKI/cacert.pem"
_SSL_VERIFY = _SOFI_CA if os.path.exists(_SOFI_CA) else True


def fetch_all_events(exp_id: str, api_key: str) -> list:
    all_events = []
    cursor = None
    page = 0
    base = "https://api.braintrust.dev"

    api_client = httpx.Client(timeout=30, follow_redirects=False, verify=_SSL_VERIFY)
    s3_client = httpx.Client(timeout=120, follow_redirects=True, verify=_SSL_VERIFY)

    try:
        while True:
            url = f"{base}/v1/experiment/{exp_id}/fetch?limit=1000"
            if cursor:
                url += f"&cursor={quote(cursor, safe='')}"

            resp = api_client.get(url, headers={"Authorization": f"Bearer {api_key}"})
            next_cursor = resp.headers.get("x-bt-cursor")  # capture BEFORE following redirect

            if resp.status_code == 421:
                redirect = resp.json().get("RedirectUrl", "").rstrip("/")
                if redirect:
                    base = redirect
                    print(f"Data plane redirect -> {base}", flush=True)
                    continue  # retry same page against new base
                print(f"421 with no RedirectUrl — stopping", flush=True)
                break
            elif resp.status_code == 303:
                data = s3_client.get(resp.headers["location"]).json()
            elif resp.status_code == 200:
                data = resp.json()
            elif resp.status_code == 429:
                print("Rate limited, sleeping 15s...", flush=True)
                time.sleep(15)
                continue
            else:
                print(f"Error {resp.status_code}: {resp.text[:300]}", flush=True)
                break

            events = data.get("events", [])
            all_events.extend(events)
            page += 1
            print(
                f"Page {page}: {len(events)} events, total={len(all_events)}, "
                f"cursor={'yes' if next_cursor else 'no'}",
                flush=True,
            )

            if not events or not next_cursor:
                break
            cursor = next_cursor
            time.sleep(3.5)
    finally:
        api_client.close()
        s3_client.close()

    return all_events


def main():
    parser = argparse.ArgumentParser(description="Fetch all Braintrust experiment events")
    parser.add_argument("--exp-id", required=True, help="Experiment UUID")
    parser.add_argument("--output", default="/tmp/bt_events.json", help="Output path for events JSON")
    args = parser.parse_args()

    api_key = os.environ.get("BRAINTRUST_API_KEY")
    if not api_key:
        print("Error: BRAINTRUST_API_KEY not set. Load your .env: set -a && source .env && set +a")
        raise SystemExit(1)

    events = fetch_all_events(args.exp_id, api_key)

    with open(args.output, "w") as f:
        json.dump(events, f)
    print(f"\nSaved {len(events)} events to {args.output}")


if __name__ == "__main__":
    main()
