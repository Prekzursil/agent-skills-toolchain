"""A SECOND negative control, built because the first one measured the wrong population.

WHY THIS EXISTS
---------------
The first negative control was the 616 authored `not a duplicate:` pairs.  It reported a 1.62%
false-merge rate and was clean -- yet the very next build produced a 15-record cluster whose
entire justification was the shared word "gate", and a 10-record cluster on the word "index".
The control did not see it because ALL 616 of its pairs live in the option families, which
carry rich hand-written mechanism prose.  The failure lives in the classes that carry NO
mechanism field at all (blueprints, presets, protocols, archaeology, verify docs).

A control measured on a population that excludes the failure mode is a weak control.  This is
the same defect class as a probe that is silent in both states, one level up: the probe fired
correctly, on the wrong sample.

THE CONTROL
-----------
Several corpus documents declare their own records MUTUALLY DISTINCT, in their own prose:

  07-OPTION-UNIVERSE.md   "Final distinct options: 283"          -> any two ids are distinct
  09-WORKFLOW-BLUEPRINT-LIBRARY.md  108 ids, "applied to all 108" -> ditto
  11-COUNCIL-OPTION-CARDS.md        CF-01..CF-59                   -> ditto
  12-COUNCIL-PROTOCOLS-AND-PRESETS.md  58 protocols, 72 presets    -> ditto within each class

Therefore ANY D3 merge between two DIFFERENT ids of the same class in the same document is,
by that document's own declaration, a FALSE MERGE.  That gives tens of thousands of negative
pairs concentrated in exactly the thin-signature population the first control missed.

HONEST LIMIT, inline: "distinct option" is the document's word, and two distinct options can
in principle share an implementation mechanism (that is what its own dedup ledger records
happening 55 times BEFORE the distinct set was finalised).  So this control's false-merge rate
is an UPPER bound on genuine error, not an exact count.  It is used as a ceiling to tune
against, never as proof that a specific merge is wrong.  Settling experiment: adjudicate a
random sample of the fires by hand; a fire between two ids the universe kept separate AFTER
running its own dedup pass is very likely a real false merge.
"""

from __future__ import annotations

import itertools

DECLARED_DISTINCT = {
    ("07-OPTION-UNIVERSE.md", "option_universe"): "Final distinct options: 283",
    ("09-WORKFLOW-BLUEPRINT-LIBRARY.md", "blueprint"): "108 distinct blueprints",
    (
        "11-COUNCIL-OPTION-CARDS.md",
        "council_card",
    ): "CF-nn distinct council option cards",
    ("12-COUNCIL-PROTOCOLS-AND-PRESETS.md", "protocol"): "58 distinct protocols",
    ("12-COUNCIL-PROTOCOLS-AND-PRESETS.md", "preset"): "72 distinct presets",
}

MAX_PAIRS_PER_GROUP = (
    6000  # bound the O(n^2); 283 ids -> 39,903 pairs, sampled deterministically
)


def intra_document_control(nodes, matcher, t) -> dict:
    """Count D3 fires between records the same document declares mutually distinct."""
    groups: dict[tuple[str, str], list] = {}
    for n in nodes:
        key = (n.source_file, n.record_class)
        if key in DECLARED_DISTINCT:
            groups.setdefault(key, []).append(n)

    total = fired = 0
    per_group = {}
    samples = []
    for key, group in sorted(groups.items()):
        group = sorted(group, key=lambda n: n.local_id)
        pairs = list(itertools.combinations(range(len(group)), 2))
        # deterministic stride sample when the group is large -- no RNG, reproducible
        if len(pairs) > MAX_PAIRS_PER_GROUP:
            stride = len(pairs) // MAX_PAIRS_PER_GROUP + 1
            pairs = pairs[::stride]
        g_total = g_fired = 0
        for i, j in pairs:
            a, b = group[i], group[j]
            if a.local_id == b.local_id:
                continue
            g_total += 1
            ok, detail = matcher(a.sig, b.sig, t)
            if ok:
                g_fired += 1
                if len(samples) < 25:
                    samples.append(
                        {
                            "a": a.raw_id,
                            "b": b.raw_id,
                            "a_title": a.title[:90],
                            "b_title": b.title[:90],
                            "detail": detail,
                        }
                    )
        per_group[f"{key[0]}::{key[1]}"] = {
            "records": len(group),
            "pairs_checked": g_total,
            "d3_fired": g_fired,
            "rate": round(g_fired / g_total, 5) if g_total else None,
            "declared_by": DECLARED_DISTINCT[key],
        }
        total += g_total
        fired += g_fired

    return {
        "description": (
            "pairs of DIFFERENT ids of the same class in a document that declares its records "
            "mutually distinct; any D3 fire is a false merge by that document's own declaration"
        ),
        "pairs": total,
        "d3_fired_falsely": fired,
        "false_merge_rate": round(fired / total, 5) if total else None,
        "per_group": per_group,
        "false_pairs_sample": samples,
        "upper_bound_caveat": (
            "two ids a document kept separate can still share an implementation mechanism, so "
            "this rate is an UPPER bound on genuine error, used as a ceiling to tune against"
        ),
    }
