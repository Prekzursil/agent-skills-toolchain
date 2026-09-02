#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
PULL = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "missing-pull",
    WAVE / "ovh-monitor" / "error-pull",
]
RELS = [
    "tools/marketplace/independent_sweep.py",
    "tools/marketplace/confusables.py",
    "tools/marketplace/name_grammar.py",
    "tools/marketplace/data/reserved_names.json",
    "tools/marketplace/fixtures/planted_collisions.json",
    "tools/marketplace/fixtures/current_index.json",
    "tools/marketplace/tests/test_name_grammar.py",
    "tools/plugin/doctor_cli.py",
    "tools/plugin/schema/deployed-copy-advisory.schema.json",
    "tools/plugin/exit_codes.json",
    "tools/plugin/support_contract.json",
    "tools/plugin/data/error-taxonomy.json",
    "tools/plugin/data/doctor-mapping.json",
    "tools/plugin/blob.py",
    "tools/plugin/tests/test_argv_only.py",
    "command-center/wrong_recipe_gate.py",
    "tools/workflow_foundry/license_extract.py",
    "blueprints/workflows/wf.research.archival.json",
    "command-center/p2-wave/probes/IMP-0069/probe1_planted_collisions.py",
]
SUBS = ("tree", "delta", "extracted", "extracted-delta")


def main() -> None:
    for rel in RELS:
        hits = []
        for root in PULL:
            if not root.is_dir():
                continue
            for box in root.iterdir():
                if not box.is_dir():
                    continue
                for sub in SUBS:
                    cand = box / sub / rel
                    if cand.is_file() and cand.stat().st_size > 0:
                        hits.append(f"{cand.relative_to(WAVE)} size={cand.stat().st_size}")
                    # error-pull extracted layouts: extracted/<box>/probes/...
                    alt = box / sub / "probes" / Path(rel).name
                    if alt.is_file() and alt.stat().st_size > 0:
                        hits.append(f"{alt.relative_to(WAVE)} size={alt.stat().st_size}")
        print(rel)
        if hits:
            for h in hits[:8]:
                print(" ", h)
        else:
            print("  NO-HARVEST")


if __name__ == "__main__":
    main()
