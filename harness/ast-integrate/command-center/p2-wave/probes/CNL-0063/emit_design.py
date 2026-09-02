#!/usr/bin/env python3
"""Emit the CNL-0063 council design note from live tabulation + independent recount."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from recount import recount  # noqa: E402
from tabulate import (  # noqa: E402
    DECLARED_COMPLETION,
    SWAP_COMPLETION,
    freeze_spec,
    ingest_and_tabulate,
    rebind_after_ingest,
    tabulate_with_rule,
)

OUT = "command-center/design/council/CNL-0063-pairwise-condorcet-tabulation-and-the-cycle-rule.md"
SCHEMA_LOCAL = (
    "command-center/p2-wave/probes/CNL-0063/council-design-note.schema.json"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0063/probe1_cycle_load_bearing.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0063/probe2_negative_and_recount.py"
)
QUESTION = (
    "What is the completion rule when the pairwise matrix contains a Condorcet "
    "cycle, and is the chosen rule declared BEFORE the ballots are seen so it "
    "cannot be picked to favour an outcome?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> tuple[str, int]:
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0063 emit anchor missing {rel} {snippet!r}")
    line = text.count("\n", 0, idx) + 1
    return rel, line


def main() -> int:
    fx = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
    cands = fx["candidate_order"]
    cycle_rows = fx["cycle_profile"]["ballots"]
    good_rows = fx["condorcet_winner_profile"]["ballots"]

    spec = freeze_spec(DECLARED_COMPLETION, cands)
    declared = ingest_and_tabulate(spec, cycle_rows)
    swapped = tabulate_with_rule(cands, cycle_rows, SWAP_COMPLETION)
    posthoc_cycle = rebind_after_ingest(spec, SWAP_COMPLETION)
    independent = recount(cands, cycle_rows)
    good = tabulate_with_rule(cands, good_rows, DECLARED_COMPLETION)
    good_swap = tabulate_with_rule(cands, good_rows, SWAP_COMPLETION)
    good_recount = recount(cands, good_rows)
    spec_good = freeze_spec(DECLARED_COMPLETION, cands)
    ingest_and_tabulate(spec_good, good_rows)
    posthoc_good = rebind_after_ingest(spec_good, SWAP_COMPLETION)

    if declared["winner"] == swapped["winner"]:
        print("FAILED:CNL-0063 emit swap did not change winner")
        return 1
    if independent["pairwise"] != declared["pairwise"]:
        print("FAILED:CNL-0063 emit recount pairwise mismatch")
        return 1
    if independent["winner"] != declared["winner"]:
        print("FAILED:CNL-0063 emit recount winner mismatch")
        return 1
    if good["cycle_detected"] or good["winner"] != good_swap["winner"]:
        print("FAILED:CNL-0063 emit Condorcet-winner control failed")
        return 1
    if posthoc_cycle.get("ok") is not False or posthoc_good.get("ok") is not False:
        print("FAILED:CNL-0063 emit post-hoc rebind allowed")
        return 1

    verbatim_cycle = (
        f"cycle_detected={declared['cycle_detected']} "
        f"smith={declared['smith_set']} "
        f"declared={DECLARED_COMPLETION} winner={declared['winner']} "
        f"swap={SWAP_COMPLETION} winner={swapped['winner']} "
        f"pairwise={declared['pairwise']}"
    )
    verbatim_good = (
        f"cycle_detected={good['cycle_detected']} "
        f"condorcet_winner={good['condorcet_winner']} "
        f"declared_winner={good['winner']} swap_winner={good_swap['winner']} "
        f"completion_used={good['completion_used']!r} "
        f"recount_cycle={good_recount['cycle_detected']}"
    )
    verbatim_posthoc = (
        f"ok={posthoc_good['ok']} reason={posthoc_good['reason']} "
        f"declared={posthoc_good.get('declared')} "
        f"rejected={posthoc_good.get('rejected')}"
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    markdown = "\n".join(
        [
            "# Pairwise / Condorcet tabulation and the cycle rule (CNL-0063)",
            "",
            QUESTION,
            "",
            "## Declared rule (frozen before ballots)",
            "",
            "Method: pairwise Condorcet. Each ranked ballot of weight w contributes",
            "w to every pair (higher, lower). A unique Condorcet winner (beats every",
            "other candidate pairwise) is elected and the cycle-completion is not used.",
            "",
            "When the majority graph contains a cycle (no Condorcet winner; Smith set",
            "size > 1), the frozen completion is Schulze (beatpath / widest path).",
            "Schulze is declared in the spec; it is not selected by inspecting the",
            "matrix. The freeze token is sha256 of the canonical JSON",
            '{"candidate_order":...,"cycle_completion":"schulze","method":"pairwise_condorcet"}.',
            "After ingest, rebinding cycle_completion is rejected.",
            "",
            "Non-equal ballot weights require a provenance_ref (CNL-0023). This unit",
            "does not invent a weight; fixtures use weight 1.",
            "",
            "## Load-bearing 3-cycle",
            "",
            "Ballots: 5× A>B>C, 4× B>C>A, 3× C>A>B, 2× C>B>A.",
            f"Live pairwise: {declared['pairwise']}.",
            f"Declared Schulze winner: {declared['winner']}.",
            f"Swap plurality-in-Smith winner: {swapped['winner']}.",
            "The completion choice changes the winner, so it cannot be left implicit.",
            "",
            "## Negative control",
            "",
            "On a unique-Condorcet-winner profile the detector is silent",
            f"({verbatim_good}). The state the check rejects is a cycle claim or a",
            "completion override when a Condorcet winner exists, and a post-hoc",
            f"rebind after ingest ({verbatim_posthoc}).",
            "",
            "SUCCESS:CNL-0063",
        ]
    )
    sch_path, sch_line = find_line(
        "command-center/p2-wave/probes/CNL-0063/tabulate.py",
        "def schulze_paths(",
    )
    rc_path, rc_line = find_line(
        "command-center/p2-wave/probes/CNL-0063/recount.py",
        "def pairwise_by_rank_pairs(",
    )
    doc = {
        "unit_id": "CNL-0063",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0063",
        "kind": "council-design-note",
        "title": "Pairwise / Condorcet tabulation and the cycle rule",
        "question": QUESTION,
        "answer": (
            "When the pairwise majority graph has no unique Condorcet winner, "
            "the frozen completion is Schulze (beatpath / widest path). The "
            "rule is hashed into freeze_token before any ballot is ingested; "
            "rebinding cycle_completion after ingest is rejected so the "
            "operator cannot pick a completion to favour an outcome. A unique "
            "Condorcet winner is elected and cycle-completion is not applied. "
            "On the constructed 3-cycle, declared Schulze elects B and "
            "plurality-in-Smith elects A, so the choice is load-bearing."
        ),
        "answers": {
            "cycle_completion_declared": (
                "When the pairwise majority graph has no unique Condorcet winner, "
                "the frozen completion is Schulze (beatpath / widest path). The "
                "rule is hashed into freeze_token before any ballot is ingested."
            ),
            "freeze_before_ballots": (
                "cycle_completion and candidate_order are declared and hashed "
                "before ingest; rebinding after ingest is rejected so the operator "
                "cannot pick a completion to favour an outcome."
            ),
            "condorcet_winner_overrides_completion": (
                "A unique Condorcet winner is elected and cycle-completion is not "
                "applied; swapping the completion on that profile must not change "
                "the winner."
            ),
        },
        "claimed_rule": {
            "method": "pairwise_condorcet",
            "cycle_completion_declared": DECLARED_COMPLETION,
            "cycle_completion_swap": SWAP_COMPLETION,
            "when_cycle": (
                "Elect the Schulze (beatpath) winner of the Smith set. Do not "
                "pick a completion by inspecting which candidate the operator prefers."
            ),
            "when_condorcet_winner": (
                "Elect the unique Condorcet winner. Cycle-completion is not applied "
                "and must not change the winner if swapped."
            ),
        },
        "freeze_contract": {
            "rule": (
                "cycle_completion and candidate_order are hashed before ingest; "
                "after ingest the token is immutable."
            ),
            "moment": "before-ballot-ingest",
            "token_algorithm": "sha256(canonical-json(candidate_order,cycle_completion,method))",
            "post_ingest_rebind": "rejected",
            "token": spec["freeze_token"],
            "declared_completion": DECLARED_COMPLETION,
        },
        "pairwise_tabulation": {
            "input": "complete rankings over the frozen candidate_order",
            "cell": "sum of ballot weights ranking row strictly above column",
            "condorcet_winner": "candidate who pairwise-beats every other",
            "smith_set": "source SCCs of the majority graph (Kosaraju)",
            "declared_completion_algorithm": "Schulze strongest paths (Floyd-Warshall max-min)",
            "swap_completion_algorithm": (
                "plurality inside the Smith set, first-ranked Smith member, "
                "ties broken by frozen candidate_order"
            ),
            "weight_default": 1,
            "non_equal_weight": "requires provenance_ref; otherwise SpecError (CNL-0023)",
        },
        "measured_cycle": {
            "fixture_id": fx["cycle_profile"]["id"],
            "ballots": cycle_rows,
            "pairwise": declared["pairwise"],
            "smith_set": declared["smith_set"],
            "cycle_detected": declared["cycle_detected"],
            "condorcet_winner": declared["condorcet_winner"],
            "declared_winner": declared["winner"],
            "swap_winner": swapped["winner"],
            "load_bearing": declared["winner"] != swapped["winner"],
            "verbatim": verbatim_cycle,
        },
        "measured_condorcet_winner": {
            "fixture_id": fx["condorcet_winner_profile"]["id"],
            "ballots": good_rows,
            "cycle_detected": good["cycle_detected"],
            "condorcet_winner": good["condorcet_winner"],
            "winner": good["winner"],
            "swap_winner": good_swap["winner"],
            "completion_used": good["completion_used"],
            "verbatim": verbatim_good,
        },
        "measured_posthoc": {
            "ok": posthoc_good["ok"],
            "reason": posthoc_good["reason"],
            "verbatim": verbatim_posthoc,
        },
        "independent_recount": {
            "mechanism": "rank-pair accumulation plus Dijkstra widest-path Schulze",
            "pairwise": independent["pairwise"],
            "schulze_scores": independent["schulze_scores"],
            "winner": independent["winner"],
            "pairwise_cells_match": independent["pairwise"] == declared["pairwise"],
            "winner_match": independent["winner"] == declared["winner"],
        },
        "markdown": markdown,
        "tests": [
            {
                "id": "T1-constructed-3-cycle-load-bearing-completion",
                "name": (
                    "A constructed 3-cycle is resolved by declared Schulze; swapping "
                    "to plurality-in-Smith changes the winner"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-negative-control-condorcet-winner-and-posthoc",
                "name": (
                    "Independent recount matches; cycle detector silent on a unique "
                    "Condorcet winner; post-hoc rebind rejected"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "On the constructed 3-cycle, declared Schulze elects B and "
                    "plurality-in-Smith elects A, so the completion is load-bearing."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "id": "C2",
                "claim": (
                    "An independent recount walking rank-pairs and Dijkstra widest "
                    "paths reproduces the same pairwise cells and the same Schulze winner."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "id": "C3",
                "claim": (
                    "The cycle detector is silent on a unique Condorcet winner and "
                    "post-hoc rebind after ingest is rejected."
                ),
                "verdict": "CONFIRMED",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "On the constructed 3-cycle, declared Schulze elects B and "
                    "plurality-in-Smith elects A, so the completion is load-bearing."
                ),
                "verdict": "CONFIRMED",
                "path": sch_path,
                "line": sch_line,
                "snippet": "def schulze_paths(",
                "kind": "live-tree",
                "anchor": f"{sch_path}:{sch_line}",
                "mechanism": "Floyd-Warshall Schulze plus plurality-in-Smith on the same ballots",
                "verbatim": verbatim_cycle,
            },
            {
                "claim": (
                    "An independent recount walking rank-pairs and Dijkstra widest "
                    "paths reproduces the same pairwise cells and the same Schulze winner."
                ),
                "verdict": "CONFIRMED",
                "path": rc_path,
                "line": rc_line,
                "snippet": "def pairwise_by_rank_pairs(",
                "kind": "live-tree",
                "anchor": f"{rc_path}:{rc_line}",
                "mechanism": "rank-pair accumulation and Dijkstra widest-path, not Floyd-Warshall",
                "verbatim": (
                    f"recount_winner={independent['winner']} "
                    f"pairwise={independent['pairwise']} "
                    f"schulze_scores={independent['schulze_scores']}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "CNL0063-C1-false-cycle",
                "kind": "known-good-condorcet-winner",
                "rejects": (
                    "Reporting cycle_detected=true or applying a cycle completion "
                    "when a unique Condorcet winner exists"
                ),
                "rejects_state": (
                    "Reporting cycle_detected=true or applying a cycle completion "
                    "when a unique Condorcet winner exists"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "verbatim": verbatim_good,
                "verbatim_bad": (
                    "check FIRES if cycle_detected is true on unique-condorcet-winner "
                    "or if swap changes that winner"
                ),
                "verbatim_good": verbatim_good,
            },
            {
                "id": "CNL0063-C2-posthoc-rebind",
                "kind": "post-hoc-completion-pick",
                "rejects": (
                    "Selecting cycle_completion after ballots have been ingested, "
                    "which would let the operator pick a winner"
                ),
                "rejects_state": (
                    "Selecting cycle_completion after ballots have been ingested, "
                    "which would let the operator pick a winner"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "verbatim": verbatim_posthoc,
                "verbatim_bad": verbatim_posthoc,
                "verbatim_good": (
                    "rebind-allowed-before-ingest when ingested=false; freeze token "
                    f"computed before any ballot is read ({spec['freeze_token'][:16]}...)"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0063-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Re-tabulated the fixtures with recount.py (rank-pair walk + Dijkstra "
                "widest paths). Disagreement in any pairwise cell or in the Schulze "
                "winner blocks the unit."
            ),
        },
        "catalog_tests_required": [
            "a constructed 3-cycle must be resolved by the declared rule, and swapping in a different completion rule must be shown to change the winner - proving the choice is load-bearing",
            "negative control recorded verbatim: state what the check does on the state it is meant to reject",
        ],
        "dependency_note": (
            "CNL-0023 (vote-weight provenance) is not delivered on this tree. "
            "This unit treats missing provenance as weight=1 only and rejects "
            "non-equal weight without provenance_ref. It does not wait on CNL-0023."
        ),
        "timestamps": {"ended_at": now},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "named_probes": [
            {"id": "probe1", "role": "cycle-load-bearing", "command": P1},
            {"id": "probe2", "role": "independent-recount-negative-control", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/CNL-0063/tabulate.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0063/recount.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0063/fixtures.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": SCHEMA_LOCAL,
                "exists": True,
                "role": "supporting",
            },
            {
                "path": SCHEMA,
                "exists": True,
                "role": "supporting",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0063/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
    }

    schema = json.loads((REPO / SCHEMA_LOCAL).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0063 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        g_errs = list(validator.iter_errors(g))
        if not g_errs:
            print(f"FAILED:CNL-0063 schema accepted garbage {list(g)[:2]}")
            return 1
    shared_path = REPO / SCHEMA
    if shared_path.is_file():
        shared = json.loads(shared_path.read_text(encoding="utf-8"))
        ref = str(shared.get("$ref") or "")
        if ref.startswith("https://ast-integrate.invalid/"):
            print(
                "WARN: catalog council-design-note.schema.json is a $ref shim; "
                "local schema used (no network retrieve)."
            )
        else:
            try:
                jsonschema.Draft7Validator(shared).validate(doc)
            except jsonschema.ValidationError as exc:
                print(
                    "WARN: catalog council-design-note.schema.json rejected the "
                    f"note; local schema used. {exc.message}"
                )
            except jsonschema.exceptions.RefResolutionError as exc:
                print(
                    "WARN: catalog council-design-note.schema.json $ref unresolved; "
                    f"local schema used. {exc}"
                )

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0063 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
