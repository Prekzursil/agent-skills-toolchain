# -*- coding: utf-8 -*-
"""Verify the curated cross-slice mechanism-overlap list for IMP-2 vs IMP-3.

The lexical Jaccard scan in _imp2_build.py is calibrated (planted reworded mutant scores 0.833)
but its SCOPE is lexical: IMP-3 titles its units as terse noun phrases while IMP-2 uses verb
phrases with long acceptance clauses, so an identical MECHANISM scores only 0.30. The pairs below
are therefore judgement calls about mechanism identity, not an algorithmic verdict - but each id
is checked to exist and each title is printed, so every claim is falsifiable by inspection.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MINE = json.loads((HERE / "IMP-2.json").read_text(encoding="utf-8"))
OTHER = json.loads((HERE / "IMP-3.json").read_text(encoding="utf-8"))

# SAMPLE STAMP: IMP-3.json was read at mtime 20:41:32, size 333381 bytes. It CHANGED under this
# analysis (333304 -> 333381; phase-7 count 39 -> 34) and an earlier pass recorded six pairs that
# no longer exist because IMP-3 itself dropped them: its old 0276 export/import, 0277 semantic
# diff, 0278 fusion algebra, 0279 lineage/decomposition, 0280 tournament, 0281 certification,
# 0282 scout, 0283 forge and 0353 blueprint-distinctness units were replaced with other
# mechanisms. Those foundry-side collisions are therefore RESOLVED in IMP-3's favour of yielding.
# The residual list below is a timestamped sample, not a frozen fact - re-run before acting.
#
# (my_id, imp3_id, resolution_recommendation)
PAIRS = [
    ("IMP-0129", "IMP-0261", "same mechanism (subworkflow + namespacing)"),
    ("IMP-0130", "IMP-0264", "same mechanism (loop + convergence rule)"),
    ("IMP-0131", "IMP-0265", "same mechanism (human checkpoint, durable pause/resume)"),
    ("IMP-0132", "IMP-0262", "same mechanism (dynamic fan-out, runtime width)"),
    ("IMP-0134", "IMP-0260", "same mechanism (param validation + typed coercion)"),
    ("IMP-0135", "IMP-0274", "same mechanism (model routing policy)"),
    ("IMP-0136", "IMP-0273", "overlapping (tool policy); IMP-2 splits tool vs source policy"),
    ("IMP-0137", "IMP-0273", "overlapping (source policy); IMP-2 adds the Tor owner-gate"),
    ("IMP-0138", "IMP-0275", "same mechanism (failure classification -> action)"),
    ("IMP-0139", "IMP-0267", "same mechanism (repair loop, attempt limit, proof-of-impossibility)"),
    ("IMP-0140", "IMP-0266", "overlapping (retry); IMP-2 frames it as the no-rival-core boundary"),
    ("IMP-0141", "IMP-0270", "same mechanism (content-addressed cache key + invalidation)"),
    ("IMP-0142", "IMP-0271", "same mechanism (dry-run planning)"),
    ("IMP-0143", "IMP-0272", "same mechanism (cost/time/impact estimator)"),
    ("IMP-0144", "IMP-0269", "same mechanism (deterministic replay)"),
    ("IMP-0145", "IMP-0268", "same mechanism (resume from partial state)"),
    ("IMP-0195", "IMP-0257", "overlapping (static validator)"),
    ("IMP-0216", "IMP-0264", "executor half of the same loop mechanism"),
    ("IMP-0217", "IMP-0261", "executor half of the same subworkflow mechanism"),
    ("IMP-0218", "IMP-0265", "executor half of the same checkpoint mechanism"),
    ("IMP-0219", "IMP-0262", "executor half of the same dynamic-fanout mechanism"),
    ("IMP-0223", "IMP-0364", "same mechanism (disposable worktree provisioning + teardown)"),
    ("IMP-0226", "IMP-0263", "overlapping (fan-in bound to the shared completion predicate)"),
    ("IMP-0227", "IMP-0271", "executor half of the dry-run mechanism"),
    ("IMP-0228", "IMP-0269", "executor half of the replay mechanism"),
    ("IMP-0229", "IMP-0270", "backend half of the cache mechanism"),
    ("IMP-0230", "IMP-0354", "overlapping (preset/example/stopping-rule fixture contract)"),
    ("IMP-0231", "IMP-0354", "overlapping (blueprint conformance)"),
]

mi = {u["id"]: u["title"] for u in MINE}
oi = {u["id"]: u["title"] for u in OTHER}
bad = []
for a, b, why in PAIRS:
    if a not in mi:
        bad.append(f"MY ID MISSING {a}")
    if b not in oi:
        bad.append(f"IMP-3 ID MISSING {b}")

print(f"IMP-2 units={len(MINE)}  IMP-3 units={len(OTHER)}  curated overlap pairs={len(PAIRS)}")
print(f"distinct IMP-2 ids implicated: {len({a for a, _, _ in PAIRS})}")
print(f"distinct IMP-3 ids implicated: {len({b for _, b, _ in PAIRS})}")
print(f"IMP-2 units with NO overlap claim: {len(MINE) - len({a for a, _, _ in PAIRS})}")
for a, b, why in PAIRS:
    print(f"  {a} | {mi.get(a,'?')[:56]:56s} <-> {b} | {oi.get(b,'?')[:52]:52s} | {why}")
print(f"ANCHOR ERRORS: {len(bad)}")
for e in bad:
    print("   ", e)
print("SUCCESS:imp2-overlap-check" if not bad else "FAILED:imp2-overlap-check")
sys.exit(1 if bad else 0)
