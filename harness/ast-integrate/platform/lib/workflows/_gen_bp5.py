#!/usr/bin/env python
"""Emit the 12 bp-5 blueprint documents (library cards 49-60) and prove they are distinct.

Run from the repo root::

    python platform/lib/workflows/_gen_bp5.py

Gates, in order. Any failure exits non-zero and NOTHING is written:

1. the three-layer self-check (schema, DSL-SEM-001..014, executed worked example) per document
2. MECHANICAL distinctness: the (subject, oracle, comparison_axis, output_type) key must be
   unique across all 12. LLM judgement is not used for a question a set comparison answers -
   measured 86% accuracy with 100% of errors pointing at data loss.
3. every ``work_unit_ref`` resolves to a real id in command-center/WORK-UNIT-CATALOG.json
4. no inline work-unit id collides with a catalog id, and no inline prefix is a catalog prefix
5. flagship count clears the spec's pro-rata floor (40 of 96 -> 5 of 12)
"""

from __future__ import annotations

import itertools
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
REPO = LIB.parents[1]
for p in (str(HERE), str(LIB)):
    if p not in sys.path:
        sys.path.insert(0, p)

import _bp5_crv_a as CRV_A  # noqa: E402
import _bp5_crv_b as CRV_B  # noqa: E402
import _bp5_selfcheck as SELFCHECK  # noqa: E402
import _bp5_tst_a as TST_A  # noqa: E402
import _bp5_tst_b as TST_B  # noqa: E402
from _bp5_terminal import append_verdict_stage, terminal_gates  # noqa: E402
from bp7_common import write_blueprint  # noqa: E402

CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

BUILDERS = [
    CRV_A.build_split_role_panel,
    CRV_A.build_differential_with_history,
    CRV_A.build_refactor_equivalence,
    CRV_B.build_variant_sweep,
    CRV_B.build_overclaim_scoping,
    TST_A.build_smallest_check_ladder,
    TST_A.build_mutation_gate,
    TST_A.build_spec_blind_synthesis,
    TST_B.build_ui_invariant_walk,
    TST_B.build_packaged_smoke,
    TST_B.build_red_proof_certification,
    TST_B.build_event_reachability,
]

DISTINCTNESS_KEY = ("subject", "oracle", "comparison_axis", "output_type")
FLAGSHIP_FLOOR = 5  # 40 of 96 pro-rata over a 12-card slice = 5.0


def _walk(node: Any, key: str) -> list[Any]:
    out: list[Any] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                out.append(v)
            out.extend(_walk(v, key))
    elif isinstance(node, list):
        for v in node:
            out.extend(_walk(v, key))
    return out


def check_distinctness(docs: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Exact set comparison over the declared mechanism fingerprints."""
    lines: list[str] = []
    keys: dict[tuple, list[str]] = {}
    prints: dict[str, dict[str, Any]] = {}
    for d in docs:
        fp = (d.get("x_extensions") or {}).get("mechanism_fingerprint")
        if not isinstance(fp, dict):
            lines.append(f"MISSING-FINGERPRINT {d['id']}")
            continue
        missing = [f for f in DISTINCTNESS_KEY if f not in fp]
        if missing:
            lines.append(f"INCOMPLETE-FINGERPRINT {d['id']}: {missing}")
            continue
        prints[d["id"]] = fp
        keys.setdefault(tuple(fp[f] for f in DISTINCTNESS_KEY), []).append(d["id"])

    for key, ids in sorted(keys.items(), key=lambda kv: kv[1]):
        if len(ids) > 1:
            lines.append(
                f"DUPLICATE-MECHANISM {ids} share {dict(zip(DISTINCTNESS_KEY, key))}"
            )

    # closest pair over the FULL fingerprint, reported so the residual is visible rather than
    # implied by the absence of an exact collision.
    fields = sorted({f for fp in prints.values() for f in fp})
    best: tuple[float, str, str, list[str]] = (-1.0, "", "", [])
    for a, b in itertools.combinations(sorted(prints), 2):
        shared = [f for f in fields if prints[a].get(f) == prints[b].get(f)]
        score = len(shared) / len(fields)
        if score > best[0]:
            best = (score, a, b, shared)
    if best[0] >= 0:
        lines.append(
            f"CLOSEST-PAIR {best[1]} vs {best[2]} agree on {len(best[3])}/{len(fields)} "
            f"fingerprint fields ({best[0]:.0%}); they differ on "
            f"{sorted(set(fields) - set(best[3]))}"
        )
    ok = not any(
        ln.startswith(
            ("DUPLICATE-MECHANISM", "MISSING-FINGERPRINT", "INCOMPLETE-FINGERPRINT")
        )
        for ln in lines
    )
    return ok, lines


def check_catalog_refs(docs: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    real = {u["id"] for u in catalog["work_units"]}
    prefixes = {m.group(1) for i in real if (m := re.match(r"^([A-Z]+)-", i))}
    lines: list[str] = []
    refs: set[str] = set()
    inline: set[str] = set()
    for d in docs:
        refs.update(str(r) for r in _walk(d, "work_unit_ref"))
        for u in _walk(d, "work_unit"):
            if isinstance(u, dict) and "id" in u:
                inline.add(str(u["id"]))
    dangling = sorted(r for r in refs if r not in real)
    if dangling:
        lines.append(f"DANGLING-WORK-UNIT-REF {dangling}")
    collide = sorted(i for i in inline if i in real)
    if collide:
        lines.append(f"INLINE-ID-COLLIDES-WITH-CATALOG {collide}")
    bad_prefix = sorted(
        i
        for i in inline
        if (m := re.match(r"^([A-Z]+)-", i)) and m.group(1) in prefixes
    )
    if bad_prefix:
        lines.append(f"INLINE-PREFIX-IS-A-CATALOG-PREFIX {bad_prefix}")
    lines.append(
        f"catalog refs used: {len(refs)} distinct, all resolving={not dangling}; "
        f"inline units minted: {len(inline)}; catalog prefixes: {len(prefixes)}"
    )
    return (not dangling and not collide and not bad_prefix), lines


#: Per-blueprint terminal verdict stage, closing the terminal-gate hole this slice's own
#: mutation control found (see _bp5_terminal.py). Keyed by workflow id.
VERDICT_STAGES: dict[str, dict[str, Any]] = {
    "crv.differential-change-review-with-history": dict(
        stage_id="emit-differential-verdict",
        title="Emit the differential verdict only after the surface and partition gates pass",
        role="surface-auditor",
        work_unit_ref="ADV-0002",
        path="command-center/review/crv-50-differential-verdict.json",
        schema_ref="command-center/schema/second-order-review.schema.json",
        consumers=["crv.bug-class-variant-sweep", "command-center/CLAIM-REGISTRY.json"],
    ),
    "crv.refactor-equivalence-proof": dict(
        stage_id="record-advisory-verdict",
        title="Record the advisory verdict downstream of the bound-disclosure gate",
        role="equivalence-runner",
        work_unit_ref="TST-0058",
        path="command-center/review/crv-51-advisory-verdict.json",
        schema_ref="command-center/schema/completion-verdict.schema.json",
        consumers=["crv.overclaim-scoping-review"],
    ),
    "crv.overclaim-scoping-review": dict(
        stage_id="emit-scoping-verdict",
        title="Emit the scoping verdict only after the defect-police gate clears",
        role="claim-rewriter",
        work_unit_ref="SYN-0015",
        path="command-center/review/crv-53-scoping-verdict.json",
        schema_ref="command-center/schema/completion-verdict.schema.json",
        consumers=["command-center/CLAIM-REGISTRY.json"],
    ),
    "tst.diff-scoped-mutation-gate": dict(
        stage_id="emit-mutation-verdict",
        title="Emit the mutation verdict only after the source-restored gate clears",
        role="survivor-triager",
        work_unit_ref="BLD-0039",
        path="command-center/test/qlt-55-mutation-verdict.json",
        schema_ref="command-center/schema/test-quality-census.schema.json",
        consumers=["tst.fail-first-red-proof-certification"],
    ),
    "tst.spec-blind-test-synthesis": dict(
        stage_id="record-shadow-verdict",
        title="Record the shadow verdict downstream of the blindness and shadow gates",
        role="leak-auditor",
        work_unit_ref="ADV-0109",
        path="command-center/test/qlt-56-shadow-verdict.json",
        schema_ref="command-center/schema/completion-verdict.schema.json",
        consumers=["command-center/CLAIM-REGISTRY.json"],
    ),
    "tst.ui-invariant-walk": dict(
        stage_id="record-walk-verdict",
        title="Record the walk verdict downstream of the coverage and shadow gates",
        role="walker",
        work_unit_ref="TST-0118",
        path="command-center/ui/qlt-57-walk-verdict.json",
        schema_ref="command-center/schema/completion-verdict.schema.json",
        consumers=["command-center/CLAIM-REGISTRY.json"],
    ),
}


def apply_verdict_stages(docs: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    by_id = {d["id"]: d for d in docs}
    for wid, cfg in VERDICT_STAGES.items():
        doc = by_id.get(wid)
        if doc is None:
            notes.append(f"MISSING-DOC {wid}")
            continue
        before = terminal_gates(doc)
        append_verdict_stage(doc, **cfg)
        after = terminal_gates(doc)
        notes.append(
            f"{wid}: terminal gates {len(before)} -> {len(after)} "
            f"(anchored {before} to {cfg['stage_id']})"
        )
    for d in docs:
        left = terminal_gates(d)
        if left:
            notes.append(f"STILL-TERMINAL {d['id']}: {left}")
    return notes


def main() -> int:
    docs = [b() for b in BUILDERS]
    print(f"=== built {len(docs)} documents ===")

    print(
        "\n=== closing the terminal-gate hole (found by this slice's own mutation control) ==="
    )
    notes = apply_verdict_stages(docs)
    for note in notes:
        print(f"  {note}")
    if any(n.startswith(("STILL-TERMINAL", "MISSING-DOC")) for n in notes):
        print(
            "FAILED:blueprints/bp-5 a gate is still deletable without breaking the graph"
        )
        return 1

    print("\n=== layer 1-3 self-check ===")
    if SELFCHECK.report(docs) != 0:
        print(
            "FAILED:blueprints/bp-5 self-check rejected at least one document; nothing written"
        )
        return 1

    print("\n=== mechanical distinctness (exact set comparison) ===")
    ok_d, lines = check_distinctness(docs)
    for ln in lines:
        print(f"  {ln}")

    print("\n=== catalog reference integrity ===")
    ok_r, lines = check_catalog_refs(docs)
    for ln in lines:
        print(f"  {ln}")

    flagships = [d["id"] for d in docs if d.get("flagship")]
    print(
        f"\n=== flagship count: {len(flagships)}/{len(docs)} (floor {FLAGSHIP_FLOOR}) ==="
    )
    for f in flagships:
        print(f"  FLAGSHIP {f}")
    ok_f = len(flagships) >= FLAGSHIP_FLOOR

    cats: dict[str, list[str]] = {}
    for d in docs:
        for c in d.get("categories", []):
            cats.setdefault(c, []).append(d["id"])
    print("\n=== category span ===")
    for c, ids in sorted(cats.items()):
        print(f"  {c}: {len(ids)}")

    if not (ok_d and ok_r and ok_f):
        print("FAILED:blueprints/bp-5 distinctness/refs/flagship gate; nothing written")
        return 1

    print("\n=== writing ===")
    for d in docs:
        path = write_blueprint(d)
        print(
            f"  wrote {path.relative_to(REPO).as_posix()} ({path.stat().st_size} bytes)"
        )
    print(f"SUCCESS:blueprints/bp-5 {len(docs)} blueprints emitted and validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
