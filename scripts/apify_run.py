"""Run an Apify actor synchronously and save dataset items to JSON.

Usage: python scripts/apify_run.py <actor_id> <input.json> <output.json> <max_charge_usd>
Token is read from .env (APIFY_TOKEN) and never printed.
"""
import json
import pathlib
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent


def token():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("APIFY_TOKEN="):
            return line.split("=", 1)[1].strip()
    sys.exit("APIFY_TOKEN not found in .env")


def main():
    actor, inp, out, cap = sys.argv[1:5]
    qs = urllib.parse.urlencode({"token": token(), "maxTotalChargeUsd": cap, "timeout": 600})
    url = f"https://api.apify.com/v2/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items?{qs}"
    body = pathlib.Path(inp).read_bytes()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=700) as r:
        items = json.loads(r.read().decode("utf-8"))
    pathlib.Path(out).write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(items)} items -> {out}")


if __name__ == "__main__":
    main()
