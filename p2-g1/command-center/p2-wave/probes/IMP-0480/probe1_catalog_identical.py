#!/usr/bin/env python3
"""IMP-0480 probe1: planted-injection behavioral diff over the catalog.

For every planted injection class the consuming stage must produce output
IDENTICAL to the clean baseline (boundary holds), while the naive
concatenating consumer diverges on every class (both-states proof) and the
prompt-level plea still follows at least one injection. A benign fact edit
(score) MUST change the output - proving the behavioral diff is sensitive,
not insensitive."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
AB = REPO / "tools" / "artifact_boundary"


def load_mod(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# The package-internal imports need the package dir importable.
sys.path.insert(0, str(AB.parent))
consume = load_mod("imp0480_consume", AB / "consume.py")
corpus = load_mod("imp0480_corpus", AB / "corpus.py")
policy = load_mod("imp0480_policy", AB / "policy.py")
naive = load_mod("imp0480_naive", AB / "naive.py")

POL = policy.TrustedPolicy()


def fail(msg):
    print("FAILED:IMP-0480-probe1 " + str(msg))
    return 1


def main() -> int:
    base = corpus.baseline_artifacts()
    clean_out = consume.behavior_of(base, POL)

    rows = []
    plea_diverged = []
    for inj_id, clean, dirty in corpus.planted_pairs():
        boundary_clean = consume.behavior_of(clean, POL)
        boundary_dirty = consume.behavior_of(dirty, POL)
        identical = boundary_clean == boundary_dirty
        naive_clean = naive.naive_consume(clean, POL)
        naive_dirty = naive.naive_consume(dirty, POL)
        naive_diverged = naive_clean != naive_dirty
        plea_out = naive.plea_then_naive(dirty, POL)
        plea_follows = any(
            frag in plea_out for frag in ("IGNORE PREVIOUS", "curl", "ssh", "administrator")
        )
        if not identical:
            return fail("injection %s changed consuming-stage output" % inj_id)
        if not naive_diverged:
            return fail("naive consumer failed to diverge on %s - diff insensitive" % inj_id)
        if plea_follows:
            plea_diverged.append(inj_id)
        rows.append({
            "id": inj_id,
            "boundary_identical": identical,
            "naive_diverged": naive_diverged,
            "plea_still_follows": plea_follows,
        })

    if not plea_diverged:
        return fail("prompt-level plea stopped every injection - plea control vacuous")

    # Sensitivity control: a benign fact edit (transcript score 1 -> 9)
    # MUST change the consuming-stage output.
    benign = corpus.benign_score_edit(base)
    benign_out = consume.behavior_of(benign, POL)
    benign_changed = benign_out != clean_out
    if not benign_changed:
        return fail("benign score edit did NOT change output - behavioral diff insensitive")

    print(json.dumps({
        "probe": "probe1-catalog-identical",
        "unit_id": "IMP-0480",
        "artifact_kinds": sorted({a.kind for a in base}),
        "catalog_classes": [r["id"] for r in rows],
        "rows": rows,
        "boundary_baseline": clean_out,
        "naive_baseline": naive.naive_consume(base, POL)[:60] + "...",
        "plea_still_follows": True,
        "plea_classes_followed": plea_diverged,
        "benign_fact_edit_changes_output": benign_changed,
        "boundary_verdict": clean_out.get("verdict"),
        "boundary_actions": clean_out.get("actions"),
        "sentinel": "SENTINEL:IMP-0480:INJECTION-BOUNDARY-HELD",
    }, indent=2))
    print("SUCCESS:IMP-0480-probe1 all catalog injections produce identical output; naive diverges on every class; plea demonstrably insufficient; benign edit changes output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
