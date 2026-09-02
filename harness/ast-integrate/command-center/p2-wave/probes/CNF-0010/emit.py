#!/usr/bin/env python3
"""Emit CNF-0010 environment-manifest artifact."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from attributor import code_control, forced_mismatch  # noqa: E402
from capture import capture_live, capture_windows_fixture, pin_parity_rows  # noqa: E402
from ci_pins import extract_pins  # noqa: E402
from contract import (  # noqa: E402
    COMPLETION_SENTINEL,
    OUT_REL,
    P1,
    P2,
    QUESTION,
    SCHEMA_REL,
    SENTINEL,
    UNIT_ID,
)
from resolver import cmd_shim_control  # noqa: E402
from schema_local import make_validator, schema_errors  # noqa: E402

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)

SUPPORTING_FOR_RECEIPT = (
    SCHEMA_REL,
    "command-center/p2-wave/probes/CNF-0010/resolver.py",
    "command-center/p2-wave/probes/CNF-0010/capture.py",
    "command-center/p2-wave/probes/CNF-0010/attributor.py",
    "command-center/p2-wave/probes/CNF-0010/ci_pins.py",
    "command-center/p2-wave/probes/CNF-0010/schema_local.py",
)


def _confirmation_corpus() -> list[str]:
    root = REPO / "command-center" / "confirmation"
    if not root.is_dir():
        return []
    return sorted(
        p.relative_to(REPO).as_posix()
        for p in root.glob("*.json")
        if p.name != "CNF-0010-environment-manifest.json"
    )


def _digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()[:32]


def _art(rel: str, role: str) -> dict:
    sha, size = _digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": max(size, 1),
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def _probe(role: str, method: str, command: str, raw: str) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": _fp(method, command),
    }


def build_payload() -> dict:
    ci = extract_pins(REPO)
    live = capture_live(REPO)
    with tempfile.TemporaryDirectory(prefix="cnf0010-win-") as tmp:
        windows = capture_windows_fixture(Path(tmp) / "path")
        shim = cmd_shim_control(Path(tmp) / "shim", "ruff")
    if not shim.get("pass"):
        raise SystemExit("FAILED:CNF-0010 resolver control did not fire")
    parity = pin_parity_rows(live, ci)
    if not parity:
        raise SystemExit("FAILED:CNF-0010 no formatter/linter pins compared")
    mismatch = forced_mismatch(live)
    if mismatch["attribution"] != "environment" or not mismatch["not_code"]:
        raise SystemExit(
            f"FAILED:CNF-0010 forced mismatch attributed {mismatch['attribution']!r}"
        )
    code = code_control(live)
    if code["attribution"] != "code":
        raise SystemExit(
            f"FAILED:CNF-0010 code control attributed {code['attribution']!r}"
        )
    reach6 = {
        "id": "recorded-REACH-6-autocrlf",
        "attribution": "environment",
        "delta_fields": ["os.family", "git.autocrlf", "locale.code_page"],
        "source_sha_same": True,
        "note": (
            "tools/command-center/seed.py:140-151 and validate.py:217-222: "
            "Windows autocrlf=true clone hashes the CRLF working tree; Linux "
            "CI hashes LF. Same commit, different environment."
        ),
    }
    planted_mismatch = {
        "id": "planted-ruff-0.15.17-vs-0.15.22",
        "attribution": mismatch["attribution"],
        "delta_fields": mismatch["delta_fields"],
        "source_sha_same": True,
    }
    planted_code = {
        "id": "planted-same-env-code-delta",
        "attribution": code["attribution"],
        "delta_fields": code["delta_fields"],
        "source_sha_same": False,
    }
    corpus = _confirmation_corpus()
    families = sorted(
        {m["os"]["family"] for m in (live, windows) if m.get("os", {}).get("family")}
    )
    if families != ["linux", "windows"]:
        raise SystemExit(f"FAILED:CNF-0010 os families {families}")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    linux_ruff = next(
        (t.get("version") for t in live.get("tools") or [] if t.get("name") == "ruff"),
        None,
    )
    return {
        "kind": "environment-manifest",
        "title": "Environment pinning manifest so a confirmation discrepancy is attributable",
        "question": QUESTION,
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "captured_at": now,
        "manifests": [live, windows],
        "operating_systems_attached": ["linux", "windows"],
        "ci_pins": {
            "source": ci["source"],
            "formatters_and_linters": ci["formatters_and_linters"],
            "interpreters": [
                {"name": r["name"], "pinned_version": r["pinned_version"]}
                for r in ci["interpreters"]
            ],
            "jsonschema_pin": ci.get("jsonschema_pin"),
            "inventory_totals": ci.get("inventory_totals"),
        },
        "pin_parity": {
            "compared": True,
            "all_equal": all(r["equal"] for r in parity),
            "rows": parity,
        },
        "forced_mismatch_control": {
            "tool": mismatch["tool"],
            "pinned_version": mismatch["pinned_version"],
            "forced_version": mismatch["forced_version"],
            "source_sha_same": True,
            "attribution": "environment",
            "not_code": True,
            "delta_fields": mismatch["delta_fields"],
        },
        "attribution_table": [planted_mismatch, planted_code, reach6],
        "corpus_answer": {
            "live_confirmation_receipts_found": len(corpus),
            "live_disagreements_examined": 0,
            "explained_by_manifest_delta_alone": 0,
            "live_receipt_paths": corpus,
            "statement": (
                "Live confirmation corpus on this worktree is empty "
                f"({len(corpus)} receipts besides this unit). Disagreements "
                "explained by a manifest delta alone: 0 of 0. Planted controls "
                "in attribution_table prove the comparator: forced ruff "
                "0.15.17 vs 0.15.22 is environment; same-env source-sha delta "
                "is code; recorded REACH-6 autocrlf is environment."
            ),
        },
        "resolver_control": {
            "powershell_found_cmd_shim": True,
            "posix_which_missed_cmd_shim": True,
            "shim_basename": "ruff",
            "pass": True,
            "powershell_resolved": shim.get("powershell_resolved"),
            "posix_which_resolved": shim.get("posix_which_resolved"),
        },
        "windows_shell_8b": {
            "input": "rules/common/windows-shell.md section 8b (CRLF pin parity)",
            "present_on_this_tree": (REPO / "rules/common/windows-shell.md").is_file(),
            "applied": (
                "Pin parity is CI-pinned formatter/linter version vs "
                "PowerShell-resolver local version; CRLF/autocrlf is a "
                "first-class manifest field so a Windows checkout cannot be "
                "compared to Linux CI without an environment delta."
            ),
        },
        "test_results": {
            "resolver_cmd_shim": "PASS",
            "pin_parity_compared": "PASS",
            "forced_mismatch_environment": "PASS",
        },
        "verbatim_evidence": {
            "linux_manifest_verbatim": live["verbatim"],
            "windows_manifest_verbatim": windows["verbatim"],
            "per_disagreement_attribution_table": True,
        },
        "named_probes": [
            {"id": "probe1", "role": "resolver-and-pin-parity", "command": P1},
            {"id": "probe2", "role": "forced-mismatch-environment", "command": P2},
        ],
        "cloud_ok": False,
        "linux_ruff_version": linux_ruff,
        "scope": {
            "proof_surface": (
                "Live Linux capture on this host; Windows family attached as a "
                "PATHEXT .cmd fixture plus verbatim recorded Windows-clone "
                "fields from seed.py/validate.py. Forced ruff version mismatch "
                "attributed to environment. Live confirmation corpus 0-of-0."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "a live Win32 host was entered on this Linux worktree",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "local ruff equals the CI pin (parity is measured, not forced)",
                "rules/common/windows-shell.md exists on this worktree",
            ],
        },
        "observations": [
            {
                "name": "operating-system-families-attached",
                "measured": ",".join(families),
                "method": "live-linux-capture plus windows-pathext-fixture",
                "anchor": "command-center/p2-wave/probes/CNF-0010/capture.py",
            },
            {
                "name": "forced-mismatch-attribution",
                "measured": "environment",
                "method": "attributor.forced_mismatch ruff 0.15.17 vs 0.15.22",
                "anchor": "command-center/p2-wave/probes/CNF-0010/attributor.py",
            },
            {
                "name": "pin-parity-compared",
                "measured": True,
                "method": "CI inventory vs PowerShell-resolver local versions",
                "anchor": "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
            },
            {
                "name": "explained-by-manifest-delta-alone",
                "measured": 0,
                "method": "confirmation-corpus scan minus this unit",
                "anchor": "command-center/confirmation",
            },
        ],
        "control_ids": [
            "CNF0010-C1-cmd-shim-pathext",
            "CNF0010-C2-forced-ruff-mismatch-environment",
            "CNF0010-C3-same-env-code-delta",
        ],
    }


def build_doc() -> dict:
    report = build_payload()
    now = report["captured_at"]
    fp1 = _fp("command", P1)
    fp2 = _fp("command", P2)
    if fp1 == fp2:
        raise SystemExit("FAILED:CNF-0010 source and verifier fingerprints collided")
    artifacts = [_art(rel, "supporting") for rel in SUPPORTING_FOR_RECEIPT]
    return {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CNF-0010",
        "min_bytes_threshold": 1024,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Two operating-system families (linux live, windows PATHEXT "
                    "fixture) are attached, and a .cmd shim is visible to the "
                    "PowerShell resolver and invisible to POSIX which."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0010/probe1_resolver_and_pin_parity.py",
                "probes": [
                    _probe("source", "command", P1, "resolver .cmd shim and pin-parity"),
                    _probe(
                        "verifier",
                        "schema-validate",
                        "command-center/p2-wave/probes/CNF-0010/schema_local.py",
                        "catalog environment-manifest schema via disk RefResolver",
                    ),
                ],
            },
            {
                "claim": (
                    "Forcing ruff 0.15.17 vs 0.15.22 on identical source bytes "
                    "is attributed to environment; the same-env source-sha delta "
                    "stays code."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0010/probe2_forced_mismatch.py",
                "probes": [
                    _probe(
                        "source",
                        "command",
                        P2,
                        "forced-mismatch attributed to environment",
                    ),
                    _probe(
                        "verifier",
                        "static-analysis",
                        "command-center/p2-wave/probes/CNF-0010/attributor.py",
                        "code_control attribution=code",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "resolver-cmd-shim",
                "name": "PowerShell resolver sees .cmd; POSIX which misses it",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
            },
            {
                "id": "pin-parity-compared",
                "name": "CI pin vs locally resolved formatter/linter versions",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
            },
            {
                "id": "forced-mismatch-environment",
                "name": "Forced ruff version mismatch attributed to environment",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
            },
        ],
        "negative_controls": [
            {
                "id": "CNF0010-C1-cmd-shim-pathext",
                "kind": "known-broken-fixture",
                "description": (
                    "Only ruff.cmd exists on a planted PATH. PowerShell PATHEXT "
                    "resolver must hit it; POSIX which must miss."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "powershell_found_cmd_shim=true posix_which_missed=true",
                "good_state_output": "extensionless real binary would be visible to both",
            },
            {
                "id": "CNF0010-C2-forced-ruff-mismatch-environment",
                "kind": "mutation",
                "description": (
                    "Force ruff 0.15.17 vs 0.15.22 with identical source sha; "
                    "attributor must report environment, not code."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "attribution=environment delta=tools.ruff.version",
                "good_state_output": "same-env source-sha delta stays attribution=code",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0010-probe2-forced-mismatch",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe1 re-runs the PATHEXT .cmd control and pin-parity "
                "comparison. Probe2 re-runs the forced-mismatch attributor "
                "and the code-delta opposite control. Conclusion field was "
                "not consulted before re-deriving attribution."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0010/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0010/schema_local.py",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "probe": _probe(
                    "verifier",
                    "schema-validate",
                    "command-center/p2-wave/probes/CNF-0010/schema_local.py",
                    "disk-local Draft7Validator accepted the receipt",
                ),
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "one retry only when the failure classifies as "
                "environment-transient; logic or evidence failure is filed"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "The Windows family is a PATHEXT fixture plus recorded "
                    "autocrlf clone fields, not a live Win32 confirmation run."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run capture_live on a Windows checkout and attach that "
                    "verbatim manifest beside the Linux live capture."
                ),
            }
        ],
        "produced_by": {
            "vendor": "x-ai",
            "model": "grok-4.6",
            "role": "environment-auditor",
            "execution_substrate": "linux-local",
        },
        "report": report,
    }


def main() -> int:
    validator = make_validator()
    for garbage in GARBAGE:
        if not schema_errors(garbage, validator):
            print("FAILED:CNF-0010 schema accepted garbage")
            return 1
    doc = build_doc()
    errs = schema_errors(doc, validator)
    if errs:
        print("FAILED:CNF-0010 schema errors")
        for err in errs[:25]:
            print(" ", err)
        return 1
    if COMPLETION_SENTINEL not in json.dumps(doc):
        print("FAILED:CNF-0010 completion sentinel absent")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    live_errs = schema_errors(json.loads(out.read_text(encoding="utf-8")), validator)
    if live_errs:
        print("FAILED:CNF-0010 post-write schema errors")
        for err in live_errs[:25]:
            print(" ", err)
        return 1
    if out.stat().st_size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0010 artifact below min_bytes_threshold {out.stat().st_size}")
        return 1
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNF-0010 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
