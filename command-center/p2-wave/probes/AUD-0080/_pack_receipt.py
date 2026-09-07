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
    ctrl = json.loads((PROBE / "control-use-vs-mention.json").read_text(encoding="utf-8"))
    started = "2026-09-07T18:25:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    miss = p2["allow_plus_hook_miss_count"]
    bypass_scopes = p1.get("bypassPermissions_scopes") or []

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
        L.art("command-center/p2-wave/probes/AUD-0080/control-use-vs-mention.json", "control"),
        L.art("command-center/p2-wave/probes/AUD-0080/probe1-allow.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0080/probe2-bypass.raw.txt", "log"),
    ]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": (
            "FAILED:AUD-0080 allow-merge+hook-bypass probes measured permission surface; "
            f"effective_allow={p1['effective_allow_count']} allow_plus_hook_miss={miss}; "
            "blocked-on-independent-review"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0080",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "security-auditor",
            "execution_substrate": "linux-local-p2-loop",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 merged allow across scopes: effective_allow_count="
                    f"{p1['effective_allow_count']} bash_preapproved="
                    f"{len(p1.get('bash_preapproved') or [])} "
                    f"bypassPermissions_scopes={bypass_scopes}."
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
                                "bypassPermissions_scopes": bypass_scopes,
                                "ok": p1["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 evaluated {p2['cases_evaluated']} verb×matcher cases over "
                    f"{p2['hooks_examined']} hooks; allow_plus_hook_miss_count={miss}; "
                    f"use-vs-mention control ok={ctrl['ok']} (payload-dangerous, verb-benign not flagged)."
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
                        "python3 -c read control-use-vs-mention.json",
                        json.dumps(
                            {
                                "ok": ctrl["ok"],
                                "silent_on_good_state": ctrl["silent_on_good_state"],
                                "allow_plus_hook_miss_count": miss,
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
                "name": "payload-quoted danger with benign verb must NOT be flagged",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0080/probe2_hook_bypass.py",
                "result": "PASS" if ctrl["ok"] else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-400:],
            }
        ],
        "negative_controls": [
            L.control(
                "AUD0080-C1",
                "adversarial-payload",
                "Payload quotes dangerous string; verb is Read — must not flag as Bash bypass.",
                True,
                True,
                bad="payload-only scanner fires",
                good=f"verb-based silent={ctrl['silent_on_good_state']}",
            )
        ],
        "reviewer": {
            "reviewer_id": "required-cross-vendor-codex-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "openai",
            "notes": (
                "Catalog requires one cross-vendor Codex reviewer who re-runs ONLY probe 2. "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        },
        "defects": [
            {
                "id": "AUD-0080-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Cross-vendor Codex independent review unpaid.",
            },
            {
                "id": "AUD-0080-D-BYPASS-MODE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"defaultMode=bypassPermissions on scopes {bypass_scopes}; "
                    f"effective_allow={p1['effective_allow_count']}; "
                    f"allow_plus_hook_miss={miss}."
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
        "retry": {"count": 1, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "failure": {
            "classification": [
                "blocked-on-independent-review",
                "use-vs-mention",
                "scope-mismatch",
            ],
            "reason": (
                f"Measured effective_allow={p1['effective_allow_count']} and "
                f"allow_plus_hook_miss={miss}, but reviewer_requirement unmet."
            ),
            "diagnostic_tail": (
                f"bypassPermissions_scopes={bypass_scopes} "
                f"bash_preapproved={len(p1.get('bash_preapproved') or [])}"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer to re-run ONLY probe 2 "
                "and falsify the headline bypass count before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0080/probe2_hook_bypass.py",
                    f"allow_plus_hook_miss_count={miss}",
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
                "claim": "Live Claude session applies agent-self/config/settings.json as the active scope.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Probe ~/.claude/settings*.json on a Windows estate host.",
            }
        ],
        "report": {
            "kind": "audit-finding",
            "question": (
                "Which command patterns are pre-approved in permissions allow-lists, and which "
                "would let a caller bypass a hook that is supposed to gate them?"
            ),
            "headline": (
                f"effective_allow={p1['effective_allow_count']}; "
                f"bypassPermissions_scopes={bypass_scopes}; "
                f"allow_plus_hook_miss={miss}; use-vs-mention control PASS. BLOCKED on review."
            ),
            "observations": [
                {
                    "name": "effective_allow_count",
                    "measured": p1["effective_allow_count"],
                    "method": "union of permissions.allow across settings scopes minus deny",
                    "anchor": "command-center/p2-wave/probes/AUD-0080/probe1-allow.raw.txt",
                },
                {
                    "name": "hooks_examined",
                    "measured": p2["hooks_examined"],
                    "method": "parse hooks from agent-self/config/settings.json",
                    "anchor": "command-center/p2-wave/probes/AUD-0080/probe2-bypass.raw.txt",
                },
                {
                    "name": "allow_plus_hook_miss",
                    "measured": miss,
                    "method": "allow-listed verb that intended matcher fails to hit",
                    "anchor": "command-center/p2-wave/probes/AUD-0080/probe2-hook-bypass.json",
                },
                {
                    "name": "use_vs_mention_control_ok",
                    "measured": ctrl["ok"],
                    "method": "benign verb + dangerous payload quote must not flag",
                    "anchor": "command-center/p2-wave/probes/AUD-0080/control-use-vs-mention.json",
                },
            ],
            "control_ids": ["AUD0080-C1"],
        },
        "extensions": {
            "anti_false_green": "BLOCKED-with-real-probes",
            "wave": "p2-loop",
            "bypassPermissions_scopes": bypass_scopes,
        },
    }


def main() -> int:
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
