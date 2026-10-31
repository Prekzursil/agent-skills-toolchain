#!/usr/bin/env python3
"""Assemble CNF-1.json (bucket B09, independent confirmation and reproduction).

Deterministic: no clock, no randomness. Re-running produces byte-identical output.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

from _cnf_common import TOOLS, REVIEWERS, RETRY, SENT_TMPL, FIELDS  # noqa: E402
from _cnf_data_a import UNITS_A  # noqa: E402
from _cnf_data_b import UNITS_B  # noqa: E402
from _cnf_data_c import UNITS_C  # noqa: E402

RAW = UNITS_A + UNITS_B + UNITS_C

# Mechanism families, used for (a) the vendor-alternation rule and (b) the
# family-level upstream bucket dependency. Ranges are 1-indexed inclusive.
FAMILIES = [
    ("A-apparatus", 1, 14, []),
    ("B-baseline-repro", 15, 27, ["B01", "B02"]),
    ("C-fix-repro", 28, 40, ["B07", "B08"]),
    ("D-rollback", 41, 50, ["B07", "B13"]),
    ("E-regression", 51, 61, ["B08"]),
    ("F-research-claims", 62, 73, ["B03"]),
    ("G-workflow-foundry", 74, 85, ["B04"]),
    ("H-council-runtime", 86, 95, ["B05"]),
    ("I-install-platform", 96, 107, ["B07", "B13"]),
    ("J-security-supply-chain", 108, 117, ["B07", "B10"]),
    ("K-meta-and-gate", 118, 128, ["B08"]),
]


def family_of(n):
    for name, lo, hi, buckets in FAMILIES:
        if lo <= n <= hi:
            return name, buckets
    raise SystemExit("unit %d falls outside every declared family" % n)


def vendor_for(n, unit, family_seq):
    """Executor assignment rule, documented so it is falsifiable.

    1. A unit whose target starts with 'Implementation target' BUILDS confirmation
       apparatus -> anthropic/opus, and its reviewer is cross-vendor.
    2. A unit that dispatches Codex through the MCP rail must itself be the Claude
       side of that rail -> anthropic/opus.
    3. Every other unit CONFIRMS someone else's work. Executors alternate by
       position WITHIN the family so no family's confirmations are all one
       vendor's blind spot.
    Never sonnet: dispatch and adjudication judgement is exactly what fails there.
    """
    if unit["q"].startswith("Implementation target"):
        return {"model": "opus", "vendor": "anthropic", "role": unit["role"]}
    if unit["tools"] in ("xv", "rwxv"):
        return {"model": "opus", "vendor": "anthropic", "role": unit["role"]}
    if family_seq % 2 == 0:
        return {"model": "gpt-5-codex", "vendor": "openai", "role": unit["role"]}
    return {"model": "opus", "vendor": "anthropic", "role": unit["role"]}


out_units = []
family_counter = {}
for i, u in enumerate(RAW, start=1):
    uid = "CNF-%04d" % i
    fam, fam_buckets = family_of(i)
    seq = family_counter.get(fam, 0)
    family_counter[fam] = seq + 1

    deps = list(u["dep"])
    for b in fam_buckets:
        if b not in deps:
            deps.append(b)

    rec = {
        "id": uid,
        "title": u["t"],
        "phase": u["ph"],
        "question_or_target": u["q"],
        "inputs": list(u["inp"]),
        "dependencies": deps,
        "assigned_model_vendor_role": vendor_for(i, u, seq),
        "tool_permissions": list(TOOLS[u["tools"]]),
        "execution_substrate": u["sub"],
        "timeout_seconds": u["to"],
        "output_path": u["out"],
        "output_schema": u["sch"],
        "evidence_requirement": u["ev"],
        "tests_required": list(u["ts"]),
        "reviewer_requirement": REVIEWERS[u["rv"]],
        "completion_sentinel": SENT_TMPL.format(id=uid, post=u["post"]),
        "retry_policy": RETRY[u["rt"]],
        "failure_classification": list(u["fc"]),
        "owner_approval_required": bool(u["ap"]),
    }
    assert list(rec) == FIELDS, (uid, [f for f in rec if f not in FIELDS])
    out_units.append(rec)

# ---- build-time integrity assertions (the verifier re-derives these off disk) --
ids = [r["id"] for r in out_units]
assert len(ids) == len(set(ids)), "duplicate id"
assert ids == ["CNF-%04d" % i for i in range(1, len(ids) + 1)], "ids not sequential from 1"
idset = set(ids)
VALID_BUCKETS = {"B%02d" % i for i in range(1, 14)}
for r in out_units:
    for d in r["dependencies"]:
        if d.startswith("CNF-"):
            assert d in idset, "dangling dep %s in %s" % (d, r["id"])
            assert d < r["id"], "forward/self dep %s in %s" % (d, r["id"])
        else:
            assert d in VALID_BUCKETS, "unknown bucket %s in %s" % (d, r["id"])
    assert r["execution_substrate"] in (
        "local-serialized", "local-parallel", "worktree-isolated", "cloud-batch")
    assert r["phase"] in ("0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7",
                          "7A", "8", "9", "10", "11", "12", "13", "14", "15", "16")
    assert r["assigned_model_vendor_role"]["model"] != "sonnet"
    assert len(r["question_or_target"]) > 150, r["id"]
    assert len(r["tests_required"]) >= 2, r["id"]

target = HERE / "CNF-1.json"
target.write_text(json.dumps(out_units, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
print("WROTE", target, len(out_units), "units")
