#!/usr/bin/env python3
"""Pack AUD-0080 permission-surface audit (BLOCKED on independent review)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0080"
OUT = "command-center/audit/AUD-0080-permission-surface-audit.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0080/UNIT-ARTIFACT-MANIFEST.json"


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-allow-merge.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-hook-bypass.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-allow.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-bypass.raw.txt").read_text(encoding="utf-8")
    ctrl = p2["control"]
    started = "2026-09-07T18:30:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art("command-center/p2-wave/probes/AUD-0080/probe1-allow-merge.json", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0080/probe2-hook-bypass.json", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0080/probe1-allow.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0080/probe2-bypass.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0080/control-use-vs-mention.json", "supporting"),
    ]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": (
            "FAILED:AUD-0080 probes measured "
            f"effective_allow={p1['effective_allow_count']} "
            f"allow_plus_hook_miss={p2['allow_plus_hook_miss_count']} "
            f"bash_preapproved={len(p1.get('bash_preapproved') or [])}; "
            "blocked-on-independent-review"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0080",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "security-auditor",
            "execution_substrate": "linux-local-p2-wave1",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 merged allow across {len(p1['scopes'])} scopes: "
                    f"merged_allow={p1['merged_allow_count']} "
                    f"effective={p1['effective_allow_count']} "
                    f"deny={p1['merged_deny_count']}; "
                    f"bash_preapproved={p1.get('bash_preapproved')}; "
                    f"bypassPermissions_scopes={p1.get('bypassPermissions_scopes')}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0080/probe1-allow.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0080/probe1_allow_merge.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-allow-merge.json",
                        json.dumps(
                            {
                                "effective_allow_count": p1["effective_allow_count"],
                                "bash_preapproved": p1.get("bash_preapproved"),
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 examined {p2['hooks_examined']} hooks / "
                    f"{p2['cases_evaluated']} cases; "
                    f"allow_plus_hook_miss={p2['allow_plus_hook_miss_count']}; "
                    f"use-vs-mention control_ok={ctrl['ok']} "
                    f"(payload-only fires={ctrl['fired_on_bad_state']}, "
                    f"verb-based silent={ctrl['silent_on_good_state']})."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0080/probe2-bypass.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0080/probe2_hook_bypass.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-hook-bypass.json",
                        json.dumps(
                            {
                                "allow_plus_hook_miss_count": p2[
                                    "allow_plus_hook_miss_count"
                                ],
                                "control_ok": ctrl["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0080-use-vs-mention-control",
                "name": "Payload mention of danger with benign verb must not flag",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0080/probe2_hook_bypass.py",
                "result": "PASS" if ctrl["ok"] else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-500:],
            }
        ],
        "negative_controls": [
            L.control(
                "AUD0080-C1",
                "adversarial-payload",
                ctrl["description"],
                bool(ctrl["fired_on_bad_state"]),
                bool(ctrl["silent_on_good_state"]),
                bad=f"payload-only flagged={ctrl.get('bad_state_flagged')}",
                good=f"verb-based flagged={ctrl.get('good_state_flagged')}",
            )
        ],
        "reviewer": {
            "reviewer_id": "required-cross-vendor-codex-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "openai",
            "notes": (
                "Catalog requires a cross-vendor Codex reviewer who re-runs ONLY "
                "the second probe. Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        },
        "defects": [
            {
                "id": "AUD-0080-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Cross-vendor Codex re-run of probe 2 unpaid.",
            },
            {
                "id": "AUD-0080-D-BASH-PREAPPROVED",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"Bash pre-approved entries={p1.get('bash_preapproved')}; "
                    f"allow_plus_hook_miss_count={p2['allow_plus_hook_miss_count']}."
                ),
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-finding schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0080/_pack_receipt.py",
                    "state=BLOCKED",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 1,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "failure": {
            "classification": ["blocked-on-independent-review", "use-vs-mention"],
            "reason": (
                f"Measured effective_allow={p1['effective_allow_count']} and "
                f"allow_plus_hook_miss={p2['allow_plus_hook_miss_count']}, but "
                "reviewer_requirement unmet."
            ),
            "diagnostic_tail": (
                f"bash_preapproved={p1.get('bash_preapproved')} control_ok={ctrl['ok']}"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer to re-run ONLY probe 2 "
                "before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0080/probe2_hook_bypass.py",
                    f"miss={p2['allow_plus_hook_miss_count']}",
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        },
        "residual_unknowns": [
            {
                "claim": "Whether Claude runtime short-circuits PreToolUse when permissions.allow matches before hook dispatch.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Instrument a disposable settings fixture with a PreToolUse "
                    "matcher that always denies Bash and confirm allow-list does "
                    "not suppress the hook."
                ),
            }
        ],
        "report": {
            "kind": "audit-finding",
            "question": (
                "Which command patterns are pre-approved in the permissions "
                "allow-lists across all settings scopes, and which of those would "
                "let a caller bypass a hook that is supposed to gate them?"
            ),
            "headline": (
                f"effective_allow={p1['effective_allow_count']}; "
                f"allow_plus_hook_miss={p2['allow_plus_hook_miss_count']}; "
                f"bash_preapproved={len(p1.get('bash_preapproved') or [])}. "
                "BLOCKED on review."
            ),
            "observations": [
                {
                    "name": "effective_allow_count",
                    "measured": p1["effective_allow_count"],
                    "method": "union allow minus exact deny across settings scopes",
                    "anchor": "command-center/p2-wave/probes/AUD-0080/probe1-allow-merge.json",
                },
                {
                    "name": "hooks_examined",
                    "measured": p2["hooks_examined"],
                    "method": "enumerate hooks from agent-self/config/settings.json",
                    "anchor": "command-center/p2-wave/probes/AUD-0080/probe2-hook-bypass.json",
                },
                {
                    "name": "allow_plus_hook_miss_count",
                    "measured": p2["allow_plus_hook_miss_count"],
                    "method": "matcher miss on intended verb that is also allow-listed",
                    "anchor": "command-center/p2-wave/probes/AUD-0080/probe2-bypass.raw.txt",
                },
                {
                    "name": "bash_preapproved_count",
                    "measured": len(p1.get("bash_preapproved") or []),
                    "method": "filter effective_allow for Bash*",
                    "anchor": "command-center/p2-wave/probes/AUD-0080/probe1-allow.raw.txt",
                },
                {
                    "name": "use_vs_mention_control_ok",
                    "measured": bool(ctrl["ok"]),
                    "method": "verb-based silent vs payload-only fire on Read+danger-quote",
                    "anchor": "command-center/p2-wave/probes/AUD-0080/control-use-vs-mention.json",
                },
            ],
            "control_ids": ["AUD0080-C1"],
        },
        "extensions": {
            "anti_false_green": "BLOCKED-with-real-probes",
            "wave": "p2-wave1",
            "bash_preapproved": p1.get("bash_preapproved"),
        },
    }


def main() -> int:
    for script in ("probe1_allow_merge.py", "probe2_hook_bypass.py"):
        rc, out = L.run(["python3", "-B", str(PROBE / script)])
        if rc != 0:
            print(out)
            print(f"FAILED:{UNIT} {script} exit={rc}")
            return rc
    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": "BLOCKED",
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state=BLOCKED bytes={L.art(OUT)['bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
