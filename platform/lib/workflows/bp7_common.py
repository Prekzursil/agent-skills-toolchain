"""Shared constructors for the Phase-2B workflow blueprints 73-84 (unit blueprints/bp-7).

WHY A BUILDER AND NOT 12 HAND-WRITTEN FILES
-------------------------------------------
The JSON documents under ``platform/workflows/`` are the deliverable; this module is their
source. Only the *policy* blocks are shared here (export/import portability, the deny-by-default
tool-policy skeleton, the 19-field work-unit constructor). Everything that carries a blueprint's
MECHANISM - params, roles, gates, stage graph, stopping rules, convergence rules - is written out
per blueprint in ``bp7_dat.py`` / ``bp7_ux.py`` / ``bp7_doc.py``, and ``bp7_build.py`` is the
driver. A shared retry policy is not a near-duplicate; a shared stage graph would be, so none is
shared - ``test_bp7_slice.py`` proves it by comparing stage-kind multisets and gate expressions
pairwise across all 66 pairs.

Every constructor here refuses to invent a value the caller must own: there is no default
``output_path``, no default ``output_schema``, and no default ``evidence_requirement``. A blueprint
that forgets one gets a TypeError at build time rather than a plausible-looking wrong artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = REPO_ROOT / "platform" / "workflows"

#: the six category spans the spec requires the 96 built-ins to cover
#: (_USER-PROMPTS.md:10897 - research/evidence; engineering/reliability; security, governance and
#: risk; product, design and strategy; data, science, knowledge and creative; collective
#: intelligence and meta-workflows).
CAT_RESEARCH = "research-and-evidence"
CAT_ENGINEERING = "engineering-and-reliability"
CAT_SECURITY = "security-governance-and-risk"
CAT_PRODUCT = "product-design-and-strategy"
CAT_DATA = "data-science-knowledge-and-creative"
CAT_META = "collective-intelligence-and-meta"

ALL_CATEGORIES = (
    CAT_RESEARCH,
    CAT_ENGINEERING,
    CAT_SECURITY,
    CAT_PRODUCT,
    CAT_DATA,
    CAT_META,
)

#: the program phase these blueprint documents were authored in. The inline work units are RUNTIME
#: task definitions embedded in a blueprint, not entries in command-center/WORK-UNIT-CATALOG.json,
#: so they carry the authoring phase rather than a made-up execution phase.
AUTHORING_PHASE = "2B"

#: Inline-unit id prefixes for this slice: the card FAMILY, so an id says which design it came
#: from. `DAT`, `UX` and `DOC` are all verified absent from the 2,007-unit catalog's 13 measured
#: prefixes (ADV ARC AUD BLD CC CNF CNL IMP REL RES SYN TST WFA), and the embedded card index
#: (73-84) is owned by this unit alone, so an id can collide with neither the catalog nor a
#: sibling slice. test_bp7_slice.py RE-MEASURES both rather than trusting this comment.
UNIT_PREFIXES = ("DAT", "UX", "DOC")


def sch(name: str) -> str:
    """A resolvable ``command-center/schema/<name>.schema.json`` reference.

    Every name passed here is verified to exist on disk by ``bp7_schema_ref_check.py``; the
    substrate unit generated 233 such shims, so a typo is a build-time finding rather than a
    dangling contract discovered at runtime.
    """
    return f"command-center/schema/{name}.schema.json"


def unit_id(prefix: str, card_index: int, stage_ordinal: int) -> str:
    """``DAT-7301`` = card 73 of the library, inline unit 01."""
    if prefix not in UNIT_PREFIXES:
        raise ValueError(f"prefix {prefix!r} is not one of {UNIT_PREFIXES}")
    if not 73 <= card_index <= 84:
        raise ValueError(f"card_index {card_index} is outside this unit's range 73-84")
    if not 1 <= stage_ordinal <= 99:
        raise ValueError(f"stage_ordinal {stage_ordinal} outside the two-digit range")
    return f"{prefix}-{card_index:02d}{stage_ordinal:02d}"


def work_unit(
    *,
    uid: str,
    title: str,
    target: str,
    inputs: Sequence[str],
    dependencies: Sequence[str],
    model: str,
    vendor: str,
    role: str,
    basis: str,
    tools: Sequence[str],
    substrate: str,
    timeout_seconds: int,
    output_path: str,
    output_schema: str,
    evidence: str,
    tests: Sequence[str],
    reviewer: str,
    sentinel_condition: str,
    retry: str,
    failure_classes: Sequence[str],
    owner_approval: bool,
    mechanism: str,
    not_a_duplicate_because: str | None = None,
    spec_anchor: str | None = None,
    notes: str | None = None,
    phase: str = AUTHORING_PHASE,
) -> dict[str, Any]:
    """One work unit under the SAME 19-field contract as the catalog, in the STRICT shape.

    STRICT (platform/schema/work-unit.strict.schema.json) means: the object form of
    ``assigned_model_vendor_role``, ARRAY forms of ``tests_required`` and
    ``failure_classification``, a sentinel opening with ``SUCCESS:<own-id>``, and no undeclared
    property. Authoring against STRICT rather than merely structural keeps this slice out of the
    catalog's measured migration debt (128 slash-triple assignments, 96 prose test strings,
    96 prose failure strings) instead of adding 40-odd new rows to it.
    """
    if not tests:
        raise ValueError(f"{uid}: tests_required must name at least one test")
    if not failure_classes:
        raise ValueError(f"{uid}: failure_classification must name at least one class")
    if len(evidence) < 20:
        raise ValueError(f"{uid}: evidence_requirement is too short to be checkable")
    if len(retry) < 10:
        # work-unit.schema.json sets minLength 10 on retry_policy. A bare "none" fails it, and
        # because draft-2020-12 discards annotations from a failed subschema the failure ALSO
        # cascades into an unevaluatedProperties error at the STAGE level - which reads as an
        # unknown-property finding and sends you looking for a typo that does not exist.
        # Measured: ten bare "none" strings produced 22 errors, 12 of them cascades.
        raise ValueError(f"{uid}: retry_policy must say WHY, not just 'none' (minLength 10)")
    if len(reviewer) < 10:
        raise ValueError(f"{uid}: reviewer_requirement must name a reviewer (minLength 10)")
    unit: dict[str, Any] = {
        "id": uid,
        "title": title,
        "phase": phase,
        "question_or_target": target,
        "inputs": list(inputs),
        "dependencies": list(dependencies),
        "assigned_model_vendor_role": {
            "model": model,
            "vendor": vendor,
            "role": role,
            "basis": basis,
        },
        "tool_permissions": list(tools),
        "execution_substrate": substrate,
        "timeout_seconds": timeout_seconds,
        "output_path": output_path,
        "output_schema": output_schema,
        "evidence_requirement": evidence,
        "tests_required": list(tests),
        "reviewer_requirement": reviewer,
        "completion_sentinel": (
            f"SUCCESS:{uid} emitted only when {sentinel_condition}; "
            f"otherwise FAILED:{uid} <reason>"
        ),
        "retry_policy": retry,
        "failure_classification": list(failure_classes),
        "owner_approval_required": owner_approval,
        "mechanism": mechanism,
    }
    if not_a_duplicate_because:
        unit["not_a_duplicate_because"] = not_a_duplicate_because
    if spec_anchor:
        unit["spec_anchor"] = spec_anchor
    if notes:
        unit["notes"] = notes
    return unit


def artifact(
    path: str,
    schema_ref: str,
    *,
    min_bytes: int,
    sentinel: str | None = None,
    consumers: Sequence[str] = (),
    register: bool = True,
) -> dict[str, Any]:
    """An artifact_spec. ``consumers`` is named so completion condition 12 is checkable."""
    spec: dict[str, Any] = {
        "path": path,
        "schema_ref": schema_ref,
        "min_bytes": min_bytes,
        "register_in_manifest": register,
    }
    if sentinel:
        spec["sentinel"] = sentinel
    if consumers:
        spec["consumers"] = list(consumers)
    return spec


def tool_policy(
    *,
    allow: Iterable[str],
    deny: Iterable[str] = (),
    network: str = "none",
    write_paths: Iterable[str] = (),
    forbid_write_paths: Iterable[str] = (),
    require_owner_approval: Iterable[str] = (),
    source_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deny-by-default tool policy. ``default`` is never parameterised: an allowlist that
    defaults to allow is how a redactor leaks, and this program already paid for that lesson."""
    pol: dict[str, Any] = {
        "default": "deny",
        "allow": sorted(set(allow)),
        "network": network,
    }
    if deny:
        pol["deny"] = sorted(set(deny))
    if require_owner_approval:
        pol["require_owner_approval"] = sorted(set(require_owner_approval))
    if write_paths:
        pol["write_paths"] = list(write_paths)
    if forbid_write_paths:
        pol["forbid_write_paths"] = list(forbid_write_paths)
    if source_policy is not None:
        sp = dict(source_policy)
        # AGENTS.md 9: not overridable, so it is set here rather than trusted to a caller.
        sp["treat_fetched_content_as_data"] = True
        pol["source_policy"] = sp
    return pol


def portability(bundle: str) -> dict[str, Any]:
    """Export/import. ``redact_secrets`` is const true in the schema and true here: an export
    bundle carries secret_ref NAMES only, never a value."""
    return {
        "export": {
            "format": "bundle",
            "includes": ["definition", "examples", "tests", "lineage"],
            "redact_secrets": True,
            "bundle_path": bundle,
        },
        "import": {
            "validate_against": "platform/schema/workflow-dsl.schema.json",
            "on_version_mismatch": "reject",
            "trust": {"require_signature": False, "allow_publishers": ["prekzursil"]},
        },
    }


def failure_policy(
    on_failure: str,
    classify_as: Sequence[str],
    *,
    escalate_to: str | None = None,
    quarantine_path: str | None = None,
    preserve_partial: bool = True,
) -> dict[str, Any]:
    pol: dict[str, Any] = {
        "on_failure": on_failure,
        "classify_as": list(classify_as),
        "terminal_state_required": True,
        "never_silent": True,
        "preserve_partial_artifact": preserve_partial,
    }
    if escalate_to:
        pol["escalate_to"] = escalate_to
    if quarantine_path:
        pol["quarantine_path"] = quarantine_path
    return pol


def resume(store: str, granularity: str, keys: Sequence[str]) -> dict[str, Any]:
    return {
        "enabled": True,
        "checkpoint_store": store,
        "granularity": granularity,
        "idempotency_key_from": list(keys),
        "resume_from": "last-checkpoint",
        "stale_checkpoint_seconds": 86400,
        "on_stale": "warn-and-resume",
    }


def replay_deterministic(
    seed: int,
    journal: str,
    *,
    verify: str,
    record: Sequence[str] = ("params", "inputs", "tool_calls", "tool_results", "env_fingerprint"),
    forbid: Sequence[str] = ("clock", "random", "filesystem-order", "process-id"),
    on_divergence: str = "record-discrepancy",
) -> dict[str, Any]:
    return {
        "deterministic": True,
        "seed": seed,
        "journal_path": journal,
        "record": list(record),
        "forbid_nondeterministic_sources": list(forbid),
        "replay_source": "recorded-journal",
        "verify": verify,
        "hash_algorithm": "sha256",
        "on_divergence": on_divergence,
    }


def replay_nondeterministic(journal: str, record: Sequence[str]) -> dict[str, Any]:
    """A workflow whose output depends on layout heuristics or model judgement is NOT replayable
    hash-for-hash. Declaring ``deterministic: false`` and still recording the journal is the
    honest form; claiming determinism and then setting ``verify: none`` would be decorative.

    ``replay_policy`` is ``additionalProperties: false``, so the PROSE reason cannot live in this
    block - the caller puts it in the workflow's ``x_extensions`` where a runner is required to
    ignore unknown keys rather than fail.
    """
    return {
        "deterministic": False,
        "journal_path": journal,
        "record": list(record),
        "replay_source": "recorded-journal",
        "verify": "semantic-equal",
        "on_divergence": "record-discrepancy",
        "forbid_nondeterministic_sources": ["clock", "process-id"],
    }


def cache(store: str, key_from: Sequence[str], *, scope: str = "stage", ttl: int = 86400) -> dict[str, Any]:
    return {
        "enabled": True,
        "scope": scope,
        "key_from": list(key_from),
        "store": store,
        "ttl_seconds": ttl,
        "verify_integrity": True,
    }


def dry_run(plan: str, forbid_tools: Sequence[str], emits: Sequence[str] = ("plan", "estimate", "permission-report")) -> dict[str, Any]:
    return {
        "supported": True,
        "side_effect_free": True,
        "emits": list(emits),
        "plan_artifact": plan,
        "forbid_tools": list(forbid_tools),
    }


def estimate(
    *,
    basis: str,
    confidence: str,
    cost_expected: float,
    cost_max: float,
    seconds_expected: int,
    seconds_max: int,
    tokens_expected: int,
    risk: str,
    reversibility: str,
    blast_radius: str,
    owner_approval: bool,
    measurement_source: str | None = None,
) -> dict[str, Any]:
    est: dict[str, Any] = {
        "basis": basis,
        "confidence": confidence,
        "cost": {"currency": "USD", "expected": cost_expected, "max": cost_max},
        "wallclock_seconds": {"expected": seconds_expected, "max": seconds_max},
        "tokens": {"expected": tokens_expected},
        "impact": {
            "risk": risk,
            "reversibility": reversibility,
            "blast_radius": blast_radius,
            "requires_owner_approval": owner_approval,
        },
    }
    if basis in ("historical-measured", "hybrid"):
        if not measurement_source:
            raise ValueError("a measured estimate must name the measurement it came from")
        est["measurement_source"] = measurement_source
    return est


def lineage(
    derived_from: Sequence[dict[str, Any]],
    *,
    decomposable: bool = True,
    rollback_to: Sequence[str] = (),
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "derived_from": list(derived_from),
        "decomposable_back_to_sources": decomposable,
    }
    if rollback_to:
        out["rollback_to"] = list(rollback_to)
    return out


def card(source: str, relation: str, *, credit: str = "owner", license_: str = "owner-proprietary") -> dict[str, Any]:
    return {"source": source, "relation": relation, "license": license_, "credit": credit}


def gate_predicate_v1(conditions: Sequence[int], on_fail: str) -> dict[str, Any]:
    return {
        "predicate": "completion-predicate-v1",
        "predicate_ref": "command-center/COMPLETION-GATES.json#/gate_a_unit_completion_predicate",
        "conditions_required": list(conditions),
        "blocking": True,
        "evidence_required": True,
        "on_fail": on_fail,
    }


def gate_expr(expression: str, on_fail: str, *, blocking: bool = True, evidence: bool = True) -> dict[str, Any]:
    return {
        "predicate": "custom-expression",
        "expression": expression,
        "blocking": blocking,
        "evidence_required": evidence,
        "on_fail": on_fail,
    }


def write_blueprint(doc: dict[str, Any]) -> Path:
    """Write ``platform/workflows/<id>.json`` with a stable, byte-reproducible encoding."""
    WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
    path = WORKFLOW_DIR / f"{doc['id']}.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path
