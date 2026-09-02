#!/usr/bin/env python3
"""Independent H-executed-corpus recount from on-disk 08 JSON.

A naive len(candidates) or raw-text hit on the family string is the known-bad
control: decoys would inflate the count. Family-field recount must be 72.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0154-executed-corpus-replay-differential-for-the-72-h-fam.json"
REG = HERE / "fixtures" / "corpus" / "08-WORKFLOW-CANDIDATE-REGISTRY.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0154-probe1 {msg}")
    return 1


def main() -> int:
    if not REG.is_file():
        return fail("registry-fixture-missing")
    if not ART.is_file():
        return fail("artifact-missing")

    raw = REG.read_text(encoding="utf-8")
    candidates = C.load_registry(REG)
    h = C.h_family(candidates)
    decoy_n = len(candidates) - len(h)
    raw_hits = raw.count(C.H_FAMILY)

    print(f"registry={REG.relative_to(REPO).as_posix()}")
    print(f"candidates_n={len(candidates)} h_family_n={len(h)} decoy_n={decoy_n}")
    print(f"raw_text_family_hits={raw_hits}")
    print(f"h_ids={[c['id'] for c in h[:3]]}...{[c['id'] for c in h[-2:]]}")

    if len(h) != C.H_N:
        return fail(f"h-count-want-{C.H_N}-got-{len(h)}")
    if decoy_n < 1:
        return fail("decoys-absent; recount cannot discriminate family-field vs len()")
    if len(candidates) == len(h):
        return fail("no-decoy-inflation-control")
    if raw_hits <= len(h):
        return fail("mention-decoy-missing; use-vs-mention control dead")
    # raw-text hits include family fields (72) + mention decoy (>=1) => 73+
    if raw_hits == len(h):
        return fail("raw-hits-eq-family; mention decoy not visible")

    naive_len = len(candidates)
    if naive_len == C.H_N:
        return fail("naive-len-equals-72; decoys not loaded")

    doc = json.loads(ART.read_text(encoding="utf-8"))
    fam = doc.get("family") or {}
    if fam.get("counted_n") != len(h):
        return fail(f"artifact-counted_n {fam.get('counted_n')} != recount {len(h)}")
    if fam.get("catalog_n") != C.CATALOG_H_N:
        return fail("artifact-catalog_n")
    if fam.get("name") != C.H_FAMILY:
        return fail("artifact-family-name")
    rows = doc.get("rows") or []
    if len(rows) != len(h):
        return fail(f"artifact-rows {len(rows)} != h {len(h)}")
    art_ids = [r.get("candidate_id") for r in rows]
    h_ids = [c["id"] for c in h]
    if art_ids != h_ids:
        return fail("artifact-row-ids-disagree-with-08-family-recount")
    if "SUCCESS:WFA-0154" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    print(
        "naive_len="
        f"{naive_len} family_field={len(h)} raw_hits={raw_hits} "
        "decoy_excluded=True"
    )
    print("SUCCESS:WFA-0154-probe1 independent H-family recount n=72 decoys-excluded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
