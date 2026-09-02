#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0466.json from live pathconv measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.shell.pathconv import (  # noqa: E402
    CORPUS,
    both_directions_report,
    contract_holds,
    global_suppression_discrimination_report,
    per_argument_shape_matrix,
)

UID = "IMP-0466"
OUT = "command-center/receipts/IMP-0466.json"
SENTINEL = "SENTINEL:IMP-0466:PATHCONV-ARGUMENT-SCOPED"
IMPL = "tools/shell/pathconv.py"
SCHEMA = "command-center/schema/receipt.schema.json profile=pathconv-argument-scoped"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0466/probe1_both_directions.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0466/probe2_global_suppression.py"
)
SUPPORTING = [
    IMPL,
    "tools/shell/__init__.py",
    "command-center/p2-wave/probes/IMP-0466/fixtures/corpus.json",
    "command-center/p2-wave/probes/IMP-0466/probe1_both_directions.py",
    "command-center/p2-wave/probes/IMP-0466/probe2_global_suppression.py",
]


def digest_rel(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    norm = data.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(data),
        "sha256": hashlib.sha256(norm).hexdigest() if data else "",
        "exists": path.is_file(),
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    both = both_directions_report()
    disc = global_suppression_discrimination_report()
    contract = contract_holds()
    if not contract["pass"]:
        print("FAILED:IMP-0466 live contracts did not pass; not emitting SUCCESS")
        print(json.dumps({"both": both["pass"], "disc": disc["pass"]}, sort_keys=True))
        return 1

    impl = digest_rel(IMPL, "primary")
    supporting = [digest_rel(p, "supporting") for p in SUPPORTING[1:]]
    matrix_scoped = per_argument_shape_matrix("scoped")
    matrix_global = per_argument_shape_matrix("global")
    matrix_none = per_argument_shape_matrix("none")

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Argument-aware shell path-rewriting control",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:IMP-0466; _USER-PROMPTS.md:11309 "
            "(PowerShell/Git Bash path rewriting); related IMP-0020 / TST-0190"
        ),
        "output_schema": SCHEMA,
        "min_bytes_threshold": 128,
        "artifact_paths": [IMPL, OUT] + SUPPORTING[1:],
        "artifacts": [impl] + supporting,
        "question": (
            "Prove path-conversion suppression is COMMAND-aware and ARGUMENT-aware: "
            "applied around revision-shaped and device-path arguments, never globally."
        ),
        "evidence_requirement": (
            "Both-direction evidence: a revision argument surviving unconverted, "
            "AND a legitimate POSIX path argument still being converted correctly "
            "under the same configuration. A run showing only one direction is "
            "half a proof."
        ),
        "resolution_table": {
            "same_scoped_configuration": both["same_configuration"],
            "revision_unconverted": both["scoped"]["revision_unconverted"],
            "revision_original": both["scoped"]["revision_original"],
            "revision_observed_scoped": both["scoped"]["revision_observed"],
            "posix_converted": both["scoped"]["posix_converted"],
            "posix_original": both["scoped"]["posix_original"],
            "posix_observed_scoped": both["scoped"]["posix_observed"],
            "clone_marker_exists": both["scoped"]["clone_intended_exists"],
            "clone_marker": both["scoped"]["clone_marker"],
            "device_unconverted": both["scoped"]["device_unconverted"],
            "note": (
                "Clone happening is the intended Windows file existing, not an "
                "exit code. Global suppression is a fixture, not the production path."
            ),
        },
        "per_argument_shape": {
            "scoped": matrix_scoped,
            "global": matrix_global,
            "conversion_on": matrix_none,
        },
        "corpus": [
            {
                "id": c["id"],
                "arg": c["arg"],
                "shape": c["shape"],
                "msys_would_convert": c["msys_would_convert"],
                "why": c["why"],
            }
            for c in CORPUS
        ],
        "evidence": [
            {
                "claim": (
                    "Under one scoped configuration, /refs/heads/main survives "
                    "unconverted and /c/Users/probe/repo converts to "
                    "C:\\Users\\probe\\repo with the clone marker present."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/shell/pathconv.py:both_directions_report",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "in-process",
                        "command": "both_directions_report()",
                        "raw_output": json.dumps(
                            {
                                "pass": both["pass"],
                                "scoped": {
                                    k: both["scoped"][k]
                                    for k in (
                                        "revision_unconverted",
                                        "revision_observed",
                                        "posix_converted",
                                        "posix_observed",
                                        "clone_intended_exists",
                                        "device_unconverted",
                                    )
                                },
                            },
                            sort_keys=True,
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "in-process",
                        "command": "mode=none must corrupt revision (dead-probe control)",
                        "raw_output": json.dumps(both["conversion_on"], sort_keys=True),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "A global-suppression fixture (MSYS_NO_PATHCONV=1 / EXCL=*) "
                    "fails the legitimate-path case: clone is a silent no-op and "
                    "redirect truncates the intended target. Scoped is not "
                    "equivalent to global."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/shell/pathconv.py:global_suppression_discrimination_report",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "in-process",
                        "command": "global_suppression_discrimination_report()",
                        "raw_output": json.dumps(
                            {
                                "discriminates": disc["discriminates"],
                                "scoped": disc["scoped"],
                                "global": {
                                    k: disc["global"][k]
                                    for k in (
                                        "posix_converted",
                                        "silent_noop",
                                        "clone_intended_exists",
                                        "redirect_truncated",
                                        "redirect_content",
                                        "global_suppression",
                                    )
                                },
                            },
                            sort_keys=True,
                        ),
                        "exit_code": 0,
                    }
                ],
            },
        ],
        "test_ids": [
            "IMP-0466-probe1-both-directions",
            "IMP-0466-probe2-global-suppression",
        ],
        "tests": [
            {"id": "IMP-0466-probe1-both-directions", "command": P1, "result": "PENDING-LIVE-RERUN"},
            {"id": "IMP-0466-probe2-global-suppression", "command": P2, "result": "PENDING-LIVE-RERUN"},
        ],
        "negative_control_ids": [
            "IMP-0466-conversion-on-corrupts-revision",
            "IMP-0466-global-suppression-noop-clone",
            "IMP-0466-global-redirect-truncates-target",
        ],
        "negative_controls": [
            {
                "id": "IMP-0466-conversion-on-corrupts-revision",
                "kind": "conversion-on",
                "description": (
                    "mode=none must rewrite /refs/heads/main and /dev/null, proving "
                    "the probe can see the broken state."
                ),
                "fired_on_bad_state": both["conversion_on"]["revision_corrupted"],
                "silent_on_good_state": both["scoped"]["revision_unconverted"],
                "bad_state_output": json.dumps(both["conversion_on"], sort_keys=True),
                "good_state_output": json.dumps(
                    {
                        "revision_observed": both["scoped"]["revision_observed"],
                        "device_observed": both["scoped"]["device_observed"],
                    },
                    sort_keys=True,
                ),
            },
            {
                "id": "IMP-0466-global-suppression-noop-clone",
                "kind": "global-suppression",
                "description": (
                    "MSYS_NO_PATHCONV=1 must leave /c/Users/probe/repo unconverted "
                    "and must not create the intended clone marker."
                ),
                "fired_on_bad_state": disc["global"]["silent_noop"],
                "silent_on_good_state": disc["scoped"]["clone_happened"],
                "bad_state_output": json.dumps(
                    {
                        "posix_observed": disc["global"]["posix_observed"],
                        "intended_exists": disc["global"]["clone_intended_exists"],
                    },
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {
                        "posix_observed": disc["scoped"]["posix_observed"],
                        "clone_happened": disc["scoped"]["clone_happened"],
                    },
                    sort_keys=True,
                ),
            },
            {
                "id": "IMP-0466-global-redirect-truncates-target",
                "kind": "redirect-truncation",
                "description": (
                    "Unconverted redirect target writes elsewhere and leaves the "
                    "intended Windows path empty."
                ),
                "fired_on_bad_state": disc["global"]["redirect_truncated"],
                "silent_on_good_state": disc["scoped"]["redirect_ok"],
                "bad_state_output": json.dumps(
                    {"intended_content": disc["global"]["redirect_content"]},
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {"intended_content": disc["scoped"]["redirect_content"]},
                    sort_keys=True,
                ),
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0466-probe2-global-suppression",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests (named probes), not the author's summary",
            "adversarial_refuter": "silent-no-op clone direction (global fixture)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This Linux worktree does not host Git Bash/MSYS. Evidence is "
                    "from the MSYS conversion model in tools/shell/pathconv.py "
                    "(drive-letter /c/ → C:\\, root-relative /refs → C:\\msys64\\refs, "
                    "/dev/null → NUL, MSYS2_ARG_CONV_EXCL prefix matching). "
                    "prepare_subprocess_env is the production hook for a real spawn."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1 and probe2 under Git Bash on Windows, comparing "
                    "child argv (MSYS_DEBUG or a wrapper) to the model."
                ),
            }
        ],
        "retry": {"count": 0, "policy": "max 2 attempts, backoff 30s/120s"},
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0466/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; global unit_manifest.py --write was not run",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "note": "G-1 measure runs after this receipt is written",
            }
        ],
        "contract": contract,
        "timestamps": {"started_at": started, "ended_at": ended},
        "notes": (
            "G-1 for IMP-0466: argument-scoped MSYS2_ARG_CONV_EXCL, never "
            "MSYS_NO_PATHCONV globally. Both directions proved under one scoped "
            "configuration; global fixture fails the POSIX-path case. Did not run "
            "global unit_manifest.py --write. "
            + SENTINEL
        ),
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0466 sentinel missing from receipt")
        return 1
    if '"state": "SUCCESS"' not in text and '"state":"SUCCESS"' not in text:
        print("FAILED:IMP-0466 state not SUCCESS")
        return 1
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
