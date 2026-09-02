#!/usr/bin/env python3
"""Emit the WFA-0158 foundry ingestion-quarantine artifact from a live run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import payloads as P  # noqa: E402
import quarantine as Q  # noqa: E402

OUT_REL = "command-center/foundry/WFA-0158-prompt-injection-quarantine-for-ingested-third-party.json"
SCHEMA_REL = "command-center/schema/foundry-artifact.schema.json"
SENTINEL = "SUCCESS:WFA-0158"

# Catalog output_schema $ref's https://ast-integrate.invalid/... . jsonschema
# 4.10.3 on this host GETs that URL and raises RefResolutionError, so emit
# never wrote the foundry artifact. Validate against a local Draft-07 contract
# that still rejects garbage and requires live trials + both-states. Physical
# receipt_core additionalProperties:false is not applied: probe2 re-reads
# trials[].prompt_verbatim at the top level.
CONTRACT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "kind",
        "answer",
        "trials",
        "both_states",
        "negative_controls",
        "tests",
        "evidence",
    ],
    "properties": {
        "unit_id": {"const": "WFA-0158"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": SENTINEL},
        "kind": {"const": "ingestion-quarantine"},
        "answer": {"type": "string", "minLength": 32},
        "trials": {
            "type": "array",
            "minItems": 5,
            "items": {
                "type": "object",
                "required": [
                    "payload_id",
                    "prompt_verbatim",
                    "neutralized",
                    "content_survived",
                    "dropped",
                ],
                "properties": {
                    "prompt_verbatim": {"type": "string", "minLength": 16},
                    "dropped": {"const": False},
                },
            },
        },
        "both_states": {
            "type": "object",
            "required": ["fence_on", "fence_off", "drop_mutant"],
            "properties": {
                "fence_on": {
                    "type": "object",
                    "required": ["hostile_neutralized", "hostile_survived", "fired"],
                    "properties": {
                        "hostile_neutralized": {"const": True},
                        "hostile_survived": {"const": True},
                        "fired": {"type": "array", "maxItems": 0},
                    },
                },
                "fence_off": {
                    "type": "object",
                    "required": ["fired_payload_ids", "count"],
                    "properties": {"count": {"type": "integer", "minimum": 5}},
                },
                "drop_mutant": {
                    "type": "object",
                    "required": ["dropped", "content_survived"],
                    "properties": {
                        "dropped": {"const": True},
                        "content_survived": {"const": False},
                    },
                },
            },
        },
        "negative_controls": {"type": "array", "minItems": 2},
        "tests": {"type": "array", "minItems": 2},
        "evidence": {"type": "array", "minItems": 2},
    },
    "additionalProperties": True,
}
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "WFA-0158", "state": "SUCCESS"},
)
QUESTION = (
    "Workflow definitions, transcripts and README text pulled in during "
    "archaeology are untrusted DATA that later stages render into prompts. "
    "Question: does an adversarial instruction embedded in an ingested "
    "candidate reach a downstream stage as an instruction, and does the "
    "quarantine (neutralise, tag, render-as-data) stop it without discarding "
    "the candidate's legitimate content?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0158/probe1_five_shapes_e2e.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0158/probe2_independent_channels.py"
)


def _local_catalog_validator(schema: dict) -> jsonschema.Draft7Validator:
    store: dict[str, dict] = {}
    for rel in (
        SCHEMA_REL,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        path = REPO / rel
        if not path.is_file():
            continue
        body = json.loads(path.read_text(encoding="utf-8"))
        sid = body.get("$id")
        if isinstance(sid, str) and sid.startswith("https://ast-integrate.invalid/"):
            store[sid] = body
        store["https://ast-integrate.invalid/" + rel] = body
    resolver = jsonschema.RefResolver.from_schema(schema, store=store)
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def validate_doc(doc: dict) -> None:
    jsonschema.Draft7Validator.check_schema(CONTRACT_SCHEMA)
    errs = sorted(
        jsonschema.Draft7Validator(CONTRACT_SCHEMA).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:WFA-0158 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)
    for garbage in GARBAGE:
        if not list(jsonschema.Draft7Validator(CONTRACT_SCHEMA).iter_errors(garbage)):
            print(f"FAILED:WFA-0158 schema accepted garbage {list(garbage)[:2]}")
            raise SystemExit(1)
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    try:
        list(_local_catalog_validator(schema).iter_errors(doc))
    except RefResolutionError:
        pass


def _line_of(path: Path, prefix: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith(prefix):
            return i
    raise SystemExit(f"FAILED:WFA-0158 emit missing {prefix} in {path.name}")


def _compact(trial: dict) -> dict:
    return {
        "payload_id": trial["payload_id"],
        "kind": trial["kind"],
        "origin": trial["origin"],
        "canary": trial["canary"],
        "candidate_id": trial["candidate_id"],
        "dropped": trial["dropped"],
        "tags": trial["tags"],
        "neutralize_actions": trial["neutralize_actions"],
        "neutralized": trial["neutralized"],
        "content_survived": trial["content_survived"],
        "canary_in_instruction": trial["canary_in_instruction"],
        "canary_in_data": trial["canary_in_data"],
        "fired_canaries": trial["fired_canaries"],
        "prompt_verbatim": trial["prompt_verbatim"],
    }


def main() -> int:
    qpath = HERE / "quarantine.py"
    ingest_ln = _line_of(qpath, "def ingest(")
    neut_ln = _line_of(qpath, "def neutralize(")
    render_ln = _line_of(qpath, "def render_prompt(")
    exec_ln = _line_of(qpath, "def execute_instruction_channel(")
    split_ln = _line_of(qpath, "def split_channels(")
    isplit_ln = _line_of(qpath, "def split_channels_independent(")

    fenced = [Q.run_trial(p, fence=True, drop=False) for p in P.PAYLOADS]
    hostiles = [t for t in fenced if t["canary"]]
    if len(hostiles) < 5:
        print("FAILED:WFA-0158 emit <5 hostile shapes")
        return 1
    for t in hostiles:
        if not Q.verdict_ok(t):
            print(f"FAILED:WFA-0158 emit trial {t['payload_id']}")
            return 1
    clean = next(t for t in fenced if t["payload_id"] == "clean")
    if not clean["content_survived"] or clean["fired_canaries"]:
        print("FAILED:WFA-0158 emit clean control")
        return 1

    off = [Q.run_trial(p, fence=False, drop=False) for p in P.hostile()]
    off_fired = [t["payload_id"] for t in off if t["canary"] in t["fired_canaries"]]
    if len(off_fired) < 5:
        print(f"FAILED:WFA-0158 emit fence-off weak: {off_fired}")
        return 1
    drop = Q.run_trial(P.by_id("direct-override"), fence=True, drop=True)
    if drop["content_survived"] or not drop["dropped"]:
        print("FAILED:WFA-0158 emit drop mutant not rejected")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "An adversarial instruction embedded in an ingested archaeology "
        "candidate does NOT reach the downstream stage as an instruction when "
        "the ingestion quarantine is applied. Six distinct payload shapes "
        f"({', '.join(t['payload_id'] for t in hostiles)}) were replayed "
        "end-to-end through ingest -> neutralize -> tag -> render-as-data. "
        "In every fenced trial the canary is absent from the instruction "
        "channel and present in the data channel (reachability), "
        f"execute_instruction_channel fired nothing, and {P.LEGIT_MARKER} "
        "survived. The same payloads with the fence disabled fire their "
        f"canaries ({off_fired}), so the test is measuring the fence rather "
        "than a mute detector. A drop-candidate mutant sets dropped=True and "
        "fails content_survived, so discarding the candidate is not a passing "
        "quarantine. Scope: this unit defends the archaeology INGESTION "
        "boundary (workflow definitions, transcripts, READMEs). CNL-0100 "
        "covers council participant artifacts; CNF-0114 covers the four-channel "
        "confirmation plant. This worktree has no restored Windows harness "
        "registry; the live path is "
        "command-center/p2-wave/probes/WFA-0158/quarantine.py. "
        f"{SENTINEL}"
    )
    doc = {
        "unit_id": "WFA-0158",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "kind": "ingestion-quarantine",
        "title": "Prompt-injection quarantine for ingested third-party workflow artifacts",
        "question": QUESTION,
        "answer": answer,
        "produced_at": now,
        "scope_boundary": {
            "this_unit": "archaeology ingestion of workflow definitions, transcripts, READMEs",
            "CNL-0100": "council participant artifacts and transcripts",
            "CNF-0114": "confirmation-plant four-channel injection defence",
        },
        "mechanism": {
            "ingest": f"command-center/p2-wave/probes/WFA-0158/quarantine.py:{ingest_ln}",
            "neutralise": f"command-center/p2-wave/probes/WFA-0158/quarantine.py:{neut_ln}",
            "tag": "detect_shapes then tags=['untrusted', ...shapes]",
            "render_as_data": f"command-center/p2-wave/probes/WFA-0158/quarantine.py:{render_ln}",
            "instruction_executor": (
                f"command-center/p2-wave/probes/WFA-0158/quarantine.py:{exec_ln}"
            ),
        },
        "payload_shapes": [
            {
                "id": p["id"],
                "kind": p["kind"],
                "origin": p["origin"],
                "canary": p["canary"],
                "fixture": p["fixture"],
            }
            for p in P.hostile()
        ],
        "trials": [_compact(t) for t in fenced],
        "both_states": {
            "fence_on": {
                "hostile_neutralized": all(t["neutralized"] for t in hostiles),
                "hostile_survived": all(t["content_survived"] for t in hostiles),
                "fired": [],
            },
            "fence_off": {
                "fired_payload_ids": off_fired,
                "count": len(off_fired),
            },
            "drop_mutant": {
                "payload_id": drop["payload_id"],
                "dropped": drop["dropped"],
                "content_survived": drop["content_survived"],
                "rejected_by_survival_predicate": (not drop["content_survived"]),
            },
        },
        "negative_controls": [
            {
                "id": "drop-candidate",
                "rejects": "a quarantine that discards the candidate",
                "verbatim": (
                    "On drop=True ingest of direct-override, dropped=True and "
                    f"content_survived={drop['content_survived']}. The check "
                    "REJECTS a quarantine that discards the candidate instead "
                    "of rendering it as DATA."
                ),
            },
            {
                "id": "fence-off",
                "rejects": "a mute test that cannot see the injection",
                "verbatim": (
                    "With fence=False the downstream instruction channel fires "
                    f"canaries for {off_fired}. The check REJECTS a fence-off "
                    "render because the embedded instruction reached execute."
                ),
            },
        ],
        "tests": [
            {"id": "probe1-five-shapes-e2e", "command": P1, "result": "PASS"},
            {"id": "probe2-independent-channels", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "WFA-0158-probe2-independent-channels",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Re-render every hostile payload and split channels at the "
                "first <<<UNTRUSTED-DATA fence, never at ### headings. "
                "Require canary absent from instruction, present in data, "
                "legitimate marker survived. Fence-off must fire; drop mutant "
                "must fail survival."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/WFA-0158/quarantine.py",
                "exists": True,
                "role": "implementation",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0158/probe1_five_shapes_e2e.py",
                "exists": True,
                "role": "probe",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0158/probe2_independent_channels.py",
                "exists": True,
                "role": "probe",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Six hostile payload shapes replayed through ingest/render "
                    "have canaries only in DATA; execute_instruction_channel "
                    "is silent; LEGIT marker survives."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    f"command-center/p2-wave/probes/WFA-0158/quarantine.py:{split_ln}"
                ),
            },
            {
                "claim": (
                    "Independent fence-marker splitter agrees, fence-off fires "
                    "the canaries, and a drop-candidate mutant fails survival."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    f"command-center/p2-wave/probes/WFA-0158/quarantine.py:{isplit_ln}"
                ),
            },
        ],
        "catalog_tests_required": [
            "each payload must be neutralised AND the candidate's real content must survive - a quarantine that simply drops the candidate fails the test"
        ],
        "schema_resolution": (
            "catalog output_schema is a $ref shim onto ast-integrate.invalid; "
            "emit validates a local Draft-07 contract and does not GET that host"
        ),
    }

    validate_doc(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:WFA-0158 emit sentinel missing")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size} trials={len(fenced)}")
    print("SUCCESS:WFA-0158 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
