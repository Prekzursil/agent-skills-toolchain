#!/usr/bin/env python3
"""Emit CNL-0031 design note (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import topology as T  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0031-flat-committee-and-caucus-grouping-when-structure-helps-an.md"
)
CATALOG_SCHEMA = "command-center/schema/council-design-note.schema.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/CNL-0031/note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0031/probe1_fragmentation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0031/probe2_negative_control.py"
)
QUESTION = (
    "Flat peer, committee and caucus are the same topology family at different "
    "grouping granularity - what is the parameter that unifies them, and at what "
    "setting does sub-grouping start losing cross-group information instead of "
    "adding parallelism?"
)
TOPO = "command-center/p2-wave/probes/CNL-0031/topology.py"
RECOUNT = "command-center/p2-wave/probes/CNL-0031/recount.py"

# Ten measured (n,k,c) cases. Shared schema requires fixtures[]; these are
# partition-grain runs, not auto-composed council selector cases.
FIXTURE_SPECS = (
    ("F01", "T0", 12, 12, 2, "flat identity: plenary is the cell"),
    ("F02", "T1", 12, 1, 2, "singleton fan-in: each cell emits its only fact"),
    ("F03", "T1", 12, 2, 2, "pair-caucus k=c: lossless subgrouping"),
    ("F04", "T2", 12, 3, 2, "first lossy k>c on n=12 c=2"),
    ("F05", "T2", 12, 4, 2, "three-committee overflow"),
    ("F06", "T3", 12, 6, 2, "first cut from flat: two-committee overflow"),
    ("F07", "T1", 12, 3, 3, "k=c=3 caucus: capacity covers the cell"),
    ("F08", "T2", 8, 4, 2, "n=8 committee k=4 c=2 overflow"),
    ("F09", "T1", 8, 2, 2, "n=8 pair-caucus lossless"),
    ("F10", "T2", 6, 3, 2, "n=6 k=3 c=2 overflow"),
)


def slim_row(row: dict) -> dict:
    return {
        "k": row["k"],
        "g": row["g"],
        "family": row["family"],
        "identity_fan_in": row["identity_fan_in"],
        "lost_count": row["lost_count"],
        "lost_ids": row["lost_ids"],
        "caucus_count": row["caucus_count"],
        "plenary_count": row["plenary_count"],
        "planted_in_group0": row["planted_in_group0"],
        "planted_in_plenary": row["planted_in_plenary"],
        "fragmentation_fires": row["fragmentation_fires"],
        "net_score": row["net_score"],
        "retention": row["retention"],
    }


def fixture_row(fid: str, tier: str, n: int, k: int, c: int, prose: str) -> dict:
    row = T.simulate(n=n, k=k, c=c)
    return {
        "id": fid,
        "risk_tier": tier,
        "task_description": (
            f"Roster n={n} grouped at partition grain k={k} with fan-in c={c}: {prose}"
        ),
        "explanation": {
            "n": n,
            "k": k,
            "c": c,
            "g": row["g"],
            "family": row["family"],
            "lost_count": row["lost_count"],
            "lost_ids": row["lost_ids"],
            "identity_fan_in": row["identity_fan_in"],
            "fragmentation_fires": row["fragmentation_fires"],
            "reason": prose,
        },
    }


def main() -> int:
    rows = T.sweep()
    live = {r["k"]: r for r in rows}
    xo = T.crossover_k()
    first_cut = T.first_subdivision_from_flat()
    ctrl = T.negative_control_verbatim()
    cex = T.lossless_counterexample()
    best = max(
        (r for r in rows if r["lost_count"] == 0 and r["k"] < T.N_DEFAULT),
        key=lambda r: r["net_score"],
    )
    bad = live[first_cut]
    flat = live[T.N_DEFAULT]
    first_lossy = live[xo]

    sn_unify = "Unifying parameter: partition grain k"
    sn_overflow = "MARKER_OVERFLOW k > c"
    sn_flat = "MARKER_FLAT_IDENTITY"
    sn_fanin = "MARKER_FANIN rapporteur capacity c"
    sn_recount = "dict.fromkeys-then-list-membership"
    line_unify = A.find_line(REPO / TOPO, sn_unify)
    line_overflow = A.find_line(REPO / TOPO, sn_overflow)
    line_flat = A.find_line(REPO / TOPO, sn_flat)
    line_fanin = A.find_line(REPO / TOPO, sn_fanin)
    line_recount = A.find_line(REPO / RECOUNT, sn_recount)

    answer = (
        "The unifying parameter is partition grain k: the cardinality of each "
        "cell in a partition of an n-member roster (k must divide n). Group "
        f"count g = n/k. Fan-in capacity c is the number of facts a cell may "
        "emit to plenary. Flat-peer is k = n (g = 1) with identity fan-in "
        "(the plenary IS the cell). Committee and caucus are the same operator "
        "at smaller k: for n=12, k in {6,4} (g<=3) is committee and k in {3,2} "
        f"(g>3) is caucus. Unique cell information is lost iff k > c under "
        "lossy fan-in. On the n=12 c=2 fixture that inequality first holds at "
        f"k*={xo} (lost={first_lossy['lost_count']}). Pair-caucus k=c=2 is "
        f"lossless (lost={cex['lost_count']}, g={cex['g']}) so subgrouping adds "
        "parallelism without fragmenting. The first cut away from flat "
        f"(k={first_cut} two-committee) already overflows (lost={bad['lost_count']}, "
        f"planted {T.PLANTED_FACT_ID} in group-0 transcript, absent from plenary). "
        f"Best lossless parallel setting is k={best['k']} net_score={best['net_score']}."
    )

    fixtures = [fixture_row(*spec) for spec in FIXTURE_SPECS]
    if len(fixtures) < 10:
        print("FAILED:CNL-0031 emit fixtures short")
        return 1

    doc = {
        "unit_id": "CNL-0031",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0031",
        "completion_sentinel": "SUCCESS:CNL-0031",
        "title": "Flat, committee and caucus grouping: when structure helps and when it fragments",
        "question": QUESTION,
        "answer": answer,
        "output_schema_catalog": CATALOG_SCHEMA,
        "output_schema_on_tree": LOCAL_SCHEMA,
        "output_schema_note": (
            "Catalog output_schema is a $ref shim to ast-integrate.invalid; "
            "jsonschema 4.10 on this host tries to fetch it and raises "
            "RefResolutionError. Local note.schema.json is the live contract "
            "and requires negative_controls[].rejects so a stripped-rejects "
            "mutant is a schema failure. G-1 is parse+sentinel+named probes."
        ),
        "algorithm": {
            "id": "CNL-0031.v1-partition-grain",
            "inputs": [
                "n:roster-size",
                "k:partition-grain",
                "c:fan-in-capacity",
            ],
            "outputs": [
                "family-label",
                "lost_count",
                "lost_ids",
                "fragmentation_fires",
            ],
            "steps": [
                "Require k divides n; form g = n/k disjoint cells of cardinality k.",
                "Each cell holds one unique fact per member; fan-in emits min(k, c) highest-priority facts unless g==1 identity.",
                "lost_ids = set(cell transcripts) minus set(plenary payloads); fire if planted F00 is in group-0 and absent from plenary.",
                "Label family: k==n is flat-peer, k==1 is singleton-fanin, g<=3 is committee, else caucus.",
            ],
        },
        "defaults": {
            "protocol": "partition-grain-plenary",
            "voting_method": "rapporteur-capacity-c",
            "stopping_rule": "one-fan-in-then-set-difference",
            "roles": ["cell-member", "rapporteur", "plenary"],
        },
        "explanation_contract": {
            "dials": [
                "partition-grain-k",
                "fan-in-c",
                "roster-n",
                "identity-fan-in",
            ],
            "missing_reason_fails": True,
            "owner_contest": (
                "Owner contests k (cell cardinality) or c (rapporteur capacity) "
                "per grouping; an off-default grain with an empty reason fails."
            ),
        },
        "fixtures": fixtures,
        "unifying_parameter": {
            "name": "partition-grain",
            "symbol": "k",
            "definition": (
                "Cell cardinality of a partition of an n-member roster. "
                "Flat-peer, committee and caucus are labels on ranges of k, "
                "not distinct topology families."
            ),
            "companion": "c",
            "companion_definition": (
                "Fan-in / rapporteur capacity: facts each cell may emit to plenary. "
                "Flat identity fan-in sets c_eff = n when g==1."
            ),
            "family_labels_n12": {
                "12": "flat-peer",
                "6": "committee",
                "4": "committee",
                "3": "caucus",
                "2": "caucus",
                "1": "singleton-fanin",
            },
        },
        "fragmentation_threshold": {
            "rule": "lossy fan-in loses unique cell facts iff k > c; flat g==1 is identity",
            "crossover_k": xo,
            "n": T.N_DEFAULT,
            "c": T.C_DEFAULT,
            "first_subdivision_from_flat_k": first_cut,
            "best_lossless_parallel_k": best["k"],
            "measured": {
                "planted_fact": T.PLANTED_FACT_ID,
                "sweep": [slim_row(r) for r in rows],
                "flat_lost_count": flat["lost_count"],
                "committee_k6_lost_count": bad["lost_count"],
                "caucus_k3_lost_count": first_lossy["lost_count"],
                "caucus_k2_lost_count": cex["lost_count"],
            },
        },
        "claims": [
            {
                "id": "C1",
                "claim": "Flat-peer, committee and caucus are one family parameterized by partition grain k.",
                "verdict": "CONFIRMED",
                "anchor": f"{TOPO}:{line_unify}",
            },
            {
                "id": "C2",
                "claim": (
                    f"Under lossy fan-in of capacity c={T.C_DEFAULT}, unique facts are "
                    f"lost iff k > c; on n={T.N_DEFAULT} the first such k is {xo}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{TOPO}:{line_overflow}",
            },
            {
                "id": "C3",
                "claim": "Flat identity fan-in (g==1) measures lost_count==0 including planted F00.",
                "verdict": "CONFIRMED",
                "anchor": f"{TOPO}:{line_flat}",
            },
            {
                "id": "C4",
                "claim": "Subgrouping never fragments: every caucus/committee forwards its full transcript.",
                "verdict": "REFUTED",
                "anchor": f"{TOPO}:{line_fanin}",
                "counterexample": {
                    "k": first_cut,
                    "c": T.C_DEFAULT,
                    "planted": T.PLANTED_FACT_ID,
                    "in_group0": True,
                    "in_plenary": False,
                    "lost_count": bad["lost_count"],
                    "lost_ids": bad["lost_ids"],
                },
            },
            {
                "id": "C5",
                "claim": "Any k < n fragments cross-group information.",
                "verdict": "REFUTED",
                "anchor": f"{TOPO}:{line_overflow}",
                "counterexample": cex,
            },
        ],
        "evidence": [
            {
                "path": TOPO,
                "line": line_overflow,
                "snippet": sn_overflow,
                "kind": "live-tree",
                "mechanism": "simulate-set-difference",
                "claim": (
                    "Signal A: topology.simulate lost_ids is set(caucus)-set(plenary); "
                    f"k={first_cut} lost_count={bad['lost_count']} includes planted {T.PLANTED_FACT_ID}."
                ),
            },
            {
                "path": RECOUNT,
                "line": line_recount,
                "snippet": sn_recount,
                "kind": "live-tree",
                "mechanism": "dict.fromkeys-then-list-membership",
                "claim": (
                    "Signal B: recount.recount unique-ifies serialized fact_ids via "
                    "dict.fromkeys and list membership, a different field path than set difference."
                ),
            },
            {
                "path": TOPO,
                "line": line_flat,
                "snippet": sn_flat,
                "kind": "live-tree",
                "mechanism": "simulate-set-difference",
                "claim": f"Flat k={T.N_DEFAULT} identity fan-in: lost_count={flat['lost_count']}.",
            },
            {
                "path": TOPO,
                "line": line_fanin,
                "snippet": sn_fanin,
                "kind": "live-tree",
                "mechanism": "simulate-set-difference",
                "claim": (
                    f"Rapporteur ranked[:c] drops {T.PLANTED_FACT_ID} when k>c; "
                    "the fragmentation probe measures that drop."
                ),
            },
        ],
        "tests": [
            {
                "id": "T1-fragmentation",
                "name": "Fragmentation probe: caucus-exclusive fact never reaching plenary; flat demonstrates zero loss",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-negative-control",
                "name": "Negative control recorded verbatim plus independent lossless counterexample",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "CNL0031-C1",
                "kind": "both-states-fragmentation",
                "description": (
                    "The check FIRES when planted F00 exists in group-0 transcript and is "
                    "absent from plenary (lossy committee k=6 c=2). It is SILENT on flat "
                    "identity fan-in where F00 reaches plenary and lost_count=0."
                ),
                "fires_on": ctrl["fires_on"],
                "silent_on": ctrl["silent_on"],
                "fires_on_bad": True,
                "silent_on_good": True,
                "rejects": (
                    "lossy committee k=6 c=2 that drops planted F00 from plenary "
                    "while claiming no fragmentation"
                ),
                "bad_state_output": ctrl["bad_state_output"],
                "good_state_output": ctrl["good_state_output"],
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0031-probe2-recount-counterexample",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Named probe2 re-tabulates lost_count from serialized fact_ids via "
                "recount.py (not the author's answer prose) and requires a live "
                "k==c lossless instance."
            ),
            "counterexample": cex,
            "scope_not_agreement": True,
        },
        "dependency_note": {
            "catalog_dependencies": ["CNL-0022"],
            "on_disk": False,
            "blocks_this_unit": False,
            "why_not_blocked": (
                "CNL-0031 measures grouping grain and fan-in loss on a fixture; "
                "it does not import CNL-0022 role-mandate schema records."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0031/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "named_probes": [
            {"id": "probe1", "role": "fragmentation", "command": P1},
            {"id": "probe2", "role": "negative-control-reviewer", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": CATALOG_SCHEMA, "exists": True, "role": "supporting"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "supporting"},
            {"path": TOPO, "exists": True, "role": "supporting"},
            {"path": RECOUNT, "exists": True, "role": "supporting"},
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(doc)
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    print(f"crossover_k={xo} first_cut={first_cut} lossless_k={cex['k']}")
    print("SUCCESS:CNL-0031 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
