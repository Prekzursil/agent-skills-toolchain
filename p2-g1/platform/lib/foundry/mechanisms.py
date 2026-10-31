"""Mechanism decomposition, semantic diff and duplicate collapse (Foundry steps 2-4, spec :10846-10848).

Two derivations, never laundered into each other
------------------------------------------------
``STRUCTURAL`` - the capability was measured by walking the DSL document. This is the only kind
of finding that may support a certification decision.

``DECLARED`` - the capability was inferred from a registry row's prose (``task_fit``, ``stages``,
``roles``, ``stop_rules``, declared mechanism strings). Useful for SEARCH ranking; never
sufficient for a certification decision. Every profile carries the derivation per capability so
a reader can tell which is which, and :func:`MechanismProfile.structural_only` exists precisely
so the forge can refuse to reason about prose.

Hazard detectors
----------------
Each of the 16 hazards in :data:`foundry.model.HAZARDS` gets one pure predicate over the DSL
document. A detector that cannot fire on a known-broken document measures nothing, so every one
is control-tested in both states by ``test_foundry.py`` and by
``_probe_foundry_bothstates.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from foundry.model import Candidate, HAZARD_IDS, capabilities

# Reuse, do not reimplement. ``iter_stages`` is the DSL validator's own depth-first stage walker
# (wfdsl/semantics.py:214) - sharing it means a hazard detector and DSL-SEM-001..014 can never
# disagree about what "a stage" is. ``topology`` is the blueprint round-trip primitive
# (workflows/mechanisms.py:407) and is what makes the forge decomposition falsifiable.
from wfdsl.semantics import iter_stages
from workflows.mechanisms import topology

STRUCTURAL = "structural"
DECLARED = "declared"
ABSENT = "absent"

__all__ = [
    "ABSENT",
    "DECLARED",
    "HAZARD_DETECTORS",
    "MechanismProfile",
    "STRUCTURAL",
    "collapse_duplicates",
    "declared_capabilities",
    "hazard_coverage",
    "iter_stages",
    "profile",
    "semantic_diff",
    "stage_mechanism_map",
    "structural_capabilities",
    "topology",
]


# --------------------------------------------------------------- DSL walking helpers


def _kinds(doc: Mapping[str, Any]) -> set[str]:
    return {str(st.get("kind")) for _, st in iter_stages(doc)}


def _work_units(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        st["work_unit"]
        for _, st in iter_stages(doc)
        if isinstance(st.get("work_unit"), Mapping)
    ]


def _gate_specs(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    out = [g for g in (doc.get("gates") or {}).values() if isinstance(g, Mapping)]
    out += [
        st["gate"] for _, st in iter_stages(doc) if isinstance(st.get("gate"), Mapping)
    ]
    return out


def _text_corpus(doc: Mapping[str, Any]) -> str:
    """Every free-text field a hazard detector is allowed to read, joined once.

    Deliberately narrow: stage titles, gate expressions, stopping-rule expressions, and the
    work-unit prose fields. NOT the workflow ``description`` - a description is marketing copy
    and letting a hazard be "covered" by a sentence in the blurb is how a decorative gate passes.
    """
    parts: list[str] = []
    for _, st in iter_stages(doc):
        parts.append(str(st.get("title", "")))
        wu = st.get("work_unit")
        if isinstance(wu, Mapping):
            for key in (
                "question_or_target",
                "evidence_requirement",
                "completion_definition",
                "title",
            ):
                v = wu.get(key)
                if isinstance(v, str):
                    parts.append(v)
    for g in _gate_specs(doc):
        v = g.get("expression")
        if isinstance(v, str):
            parts.append(v)
    for r in doc.get("stopping_rules") or []:
        if isinstance(r, Mapping) and isinstance(r.get("expression"), str):
            parts.append(r["expression"])
    return "\n".join(parts).lower()


# ------------------------------------------------------- structural capability probes

CapProbe = Callable[[Mapping[str, Any]], bool]

_CAPABILITY_PROBES: dict[str, CapProbe] = {
    "stages": lambda d: bool(d.get("stages")),
    "roles": lambda d: bool(d.get("roles")),
    "gates": lambda d: bool(_gate_specs(d)),
    "tools": lambda d: bool(d.get("tool_policy")),
    "typed_params": lambda d: bool(d.get("params")),
    "subworkflows": lambda d: bool(d.get("subworkflows")) or "subworkflow" in _kinds(d),
    "dynamic_fanout": lambda d: "fanout" in _kinds(d),
    "barriers": lambda d: "barrier" in _kinds(d),
    "loops_with_convergence": lambda d: any(
        st.get("kind") == "loop" and isinstance(st.get("convergence"), Mapping)
        for _, st in iter_stages(d)
    ),
    "human_checkpoints": lambda d: "human_checkpoint" in _kinds(d),
    "retries": lambda d: (
        bool(d.get("retry_policy"))
        or any(isinstance(st.get("retry"), Mapping) for _, st in iter_stages(d))
    ),
    "repair_loops": lambda d: "repair_loop" in _kinds(d),
    "resume": lambda d: bool((d.get("resume") or {}).get("enabled")),
    "deterministic_replay": lambda d: bool(
        (d.get("replay") or {}).get("deterministic")
    ),
    "artifact_caching": lambda d: (
        bool((d.get("cache") or {}).get("enabled"))
        or any(
            bool((st.get("cache") or {}).get("enabled"))
            for _, st in iter_stages(d)
            if isinstance(st.get("cache"), Mapping)
        )
    ),
    "dry_run": lambda d: bool((d.get("dry_run") or {}).get("supported")),
    "cost_estimate": lambda d: (
        bool(d.get("estimate"))
        or any(isinstance(st.get("estimate"), Mapping) for _, st in iter_stages(d))
    ),
    "model_routing": lambda d: (
        bool(d.get("model_routing"))
        or any(isinstance(st.get("model"), Mapping) for _, st in iter_stages(d))
    ),
    "failure_policy": lambda d: (
        bool(d.get("failure_policy"))
        or any(isinstance(st.get("on_failure"), Mapping) for _, st in iter_stages(d))
    ),
    "export_import": lambda d: bool(
        (d.get("portability") or {}).get("export")
        and (d.get("portability") or {}).get("import")
    ),
    "work_unit_binding": lambda d: any(
        ("work_unit" in st or "work_unit_ref" in st) for _, st in iter_stages(d)
    ),
    "stopping_rules": lambda d: bool(d.get("stopping_rules")),
    "source_policy": lambda d: bool((d.get("tool_policy") or {}).get("source_policy")),
    "lineage": lambda d: bool((d.get("lineage") or {}).get("derived_from")),
}


def structural_capabilities(doc: Mapping[str, Any]) -> dict[str, bool]:
    """Which of the 24 capability-map ids this DSL document actually exercises."""
    missing = set(capabilities()) - set(_CAPABILITY_PROBES)
    if missing:  # pragma: no cover - guards against a capability-map edit with no probe
        raise AssertionError(
            f"capability-map ids with no structural probe: {sorted(missing)}"
        )
    return {cap: bool(_CAPABILITY_PROBES[cap](doc)) for cap in capabilities()}


#: lexical evidence for a registry row that has no DSL document. Each capability lists the
#: tokens that count as a DECLARATION of it. Kept short and specific: a token that matches
#: everything (``stage``, ``run``) would make every candidate look fully capable.
_DECLARED_TOKENS: dict[str, tuple[str, ...]] = {
    "stages": ("stage", "phase", "pipeline"),
    "roles": ("role", "persona", "reviewer", "agent"),
    "gates": ("gate", "predicate", "quality gate", "acceptance"),
    "tools": ("tool", "permission", "least privilege", "allowlist"),
    "typed_params": ("typed param", "parameter", "schema-typed", "typed input"),
    "subworkflows": ("subworkflow", "sub-workflow", "nested workflow"),
    "dynamic_fanout": ("fan-out", "fanout", "parallel", "fan out"),
    "barriers": ("barrier", "fan-in", "fanin", "join"),
    "loops_with_convergence": ("loop", "converge", "iterate", "refine loop", "round"),
    "human_checkpoints": (
        "human checkpoint",
        "owner approval",
        "ask the user",
        "approval",
    ),
    "retries": ("retry", "two-strikes", "attempt"),
    "repair_loops": ("repair loop", "fix loop", "repair"),
    "resume": ("resume", "checkpoint", "resumable"),
    "deterministic_replay": ("replay", "deterministic", "seed"),
    "artifact_caching": ("cache", "cached", "ttl"),
    "dry_run": ("dry-run", "dry run", "plan-only", "shadow mode"),
    "cost_estimate": ("estimate", "cost", "budget", "token budget"),
    "model_routing": (
        "model routing",
        "opus",
        "sonnet",
        "cross-vendor",
        "codex",
        "model pinning",
    ),
    "failure_policy": (
        "failure",
        "terminal state",
        "fail-fast",
        "quarantine",
        "degrade",
    ),
    "export_import": ("export", "import", "bundle", "portable"),
    "work_unit_binding": ("work unit", "work-unit", "unit id"),
    "stopping_rules": (
        "stop rule",
        "stopping rule",
        "stop condition",
        "stopping condition",
    ),
    "source_policy": ("license", "provenance", "source policy", "domain allowlist"),
    "lineage": ("lineage", "credit", "rollback", "derived from"),
}


def declared_capabilities(text: str) -> dict[str, bool]:
    low = (text or "").lower()
    return {
        cap: any(tok in low for tok in _DECLARED_TOKENS.get(cap, ()))
        for cap in capabilities()
    }


# ------------------------------------------------------------------ hazard detectors

_TWO_SIGNAL = re.compile(
    r"(two[- ]signal|two independent|second independent|mechanically independent|corroborat|and-gate)"
)
_BOTH_STATES = re.compile(
    r"(both[- ]states|known[- ]broken|negative control|control probe|fires on a known|mutation)"
)


def _all_retries_bounded(doc: Mapping[str, Any]) -> tuple[bool, bool]:
    """``(any_retry_declared, all_declared_retries_are_bounded)``."""
    policies: list[Mapping[str, Any]] = []
    if isinstance(doc.get("retry_policy"), Mapping):
        policies.append(doc["retry_policy"])
    for _, st in iter_stages(doc):
        if isinstance(st.get("retry"), Mapping):
            policies.append(st["retry"])
    if not policies:
        return False, True
    ok = True
    for p in policies:
        strategy = str(p.get("strategy", ""))
        if strategy == "none":
            continue
        if not isinstance(p.get("max_attempts"), int):
            ok = False
        if strategy == "two-strikes-then-pivot" and not isinstance(
            p.get("pivot"), Mapping
        ):
            ok = False
    return True, ok


def _tool_tokens(doc: Mapping[str, Any]) -> list[str]:
    toks: list[str] = []
    for rspec in (doc.get("roles") or {}).values():
        if isinstance(rspec, Mapping):
            toks += [str(t) for t in rspec.get("tool_permissions", []) or []]
    for _, st in iter_stages(doc):
        toks += [str(t) for t in st.get("tool_permissions", []) or []]
    return toks


def _h_straggler(d: Mapping[str, Any]) -> bool:
    barriers = [
        st.get("barrier")
        for _, st in iter_stages(d)
        if st.get("kind") == "barrier" and isinstance(st.get("barrier"), Mapping)
    ]
    if not barriers:
        return False
    return all(
        str(b.get("on_partial"))
        in {"fail", "proceed-degraded", "proceed-with-quarantine"}
        for b in barriers
    )


def _h_unbounded_retry(d: Mapping[str, Any]) -> bool:
    declared, bounded = _all_retries_bounded(d)
    return declared and bounded


def _h_unbounded_loop(d: Mapping[str, Any]) -> bool:
    bounds: list[bool] = []
    for _, st in iter_stages(d):
        if st.get("kind") == "loop":
            conv = st.get("convergence")
            bounds.append(
                isinstance(conv, Mapping)
                and isinstance(conv.get("max_iterations"), int)
            )
        if st.get("kind") == "repair_loop":
            bounds.append(isinstance(st.get("max_attempts"), int))
    if bounds:
        return all(bounds)
    return bool(re.search(r"max_(rounds|iterations|attempts)", _text_corpus(d)))


def _h_silent_failure(d: Mapping[str, Any]) -> bool:
    fp = d.get("failure_policy") or {}
    return bool(fp.get("terminal_state_required")) or bool(fp.get("never_silent"))


def _h_single_signal(d: Mapping[str, Any]) -> bool:
    roles = [r for r in (d.get("roles") or {}).values() if isinstance(r, Mapping)]
    independent = sum(
        1 for r in roles if str(r.get("independence", "independent")) == "independent"
    )
    if independent >= 2:
        return True
    if any(r.get("cross_vendor_required") for r in roles):
        return True
    return bool(_TWO_SIGNAL.search(_text_corpus(d)))


def _h_both_states(d: Mapping[str, Any]) -> bool:
    return bool(_BOTH_STATES.search(_text_corpus(d)))


def _h_secret_export(d: Mapping[str, Any]) -> bool:
    export = (d.get("portability") or {}).get("export") or {}
    return export.get("redact_secrets") is True


def _h_untrusted_fetched(d: Mapping[str, Any]) -> bool:
    sp = (d.get("tool_policy") or {}).get("source_policy") or {}
    return sp.get("treat_fetched_content_as_data") is True


def _h_stale_checkpoint(d: Mapping[str, Any]) -> bool:
    r = d.get("resume") or {}
    return (
        bool(r.get("enabled"))
        and bool(r.get("stale_checkpoint_seconds"))
        and bool(r.get("on_stale"))
    )


def _h_tool_escalation(d: Mapping[str, Any]) -> bool:
    policy = d.get("tool_policy") or {}
    if str(policy.get("default", "deny")) != "deny":
        return False
    allow = set(policy.get("allow", []) or [])
    deny = set(policy.get("deny", []) or [])
    if not allow:
        return False
    toks = _tool_tokens(d)
    if not toks:
        return False
    return all(t in allow and t not in deny for t in toks)


def _h_irreversible_no_human(d: Mapping[str, Any]) -> bool:
    hcs = [st for _, st in iter_stages(d) if st.get("kind") == "human_checkpoint"]
    if not hcs:
        return False
    return all(str(st.get("on_timeout")) in {"fail", "escalate"} for st in hcs)


def _h_no_rollback(d: Mapping[str, Any]) -> bool:
    return bool((d.get("lineage") or {}).get("rollback_to"))


def _h_unverifiable_claim(d: Mapping[str, Any]) -> bool:
    gates = _gate_specs(d)
    if not gates:
        return False
    if any(g.get("evidence_required") is False for g in gates):
        return False
    wus = _work_units(d)
    if wus and not all(str(w.get("evidence_requirement", "")).strip() for w in wus):
        return False
    return True


def _h_total_loss_on_freeze(d: Mapping[str, Any]) -> bool:
    any_checkpoint = any(st.get("checkpoint") is True for _, st in iter_stages(d))
    return any_checkpoint and bool((d.get("resume") or {}).get("enabled"))


def _h_cost_blowout(d: Mapping[str, Any]) -> bool:
    if not d.get("estimate"):
        return False
    for _, st in iter_stages(d):
        if st.get("kind") == "fanout" and not isinstance(
            st.get("max_concurrency"), int
        ):
            return False
    return True


def _h_nondeterministic_replay(d: Mapping[str, Any]) -> bool:
    rp = d.get("replay") or {}
    if rp.get("deterministic") is not True:
        return False
    forbidden = {str(x) for x in rp.get("forbid_nondeterministic_sources", []) or []}
    return {"clock", "random"} <= forbidden


HAZARD_DETECTORS: dict[str, Callable[[Mapping[str, Any]], bool]] = {
    "straggler-work-silently-dropped": _h_straggler,
    "unbounded-retry-grind": _h_unbounded_retry,
    "unbounded-loop": _h_unbounded_loop,
    "silent-failure": _h_silent_failure,
    "single-signal-verdict": _h_single_signal,
    "detector-silent-in-both-states": _h_both_states,
    "secret-value-in-export": _h_secret_export,
    "untrusted-fetched-content-executed": _h_untrusted_fetched,
    "stale-checkpoint-resumed": _h_stale_checkpoint,
    "tool-privilege-escalation": _h_tool_escalation,
    "irreversible-action-without-human": _h_irreversible_no_human,
    "no-rollback-path": _h_no_rollback,
    "unverifiable-claim": _h_unverifiable_claim,
    "total-loss-on-freeze": _h_total_loss_on_freeze,
    "cost-blowout": _h_cost_blowout,
    "non-deterministic-replay": _h_nondeterministic_replay,
}

assert set(HAZARD_DETECTORS) == set(HAZARD_IDS), (
    "every hazard needs exactly one detector; "
    f"missing={sorted(set(HAZARD_IDS) - set(HAZARD_DETECTORS))} "
    f"extra={sorted(set(HAZARD_DETECTORS) - set(HAZARD_IDS))}"
)


def hazard_coverage(doc: Mapping[str, Any]) -> dict[str, bool]:
    return {h: bool(HAZARD_DETECTORS[h](doc)) for h in HAZARD_IDS}


# --------------------------------------------------------------------- the profile


@dataclass
class MechanismProfile:
    candidate_id: str
    derivation: str  # STRUCTURAL for a DSL doc, DECLARED for a prose row
    capabilities: dict[str, bool] = field(default_factory=dict)
    hazards: dict[str, bool] = field(default_factory=dict)
    #: stage id -> the capability ids that stage contributes. Only for STRUCTURAL profiles;
    #: this is what makes a fusion decomposable back to its source mechanisms.
    stage_mechanisms: dict[str, list[str]] = field(default_factory=dict)

    @property
    def provided(self) -> set[str]:
        return {k for k, v in self.capabilities.items() if v}

    @property
    def covered_hazards(self) -> set[str]:
        return {k for k, v in self.hazards.items() if v}

    @property
    def structural_only(self) -> bool:
        return self.derivation == STRUCTURAL

    def to_json(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "derivation": self.derivation,
            "capabilities_provided": sorted(self.provided),
            "capabilities_absent": sorted(set(self.capabilities) - self.provided),
            "hazards_covered": sorted(self.covered_hazards),
            "hazards_uncovered": sorted(set(self.hazards) - self.covered_hazards),
            "stage_mechanisms": {
                k: sorted(v) for k, v in sorted(self.stage_mechanisms.items())
            },
        }


#: which capability each stage KIND contributes, so a fused workflow can be walked back to the
#: source that donated each stage.
_KIND_TO_CAPABILITY: dict[str, tuple[str, ...]] = {
    "task": ("stages", "work_unit_binding"),
    "gate": ("gates",),
    "fanout": ("dynamic_fanout",),
    "barrier": ("barriers",),
    "loop": ("loops_with_convergence",),
    "repair_loop": ("repair_loops",),
    "human_checkpoint": ("human_checkpoints",),
    "subworkflow": ("subworkflows",),
    "council": ("roles",),
}


def stage_mechanism_map(doc: Mapping[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for _, st in iter_stages(doc):
        sid = str(st.get("id"))
        caps = list(_KIND_TO_CAPABILITY.get(str(st.get("kind")), ("stages",)))
        if isinstance(st.get("retry"), Mapping):
            caps.append("retries")
        if isinstance(st.get("estimate"), Mapping):
            caps.append("cost_estimate")
        if isinstance(st.get("model"), Mapping):
            caps.append("model_routing")
        if st.get("produces"):
            caps.append("work_unit_binding")
        out[sid] = sorted(set(caps))
    return out


def profile(cand: Candidate) -> MechanismProfile:
    """Decompose one candidate into the canonical mechanism namespace."""
    if cand.dsl_doc is not None:
        doc = cand.dsl_doc
        return MechanismProfile(
            candidate_id=cand.id,
            derivation=STRUCTURAL,
            capabilities=structural_capabilities(doc),
            hazards=hazard_coverage(doc),
            stage_mechanisms=stage_mechanism_map(doc),
        )
    return MechanismProfile(
        candidate_id=cand.id,
        derivation=DECLARED,
        capabilities=declared_capabilities(cand.searchable_text),
        hazards={h: False for h in HAZARD_IDS},
    )


# ---------------------------------------------------------- semantic diff / dedupe


def semantic_diff(a: MechanismProfile, b: MechanismProfile) -> dict[str, Any]:
    """Mechanism-level diff. Exact set algebra - no judgement anywhere in here."""
    pa, pb = a.provided, b.provided
    ha, hb = a.covered_hazards, b.covered_hazards
    union = pa | pb
    jaccard = len(pa & pb) / len(union) if union else 1.0
    return {
        "a": a.candidate_id,
        "b": b.candidate_id,
        "shared_capabilities": sorted(pa & pb),
        "only_a": sorted(pa - pb),
        "only_b": sorted(pb - pa),
        "capability_jaccard": round(jaccard, 4),
        "hazards_shared": sorted(ha & hb),
        "hazards_only_a": sorted(ha - hb),
        "hazards_only_b": sorted(hb - ha),
        "complementary": bool((pa - pb) and (pb - pa)) or bool((ha - hb) and (hb - ha)),
    }


def collapse_duplicates(
    profiles: Iterable[MechanismProfile], threshold: float = 1.0
) -> dict[str, Any]:
    """Group profiles whose mechanism sets are identical (``threshold=1.0``) or near-identical.

    ``threshold`` is a Jaccard floor on the capability sets. At 1.0 this is exact duplicate
    collapse; below 1.0 it is a near-duplicate cluster and the caller must treat the cluster as
    a candidate for MERGE, not as a proven duplicate.
    """
    plist = list(profiles)
    groups: list[list[str]] = []
    assigned: set[str] = set()
    for i, p in enumerate(plist):
        if p.candidate_id in assigned:
            continue
        group = [p.candidate_id]
        assigned.add(p.candidate_id)
        for q in plist[i + 1 :]:
            if q.candidate_id in assigned:
                continue
            union = p.provided | q.provided
            j = len(p.provided & q.provided) / len(union) if union else 1.0
            if j >= threshold:
                group.append(q.candidate_id)
                assigned.add(q.candidate_id)
        groups.append(group)
    return {
        "threshold": threshold,
        "input_count": len(plist),
        "group_count": len(groups),
        "collapsed": sum(len(g) - 1 for g in groups),
        "groups_with_duplicates": [g for g in groups if len(g) > 1],
    }
