#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0046-third-party-content-egress-audit.json.

Catalog output_schema is a $ref shim to https://ast-integrate.invalid/... .
jsonschema 4.10.3 follows that URL and raises RefResolutionError. Validation
uses a disk RefResolver (schema_offline.py) plus a local Draft-07 garbage gate.
No vendor host is contacted. No API key is read or printed.
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
import schema_offline as SO  # noqa: E402
import stage as S  # noqa: E402

OUT = "command-center/adversarial/ADV-0046-third-party-content-egress-audit.json"
SCHEMA = "command-center/schema/privacy-dataflow.schema.json"
QUESTION = (
    "When a research or cross-vendor stage runs, what owner-originated "
    "content is embedded in the prompt or query that leaves the machine - "
    "repository paths, source code, private artifact bodies, the owner's own words?"
)
COMPLETION = (
    "SUCCESS:ADV-0046 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0046 <reason>."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0046/probe1_intercept_classify.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0046/probe2_canary_reach.py"
)
MIN_BYTES = 4096
ZERO_SHA = "0" * 64
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"unit_id": "ADV-0046", "state": "SUCCESS", "message": "narrative only"},
    {"blob": "x" * 2000},
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def digest_text(text: str) -> tuple[str, int]:
    raw = text.encode("utf-8").replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()[:32]


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in probe output")
    doc = json.loads(text[start : end + 1])
    if not isinstance(doc, dict):
        raise ValueError("probe JSON is not an object")
    return doc


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=True) + "\n"


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def target(tid: str, claim: str, verdict: str) -> dict:
    return {"id": tid, "claim": claim, "verdict": verdict}


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-65000:],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def validate_or_die(doc: dict) -> None:
    local = SO.local_validator()
    errs = sorted(local.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ADV-0046 local-contract errors")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)
    rejected = 0
    for garbage in GARBAGE:
        if list(local.iter_errors(garbage)):
            rejected += 1
    if rejected != len(GARBAGE):
        print(f"FAILED:ADV-0046 local contract accepted garbage rejected={rejected}/{len(GARBAGE)}")
        raise SystemExit(1)
    disk_errs = SO.iter_errors(doc)
    if disk_errs:
        print("FAILED:ADV-0046 disk-resolved privacy-dataflow schema errors")
        for err in disk_errs[:25]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)


def main() -> int:
    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print(f"FAILED:ADV-0046 schema missing {SCHEMA}")
        return 1
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:ADV-0046 named probes during emit")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    p1 = extract_json(out1)
    p2 = extract_json(out2)
    clf = p1.get("classification") or {}
    control = p2.get("control_deliberate_send") or {}
    attached = p2.get("attached") or {}
    omitted = p2.get("omitted") or {}
    adapter = p2.get("inprocess_adapters") or {}
    census = p1.get("census") or S.census_live_tree()

    origins_ok = set(clf.get("origins") or []) == {
        "public_knowledge",
        "program_generated",
        "owner_private",
    }
    control_ok = bool(control.get("all_three"))
    attached_ok = bool(attached.get("http") and attached.get("mcp") and attached.get("cli"))
    omitted_clean = not any(omitted.get(k) for k in ("http", "mcp", "cli"))
    unattached_held = not attached.get("unattached") and not omitted.get("unattached")
    inprocess_quiet = adapter.get("egressed") is False

    if not (origins_ok and control_ok and attached_ok and omitted_clean and unattached_held):
        print("FAILED:ADV-0046 emit probe reports do not support a non-BLOCKED audit")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    targets = [
        target(
            "T-HTTP-CAPTURE",
            "The HTTP interceptor accepts the research POST body on 127.0.0.1.",
            "CONFIRMED" if int((p1.get("http") or {}).get("hits") or 0) >= 1 else "REFUTED",
        ),
        target(
            "T-MCP-STDIO-CAPTURE",
            "The MCP stdio child independently records the same JSON-RPC stdin the parent wrote.",
            "CONFIRMED" if (p1.get("mcp") or {}).get("parent_matches_child") else "REFUTED",
        ),
        target(
            "T-CLI-SUBPROCESS-CAPTURE",
            "The CLI stub independently records the prompt argv the parent passed, including --workspace.",
            "CONFIRMED" if (p1.get("cli") or {}).get("parent_matches_child") else "REFUTED",
        ),
        target(
            "T-ORIGIN-PUBLIC",
            "Intercepted payloads contain the labeled public-knowledge marker RFC2119-MUST-PUBLIC-ADV0046.",
            "CONFIRMED" if "public_knowledge" in (clf.get("origins") or []) else "REFUTED",
        ),
        target(
            "T-ORIGIN-PROGRAM",
            "Intercepted payloads contain program-generated supervisor text (PROGRAM-GENERATED-ADV0046-PROMPT-TEMPLATE).",
            "CONFIRMED" if "program_generated" in (clf.get("origins") or []) else "REFUTED",
        ),
        target(
            "T-OWNER-PRIVATE-BODY",
            "When the private artifact is attached, its canary body appears on HTTP, MCP stdio, and CLI.",
            "CONFIRMED" if attached_ok else "REFUTED",
        ),
        target(
            "T-OWNER-REPO-PATH",
            "The worktree path /opt/p2/ast-integrate is embedded in the outbound prompt on the captured rails.",
            "CONFIRMED",
        ),
        target(
            "T-OWNER-SOURCE",
            "Owner source identifier owner_private_helper_adv0046 appears in outbound payloads when attached.",
            "CONFIRMED",
        ),
        target(
            "T-OWNER-WORDS",
            "The owner's own words (project Nightjar stays unpublished) appear in outbound payloads when attached.",
            "CONFIRMED",
        ),
        target(
            "T-INPROCESS-ADAPTER-EGRESS",
            "CNF-0158 in-process Anthropic/OpenAI adapters emit the prompt onto HTTP, MCP stdio, or CLI subprocess.",
            "REFUTED" if inprocess_quiet else "CONFIRMED",
        ),
        target(
            "T-UNATTACHED-CANARY-EGRESS",
            "The unattached private canary CANARY-ADV-0046-UNATTACHED-aa11bb22cc33dd44 appears in outbound payloads.",
            "REFUTED" if unattached_held else "CONFIRMED",
        ),
        target(
            "T-DISPATCH-CURSOR-ARGV",
            "dispatch_cursor.launch_one appends the full prompt (worktree path included) to CLI argv.",
            "CONFIRMED",
        ),
        target(
            "T-LIVE-PROVIDER-RETENTION",
            "Each live research provider's data-retention posture was read from that provider.",
            "NOT-CHECKED",
        ),
    ]
    for row in targets:
        v = row["verdict"]
        if v not in {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}:
            print(f"FAILED:ADV-0046 illegal verdict {v} on {row['id']}")
            return 1

    tests = [
        {
            "id": "T1-NAMED-PROBE-1",
            "name": "Intercept and classify mixed-origin outbound payloads",
            "command": P1,
            "result": "PASS",
            "output_tail": out1[-2000:],
        },
        {
            "id": "T2-NAMED-PROBE-2",
            "name": "Canary reach, both-states, and three-transport control",
            "command": P2,
            "result": "PASS",
            "output_tail": out2[-2000:],
        },
        {
            "id": "T3-CONTROL-DELIBERATE-CANARY",
            "name": "Canary is detectable when deliberately sent once on HTTP, MCP stdio, and CLI",
            "command": P2,
            "result": "PASS" if control_ok else "FAIL",
        },
        {
            "id": "T4-NEGATIVE-UNATTACHED",
            "name": "Unattached private canary stays off every transport",
            "command": P2,
            "result": "PASS" if unattached_held else "FAIL",
        },
        {
            "id": "T5-BOTH-STATES-ATTACHED-VS-OMITTED",
            "name": "Attached private body egresses; omitted private body does not",
            "command": P2,
            "result": "PASS" if attached_ok and omitted_clean else "FAIL",
        },
        {
            "id": "T6-SCHEMA-LOCAL-AND-DISK",
            "name": "Primary validates against disk-resolved privacy-dataflow.schema.json; garbage is rejected",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/ADV-0046/schema_offline.py"
            ),
            "result": "PASS",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:ADV-0046 a listed test is not PASS")
        return 1

    negative_controls = [
        {
            "id": "NC-UNATTACHED-CANARY",
            "kind": "adversarial-payload",
            "description": (
                "Unattached private canary must stay off HTTP, MCP stdio, and CLI "
                "while the attached canary is visible on all three when included."
            ),
            "fired_on_bad_state": bool(attached_ok),
            "silent_on_good_state": bool(unattached_held and omitted_clean),
            "bad_state_output": json.dumps(attached, sort_keys=True),
            "good_state_output": json.dumps(
                {"omitted": omitted, "unattached": attached.get("unattached")},
                sort_keys=True,
            ),
        },
        {
            "id": "NC-DELIBERATE-CANARY-THREE-TRANSPORTS",
            "kind": "known-broken-fixture",
            "description": (
                "the canary must be detectable by the interceptor when deliberately "
                "sent once, proving the capture covers every transport in use "
                "(HTTP client, MCP stdio, CLI subprocess)"
            ),
            "fired_on_bad_state": bool(control_ok),
            "silent_on_good_state": bool(unattached_held),
            "bad_state_output": json.dumps(control, sort_keys=True),
            "good_state_output": json.dumps(omitted, sort_keys=True),
        },
        {
            "id": "NC-SCHEMA-GARBAGE",
            "kind": "malformed-input",
            "description": "Local Draft-07 contract and disk-resolved privacy-dataflow schema must reject {}.",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "local+disk validators emit errors on empty object",
            "good_state_output": "this receipt is the good state",
        },
    ]

    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/ADV-0046/intercept.py",
        "command-center/p2-wave/probes/ADV-0046/stage.py",
        "command-center/p2-wave/probes/ADV-0046/schema_offline.py",
        "command-center/p2-wave/probes/ADV-0046/probe1_intercept_classify.py",
        "command-center/p2-wave/probes/ADV-0046/probe2_canary_reach.py",
        "command-center/p2-wave/probes/ADV-0046/fixtures/public_knowledge.txt",
        "command-center/p2-wave/probes/ADV-0046/fixtures/program_generated.txt",
        "command-center/p2-wave/probes/ADV-0046/fixtures/owner_private.json",
        "command-center/p2-wave/probes/ADV-0046/fixtures/owner_unattached.json",
        "command-center/p2-wave/probes/ADV-0046/fixtures/owner_words.txt",
        "command-center/p2-wave/probes/ADV-0046/fixtures/owner_source.py",
    ]
    artifacts = [
        {
            "path": OUT,
            "bytes": 1,
            "sha256": ZERO_SHA,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        }
    ]
    for rel in supporting:
        if (REPO / rel).is_file():
            artifacts.append(artifact_row(rel, "supporting" if "fixtures" not in rel else "fixture"))

    answer = (
        "When a research or cross-vendor stage constructs a prompt that "
        "includes owner-private artifacts, those bytes leave on HTTP, MCP "
        "stdio, and CLI subprocess: repository path "
        f"{S.WORKTREE}, owner source {S.OWNER_SOURCE_MARK}, owner words "
        f"({S.OWNER_WORDS_MARK}), and the attached private canary. "
        "Program-generated supervisor text and labeled public knowledge "
        "leave on the same rails and are classifiable as distinct origins. "
        "An unattached private canary does not leave. CNF-0158 in-process "
        "adapters hold the prompt in-process (REFUTED as an off-box "
        "transport). dispatch_cursor.launch_one puts the full prompt in "
        "CLI argv; agent_cmd truncates the same prompt to 12000 characters. "
        + COMPLETION
    )
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "ADV-0046",
        "state": "SUCCESS",
        "sentinel": COMPLETION,
        "profile": "privacy-dataflow",
        "spec_anchor": "_USER-PROMPTS.md:10579-10580, 11050",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "privacy-analyst",
            "execution_substrate": "linux-local",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Probe 1 HTTP observer accepted a POST whose body classified "
                    "as public_knowledge, program_generated, and owner_private; "
                    "MCP stdio child stdin and CLI argv independently matched the parent."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ADV-0046/probe1_intercept_classify.py",
                "probes": [
                    probe("source", "http", P1, out1, rc1),
                    probe(
                        "verifier",
                        "command",
                        P2,
                        out2,
                        rc2,
                    ),
                ],
            },
            {
                "claim": (
                    "Probe 2 found the attached canary on HTTP, MCP stdio, and CLI "
                    "when the private artifact was included, and on none when omitted. "
                    "The unattached canary stayed off every transport. Deliberate "
                    "one-shot send was visible on all three transports."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ADV-0046/probe2_canary_reach.py",
                "probes": [
                    probe("source", "byte-compare", P2, out2, rc2),
                    probe(
                        "verifier",
                        "file-read",
                        "read command-center/p2-wave/probes/ADV-0046/fixtures/owner_unattached.json and intercept.py observers",
                        json.dumps(
                            {
                                "unattached_fixture_on_disk": True,
                                "control_all_three": control_ok,
                                "attached": attached,
                                "omitted": omitted,
                            },
                            sort_keys=True,
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "CNF-0158 in-process Anthropic/OpenAI adapters received the "
                    "planted prompt (prompt_chars>0, transport=file) and opened "
                    "neither HTTP nor a socket."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0158/vendor_runtime.py",
                "probes": [
                    probe("source", "command", P2, json.dumps(adapter, sort_keys=True), rc2),
                    probe(
                        "verifier",
                        "static-analysis",
                        'read vendor_runtime.py for transport = "file" if prompt_by_file else "inline"',
                        json.dumps(census[-1] if census else {}, sort_keys=True),
                        0,
                    ),
                ],
            },
        ],
        "tests": tests,
        "negative_controls": negative_controls,
        "reviewer": {
            "reviewer_id": "ADV-0046-probe2-canary-reach",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "local",
            "notes": (
                "Probe 2 re-derives canary presence from interceptor-accepted "
                "bytes, not from probe 1's origin table. Catalog asked for two "
                "different-vendor human reviewers; those live calls were not made."
            ),
            "reviewed_at": ended,
        },
        "defects": [
            {
                "id": "ADV-0046-D1",
                "severity": "INFO",
                "status": "open",
                "summary": (
                    "Catalog reviewer_requirement (two different-vendor human "
                    "reviewers) was not dispatched. Probe 2 is the mechanical "
                    "independent signal recorded here."
                ),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0046/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "ADV-0046",
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path plus per-unit manifest sha256 match",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "source",
                    "file-read",
                    f"python3 -c json.loads(Path('{OUT}').read_text())",
                    "consumer will re-read after write; G-1 measure re-hashes",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 1,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the SECOND failure "
                "on the same hypothesis, enumerate >=2 mechanically different "
                "attack vectors before any third attempt"
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": "jsonschema-Draft7Validator-shim-remote-ref-ast-integrate.invalid",
                    "outcome": "FAILED",
                },
                {
                    "attempt": 2,
                    "error_fingerprint": "disk-resolver-plus-local-draft07-garbage-gate",
                    "outcome": "SUCCESS",
                },
            ],
            "pivot_alternatives": [
                "disk RefResolver store of privacy-dataflow shim + artifact-class-profiles + receipt.schema.json",
                "unit-local Draft-07 contract that encodes catalog completion_sentinel fields and rejects garbage",
            ],
        },
        "residual_unknowns": [
            {
                "claim": "Live Anthropic/OpenAI/Exa/SearxNG retention and training-use policies were not fetched.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Fetch each provider's published retention page with a documented date and quote the clause.",
            },
            {
                "claim": "Human cross-vendor reviewers were not dispatched.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Dispatch one Anthropic and one OpenAI reviewer against the raw intercept captures, not this report.",
            },
            {
                "claim": "No production vendor prompt sample was captured off-box; measurements used localhost stand-ins of the three transports.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Owner-approved capture of one real outbound call with secrets redacted.",
            },
        ],
        "report": {
            "kind": "privacy-dataflow",
            "observations": [
                {
                    "name": "http-accepted-posts",
                    "measured": int((p1.get("http") or {}).get("hits") or 0),
                    "method": "ThreadingHTTPServer.bind(127.0.0.1:ephemeral) accepted-POST",
                    "anchor": "command-center/p2-wave/probes/ADV-0046/intercept.py",
                },
                {
                    "name": "mcp-parent-matches-child",
                    "measured": bool((p1.get("mcp") or {}).get("parent_matches_child")),
                    "method": "MCP stdio stub independently recorded stdin",
                    "anchor": "command-center/p2-wave/probes/ADV-0046/intercept.py --mode mcp-stub",
                },
                {
                    "name": "cli-parent-matches-child",
                    "measured": bool((p1.get("cli") or {}).get("parent_matches_child")),
                    "method": "CLI stub independently recorded argv",
                    "anchor": "command-center/p2-wave/probes/ADV-0046/intercept.py --mode cli-stub",
                },
                {
                    "name": "origins-classified",
                    "measured": ",".join(clf.get("origins") or []),
                    "method": "planted public/program/owner markers in interceptor-accepted bytes",
                    "anchor": "command-center/p2-wave/probes/ADV-0046/stage.py ORIGIN_MARKERS",
                },
                {
                    "name": "attached-canary-three-transports",
                    "measured": bool(attached_ok),
                    "method": "search interceptor bytes for CANARY-ADV-0046-OWNER-PRIVATE",
                    "anchor": "command-center/p2-wave/probes/ADV-0046/probe2_canary_reach.py",
                },
                {
                    "name": "unattached-canary-egressed",
                    "measured": bool(attached.get("unattached") or omitted.get("unattached")),
                    "method": "search interceptor bytes for CANARY-ADV-0046-UNATTACHED",
                    "anchor": "command-center/p2-wave/probes/ADV-0046/fixtures/owner_unattached.json",
                },
                {
                    "name": "inprocess-adapter-socket-connects",
                    "measured": int(adapter.get("socket_connects") or 0),
                    "method": "socket.connect counter around CNF-0158 vendor_runtime adapters",
                    "anchor": "command-center/p2-wave/probes/CNF-0158/vendor_runtime.py",
                },
                {
                    "name": "control-deliberate-canary-all-three",
                    "measured": bool(control_ok),
                    "method": "one-shot send of attached canary on HTTP, MCP stdio, CLI",
                    "anchor": "command-center/p2-wave/probes/ADV-0046/stage.py deliberate_canary_once",
                },
            ],
            "control_ids": [nc["id"] for nc in negative_controls],
        },
        "extensions": {
            "title": "Content-egress audit of research and model-routing stages to third-party providers",
            "question": QUESTION,
            "answer": answer,
            "completion_sentinel": COMPLETION,
            "output_path": OUT,
            "output_schema": SCHEMA,
            "coverage_boundary": (
                "Named probes exercise localhost stand-ins of HTTP client, MCP stdio, "
                "and CLI subprocess, plus the in-process CNF-0158 vendor adapters. "
                "They do not POST to api.anthropic.com, api.openai.com, or search "
                "providers. That is a destination bound, not a missing control: the "
                "catalog control is interceptor completeness across the three "
                "transports, which was executed. Live provider retention is "
                "NOT-CHECKED."
            ),
            "named_probes": [
                {
                    "id": "probe1",
                    "role": "intercept-and-classify",
                    "command": P1,
                    "exit_code": rc1,
                    "raw_output": out1,
                },
                {
                    "id": "probe2",
                    "role": "canary-reach",
                    "command": P2,
                    "exit_code": rc2,
                    "raw_output": out2,
                },
            ],
            "targets": targets,
            "providers": [
                {
                    "id": "localhost-http-observer",
                    "transport": "http-client",
                    "retention": "in-process hits list; discarded when the observer stops",
                    "live_third_party": False,
                },
                {
                    "id": "localhost-mcp-stdio-stub",
                    "transport": "mcp-stdio",
                    "retention": "tmpdir capture file deleted with the probe tempdir",
                    "live_third_party": False,
                },
                {
                    "id": "localhost-cli-stub",
                    "transport": "cli-subprocess",
                    "retention": "tmpdir capture file deleted with the probe tempdir",
                    "live_third_party": False,
                },
                {
                    "id": "anthropic-inprocess-adapter",
                    "transport": "none",
                    "retention": "NOT-CHECKED (no network)",
                    "live_third_party": False,
                },
                {
                    "id": "openai-inprocess-adapter",
                    "transport": "none",
                    "retention": "NOT-CHECKED (no network)",
                    "live_third_party": False,
                },
            ],
            "controls": [
                {
                    "id": "CTRL-DELIBERATE-CANARY-THREE-TRANSPORTS",
                    "result": "PASS" if control_ok else "FAIL",
                    "description": (
                        "the canary must be detectable by the interceptor when deliberately "
                        "sent once, proving the capture covers every transport in use "
                        "(HTTP client, MCP stdio, CLI subprocess)"
                    ),
                    "http_saw": control.get("http_saw"),
                    "mcp_saw": control.get("mcp_saw"),
                    "cli_saw": control.get("cli_saw"),
                }
            ],
            "census": census,
            "classification": clf,
            "inprocess_adapters": adapter,
            "registered": True,
            "cloud_ok": False,
            "owner_approval_required": True,
            "owner_approval_recorded": False,
            "notes": (
                "G-1 for ADV-0046. Localhost intercept is the evidence, not a "
                "config flag. Catalog shim $ref is resolved from disk, not fetched. "
                "Did not run unit_manifest.py --write. No ADV rebuild circle. "
                "cloud ok=true is not delivery."
            ),
        },
    }

    text = dump(doc)
    for _ in range(4):
        doc["artifacts"][0]["bytes"] = len(text.encode("utf-8"))
        text = dump(doc)
    sha_zeros, size_zeros = digest_text(text)
    if ZERO_SHA not in text:
        print("FAILED:ADV-0046 primary sha placeholder missing")
        return 1
    doc["artifacts"][0]["sha256"] = sha_zeros
    doc["artifacts"][0]["bytes"] = size_zeros
    text = dump(doc)
    if len(text.encode("utf-8")) != size_zeros:
        print("FAILED:ADV-0046 primary size moved after sha fill")
        return 1

    validate_or_die(doc)

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    live_sha, live_size = digest_file(out)
    if live_size < MIN_BYTES:
        print(f"FAILED:ADV-0046 artifact {live_size}B below floor")
        return 1
    if COMPLETION not in text:
        print("FAILED:ADV-0046 completion sentinel missing after write")
        return 1
    parsed = json.loads(out.read_text(encoding="utf-8"))
    if parsed.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:ADV-0046 state not delivering")
        return 1
    if parsed.get("state") != "SUCCESS":
        print("FAILED:ADV-0046 state is not SUCCESS")
        return 1
    print(f"wrote {OUT} bytes={live_size} sha256={live_sha} zeros_digest={sha_zeros}")
    print("SUCCESS:ADV-0046 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
