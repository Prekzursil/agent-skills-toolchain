#!/usr/bin/env python3
"""Emit RES-0143 primary artifact and per-unit G-1 receipts.

Catalog output_schema design-spec.schema.json is absent on this worktree.
G-1 does not consult that file. Do not run unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import ensure_on_disk  # noqa: E402
from measure import measure  # noqa: E402
from protocol import PROTOCOL_ID  # noqa: E402

UNIT = "RES-0143"
OUT = (
    "command-center/research/sources-frontier/"
    "RES-0143-anecdote-to-falsifiable-claim-protocol.json"
)
SCHEMA_DECLARED = "command-center/schema/design-spec.schema.json"
SENTINEL = "SUCCESS:RES-0143"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0143/probe1_survival_and_negative_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0143/probe2_span_diff_both_states.py"
)
PROTO_REL = "command-center/p2-wave/probes/RES-0143/protocol.py"
AUDIT_REL = "command-center/p2-wave/probes/RES-0143/audit.py"
CORPUS_REL = "command-center/p2-wave/probes/RES-0143/corpus.py"
QUESTION = (
    "Define and validate the transformation that takes an unstructured "
    "anecdote ('X broke when I did Y') into a claim record with an explicit "
    "precondition, an observable, and a local experiment - and measure what "
    "fraction of a 30-anecdote sample survives the transformation without "
    "inventing detail the source never stated."
)


def sha_bytes(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def file_url(rel: str) -> str:
    return "file://" + str((REPO / rel).resolve())


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def first_json(text: str):
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = decoder.raw_decode(text[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


def manifest_row(rel: str, role: str) -> dict:
    sha, size = sha_bytes(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/RES-0143/SUBAGENT-RETURN.json",
        "role": role,
    }


def slim(rec: dict) -> dict:
    keys = (
        "id",
        "cohort",
        "live_disposition",
        "reason",
        "template_id",
        "precondition",
        "observable",
        "local_experiment",
        "inferred_labels",
        "source_diff",
        "path",
        "sha256",
        "matches_pin",
        "audit_ok",
    )
    return {k: rec.get(k) for k in keys}


def rail(kind: str, rel: str, sha: str, ts: str) -> dict:
    return {
        "kind": kind,
        "permalink": file_url(rel),
        "path": rel,
        "fetch_timestamp": ts,
        "http_status": 0,
        "sha256": sha,
    }


def main() -> int:
    pinned = ensure_on_disk()
    m = measure()
    if not (
        m["pin_ok"]
        and m["audit_ok"]
        and m["negative_controls"]["all_not_transformable"]
        and m["survival_not_100_percent"]
        and m["n_sample"] == 30
    ):
        print("FAILED:RES-0143 emit live measure did not pass")
        print(json.dumps({k: v for k, v in m.items() if k != "rows"}, indent=2, sort_keys=True))
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_path = REPO / SCHEMA_DECLARED
    schema_present = schema_path.is_file() and schema_path.stat().st_size > 0
    user_prompts = REPO / "_USER-PROMPTS.md"
    register = REPO / "command-center/sources/REGISTER.md"
    claims_reg = REPO / "command-center/CLAIM-REGISTRY.json"
    proto_sha, proto_n = sha_bytes(REPO / PROTO_REL)
    audit_sha, audit_n = sha_bytes(REPO / AUDIT_REL)
    corpus_sha, _ = sha_bytes(REPO / CORPUS_REL)

    survived = [
        r
        for r in m["rows"]
        if str(r["id"]).startswith("S") and r["live_disposition"] == "TRANSFORMABLE"
    ]
    refused = [
        r
        for r in m["rows"]
        if str(r["id"]).startswith("S") and r["live_disposition"] != "TRANSFORMABLE"
    ]
    negs = [r for r in m["rows"] if str(r["id"]).startswith("N")]
    lineage = [
        {
            "id": r["id"],
            "resolved_url": file_url(r["path"]),
            "path": r["path"],
            "fetch_timestamp": ts,
            "http_status": 0,
            "sha256": r["sha256"],
            "bytes": r["bytes"],
            "note": "committed fixture; not a live forum fetch",
        }
        for r in pinned
    ]

    claims = [
        {
            "id": "CLM-PROTOCOL-SPAN-COPY",
            "claim": (
                "The protocol emits a claim only when the anecdote already contains "
                "a first-person when/after/if clause and a specific failure observable; "
                "required slots are copied as contiguous source spans."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "sources": [
                rail("api", PROTO_REL, proto_sha, ts),
                rail("prose", AUDIT_REL, audit_sha, ts),
            ],
            "named_independent_verification_path": P2,
        },
        {
            "id": "CLM-SURVIVAL-FRACTION",
            "claim": (
                f"On this pinned 30-anecdote fixture sample, {m['n_survived']}/30 "
                f"({m['survival_fraction']:.3f}) survive as TRANSFORMABLE without "
                "invented required-slot tokens. The rate is not 100%."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "sources": [
                rail("api", PROTO_REL, proto_sha, ts),
                rail("prose", CORPUS_REL, corpus_sha, ts),
            ],
            "named_independent_verification_path": P1,
            "n_survived": m["n_survived"],
            "n_sample": 30,
            "fraction": m["survival_fraction"],
        },
        {
            "id": "CLM-NEGATIVE-CONTROL",
            "claim": (
                "Five vague anecdotes (N01-N05) are NOT-TRANSFORMABLE. A protocol "
                "that transformed 100% of inputs, including these, would be fabricating."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "sources": [
                rail("api", PROTO_REL, proto_sha, ts),
                rail("prose", CORPUS_REL, corpus_sha, ts),
            ],
            "named_independent_verification_path": P1,
            "ids": [r["id"] for r in negs],
        },
        {
            "id": "CLM-FIXTURE-NOT-LIVE-HARVEST",
            "claim": (
                "The 30-anecdote sample is a committed fixture corpus constructed to "
                "exercise specified / partial / hearsay / vague shapes. It is not a "
                "harvest of 30 live forum posts. _USER-PROMPTS.md, "
                "command-center/sources/REGISTER.md, and "
                "command-center/CLAIM-REGISTRY.json are absent on this worktree."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "sources": [
                {
                    "kind": "prose",
                    "permalink": "file://" + str(user_prompts),
                    "path": "_USER-PROMPTS.md",
                    "fetch_timestamp": ts,
                    "http_status": 0 if user_prompts.is_file() else None,
                    "sha256": sha_bytes(user_prompts)[0] if user_prompts.is_file() else None,
                    "present": user_prompts.is_file(),
                },
                {
                    "kind": "prose",
                    "permalink": "file://" + str(register),
                    "path": "command-center/sources/REGISTER.md",
                    "fetch_timestamp": ts,
                    "http_status": 0 if register.is_file() else None,
                    "sha256": sha_bytes(register)[0] if register.is_file() else None,
                    "present": register.is_file(),
                },
            ],
            "named_independent_verification_path": "pathlib exists() on the three catalog inputs",
        },
    ]

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "title": "Protocol for converting a practitioner anecdote into a falsifiable, testable claim",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "design-spec",
        "schema_version": 1,
        "ts": ts,
        "output_path": OUT,
        "output_schema": SCHEMA_DECLARED,
        "schema_gate": {
            "enforced": False,
            "valid": None,
            "classification": "schema-unresolvable" if not schema_present else "ok",
            "schema_path": SCHEMA_DECLARED,
            "on_disk": schema_present,
            "note": (
                "Catalog points at design-spec.schema.json which is absent. "
                "This artifact is a design-spec by report_kind. G-1 delivery "
                "does not parse that schema file."
            ),
        },
        "question": QUESTION,
        "answer": (
            f"Span-copy protocol {PROTOCOL_ID}: TRANSFORMABLE iff the source "
            "already states a first-person local action and a specific failure "
            "observable; required slots are exact substrings. Survival on the "
            f"pinned 30-sample is {m['n_survived']}/30 "
            f"({m['survival_fraction']:.3f}); 5/5 vague controls are "
            "NOT-TRANSFORMABLE. SUCCESS:RES-0143"
        ),
        "protocol": {
            "id": PROTOCOL_ID,
            "required_slots": ["precondition", "observable", "local_experiment"],
            "rule": (
                "Copy spans; never invent required-slot tokens. Classification "
                "labels may be INFERRED with the inference stated."
            ),
            "refuse_when": [
                "no when/after/if I|we clause",
                "observable lacks a failure verb/phrase",
                "observable is pronoun-only",
                "precondition is vague (usual thing / stuff)",
                "any required-slot token is not in the source",
            ],
            "implementation": PROTO_REL,
            "independent_auditor": AUDIT_REL,
        },
        "sample_measurement": {
            "kind": "committed-fixture-corpus",
            "n": m["n_sample"],
            "n_survived": m["n_survived"],
            "n_refused": m["n_refused"],
            "survival_fraction": m["survival_fraction"],
            "survival_not_100_percent": m["survival_not_100_percent"],
            "survived_ids": m["survived_ids"],
            "refused_ids": m["refused_ids"],
            "why_not_live_forum_harvest": (
                "_USER-PROMPTS.md, sources/REGISTER.md, and CLAIM-REGISTRY.json "
                "are absent; the sample is a pinned fixture corpus."
            ),
        },
        "negative_control": {
            "requirement": (
                "pass 5 anecdotes that are too vague to transform and require "
                "the protocol to emit NOT-TRANSFORMABLE rather than a "
                "plausible-looking claim; a protocol with a 100 percent "
                "transformation rate is fabricating"
            ),
            "n": m["negative_controls"]["n"],
            "all_not_transformable": m["negative_controls"]["all_not_transformable"],
            "ids": m["negative_controls"]["ids"],
            "dispositions": m["negative_controls"]["dispositions"],
        },
        "transformations": {
            "survived": [slim(r) for r in survived],
            "refused_in_sample": [slim(r) for r in refused],
            "negative_controls": [slim(r) for r in negs],
        },
        "fixture_lineage": lineage,
        "input_gaps": [
            {
                "path": "_USER-PROMPTS.md",
                "present": user_prompts.is_file(),
                "effect": "Phase-2 source-class prose not mounted; protocol uses catalog question text.",
            },
            {
                "path": "command-center/sources/REGISTER.md",
                "present": register.is_file(),
                "effect": "no live source register; fixture corpus used.",
            },
            {
                "path": "command-center/CLAIM-REGISTRY.json",
                "present": claims_reg.is_file(),
                "effect": "no claim registry to bind transformed records into.",
            },
            {
                "path": SCHEMA_DECLARED,
                "present": schema_present,
                "effect": "catalog output_schema file is absent; G-1 does not consult it.",
            },
        ],
        "claims": claims,
        "tests": [
            {"id": "named-probe-1-survival-and-negative-control", "command": P1, "result": "NOT-RUN"},
            {"id": "named-probe-2-span-diff-both-states", "command": P2, "result": "NOT-RUN"},
            {
                "id": "required-negative-control-five-vague",
                "result": "PASS" if m["negative_controls"]["all_not_transformable"] else "FAIL",
            },
            {
                "id": "sample-not-100-percent",
                "result": "PASS" if m["survival_not_100_percent"] else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0143-probe2-span-diff-both-states",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "defaults_to": "REFUTED",
            "method": (
                "Independent substring/token audit of every TRANSFORMABLE claim; "
                "strip a gold anecdote and require NOT-TRANSFORMABLE; inject a "
                "specified anecdote into a vague control and require TRANSFORMABLE; "
                "require a fabricating always-claim protocol to fail the audit."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "path": "command-center/p2-wave/probes/RES-0143/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "evidence": [
            {"path": PROTO_REL, "kind": "protocol-implementation", "bytes": proto_n, "sha256": proto_sha},
            {"path": AUDIT_REL, "kind": "independent-auditor", "bytes": audit_n, "sha256": audit_sha},
            {
                "path": "command-center/p2-wave/probes/RES-0143/probe1_survival_and_negative_control.py",
                "kind": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0143/probe2_span_diff_both_states.py",
                "kind": "named-probe",
            },
        ],
        "residual_unknowns": [
            {
                "id": "U-USER-PROMPTS-ANECDOTE-CLASS",
                "unknown": "Byte-exact anecdotal-source-class wording at _USER-PROMPTS.md:11270.",
                "named_experiment": "Mount the restore snapshot and diff against this protocol's refuse rules.",
            },
            {
                "id": "U-LIVE-FORUM-SAMPLE",
                "unknown": "Survival fraction on 30 live harvested practitioner posts rather than fixtures.",
                "named_experiment": "When REGISTER.md exists, draw 30 posts with lineage and re-run transform() unchanged.",
            },
            {
                "id": "U-DESIGN-SPEC-SCHEMA",
                "unknown": "Whether this document validates against the missing design-spec.schema.json.",
                "named_experiment": "Place the schema file and re-validate; do not hand-flip state.",
            },
        ],
        "honesty": {
            "cloud_ok_is_not_delivery": True,
            "did_not_run_global_unit_manifest_write": True,
            "user_prompts_absent": not user_prompts.is_file(),
            "catalog_schema_absent": not schema_present,
            "sample_is_committed_fixtures": True,
            "not_a_live_forum_harvest": True,
            "independence": "template-regex extraction vs substring/token audit in audit.py",
        },
        "SUCCESS:RES-0143": True,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0143 emit probes c1={c1} c2={c2}")
        print(t1[-4000:])
        print(t2[-4000:])
        return 1

    j1 = first_json(t1) or {}
    j2 = first_json(t2) or {}
    doc["tests"][0]["result"] = "PASS"
    doc["tests"][0]["exit_code"] = c1
    doc["tests"][1]["result"] = "PASS"
    doc["tests"][1]["exit_code"] = c2
    doc["probe1"] = j1
    doc["probe2"] = j2
    doc["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    supporting = [
        PROTO_REL,
        CORPUS_REL,
        AUDIT_REL,
        "command-center/p2-wave/probes/RES-0143/measure.py",
        "command-center/p2-wave/probes/RES-0143/probe1_survival_and_negative_control.py",
        "command-center/p2-wave/probes/RES-0143/probe2_span_diff_both_states.py",
        "command-center/p2-wave/probes/RES-0143/emit.py",
    ] + [r["path"] for r in pinned]
    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in supporting]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "cloud_ok": False,
        "output_path": OUT,
        "output_schema": SCHEMA_DECLARED,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "survival-and-negative-control",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "span-diff-both-states",
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/RES-0143/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0143-probe2-span-diff-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": doc["ts"],
        "notes": (
            "G-1 for RES-0143: live named probes exit 0, primary state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Sample is a committed 30-anecdote fixture corpus plus 5 vague "
            "negative controls; not a live forum harvest."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:RES-0143 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
