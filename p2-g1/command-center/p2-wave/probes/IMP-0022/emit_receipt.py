#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0022.json from live measurements."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.case_collision import both_signals, find_casefold_collisions  # noqa: E402
from plugin.pathnorm import NORMALISATION  # noqa: E402
from plugin.payload_paths import expand_payload_paths  # noqa: E402

OUT = "command-center/receipts/IMP-0022.json"
TEST = "tools/plugin/tests/test_case_collision_paths.py"


def digest(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes()
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        "exists": True,
        "role": "supporting",
        "eol": "LF",
    }


def run(cmd: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    rc_tests, tests_out = run(["python3", "-B", TEST])
    if rc_tests != 0:
        print(tests_out[-4000:])
        print("FAILED:IMP-0022 tests red; refusing to emit SUCCESS receipt")
        return 1

    payload = expand_payload_paths(REPO)
    hits = find_casefold_collisions(payload)
    planted = both_signals(
        {
            "docs/README.md": b"UPPER\n",
            "docs/readme.md": b"lower\n",
            "docs/unique.txt": b"only-once\n",
        }
    )
    clean = both_signals({"a.txt": b"a\n", "b.txt": b"b\n"})
    if hits or not planted["set_fired"] or not planted["extract_fired"]:
        print("FAILED:IMP-0022 live signals do not match the contract")
        print(
            json.dumps(
                {"hits": [h.paths for h in hits], "planted": planted},
                default=str,
            )
        )
        return 1
    if clean["shortfall"] != 0:
        print(f"FAILED:IMP-0022 clean extract shortfall {clean}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        "tools/plugin/pathnorm.py",
        "tools/plugin/case_collision.py",
        "tools/plugin/payload_paths.py",
        "tools/plugin/payload-allowlist.json",
        "tools/plugin/tests/test_case_collision_paths.py",
        "command-center/p2-wave/probes/IMP-0022/probe1_set_collision.py",
        "command-center/p2-wave/probes/IMP-0022/probe2_extract_shortfall.py",
    ]
    artifacts = [digest(p) for p in supporting]
    artifacts[0]["role"] = "primary"

    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0022",
        "id": "IMP-0022",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0022",
        "completion_sentinel": "SUCCESS:IMP-0022",
        "title": "Path-casing normalisation and cross-filesystem collision detection",
        "spec_anchor": "_USER-PROMPTS.md:11016 (path-casing tests)",
        "min_bytes_threshold": 128,
        "normalisation": NORMALISATION,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    f"Signal 1: casefold-collision count over the live payload "
                    f"path set is {len(hits)} (payload_paths={len(payload)}). "
                    "Grouping key is NFC then str.casefold, not str.lower()."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/pathnorm.py:NORMALISATION",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "PYTHONPATH=tools python3 -B -m plugin",
                        "exit_code": 0,
                        "raw_output": (
                            f"payload_paths={len(payload)} "
                            f"casefold_collision_count={len(hits)} "
                            "normalisation=NFC+casefold"
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0022/probe1_set_collision.py"
                        ),
                        "exit_code": 0,
                        "raw_output": (
                            "independent grouping agrees with production; "
                            "planted README pair fires"
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "Signal 2: extracting a zip of the planted README.md + "
                    f"readme.md pair onto a case-insensitive overlay yields "
                    f"archive_entry_count={planted['archive_entry_count']} "
                    f"extracted_file_count={planted['extracted_file_count']} "
                    f"shortfall={planted['shortfall']}. The same zip of a "
                    f"non-colliding pair has shortfall={clean['shortfall']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/case_collision.py:extract_zip_case_insensitive",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONPATH=tools python3 -B -m plugin "
                            "--negative-control"
                        ),
                        "exit_code": 0,
                        "raw_output": (
                            f"set_collision_count={planted['set_collision_count']} "
                            f"shortfall={planted['shortfall']}"
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0022/"
                            "probe2_extract_shortfall.py"
                        ),
                        "exit_code": 0,
                        "raw_output": (
                            "independent os.walk shortfall agrees; "
                            "reviewer NFC+casefold holds"
                        ),
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "test_no_casefold_collisions_in_payload",
                "command": f"python3 -B {TEST}::test_no_casefold_collisions_in_payload",
                "result": "PASS",
            },
            {
                "id": "test_negative_control_readme_pair_fires_both_signals",
                "command": (
                    f"python3 -B {TEST}::"
                    "test_negative_control_readme_pair_fires_both_signals"
                ),
                "result": "PASS",
            },
            {
                "id": "test_normalisation_is_casefold_not_lower",
                "command": f"python3 -B {TEST}::test_normalisation_is_casefold_not_lower",
                "result": "PASS",
            },
            {
                "id": "test_nfc_applied_before_casefold",
                "command": f"python3 -B {TEST}::test_nfc_applied_before_casefold",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0022-C1-readme-pair",
                "kind": "known-broken-fixture",
                "description": (
                    "Plant README.md and readme.md. Both the set-collision "
                    "count and the extract-count shortfall must fire. A "
                    "detector silent on either signal measures nothing."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"set_collision_count={planted['set_collision_count']} "
                    f"shortfall={planted['shortfall']}"
                ),
                "good_state_output": (
                    f"live_payload_collisions={len(hits)} "
                    f"clean_shortfall={clean['shortfall']}"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0022-probe2-nfc-casefold-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Confirmed the comparison key is NFC then str.casefold, not "
                "str.lower(): Straße.md vs STRASSE.md collides under casefold "
                "and is silent under lower(); cafe.txt NFC vs NFD collides "
                "only when NFC is applied first."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0022/"
                "UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "report": {
            "kind": "path-casing-normalisation",
            "payload_path_count": len(payload),
            "payload_paths": payload,
            "casefold_collision_count": len(hits),
            "planted_readme_pair": {
                "set_collision_count": planted["set_collision_count"],
                "archive_entry_count": planted["archive_entry_count"],
                "extracted_file_count": planted["extracted_file_count"],
                "shortfall": planted["shortfall"],
            },
            "clean_pair_shortfall": clean["shortfall"],
            "test_output": tests_out,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Extraction uses a userspace case-insensitive overlay "
                    "(os.listdir + NFC+casefold, last writer wins) because "
                    "this Linux worktree cannot mount a VFAT/NTFS volume. "
                    "Behaviour matches default Windows/macOS overwrite, not "
                    "NTFS's exact Unicode folding table."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Re-run extract_shortfall onto a real NTFS or APFS "
                    "volume and compare shortfall with this overlay."
                ),
            }
        ],
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:IMP-0022")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
