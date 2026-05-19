#!/usr/bin/env python3
# Run with Python 3.12: PYENV_VERSION=3.12.0 python3 resolve_experiment.py
"""
Resolve a Braintrust experiment to its full UUID.

Accepts:
  - Full Braintrust URL (parses experiment name from path)
  - Experiment name (e.g. test-cases-super-merge-train-aa18ec60)
  - Short fragment (e.g. aa18ec60 — last 8 chars)

Usage:
  python3 resolve_experiment.py --identifier <url|name|fragment> [--project "CI Regression Tests"]

Output (stdout):
  <uuid> <experiment-name>

On failure, prints available experiments and exits 1.
"""
import argparse
import json
import os
import sys
from urllib.parse import unquote
from urllib.request import Request, urlopen

SOFI_CA = "/Library/SoFi/PKI/cacert.pem"


_DEFAULT_BASE = "https://api.braintrust.dev"


def api_get(path: str, api_key: str, base: str = _DEFAULT_BASE) -> tuple[dict, str]:
    """Returns (response_dict, resolved_base). Follows 421 DataPlaneRedirect once."""
    url = f"{base}{path}"
    req = Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        # urllib uses system SSL on 3.12 which trusts the SoFi CA
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()), base
    except Exception as e:
        # urllib raises HTTPError for non-2xx; check for 421 by reading the body
        body = e.read().decode() if hasattr(e, "read") else ""
        if hasattr(e, "code") and e.code == 421:
            try:
                redirect = json.loads(body).get("RedirectUrl", "").rstrip("/")
            except Exception:
                redirect = ""
            if redirect:
                print(f"Data plane redirect -> {redirect}", file=sys.stderr)
                url2 = f"{redirect}{path}"
                req2 = Request(url2, headers={"Authorization": f"Bearer {api_key}"})
                with urlopen(req2, timeout=30) as resp2:
                    return json.loads(resp2.read()), redirect
        raise


def parse_url(url: str) -> str:
    """Extract experiment name from a braintrust.dev URL."""
    # .../experiments/test-cases-super-merge-train-aa18ec60?c=...
    path = url.split("?")[0]
    parts = unquote(path).split("/experiments/")
    if len(parts) == 2:
        return parts[1].rstrip("/")
    return ""


def find_experiment(identifier: str, project: str, api_key: str) -> tuple[str, str]:
    """Returns (uuid, name) or raises SystemExit."""
    # Normalise identifier
    if "braintrust.dev" in identifier:
        name = parse_url(identifier)
        if not name:
            print(f"Could not parse experiment name from URL: {identifier}", file=sys.stderr)
            raise SystemExit(1)
    else:
        name = identifier  # full name or short fragment

    path = f"/v1/experiment?project_name={project.replace(' ', '+')}&limit=200"
    data, _ = api_get(path, api_key)
    experiments = data.get("objects", [])

    # Match by exact name or substring (handles short fragments)
    matches = [e for e in experiments if name in e.get("name", "")]
    if matches:
        e = matches[0]
        return e["id"], e["name"]

    # Not found — print list and exit
    print(f"Experiment '{name}' not found in project '{project}'.", file=sys.stderr)
    print(f"Available ({len(experiments)} total, newest first):", file=sys.stderr)
    for e in experiments[:10]:
        print(f"  {e['id']}  {e['name']}", file=sys.stderr)
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="Resolve a Braintrust experiment to its UUID")
    parser.add_argument("--identifier", required=True, help="URL, experiment name, or short fragment")
    parser.add_argument("--project", default="CI Regression Tests", help="Braintrust project name")
    args = parser.parse_args()

    api_key = os.environ.get("BRAINTRUST_API_KEY")
    if not api_key:
        print("Error: BRAINTRUST_API_KEY not set. Run: set -a && source .env && set +a", file=sys.stderr)
        raise SystemExit(1)

    uuid, name = find_experiment(args.identifier, args.project, api_key)
    print(f"{uuid} {name}")


if __name__ == "__main__":
    main()
