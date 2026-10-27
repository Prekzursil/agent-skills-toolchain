"""Builder for blueprints 1-12 of 96 (the head of 09-WORKFLOW-BLUEPRINT-LIBRARY.md).

Emits one Workflow-DSL v1 JSON document per blueprint into ``platform/workflows/``.

WHY A BUILDER AND NOT 12 HAND-WRITTEN FILES
    The 19-field work-unit contract and the eight policy blocks (retry, failure, resume,
    replay, cache, dry-run, estimate, portability) are IDENTICAL IN SHAPE across blueprints
    and DIFFERENT IN VALUE. Hand-writing the shape twelve times is how a transcription typo
    ships. So the shape is factored into helpers here and every VALUE - params, roles, the
    stage graph, the gates, the stopping rules, the work units, the mechanism signature -
    is authored per blueprint in ``bp1_data_res.py`` / ``bp1_data_gem.py``.

    Two guards keep the factoring from manufacturing near-duplicates:
      * ``assert_tools_permitted`` fails the BUILD if any role/stage/work-unit tool token is
        absent from that blueprint's hand-authored ``tool_policy.allow`` - so the allowlist
        is authored, never derived from the requests it is supposed to constrain.
      * ``test_bp1_blueprint_conformance.py`` fails if any two blueprints' mechanism
        signatures overlap too far, or if two work units share an id or an output path.

Run: ``python platform/lib/workflows/bp1_build.py`` (add ``--check`` to assert the committed
JSON is byte-identical to what this builder produces - the drift guard the test uses).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

LIB_ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
for _p in (str(LIB_ROOT), str(HERE)):
    if _p not in sys.path:  # pragma: no cover - import plumbing
        sys.path.insert(0, _p)

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / "platform" / "workflows"
SCHEMA_DIR = "command-center/schema"
LIBRARY = "C:/Users/Prekzursil/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.md"

DSL_VERSION = "1.0.0"
WORKFLOW_SCHEMA = "platform/schema/workflow-dsl.schema.json"

#: the six spec-mandated category axes (_USER-PROMPTS.md:10898 area); a blueprint names >=1
CATEGORIES = (
    "research-and-evidence",
    "engineering-and-reliability",
    "security-governance-and-risk",
    "product-design-and-strategy",
    "data-science-knowledge-and-creative",
    "collective-intelligence-and-meta",
)


def schema(name: str) -> str:
    """A resolvable ``command-center/schema`` reference for artifact class ``name``."""
    return f"{SCHEMA_DIR}/{name}.schema.json"


# ----------------------------------------------------------------------- work units


def wu(
    *,
    uid: str,
    title: str,
    phase: str,
    target: str,
    inputs: Sequence[str],
    deps: Sequence[str],
    role: str,
    tools: Sequence[str],
    substrate: str,
    timeout: int,
    out_path: str,
    out_schema: str,
    evidence: str,
    tests: Sequence[str],
    reviewer: str,
    postcondition: str,
    retry: str,
    failure_classes: Sequence[str],
    model: str = "opus",
    vendor: str = "anthropic",
    basis: str = "substantive subagents default to Opus (performance rule: quality over cost)",
    owner_approval: bool = False,
    mechanism: str | None = None,
    not_a_duplicate_because: str | None = None,
) -> dict[str, Any]:
    """One work unit carrying all 19 mandated fields (work-unit.schema.json).

    ``completion_sentinel`` is composed so it always names THIS unit's id in both the
    success and the failure branch - the SEM-002 rule 96 catalog units violate.
    """
    unit: dict[str, Any] = {
        "id": uid,
        "title": title,
        "phase": phase,
        "question_or_target": target,
        "inputs": list(inputs),
        "dependencies": list(deps),
        "assigned_model_vendor_role": {
            "model": model,
            "vendor": vendor,
            "role": role,
            "basis": basis,
        },
        "tool_permissions": list(tools),
        "execution_substrate": substrate,
        "timeout_seconds": timeout,
        "output_path": out_path,
        "output_schema": out_schema,
        "evidence_requirement": evidence,
        "tests_required": list(tests),
        "reviewer_requirement": reviewer,
        "completion_sentinel": (
            f"SUCCESS:{uid} emitted only when {postcondition}; "
            f"otherwise FAILED:{uid} <failure-class> <reason>"
        ),
        "retry_policy": retry,
        "failure_classification": list(failure_classes),
        "owner_approval_required": owner_approval,
    }
    if mechanism:
        unit["mechanism"] = mechanism
    if not_a_duplicate_because:
        unit["not_a_duplicate_because"] = not_a_duplicate_because
    return unit


def artifact(
    path: str,
    schema_ref: str,
    *,
    min_bytes: int = 256,
    sentinel: str | None = None,
    consumers: Sequence[str] = (),
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "path": path,
        "schema_ref": schema_ref,
        "min_bytes": min_bytes,
        "register_in_manifest": True,
    }
    if sentinel:
        out["sentinel"] = sentinel
    if consumers:
        out["consumers"] = list(consumers)
    return out


# -------------------------------------------------------------------- policy blocks


def retry_two_strikes(
    max_attempts: int = 3, *, escalate_to: str, retry_on: Sequence[str]
) -> dict[str, Any]:
    return {
        "strategy": "two-strikes-then-pivot",
        "max_attempts": max_attempts,
        "backoff_seconds": 20,
        "jitter": True,
        "retry_on": list(retry_on),
        "no_retry_on": ["owner-blocked", "licence-blocked"],
        "pivot": {
            "after_attempts": 2,
            "enumerate_alternatives_min": 2,
            "escalate_to": escalate_to,
        },
    }


def retry_none() -> dict[str, Any]:
    return {"strategy": "none", "max_attempts": 1}


def failure(
    on_failure: str,
    classes: Sequence[str],
    *,
    escalate_to: str | None = None,
    quarantine_path: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "on_failure": on_failure,
        "classify_as": list(classes),
        "terminal_state_required": True,
        "never_silent": True,
        "preserve_partial_artifact": True,
    }
    if escalate_to:
        out["escalate_to"] = escalate_to
    if quarantine_path:
        out["quarantine_path"] = quarantine_path
    return out


def resume_block(
    store: str, *, granularity: str, keys: Sequence[str]
) -> dict[str, Any]:
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
    seed: int, journal: str, *, verify: str = "hash-equal"
) -> dict[str, Any]:
    return {
        "deterministic": True,
        "seed": seed,
        "journal_path": journal,
        "record": [
            "params",
            "inputs",
            "tool_calls",
            "tool_results",
            "timings",
            "env_fingerprint",
        ],
        "forbid_nondeterministic_sources": [
            "clock",
            "random",
            "filesystem-order",
            "process-id",
        ],
        "replay_source": "recorded-journal",
        "verify": verify,
        "hash_algorithm": "sha256",
        "on_divergence": "fail",
    }


def replay_not_deterministic() -> dict[str, Any]:
    """Honest: live external state cannot be replayed. See x_extensions.replay_note."""
    return {"deterministic": False, "replay_source": "artifact-cache", "verify": "none"}


def cache_block(
    store: str, key_from: Sequence[str], *, ttl: int, scope: str = "stage"
) -> dict[str, Any]:
    return {
        "enabled": True,
        "scope": scope,
        "key_from": list(key_from),
        "store": store,
        "ttl_seconds": ttl,
        "verify_integrity": True,
        "invalidate_on": ["schema-version-change", "tool-version-change"],
        "read_only": False,
    }


def cache_off() -> dict[str, Any]:
    return {"enabled": False}


def dry_run_block(
    plan_artifact: str,
    forbid_tools: Sequence[str],
    *,
    emits: Sequence[str] = ("plan", "estimate", "permission-report", "graph"),
) -> dict[str, Any]:
    if not forbid_tools:
        raise ValueError(
            "dry_run.side_effect_free=true requires a non-empty forbid_tools list "
            "(a side-effect-free claim with nothing forbidden is decorative)"
        )
    return {
        "supported": True,
        "side_effect_free": True,
        "emits": list(emits),
        "plan_artifact": plan_artifact,
        "forbid_tools": list(forbid_tools),
    }


def estimate_block(
    *,
    wallclock: tuple[float, float, float],
    tokens: tuple[float, float, float],
    tool_calls: tuple[float, float],
    cost: tuple[float, float, float],
    risk: str,
    reversibility: str,
    blast_radius: str,
    confidence: str = "roughly-even",
    owner_approval: bool = False,
) -> dict[str, Any]:
    """A STATIC-DECLARED estimate.

    ``basis`` is deliberately never ``historical-measured``: none of these twelve blueprints
    has ever been run, so claiming a measured basis would be a fabrication (and the schema
    would then demand a ``measurement_source`` that does not exist).
    """
    return {
        "basis": "static-declared",
        "confidence": confidence,
        "cost": {
            "currency": "USD",
            "min": cost[0],
            "expected": cost[1],
            "max": cost[2],
        },
        "wallclock_seconds": {
            "min": wallclock[0],
            "expected": wallclock[1],
            "max": wallclock[2],
        },
        "tokens": {"min": tokens[0], "expected": tokens[1], "max": tokens[2]},
        "tool_calls": {"expected": tool_calls[0], "max": tool_calls[1]},
        "impact": {
            "risk": risk,
            "reversibility": reversibility,
            "blast_radius": blast_radius,
            "requires_owner_approval": owner_approval,
        },
    }


def portability_block(
    bundle_path: str,
    *,
    includes: Sequence[str] = ("definition", "examples", "tests", "lineage"),
) -> dict[str, Any]:
    return {
        "export": {
            "format": "bundle",
            "includes": list(includes),
            "redact_secrets": True,
            "bundle_path": bundle_path,
        },
        "import": {
            "validate_against": WORKFLOW_SCHEMA,
            "on_version_mismatch": "reject",
            "trust": {"require_signature": False, "allow_publishers": ["prekzursil"]},
        },
    }


def lineage_block(
    sources: Sequence[Mapping[str, Any]], *, rollback_to: Sequence[str] = ()
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "derived_from": [dict(s) for s in sources],
        "decomposable_back_to_sources": True,
    }
    if rollback_to:
        out["rollback_to"] = list(rollback_to)
    return out


def card(bp_id: str, line: int) -> dict[str, Any]:
    return {"card": bp_id, "library": LIBRARY, "card_heading_line": line}


# ------------------------------------------------------------------- build guards


def _walk_stages(stages: Any):
    if not isinstance(stages, list):
        return
    for stage in stages:
        if not isinstance(stage, Mapping):
            continue
        yield stage
        if isinstance(stage.get("body"), list):
            yield from _walk_stages(stage["body"])
        for slot in ("diagnose", "repair", "verify"):
            if isinstance(stage.get(slot), Mapping):
                yield from _walk_stages([stage[slot]])


def assert_tools_permitted(doc: Mapping[str, Any]) -> None:
    """Fail the BUILD when a requested tool is outside the hand-authored allowlist."""
    policy = doc.get("tool_policy") or {}
    allow = {str(t) for t in policy.get("allow") or []}
    deny = {str(t) for t in policy.get("deny") or []}
    problems: list[str] = []

    def check(where: str, tokens: Any) -> None:
        for token in tokens or []:
            text = str(token)
            if text in deny:
                problems.append(f"{where}: {text!r} is in tool_policy.deny")
            elif text not in allow:
                problems.append(f"{where}: {text!r} is not in tool_policy.allow")

    for name, spec in (doc.get("roles") or {}).items():
        if isinstance(spec, Mapping):
            check(f"roles/{name}", spec.get("tool_permissions"))
    for stage in _walk_stages(doc.get("stages")):
        sid = stage.get("id")
        check(f"stage/{sid}", stage.get("tool_permissions"))
        unit = stage.get("work_unit")
        if isinstance(unit, Mapping):
            check(f"stage/{sid}/work_unit", unit.get("tool_permissions"))
    if problems:
        raise SystemExit(
            f"FAILED:bp1-build tool_policy conformance for {doc.get('id')!r}:\n  "
            + "\n  ".join(problems)
        )


def assert_roles_declared(doc: Mapping[str, Any]) -> None:
    declared = set(doc.get("roles") or {})
    bad = [
        f"{s.get('id')} -> {s.get('role')}"
        for s in _walk_stages(doc.get("stages"))
        if s.get("role") and str(s["role"]) not in declared
    ]
    if bad:
        raise SystemExit(
            f"FAILED:bp1-build undeclared stage role(s) in {doc.get('id')!r}: {bad}; "
            f"declared {sorted(declared)}"
        )


def assert_worked_example(doc: Mapping[str, Any]) -> None:
    """A worked example must exist, be typed, and declare an expected plan + both-states."""
    ext = doc.get("x_extensions") or {}
    example = ext.get("worked_example")
    if not isinstance(example, Mapping):
        raise SystemExit(
            f"FAILED:bp1-build {doc.get('id')!r} has no x_extensions.worked_example"
        )
    for key in ("name", "params", "expected_stage_order", "stopping_rule_controls"):
        if key not in example:
            raise SystemExit(
                f"FAILED:bp1-build {doc.get('id')!r} worked_example missing {key!r}"
            )
    for ctl in example["stopping_rule_controls"]:
        for key in ("rule", "fires_on", "does_not_fire_on"):
            if key not in ctl:
                raise SystemExit(
                    f"FAILED:bp1-build {doc.get('id')!r} stopping_rule_control missing {key!r} "
                    "- a firing context without a NON-firing control measures nothing"
                )
    if not ext.get("mechanism_signature"):
        raise SystemExit(
            f"FAILED:bp1-build {doc.get('id')!r} has no mechanism_signature"
        )


def finalise(doc: dict[str, Any]) -> dict[str, Any]:
    """Run every build guard over one blueprint, then return it."""
    for key in ("dsl_version", "id", "name", "version", "stages"):
        if key not in doc:
            raise SystemExit(f"FAILED:bp1-build blueprint missing required key {key!r}")
    bad_cats = [c for c in doc.get("categories", []) if c not in CATEGORIES]
    if bad_cats:
        raise SystemExit(
            f"FAILED:bp1-build {doc['id']!r} declares category outside the spec axes: {bad_cats}"
        )
    assert_tools_permitted(doc)
    assert_roles_declared(doc)
    assert_worked_example(doc)
    return doc


# ------------------------------------------------------------------------- registry


#: data modules, in blueprint order; each exposes ``blueprints() -> list[dict]``
DATA_MODULES = (
    "bp1_data_a",  # BP-RES-01, BP-RES-02
    "bp1_data_b",  # BP-RES-03, BP-RES-04
    "bp1_data_c",  # BP-RES-05, BP-RES-06
    "bp1_data_d",  # BP-GEM-01, BP-GEM-02
    "bp1_data_e",  # BP-GEM-03, BP-GEM-04
    "bp1_data_f",  # BP-GEM-05, BP-BRN-01
)


def all_blueprints(modules: Sequence[str] | None = None) -> list[dict[str, Any]]:
    import importlib

    docs: list[dict[str, Any]] = []
    for name in modules or DATA_MODULES:
        docs.extend(importlib.import_module(name).blueprints())
    seen: dict[str, str] = {}
    for doc in docs:
        if doc["id"] in seen:
            raise SystemExit(f"FAILED:bp1-build duplicate blueprint id {doc['id']!r}")
        seen[doc["id"]] = doc["name"]
    return docs


def filename(doc: Mapping[str, Any]) -> str:
    return f"{doc['id']}.json"


def render(doc: Mapping[str, Any]) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=False) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bp1_build")
    ap.add_argument(
        "--check",
        action="store_true",
        help="do not write; assert the committed JSON matches this builder byte-for-byte",
    )
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    docs = all_blueprints()
    drift: list[str] = []
    for doc in docs:
        target = out_dir / filename(doc)
        text = render(doc)
        if args.check:
            if not target.is_file():
                drift.append(f"{target.name}: MISSING on disk")
            elif target.read_text(encoding="utf-8") != text:
                drift.append(
                    f"{target.name}: on-disk bytes differ from the builder output"
                )
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    flagship = [d["id"] for d in docs if d.get("flagship")]
    print(f"blueprints         : {len(docs)}")
    print(f"flagship           : {len(flagship)} -> {flagship}")
    print(f"output dir         : {out_dir}")
    if args.check and drift:
        for row in drift:
            print(f"  DRIFT {row}")
        print(f"FAILED:bp1-build {len(drift)} file(s) drifted from the builder")
        return 1
    print("SUCCESS:bp1-build" if not drift else "FAILED:bp1-build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
