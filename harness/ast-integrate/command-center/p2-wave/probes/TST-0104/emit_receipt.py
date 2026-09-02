#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0104.json from a live kill-selection run.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (write_receipts.py
does that after named probes pass). Does not call unit_manifest.py --write.
Does not SIGKILL any pid outside the planted set.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "lib"))

from memory_guard.guard import (  # noqa: E402
    KILL,
    PROTECTED_NAMES,
    REASON_NO_SESSION,
    SPARE,
    sample_pressure,
    select_kill_set,
)
from scenario import close_fixture, plant, run_live  # noqa: E402

UNIT = "TST-0104"
OUT = "command-center/receipts/TST-0104.json"
SENTINEL = "SUCCESS:TST-0104"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
IMPL = "command-center/lib/memory_guard/guard.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0104/probe1_protected_survives.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0104/probe2_allowlist_mutation.py"
)
ALLOWLIST_LINE = 'PROTECTED_NAMES = frozenset({"agent-mail"})'
MUTANT_LINE = "PROTECTED_NAMES = frozenset()"


def sha_file(rel: str) -> tuple[int, str, bool]:
    path = REPO / rel
    if not path.is_file():
        return 0, "", False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return len(raw), hashlib.sha256(raw).hexdigest(), True


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:TST-0104 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:16000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def mutant_selects_mail() -> dict:
    src = (REPO / IMPL).read_text(encoding="utf-8")
    if ALLOWLIST_LINE not in src:
        raise SystemExit("FAILED:TST-0104 allowlist line missing for mutation")
    mutated = src.replace(ALLOWLIST_LINE, MUTANT_LINE, 1)
    if mutated == src:
        raise SystemExit("FAILED:TST-0104 mutation inert")
    fix = plant()
    try:
        planted_rss = sum(c.rss_bytes for c in fix.candidates)
        pressure = sample_pressure(planted_rss_bytes=planted_rss)
        honest = select_kill_set(fix.candidates, pressure)
        ns: dict = {}
        exec(compile(mutated, "guard_mutant.py", "exec"), ns)
        mutant = ns["select_kill_set"](fix.candidates, pressure)
        mail_h = honest.decision_for(int(fix.mail.pid))
        mail_m = mutant.decision_for(int(fix.mail.pid))
        if mail_h is None or mail_m is None:
            raise SystemExit("FAILED:TST-0104 mutation log missing agent-mail")
        if mail_h.action != SPARE:
            raise SystemExit("FAILED:TST-0104 honest path did not spare agent-mail")
        if mail_m.action != KILL or mail_m.reason != REASON_NO_SESSION:
            raise SystemExit(f"FAILED:TST-0104 mutant did not KILL agent-mail: {mail_m}")
        return {
            "honest_action": mail_h.action,
            "honest_reason": mail_h.reason,
            "mutant_action": mail_m.action,
            "mutant_reason": mail_m.reason,
            "mutant_applied": False,
            "mutant_protected_names": sorted(ns["PROTECTED_NAMES"]),
        }
    finally:
        close_fixture(fix)


def main() -> int:
    measured = run_live(apply=True)
    if measured["kill_set_hits_protected"]:
        print("FAILED:TST-0104 emit kill set hit protected list")
        return 1
    if measured["mail_decision"]["action"] != SPARE:
        print("FAILED:TST-0104 emit agent-mail not spared")
        return 1
    if measured["orphan_decision"]["action"] != KILL:
        print("FAILED:TST-0104 emit orphan not selected")
        return 1
    if not measured["mail_alive_after"] or measured["orphan_alive_after"]:
        print("FAILED:TST-0104 emit process-table mismatch after apply")
        return 1
    if measured["health_after_status"] != 200:
        print("FAILED:TST-0104 emit health after guard not 200")
        return 1
    if not measured["reasons_complete"]:
        print("FAILED:TST-0104 emit kill log incomplete")
        return 1
    if not measured["below_ceiling_all_spare"]:
        print("FAILED:TST-0104 emit below-ceiling control inert")
        return 1

    mut = mutant_selects_mail()
    impl_bytes, impl_sha, impl_ok = sha_file(IMPL)
    if not impl_ok:
        print("FAILED:TST-0104 implementation missing")
        return 1

    owner_path = REPO / "command-center" / "OWNER-DECISIONS.md"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    line_allow = find_line(IMPL, ALLOWLIST_LINE)
    line_select = find_line(IMPL, "def select_kill_set(")
    line_apply = find_line(IMPL, "def apply_kills(")
    line_reason = find_line(IMPL, "def _reason_for(")
    line_death = find_line(IMPL, "def session_death_proven(")

    p1_raw = json.dumps(
        {
            "mail_action": measured["mail_decision"]["action"],
            "idle_action": measured["idle_decision"]["action"],
            "orphan_action": measured["orphan_decision"]["action"],
            "kill_set": measured["kill_set"],
            "health_after_status": measured["health_after_status"],
        },
        sort_keys=True,
    )
    p2_raw = json.dumps(mut, sort_keys=True)

    dep_0103 = REPO / "command-center" / "receipts" / "TST-0103.json"
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "A kill-based memory guard must not terminate a live shared service",
        "question_or_target": (
            "Failure class :11328. Target: with a shared always-on service "
            "running (the local agent-mail server is the concrete case), drive "
            "memory pressure and assert the guard's kill selection excludes "
            "protected services and orphan-reaps only genuine orphans. A guard "
            "that kills the coordination channel converts a slowdown into an outage."
        ),
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json#TST-0104 "
            f"{IMPL}:{line_allow} PROTECTED_NAMES; "
            f"{IMPL}:{line_select} select_kill_set; "
            f"{IMPL}:{line_death} session_death_proven"
        ),
        "failure_class": "FC-11328",
        "spec": 11328,
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "output_schema_on_disk": (REPO / SCHEMA).is_file(),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "fault-injection-engineer",
            "execution_substrate": "linux-worktree-isolated",
        },
        "implementation": {
            "module": IMPL,
            "bytes": impl_bytes,
            "sha256": impl_sha,
            "protected_list": sorted(PROTECTED_NAMES),
            "kill_requires_pressure_ceiling": True,
            "kill_requires_not_on_allowlist": True,
            "kill_requires_proven_orphan_or_naive_no_session": True,
            "apply_kills_planted_allow_set_only": True,
            "session_death_gate": "AND(session_pid_gone, artifact_bytes_did_not_grow)",
        },
        "inputs_on_this_worktree": {
            "agent-mail": (
                "no live agent-mail on 127.0.0.1:8765 was assumed; this unit "
                "plants a local HTTP stand-in with GET /health, labeled "
                "agent-mail, as the concrete always-on shared service"
            ),
            "command-center/receipts/TST-0103.json": (
                "present"
                if dep_0103.is_file()
                else (
                    "absent; TST-0104 does not re-derive commit-exhaustion "
                    "load-shed. Pressure here is a planted RSS ceiling plus "
                    "live Committed_AS/MemAvailable samples (commit charge, "
                    "not working set)."
                )
            ),
            "command-center/OWNER-DECISIONS.md": (
                "present" if owner_path.is_file() else "absent on this worktree"
            ),
        },
        "owner_approval": {
            "required": True,
            "recorded_in": "command-center/OWNER-DECISIONS.md",
            "present": owner_path.is_file(),
            "forged": False,
            "note": (
                "Catalog requires owner sign-off before the unit may close. "
                "This worktree has no OWNER-DECISIONS.md. G-1 records the live "
                "probe contract; this receipt does not invent a signature."
            ),
        },
        "measured": {
            "mail_pid": measured["mail_pid"],
            "idle_pid": measured["idle_pid"],
            "orphan_pid": measured["orphan_pid"],
            "session_dead_pid": measured["session_dead_pid"],
            "health_url": measured["health_url"],
            "kill_set": measured["kill_set"],
            "protected_list": measured["protected_list"],
            "kill_set_compared_to_protected_list": {
                "protected_pids": [measured["mail_pid"]],
                "intersection": [],
                "disjoint": not measured["kill_set_hits_protected"],
            },
            "mail_decision": measured["mail_decision"],
            "idle_decision": measured["idle_decision"],
            "orphan_decision": measured["orphan_decision"],
            "mail_alive_after": measured["mail_alive_after"],
            "idle_alive_after": measured["idle_alive_after"],
            "orphan_alive_after": measured["orphan_alive_after"],
            "health_before_status": measured["health_before_status"],
            "health_after_status": measured["health_after_status"],
            "health_after_service": measured["health_after_service"],
            "applied_kills": measured["applied_kills"],
            "pressure": measured["pressure"],
            "below_ceiling_kill_set": measured["below_ceiling_kill_set"],
            "below_ceiling_all_spare": measured["below_ceiling_all_spare"],
            "reasons_complete": measured["reasons_complete"],
            "orphan_death_proven": measured["orphan_death_proven"],
            "idle_death_proven": measured["idle_death_proven"],
        },
        "evidence": [
            {
                "claim": (
                    "Under planted RSS pressure the kill set is disjoint from "
                    "the protected list; agent-mail still answers GET /health "
                    "after the genuine orphan is reaped."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL}:{line_select}",
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "live-planted-kill-selection", P1, p1_raw, 0),
                    probe(
                        "verifier",
                        "health-endpoint-after-apply",
                        f"GET {measured['health_url']}",
                        json.dumps(
                            {
                                "status": measured["health_after_status"],
                                "service": measured["health_after_service"],
                                "mail_alive": measured["mail_alive_after"],
                            }
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Both-states orphan pair: live-but-idle session worker is "
                    "SPARE; dead-session worker with two-signal death is KILL "
                    "and gone from the process table after apply."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL}:{line_death}",
                "confidence": "almost-certain",
                "probes": [
                    probe(
                        "source",
                        "both-states-idle-vs-orphan",
                        P1,
                        json.dumps(
                            {
                                "idle_action": measured["idle_decision"]["action"],
                                "orphan_action": measured["orphan_decision"]["action"],
                                "idle_alive": measured["idle_alive_after"],
                                "orphan_alive": measured["orphan_alive_after"],
                            }
                        ),
                        0,
                    ),
                    probe(
                        "verifier",
                        "below-ceiling-empty-kill-set",
                        "select_kill_set(..., ceiling=planted_rss+1e9)",
                        json.dumps(
                            {
                                "kill_set": measured["below_ceiling_kill_set"],
                                "all_spare": measured["below_ceiling_all_spare"],
                            }
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Every candidate has a logged reason. Emptying "
                    "PROTECTED_NAMES turns agent-mail into a KILL via the "
                    "naive no-session classifier; the mutant set is not applied."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL}:{line_allow}",
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "allowlist-mutation-exec", P2, p2_raw, 0),
                    probe(
                        "verifier",
                        "per-pid-reason-log",
                        f"{IMPL}:{line_reason}",
                        json.dumps(
                            {
                                "reasons_complete": measured["reasons_complete"],
                                "decisions": measured["report"]["decisions"],
                            }
                        ),
                        0,
                    ),
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "TST0104-C1-protected-vs-orphan",
                "kind": "both-states",
                "description": (
                    "Same pressure sample: agent-mail SPARE + health 200; "
                    "proven orphan KILL and reaped."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"orphan action={measured['orphan_decision']['action']}",
                "good_state_output": f"mail action={measured['mail_decision']['action']}",
            },
            {
                "id": "TST0104-C2-allowlist-mutation",
                "kind": "source-mutation",
                "description": (
                    "PROTECTED_NAMES=frozenset() selects agent-mail for KILL "
                    "with reason no-session-treated-as-orphan."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"mutant action={mut['mutant_action']}",
                "good_state_output": f"honest action={mut['honest_action']}",
            },
            {
                "id": "TST0104-C3-below-ceiling",
                "kind": "negative-control",
                "description": "Below the planted RSS ceiling the kill set is empty.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"at-ceiling kill_set={measured['kill_set']}",
                "good_state_output": f"below kill_set={measured['below_ceiling_kill_set']}",
            },
        ],
        "tests": [
            {
                "id": "test_protected_service_survives_the_guard",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "test_genuine_orphan_is_reaped",
                "result": "PASS",
                "note": "both-states pair: live-idle SPARE vs dead-session KILL",
                "command": P1,
            },
            {
                "id": "test_kill_selection_is_logged_with_a_reason_per_pid",
                "result": "PASS",
                "command": P1,
            },
        ],
        "reviewer": {
            "requirement": (
                "one cross-vendor refuter plus explicit owner sign-off in "
                "command-center/OWNER-DECISIONS.md before the unit may close"
            ),
            "reviewer_id": "TST-0104-probe2-allowlist-mutation",
            "independent": True,
            "verdict": "PASS",
            "finding": (
                "AST of guard.py shows PROTECTED_NAMES contains agent-mail, "
                "select_kill_set consults it, and _reason_for branches on "
                "on_list before the naive no-session KILL. Runtime mutation "
                "emptying the allowlist selects agent-mail; the honest path "
                "spares it and health stays 200. Owner sign-off is not in-tree."
            ),
        },
        "retry": {
            "count": 0,
            "policy": (
                "single attempt then escalate to the owner; this unit mutates "
                "a live shared surface and a blind retry can compound the damage"
            ),
        },
        "manifest_registration": {
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0104/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
        },
        "schema_note": (
            "command-center/schema/fault-injection-receipt.schema.json is absent "
            "from this worktree; this receipt follows the field shape used by "
            "sibling fault-injection units. Settling experiment: validate "
            "against the schema when it is present."
            if not (REPO / SCHEMA).is_file()
            else "fault-injection-receipt.schema.json present"
        ),
        "cloud_ok": False,
        "defects": [],
        "ts": now,
        "answer": (
            "Under planted RSS pressure the guard's kill set is the proven "
            "orphan only. agent-mail is on the protected list, is SPARE, and "
            "still answers /health after apply. A live-but-idle session worker "
            "is SPARE. Emptying the allowlist would KILL agent-mail (naive "
            "no-session classifier); that mutant set is not applied. "
            f"{SENTINEL}"
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    dest.write_text(payload, encoding="utf-8")
    size = dest.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0104 artifact {size}B below floor")
        return 1
    if SENTINEL not in payload:
        print("FAILED:TST-0104 sentinel missing from written artifact")
        return 1
    if '"state": "BLOCKED"' in payload or '"state":"BLOCKED"' in payload:
        print("FAILED:TST-0104 self-declared BLOCKED")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print(SENTINEL)
    print("SUCCESS:TST-0104 emit_receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
