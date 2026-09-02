#!/usr/bin/env python3
"""Named probe 2: schema, sentinel, recorded evidence, live re-run, no private keys."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402
import schema_check as SC  # noqa: E402
from verifier import VARIANT_ERROR_CODES  # noqa: E402

OUT = "command-center/confirmation/CNF-0110-signature-negative-control.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SECRET_RE = re.compile(
    r"BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY|private_key|secret_key|"
    r"publisher_private|builder_private",
    re.IGNORECASE,
)


def catalog_sentinel() -> str:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "CNF-0110":
            return str(unit["completion_sentinel"])
    raise SystemExit("FAILED:CNF-0110-probe2 catalog unit missing")


def negative_control(doc: dict) -> dict | None:
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("negative_control"), dict):
        return report["negative_control"]
    if isinstance(doc.get("negative_control"), dict):
        return doc["negative_control"]
    extensions = doc.get("extensions")
    if isinstance(extensions, dict) and isinstance(extensions.get("negative_control"), dict):
        return extensions["negative_control"]
    return None


def main() -> int:
    out = REPO / OUT
    if not out.is_file() or out.stat().st_size <= 0:
        print("FAILED:CNF-0110-probe2 artifact absent")
        return 1
    try:
        text = out.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"FAILED:CNF-0110-probe2 unparseable {type(exc).__name__}")
        return 1
    sentinel = catalog_sentinel()
    if sentinel not in text:
        print("FAILED:CNF-0110-probe2 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0110-probe2 self-declared:{doc.get('state')}")
        return 1
    if SECRET_RE.search(text):
        print("FAILED:CNF-0110-probe2 private-key-shaped material in artifact")
        return 1
    errs = SC.error_messages(doc)
    if errs:
        print("FAILED:CNF-0110-probe2 schema errors")
        for line in errs[:12]:
            print(" ", line)
        return 1
    if not SC.rejects_garbage():
        print("FAILED:CNF-0110-probe2 schema accepted garbage")
        return 1
    report = doc.get("report")
    if not isinstance(report, dict) or report.get("kind") != "security-report":
        print("FAILED:CNF-0110-probe2 report.kind is not security-report")
        return 1
    nc = negative_control(doc)
    if not isinstance(nc, dict):
        print("FAILED:CNF-0110-probe2 negative_control missing")
        return 1
    variants = nc.get("variants") or []
    if len(variants) != 3:
        print("FAILED:CNF-0110-probe2 expected 3 variants")
        return 1
    codes = [str(v.get("error_code") or "") for v in variants if isinstance(v, dict)]
    exits = [int(v.get("exit_code")) for v in variants if isinstance(v, dict)]
    if sorted(codes) != sorted(VARIANT_ERROR_CODES):
        print(f"FAILED:CNF-0110-probe2 error_codes {codes}")
        return 1
    if len(set(exits)) != 3 or any(code == 0 for code in exits):
        print(f"FAILED:CNF-0110-probe2 exit_codes {exits}")
        return 1
    if not all(v.get("rejected") is True for v in variants if isinstance(v, dict)):
        print("FAILED:CNF-0110-probe2 a recorded variant was not rejected")
        return 1
    control = nc.get("untampered") or {}
    if not (control.get("verified") is True and int(control.get("exit_code", 1)) == 0):
        print("FAILED:CNF-0110-probe2 recorded control did not verify")
        return 1
    if nc.get("same_invocation") is not True:
        print("FAILED:CNF-0110-probe2 recorded run was not same_invocation")
        return 1
    live = M.run_matrix()
    if not live.get("contract_holds"):
        print(f"FAILED:CNF-0110-probe2 live rerun {live.get('classification')}")
        return 1
    print(
        f"schema_ok=True sentinel_ok=True recorded_distinguishable=True "
        f"live_rerun=True invocation_recorded={nc.get('invocation_id')} "
        f"invocation_live={live['invocation_id']}"
    )
    print("SUCCESS:CNF-0110-probe2 schema evidence live-rerun")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
