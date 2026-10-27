#!/usr/bin/env python3
"""Adversarial self-audit of this unit's own two load-bearing claims.

CLAIM 1  'the brief's 269 distinct / 1896 references are REFUTED'
   A flat REFUTED is only honest if no reasonable normalization yields those numbers.
   Enumerate six normalizations mechanically and report which, if any, hits 269/1896.

CLAIM 2  'all 236 generated documents resolve and compile'
   Compiling a $ref does NOT prove the referring document is itself a legal
   draft-2020-12 schema. Meta-validate every generated document.

CLAIM 3  quantify what is NOT class-discriminated, so the coverage claim is scoped.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver as sr  # noqa: E402
from jsonschema.validators import Draft202012Validator  # noqa: E402


def claim1() -> dict:
    wus = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_bytes().decode("utf-8")
    )["work_units"]
    raw = [w["output_schema"] for w in wus]

    def norm_none(s):
        return s

    def norm_frag(s):
        return s.split("#", 1)[0]

    def norm_ann(s):
        return s.split(" ", 1)[0]

    def norm_both(s):
        return s.split(" ", 1)[0].split("#", 1)[0]

    variants = {
        "raw_strings": [norm_none(s) for s in raw],
        "strip_fragment_only": [norm_frag(s) for s in raw],
        "strip_annotation_only": [norm_ann(s) for s in raw],
        "strip_both (file path)": [norm_both(s) for s in raw],
        "strip_both, drop meta-url": [norm_both(s) for s in raw if not s.startswith("http")],
        "basenames only": [os.path.basename(norm_both(s)) for s in raw],
    }
    rows = {}
    for name, vals in variants.items():
        rows[name] = {"distinct": len(set(vals)), "references": len(vals)}
    hits_269 = [k for k, v in rows.items() if v["distinct"] == 269]
    hits_1896 = [k for k, v in rows.items() if v["references"] == 1896]
    return {
        "normalizations": rows,
        "any_normalization_gives_269_distinct": hits_269,
        "any_normalization_gives_1896_references": hits_1896,
        "VERDICT": (
            "REFUTED - no normalization reproduces either number"
            if not hits_269 and not hits_1896
            else "PARTIAL - some normalization reproduces a briefed number"
        ),
    }


def claim2() -> dict:
    reg = sr.load_registry()
    docs = [
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/ARTIFACT-CLASS-REGISTRY.json",
    ] + sorted(reg["entries"])
    meta = Draft202012Validator(dict(Draft202012Validator.META_SCHEMA))
    bad = []
    checked = 0
    for rel in docs:
        p = REPO / rel
        doc = json.loads(p.read_bytes().decode("utf-8"))
        if rel.endswith("ARTIFACT-CLASS-REGISTRY.json"):
            continue  # data file, not a schema
        checked += 1
        errs = [e.message for e in meta.iter_errors(doc)]
        if errs:
            bad.append({"file": rel, "errors": errs[:3]})
    # detector control: a KNOWN-BAD schema doc must be caught
    control_fires = bool(list(meta.iter_errors({"type": 7})))
    control_silent_on_good = not list(meta.iter_errors({"type": "object"}))
    return {
        "documents_meta_validated": checked,
        "documents_failing_meta_validation": bad,
        "detector_fires_on_known_bad": control_fires,
        "detector_silent_on_known_good": control_silent_on_good,
        "VERDICT": (
            "CONFIRMED" if not bad and control_fires and control_silent_on_good
            else "REFUTED"
        ),
    }


def claim3() -> dict:
    wus = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_bytes().decode("utf-8")
    )["work_units"]
    pinned = unpinned = meta = 0
    unpinned_ids = Counter()
    ann = 0
    for w in wus:
        d = w["output_schema"]
        res = sr.resolve(d)
        if res.kind == "meta-schema-url" or res.kind == "meta-schema-mirror":
            meta += 1
        elif res.report_kind_pinned:
            pinned += 1
        else:
            unpinned += 1
            unpinned_ids[res.logical_id] += 1
            if " profile=" in d:
                ann += 1
    return {
        "references_resolving_to_a_kind_pinned_class": pinned,
        "references_resolving_to_the_UNPINNED_canonical_receipt": unpinned,
        "of_those_carrying_a_profile_annotation": ann,
        "references_resolving_to_the_meta_schema": meta,
        "unpinned_logical_ids": dict(unpinned_ids),
        "why_unpinned_is_deliberate": (
            "receipt.schema.json's own $defs.receipt_core.properties.profile says the 30 "
            "profile= variants 'all declare the same required core, so a profile narrows "
            "nothing structurally and is carried for routing only'. Pinning profile would "
            "invent a contract the source explicitly says does not exist. These references "
            "still get the full receipt_core discipline plus the 12-condition predicate; "
            "what they do NOT get is cross-class discrimination."
        ),
    }


def main() -> int:
    out = {"claim1_brief_numbers": claim1(), "claim2_meta_validation": claim2(), "claim3_discrimination_scope": claim3()}
    ok = out["claim2_meta_validation"]["VERDICT"] == "CONFIRMED"
    (REPO / "platform" / "lib" / "_probe_substrate_selfaudit_out.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=2)[:4500])
    print("SUCCESS:substrate-selfaudit" if ok else "FAILED:substrate-selfaudit")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
