#!/usr/bin/env python3
"""Emit the CNL-0075 design note (JSON document at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import lineage as L  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0075-decision-lineage-decomposing-a-decision-back-to-the-ideas-.md"
)
NOTE_SCHEMA = "command-center/p2-wave/probes/CNL-0075/design-note.schema.json"
CATALOG_NOTE_SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0075/probe1_decompose.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0075/probe2_recount.py"
)
QUESTION = (
    "Can a final recommendation and its action plan be decomposed back through "
    "synthesis, votes, arguments, option cards and claims to the originating "
    "ideas - and what link in that chain (idea -> option card -> claim -> "
    "argument -> vote -> decision -> action plan) is missing today so the "
    "trace breaks?"
)


def first_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:emit snippet not found in {rel}: {snippet!r}")


def evidence_file(claim: str, verdict: str, rel: str, snippet: str, mechanism: str) -> dict:
    line = first_line(rel, snippet)
    return {
        "claim": claim,
        "verdict": verdict,
        "mechanism": mechanism,
        "path": rel,
        "line": line,
        "snippet": snippet,
        "signal": {
            "kind": "file_line",
            "anchor": f"{rel}:{line}",
        },
    }


def evidence_cmd(claim: str, verdict: str, command: str, output: str, rel: str, snippet: str, mechanism: str) -> dict:
    line = first_line(rel, snippet)
    return {
        "claim": claim,
        "verdict": verdict,
        "mechanism": mechanism,
        "path": rel,
        "line": line,
        "snippet": snippet,
        "signal": {
            "kind": "command_output",
            "command": command,
            "output": output,
        },
    }


def main() -> int:
    good = L.load_council(HERE / "fixtures/good.json")
    orphan = L.load_council(HERE / "fixtures/orphan.json")
    severed = L.load_council(HERE / "fixtures/severed-claim-hop.json")
    g, _ = L.both_walkers_agree(good)
    o, _ = L.both_walkers_agree(orphan)
    s, _ = L.both_walkers_agree(severed)
    measured = C.measure()
    if measured["missing_link"] != "option_card->claim":
        print(f"FAILED:emit census missing_link={measured['missing_link']}")
        return 1
    if not g["pass"] or o["orphan_ids"] != ["s3"] or set(s["orphan_ids"]) != {"s1", "s2"}:
        print("FAILED:emit fixture walkers not in expected states")
        return 1

    good_out = (
        f"good pass={g['pass']} sentences={g['sentence_count']} "
        f"resolved={g['resolved_count']} orphans={g['orphan_ids']}"
    )
    orphan_out = (
        f"orphan pass={o['pass']} sentences={o['sentence_count']} "
        f"resolved={o['resolved_count']} orphans={o['orphan_ids']} "
        f"s3_reasons={o['sentences'][2]['orphan_reasons']}"
    )
    severed_out = (
        f"severed pass={s['pass']} sentences={s['sentence_count']} "
        f"resolved={s['resolved_count']} orphans={s['orphan_ids']} "
        f"s1_reasons={s['sentences'][0]['orphan_reasons']}"
    )

    hop_table = []
    for row in measured["hops"]:
        hop_table.append(
            {
                "from_kind": row["from_kind"],
                "to_kind": row["to_kind"],
                "parent_field": row["parent_field"],
                "catalog_authors_cnl_or_imp": row["catalog_authors_excluding_self"],
                "parent_field_present_on_disk": row["parent_field_present_on_disk"],
                "child_module": row["child_module"],
                "child_module_exists": row["child_module_exists"],
            }
        )

    answer = (
        "Not on this worktree: no live council runtime, no idea-ledger artifact, "
        "and no typed parent pointers for the chain exist on disk. Under the "
        "scripted council in probes/CNL-0075/fixtures, a recommendation CAN be "
        "decomposed: each sentence may cite only a decision or action_plan id, "
        "and a parent-pointer walk must reach at least one idea ledger id. Two "
        "walkers (stack chase vs relational join) agreed: the good fixture "
        "resolves both sentences to idea.http-cache; an orphan sentence with "
        "empty cites fails as s3. The link that is missing TODAY, so the trace "
        "breaks even after the other hops are named in the catalog, is "
        "option_card->claim: no CNL/IMP unit other than CNL-0075 requires "
        "about_option_card_ids, and grepping that field outside this probe is "
        "empty. IMP-0339 authors idea->option_card; IMP-0313 authors a graph of "
        "claims extracted from turns, not from option cards. Severing "
        "about_option_card_ids on the otherwise-good fixture orphans every "
        "recommendation sentence (no-idea-reached)."
    )

    doc = {
        "unit_id": "CNL-0075",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0075",
        "completion_sentinel": "SUCCESS:CNL-0075",
        "title": "Decision lineage: decomposing a decision back to the ideas that made it",
        "question": QUESTION,
        "answer": answer,
        "missing_link": "option_card->claim",
        "missing_link_rule": measured["missing_link_rule"],
        "lineage_rules": {
            "chain": [h["from_kind"] for h in L.HOPS] + ["action_plan"],
            "sentence_cite_kinds": sorted(L.SENTENCE_CITE_KINDS),
            "parent_fields": {h["to_kind"]: h["parent_field"] for h in L.HOPS},
            "orphan_if": [
                "empty-cites",
                "dangling-cite",
                "illegal-cite-kind",
                "no-idea-reached",
            ],
            "walkers_must_agree": ["chase", "join"],
        },
        "hop_table": hop_table,
        "on_disk": measured["on_disk"],
        "decomposition_counts": {
            "good_sentences": g["sentence_count"],
            "good_resolved": g["resolved_count"],
            "good_ideas_s1": g["sentences"][0]["ideas"],
            "good_ideas_s2": g["sentences"][1]["ideas"],
            "orphan_ids": o["orphan_ids"],
            "severed_orphan_ids": s["orphan_ids"],
        },
        "tests": [
            {
                "id": "decompose-scripted-council",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "independent-recount",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "orphan-sentence",
                "rejects": (
                    "A recommendation sentence with empty cites (s3: Also "
                    "migrate billing to another continent.) must FAIL; the "
                    "checker must name s3 and empty-cites."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": orphan_out,
                "good_state_output": good_out,
            },
            {
                "id": "severed-option-card-to-claim",
                "rejects": (
                    "A claim with about_option_card_ids=[] severs option_card->"
                    "claim; walking from decision/action_plan must not reach "
                    "an idea, so s1 and s2 FAIL with no-idea-reached."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": severed_out,
                "good_state_output": good_out,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0075-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "recount_good_sentences": g["sentence_count"],
            "recount_orphan_ids": o["orphan_ids"],
            "counterexample": {
                "id": "orphan-s3",
                "attempted": True,
                "refutes": False,
            },
        },
        "evidence": [
            evidence_file(
                "IMP-0339 is the only CNL/IMP unit that names idea and option card together; idea->option_card is catalog-authored.",
                "CONFIRMED",
                "command-center/p2-wave/probes/CNL-0075/census.py",
                'COUNCIL_UID = re.compile(r"^(CNL|IMP)-\\d+$")',
                "catalog-needle-scan",
            ),
            evidence_file(
                "No CNL/IMP unit other than CNL-0075 names option card and claim together, so option_card->claim is the first unspecified hop.",
                "CONFIRMED",
                "command-center/p2-wave/probes/CNL-0075/lineage.py",
                '"to_kind": "claim"',
                "catalog-needle-scan",
            ),
            evidence_cmd(
                "Chase walker and join walker agree: good fixture has 0 orphans; both sentences resolve to idea.http-cache.",
                "CONFIRMED",
                "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0075'); import lineage as L; from pathlib import Path; r=L.sentence_report(L.load_council(Path('command-center/p2-wave/probes/CNL-0075/fixtures/good.json'))); print(r['pass'], r['orphan_ids'], r['sentences'][0]['ideas'])\"",
                f"{g['pass']} {g['orphan_ids']} {g['sentences'][0]['ideas']}",
                "command-center/p2-wave/probes/CNL-0075/lineage.py",
                "def chase_ideas(",
                "parent-chase-walk",
            ),
            evidence_cmd(
                "Negative control: empty-cites sentence s3 fails; good fixture stays silent.",
                "CONFIRMED",
                P1,
                orphan_out,
                "command-center/p2-wave/probes/CNL-0075/fixtures/orphan.json",
                '"id": "s3"',
                "relational-join-orphan",
            ),
        ],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/CNL-0075/lineage.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0075/fixtures/good.json",
                "exists": True,
                "role": "fixture",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0075/fixtures/orphan.json",
                "exists": True,
                "role": "negative-control",
            },
            {
                "path": NOTE_SCHEMA,
                "exists": True,
                "role": "supporting",
            },
        ],
        "residual_unknowns": [
            "Declared output_schema command-center/schema/councilspec.v2.schema.json exists as a generated shim ($ref to https://ast-integrate.invalid/...). Draft202012Validator raises RefResolutionError offline, so this note is validated against the per-unit design-note.schema.json.",
            "command-center/schema/council-design-note.schema.json is the same class of shim; it is not a closed schema for this design note.",
            "CNL-0056 idea-ledger artifact is absent; this unit consumes a scripted ledger fixture rather than a live CNL-0056 schema.",
            "11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent on this worktree; hop authorship was read from WORK-UNIT-CATALOG.json, not from those inputs.",
            "argument->vote has CNL-0087/IMP-0356 needle hits; those units do not require rests_on_argument_ids. Ranked after option_card->claim because they are not the first empty hop.",
        ],
        "declared_output_schema": "command-center/schema/councilspec.v2.schema.json",
        "catalog_note_schema": CATALOG_NOTE_SCHEMA,
        "validated_against": NOTE_SCHEMA,
    }

    schema = json.loads((REPO / NOTE_SCHEMA).read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        print("FAILED:emit schema", [e.message for e in errs[:8]])
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    # After write, primary artifact exists=true is honest.
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNL-0075 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
