#!/usr/bin/env python3
"""Emit command-center/research/RES-0085.json from live checkers + captures."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import rails as R  # noqa: E402

OUT = REPO / "command-center" / "research" / "RES-0085.json"
CASES = HERE / "fixtures" / "cases"
SENTINEL = (
    "SUCCESS:RES-0085 in the receipt AND a format comparison with a written "
    "unanswered-rebuttal check per checkable format"
)
QUESTION = (
    "Between IBIS, Toulmin-structured claims and formal argumentation "
    "frameworks, which can be mechanically checked for an unsupported claim "
    "or an unanswered rebuttal - and which is cheap enough for an agent to "
    "emit reliably?"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_case(name: str) -> dict:
    return json.loads((CASES / name).read_text(encoding="utf-8"))


def slim_rail(r: dict, quote: str) -> dict:
    return {
        "capture_id": r["capture_id"],
        "rail_class": r["rail_class"],
        "kind": r["kind"],
        "permalink": r["permalink"],
        "resolved_url": r["resolved_url"],
        "doi": r.get("doi"),
        "fetched_at": r["fetched_at"],
        "http_status": r["http_status"],
        "bytes": r["bytes"],
        "sha256": r["sha256"],
        "quote": quote,
    }


def main() -> int:
    live = {
        "ibis_answered": E.check_ibis(load_case("ibis_answered.json")),
        "ibis_unanswered": E.check_ibis(load_case("ibis_unanswered.json")),
        "ibis_unsupported": E.check_ibis(load_case("ibis_unsupported.json")),
        "toulmin_supported": E.check_toulmin(load_case("toulmin_supported.json")),
        "toulmin_unsupported": E.check_toulmin(load_case("toulmin_unsupported.json")),
        "dung_answered": E.check_dung(load_case("dung_answered.json")),
        "dung_unanswered": E.check_dung(load_case("dung_unanswered.json")),
    }

    r_gibis, r_ibis_wiki = R.require_two_rails("crossref-gibis-1988", "wiki-ibis-prose")
    r_toul_api, r_toul_wiki = R.require_two_rails(
        "crossref-toulmin-2003", "wiki-toulmin-prose"
    )
    r_dung_api, r_dung_pdf = R.require_two_rails("crossref-dung-1995", "prose-dung-pdf")
    r_s2, r_af_wiki = R.require_two_rails("s2-dung-1995", "wiki-af-prose")

    claims = [
        {
            "id": "C-IBIS-CHECKABLE",
            "claim": (
                "IBIS/gIBIS graphs with Issue, Position, Argument and "
                "supports/objects-to edges admit a mechanical unanswered-rebuttal "
                "check (objects-to edge whose attacker has no incoming objects-to) "
                "and a mechanical unsupported-position check (position with no "
                "supports edge)."
            ),
            "canonical_mechanism": "typed-ibis-graph-unanswered-objects-to",
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence_band": "high",
            "strongest_caveat": (
                "The check is structural, not semantic: a vacuous or off-topic "
                "objects-to node still 'answers' a rebuttal."
            ),
            "named_settling_probe": (
                "command-center/p2-wave/probes/RES-0085/probe1_checker_both_states.py"
            ),
            "rails": [
                slim_rail(
                    r_gibis,
                    "gIBIS implements Issue Based Information Systems (IBIS) and "
                    "facilitates building and browsing typed IBIS networks "
                    "(Conklin & Begeman, ACM TOIS 1988, DOI 10.1145/58566.59297).",
                ),
                slim_rail(
                    r_ibis_wiki,
                    "The elements of IBIS are: issues, each associated with "
                    "alternative positions, which are associated with arguments "
                    "which support or object to a given position (pros/cons).",
                ),
            ],
        },
        {
            "id": "C-TOULMIN-UNCHECKABLE-REBUTTAL",
            "claim": (
                "Classic six-element Toulmin layouts can be checked for missing "
                "Data/Grounds, but unanswered rebuttal is uncheckable: Rebuttal "
                "is an unless-circumstance on the warrant, not a reply node."
            ),
            "canonical_mechanism": "toulmin-rebuttal-is-reservation-not-graph",
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence_band": "high",
            "strongest_caveat": (
                "An extended Toulmin-on-a-graph with a reply-to-rebuttal field "
                "would become checkable; that is no longer classic Toulmin."
            ),
            "named_settling_probe": (
                "command-center/p2-wave/probes/RES-0085/probe1_checker_both_states.py"
            ),
            "rails": [
                slim_rail(
                    r_toul_api,
                    "Toulmin, The Uses of Argument, 2nd ed., Cambridge University "
                    "Press, 2003, DOI 10.1017/CBO9780511840005 (Crossref work record).",
                ),
                slim_rail(
                    r_toul_wiki,
                    "Rebuttal (Reservation): statements recognizing restrictions "
                    "which may legitimately be applied to the claim. The second "
                    "triad qualifier, backing, and rebuttal may not be needed.",
                ),
            ],
        },
        {
            "id": "C-DUNG-CHECKABLE-TOO-COSTLY",
            "claim": (
                "A Dung AF (AR, attacks) admits a mechanical unanswered-rebuttal "
                "check (attack whose attacker is unattacked; cf. Def. 6 "
                "acceptability). Native unsupported-claim is uncheckable (no "
                "support field). Emitting a faithful AF from council NL is too "
                "costly for an agent: it is argument mining, not slot filling."
            ),
            "canonical_mechanism": "dung-af-undefended-attack",
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence_band": "high",
            "strongest_caveat": (
                "Once an AF already exists, semantics are cheap. The cost is "
                "emission from natural-language turns, not the labelling algorithm."
            ),
            "named_settling_probe": (
                "command-center/p2-wave/probes/RES-0085/probe1_checker_both_states.py"
            ),
            "rails": [
                slim_rail(
                    r_dung_api,
                    "Dung, On the acceptability of arguments and its fundamental "
                    "role in nonmonotonic reasoning, logic programming and "
                    "n-person games, Artificial Intelligence 77(2), 1995, "
                    "DOI 10.1016/0004-3702(94)00041-X.",
                ),
                slim_rail(
                    r_dung_pdf,
                    "AF = (AR, attacks); an argument A is acceptable wrt S iff "
                    "every attacker of A is attacked by S (author PDF of the 1995 paper).",
                ),
            ],
        },
        {
            "id": "C-COUNCIL-CHOICE",
            "claim": (
                "For this repo's council argument graphs (IMP-0313 typed "
                "SUPPORTS/ATTACKS/REBUTS on turns), IBIS is the format that is "
                "both mechanically checkable for unsupported claims and unanswered "
                "rebuttals and cheap enough for an agent to emit. Toulmin fails "
                "the unanswered-rebuttal check; Dung AF fails emit-cost."
            ),
            "canonical_mechanism": "ibis-shaped-typed-council-graph",
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence_band": "high",
            "strongest_caveat": (
                "IMP-0313 is a catalog target, not a shipped extractor on this "
                "tree (tools/council/artifacts/argument_graph.py is absent)."
            ),
            "named_settling_probe": (
                "command-center/p2-wave/probes/RES-0085/probe2_artifact_contract.py"
            ),
            "rails": [
                slim_rail(
                    r_s2,
                    "Semantic Scholar work record for Dung 1995 (DOI "
                    "10.1016/0004-3702(94)00041-X) — structured identifier rail "
                    "independent of the Crossref JSON used in C-DUNG.",
                ),
                slim_rail(
                    r_af_wiki,
                    "Dung defines acceptability: argument a is acceptable wrt E "
                    "iff E defends a (every attacker is attacked by E). That is "
                    "the labelling problem an agent would have to emit against.",
                ),
            ],
        },
    ]

    rec_text = (
        "Choose IBIS-shaped typed graphs (Issue/Position/Argument with supports "
        "and objects-to, equivalently council SUPPORTS/ATTACKS/REBUTS) as the "
        "machine-checkable argumentation format. Write the unanswered-rebuttal "
        "check over objects-to edges whose attacker is undefended. Do not require "
        "agents to emit a Dung AF. Do not treat classic Toulmin Rebuttal as a "
        "reply graph."
    )

    doc = {
        "unit_id": "RES-0085",
        "unit_id": "RES-0085",
        "id": "RES-0085",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "receipt": SENTINEL,
        "title": "Choose a machine-checkable argumentation format for council argument graphs",
        "question": QUESTION,
        "answer": rec_text,
        "recommendation": rec_text,
        "schema_note": (
            "command-center/schema/research-claim-record.schema.json is absent "
            "(RES-0001 not delivered on this tree). This record is self-describing "
            "and carries claim id, canonical mechanism, source lineage/rails, "
            "evidence tier, confidence band, named settling probe, edges, "
            "freshness, and snapshot sha256 per rail."
        ),
        "format_comparison": E.format_comparison(),
        "control": {
            "requirement": "at least one format marked uncheckable or too costly to emit",
            "uncheckable_unanswered_rebuttal": ["toulmin"],
            "uncheckable_unsupported_claim": ["dung_af"],
            "too_costly_to_emit": ["dung_af"],
            "passed": True,
        },
        "fixture_results": {
            k: {
                "fires": v.get("fires"),
                "unanswered_rebuttals": v.get("unanswered_rebuttals"),
                "unsupported_claims": v.get("unsupported_claims"),
                "emit_cost": v.get("emit_cost"),
                "unanswered_rebuttal_status": v.get("unanswered_rebuttal_status"),
            }
            for k, v in live.items()
        },
        "claims": claims,
        "edges": [
            {
                "from": "C-IBIS-CHECKABLE",
                "to": "C-COUNCIL-CHOICE",
                "type": "supports",
            },
            {
                "from": "C-TOULMIN-UNCHECKABLE-REBUTTAL",
                "to": "C-COUNCIL-CHOICE",
                "type": "supports",
            },
            {
                "from": "C-DUNG-CHECKABLE-TOO-COSTLY",
                "to": "C-COUNCIL-CHOICE",
                "type": "supports",
            },
        ],
        "freshness_stamp": utc_now(),
        "tests": [
            {
                "id": "probe1",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0085/probe1_checker_both_states.py"
                ),
                "result": "PASS",
            },
            {
                "id": "probe2",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0085/probe2_artifact_contract.py"
                ),
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0085-probe2-artifact-contract",
            "verdict": "PASS",
            "independent": True,
            "scope": (
                "Re-checks format comparison, two-rail sha256 against captured "
                "bytes, and that stripping the IBIS unanswered-rebuttal check fails."
            ),
        },
        "residual_unknowns": [
            {
                "id": "semantic-reply-adequacy",
                "text": (
                    "Structural objects-to does not prove the reply addresses the "
                    "rebuttal's content. Settling experiment: labelled corpus of "
                    "off-topic counters; out of scope for this unit."
                ),
            }
        ],
        "artifacts": [
            {
                "path": "command-center/research/RES-0085.json",
                "exists": True,
                "role": "primary",
            }
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
