r"""B8 - what would deploying `edit-checkpoints` COST per edit?

The /rollback producer gap is one manifest deploy away from closing, so the decision is
not "does it work" (the grounding lane already proved it writes an index plus a real
git-stash object) but "what does arming it charge every Edit/Write/MultiEdit". That is
the number a deploy plan has to carry, because PreToolUse fires on the single most
frequent tool call in a session.

Runs against a THROWAWAY git repo with an isolated EDIT_CHECKPOINTS_DIR, asserted empty
first, so nothing touches this worktree, the real checkpoint index, or the real stash
refs.

ROUND 3 -- THE ROUND-1 NUMBER MEASURED THE WRONG PATH, and its own evidence said so.
`checkpoint.py:208-211` keys a snapshot on `f"{turn}|{repo}"` and returns 0 when that key
is already present: **one git snapshot per human turn per repo**, not one per edit. The
round-1 probe sent five identical payloads with no `transcript_path`, so all five shared a
turn key -- one snapshot, four no-ops -- and then published the mean of the FOUR NO-OPS as
"what arming the producer charges every Edit". The give-away was already in the committed
file: `index_records: 1` beside five samples. Nobody read it.

So this version measures BOTH paths and refuses to publish unless it can tell them apart:

  FIRST-IN-TURN   a fresh session id per iteration, so every call takes the snapshot path.
                  This is the cost paid once per turn per repo -- every turn.
  SUBSEQUENT      one session id, repeated, so every call after the first hits the
                  already-snapshotted-this-turn early return. This is what every other
                  edit in the same turn costs.

CONTROL, fail-closed: the armed phase must produce exactly one index record per call and
the repeat phase exactly one in total. If those counts do not hold, the two phases are not
exercising different code paths and no cost is published -- which is precisely the check
that would have caught the round-1 number.

`verdict_fits_budget` is decided on the MAX, not a mean: `dispatch.py:368-372` drops the
ENTIRE output of a check that overruns once.

Writes B8-ROLLBACK-COST.json.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

# Derived, never hardcoded: an absolute path here measures whichever checkout the author
# happened to have, not the one the caller is standing in (the H2 shape fixed in
# check_citations.py this round).
REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PRODUCER = REPO / "hooks" / "edit-checkpoints" / "checkpoint.py"
# live PreToolUse dispatcher budget (settings.json) and the manifest's own per-check cap
LIVE_PRETOOL_BUDGET_S = 20.0
CHECK_BUDGET_S = 15.0


def git(cwd: Path, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def fire(producer: Path, repo: Path, target: Path, sid: str, i: int, env: dict) -> dict:
    target.write_text(f"# baseline\n# edit {i}\n", encoding="utf-8")
    payload = json.dumps(
        {
            "session_id": sid,
            "cwd": str(repo),
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "# baseline",
                "new_string": f"# edit {i}",
            },
        }
    ).encode("utf-8")
    t0 = time.perf_counter()
    p = subprocess.run(
        [sys.executable, str(producer)],
        input=payload,
        capture_output=True,
        timeout=300,
        env=env,
        cwd=str(repo),
    )
    return {
        "iteration": i,
        "wall_ms": round((time.perf_counter() - t0) * 1000, 1),
        "exit": p.returncode,
        "stderr_tail": p.stderr.decode("utf-8", "replace")[-200:],
    }


def records_in(ck: Path) -> int:
    return sum(
        len([x for x in f.read_text(encoding="utf-8").splitlines() if x.strip()])
        for f in ck.rglob("index.ndjson")
    )


def stats(rows: list[dict], label: str) -> dict:
    v = sorted(r["wall_ms"] for r in rows)
    med = round(statistics.median(v), 1)
    mx = max(v)
    return {
        f"{label}_n": len(v),
        f"{label}_min_ms": v[0],
        f"{label}_median_ms": med,
        f"{label}_p90_ms": v[min(len(v) - 1, int(round(0.9 * (len(v) - 1))))],
        f"{label}_max_ms": mx,
        f"{label}_spread_x": round(mx / max(v[0], 0.1), 2),
        f"{label}_median_pct_of_check_budget": round(
            100.0 * (med / 1000.0) / CHECK_BUDGET_S, 1
        ),
        f"{label}_max_pct_of_check_budget": round(
            100.0 * (mx / 1000.0) / CHECK_BUDGET_S, 1
        ),
        f"{label}_max_pct_of_event_budget": round(
            100.0 * (mx / 1000.0) / LIVE_PRETOOL_BUDGET_S, 1
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=12)
    n = max(3, ap.parse_args().repeat)

    repo = Path(tempfile.gettempdir()) / f"b8-{uuid.uuid4().hex[:8]}"
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q")
    target = repo / "mod.py"
    target.write_text("# baseline\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "baseline")

    ck = repo / "_ckpt"
    assert not ck.exists() or not any(ck.iterdir()), "checkpoint dir must start empty"
    env = dict(os.environ)
    env["EDIT_CHECKPOINTS_DIR"] = str(ck)

    # PHASE 1 -- first-edit-in-turn: a fresh session id forces the snapshot path each call.
    armed = [fire(PRODUCER, repo, target, f"b8armed{i}", i, env) for i in range(n)]
    armed_records = records_in(ck)

    # PHASE 2 -- subsequent edits in the SAME turn: one id, so only the first works.
    repeat_rows = [fire(PRODUCER, repo, target, "b8repeat", i, env) for i in range(n)]
    repeat_records = records_in(ck) - armed_records
    subsequent = repeat_rows[1:]

    refs = [
        r
        for r in git(repo, "for-each-ref", "--format=%(refname)").stdout.splitlines()
        if "checkpoint" in r.lower()
    ]

    res: dict = {
        "producer": str(PRODUCER),
        "isolated_checkpoint_dir": str(ck),
        "samples_per_phase": n,
        "armed_index_records": armed_records,
        "repeat_index_records": repeat_records,
        "snapshot_refs_created": len(refs),
        "armed_runs": armed,
        "repeat_runs": repeat_rows,
    }
    res.update(stats(armed, "first_in_turn"))
    res.update(stats(subsequent, "subsequent"))
    res["verdict_fits_budget"] = res["first_in_turn_max_ms"] / 1000.0 < CHECK_BUDGET_S

    # CONTROL. One record per armed call, exactly one for the whole repeat phase. Anything
    # else means the phases are not on different paths and the numbers mean nothing.
    control_ok = armed_records == n and repeat_records == 1
    res["control_phases_distinguished"] = control_ok
    res["control_expected"] = {"armed_index_records": n, "repeat_index_records": 1}

    (OUT / "B8-ROLLBACK-COST.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8"
    )
    shutil.rmtree(repo, ignore_errors=True)

    print(
        f"FIRST-IN-TURN (snapshot path, n={n}): min/median/p90/max = "
        f"{res['first_in_turn_min_ms']}/{res['first_in_turn_median_ms']}/"
        f"{res['first_in_turn_p90_ms']}/{res['first_in_turn_max_ms']} ms  "
        f"median {res['first_in_turn_median_pct_of_check_budget']}% / max "
        f"{res['first_in_turn_max_pct_of_check_budget']}% of the {CHECK_BUDGET_S}s budget"
    )
    print(
        f"SUBSEQUENT    (early return, n={len(subsequent)}): median "
        f"{res['subsequent_median_ms']} ms, max {res['subsequent_max_ms']} ms  "
        f"({res['subsequent_max_pct_of_check_budget']}% of budget)"
    )
    print(
        f"CONTROL index records armed={armed_records} (want {n})  "
        f"repeat={repeat_records} (want 1)  refs={len(refs)}"
    )
    if not control_ok:
        print(
            "FAILED:b8-rollback-cost the two phases are NOT on different code paths -- "
            "publishing a per-edit cost from this run would repeat the round-1 defect"
        )
        return 1
    print("SUCCESS:b8-rollback-cost")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
