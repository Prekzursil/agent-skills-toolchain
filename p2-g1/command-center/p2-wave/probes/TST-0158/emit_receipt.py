#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0158.json concurrency report."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0158.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0158/probe1_merger_refuse.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0158/probe2_intersection.py"
)
QUESTION = (
    "When two catalog slices reuse the same id namespace with different "
    "meanings, does the merger refuse and enumerate the colliding ids? PASS "
    "requires refusal plus the full collision list; silently taking last-wins "
    "is a FAIL."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(rel: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {"path": rel, "sha256": sha, "bytes": size}


def main() -> int:
    live = S.live_experiment()
    if not live.get("pass"):
        print("FAILED:TST-0158 emit live experiment did not pass")
        print(json.dumps(live, indent=2, sort_keys=True)[:4000])
        return 1

    src_probe = {
        "id": "probe1_merger_refuse",
        "command": P1,
        "role": "merger-exit-and-collision-list",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0158/probe1_merger_refuse.py"
        ),
    }
    ver_probe = {
        "id": "probe2_intersection",
        "command": P2,
        "role": "independent-id-set-intersection",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0158/probe2_intersection.py"
        ),
    }
    if src_probe["fingerprint"]["sha256"] == ver_probe["fingerprint"]["sha256"]:
        print("FAILED:TST-0158 emit source/verifier probe files identical")
        return 1

    collision = live["collision_run"]
    disjoint = live["disjoint_run"]
    last_wins = live["last_wins_control"]
    ids = list(live["expected_collision_ids"])

    doc = {
        "unit_id": "TST-0158",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "concurrency_report",
        "title": "Catalog merge refuses colliding id namespaces",
        "question": QUESTION,
        "sentinel": "SUCCESS:TST-0158",
        "completion_sentinel": "SUCCESS:TST-0158",
        "min_bytes_threshold": 2048,
        "verdict": "PASS",
        "cloud_ok": False,
        "source_probe": src_probe,
        "verifier_probe": ver_probe,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": src_probe["role"]},
            {"id": "probe2", "command": P2, "role": ver_probe["role"]},
        ],
        "merger_signal": {
            "tool": "tools/command-center/merge_catalog.py",
            "exit_code": collision["exit_code"],
            "refused": collision["refused"],
            "reason": collision["reason"],
            "collision_ids": collision["collision_ids"],
            "collision_count": collision["collision_count"],
            "wrote_merged_catalog": collision["wrote_merged_catalog"],
            "order_independent": collision["order_independent"],
        },
        "independent_intersection": {
            "method": (
                "set(ids of option-universe items) & "
                "set(ids of architecture-mechs items)"
            ),
            "ids": live["independent_intersection"],
            "count": live["expected_collision_count"],
            "agrees_with_merger": live["signals_agree"],
        },
        "last_wins_control": last_wins,
        "regression_seed": {
            "name": (
                "31-way M-NN option-universe vs architecture-candidates "
                "mechanisms"
            ),
            "option_count": last_wins["option_count"],
            "mech_count": last_wins["mech_count"],
            "collision_count": 31,
            "collision_ids": ids,
            "option_numbers": list(S.OPTION_NUMBERS),
            "mech_numbers": list(S.MECH_NUMBERS),
            "note": (
                "Pre-reprefix mechanism cards still used the M-NN token. "
                "Live estate re-prefixed mechanisms to MECH-NN on 2026-08-07; "
                "this seed reconstitutes the measured 31-way collision."
            ),
        },
        "tests": {
            "disjoint_slices_merge_clean": {
                "pass": live["disjoint_ok"],
                "exit_code": disjoint["exit_code"],
                "ids": disjoint["ids"],
                "count": disjoint["count"],
                "order_independent": disjoint["order_independent"],
            },
            "regression_seed_31_way_mnn": {
                "pass": live["refuse_ok"] and live["signals_agree"],
                "collision_count": collision["collision_count"],
                "collision_ids": collision["collision_ids"],
                "full_list_not_sample": len(ids) == 31
                and collision["collision_ids"] == ids,
            },
            "last_wins_is_fail": {
                "pass": live["last_wins_is_fail"],
                "catalog_by_id": "tools/command-center/catalog.py:by_id",
                "silently_took_last_wins": last_wins["silently_took_last_wins"],
                "hidden_collision_count": last_wins["hidden_collision_count"],
            },
        },
        "evidence": {
            "signal_a": "merger CLI exit status and complete collision_ids list",
            "signal_b": (
                "independent set-intersection over the two slices' id fields"
            ),
            "signals_agree": live["signals_agree"],
        },
        "reviewer": {
            "reviewer_id": "TST-0158-probe2-intersection",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 recomputes set intersection from slice id fields and "
                "does not read merge_catalog.collision_ids as authority. It "
                "also requires catalog.by_id last-wins to hide the 31 ids."
            ),
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {
                "path": "tools/command-center/merge_catalog.py",
                "role": "merger",
            },
        ],
        "fixtures": live["fixtures"],
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "command-center/OPTION-ID-RESOLUTION.json exists on this tree",
                "07-OPTION-UNIVERSE / 13-ARCHITECTURE-CANDIDATES source docs are present",
            ],
            "proof_surface": (
                "merge_catalog.py CLI against reconstituted 31-way M-NN slices "
                "and a disjoint work-unit pair; independent id set-intersection; "
                "catalog.by_id last-wins negative control."
            ),
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0158 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
