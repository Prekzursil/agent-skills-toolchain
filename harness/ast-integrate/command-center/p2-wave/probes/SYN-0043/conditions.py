"""CC-0015-shaped encoding of the 21 program stopping conditions.

_USER-PROMPTS.md is absent on this worktree. Condition 1, 4, 5, 8, 12-19
are taken from catalog citations of spec lines 11376-11398. The remaining
texts are reconstructed from the same catalog's per-line spec_anchor map
(11378=C1 ... 11398=C21) and are labelled reconstructed=true so they cannot
be mistaken for a verbatim spec quote.
"""
from __future__ import annotations

# condition_id -> spec line. Catalog: C1 is :11378, C13 is :11390, C16 is :11393.
SPEC = (
    {
        "condition_id": 1,
        "spec_line": 11378,
        "reconstructed": False,
        "text": (
            "Every selected option id is in exactly one terminal state: "
            "IMPLEMENTED, SUPERSEDED, or REJECTED-WITH-OWNER-REASONING."
        ),
        "catalog_citation": "SYN-0028 / BLD-0019 (stopping condition 1, :11378)",
        "floor": None,
    },
    {
        "condition_id": 2,
        "spec_line": 11379,
        "reconstructed": True,
        "text": (
            "Every owner requirement extracted from the spec is bound to a "
            "satisfying work unit; an unbound requirement is a named gap."
        ),
        "catalog_citation": "CC-0024 (disappeared-requirement binding)",
        "floor": None,
    },
    {
        "condition_id": 3,
        "spec_line": 11380,
        "reconstructed": True,
        "text": (
            "Cited green results are not rerun-until-green laundering: a "
            "result that required discarded failures does not count as green."
        ),
        "catalog_citation": "ADV-0090 spec_anchor :11380, :11059",
        "floor": None,
    },
    {
        "condition_id": 4,
        "spec_line": 11381,
        "reconstructed": False,
        "text": "No required test is red.",
        "catalog_citation": "SYN-0043 tests_required planted-false on condition 4",
        "floor": None,
    },
    {
        "condition_id": 5,
        "spec_line": 11382,
        "reconstructed": False,
        "text": (
            "Mutation and negative-control coverage demonstrate detector "
            "validity; a declared-but-never-FAIL control does not count."
        ),
        "catalog_citation": "CC-0014 / TST-0329 / ADV-0010 spec_anchor :11382",
        "floor": None,
    },
    {
        "condition_id": 6,
        "spec_line": 11383,
        "reconstructed": True,
        "text": (
            "Every load-bearing claim carries two mechanically independent "
            "signals; a single probe is not verification."
        ),
        "catalog_citation": "rules/common/single-signal-verification.md (estate rule)",
        "floor": None,
    },
    {
        "condition_id": 7,
        "spec_line": 11384,
        "reconstructed": True,
        "text": (
            "The compatibility matrix never represents an UNTESTED cell as "
            "SUPPORTED; inference is labelled INFERRED."
        ),
        "catalog_citation": "ARC-0095 input :11384",
        "floor": None,
    },
    {
        "condition_id": 8,
        "spec_line": 11385,
        "reconstructed": False,
        "text": (
            "Benchmark results show the intended improvement without material "
            "regression; UNMEASURED is not NEUTRAL."
        ),
        "catalog_citation": "SYN-0034 / TST-0308 stopping condition 8 :11385",
        "floor": None,
    },
    {
        "condition_id": 9,
        "spec_line": 11386,
        "reconstructed": True,
        "text": (
            "Credentials or decrypted secrets have not entered an artifact "
            "bundle, receipt, event or rollback backup."
        ),
        "catalog_citation": "IMP-0458 / CC-0013 regression class :11345 (adjacent)",
        "floor": None,
    },
    {
        "condition_id": 10,
        "spec_line": 11387,
        "reconstructed": True,
        "text": (
            "Every recorded completion/CI gate required to stop is green on "
            "a live re-run; a missing gate file is not a pass."
        ),
        "catalog_citation": "CC-0015 input COMPLETION-GATES.json; CC-0003 reducer",
        "floor": None,
    },
    {
        "condition_id": 11,
        "spec_line": 11388,
        "reconstructed": True,
        "text": (
            "The release gate re-runs vulnerability and license scanners at "
            "release time rather than accepting a cached implementation-time result."
        ),
        "catalog_citation": "ADV-0016 spec_anchor :11112, :11129, :11388",
        "floor": None,
    },
    {
        "condition_id": 12,
        "spec_line": 11389,
        "reconstructed": False,
        "text": "Docs and code agree.",
        "catalog_citation": "SYN-0020 / TST-0112 stopping condition 12 :11389",
        "floor": None,
    },
    {
        "condition_id": 13,
        "spec_line": 11390,
        "reconstructed": False,
        "text": "Release or canary succeeds.",
        "catalog_citation": "CC-0015 / REL-0003 / SYN-0043 condition 13 :11390",
        "floor": None,
    },
    {
        "condition_id": 14,
        "spec_line": 11391,
        "reconstructed": False,
        "text": "Rollback is tested.",
        "catalog_citation": "ADV-0119 / REL-0006 stopping condition 14 :11391",
        "floor": None,
    },
    {
        "condition_id": 15,
        "spec_line": 11392,
        "reconstructed": False,
        "text": (
            "Every residual unknown has a named settling experiment and an "
            "owner-visible impact statement."
        ),
        "catalog_citation": "BLD-0029 stopping condition 15 :11392",
        "floor": None,
    },
    {
        "condition_id": 16,
        "spec_line": 11393,
        "reconstructed": False,
        "text": (
            "At least 160 workflow candidates/mechanisms researched and "
            "classified with provenance and licence records."
        ),
        "catalog_citation": "WFA-0123 / SYN-0031 stopping condition 16 :11393",
        "floor": 160,
    },
    {
        "condition_id": 17,
        "spec_line": 11394,
        "reconstructed": False,
        "text": (
            "At least 96 materially distinct workflow blueprints executable "
            "under the selected quality tiers."
        ),
        "catalog_citation": "WFA-0124 / SYN-0031 stopping condition 17 :11394",
        "floor": 96,
    },
    {
        "condition_id": 18,
        "spec_line": 11395,
        "reconstructed": False,
        "text": "At least 48 council protocols.",
        "catalog_citation": "SYN-0031 floors :11393-11396 (protocol half of the pair)",
        "floor": 48,
    },
    {
        "condition_id": 19,
        "spec_line": 11396,
        "reconstructed": False,
        "text": "At least 64 editable council presets.",
        "catalog_citation": "SYN-0031 floors :11393-11396 (preset half of the pair)",
        "floor": 64,
    },
    {
        "condition_id": 20,
        "spec_line": 11397,
        "reconstructed": True,
        "text": "At least 2048 work units in the merged catalog.",
        "catalog_citation": (
            "CC-0024 nine floors; catalog work_units_meta.target=2048 "
            "(SYN-0031 lists this floor with 16-19; encoded here as its own row)"
        ),
        "floor": 2048,
    },
    {
        "condition_id": 21,
        "spec_line": 11398,
        "reconstructed": True,
        "text": "At least 160 platform options.",
        "catalog_citation": (
            "SYN-0031 floors include >=160 platform options; encoded as C21 "
            "so each numeric floor is independently falsifiable"
        ),
        "floor": 160,
    },
)

assert len(SPEC) == 21
assert [c["condition_id"] for c in SPEC] == list(range(1, 22))
assert [c["spec_line"] for c in SPEC] == list(range(11378, 11399))

BY_ID = {c["condition_id"]: c for c in SPEC}
