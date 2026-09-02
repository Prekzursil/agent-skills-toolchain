#!/usr/bin/env python3
"""Probe 1: planted breaking change under PATCH is rejected; genuine PATCH accepted."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from suite import (  # noqa: E402
    genuine_patch_pair,
    materialize_fixtures,
    planted_breaking_pair,
    _indep_patch,
    _indep_planted,
)

ART = REPO / "command-center/receipts/TST-0046.json"
SCHEMA = REPO / "command-center/schema/conformance-report.schema.json"
GATE = HERE / "gate.py"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0046-probe1 {msg}")
    return 1


def run_gate(old: Path, new: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(GATE),
            "--old",
            str(old),
            "--new",
            str(new),
            "--class",
            "schema",
            "--from-version",
            "1.2.3",
            "--to-version",
            "1.2.4",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    try:
        body = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return proc.returncode, {"raw": (proc.stdout or "") + (proc.stderr or "")}
    return proc.returncode, body


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0046" not in text:
        return fail("sentinel absent")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")

    fixtures = materialize_fixtures()
    p_old, p_new = planted_breaking_pair()
    g_old, g_new = genuine_patch_pair()
    if not _indep_planted(p_old, p_new):
        return fail("planted pair is not an independent enum narrowing")
    if not _indep_patch(g_old, g_new):
        return fail("genuine pair is not description-only")

    p_code, p_body = run_gate(REPO / fixtures["planted_old"], REPO / fixtures["planted_new"])
    g_code, g_body = run_gate(REPO / fixtures["genuine_old"], REPO / fixtures["genuine_new"])

    if p_code != 2 or p_body.get("decision") != "REJECT" or p_body.get("required_bump") != "MAJOR":
        return fail(f"planted not rejected {p_code} {p_body}")
    if "narrowed_enum" not in (p_body.get("kinds") or []):
        return fail(f"planted kinds {p_body.get('kinds')}")
    if g_code != 0 or g_body.get("decision") != "ACCEPT" or g_body.get("required_bump") != "PATCH":
        return fail(f"genuine not accepted {g_code} {g_body}")
    if "description_change" not in (g_body.get("kinds") or []):
        return fail(f"genuine kinds {g_body.get('kinds')}")

    ans = doc.get("answer") or {}
    if not ans.get("breaking_under_patch_rejected") or not ans.get("genuine_patch_accepted"):
        return fail("artifact answer does not record both evidence legs")
    print(
        json.dumps(
            {
                "planted_exit": p_code,
                "planted_decision": p_body.get("decision"),
                "planted_required": p_body.get("required_bump"),
                "genuine_exit": g_code,
                "genuine_decision": g_body.get("decision"),
                "genuine_required": g_body.get("required_bump"),
                "semver": "1.2.3->1.2.4",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0046-probe1 planted-breaking-rejected genuine-patch-accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
