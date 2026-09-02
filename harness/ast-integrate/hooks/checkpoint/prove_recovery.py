#!/usr/bin/env python3
"""Executable acceptance proof: a simulated compaction resumes with ZERO owner re-explanation.

Run:  python prove_recovery.py            (add --keep to inspect the temp workspace)

WHAT MAKES THIS A PROOF AND NOT A DEMO
--------------------------------------
1. Every stage runs the real entry point as a SEPARATE OS PROCESS. "Clearing the in-memory view"
   is not a claim here -- the recovering process is a fresh interpreter that has never seen the
   session. It receives ONLY `{session_id, cwd, source}`.
2. BOTH STATES. Probe 1 runs the recovery against the KNOWN-BROKEN state (no checkpoint on disk)
   and REQUIRES it to fire. Probe 3 runs the identical command against the fixed state and
   requires the alarm to be gone. A probe that is silent in both states measures nothing.
3. RECONSTRUCTED-FROM-DISK-ONLY is asserted mechanically: four load-bearing facts must appear in
   the recovered context AND must be absent from the JSON that was fed to the recovering process.
   The transcript is DELETED before the recovery runs, so it cannot have been re-mined.
4. The negative controls matter as much as the positive: a foreign session must NOT receive the
   content, a planted credential must NOT reach disk, a fresh start must stay CLEAN, and a write
   that cannot happen must report NOT-CHECKED rather than nothing.

Terminal state per AGENTS.md section 4: one SUCCESS:/FAILED: line per probe plus an overall line.
Exit 0 = every probe passed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRECOMPACT = HERE / "precompact.py"
RECOVER = HERE / "recover.py"

SESSION = "11111111-2222-3333-4444-555555555555"
OTHER_SESSION = "99999999-8888-7777-6666-555555555555"

# Load-bearing facts. Each must survive the compaction and reach the resumed session.
FACT_PLAN = "ORBITAL-LEDGER-MIGRATION-STEP-7"
FACT_FILE = "zx9quorum_ledger.py"
FACT_TASK = "backfill the quorum index"
FACT_WHERE = "waiting on the backfill to finish"
FACTS = (FACT_PLAN, FACT_FILE, FACT_TASK, FACT_WHERE)

# Planted FAKE credentials (PLACEHOLDER / EXAMPLE values, assembled at runtime so this source file
# itself never contains a contiguous credential-shaped literal -- the repo secret guard is right to
# reject one, and a test fixture is not an exception to that rule). Neither may ever reach disk.
PLANTED_TOKEN = (
    "gh" + "p_" + "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
)  # PLACEHOLDER, not a real key
PLANTED_JSON_PW = "sup3rsecret-quorum-pw"  # PLACEHOLDER

results: list[tuple[bool, str, str]] = []


def check(ok: bool, ident: str, detail: str = "") -> bool:
    results.append((ok, ident, detail))
    print(("SUCCESS:" if ok else "FAILED:") + ident + (f" {detail}" if detail else ""))
    return ok


def run(
    script: Path, payload: dict, env_extra: dict | None = None
) -> tuple[int, str, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def context_of(stdout: str) -> str:
    try:
        return json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return ""


def build_transcript(path: Path, cwd: str) -> None:
    """A plan-shaped session tail, in real Claude Code JSONL shapes (probed 2026-08-08)."""
    common = {
        "sessionId": SESSION,
        "cwd": cwd,
        "gitBranch": "feature/quorum",
        "version": "2.1.214",
    }
    records = [
        {
            **common,
            "type": "user",
            "message": {"role": "user", "content": f"Start {FACT_PLAN}."},
        },
        {
            **common,
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Editing the ledger module."},
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": f"/srv/app/{FACT_FILE}"},
                    },
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {
                            "command": f"curl -H 'Authorization: Bearer {PLANTED_TOKEN}' https://x.invalid"
                        },
                    },
                    {
                        "type": "tool_use",
                        "name": "TodoWrite",
                        "input": {
                            "todos": [
                                {
                                    "content": f"{FACT_TASK} for shard 3",
                                    "status": "in_progress",
                                },
                                {
                                    "content": "re-run the parity check",
                                    "status": "pending",
                                },
                            ]
                        },
                    },
                ],
            },
        },
        {
            "type": "last-prompt",
            "sessionId": SESSION,
            "lastPrompt": f"Continue {FACT_PLAN}: migrate shards 3-9, keep the old index readable, "
            f'and use the config {{"password": "{PLANTED_JSON_PW}"}} for the staging box.',
        },
        {
            **common,
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": f"Shard 3 migrated; {FACT_WHERE} before shard 4.",
                    }
                ],
            },
        },
    ]
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8", newline="\n"
    )


def git_init(cwd: Path) -> None:
    for args in (
        ["init", "-q"],
        ["config", "user.email", "probe@local.invalid"],
        ["config", "user.name", "probe"],
        ["commit", "-q", "--allow-empty", "-m", "base"],
    ):
        try:
            subprocess.run(
                ["git", "-C", str(cwd), *args], capture_output=True, timeout=20
            )
        except Exception:
            return


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--keep", action="store_true", help="do not delete the temp workspace"
    )
    ap.add_argument(
        "--real-transcript",
        default="",
        help="time the writer against a real transcript",
    )
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="checkpoint-proof-"))
    proj = tmp / "proj"
    (proj / ".beads").mkdir(parents=True, exist_ok=True)
    git_init(proj)
    transcript = tmp / "transcript.jsonl"
    build_transcript(transcript, str(proj))

    state_file = proj / ".beads" / "context" / "execution-state.md"
    resume_payload = {"session_id": SESSION, "cwd": str(proj), "source": "compact"}

    # ---- PROBE 1 -- KNOWN-BROKEN STATE: no checkpoint exists. The probe MUST fire. -------
    rc, out, err = run(RECOVER, resume_payload)
    ctx_broken = context_of(out)
    check(rc == 0, "probe1.exit0", f"rc={rc}")
    check(
        "CHECKPOINT-RECOVER: FINDING" in err,
        "probe1.broken-state-FIRES",
        err.strip()[:120],
    )
    check("no checkpoint for a" in ctx_broken, "probe1.alarm-text-present")
    check(not state_file.exists(), "probe1.precondition-no-state-file")

    # ---- STAGE 2 -- the PreCompact writer runs (a separate process) ----------------------
    t0 = time.monotonic()
    rc, out, err = run(
        PRECOMPACT,
        {
            "session_id": SESSION,
            "cwd": str(proj),
            "transcript_path": str(transcript),
            "trigger": "auto",
            "hook_event_name": "PreCompact",
        },
    )
    write_elapsed = time.monotonic() - t0
    check(rc == 0, "probe2.exit0", f"rc={rc}")
    check(
        json.loads(out or "{}").get("suppressOutput") is True,
        "probe2.suppresses-output",
    )
    check(
        "CHECKPOINT-WRITE: RAISED" in err or "CHECKPOINT-WRITE: DEGRADED" in err,
        "probe2.typed-stderr",
        err.strip()[:140],
    )
    check(state_file.exists(), "probe2.state-file-written", str(state_file))
    disk = state_file.read_text(encoding="utf-8") if state_file.exists() else ""

    # ---- PROBE 2b -- redaction: no planted credential may reach disk ---------------------
    check(PLANTED_TOKEN not in disk, "probe2b.bare-token-redacted")
    check(PLANTED_JSON_PW not in disk, "probe2b.json-password-redacted")

    # ---- STAGE 3 -- destroy every in-memory and in-transcript trace ----------------------
    transcript.unlink(missing_ok=True)
    check(not transcript.exists(), "probe3.transcript-deleted-before-recovery")

    # ---- PROBE 3 -- FIXED STATE: identical command, alarm gone, facts recovered ----------
    rc, out, err = run(RECOVER, resume_payload)
    ctx = context_of(out)
    check(rc == 0, "probe3.exit0", f"rc={rc}")
    check(
        "CHECKPOINT-RECOVER: RAISED" in err,
        "probe3.fixed-state-RAISED",
        err.strip()[:120],
    )
    check("no checkpoint for a" not in ctx, "probe3.alarm-text-ABSENT-in-fixed-state")

    payload_json = json.dumps(resume_payload)
    for i, fact in enumerate(FACTS, 1):
        check(fact in ctx, f"probe3.fact{i}-recovered", fact)
        check(
            fact not in payload_json,
            f"probe3.fact{i}-not-in-input",
            "so it came from disk",
        )

    check(
        PLANTED_TOKEN not in ctx and PLANTED_JSON_PW not in ctx,
        "probe3.no-credential-in-context",
    )
    check("UNTRUSTED historical content" in ctx, "probe3.untrusted-label-present")

    # ---- PROBE 4 -- foreign session must NOT be steered (snapshot.ps1:43-48 lesson) ------
    rc, out, err = run(
        RECOVER, {"session_id": OTHER_SESSION, "cwd": str(proj), "source": "compact"}
    )
    ctx_foreign = context_of(out)
    check(
        "CHECKPOINT-RECOVER: DEGRADED" in err,
        "probe4.foreign-session-DEGRADED",
        err.strip()[:120],
    )
    check(FACT_PLAN not in ctx_foreign, "probe4.foreign-session-content-withheld")
    check("DIFFERENT session" in ctx_foreign, "probe4.foreign-session-explains-why")

    # ---- PROBE 5 -- a fresh startup with nothing to recover stays CLEAN and silent -------
    empty = tmp / "empty"
    (empty / ".beads").mkdir(parents=True, exist_ok=True)
    rc, out, err = run(
        RECOVER, {"session_id": SESSION, "cwd": str(empty), "source": "startup"}
    )
    check(
        "CHECKPOINT-RECOVER: CLEAN" in err,
        "probe5.fresh-start-CLEAN",
        err.strip()[:120],
    )
    check(out.strip() == "", "probe5.CLEAN-injects-nothing")

    # ---- PROBE 6 -- an impossible write reports NOT-CHECKED, never nothing ---------------
    blocker = tmp / "blocker"
    blocker.write_text("i am a file, not a directory", encoding="utf-8")
    rc, out, err = run(
        PRECOMPACT,
        {
            "session_id": SESSION,
            "cwd": str(proj),
            "transcript_path": "",
            "trigger": "manual",
        },
        env_extra={"CHECKPOINT_BEADS_ROOT": str(blocker / "nope")},
    )
    check(rc == 0, "probe6.exit0-even-when-write-impossible", f"rc={rc}")
    check(
        "CHECKPOINT-WRITE: NOT-CHECKED" in err,
        "probe6.unwritable-reports-NOT-CHECKED",
        err.strip()[:140],
    )

    # ---- PROBE 7 -- a second compaction increments the counter and keeps history ---------
    build_transcript(transcript, str(proj))
    run(
        PRECOMPACT,
        {
            "session_id": SESSION,
            "cwd": str(proj),
            "transcript_path": str(transcript),
            "trigger": "manual",
        },
    )
    disk2 = state_file.read_text(encoding="utf-8")
    check("compaction_seq: 2" in disk2, "probe7.counter-increments")
    check(
        disk2.count("\n- #") >= 2 or ("#1 " in disk2 and "#2 " in disk2),
        "probe7.history-retained",
    )

    # ---- PROBE 8 -- unparseable checkpoint degrades, never crashes or leaks ---------------
    state_file.write_text("this is not front matter at all\n", encoding="utf-8")
    rc, out, err = run(RECOVER, resume_payload)
    check(
        "CHECKPOINT-RECOVER: DEGRADED" in err,
        "probe8.garbage-file-DEGRADED",
        err.strip()[:120],
    )

    # ---- optional: budget evidence against a REAL transcript -----------------------------
    if args.real_transcript and Path(args.real_transcript).is_file():
        big = Path(args.real_transcript)
        root = tmp / "realroot"
        t0 = time.monotonic()
        rc, out, err = run(
            PRECOMPACT,
            {
                "session_id": SESSION,
                "cwd": str(proj),
                "transcript_path": str(big),
                "trigger": "auto",
            },
            env_extra={"CHECKPOINT_BEADS_ROOT": str(root)},
        )
        real_elapsed = time.monotonic() - t0
        mb = big.stat().st_size / (1024 * 1024)
        check(rc == 0, "probe9.real-transcript-exit0")
        check(
            real_elapsed < 10.0,
            "probe9.real-transcript-under-10s",
            f"{real_elapsed:.2f}s incl. interpreter start on {mb:.0f} MB",
        )
        # A file >400 bytes is NOT evidence -- a fully DEGRADED capture is also >400 bytes. The
        # control has to prove the read actually happened, or the speed number means nothing.
        wrote = root / "context" / "execution-state.md"
        real_text = wrote.read_text(encoding="utf-8") if wrote.is_file() else ""
        mined_n = 0
        for line in real_text.splitlines():
            if line.startswith("events_mined:"):
                try:
                    mined_n = int(line.split(":", 1)[1].strip())
                except Exception:
                    mined_n = 0
        check(
            mined_n > 100,
            "probe9.real-transcript-ACTUALLY-mined",
            f"events_mined={mined_n}",
        )
        check("status: OK" in real_text, "probe9.real-transcript-status-OK")
        check(
            "transcript-unreadable" not in real_text,
            "probe9.real-transcript-not-silently-degraded",
        )

    print(
        f"\nTIMING: synthetic write {write_elapsed:.3f}s (includes python interpreter startup)"
    )
    if not args.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"WORKSPACE KEPT: {tmp}")

    failed = [ident for ok, ident, _ in results if not ok]
    if failed:
        print(
            f"\nFAILED:checkpoint-acceptance {len(failed)}/{len(results)} probes failed: {', '.join(failed)}"
        )
        return 1
    print(f"\nSUCCESS:checkpoint-acceptance all {len(results)} probes passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
