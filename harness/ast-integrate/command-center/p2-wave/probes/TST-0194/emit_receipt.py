#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0194.json portability report."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0194.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0194/probe1_packer_exit_and_setsize.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0194/probe2_both_states_and_install_deferral.py"
)
QUESTION = (
    "Do two package entries differing only in case get rejected when the "
    "package is built, rather than colliding on the user's case-insensitive "
    "filesystem at install time? PASS requires the build to fail with both "
    "paths named."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(rel: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {"path": rel, "sha256": sha, "bytes": size}


def main() -> int:
    live = S.evaluate()
    if not live.get("pass"):
        print("FAILED:TST-0194 emit live measurement did not pass")
        print(json.dumps(live.get("gates"), indent=2))
        print(json.dumps(live.get("signal_a"), indent=2)[:4000])
        return 1

    sig_a = live["signal_a"]
    sig_b = live["signal_b"]
    nc = live["negative_control"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    src_probe = {
        "id": "probe1_packer_exit_and_setsize",
        "command": P1,
        "role": "packer-exit-and-independent-set-size",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0194/probe1_packer_exit_and_setsize.py"
        ),
    }
    ver_probe = {
        "id": "probe2_both_states_and_install_deferral",
        "command": P2,
        "role": "both-states-and-install-time-deferral-negative-control",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0194/probe2_both_states_and_install_deferral.py"
        ),
    }
    if src_probe["fingerprint"]["sha256"] == ver_probe["fingerprint"]["sha256"]:
        print("FAILED:TST-0194 emit source/verifier probe files identical")
        return 1

    doc = {
        "unit_id": "TST-0194",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "portability_report",
        "title": "Case-only duplicate manifest entries are caught at BUILD time",
        "question": QUESTION,
        "sentinel": "SUCCESS:TST-0194",
        "completion_sentinel": "SUCCESS:TST-0194",
        "overall_verdict": "PASS",
        "answer": (
            "Yes. tools/plugin/pack.py rejects colliding payload paths at BUILD "
            "(exit 2) and names both original paths. An independent NFC+casefold "
            "set-size comparison over the same manifest files list agrees. A "
            "case-distinct-but-non-colliding manifest packs. Deferring the check "
            "to install time (mutant packer) produces a successful build and "
            "therefore FAILS this test."
        ),
        "min_bytes_threshold": 2048,
        "ts": now,
        "platform": {
            "os": "linux",
            "filesystem": "case-sensitive",
            "note": (
                "Linux can store both README.md and readme.md. The packer still "
                "refuses, so a Windows/macOS install never sees the pair."
            ),
        },
        "normalisation": {
            "order": ["Unicode NFC", "str.casefold()"],
            "not": "str.lower()",
            "eszett_pair_proves_casefold_not_lower": True,
        },
        "source_probe": src_probe,
        "verifier_probe": ver_probe,
        "named_probes": [
            {"id": "probe1", "role": src_probe["role"], "command": P1},
            {"id": "probe2", "role": ver_probe["role"], "command": P2},
        ],
        "evidence": [
            {
                "id": "a",
                "kind": "packer-exit-status-and-message",
                "claim": (
                    "Live subprocess of tools/plugin/pack.py exits 2 and names "
                    "both colliding paths."
                ),
                "colliding_rc": sig_a["colliding"]["rc"],
                "colliding_both_paths_named": sig_a["colliding"]["both_paths_named"],
                "declared_only_rc": sig_a["declared_only"]["rc"],
                "declared_only_both_paths_named": sig_a["declared_only"]["both_paths_named"],
                "eszett_rc": sig_a["eszett"]["rc"],
                "eszett_both_paths_named": sig_a["eszett"]["both_paths_named"],
                "colliding_text_tail": sig_a["colliding"]["text_tail"],
            },
            {
                "id": "b",
                "kind": "independent-casefold-set-size",
                "claim": (
                    "len(manifest files) > len({NFC+casefold(p)}) on colliding "
                    "fixtures; equal on the clean fixture. Computed in scenario.py "
                    "without calling pack.collision_groups."
                ),
                "colliding_raw_count": sig_b["colliding"]["raw_count"],
                "colliding_folded_count": sig_b["colliding"]["folded_count"],
                "declared_only_raw_count": sig_b["declared_only"]["raw_count"],
                "declared_only_folded_count": sig_b["declared_only"]["folded_count"],
                "eszett_raw_count": sig_b["eszett"]["raw_count"],
                "eszett_folded_count": sig_b["eszett"]["folded_count"],
                "eszett_lower_count": sig_b["eszett"]["lower_count"],
                "clean_raw_count": sig_b["clean"]["raw_count"],
                "clean_folded_count": sig_b["clean"]["folded_count"],
            },
        ],
        "tests": {
            "colliding_manifest_rejected_at_build": {
                "pass": live["gates"]["colliding_build_rejected"],
                "paths": sig_b["colliding"]["paths"],
            },
            "declared_only_manifest_rejected_at_build": {
                "pass": live["gates"]["declared_build_rejected"],
                "note": "Staging has only README.md; manifest still lists readme.md.",
            },
            "casefold_not_lower_eszett": {
                "pass": live["gates"]["eszett_build_rejected"]
                and live["gates"]["eszett_proves_casefold_not_lower"],
                "paths": sig_b["eszett"]["paths"],
            },
            "both_states_clean_builds": {
                "pass": live["both_states"]["clean_manifest_builds"],
                "paths": live["both_states"]["clean_paths"],
            },
            "negative_control_install_deferral": {
                "pass": nc["fired_on_bad_state"] and nc["silent_on_good_state"],
                "id": nc["id"],
                "test_applied_to_mutant": nc["test_applied_to_mutant"],
                "mutant_build_rc": nc["mutant_build_rc"],
            },
        },
        "fixtures": {
            "colliding": "command-center/p2-wave/probes/TST-0194/fixtures/colliding/",
            "declared_only": "command-center/p2-wave/probes/TST-0194/fixtures/declared-only/",
            "clean": "command-center/p2-wave/probes/TST-0194/fixtures/clean/",
            "casefold_not_lower": "command-center/p2-wave/probes/TST-0194/fixtures/casefold-not-lower/",
        },
        "reviewer": {
            "reviewer_id": "TST-0194-probe2-both-states-and-install-deferral",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-packs the clean fixture and the install-time mutant; "
                "it does not reuse probe 1's colliding-subprocess assertions as "
                "its pass criterion. Catalog asked for a second Windows shell; "
                "this Linux worktree records that the second-shell reviewer was "
                "not executed here. Linux is sufficient to store both casings "
                "and to prove the build gate."
            ),
            "second_windows_shell": "NOT-RUN",
        },
        "residual_caveat": (
            "IMP-0002's full deterministic packer (git cat-file, pinned mtimes "
            "across three builds) is out of scope. This unit owns the BUILD-time "
            "casefold collision gate. cloud ok=true is not delivery."
        ),
        "scope": {
            "proof_surface": (
                "tools/plugin/pack.py NFC+casefold collision groups; colliding, "
                "declared-only, eszett, and clean fixtures; install-time mutant."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "pwsh7 and Git Bash second-shell review ran on this box",
            ],
        },
        "cloud_ok": False,
        "registered": True,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": "tools/plugin/pack.py", "exists": True, "role": "supporting"},
        ],
        "gates": live["gates"],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0194 artifact {size}B below floor")
        return 1
    if b"SUCCESS:TST-0194" not in out.read_bytes():
        print("FAILED:TST-0194 sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0194 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
