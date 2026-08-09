"""Cross-field semantic rules for CouncilSpec.

JSON Schema pins shapes, enums and single-field conditionals. It cannot express
"min <= max", "every referenced participant_id exists", "the source_expression string
means the same thing as the structured tree", or "a delegation map has no cycles".
Those live here as numbered rules so a failure names the rule that caught it.

Severity: ERROR fails conformance; WARN is reported and does not fail.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Set

from .expression import ExpressionError, iter_leaves, parse, referenced_metrics

BRAINSTORM_STAGES = {"brainstorm", "nominal_group", "six_hats"}


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str  # "ERROR" | "WARN"
    message: str
    path: str = "$"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"[{self.severity}] {self.rule} at {self.path}: {self.message}"


def _roster_ids(spec: Mapping[str, Any]) -> List[str]:
    roster = spec.get("participants", {}).get("roster") or []
    return [p.get("participant_id") for p in roster if isinstance(p, Mapping)]


def _stage_kinds(spec: Mapping[str, Any]) -> Set[str]:
    seq = spec.get("protocol", {}).get("sequence") or []
    return {s.get("kind") for s in seq if isinstance(s, Mapping)}


def _all_stop_expressions(spec: Mapping[str, Any]):
    top = spec.get("stopping", {}).get("expression")
    if isinstance(top, Mapping):
        yield "$.stopping.expression", top
    for idx, stage in enumerate(spec.get("protocol", {}).get("sequence") or []):
        if isinstance(stage, Mapping) and isinstance(stage.get("exit_when"), Mapping):
            yield f"$.protocol.sequence[{idx}].exit_when", stage["exit_when"]


# --------------------------------------------------------------------------- rules


def _sem001_source_expression_matches(spec, out):
    stopping = spec.get("stopping") or {}
    src = stopping.get("source_expression")
    tree = stopping.get("expression")
    if not src or not isinstance(tree, Mapping):
        return
    try:
        parsed = parse(src)
    except ExpressionError as exc:
        out.append(
            Finding(
                "SEM-001",
                "ERROR",
                f"source_expression does not parse: {exc}",
                "$.stopping.source_expression",
            )
        )
        return
    if parsed != tree:
        out.append(
            Finding(
                "SEM-001",
                "ERROR",
                "source_expression parses to a DIFFERENT tree than stopping.expression; "
                f"parsed={parsed!r}",
                "$.stopping.source_expression",
            )
        )


def _sem002_count_coherence(spec, out):
    count = spec.get("participants", {}).get("count") or {}
    lo, hi, exact = count.get("min"), count.get("max"), count.get("exact_n")
    if lo is not None and hi is not None and lo > hi:
        out.append(
            Finding(
                "SEM-002",
                "ERROR",
                f"count.min ({lo}) > count.max ({hi})",
                "$.participants.count",
            )
        )
    if exact is not None and lo is not None and exact < lo:
        out.append(
            Finding(
                "SEM-002",
                "ERROR",
                f"count.exact_n ({exact}) < count.min ({lo})",
                "$.participants.count",
            )
        )
    if exact is not None and hi is not None and exact > hi:
        out.append(
            Finding(
                "SEM-002",
                "ERROR",
                f"count.exact_n ({exact}) > count.max ({hi})",
                "$.participants.count",
            )
        )


def _sem003_unique_participant_ids(spec, out):
    ids = _roster_ids(spec)
    seen, dupes = set(), set()
    for pid in ids:
        if pid in seen:
            dupes.add(pid)
        seen.add(pid)
    if dupes:
        out.append(
            Finding(
                "SEM-003",
                "ERROR",
                f"duplicate participant_id: {sorted(dupes)}",
                "$.participants.roster",
            )
        )


def _sem004_exact_selection_needs_roster(spec, out):
    participants = spec.get("participants") or {}
    mode = (participants.get("selection") or {}).get("mode")
    count = participants.get("count") or {}
    roster = participants.get("roster")
    if mode == "exact" and not roster:
        out.append(
            Finding(
                "SEM-004",
                "ERROR",
                "selection.mode == exact requires a non-empty roster",
                "$.participants.roster",
            )
        )
        return
    if (
        mode == "exact"
        and count.get("mode") == "exact"
        and count.get("exact_n") is not None
    ):
        if len(roster) != count["exact_n"]:
            out.append(
                Finding(
                    "SEM-004",
                    "ERROR",
                    f"roster has {len(roster)} participants but count.exact_n is "
                    f"{count['exact_n']}",
                    "$.participants.roster",
                )
            )
    if mode == "automatic" and roster:
        out.append(
            Finding(
                "SEM-004",
                "WARN",
                "selection.mode == automatic but a roster is pinned; the roster will "
                "be treated as seed participants",
                "$.participants.roster",
            )
        )


def _sem005_weights(spec, out):
    voting = spec.get("voting") or {}
    weights = voting.get("weights") or {}
    ids = set(_roster_ids(spec))
    if voting.get("method") == "weighted":
        if not any(float(w) > 0 for w in weights.values()):
            out.append(
                Finding(
                    "SEM-005",
                    "ERROR",
                    "voting.method == weighted requires at least one positive weight",
                    "$.voting.weights",
                )
            )
    if ids and weights:
        unknown = sorted(set(weights) - ids)
        if unknown:
            out.append(
                Finding(
                    "SEM-005",
                    "ERROR",
                    f"voting.weights references unknown participant_id: {unknown}",
                    "$.voting.weights",
                )
            )


def _collect_id_refs(spec: Mapping[str, Any]):
    topology = spec.get("topology") or {}
    if topology.get("chair"):
        yield "$.topology.chair", [topology["chair"]]
    for i, c in enumerate(topology.get("committees") or []):
        yield f"$.topology.committees[{i}].members", c.get("members") or []
    for i, c in enumerate(topology.get("caucuses") or []):
        yield f"$.topology.caucuses[{i}].members", c.get("members") or []
    voting = spec.get("voting") or {}
    veto = voting.get("veto") or {}
    if veto.get("holders"):
        yield "$.voting.veto.holders", veto["holders"]
    deleg = (voting.get("delegation") or {}).get("map") or {}
    if deleg:
        yield "$.voting.delegation.map", list(deleg.keys()) + list(deleg.values())
    part = spec.get("participants") or {}
    for i, p in enumerate(
        (part.get("information_partition") or {}).get("partitions") or []
    ):
        yield (
            f"$.participants.information_partition.partitions[{i}].visible_to",
            p.get("visible_to") or [],
        )
    for i, s in enumerate((spec.get("protocol") or {}).get("sequence") or []):
        if isinstance(s, Mapping) and s.get("participants"):
            yield f"$.protocol.sequence[{i}].participants", s["participants"]


def _sem006_id_references(spec, out):
    ids = set(_roster_ids(spec))
    if not ids:
        return  # nothing to check against; auto-selected councils have no roster yet
    for path, refs in _collect_id_refs(spec):
        unknown = sorted({r for r in refs if r not in ids})
        if unknown:
            out.append(
                Finding(
                    "SEM-006",
                    "ERROR",
                    f"references unknown participant_id: {unknown}",
                    path,
                )
            )


def _sem007_idea_targets(spec, out):
    for path, tree in _all_stop_expressions(spec):
        leaves = [
            lf
            for lf in iter_leaves(tree)
            if lf["metric"] in ("unique_ideas", "deduplicated_ideas", "novel_ideas")
        ]
        if not leaves:
            continue
        if not (_stage_kinds(spec) & BRAINSTORM_STAGES):
            out.append(
                Finding(
                    "SEM-007",
                    "ERROR",
                    f"{path} gates on an idea-count metric but protocol.sequence has no "
                    f"idea-generating stage (one of {sorted(BRAINSTORM_STAGES)})",
                    path,
                )
            )
        target = (spec.get("targets") or {}).get("unique_ideas")
        wanted = max(
            (lf["value"] for lf in leaves if lf["op"] in (">=", ">")), default=None
        )
        if wanted is not None:
            if target is None:
                out.append(
                    Finding(
                        "SEM-007",
                        "ERROR",
                        f"{path} requires an idea count of {wanted} but "
                        "targets.unique_ideas is unset",
                        "$.targets",
                    )
                )
            elif target < wanted:
                out.append(
                    Finding(
                        "SEM-007",
                        "ERROR",
                        f"targets.unique_ideas ({target}) is below the stopping "
                        f"threshold ({wanted})",
                        "$.targets.unique_ideas",
                    )
                )


def _sem008_delegation_cycles(spec, out):
    deleg = (spec.get("voting") or {}).get("delegation") or {}
    mapping = deleg.get("map") or {}
    if not mapping:
        return
    for start in mapping:
        seen, node, hops = {start}, mapping[start], 1
        while node in mapping:
            if node in seen:
                out.append(
                    Finding(
                        "SEM-008",
                        "ERROR",
                        f"delegation cycle reachable from {start!r} (revisits {node!r})",
                        "$.voting.delegation.map",
                    )
                )
                break
            seen.add(node)
            node = mapping[node]
            hops += 1
        maxlen = deleg.get("max_chain_length")
        if maxlen is not None and hops > maxlen:
            out.append(
                Finding(
                    "SEM-008",
                    "ERROR",
                    f"delegation chain from {start!r} is {hops} hops, exceeding "
                    f"max_chain_length {maxlen}",
                    "$.voting.delegation.map",
                )
            )


def _sem009_outcomes_cover_stopping(spec, out):
    outcomes = set((spec.get("outcomes") or {}).get("allowed") or [])
    if not outcomes:
        return
    needed: Dict[str, str] = {
        "proof_of_impossibility": "proof_of_impossibility",
    }
    refs: Set[str] = set()
    for _, tree in _all_stop_expressions(spec):
        refs |= referenced_metrics(tree)
    for metric, outcome in needed.items():
        if metric in refs and outcome not in outcomes:
            out.append(
                Finding(
                    "SEM-009",
                    "ERROR",
                    f"stopping rule can terminate on {metric} but outcomes.allowed does not "
                    f"include {outcome!r}",
                    "$.outcomes.allowed",
                )
            )
    if (spec.get("consensus") or {}).get(
        "minority_report"
    ) == "required" and "minority_report" not in outcomes:
        out.append(
            Finding(
                "SEM-009",
                "ERROR",
                "consensus.minority_report is 'required' but outcomes.allowed omits "
                "'minority_report'",
                "$.outcomes.allowed",
            )
        )


def _sem010_council_of_councils(spec, out):
    topology = spec.get("topology") or {}
    if topology.get("kind") == "council_of_councils":
        if not (topology.get("fan_in") or {}).get("reducer"):
            out.append(
                Finding(
                    "SEM-010",
                    "ERROR",
                    "council_of_councils requires topology.fan_in.reducer",
                    "$.topology.fan_in",
                )
            )


def _sem011_round_cap_coherence(spec, out):
    caps = (spec.get("stopping") or {}).get("hard_caps") or {}
    rounds = (spec.get("protocol") or {}).get("rounds") or {}
    cap, rmin, rmax = caps.get("max_rounds"), rounds.get("min"), rounds.get("max")
    if cap is not None and rmin is not None and cap < rmin:
        out.append(
            Finding(
                "SEM-011",
                "ERROR",
                f"hard_caps.max_rounds ({cap}) is below protocol.rounds.min ({rmin})",
                "$.stopping.hard_caps.max_rounds",
            )
        )
    declared = [
        lf["value"]
        for _, tree in _all_stop_expressions(spec)
        for lf in iter_leaves(tree)
        if lf["metric"] == "max_rounds"
    ]
    for value in declared:
        if cap is None and rmax is None:
            out.append(
                Finding(
                    "SEM-011",
                    "ERROR",
                    f"stopping rule fires at max_rounds == {value} but neither "
                    "protocol.rounds.max nor stopping.hard_caps.max_rounds declares it",
                    "$.stopping",
                )
            )
        elif value not in (cap, rmax):
            out.append(
                Finding(
                    "SEM-011",
                    "ERROR",
                    f"stopping rule fires at max_rounds == {value} but the configured "
                    f"caps are rounds.max={rmax} / hard_caps.max_rounds={cap}",
                    "$.stopping",
                )
            )


def _sem012_custom_metric_producer(spec, out):
    for path, tree in _all_stop_expressions(spec):
        for leaf in iter_leaves(tree):
            if leaf["metric"].startswith("custom:") and not leaf.get("producer"):
                out.append(
                    Finding(
                        "SEM-012",
                        "WARN",
                        f"custom metric {leaf['metric']!r} declares no producer, so "
                        "nothing in the run is guaranteed to compute it",
                        path,
                    )
                )


_RULES = [
    _sem001_source_expression_matches,
    _sem002_count_coherence,
    _sem003_unique_participant_ids,
    _sem004_exact_selection_needs_roster,
    _sem005_weights,
    _sem006_id_references,
    _sem007_idea_targets,
    _sem008_delegation_cycles,
    _sem009_outcomes_cover_stopping,
    _sem010_council_of_councils,
    _sem011_round_cap_coherence,
    _sem012_custom_metric_producer,
]

RULE_IDS = tuple(sorted({f"SEM-{i:03d}" for i in range(1, len(_RULES) + 1)}))


def check(spec: Mapping[str, Any], recurse: bool = True) -> List[Finding]:
    """Run every semantic rule. Recurses into topology.subcouncils."""
    out: List[Finding] = []
    for rule in _RULES:
        try:
            rule(spec, out)
        except Exception as exc:  # a rule crash must not be silent
            out.append(Finding(rule.__name__, "ERROR", f"rule crashed: {exc!r}"))
    if recurse:
        for idx, sub in enumerate(
            (spec.get("topology") or {}).get("subcouncils") or []
        ):
            for finding in check(sub, recurse=True):
                out.append(
                    Finding(
                        finding.rule,
                        finding.severity,
                        finding.message,
                        f"$.topology.subcouncils[{idx}]" + finding.path.lstrip("$"),
                    )
                )
    return out


def errors(findings: Sequence[Finding]) -> List[Finding]:
    return [f for f in findings if f.severity == "ERROR"]
