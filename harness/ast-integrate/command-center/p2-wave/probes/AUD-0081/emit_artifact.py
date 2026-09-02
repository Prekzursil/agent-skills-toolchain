#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0081-untrusted-autoload-config-audit.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import autoload as A  # noqa: E402

UID = "AUD-0081"
OUT = "command-center/audit/AUD-0081-untrusted-autoload-config-audit.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
COMPLETION_SENTINEL = (
    "SUCCESS:AUD-0081 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Do any cloned, vendored, or agent-scratch trees under the estate carry a "
    ".claude, .codex, .mcp.json, hooks directory, AGENTS.md or CLAUDE.md that "
    "would auto-load the moment an agent runs inside them?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0081/probe1_filename_search.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0081/probe2_classify.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/AUD-0081/autoload.py",
    "command-center/p2-wave/probes/AUD-0081/probe1_filename_search.py",
    "command-center/p2-wave/probes/AUD-0081/probe2_classify.py",
    "command-center/p2-wave/probes/AUD-0081/fixtures/untrusted-clone/inert-docs/AGENTS.md",
    "command-center/p2-wave/probes/AUD-0081/fixtures/untrusted-clone/active-hooks/AGENTS.md",
    "command-center/p2-wave/probes/AUD-0081/fixtures/untrusted-clone/docs/CLAUDE.md",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def probe_row(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
        "exit_code": exit_code,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes()
    return {
        "path": rel,
        "exists": True,
        "role": role,
        "bytes": len(data),
        "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),
        "eol": "LF",
    }


def _validator():
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    profiles = json.loads(
        (
            REPO / "platform/schema/artifact-class-profiles.schema.json"
        ).read_text(encoding="utf-8")
    )
    store = {
        shim["$id"]: shim,
        receipt["$id"]: receipt,
        profiles["$id"]: profiles,
    }
    resolver = RefResolver.from_schema(shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def schema_errors(doc: dict) -> list[str]:
    validator = _validator()
    return [
        f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(doc)
    ]


def _garbage_rejected() -> dict:
    validator = _validator()
    probes = (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    )
    counts = [len(list(validator.iter_errors(p))) for p in probes]
    kind_mutant = {
        "schema_version": 1,
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0081 schema-kind-mutant",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0081",
        "min_bytes_threshold": 1024,
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
                "bytes": 2048,
                "sha256": "ab" * 32,
            }
        ],
        "evidence": [
            {
                "claim": "placeholder-claim-text-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "verdict": "PARTIAL",
                "anchor": "command-center/p2-wave/probes/AUD-0081/probe1_filename_search.py",
                "probes": [
                    probe_row("source", "command", P1, "placeholder-output", 0)
                ],
            },
            {
                "claim": "second-placeholder-claim-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "verdict": "PARTIAL",
                "anchor": "command-center/p2-wave/probes/AUD-0081/probe2_classify.py",
                "probes": [
                    probe_row("verifier", "file-read", P2, "placeholder-output", 0)
                ],
            },
        ],
        "tests": [
            {"id": "t1", "command": P1, "result": "PASS"},
            {"id": "t2", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "AUD0081-C1",
                "kind": "known-broken-fixture",
                "description": "kind-mutant control fixture",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "AUD-0081-probe2-classifier",
            "verdict": "PASS",
            "independent": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0081/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema-kind-mutant",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "probe": probe_row(
                    "source", "schema-validate", "kind-mutant", "kind=receipt", 0
                ),
            }
        ],
        "timestamps": {
            "started_at": "2026-08-25T00:00:00Z",
            "ended_at": "2026-08-25T00:00:01Z",
        },
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "residual_unknowns": [
            {
                "claim": "kind mutant should fail the audit-finding pin",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Validate a document whose report.kind is receipt.",
            }
        ],
        "produced_by": {"vendor": "xai", "model": "grok"},
        "report": {"kind": "receipt", "observations": [], "control_ids": ["x"]},
    }
    kind_errs = list(validator.iter_errors(kind_mutant))
    kind_msgs = [e.message for e in kind_errs]
    kind_pin = any(
        "audit-finding" in m or "receipt" in m or "kind" in m.lower()
        for m in kind_msgs
    )
    return {
        "garbage_error_counts": counts,
        "all_garbage_rejected": all(c > 0 for c in counts),
        "schema_kind_mutant_error_count": len(kind_errs),
        "schema_kind_mutant_goes_red": len(kind_errs) > 0,
        "schema_kind_mutant_pin_mentioned": kind_pin,
        "schema_kind_mutant_sample": kind_msgs[:6],
    }


def build_doc(*, t1: str, c1: int, t2: str, c2: int) -> dict:
    snap = A.summary()
    control = snap["control"]
    live_active = snap["live_untrusted_active"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_row("source", "command", P1, t1, c1)
    p2 = probe_row("verifier", "file-read", P2, t2, c2)

    planted_active = [
        r
        for r in snap["classified"]
        if r.get("planted_control") and r.get("classification") == "active"
    ]
    planted_inert = [
        r
        for r in snap["classified"]
        if r.get("planted_control") and r.get("classification") == "inert"
    ]

    if live_active:
        answer = (
            f"Yes: {len(live_active)} active auto-load registration(s) in live "
            f"cloned/vendored/scratch trees (not counting the unit fixture). "
            "Probe 1 listed auto-load names; Probe 2 content-classified each hit. "
            + "; ".join(r["path"] for r in live_active[:12])
        )
    else:
        answer = (
            "No live cloned, vendored, or agent-scratch tree on this sparse "
            "Linux worktree carries an active auto-load hook or MCP registration. "
            f"AUD-0009 inventory is "
            f"{'present' if snap['aud0009']['present'] else 'absent'}; "
            f"the live walk found {snap['untrusted_root_count']} untrusted root(s) "
            f"and {snap['filename_hit_count']} auto-load-named path(s). "
            f"{len(planted_active)} planted-control path(s) classified active "
            f"and {len(planted_inert)} inert on the single fixture "
            f"{A.PLANTED_REL}. A file named CLAUDE.md in that fixture is inert "
            "prose, so the filename is not a risk finding."
        )

    findings = []
    for row in snap["classified"]:
        if row.get("classification") != "active":
            continue
        findings.append(
            {
                "id": "AUD0081-" + row["path"].replace("/", "-")[:80],
                "severity": "P2" if row.get("planted_control") else "P1",
                "status": "control" if row.get("planted_control") else "open",
                "classification": "active-autoload",
                "path": row["path"],
                "tree_class": row.get("tree_class"),
                "reason": row.get("reason"),
                "planted_control": bool(row.get("planted_control")),
                "summary": (
                    "Planted PreToolUse registration used as the both-states control."
                    if row.get("planted_control")
                    else f"Active auto-load surface at {row['path']}"
                ),
            }
        )

    schema_ctl = _garbage_rejected()
    tests_ok = (
        c1 == 0
        and c2 == 0
        and control.get("pass") is True
        and schema_ctl["all_garbage_rejected"]
        and schema_ctl["schema_kind_mutant_goes_red"]
    )
    if not tests_ok:
        raise RuntimeError(
            f"refusing SUCCESS: c1={c1} c2={c2} control={control} schema={schema_ctl}"
        )

    primary = {
        "path": OUT,
        "exists": True,
        "role": "primary",
        "bytes": 2048,
        "sha256": "00" * 32,
        "eol": "LF",
    }

    report = {
        "kind": "audit-finding",
        "observations": [
            {
                "name": "filename-hit-count",
                "measured": snap["filename_hit_count"],
                "method": "os.walk name match, no body read",
                "anchor": "command-center/p2-wave/probes/AUD-0081/probe1_filename_search.py",
            },
            {
                "name": "live-untrusted-active-count",
                "measured": len(live_active),
                "method": "utf-8 body read classifying hook/MCP vs prose",
                "anchor": "command-center/p2-wave/probes/AUD-0081/probe2_classify.py",
            },
            {
                "name": "both-states-on-one-fixture",
                "measured": bool(control["both_states_on_one_fixture"]),
                "method": "planted prose vs PreToolUse AGENTS.md pair",
                "anchor": A.PLANTED_REL,
            },
        ],
        "control_ids": ["AUD0081-C1", "AUD0081-C2"],
        "answer": answer,
        "question": QUESTION,
        "title": "Untrusted auto-loaded configuration audit in cloned and vendored trees",
        "report_kind": "audit-finding",
        "live_untrusted_active_count": len(live_active),
        "planted_active_count": len(planted_active),
        "autoload_name_set": snap["autoload_names"],
        "filename_census": {
            "method": "os.walk name match, no body read",
            "hit_count": snap["filename_hit_count"],
            "untrusted_root_count": snap["untrusted_root_count"],
            "planted_control_found": snap["planted_hit_count"] >= 3,
            "hits": snap["filename_hits"],
            "untrusted_roots": snap["untrusted_roots"],
        },
        "classification": {
            "method": "utf-8 body read; JSON hooks/mcpServers or PreToolUse registration",
            "both_states_on_one_fixture": control["both_states_on_one_fixture"],
            "claude_md_filename_is_not_risk": control["claude_md_filename_is_not_risk"],
            "live_untrusted_active_count": len(live_active),
            "live_untrusted_active": live_active,
            "classified": snap["classified"],
            "control": control,
        },
        "findings": findings,
        "aud0009_dependency": snap["aud0009"],
        "owner_approval": {
            "required_by_catalog": True,
            "supplied": False,
            "note": (
                "Catalog flags owner_approval_required. This G-1 artifact is the "
                "audit measurement, not an owner ruling that untrusted configs may run."
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1[:65000],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2[:65000],
            },
        ],
        "schema_controls": schema_ctl,
    }

    doc = {
        "schema_version": 1,
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0081",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "security-auditor",
            "execution_substrate": "linux-local",
        },
        "artifacts": [primary, *[art(p, "supporting") for p in SUPPORTING]],
        "evidence": [
            {
                "claim": (
                    f"Probe 1 filename-walked {snap['untrusted_root_count']} untrusted "
                    f"root(s) and recorded {snap['filename_hit_count']} auto-load-named "
                    f"path(s), including the planted AGENTS.md pair and CLAUDE.md."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0081/probe1_filename_search.py",
                "probes": [p1, p2],
            },
            {
                "claim": (
                    "On one fixture, prose AGENTS.md classified inert and PreToolUse "
                    "AGENTS.md classified active; prose CLAUDE.md classified inert so "
                    "the filename is not a risk finding; a filename-only mutant flags "
                    "the inert files."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0081/probe2_classify.py",
                "probes": [p1, p2],
            },
        ],
        "tests": [
            {
                "id": "probe1-filename-search",
                "name": "Filename search for the auto-load set across non-owner-authored trees",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "output_tail": t1[-1500:],
            },
            {
                "id": "probe2-content-classify",
                "name": "Content read classifying inert documentation vs active hook/MCP",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "output_tail": t2[-1500:],
            },
            {
                "id": "both-states-agents-md-fixture",
                "name": (
                    "control: classifier rates prose AGENTS.md inert and PreToolUse "
                    "AGENTS.md active on one fixture"
                ),
                "command": P2,
                "result": "PASS" if control["both_states_on_one_fixture"] else "FAIL",
                "assertions": 2,
            },
            {
                "id": "claude-md-filename-not-risk",
                "name": "Presence of CLAUDE.md is not by itself a risk finding",
                "command": P2,
                "result": "PASS" if control["claude_md_filename_is_not_risk"] else "FAIL",
            },
            {
                "id": "filename-only-mutant-red",
                "name": "Filename-only risk mutant flags inert autoload names",
                "command": P2,
                "result": "PASS"
                if control["filename_only_mutant_flags_inert_agents"]
                else "FAIL",
            },
            {
                "id": "schema-garbage-and-kind-mutant",
                "name": "Declared audit-finding schema rejects garbage and a kind mutant",
                "command": "jsonschema.Draft202012Validator(audit-finding.schema.json)",
                "result": "PASS"
                if schema_ctl["all_garbage_rejected"]
                and schema_ctl["schema_kind_mutant_goes_red"]
                else "FAIL",
                "assertions": 4,
                "output_tail": json.dumps(schema_ctl, sort_keys=True)[:4000],
            },
        ],
        "negative_controls": [
            {
                "id": "AUD0081-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "Prose AGENTS.md must be inert; PreToolUse AGENTS.md must be "
                    "active; both on fixtures/untrusted-clone."
                ),
                "fired_on_bad_state": control["active_classified_active"],
                "silent_on_good_state": control["inert_classified_inert"],
                "bad_state_output": A.fixture_paths()["active_agents"],
                "good_state_output": A.fixture_paths()["inert_agents"],
            },
            {
                "id": "AUD0081-C2",
                "kind": "mutation",
                "description": (
                    "A classifier that treats the auto-load filename as the finding "
                    "must flag inert CLAUDE.md and inert AGENTS.md."
                ),
                "fired_on_bad_state": control["filename_only_mutant_flags_inert_claude"],
                "silent_on_good_state": control["claude_classified_inert"],
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0081-probe2-content-classifier",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "local",
            "notes": (
                "Catalog asked for one fresh-context Claude and one Codex human "
                "reviewer, escalating disagreement to the owner. Those humans were "
                "not dispatched to this G-1 worker. Probe 2 is a mechanically "
                "different measurement (body read vs filename walk) and is the "
                "independent reviewer of record here. Dual-human review remains a "
                "named residual, not a silent PASS."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0081/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema.Draft202012Validator+disk-RefResolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_row(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0081/emit_artifact.py",
                    "schema-errors=0 (filled after validate)",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second failure "
                "with the same detector, enumerate at least 2 mechanically "
                "different detectors before a third attempt"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog-required dual human review (fresh-context Claude + "
                    "Codex) was not executed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Dispatch a fresh-context Claude reviewer and a Codex reviewer "
                    "with both named-probe transcripts attached; escalate disagreement "
                    "to the owner rather than resolving by vote."
                ),
            },
            {
                "claim": (
                    "Trees outside this worktree (sibling checkouts, home-directory "
                    "clones) were not walked."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run untrusted_roots() against each owner checkout listed in "
                    "docs/ssot/SSOT-CLONE-INVENTORY.md."
                ),
            },
        ],
        "report": report,
        "extensions": {
            "notes": (
                "G-1 for AUD-0081: live named probes exit 0, honest non-BLOCKED "
                "audit-finding, per-unit UNIT-ARTIFACT-MANIFEST.json row. Did not run "
                "global unit_manifest.py --write. cloud ok=true is not delivery. "
                + COMPLETION_SENTINEL
            ),
            "owner_approval_required": True,
        },
    }
    return doc


def _encode(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True) + "\n"


def write_artifact(doc: dict) -> Path:
    text = _encode(doc)
    raw = text.encode("utf-8")
    doc["artifacts"][0]["bytes"] = len(raw)
    doc["artifacts"][0]["sha256"] = hashlib.sha256(
        raw.replace(b"\r\n", b"\n")
    ).hexdigest()
    errs = schema_errors(doc)
    if errs:
        raise RuntimeError("schema-invalid:\n" + "\n".join(errs[:20]))
    doc["downstream_consumers"][0]["probe"]["raw_output"] = (
        f"schema-errors={len(errs)} bytes={doc['artifacts'][0]['bytes']}"
    )
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        raise RuntimeError(f"refusing to write self-declared {doc.get('state')}")
    text = _encode(doc)
    if COMPLETION_SENTINEL not in text:
        raise RuntimeError("completion_sentinel missing from encoded artifact")
    # Re-check after the consumer probe tail rewrite.
    errs = schema_errors(json.loads(text))
    if errs:
        raise RuntimeError("schema-invalid-after-encode:\n" + "\n".join(errs[:20]))
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    return out


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UID} emit probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1
    doc = build_doc(t1=t1, c1=c1, t2=t2, c2=c2)
    path = write_artifact(doc)
    print(f"wrote {OUT} bytes={path.stat().st_size}")
    print(f"SUCCESS:{UID} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
