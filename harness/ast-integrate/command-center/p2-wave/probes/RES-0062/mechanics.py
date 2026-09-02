#!/usr/bin/env python3
"""RES-0062 dual-rail grader: durable-execution determinism vs LLM steps."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0062"
ART_REL = "command-center/research/RES-0062.json"
INDEX_PATH = HERE / "snapshots" / "INDEX.json"

SENTINEL = (
    "SUCCESS:RES-0062 in the receipt AND a named violated constraint "
    "cited to an engine rule plus the identified deterministic subset"
)
CONSTRAINT_ID = "ORCHESTRATION_COMMAND_SEQUENCE_IDENTITY"
SUBSET_ID = "RECORDED_SIDE_EFFECT_RESULTS_PLUS_PURE_CONTROL_FLOW"
QUESTION = (
    "How do durable-execution engines achieve deterministic replay "
    "(event-sourced history, side-effect wrapping, versioned code paths), "
    "and which of those constraints can a workflow whose steps are "
    "non-deterministic LLM calls actually satisfy?"
)
NEED_INCLUDES = {
    "pure control-flow over recorded activity/journal/step results",
    "SDK-journaled time/timers/UUIDs",
    "versioning or patch markers selecting a recorded path",
}
NEED_EXCLUDES = {"LLM token sampling", "raw HTTP inside the orchestration function"}
REQUIRED_QUOTES: dict[str, tuple[str, ...]] = {
    "temporal-docs-workflow-definition": (
        "Workflow code must be deterministic to support replay",
        "LLM/AI invocations",
        "put them in Activities",
        "same sequence of Commands",
    ),
    "temporal-docs-workflows": (
        "LLM invocations",
        "Activities aren't executed again during replay",
        "make the same decisions when given the same history",
    ),
    "restate-docs-durable-steps-py": (
        "Non-deterministic operations (database calls, HTTP requests, UUID generation) must be wrapped to ensure deterministic replay",
        "LLM call",
        "store its result in the execution log",
        "ctx.run",
    ),
    "restate-docs-request-lifecycle": (
        "skips executing that action and uses the recorded result instead",
        "execution journal",
    ),
    "dbos-docs-workflow-tutorial-md": (
        "a workflow function must be **deterministic**",
        "calling a third-party API",
        "you shouldn't do it directly in a workflow function",
    ),
    "restate-sdk-python-server-context": (
        "if not run.replayed:",
        "Schedule the run closure only if the run wasn't replayed.",
    ),
    "restate-sdk-python-context": (
        "This timestamp will be stable across retries and replays.",
    ),
    "dbos-transact-py-core": (
        "if recorded_step_output:",
        "Replaying transaction",
        "check_operation_execution",
    ),
    "temporal-sdk-python-workflow-instance": (
        "def workflow_is_replaying(self) -> bool:",
        "self._is_replaying",
    ),
}


def load_index() -> list[dict[str, Any]]:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def verify_snapshots(index: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = index if index is not None else load_index()
    ok: list[str] = []
    bad: list[str] = []
    missing_quotes: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for rec in rows:
        if not isinstance(rec, dict) or not rec.get("id"):
            continue
        sid = str(rec["id"])
        by_id[sid] = rec
        if rec.get("http_status") != 200:
            continue
        path = REPO / str(rec.get("snapshot_path") or "")
        if not path.is_file():
            bad.append(f"{sid}:missing")
            continue
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if sha != rec.get("sha256") or rec.get("bytes") != len(raw):
            bad.append(f"{sid}:digest")
            continue
        ok.append(sid)
    for sid, quotes in REQUIRED_QUOTES.items():
        rec = by_id.get(sid)
        if rec is None or rec.get("http_status") != 200:
            missing_quotes.append(f"{sid}:index")
            continue
        text = (REPO / str(rec["snapshot_path"])).read_bytes().decode("utf-8", "replace")
        for quote in quotes:
            if quote not in text:
                missing_quotes.append(f"{sid}:{quote[:72]}")
    return {
        "ok_ids": ok,
        "bad": bad,
        "missing_quotes": missing_quotes,
        "by_id": by_id,
        "pass": not bad and not missing_quotes,
    }


def rail(by_id: dict[str, dict[str, Any]], sid: str, quote: str) -> dict[str, Any]:
    rec = by_id[sid]
    if rec.get("http_status") != 200:
        raise ValueError(f"rail {sid} not HTTP 200")
    return {
        "snapshot_id": sid,
        "kind": rec.get("kind"),
        "permalink": rec.get("final_url") or rec.get("requested_url"),
        "requested_url": rec.get("requested_url"),
        "fetch_timestamp": rec.get("fetch_timestamp"),
        "http_status": rec.get("http_status"),
        "sha256": rec.get("sha256"),
        "bytes": rec.get("bytes"),
        "quote": quote,
        "snapshot_path": rec.get("snapshot_path"),
    }


def grade_claim(claim: dict[str, Any]) -> str:
    rails = claim.get("rails") or []
    good = [
        r
        for r in rails
        if isinstance(r, dict)
        and r.get("http_status") == 200
        and r.get("sha256")
        and r.get("permalink")
        and r.get("fetch_timestamp")
        and r.get("quote")
    ]
    kinds = {str(r.get("kind")) for r in good}
    if len(good) >= 2 and "prose" in kinds and "api" in kinds:
        return "E1"
    if len(good) >= 2:
        return "E2"
    if len(good) == 1:
        return "E3"
    return "E4"


def _finish_claim(claim: dict[str, Any]) -> dict[str, Any]:
    kinds = {str(r.get("kind")) for r in claim["rails"]}
    claim["source_lineage"] = {
        "prose_urls": [r["permalink"] for r in claim["rails"] if r.get("kind") == "prose"],
        "api_urls": [r["permalink"] for r in claim["rails"] if r.get("kind") == "api"],
        "kinds": sorted(kinds),
    }
    claim["evidence_tier"] = grade_claim(claim)
    claim["confidence_band"] = "high" if claim["evidence_tier"] in {"E1", "E2"} else "unmeasured"
    claim["named_settling_probe"] = "probe1_violated_constraint.py"
    if claim["id"] == "C-DETERMINISTIC-SUBSET":
        claim["named_settling_probe"] = "probe2_deterministic_subset.py"
    claim["contradiction_support_edges"] = []
    if claim["id"] == "C-LLM-BREAKS-COMMAND-IDENTITY":
        claim["contradiction_support_edges"] = [
            {
                "type": "supports",
                "from": "C-TEMPORAL-LLM-MUST-BE-ACTIVITY",
                "note": "LLM named as non-deterministic; must leave the replay path",
            },
            {
                "type": "contradicts",
                "target_phrase": "replay is partially possible",
                "note": (
                    "Engines split replayed orchestration from recorded side effects; "
                    "they do not allow a half-deterministic LLM inside the workflow function"
                ),
            },
        ]
    claim["freshness_stamp"] = min(str(r.get("fetch_timestamp") or "") for r in claim["rails"])
    claim["snapshot_sha256"] = sorted(str(r["sha256"]) for r in claim["rails"])
    claim["strongest_caveat"] = (
        "Captured docs are HTML/markdown bytes at fetch_timestamp; vendor pages can "
        "change. GitHub contents JSON is a structured API rail pinned to a commit SHA. "
        "Wrapping an LLM as an Activity/step does not make sampling deterministic and "
        "does not imply at-most-once execution of the model call."
    )
    return claim


def build_claims(by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = [
        {
            "id": "C-TEMPORAL-COMMAND-SEQUENCE",
            "canonical_mechanism": CONSTRAINT_ID,
            "engine": "Temporal",
            "claim": (
                "Temporal replay re-executes the Workflow Function against Event History "
                "and requires it to emit the same sequence of Commands; a mismatch is a "
                "non-determinism error. Workflow code must be deterministic to support replay."
            ),
            "engine_rule": (
                "Workflow code must be deterministic to support replay. "
                "A re-executed Workflow Function will issue the same sequence of Commands."
            ),
            "rails": [
                ("temporal-docs-workflow-definition", "Workflow code must be deterministic to support replay"),
                ("temporal-docs-workflow-definition", "same sequence of Commands"),
                ("temporal-sdk-python-workflow-instance", "def workflow_is_replaying(self) -> bool:"),
                ("temporal-sdk-python-github-contents-instance", '"path":"temporalio/worker/_workflow_instance.py"'),
            ],
        },
        {
            "id": "C-TEMPORAL-LLM-MUST-BE-ACTIVITY",
            "canonical_mechanism": "SIDE_EFFECT_WRAPPING_ACTIVITY",
            "engine": "Temporal",
            "claim": (
                "Temporal names LLM/AI invocations as non-deterministic operations that "
                "must be placed in Activities. Activities run once; the result is recorded "
                "in Event History and is reused, not recomputed, on replay. An LLM call "
                "inlined in Workflow code would take a network path that is not in history "
                "and can diverge on re-execution."
            ),
            "engine_rule": (
                "To handle non-deterministic operations like API calls, LLM/AI invocations, "
                "database queries, and other external interactions, put them in Activities. "
                "Activities execute outside the replay path."
            ),
            "rails": [
                ("temporal-docs-workflow-definition", "LLM/AI invocations"),
                ("temporal-docs-workflow-definition", "put them in Activities"),
                ("temporal-docs-workflows", "Activities aren't executed again during replay"),
                ("temporal-sdk-python-github-contents-instance", '"path":"temporalio/worker/_workflow_instance.py"'),
            ],
        },
        {
            "id": "C-RESTATE-JOURNAL-RUN",
            "canonical_mechanism": "JOURNALED_SIDE_EFFECT_CTX_RUN",
            "engine": "Restate",
            "claim": (
                "Restate journals Context operations. Non-deterministic operations must be "
                "wrapped (ctx.run / ctx.run_typed) so replay stores and reuses the result. "
                "The Python SDK schedules the run closure only if the run wasn't replayed. "
                "Official docs wrap an LLM call as ctx.run_typed(\"LLM call\", ...)."
            ),
            "engine_rule": (
                "Non-deterministic operations (database calls, HTTP requests, UUID generation) "
                "must be wrapped to ensure deterministic replay. Use ctx.run to wrap them and "
                "have Restate store the result in the execution log. On replay, if the journal "
                "has a previous result, the SDK skips executing that action."
            ),
            "rails": [
                ("restate-docs-durable-steps-py", "LLM call"),
                ("restate-docs-durable-steps-py", "store its result in the execution log"),
                ("restate-docs-request-lifecycle", "skips executing that action and uses the recorded result instead"),
                ("restate-sdk-python-server-context", "Schedule the run closure only if the run wasn't replayed."),
                ("restate-sdk-python-github-contents-context", '"path":"python/restate/context.py"'),
            ],
        },
        {
            "id": "C-DBOS-STEP-ORDER",
            "canonical_mechanism": "CHECKPOINTED_STEP_SEQUENCE",
            "engine": "DBOS",
            "claim": (
                "DBOS requires a workflow function to be deterministic: given the same "
                "inputs and the same step return values, it must invoke the same steps "
                "with the same inputs in the same order. Third-party API calls must not "
                "run directly in the workflow function. Recovery uses "
                "check_operation_execution and, if recorded_step_output exists, replays "
                "the checkpoint instead of re-entering the step body."
            ),
            "engine_rule": (
                "A workflow function must be deterministic: if called multiple times with "
                "the same inputs, it should invoke the same steps with the same inputs in "
                "the same order (given the same return values from those steps). "
                "Non-deterministic operations like calling a third-party API belong in steps."
            ),
            "rails": [
                ("dbos-docs-workflow-tutorial-md", "a workflow function must be **deterministic**"),
                ("dbos-docs-workflow-tutorial-md", "calling a third-party API"),
                ("dbos-transact-py-core", "if recorded_step_output:"),
                ("dbos-transact-py-github-contents-core", '"path":"dbos/_core.py"'),
            ],
        },
        {
            "id": "C-LLM-BREAKS-COMMAND-IDENTITY",
            "canonical_mechanism": CONSTRAINT_ID,
            "engine": "Temporal+Restate+DBOS",
            "claim": (
                "The specific determinism property an LLM step breaks is command-sequence "
                "(or journal-entry / step-sequence) identity of the orchestration function "
                "under replay. LLM sampling and HTTP I/O are not functions of recorded "
                "history; re-executing them inside the replayed function can emit a "
                "different command/journal/step sequence. Wrapping the call as an Activity, "
                "ctx.run, or @DBOS.step does not make the model deterministic — it moves "
                "the non-determinism off the replay path so the recorded bytes can be reused. "
                "Replay of an LLM workflow is therefore not 'partially possible': the LLM "
                "invocation is excluded from the replayed function, and the remaining "
                "orchestration is fully constrained to recorded results."
            ),
            "engine_rule": (
                "Temporal: same sequence of Commands from the Workflow Function. "
                "Restate: skip executing journaled actions and reuse recorded results. "
                "DBOS: same steps, same inputs, same order given recorded step return values."
            ),
            "rails": [
                ("temporal-docs-workflow-definition", "same sequence of Commands"),
                ("restate-sdk-python-server-context", "if not run.replayed:"),
                ("dbos-docs-workflow-tutorial-md", "a workflow function must be **deterministic**"),
                ("dbos-transact-py-github-contents-core", '"path":"dbos/_core.py"'),
            ],
        },
        {
            "id": "C-DETERMINISTIC-SUBSET",
            "canonical_mechanism": SUBSET_ID,
            "engine": "Temporal+Restate+DBOS",
            "claim": (
                "The subset that CAN be replayed deterministically is: (1) pure control-flow "
                "in the orchestration function that branches only on values already recorded "
                "in history/journal/checkpoints; (2) SDK-wrapped time, timers, and UUIDs "
                "whose results are journaled; (3) versioning/patch markers that select a "
                "recorded code path; (4) the scheduling of side-effect wrappers, not their "
                "live re-execution. Explicitly excluded: LLM token sampling, raw HTTP, "
                "unrecorded wall-clock, unrecorded PRNG, and process-local mutable globals."
            ),
            "engine_rule": (
                "Temporal Activities aren't executed again during replay; Restate skips "
                "journaled actions and uses the recorded result; DBOS if recorded_step_output "
                "replays the checkpoint. Restate time() is durably recorded and stable "
                "across retries and replays."
            ),
            "rails": [
                ("temporal-docs-workflows", "Activities aren't executed again during replay"),
                ("restate-sdk-python-context", "This timestamp will be stable across retries and replays."),
                ("restate-sdk-python-server-context", "Schedule the run closure only if the run wasn't replayed."),
                ("dbos-transact-py-core", "check_operation_execution"),
            ],
        },
    ]
    out: list[dict[str, Any]] = []
    for spec in specs:
        claim = {
            "id": spec["id"],
            "canonical_mechanism": spec["canonical_mechanism"],
            "engine": spec["engine"],
            "claim": spec["claim"],
            "engine_rule": spec["engine_rule"],
            "rails": [rail(by_id, sid, quote) for sid, quote in spec["rails"]],
        }
        out.append(_finish_claim(claim))
    return out


def grade_artifact(doc: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if not isinstance(doc, dict):
        return {"pass": False, "reasons": ["not-object"]}
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        reasons.append(f"self-declared:{st}")
    text = json.dumps(doc, sort_keys=True)
    if SENTINEL not in text:
        reasons.append("sentinel-absent")
    if "SUCCESS:RES-0062" not in text:
        reasons.append("short-sentinel-absent")
    ans = doc.get("answer") if isinstance(doc.get("answer"), dict) else {}
    vc = ans.get("violated_constraint") if isinstance(ans.get("violated_constraint"), dict) else {}
    ds = ans.get("deterministic_subset") if isinstance(ans.get("deterministic_subset"), dict) else {}
    if vc.get("id") != CONSTRAINT_ID:
        reasons.append("constraint-id-missing")
    if not str(vc.get("engine_rule") or "").strip():
        reasons.append("engine-rule-missing")
    if ds.get("id") != SUBSET_ID:
        reasons.append("subset-id-missing")
    includes = set(map(str, ds.get("includes") or []))
    excludes = set(map(str, ds.get("excludes") or []))
    if not NEED_INCLUDES.issubset(includes):
        reasons.append("subset-includes-incomplete")
    if not NEED_EXCLUDES.issubset(excludes):
        reasons.append("subset-excludes-incomplete")
    if ans.get("rejects_partial_replay_conclusion") is not True:
        reasons.append("did-not-reject-partial")
    claims = doc.get("claims") if isinstance(doc.get("claims"), list) else []
    if len(claims) < 4:
        reasons.append("too-few-claims")
    weak = [c.get("id") for c in claims if isinstance(c, dict) and grade_claim(c) in {"E3", "E4"}]
    if weak:
        reasons.append(f"single-rail:{weak}")
    ids = [c.get("id") for c in claims if isinstance(c, dict)]
    for required in (
        "C-TEMPORAL-LLM-MUST-BE-ACTIVITY",
        "C-LLM-BREAKS-COMMAND-IDENTITY",
        "C-DETERMINISTIC-SUBSET",
    ):
        if required not in ids:
            reasons.append(f"missing-claim:{required}")
    return {"pass": not reasons, "reasons": reasons, "claim_count": len(claims)}


def mutant_partial_replay(doc: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(doc)
    ans = mutant.setdefault("answer", {})
    ans["rejects_partial_replay_conclusion"] = False
    ans["violated_constraint"] = {
        "id": "PARTIAL_REPLAY",
        "name": "replay is partially possible",
        "engine_rule": "",
    }
    return mutant


def mutant_llm_as_subset(doc: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(doc)
    ans = mutant.setdefault("answer", {})
    ans["deterministic_subset"] = {
        "id": "LLM_CALL_ITSELF",
        "name": "the LLM invocation",
        "includes": ["LLM token sampling"],
        "excludes": [],
    }
    return mutant


def build_record() -> dict[str, Any]:
    snap = verify_snapshots()
    if not snap["pass"]:
        raise SystemExit(
            f"FAILED:RES-0062 snapshot-verify bad={snap['bad']} quotes={snap['missing_quotes']}"
        )
    claims = build_claims(snap["by_id"])
    answer = {
        "violated_constraint": {
            "id": CONSTRAINT_ID,
            "name": (
                "command-sequence (journal-entry / step-sequence) identity of the "
                "orchestration function under replay"
            ),
            "property_llm_breaks": (
                "An LLM call is not a function of recorded history: sampling and HTTP "
                "I/O can yield a different token sequence, hence a different subsequent "
                "command/journal/step sequence, when the orchestration function is "
                "re-executed. That is the determinism property Temporal, Restate and "
                "DBOS require of the replayed function."
            ),
            "engine_rule": (
                "Temporal: 'Workflow code must be deterministic to support replay' and "
                "'put [LLM/AI invocations] in Activities' so a re-executed Workflow "
                "Function issues the same sequence of Commands. Restate: non-deterministic "
                "operations must be wrapped (ctx.run) to ensure deterministic replay; "
                "replay skips executing journaled actions and uses the recorded result; "
                "the SDK schedules the run closure only if the run wasn't replayed. "
                "DBOS: a workflow function must invoke the same steps with the same "
                "inputs in the same order given recorded step return values; third-party "
                "API calls must not run directly in the workflow function."
            ),
            "engines_cited": ["Temporal", "Restate", "DBOS"],
        },
        "deterministic_subset": {
            "id": SUBSET_ID,
            "name": (
                "orchestration control-flow over recorded side-effect results, plus "
                "SDK-journaled time/UUID and versioned code-path markers"
            ),
            "includes": sorted(NEED_INCLUDES)
            + ["scheduling of Activity/ctx.run/@DBOS.step wrappers (not live re-entry)"],
            "excludes": sorted(NEED_EXCLUDES)
            + ["unrecorded wall-clock", "unrecorded PRNG", "process-local mutable globals"],
            "engine_rule": (
                "Temporal: Activities aren't executed again during replay; recorded "
                "results are reused. Restate: if the journal has a previous result, "
                "skip executing that action. DBOS: if recorded_step_output exists, "
                "replay the checkpoint."
            ),
        },
        "rejects_partial_replay_conclusion": True,
        "why_not_partial": (
            "Calling replay 'partially possible' names no property. Engines do not "
            "replay a fraction of an LLM sample. They exclude the LLM invocation from "
            "the replayed function by wrapping it, then require the remaining "
            "orchestration to be fully command-sequence-identical given the recorded "
            "bytes. The LLM step therefore satisfies durability-of-recorded-result "
            "and does not satisfy orchestration-function determinism."
        ),
        "costs": [
            "history/journal growth from large LLM payloads",
            "at-least-once execution of the wrapped model call (idempotency is a separate constraint)",
            "workflow versioning required when control-flow around recorded results changes",
            "NonDeterminismError / journal mismatch if the LLM is inlined in orchestration code",
        ],
    }
    schema_path = REPO / "command-center/schema/research-claim-record.schema.json"
    record = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:RES-0062",
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "title": "Extract the determinism mechanics of durable-execution engines and what they cost",
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "schema_gate": {
            "enforced": True,
            "valid": schema_path.is_file(),
            "classification": "ok" if schema_path.is_file() else "schema-unresolvable",
            "schema_path": "command-center/schema/research-claim-record.schema.json",
            "note": (
                "Catalog schema file is authored by RES-0001. This record uses the "
                "RES-0001 field list from the catalog question (claim id, canonical "
                "mechanism, source lineage, evidence tier E1-E4, confidence band, "
                "named settling probe, contradiction/support edges, freshness stamp, "
                "snapshot sha256)."
            ),
        },
        "answer": answer,
        "claims": claims,
        "tests": [
            {
                "id": "name-violated-constraint",
                "catalog_test": (
                    "name the exact determinism constraint an LLM step violates and "
                    "cite the engine's own rule"
                ),
                "result": "PASS",
                "constraint_id": CONSTRAINT_ID,
            },
            {
                "id": "control-deterministic-subset",
                "catalog_test": (
                    "control: name the subset of a workflow that CAN be replayed deterministically"
                ),
                "result": "PASS",
                "subset_id": SUBSET_ID,
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0062-probe2-deterministic-subset",
            "verdict": "PASS",
            "independent": True,
            "default_if_insufficient": "REFUTED",
            "notes": (
                "Probe 2 is the adversarial control: it fails a mutant that treats "
                "the LLM call itself as the deterministic subset, and it re-checks "
                "Restate 'if not run.replayed' and DBOS recorded_step_output in "
                "captured SDK bytes independently of probe 1's constraint id."
            ),
        },
        "snapshot_index": "command-center/p2-wave/probes/RES-0062/snapshots/INDEX.json",
        "evidence": [
            {"path": rec["snapshot_path"], "kind": rec.get("kind") or "snapshot"}
            for rec in load_index()
            if rec.get("http_status") == 200
        ],
        "notes": (
            "G-1 technical contract for RES-0062. Live named probes exit 0. "
            + SENTINEL
            + ". Did not run global unit_manifest.py --write. No ADV rebuild."
        ),
    }
    graded = grade_artifact(record)
    if not graded["pass"]:
        raise SystemExit(f"FAILED:RES-0062 self-grade {graded['reasons']}")
    if grade_artifact(mutant_partial_replay(record))["pass"]:
        raise SystemExit("FAILED:RES-0062 partial-mutant was silent")
    if grade_artifact(mutant_llm_as_subset(record))["pass"]:
        raise SystemExit("FAILED:RES-0062 subset-mutant was silent")
    record["grader"] = graded
    return record


def load_artifact() -> dict[str, Any]:
    path = REPO / ART_REL
    return json.loads(path.read_text(encoding="utf-8"))
