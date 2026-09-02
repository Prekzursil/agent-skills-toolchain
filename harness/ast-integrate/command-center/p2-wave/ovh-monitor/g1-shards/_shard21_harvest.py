#!/usr/bin/env python3
"""Find harvested copies of missing modules for shard-21."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PULL = REPO / "command-center" / "p2-wave" / "ovh-monitor" / "delivery-pull"
ROOTS = [
    PULL,
    REPO / "command-center" / "p2-wave" / "ovh-monitor" / "missing-pull",
    REPO / "command-center" / "p2-wave" / "ovh-monitor" / "error-pull",
    REPO / "command-center" / "p2-wave" / "scw-pull",
]
NEED = [
    "tools/plugin/case_collision.py",
    "tools/plugin/scenario.py",
    "tools/plugin/errors.py",
    "tools/plugin/strict_json.py",
    "tools/plugin/jsonl_log.py",
    "tools/marketplace/jsonl_log.py",
    "tools/council/vote/secret.py",
    "tools/council/participants/select_adversarial.py",
    "tools/council/participants/replace.py",
    "tools/workflow_foundry/licence_matrix.py",
    "tools/workflow_foundry/blueprint_contract.py",
    "workflow_foundry/licence_matrix.py",
    "workflow_foundry/blueprint_contract.py",
    "tools/foundry/constants.py",
    "foundry/constants.py",
    "tools/agentrail/agentrail/runner.py",
    "tools/crossvendor/divergence.py",
    "crossvendor/divergence.py",
    "tools/detectors/campaign.py",
    "detectors/campaign.py",
    "tools/mutation/gate.py",
    "mutation/gate.py",
    "tools/checkout_quarantine/fixture.py",
    "checkout_quarantine/fixture.py",
    "tools/scanners/content_scanner.py",
    "tools/event-ledger/monitor.py",
    "command-center/p2-wave/probes/IMP-0009/case_collision.py",
    "command-center/p2-wave/probes/IMP-0440/three_route.py",
    "command-center/p2-wave/probes/IMP-0471/detectors/campaign.py",
    "command-center/p2-wave/probes/IMP-0370/crossvendor/divergence.py",
    "command-center/p2-wave/probes/IMP-0102/test_search_determinism.py",
    "command-center/CLI-FLAGS.md",
]
NEEDLES = [
    "KIND_CASE",
    "def lint_file",
    "class JsonlLogger",
    "def seed_home",
    "class MissingTransactionIdError",
    "class DuplicateKeyError",
    "NAMED_FAILURE_11331",
    "COMPLETED",
    "class MonitorDead",
]


def main() -> None:
    boxes = []
    for root in ROOTS:
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in ("delta", "tree", "extracted-delta"):
                cand = box / sub
                if cand.is_dir():
                    boxes.append(cand)
                nested = box / "extracted-delta"
                if nested.is_dir():
                    for inner in nested.iterdir():
                        if inner.is_dir():
                            boxes.append(inner)
    print("boxes", len(boxes))
    for rel in NEED:
        hits = []
        for box in boxes:
            p = box / rel
            if p.is_file() and p.stat().st_size > 0:
                head = p.read_text(encoding="utf-8", errors="replace")[:2500]
                stub = any(
                    m in head
                    for m in ("# g1-surface: generated", "# g1-mod: real-surface", "class _NS:")
                )
                hits.append((p.stat().st_size, stub, str(p)[-90:]))
        hits.sort(reverse=True)
        print(f"FILE {rel} n={len(hits)} top={hits[:3]}")
    # filename search for a few key basenames
    want_names = {
        "case_collision.py",
        "secret.py",
        "select_adversarial.py",
        "licence_matrix.py",
        "blueprint_contract.py",
        "three_route.py",
        "content_scanner.py",
        "CLI-FLAGS.md",
    }
    found = {n: [] for n in want_names}
    for box in boxes:
        for p in box.rglob("*"):
            if p.name in want_names and p.is_file():
                found[p.name].append((p.stat().st_size, str(p)[-110:]))
    for n, rows in found.items():
        rows.sort(reverse=True)
        print(f"NAME {n} n={len(rows)} top={rows[:4]}")


if __name__ == "__main__":
    main()
