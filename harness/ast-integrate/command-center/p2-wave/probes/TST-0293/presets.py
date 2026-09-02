"""64 editable CouncilSpec presets for TST-0293.

Named ids (spec :11200-11225) are the 26 family members drawn from
CNL-0103..CNL-0116. Remaining seats bind unused P01-P58 protocols
(CNL-0038..CNL-0046) so the floor is 64, not 26.

Distinctness key: (protocol_id, roles, voting.rule, stopping.expression).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

REQUIRED_OUTPUTS = (
    "transcript",
    "idea_catalog",
    "argument_graph",
    "evidence_map",
    "vote_history",
    "confidence_evolution",
    "dissent",
    "unresolved_questions",
    "action_plan",
)

# Keep in lockstep with the first column of NAMED_ROWS (spec :11200-11225).
NAMED_AT_11200_11225 = (
    "100-idea-brainstorm",
    "innovation-moonshot",
    "design-plan-critique",
    "release-go-no-go",
    "anonymous-peer-review",
    "code-review-tribunal",
    "security-red-blue",
    "incident-war-room",
    "retrospective-postmortem",
    "strategy-council",
    "constrained-prioritisation",
    "requirements-elicitation",
    "conflict-reconciliation",
    "ethics-review",
    "legal-review",
    "risk-committee",
    "forecasting-proper-scoring",
    "expert-elicitation",
    "evidence-adjudication-jury",
    "benchmark-results-jury",
    "negotiation",
    "mediation",
    "adversarial-collaboration",
    "lay-panel",
    "standing-watch",
    "general-purpose-auto-composed",
)

PROTOCOLS: dict[str, tuple[str, str]] = {
    "P01": ("free-form-moderated-panel", "DELIBERATIVE"),
    "P02": ("round-robin", "DELIBERATIVE"),
    "P03": ("fishbowl", "DELIBERATIVE"),
    "P04": ("consensus-conference", "DELIBERATIVE"),
    "P05": ("rotating-chair", "DELIBERATIVE"),
    "P06": ("nominal-group-technique", "DELIBERATIVE"),
    "P07": ("oxford-debate", "ADVERSARIAL"),
    "P08": ("red-blue-team", "ADVERSARIAL"),
    "P09": ("dialectical-inquiry", "ADVERSARIAL"),
    "P10": ("mandated-devils-advocate", "ADVERSARIAL"),
    "P11": ("team-b-competitive-estimate", "ADVERSARIAL"),
    "P12": ("adversarial-collaboration", "ADVERSARIAL"),
    "P13": ("hostile-cross-examination", "ADVERSARIAL"),
    "P14": ("judge-and-jury", "JUDICIAL"),
    "P15": ("claim-by-claim-adjudication", "JUDICIAL"),
    "P16": ("grand-jury-threshold", "JUDICIAL"),
    "P17": ("jury-with-allowed-hung", "JUDICIAL"),
    "P18": ("two-key-dual-control", "JUDICIAL"),
    "P19": ("rfc-last-call", "JUDICIAL"),
    "P20": ("delphi-anonymous-rounds", "ANONYMOUS"),
    "P21": ("wideband-delphi-estimation", "ANONYMOUS"),
    "P22": ("brainwriting-635", "ANONYMOUS"),
    "P23": ("silent-start-pooling", "ANONYMOUS"),
    "P24": ("surprisingly-popular-bts", "ANONYMOUS"),
    "P25": ("blind-reevaluation", "ANONYMOUS"),
    "P26": ("brainstorming-swarm", "GENERATIVE"),
    "P27": ("design-charrette", "GENERATIVE"),
    "P28": ("morphological-analysis", "GENERATIVE"),
    "P29": ("triz-contradiction", "GENERATIVE"),
    "P30": ("six-hats-rotation", "GENERATIVE"),
    "P31": ("constraint-relaxation", "GENERATIVE"),
    "P32": ("counterfactual-council", "GENERATIVE"),
    "P33": ("prediction-tournament", "FORECASTING"),
    "P34": ("scenario-planning", "FORECASTING"),
    "P35": ("reference-class-planning-poker", "FORECASTING"),
    "P36": ("calibration-tournament", "FORECASTING"),
    "P37": ("pairwise-comparison", "FORECASTING"),
    "P38": ("analysis-of-competing-hypotheses", "TRADECRAFT"),
    "P39": ("key-assumptions-check", "TRADECRAFT"),
    "P40": ("quality-of-information-check", "TRADECRAFT"),
    "P41": ("deception-detection", "TRADECRAFT"),
    "P42": ("argument-mapping", "TRADECRAFT"),
    "P43": ("premortem", "TRADECRAFT"),
    "P44": ("postmortem-5whys-causal", "TRADECRAFT"),
    "P45": ("scientific-peer-review", "ENGINEERING-REVIEW"),
    "P46": ("architecture-review-board", "ENGINEERING-REVIEW"),
    "P47": ("incident-war-room", "ENGINEERING-REVIEW"),
    "P48": ("kill-the-company", "ENGINEERING-REVIEW"),
    "P49": ("socratic-interrogation", "ENGINEERING-REVIEW"),
    "P50": ("evidence-clerk-led", "ENGINEERING-REVIEW"),
    "P51": ("timeboxed-spike-council", "ENGINEERING-REVIEW"),
    "P52": ("nested-subcouncils-meta-council", "META-COMPOSITION"),
    "P53": ("escalation-ladder", "META-COMPOSITION"),
    "P54": ("cross-vendor-mirrored", "META-COMPOSITION"),
    "P55": ("shadow-council", "META-COMPOSITION"),
    "P56": ("minority-report-mandatory", "META-COMPOSITION"),
    "P57": ("stopping-rule-tournament", "META-COMPOSITION"),
    "P58": ("owner-in-the-loop-stepwise", "META-COMPOSITION"),
}

NAMED_ROWS: list[tuple[Any, ...]] = [
    ("100-idea-brainstorm", "P26", ("facilitator", "generator-a", "generator-b", "synthesizer"), "none-generation-phase", "idea_count >= 8 OR round >= max_rounds", 6, "none", "CNL-0103", "What catalog of distinct ideas does the swarm emit before critique is allowed?"),
    ("innovation-moonshot", "P29", ("inventor", "feasibility-critic", "novelty-scorer", "sponsor"), "novelty-weighted-score", "moonshot_candidates >= 3 OR round >= max_rounds", 5, "none", "CNL-0103", "Which contradiction-breaking options survive a feasibility haircut?"),
    ("design-plan-critique", "P46", ("chair", "architect", "reliability", "security", "scribe"), "rubric-majority", "rubric_complete AND (fail_count == 0 OR round >= max_rounds)", 4, "none", "CNL-0104", "Does the design or plan pass the published rubric without a silent override?"),
    ("release-go-no-go", "P19", ("release-manager", "qa", "sre", "product"), "last-call-silence", "no_blockers_for_ttl OR explicit_no_go", 3, "none", "CNL-0104", "Ship, hold, or roll back given the last-call blocker set?"),
    ("anonymous-peer-review", "P45", ("editor", "reviewer-1", "reviewer-2", "author"), "reviewer-majority-then-rebuttal", "rebuttal_complete OR round >= max_rounds", 5, "until-lift", "CNL-0105", "After bounded author rebuttal, is the manuscript accepted, revised, or rejected?"),
    ("code-review-tribunal", "P50", ("clerk", "reviewer-a", "reviewer-b", "author"), "oracle-overrides-majority", "oracle_settled OR round >= max_rounds", 4, "none", "CNL-0106", "Does the executable oracle override reviewer opinion when they conflict?"),
    ("security-red-blue", "P08", ("white-cell", "red-lead", "blue-lead", "logger"), "asymmetric-win-conditions", "red_objective_met OR blue_hold OR round >= max_rounds", 6, "none", "CNL-0107", "Did red meet an objective, or did blue hold without red merely timing out?"),
    ("incident-war-room", "P47", ("incident-commander", "comms", "sre", "scribe"), "commander-with-dissent-log", "service_restored OR escalate OR round >= max_rounds", 4, "none", "CNL-0108", "What action restores service now, with evidence deferred if needed?"),
    ("retrospective-postmortem", "P44", ("facilitator", "primary", "secondary", "customer-proxy"), "causal-graph-consensus", "root_cause_signed OR round >= max_rounds", 5, "none", "CNL-0108", "What causal chain, not a timeline, explains the incident?"),
    ("strategy-council", "P34", ("strategist", "sceptic", "operator", "finance"), "scenario-weighted-majority", "direction_named OR round >= max_rounds", 5, "none", "CNL-0109", "Which direction under uncertainty, not a ranked backlog?"),
    ("constrained-prioritisation", "P37", ("pm", "eng", "design", "support"), "pairwise-not-ranked-choice", "budget_exhausted OR pair_matrix_complete", 4, "none", "CNL-0109", "Which non-exclusive bundle fits the fixed budget?"),
    ("requirements-elicitation", "P04", ("facilitator", "stakeholder-a", "stakeholder-b", "analyst"), "capture-no-vote", "elicitation_quota_met OR round >= max_rounds", 4, "none", "CNL-0110", "What do stakeholders want, recorded before any reconciliation?"),
    ("conflict-reconciliation", "P09", ("moderator", "thesis", "antithesis", "integrator"), "unreconciled-pair-as-outcome", "conflicts_classified OR round >= max_rounds", 5, "none", "CNL-0110", "Which requirement pairs reconcile, and which stay unreconcilable?"),
    ("ethics-review", "P49", ("chair", "ethicist", "affected-proxy", "counsel-observer"), "may-we-unanimity-or-dissent", "may_we_decided OR round >= max_rounds", 4, "none", "CNL-0111", "May we do this, independent of residual risk?"),
    ("legal-review", "P18", ("counsel-a", "counsel-b", "business", "recorder"), "two-key-must-both-turn", "both_keys OR either_blocks", 3, "none", "CNL-0111", "Do both legal keys turn, or is the action blocked?"),
    ("risk-committee", "P43", ("cro", "ops-risk", "tech-risk", "audit"), "exposure-band-majority", "band_assigned OR round >= max_rounds", 4, "none", "CNL-0111", "How exposed are we, even if legal already said no?"),
    ("forecasting-proper-scoring", "P33", ("forecaster-a", "forecaster-b", "resolver", "scorer"), "brier-proper-score", "forecasts_logged AND resolution_dated OR unresolvable_parked", 4, "none", "CNL-0112", "What Brier-scored forecasts are dated, and which are parked unresolvable?"),
    ("expert-elicitation", "P21", ("elicitor", "expert-1", "expert-2", "expert-3"), "median-then-spread", "round2_complete OR round >= max_rounds", 4, "until-lift", "CNL-0112", "What is the anonymised distribution after the second Delphi round?"),
    ("evidence-adjudication-jury", "P15", ("judge", "juror-1", "juror-2", "juror-3", "clerk"), "claim-by-claim-majority", "all_claims_ruled OR hung_on_named_claim", 5, "none", "CNL-0113", "For each claim, admitted or out, without the judge becoming the decider?"),
    ("benchmark-results-jury", "P17", ("foreperson", "juror-a", "juror-b", "methodologist", "sponsor-recused"), "hung-allowed-majority", "benchmark_accepted OR hung OR gamed", 4, "none", "CNL-0113", "Is the interested-party number admissible, gamed, or hung?"),
    ("negotiation", "P31", ("party-a", "party-b", "recorder"), "bargain-until-zone-or-impasse", "agreement OR impasse OR round >= max_rounds", 5, "none", "CNL-0114", "Do the parties reach a zone of agreement, or is impasse recorded?"),
    ("mediation", "P05", ("mediator", "party-a", "party-b", "scribe"), "mediator-reframe-no-vote", "interests_reframed OR walk_away", 4, "none", "CNL-0114", "What interest-reframe does the mediator produce that neither party wrote?"),
    ("adversarial-collaboration", "P12", ("collaborator-a", "collaborator-b", "registrar"), "shared-preregistered-test", "test_registered OR split_verdict_forbidden", 4, "none", "CNL-0114", "What shared pre-registered test did the adversaries agree, not a split verdict?"),
    ("lay-panel", "P03", ("steward", "expert-presenter", "lay-1", "lay-2", "lay-3"), "lay-majority-expert-silent", "lay_verdict OR round >= max_rounds", 3, "none", "CNL-0114", "What do the lay members decide after the expert presents, without being steered?"),
    ("standing-watch", "P53", ("watch-lead", "oncall", "historian"), "trigger-then-escalate", "trigger_handled OR already_settled_skip", 3, "none", "CNL-0115", "Does this wake relitigate a settled question, or apply the stored ruling?"),
    ("general-purpose-auto-composed", "P52", ("composer", "explainer", "owner-override", "critic"), "composer-explains-every-dial", "explanation_complete AND override_path_named", 4, "none", "CNL-0116", "For an unnamed request, which dials were chosen and what is the one-step override?"),
]

EXTRA_VOTE_STOP: list[tuple[str, str, int]] = [
    ("majority", "majority OR round >= max_rounds", 4),
    ("supermajority-2-3", "supermajority OR round >= max_rounds", 5),
    ("unanimity-or-record-dissent", "unanimity OR dissent_logged", 4),
    ("borda", "ranking_complete OR round >= max_rounds", 3),
    ("approval", "approval_quota OR round >= max_rounds", 4),
    ("condorcet-with-minimax-fallback", "condorcet_winner OR minimax", 5),
    ("chair-tiebreak", "majority OR chair_breaks", 3),
    ("weighted-expertise", "weighted_median OR round >= max_rounds", 4),
    ("score-0-5", "mean_score_stable OR round >= max_rounds", 4),
    ("veto-any-one", "no_veto AND quorum OR veto_named", 3),
]

FAMILY_ROLES = {
    "DELIBERATIVE": ("chair", "member-a", "member-b", "scribe"),
    "ADVERSARIAL": ("attacker", "defender", "umpire", "scribe"),
    "JUDICIAL": ("judge", "juror-a", "juror-b", "clerk"),
    "ANONYMOUS": ("elicitor", "peer-a", "peer-b", "peer-c"),
    "GENERATIVE": ("generator", "critic", "curator", "scribe"),
    "FORECASTING": ("forecaster-a", "forecaster-b", "resolver", "scorer"),
    "TRADECRAFT": ("analyst", "challenger", "auditor", "scribe"),
    "ENGINEERING-REVIEW": ("reviewer-a", "reviewer-b", "author", "oracle-steward"),
    "META-COMPOSITION": ("parent-chair", "child-delegate", "fan-in", "owner"),
}


def distinctness_key(spec: dict[str, Any]) -> tuple:
    return (
        spec["protocol_binding"]["protocol_id"],
        spec["protocol_binding"]["protocol_name"],
        tuple(spec["roles"]),
        spec["voting"]["rule"],
        spec["stopping"]["expression"],
    )


def _spec(
    pid: str,
    protocol_id: str,
    roles: tuple[str, ...],
    vote_rule: str,
    stop_expr: str,
    max_rounds: int,
    anonymity: str,
    family: str,
    question: str,
    named: bool,
) -> dict[str, Any]:
    proto_name, fam = PROTOCOLS[protocol_id]
    n_roles = len(roles)
    return {
        "id": pid,
        "name": pid.replace("-", " "),
        "status": "editable",
        "editable": True,
        "base_spec_ref": "CouncilSpec/v2",
        "default_binding": "auto-compose" if pid == "general-purpose-auto-composed" else "static",
        "editable_dials": ["budgets.max_rounds", "voting.rule", "stopping.expression"],
        "charter": {
            "purpose": f"Editable preset {pid} bound to {proto_name}.",
            "question": question,
        },
        "participants": {
            "min": max(2, n_roles - 1),
            "max": n_roles + 2,
            "selection": "scripted-cast",
        },
        "roles": list(roles),
        "protocol_binding": {
            "protocol_id": protocol_id,
            "protocol_name": proto_name,
            "family": fam,
        },
        "engagement": {"anonymity": anonymity, "partition": "shared-unless-protocol"},
        "budgets": {"max_rounds": max_rounds, "wall_clock_ms": 4000},
        "evidence": {
            "standard": "citation-or-oracle",
            "oracle": "executable-test" if pid == "code-review-tribunal" else None,
        },
        "anti_failure": {
            "on_split": "surface-disagreement",
            "no_silent_average": True,
            "fast_unanimity_tripwire": fam == "ADVERSARIAL",
        },
        "audit": {
            "persist_transcript": True,
            "hash_inputs": True,
            "replay": True,
        },
        "voting": {"rule": vote_rule, "quorum": max(2, n_roles - 1)},
        "consensus": {
            "reducer": "shared-completion-predicate",
            "local_completion_forbidden": True,
        },
        "stopping": {
            "max_rounds": max_rounds,
            "expression": stop_expr,
            "on_timeout": "FAILED",
        },
        "outcomes": list(REQUIRED_OUTPUTS),
        "integrity": {"seeded": True, "scripted_personas": True},
        "execution": {
            "substrate": "deterministic-scripted-simulator",
            "live_model_arm": "owner-gated",
        },
        "meta": {
            "named_at_11200_11225": named,
            "family": family,
        },
    }


def all_presets() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    fingerprints: set[tuple] = set()
    used_protocols: set[str] = set()

    for row in NAMED_ROWS:
        spec = _spec(*row, True)
        fp = distinctness_key(spec)
        if fp in fingerprints:
            raise RuntimeError(f"named collision {spec['id']}")
        fingerprints.add(fp)
        used_protocols.add(spec["protocol_binding"]["protocol_id"])
        specs.append(spec)

    unused = [pid for pid in PROTOCOLS if pid not in used_protocols]
    extras_needed = 64 - len(specs)
    for extra_i in range(extras_needed):
        proto = unused[extra_i % len(unused)]
        variant = 0 if extra_i < len(unused) else 1 + (extra_i - len(unused))
        vote_rule, stop_expr, mx = EXTRA_VOTE_STOP[extra_i % len(EXTRA_VOTE_STOP)]
        fam = PROTOCOLS[proto][1]
        roles = FAMILY_ROLES[fam]
        if variant:
            vote_rule = f"{vote_rule}-alt{variant}"
            stop_expr = f"({stop_expr}) AND variant=={variant}"
            roles = tuple(f"{r}-v{variant}" for r in roles)
        proto_name = PROTOCOLS[proto][0]
        pid = f"protocol-{proto_name}" if not variant else f"protocol-{proto_name}-alt{variant}"
        anonymity = "until-lift" if fam == "ANONYMOUS" else "none"
        spec = _spec(
            pid,
            proto,
            roles,
            vote_rule,
            stop_expr,
            mx,
            anonymity,
            f"protocol-{proto}",
            f"What terminal artifact does protocol {proto_name} emit under a scripted cast?",
            False,
        )
        fp = distinctness_key(spec)
        if fp in fingerprints:
            spec["voting"]["rule"] = f"{spec['voting']['rule']}-{proto}"
            spec["stopping"]["expression"] = (
                f"{spec['stopping']['expression']} AND proto=={proto}"
            )
            fp = distinctness_key(spec)
        if fp in fingerprints:
            raise RuntimeError(f"extra collision {pid}")
        fingerprints.add(fp)
        specs.append(spec)

    if len(specs) != 64:
        raise RuntimeError(f"expected 64 presets, got {len(specs)}")
    ids = [s["id"] for s in specs]
    if len(set(ids)) != 64:
        raise RuntimeError("duplicate preset ids")
    missing = set(NAMED_AT_11200_11225) - set(ids)
    if missing:
        raise RuntimeError(f"named missing {sorted(missing)}")
    return specs


def timeout_fixture() -> dict[str, Any]:
    spec = deepcopy(all_presets()[0])
    spec["id"] = "NEG-never-stop"
    spec["name"] = "negative control never stop"
    spec["meta"]["named_at_11200_11225"] = False
    spec["stopping"]["expression"] = "NEVER"
    spec["stopping"]["max_rounds"] = 10_000
    spec["budgets"]["max_rounds"] = 10_000
    spec["voting"]["rule"] = "vacuous-never-quorum"
    return spec


def schema_invalid_fixture() -> dict[str, Any]:
    spec = deepcopy(all_presets()[0])
    spec.pop("stopping")
    spec["id"] = "NEG-missing-stopping"
    return spec
