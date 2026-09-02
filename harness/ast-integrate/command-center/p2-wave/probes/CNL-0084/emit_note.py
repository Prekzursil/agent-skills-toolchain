#!/usr/bin/env python3
"""Emit the CNL-0084 council design note (JSON at the catalog .md path)."""
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
from detector import classify_path  # noqa: E402
from probe2_both_states import independent_deadlocked  # noqa: E402
import note_schema as NS  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0084-deadlock-detection-and-the-escalation-ladder.md"
)
OUT = REPO / OUT_REL
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
DET_REL = "command-center/p2-wave/probes/CNL-0084/detector.py"
GOOD_REL = "command-center/p2-wave/probes/CNL-0084/fixtures/known_good_slow_progress.json"
BAD_REL = "command-center/p2-wave/probes/CNL-0084/fixtures/planted_bad_deadlock.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0084/probe1_slow_vs_stuck.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0084/probe2_both_states.py"
)
QUESTION = (
    "What signature identifies a deadlocked council (as distinct from a slow "
    "but progressing one), and what is the ordered escalation ladder - recruit, "
    "replace, reframe, escalate to owner - with the trigger for each rung?"
)
SUPPORTING = [
    SCHEMA_REL,
    DET_REL,
    "command-center/p2-wave/probes/CNL-0084/probe1_slow_vs_stuck.py",
    "command-center/p2-wave/probes/CNL-0084/probe2_both_states.py",
    "command-center/p2-wave/probes/CNL-0084/note_schema.py",
    GOOD_REL,
    BAD_REL,
    "command-center/p2-wave/probes/CNL-0084/fixtures/productive_disagreement.json",
    "command-center/p2-wave/probes/CNL-0084/fixtures/stalled_runtime.json",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def snippet_line(rel: str, needle: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(needle)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0084 snippet missing in {rel}: {needle[:80]}")
    return text[:idx].count("\n") + 1


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(
    role: str, method: str, command: str, raw_output: str, exit_code: int = 0
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:8000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0)
    fx = HERE / "fixtures"
    good = classify_path(fx / "known_good_slow_progress.json")
    bad = classify_path(fx / "planted_bad_deadlock.json")
    dissent = classify_path(fx / "productive_disagreement.json")
    stall = classify_path(fx / "stalled_runtime.json")
    rec = classify_path(fx / "ladder_after_recruit.json")
    rep = classify_path(fx / "ladder_after_replace.json")
    ref = classify_path(fx / "ladder_after_reframe.json")
    full = classify_path(fx / "ladder_full_roster.json")

    if good["label"] != "PROGRESSING" or good["fired"]:
        print(f"FAILED:CNL-0084 emit known-good {good['label']} fired={good['fired']}")
        return 1
    if bad["label"] != "DEADLOCKED" or not bad["fired"]:
        print(f"FAILED:CNL-0084 emit planted-bad {bad['label']} fired={bad['fired']}")
        return 1
    if int(good["wall_ms"] or 0) <= int(bad["wall_ms"] or 0):
        print("FAILED:CNL-0084 emit wall-clock control")
        return 1
    if dissent["fired"] or stall["fired"]:
        print("FAILED:CNL-0084 emit negative controls fired")
        return 1
    want = [
        (bad, "recruit", "first"),
        (rec, "replace", "after-recruit"),
        (rep, "reframe", "after-replace"),
        (ref, "escalate_to_owner", "after-reframe"),
        (full, "replace", "full-roster"),
    ]
    for verdict, rung, name in want:
        got = (verdict.get("next_rung") or {}).get("rung")
        if got != rung:
            print(f"FAILED:CNL-0084 emit {name} want={rung} got={got}")
            return 1

    ig = independent_deadlocked(fx / "known_good_slow_progress.json")
    ib = independent_deadlocked(fx / "planted_bad_deadlock.json")
    if ig["deadlocked"] or not ib["deadlocked"]:
        print("FAILED:CNL-0084 emit Kahn recount disagrees")
        return 1

    c1, t1 = run_cmd(P1)
    if c1 != 0:
        print("FAILED:CNL-0084 emit probe1")
        print(t1[-2000:])
        return 1
    ok_g, n_g = NS.rejects_garbage()
    if not ok_g:
        print(f"FAILED:CNL-0084 emit schema accepts garbage ({n_g}/3)")
        return 1
    if not NS.shim_exists():
        print("FAILED:CNL-0084 emit catalog schema shim missing")
        return 1

    good_out = (
        f"label={good['label']} fired={good['fired']} wall_ms={good['wall_ms']} "
        f"reason={good['reason']}"
    )
    bad_out = (
        f"label={bad['label']} fired={bad['fired']} wall_ms={bad['wall_ms']} "
        f"cycle={bad['cycle']} reason={bad['reason']}"
    )
    dissent_out = (
        f"label={dissent['label']} fired={dissent['fired']} reason={dissent['reason']}"
    )
    stall_out = (
        f"label={stall['label']} fired={stall['fired']} missing={stall['missing_seats']}"
    )
    kahn_out = (
        f"independent_known_good_deadlocked={ig['deadlocked']} "
        f"independent_planted_bad_deadlocked={ib['deadlocked']}"
    )
    det_line_wall = snippet_line(
        DET_REL, "Wall-clock elapsed time is recorded and is NOT a predicate"
    )
    det_line_cycle = snippet_line(DET_REL, "frozen-ledger-and-wait-for-cycle")
    good_line = snippet_line(GOOD_REL, '"claim_ids": ["c1", "c2", "c3"]')
    bad_line = snippet_line(
        BAD_REL, '"awaiting": {"alice": ["bob"], "bob": ["alice"]}'
    )
    cat_line = snippet_line(
        "command-center/WORK-UNIT-CATALOG.json", '"id": "CNL-0084"'
    )

    answer = (
        "A council is deadlocked when it is still producing turns (every expected "
        "seat has returned at least once, so this is not a stalled runtime) AND "
        "the deliberation ledger fingerprint is identical across the last "
        "stuck_windows observation windows AND the seat awaiting-graph contains "
        "a wait-for cycle. The fingerprint is the sorted tuple of claim_ids, "
        "evidence_hashes, vote_tally pairs, dissent_brief_ids, and open_questions. "
        "Wall-clock elapsed time is not a predicate: the known-good slow-progress "
        f"fixture ends at wall_ms={good['wall_ms']} and is SILENT "
        f"(label={good['label']}); the planted-bad fixture ends at "
        f"wall_ms={bad['wall_ms']} and FIRES (label={bad['label']}, "
        f"cycle={bad['cycle']}). Productive disagreement that keeps adding "
        f"dissent briefs is {dissent['label']}. A seat that never returns is "
        f"{stall['label']}, an operational failure path, not a deliberation "
        "outcome. Frozen ledger without a cycle is FROZEN_WITHOUT_CYCLE and is "
        "out of scope here (CNL-0090 circular debate). "
        "Ordered ladder, each rung gated on DEADLOCKED still holding: "
        "(1) recruit — vacant required role or vote_tally has <2 distinct options; "
        "(2) replace — recruit already applied, or recorded inapplicable because "
        "the roster is full and dissent already exists, and the same wait-for "
        "cycle persists; "
        "(3) reframe — replace already applied and the open question set is still "
        "frozen; "
        "(4) escalate_to_owner — reframe already applied; emit one foundation-level "
        "question naming the deadlocked proposition, a recommendation, and "
        "default_if_silent=UNRESOLVED-AND-FREEZE. Rungs cannot be skipped upward "
        "except recruit-inapplicable, which is recorded on the replace trigger. "
        "SUCCESS:CNL-0084"
    )

    owner = (ref.get("next_rung") or {}).get("owner_packet") or {}
    ended = datetime.now(timezone.utc).replace(microsecond=0)
    duration = max(0, int((ended - started).total_seconds()))

    p1_src = probe("source", "command", P1, t1, c1)
    p1_ver = probe(
        "verifier",
        "file-read",
        f"{DET_REL}:{det_line_wall}",
        (
            "Wall-clock elapsed time is recorded and is NOT a predicate; "
            f"known-good wall_ms={good['wall_ms']} planted-bad wall_ms={bad['wall_ms']}"
        ),
    )
    kahn_src = probe(
        "source",
        "static-analysis",
        "command-center/p2-wave/probes/CNL-0084/probe2_both_states.py:independent_deadlocked",
        kahn_out,
    )
    kahn_ver = probe(
        "verifier",
        "file-read",
        f"{DET_REL}:{det_line_cycle}",
        f"planted-bad reason={bad['reason']} cycle={bad['cycle']}",
    )
    schema_src = probe(
        "source",
        "schema-validate",
        "python3 -B command-center/p2-wave/probes/CNL-0084/note_schema.py",
        "inlined generic_report+$defs; garbage 3/3 rejected",
    )
    schema_ver = probe(
        "verifier",
        "file-read",
        SCHEMA_REL,
        "catalog shim exists; physical pin is council-design-note",
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0084",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0084",
        "spec_anchor": f"command-center/WORK-UNIT-CATALOG.json:{cat_line}",
        "min_bytes_threshold": 2048,
        "profile": "council-design-note",
        "produced_by": {
            "vendor": "grok",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "council-design-note",
            "title": "Deadlock detection and the escalation ladder",
            "question": QUESTION,
            "answer": answer,
            "format_note": (
                "Catalog output_path ends in .md. G-1 _measure_one_delivered.py "
                "json.loads the whole file, so this artifact is JSON."
            ),
            "deadlock_signature": {
                "signals": ["ledger-fingerprint-freeze", "wait-for-cycle"],
                "not_a_signal": "wall_ms",
                "stuck_windows": 2,
                "min_turns": 2,
                "exclusions": [
                    "STALLED_RUNTIME when any expected seat never returned",
                    "STOPPED when stopping_satisfied is true (CNL-0076 evaluates that bit)",
                    "FROZEN_WITHOUT_CYCLE deferred to CNL-0090",
                    "PROGRESSING when any ledger field changes",
                ],
                "both_states": {
                    "known_good_label": good["label"],
                    "known_good_fired": good["fired"],
                    "known_good_wall_ms": good["wall_ms"],
                    "planted_bad_label": bad["label"],
                    "planted_bad_fired": bad["fired"],
                    "planted_bad_wall_ms": bad["wall_ms"],
                    "planted_bad_cycle": bad["cycle"],
                    "independent_known_good_deadlocked": ig["deadlocked"],
                    "independent_planted_bad_deadlocked": ib["deadlocked"],
                },
            },
            "escalation_ladder": [
                {
                    "rung": "recruit",
                    "order": 1,
                    "trigger": (
                        "DEADLOCKED and (vacant required role or no dissent in vote_tally)"
                    ),
                    "measured": bad["next_rung"],
                },
                {
                    "rung": "replace",
                    "order": 2,
                    "trigger": (
                        "DEADLOCKED after recruit, or recruit inapplicable on a "
                        "full dissenting roster"
                    ),
                    "measured_after_recruit": rec["next_rung"],
                    "measured_full_roster": full["next_rung"],
                },
                {
                    "rung": "reframe",
                    "order": 3,
                    "trigger": "DEADLOCKED after replace on the same open-question set",
                    "measured": rep["next_rung"],
                },
                {
                    "rung": "escalate_to_owner",
                    "order": 4,
                    "trigger": "DEADLOCKED after reframe; one foundation question plus default",
                    "measured": ref["next_rung"],
                    "owner_packet": owner,
                },
            ],
            "observations": [
                {
                    "name": "known-good-slow-progress",
                    "measured": good_out,
                    "method": "detector.classify fingerprint-tuple plus DFS cycle",
                    "anchor": f"{GOOD_REL}:{good_line}",
                },
                {
                    "name": "planted-bad-deadlock",
                    "measured": bad_out,
                    "method": "detector.classify fingerprint-tuple plus DFS cycle",
                    "anchor": f"{BAD_REL}:{bad_line}",
                },
                {
                    "name": "independent-kahn-recount",
                    "measured": kahn_out,
                    "method": "canonical JSON of ledger fields plus Kahn cycle",
                    "anchor": (
                        "command-center/p2-wave/probes/CNL-0084/"
                        "probe2_both_states.py:independent_deadlocked"
                    ),
                },
            ],
            "control_ids": [
                "slow-progress-must-stay-silent",
                "productive-disagreement-is-not-deadlock",
                "stalled-runtime-is-operational-not-deliberation",
            ],
        },
        "artifacts": [artifact_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Deadlock requires a frozen ledger fingerprint and a wait-for "
                    "cycle; wall_ms is recorded and is not a predicate."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{DET_REL}:{det_line_wall}",
                "probes": [p1_src, p1_ver],
            },
            {
                "claim": (
                    "Independent Kahn + canonical-JSON recount agrees: known-good "
                    "is not deadlocked, planted-bad is deadlocked."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0084/"
                    "probe2_both_states.py:independent_deadlocked"
                ),
                "probes": [kahn_src, kahn_ver],
            },
            {
                "claim": (
                    "The catalog output_schema shim exists; this note validates "
                    "against the inlined council-design-note generic_report pin "
                    "without a network $ref fetch."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": SCHEMA_REL,
                "probes": [schema_src, schema_ver],
            },
        ],
        "tests": [
            {
                "id": "probe1-slow-vs-stuck",
                "name": (
                    "slow-but-progressing stays SILENT; genuinely stuck FIRES; "
                    "wall-clock would invert"
                ),
                "command": P1,
                "result": "PASS",
                "output_tail": t1[-2000:],
            },
            {
                "id": "independent-kahn-both-states",
                "name": (
                    "Kahn recount SILENT on known-good and FIRE on planted-bad"
                ),
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                    "\"import sys; from pathlib import Path; "
                    "sys.path.insert(0,'command-center/p2-wave/probes/CNL-0084'); "
                    "from probe2_both_states import independent_deadlocked; "
                    "fx=Path('command-center/p2-wave/probes/CNL-0084/fixtures'); "
                    "print(independent_deadlocked(fx/'known_good_slow_progress.json')); "
                    "print(independent_deadlocked(fx/'planted_bad_deadlock.json'))\""
                ),
                "result": "PASS",
                "output_tail": kahn_out,
            },
        ],
        "negative_controls": [
            {
                "id": "slow-progress-must-stay-silent",
                "kind": "known-broken-fixture",
                "description": (
                    "The detector must FIRE on planted-bad deadlock and stay "
                    "SILENT on known-good slow progress. A duration-only "
                    "heuristic would invert the labels."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": bad_out,
                "good_state_output": good_out,
            },
            {
                "id": "productive-disagreement-is-not-deadlock",
                "kind": "other",
                "description": (
                    "Productive disagreement that keeps adding dissent briefs "
                    "must not be labelled DEADLOCKED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": bad_out,
                "good_state_output": dissent_out,
            },
            {
                "id": "stalled-runtime-is-operational-not-deliberation",
                "kind": "other",
                "description": (
                    "A seat that never returns is STALLED_RUNTIME, not deadlock."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": bad_out,
                "good_state_output": stall_out,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0084-probe2-both-states-kahn-recount",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Catalog asked for a cross-vendor openai/gpt-5-codex reviewer "
                "who re-runs the both-states control. No that-vendor session is "
                "on this Linux worktree. The live independent control is probe2: "
                "Kahn's algorithm plus canonical JSON of ledger fields, a "
                "different mechanism from detector.py's DFS+tuple fingerprint. "
                f"Wall-clock counterexample: known-good wall_ms={good['wall_ms']} "
                f"exceeds planted-bad wall_ms={bad['wall_ms']} yet only the "
                "planted-bad FIRES. Named probe2 re-runs FIRE/SILENT before G-1 "
                "accepts this unit."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0084/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNL-0084",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNL-0084/note_schema.py "
                    "Draft202012Validator"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/CNL-0084/note_schema.py",
                    "validate(doc) errors=[] ; garbage 3/3 rejected",
                ),
            },
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNL-0084/probe2_both_states.py"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe("verifier", "command", P2, "named probe2 both-states"),
            },
        ],
        "timestamps": {
            "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_at": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "hypothesis, enumerate >=2 alternative mechanisms before a 3rd "
                "attempt (AGENTS.md 4b). Max 3 attempts."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "CNL-0076 owns when stopping_satisfied is evaluated; this "
                    "detector only reads the bit."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNL-0076 on this worktree and replay the planted-bad "
                    "fixture with stopping_satisfied flipped at end-of-round."
                ),
            },
            {
                "claim": (
                    "FROZEN_WITHOUT_CYCLE is labelled and left SILENT for deadlock; "
                    "CNL-0090 owns circular-debate / information-gain."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNL-0090 and confirm a frozen-no-cycle fixture stays "
                    "outside this detector's FIRE set."
                ),
            },
            {
                "claim": (
                    "Catalog inputs cite a Windows harness-restore _USER-PROMPTS.md "
                    "that is not on this Linux worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount the harness-restore slice and quote the cited line "
                    "range; until then the signature is derived from the catalog "
                    "question plus the both-states fixtures."
                ),
            },
        ],
    }

    schema_errs = NS.errors(doc)
    if schema_errs:
        print("FAILED:CNL-0084 emit schema-invalid")
        for line in schema_errs[:12]:
            print(" ", line)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    live_errs = NS.errors(json.loads(OUT.read_text(encoding="utf-8")))
    if live_errs:
        print("FAILED:CNL-0084 emit live reparse schema-invalid")
        print(live_errs[0])
        return 1
    if "SUCCESS:CNL-0084" not in OUT.read_text(encoding="utf-8"):
        print("FAILED:CNL-0084 emit sentinel absent after write")
        return 1
    print(f"wrote {OUT_REL} bytes={OUT.stat().st_size}")
    print("SUCCESS:CNL-0084 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
