#!/usr/bin/env python3
"""CNF-0117 subject: a permission/credential consumer that fails loud.

Required:
  * env CNF_0117_TOKEN (synthetic fixture; never a live secret)
  * readable catalog path in CNF_0117_CATALOG
Optional enrichment:
  * writable directory CNF_0117_ENRICH_DIR — if denied, still emit an artifact
    marked degraded in its own body (not only in the log).

--mode silent is the planted mutant: missing token still reports success.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

TOKEN_ENV = "CNF_0117_TOKEN"
CATALOG_ENV = "CNF_0117_CATALOG"
ENRICH_ENV = "CNF_0117_ENRICH_DIR"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=("loud", "silent"), default="loud")
    args = ap.parse_args()
    out = Path(args.out)
    token = os.environ.get(TOKEN_ENV)
    catalog = os.environ.get(CATALOG_ENV)
    enrich = os.environ.get(ENRICH_ENV)

    if not token:
        if args.mode == "silent":
            _write(
                out,
                {
                    "consumer": "CNF-0117-subject",
                    "degraded": False,
                    "missing_capability": None,
                    "state": "SUCCESS",
                    "message": "ok",
                },
            )
            print("ok")
            return 0
        print(
            f"FAILED:missing-capability credential:{TOKEN_ENV}",
            file=sys.stderr,
        )
        return 2

    if not catalog:
        print("FAILED:missing-capability permission:catalog-read", file=sys.stderr)
        return 2
    cat_path = Path(catalog)
    try:
        raw = cat_path.read_text(encoding="utf-8")
        json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(
            f"FAILED:missing-capability permission:catalog-read path={cat_path} err={type(exc).__name__}",
            file=sys.stderr,
        )
        return 2

    missing = None
    if enrich:
        enrich_path = Path(enrich)
        marker = enrich_path / "enrichment.json"
        try:
            enrich_path.mkdir(parents=True, exist_ok=True)
            marker.write_text('{"enrichment":true}\n', encoding="utf-8")
        except OSError:
            missing = "permission:enrichment-write"

    degraded = missing is not None
    doc = {
        "consumer": "CNF-0117-subject",
        "degraded": degraded,
        "missing_capability": missing,
        "state": "DEGRADED" if degraded else "SUCCESS",
        "message": (
            f"artifact marked degraded: missing {missing}"
            if degraded
            else "all required dependencies present"
        ),
    }
    try:
        _write(out, doc)
    except OSError as exc:
        print(
            f"FAILED:missing-capability permission:artifact-write err={type(exc).__name__}",
            file=sys.stderr,
        )
        return 2
    print(doc["message"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
