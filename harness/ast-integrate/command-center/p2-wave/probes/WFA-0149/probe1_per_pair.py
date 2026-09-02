#!/usr/bin/env python3
"""Probe 1: re-derive the 140 pairs and per-pair verdicts from the library.

Does not trust the artifact's stored census or pair list until a live walk of
blueprints[].compat reproduces them. Ignores any counts block on the library.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import graph as G  # noqa: E402

ART = (
    REPO
    / "command-center/foundry/WFA-0149-resolve-the-140-asymmetric-compatibility-declaration.json"
)
SENTINEL = "SUCCESS:WFA-0149"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0149-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    library, source_label, live = G.load_subject(REPO)
    bps = G.blueprints_of(library)
    lists = G.census_from_lists(bps)
    matrix = G.census_from_matrix(bps)
    print(f"source={source_label} live={live}")
    print(f"lists={lists}")
    print(f"matrix={matrix}")
    if lists != matrix:
        return fail(f"census-paths-disagree lists={lists} matrix={matrix}")
    decoy = library.get("counts") if isinstance(library.get("counts"), dict) else {}
    print(f"decoy_counts={decoy}")
    if decoy and decoy.get("asymmetric") == 0 and lists["asymmetric"] != 0:
        print("decoy_ignored=True")
    elif decoy and decoy != lists:
        print("decoy_ignored=True")
    else:
        print("decoy_ignored=False")
        if decoy:
            return fail("decoy counts were not distinct from the live census")

    if not live and lists != G.PUBLISHED:
        return fail(f"replica census {lists} != published {G.PUBLISHED}")

    verdicts = G.adjudicate_all(bps)
    if len(verdicts) != lists["asymmetric"]:
        return fail(f"verdict n={len(verdicts)} asymmetric={lists['asymmetric']}")
    if any(v["verdict"] not in G.VERDICTS for v in verdicts):
        return fail("unresolved-verdict")
    counts = Counter(v["verdict"] for v in verdicts)
    print(f"verdict_counts={dict(counts)}")
    if counts.get("DIRECTIONAL", 0) < 1 or counts.get("MISSING-REVERSE", 0) < 1:
        return fail("mixed-verdicts-required")

    art_pairs = doc.get("pairs") or []
    if len(art_pairs) != 140:
        return fail(f"artifact pairs n={len(art_pairs)}")
    live_keys = {(v["from"], v["to"], v["verdict"]) for v in verdicts}
    art_keys = {(p["from"], p["to"], p["verdict"]) for p in art_pairs}
    if live_keys != art_keys:
        return fail("artifact pair set != live adjudication")
    if doc.get("census_rederived") != lists:
        return fail("artifact census_rederived != live lists census")
    if doc.get("census_matrix") != matrix:
        return fail("artifact census_matrix != live matrix census")

    repaired = G.typed_repair(bps, verdicts)
    ok, why = G.repair_is_admissible(bps, repaired, verdicts)
    print(f"typed_repair_admissible={ok} {why}")
    if not ok:
        return fail(f"typed-repair {why}")
    rc = G.census_from_lists(repaired)
    print(f"repaired={rc}")
    if rc["asymmetric"] != counts["DIRECTIONAL"]:
        return fail("remaining asymmetric != DIRECTIONAL")
    if rc["undirected"] != lists["undirected"]:
        return fail("undirected changed")
    if doc.get("repaired_census") != rc:
        return fail("artifact repaired_census != live repaired census")

    print(
        f"artifact_ok=True items={len(art_pairs)} "
        f"directional={counts['DIRECTIONAL']} missing_reverse={counts['MISSING-REVERSE']}"
    )
    print("SUCCESS:WFA-0149-probe1 per-pair adjudication decoy-counts-ignored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
