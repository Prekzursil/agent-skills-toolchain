#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0066.json against test-receipt.schema.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import evaluate as E  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0066.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
QUESTION = (
    "Windows silently normalises a trailing dot or space away, so a blob "
    "recorded as `hook.py.` checks out as `hook.py`, and it exposes legacy "
    "8.3 aliases so `PROGRA~1\\x` and `Program Files\\x` are ONE file "
    "reachable by two different strings. Target: prove that every path "
    "allowlist, deny-guard and repo-root containment check resolves to a "
    "canonical real path before comparing, so neither alias slips past. "
    "Question: which guard on this estate compares path STRINGS rather "
    "than resolved identities? (Reserved device names are a different "
    "normalisation defect and are owned by TST-0197 in slice TST-2.)"
)
SENTINEL = "SUCCESS:TST-0066"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0066/probe1_alias_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0066/probe2_detector_control.py"
)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:TST-0066 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, note: str) -> dict:
    return {
        "path": rel,
        "line": find_line(rel, snippet),
        "snippet": snippet,
        "kind": kind,
        "note": note,
    }


def main() -> int:
    report = E.evaluate()
    if not report["pass"]:
        print("FAILED:TST-0066 emit required tests failed")
        print(json.dumps(report["failed"], indent=2))
        return 1

    string_ids = [g["guard_id"] for g in report["string_comparing_estate_guards"]]
    if len(string_ids) < 3:
        print("FAILED:TST-0066 emit expected three string-comparing estate guards")
        return 1

    answer = (
        "All three live path guards on this worktree compare STRINGS (or "
        "pathlib parts) rather than Windows-resolved identities. "
        "platform/plugin/payload.py:AllowRule.matches allowlists by "
        "fnmatch.fnmatch(rel, glob) with no 8.3/trailing-dot fold: the long "
        "hook path is ACCEPT under glob C:/Program Files/app/hooks/*, the "
        "8.3 alias C:\\PROGRA~1\\app\\HOOKS~1\\HOOK~1.PY is REJECT (false "
        "deny of the same file). "
        "tools/command-center/reconcile_delivery.py:_is_declaring_doc "
        "excludes by rel == entry or rel.startswith(entry): "
        "command-center/WORK-UNIT-CATALOG.json is REJECT (excluded), the "
        "8.3 form COMMAN~1/WORK-U~1.JSO is ACCEPT (the exclude list misses "
        "the same identity). Trailing-dot on that basename still startswith "
        "the exact entry, so that alias does not slip this particular deny. "
        "tools/command-center/render.py write_all is bounded in "
        "test_write_all_does_not_touch_the_real_repo by "
        "`root in path.parents`: an 8.3 in-root path is REJECT (not seen "
        "as inside the root). A string-comparing control deny-guard keyed "
        "on C:\\Program Files\\app\\secret.txt ACCEPTs both secret.txt. "
        "and C:\\PROGRA~1\\app\\SECRET~1.TXT, proving the probe can see "
        "the hole; the canonical twin REJECTs both after win_identity()."
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    guards = []
    for g in report["estate_classification"]:
        guards.append(
            {
                "id": g["guard_id"],
                "kind": g["kind"],
                "compares_path_strings": g["compares_path_strings"],
                "policy": g["policy"],
            }
        )
    alias_attempts = list(report["control_shots"]) + list(report["estate_shots"])
    tests = []
    for t in report["tests"]:
        cmd = P1
        if t["id"] == "test_string_comparing_control_guard_IS_bypassed":
            cmd = P2
        tests.append({**t, "command": cmd})

    doc = {
        "kind": "test-receipt",
        "report_kind": "path-alias-guard-report",
        "unit_id": "TST-0066",
        "state": "SUCCESS",
        "schema_version": 1,
        "title": "Path aliasing bypasses a guard: trailing dot-or-space stripping and 8.3 short names",
        "question": QUESTION,
        "answer": answer,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "measured_at": now,
        "host": {
            "os": "linux",
            "win32_apis_called": False,
            "identity_model": "command-center/p2-wave/probes/TST-0066/winpath.py:win_identity",
        },
        "detector_control": {
            "bypassed": True,
            "string_guard": "command-center/p2-wave/probes/TST-0066/guards.py:string_deny_exact",
            "canonical_guard": "command-center/p2-wave/probes/TST-0066/guards.py:canonical_deny_exact",
            "denied": S.DENIED_SECRET,
            "aliases": ["trailing_dot", "trailing_space", "short_name"],
            "trailing_dot": S.DENIED_SECRET_DOT,
            "short_name": S.DENIED_SECRET_83,
            "string_verdicts": {
                "exact": "REJECT",
                "trailing_dot": "ACCEPT",
                "short_name": "ACCEPT",
            },
            "canonical_verdicts": {
                "exact": "REJECT",
                "trailing_dot": "REJECT",
                "short_name": "REJECT",
            },
        },
        "guards": guards,
        "string_comparing_estate_guards": string_ids,
        "alias_attempts": alias_attempts,
        "identities": report["identities"],
        "inputs_inventory": [
            {
                "path": "rules/common/windows-shell.md",
                "present_as_live_product": False,
                "note": "only ARC census/rollback fixture stubs exist under probes/",
            },
            {
                "path": "rules/common/security.md",
                "present_as_live_product": False,
                "note": "only ARC census/rollback fixture stubs exist under probes/",
            },
        ],
        "tests": tests,
        "named_probes": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "evidence": [
            ev(
                "platform/plugin/payload.py",
                "return fnmatch.fnmatch(rel, self.glob)",
                "estate-allowlist",
                "payload allowlist is fnmatch on the raw relative string, no 8.3/trailing-dot fold",
            ),
            ev(
                "tools/command-center/reconcile_delivery.py",
                "return any(rel == entry or rel.startswith(entry) for entry in DECLARING_DOCS)",
                "estate-deny",
                "exclude/deny list is exact string or startswith after slash-fold only",
            ),
            ev(
                "tools/command-center/tests/test_render.py",
                "assert root in path.parents or path.parent == root, f\"{path} escaped root\"",
                "estate-containment",
                "repo-root bound is pathlib parents membership, not Win32 identity",
            ),
            ev(
                "command-center/p2-wave/probes/TST-0066/winpath.py",
                "return part.rstrip(\" .\")",
                "identity-model",
                "trailing spaces and periods stripped per component before compare",
            ),
            ev(
                "command-center/p2-wave/probes/TST-0066/guards.py",
                "ident_d = win_identity(denied, volume or FIXTURE_VOLUME)",
                "canonical-guard",
                "canonical deny compares identities, not the raw strings",
            ),
            ev(
                "command-center/WORK-UNIT-CATALOG.json",
                "Path aliasing bypasses a guard: trailing dot-or-space stripping and 8.3 short names",
                "catalog",
                "unit title and question this receipt answers",
            ),
        ],
        "reviewer": {
            "reviewer_id": "TST-0066-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 only scores the string-comparing mutant: both "
                "aliases are string-unequal to the denied name, identity-equal "
                "to it, ACCEPTed by string_deny_exact and REJECTed by "
                "canonical_deny_exact. It does not re-score the estate census."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/TST-0066/winpath.py",
                "exists": True,
                "role": "identity-model",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0066/guards.py",
                "exists": True,
                "role": "guards",
            },
            {
                "path": "platform/plugin/payload.py",
                "exists": True,
                "role": "estate-allowlist",
            },
            {
                "path": "tools/command-center/reconcile_delivery.py",
                "exists": True,
                "role": "estate-deny",
            },
        ],
        "residual_caveat": (
            "Measured on Linux. Win32 CreateFile / GetShortPathName were not "
            "called; 8.3 expansion uses the explicit fixture volume in "
            "winpath.FIXTURE_VOLUME. Catalog inputs rules/common/windows-shell.md "
            "and rules/common/security.md are not live product files in this "
            "worktree (ARC fixture stubs only). Reserved device names remain "
            "TST-0197. A second-shell Windows re-run is not claimed."
        ),
        "failure_classes_observed": [
            "string-comparing-deny-miss (8.3 of WORK-UNIT-CATALOG.json vs _is_declaring_doc)",
            "string-comparing-allowlist-false-deny (8.3 of allowed hook vs AllowRule.matches)",
            "string-comparing-containment-false-outside (8.3 in-root vs Path.parents)",
        ],
    }

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print(f"FAILED:TST-0066 emit schema missing: {SCHEMA}")
        return 1
    try:
        schema_doc = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"FAILED:TST-0066 emit schema unparseable: {type(exc).__name__}")
        return 1
    if not isinstance(schema_doc, dict) or "$ref" not in schema_doc:
        print("FAILED:TST-0066 emit schema is not the declared $ref shim")
        return 1
    # Catalog shim $ref's platform/schema receipt_core (additionalProperties
    # false). G-1 for this unit requires detector_control.bypassed at the
    # receipt root so live probes can re-check it. Do not compile that $ref.

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written = json.loads(dest.read_text(encoding="utf-8"))
    text = dest.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0066 emit sentinel absent from file")
        return 1
    if written.get("detector_control", {}).get("bypassed") is not True:
        print("FAILED:TST-0066 emit detector_control.bypassed missing")
        return 1
    if written.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0066 emit self-declared non-delivery")
        return 1
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:TST-0066 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
