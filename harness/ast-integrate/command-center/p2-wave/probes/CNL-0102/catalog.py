"""Reconstructed 58-protocol / 72-preset corpus for CNL-0102.

The original library file 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is ABSENT
on this worktree (same measurement as ARC-0003/ARC-0010). Protocol ids and
slugs are transcribed from WORK-UNIT-CATALOG.json CNL-0038..CNL-0046
questions, which name P01-P58 so no member can fall through a family
mis-assignment. Preset cardinality 72 is the catalog-cited present count.
Named family presets C01-C25 are grounded in CNL-0103..CNL-0116 titles.
C26-C70 fill the remaining present-count slots with unique 4-tuples.
C71 and C72 are deliberate name-only clones (mechanism duplicates).

This is a catalog-cited reconstruction, not a byte copy of the missing
library. The metric's blind spot is disclosed on the design note.
"""
from __future__ import annotations

from copy import deepcopy

# (id, family, slug) — 6+7+6+6+7+5+7+7+7 = 58
PROTOCOLS: list[tuple[str, str, str]] = [
    ("P01", "DELIBERATIVE", "free-form-moderated-panel"),
    ("P02", "DELIBERATIVE", "round-robin"),
    ("P03", "DELIBERATIVE", "fishbowl"),
    ("P04", "DELIBERATIVE", "consensus-conference"),
    ("P05", "DELIBERATIVE", "rotating-chair"),
    ("P06", "DELIBERATIVE", "nominal-group-technique"),
    ("P07", "ADVERSARIAL", "oxford-debate"),
    ("P08", "ADVERSARIAL", "red-blue-team"),
    ("P09", "ADVERSARIAL", "dialectical-inquiry"),
    ("P10", "ADVERSARIAL", "mandated-devils-advocate"),
    ("P11", "ADVERSARIAL", "team-b-competitive-estimate"),
    ("P12", "ADVERSARIAL", "adversarial-collaboration"),
    ("P13", "ADVERSARIAL", "hostile-cross-examination"),
    ("P14", "JUDICIAL", "judge-and-jury"),
    ("P15", "JUDICIAL", "claim-by-claim-adjudication"),
    ("P16", "JUDICIAL", "grand-jury-threshold"),
    ("P17", "JUDICIAL", "jury-with-allowed-hung"),
    ("P18", "JUDICIAL", "two-key-dual-control"),
    ("P19", "JUDICIAL", "rfc-last-call"),
    ("P20", "ANONYMOUS", "delphi-anonymous-rounds"),
    ("P21", "ANONYMOUS", "wideband-delphi-estimation"),
    ("P22", "ANONYMOUS", "brainwriting-635"),
    ("P23", "ANONYMOUS", "silent-start-pooling"),
    ("P24", "ANONYMOUS", "surprisingly-popular-bts"),
    ("P25", "ANONYMOUS", "blind-reevaluation"),
    ("P26", "GENERATIVE", "brainstorming-swarm"),
    ("P27", "GENERATIVE", "design-charrette"),
    ("P28", "GENERATIVE", "morphological-analysis"),
    ("P29", "GENERATIVE", "triz-contradiction"),
    ("P30", "GENERATIVE", "six-hats-rotation"),
    ("P31", "GENERATIVE", "constraint-relaxation"),
    ("P32", "GENERATIVE", "counterfactual-council"),
    ("P33", "FORECASTING", "prediction-tournament"),
    ("P34", "FORECASTING", "scenario-planning"),
    ("P35", "FORECASTING", "reference-class-planning-poker"),
    ("P36", "FORECASTING", "calibration-tournament"),
    ("P37", "FORECASTING", "pairwise-comparison"),
    ("P38", "TRADECRAFT", "analysis-of-competing-hypotheses"),
    ("P39", "TRADECRAFT", "key-assumptions-check"),
    ("P40", "TRADECRAFT", "quality-of-information-check"),
    ("P41", "TRADECRAFT", "deception-detection"),
    ("P42", "TRADECRAFT", "argument-mapping"),
    ("P43", "TRADECRAFT", "premortem"),
    ("P44", "TRADECRAFT", "postmortem-5whys-causal"),
    ("P45", "ENGINEERING-REVIEW", "scientific-peer-review"),
    ("P46", "ENGINEERING-REVIEW", "architecture-review-board"),
    ("P47", "ENGINEERING-REVIEW", "incident-war-room"),
    ("P48", "ENGINEERING-REVIEW", "kill-the-company"),
    ("P49", "ENGINEERING-REVIEW", "socratic-interrogation"),
    ("P50", "ENGINEERING-REVIEW", "evidence-clerk-led"),
    ("P51", "ENGINEERING-REVIEW", "timeboxed-spike-council"),
    ("P52", "META-COMPOSITION", "nested-subcouncils-meta-council"),
    ("P53", "META-COMPOSITION", "escalation-ladder"),
    ("P54", "META-COMPOSITION", "cross-vendor-mirrored"),
    ("P55", "META-COMPOSITION", "shadow-council"),
    ("P56", "META-COMPOSITION", "minority-report-mandatory"),
    ("P57", "META-COMPOSITION", "stopping-rule-tournament"),
    ("P58", "META-COMPOSITION", "owner-in-the-loop-stepwise"),
]

VOTES = (
    "majority",
    "supermajority",
    "unanimity",
    "consent",
    "ranked-choice",
    "approval",
    "score",
    "condorcet",
    "weighted",
    "log-pool",
)

ROLE_POOL = (
    "Architect",
    "Skeptic",
    "Pragmatist",
    "Critic",
    "Chair",
    "Judge",
    "Juror",
    "Proposer",
    "Synthesizer",
    "Red",
    "Blue",
    "Clerk",
    "Owner",
    "Mediator",
    "Forecaster",
    "Reviewer",
    "Author",
    "Advocate",
)


def _p(*ids: str) -> list[str]:
    return list(ids)


def _preset(
    pid: str,
    name: str,
    protocols: list[str],
    roles: list[str],
    vote: str,
    stop: str,
    basis: str,
    clone_of: str | None = None,
) -> dict:
    return {
        "id": pid,
        "name": name,
        "bound_protocols": list(protocols),
        "roles": list(roles),
        "voting_method": vote,
        "stopping_expression": stop,
        "reconstruction_basis": basis,
        "clone_of": clone_of,
        "base_spec": "CouncilSpec/v2",
        "default_binding": {
            "protocols": list(protocols),
            "roles": list(roles),
            "voting_method": vote,
            "stopping_expression": stop,
        },
        "editable_dials": ["roles", "budgets.max_rounds"],
    }


def named_family_presets() -> list[dict]:
    """C01-C25: CNL-0103..CNL-0116 family members, distinct 4-tuples."""
    return [
        _preset(
            "C01",
            "brainstorm-100-idea",
            _p("P26", "P22", "P06"),
            ["Proposer", "Skeptic", "Synthesizer", "Chair"],
            "approval",
            "unique_ideas >= 100 AND completeness_score >= 0.90",
            "CNL-0103 brainstorm arm",
        ),
        _preset(
            "C02",
            "innovation-moonshot",
            _p("P26", "P32", "P31"),
            ["Proposer", "Advocate", "Skeptic", "Owner"],
            "score",
            "unique_ideas >= 40 AND novelty_share >= 0.60 AND max_rounds == 14",
            "CNL-0103 moonshot arm (novelty vs feasibility via stop, not name)",
        ),
        _preset(
            "C03",
            "design-critique-board",
            _p("P46", "P45", "P49"),
            ["Reviewer", "Architect", "Critic", "Chair"],
            "majority",
            "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
            "CNL-0104 design/plan critique",
        ),
        _preset(
            "C04",
            "plan-critique-board",
            _p("P46", "P39", "P42"),
            ["Reviewer", "Pragmatist", "Skeptic", "Chair"],
            "supermajority",
            "key_assumptions_checked == true AND max_rounds == 8",
            "CNL-0104 plan critique (rubric/evidence differ from C03)",
        ),
        _preset(
            "C05",
            "release-go-no-go",
            _p("P18", "P19", "P46"),
            ["Owner", "Reviewer", "Judge", "Clerk"],
            "unanimity",
            "two_key_consent == true OR rfc_last_call_elapsed",
            "CNL-0104 release go-no-go",
        ),
        _preset(
            "C06",
            "anonymous-peer-review",
            _p("P20", "P45", "P25"),
            ["Reviewer", "Author", "Clerk", "Chair"],
            "majority",
            "rebuttal_rounds >= 1 AND anonymity_lifted == false OR max_rounds == 6",
            "CNL-0105",
        ),
        _preset(
            "C07",
            "code-review-tribunal",
            _p("P45", "P50", "P51"),
            ["Reviewer", "Judge", "Clerk", "Architect"],
            "condorcet",
            "oracle_failing_tests == 0 OR oracle_itself_disputed == true",
            "CNL-0106 executable oracle",
        ),
        _preset(
            "C08",
            "security-red-blue",
            _p("P08", "P48", "P41"),
            ["Red", "Blue", "Judge", "Clerk"],
            "weighted",
            "red_findings_open == 0 AND red_budget_remaining > 0",
            "CNL-0107",
        ),
        _preset(
            "C09",
            "live-war-room",
            _p("P47", "P43", "P53"),
            ["Chair", "Architect", "Skeptic", "Owner"],
            "consent",
            "mitigation_in_place == true OR time_minutes >= 45",
            "CNL-0108 live war room (may skip min-deliberation floor)",
        ),
        _preset(
            "C10",
            "retrospective-postmortem",
            _p("P44", "P38", "P39"),
            ["Clerk", "Skeptic", "Pragmatist", "Chair"],
            "majority",
            "causal_chain_complete == true AND no_new_factor_rounds >= 2",
            "CNL-0108 retrospective",
        ),
        _preset(
            "C11",
            "strategy-direction",
            _p("P34", "P01", "P04"),
            ["Owner", "Architect", "Skeptic", "Forecaster"],
            "ranked-choice",
            "scenario_coverage >= 3 AND consensus >= 0.80",
            "CNL-0109 direction-setting",
        ),
        _preset(
            "C12",
            "constrained-prioritisation",
            _p("P37", "P35", "P06"),
            ["Pragmatist", "Owner", "Critic", "Chair"],
            "approval",
            "budget_exhausted == false AND ranked_nonexclusive == true",
            "CNL-0109 ranking under a fixed budget (ranked-choice is a trap)",
        ),
        _preset(
            "C13",
            "requirements-elicitation",
            _p("P23", "P01", "P22"),
            ["Proposer", "Mediator", "Skeptic", "Clerk"],
            "approval",
            "stakeholder_coverage >= 0.90 AND max_rounds == 5",
            "CNL-0110 elicitation arm",
        ),
        _preset(
            "C14",
            "requirements-conflict-reconciliation",
            _p("P12", "P09", "P56"),
            ["Mediator", "Advocate", "Skeptic", "Owner"],
            "consent",
            "unreconciled_pairs == 0 OR outcome == irreducible_disagreement",
            "CNL-0110 reconciliation arm",
        ),
        _preset(
            "C15",
            "ethics-legal-review",
            _p("P14", "P19", "P56"),
            ["Judge", "Reviewer", "Skeptic", "Clerk"],
            "unanimity",
            "may_we == true OR minority_report_filed == true",
            "CNL-0111 ethics/legal",
        ),
        _preset(
            "C16",
            "risk-committee",
            _p("P39", "P40", "P43"),
            ["Forecaster", "Skeptic", "Owner", "Chair"],
            "supermajority",
            "exposure_accepted == true AND residual_risk_named == true",
            "CNL-0111 risk committee",
        ),
        _preset(
            "C17",
            "forecasting-proper-score",
            _p("P33", "P36", "P35"),
            ["Forecaster", "Skeptic", "Clerk", "Chair"],
            "log-pool",
            "brier_or_log_score_applied == true AND unresolvable_forecasts_parked == true",
            "CNL-0112",
        ),
        _preset(
            "C18",
            "evidence-adjudication-jury",
            _p("P15", "P17", "P50"),
            ["Juror", "Judge", "Clerk", "Advocate"],
            "majority",
            "hung_allowed == true AND claims_adjudicated == total_claims",
            "CNL-0113 evidence jury",
        ),
        _preset(
            "C19",
            "benchmark-results-jury",
            _p("P15", "P36", "P51"),
            ["Juror", "Skeptic", "Clerk", "Judge"],
            "supermajority",
            "interested_party_number_replicated == true OR result_parked",
            "CNL-0113 benchmark jury",
        ),
        _preset(
            "C20",
            "negotiation",
            _p("P12", "P01", "P04"),
            ["Advocate", "Advocate", "Mediator", "Owner"],
            "consent",
            "bargain_closed == true OR impasse == true",
            "CNL-0114 negotiation (parties bargain directly)",
        ),
        _preset(
            "C21",
            "mediation",
            _p("P12", "P05", "P23"),
            ["Mediator", "Advocate", "Advocate", "Clerk"],
            "consent",
            "interests_reframed == true AND no_direct_bargain_required",
            "CNL-0114 mediation",
        ),
        _preset(
            "C22",
            "adversarial-collaboration",
            _p("P12", "P56", "P42"),
            ["Red", "Blue", "Clerk", "Judge"],
            "unanimity",
            "shared_preregistered_test_exists == true",
            "CNL-0114 adversarial collaboration",
        ),
        _preset(
            "C23",
            "lay-panel",
            _p("P17", "P23", "P01"),
            ["Juror", "Juror", "Juror", "Chair"],
            "majority",
            "expert_steering_flags == 0 AND hung_allowed == true",
            "CNL-0114 lay panel",
        ),
        _preset(
            "C24",
            "standing-watch",
            _p("P55", "P53", "P58"),
            ["Chair", "Skeptic", "Clerk", "Owner"],
            "consent",
            "wake_trigger_fired == true AND prior_settled_questions_not_relitigated",
            "CNL-0115",
        ),
        _preset(
            "C25",
            "general-purpose-auto-composed",
            _p("P52", "P13", "P57"),
            ["Chair", "Architect", "Skeptic", "Pragmatist", "Critic"],
            "ranked-choice",
            "owner_override_unused == true AND every_dial_explained == true",
            "CNL-0116 flagship",
        ),
    ]


def filler_presets() -> list[dict]:
    """C26-C70: remaining present-count slots, unique stopping expressions."""
    out = []
    for i in range(45):
        n = 26 + i
        proto = PROTOCOLS[i][0]  # P01..P45, unique singletons
        vote = VOTES[i % len(VOTES)]
        r0 = ROLE_POOL[i % len(ROLE_POOL)]
        r1 = ROLE_POOL[(i + 3) % len(ROLE_POOL)]
        r2 = ROLE_POOL[(i + 7) % len(ROLE_POOL)]
        out.append(
            _preset(
                f"C{n:02d}",
                f"reconstruction-slot-{n:02d}-{PROTOCOLS[i][2]}",
                _p(proto),
                [r0, r1, r2],
                vote,
                f"slot_index == {n} AND max_rounds == {4 + (i % 9)} AND unique_ideas >= {12 + i}",
                "catalog-cited cardinality filler; unique 4-tuple (not a library byte copy)",
            )
        )
    return out


def clone_presets(base: list[dict]) -> list[dict]:
    by_id = {p["id"]: p for p in base}
    c72 = deepcopy(by_id["C01"])
    c72["id"] = "C72"
    c72["name"] = "brainstorm-100-idea-renamed"
    c72["clone_of"] = "C01"
    c72["reconstruction_basis"] = (
        "deliberate name-only clone of C01; same protocol/role/vote/stop"
    )
    c71 = deepcopy(by_id["C25"])
    c71["id"] = "C71"
    c71["name"] = "flagship-auto-composed-alias"
    c71["clone_of"] = "C25"
    c71["reconstruction_basis"] = (
        "deliberate name-only clone of C25; same protocol/role/vote/stop"
    )
    return [c71, c72]


def protocol_records() -> list[dict]:
    return [
        {"id": pid, "family": family, "slug": slug}
        for pid, family, slug in PROTOCOLS
    ]


def preset_records() -> list[dict]:
    named = named_family_presets()
    fillers = filler_presets()
    clones = clone_presets(named)
    rows = named + fillers + clones
    rows.sort(key=lambda p: p["id"])
    if len(rows) != 72:
        raise RuntimeError(f"expected 72 presets, got {len(rows)}")
    ids = [p["id"] for p in rows]
    if ids != [f"C{i:02d}" for i in range(1, 73)]:
        raise RuntimeError(f"preset ids not C01..C72: {ids[:5]}..{ids[-5:]}")
    return rows


def load_corpus() -> dict:
    protocols = protocol_records()
    presets = preset_records()
    pids = {p["id"] for p in protocols}
    cids = {p["id"] for p in presets}
    return {
        "source": "catalog-cited-reconstruction",
        "original_library": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "original_library_present": False,
        "protocol_count": len(protocols),
        "preset_count": len(presets),
        "id_spaces_disjoint": pids.isdisjoint(cids),
        "protocols": protocols,
        "presets": presets,
    }
