#!/usr/bin/env python3
"""Probe 1: zero fingerprint collisions; library total re-derived from spec text."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "command-center"))

from blueprint_library.catalog import build_catalog  # noqa: E402
from blueprint_library.fingerprint import fingerprint  # noqa: E402
from blueprint_library.library import LIBRARY, paraphrase  # noqa: E402
from blueprint_library.taxonomy import (  # noqa: E402
    derived_library_total,
    load_spec_text,
    parse_category_counts,
)

TAXONOMY_PY = ROOT / "command-center/blueprint_library/taxonomy.py"


def _assert_no_hardcoded_total(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == 96:
            raise SystemExit(
                "FAILED:IMP-0232-probe1 hardcoded 96 in taxonomy.py (broken detector)"
            )


def _mutant_sum_changes(spec_text: str, original: int) -> None:
    lines = [
        ln
        for ln in spec_text.splitlines()
        if ln.strip() and not ln.strip().startswith("#") and ":" in ln.strip()
    ]
    if len(lines) < 2:
        raise SystemExit("FAILED:IMP-0232-probe1 spec has too few category lines")
    kept = spec_text.replace(lines[-1], f"# removed {lines[-1]}", 1)
    mutated = derived_library_total(kept)
    if mutated == original:
        raise SystemExit(
            f"FAILED:IMP-0232-probe1 mutant total unchanged ({mutated})"
        )
    print(f"mutant_total={mutated} original_total={original} changed=True")


def main() -> int:
    _assert_no_hardcoded_total(TAXONOMY_PY)
    spec = load_spec_text(ROOT)
    counts = parse_category_counts(spec)
    derived = derived_library_total(spec)
    fps = [fingerprint(e) for e in LIBRARY]
    collisions = len(fps) - len(set(fps))
    catalog = build_catalog(ROOT)
    print(f"derived_total={derived}")
    print(f"categories={counts}")
    print(f"library_len={len(LIBRARY)}")
    print(f"unique_fingerprints={len(set(fps))}")
    print(f"collisions={collisions}")
    print(f"catalog_collisions={catalog['fingerprint_collisions']}")
    print(f"counts_agree={catalog['counts_agree']}")
    if collisions != 0:
        print("FAILED:IMP-0232-probe1 fingerprint collisions in library")
        return 1
    if derived != len(LIBRARY):
        print("FAILED:IMP-0232-probe1 derived total != registered library size")
        return 1
    if not catalog["counts_agree"]:
        print("FAILED:IMP-0232-probe1 catalog counts_agree is false")
        return 1
    # Rename invariance: paraphrasing one incumbent must not change its fingerprint.
    sample = LIBRARY[0]
    clone = paraphrase(sample, "tmp-paraphrase-check")
    if fingerprint(clone) != fingerprint(sample):
        print("FAILED:IMP-0232-probe1 paraphrase changed fingerprint")
        return 1
    print("paraphrase_preserves_fingerprint=True")
    _mutant_sum_changes(spec, derived)
    print("SUCCESS:IMP-0232-probe1 zero collisions; total re-derived from spec")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
