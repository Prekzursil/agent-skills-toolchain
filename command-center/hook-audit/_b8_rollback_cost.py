r"""B8 - what would deploying `edit-checkpoints` COST per edit?

The /rollback producer gap is one manifest deploy away from closing, so the decision is
not "does it work" (the grounding lane already proved it writes an index plus a real
git-stash object) but "what does arming it charge every Edit/Write/MultiEdit". That is
the number a deploy plan has to carry, because PreToolUse fires on the single most
frequent tool call in a session.

Runs against a THROWAWAY git repo with an isolated EDIT_CHECKPOINTS_DIR, asserted empty
first, so nothing touches this worktree, the real checkpoint index, or the real stash
refs. Measures a cold first call and warm repeats separately -- a single reading cannot
tell one-off setup from per-edit steady state.

Writes B8-ROLLBACK-COST.json.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
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


def main() -> int:
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

    rows = []
    for i in range(5):
        target.write_text(f"# baseline\n# edit {i}\n", encoding="utf-8")
        payload = json.dumps(
            {
                "session_id": "b8",
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
            [sys.executable, str(PRODUCER)],
            input=payload,
            capture_output=True,
            timeout=300,
            env=env,
            cwd=str(repo),
        )
        rows.append(
            {
                "iteration": i,
                "wall_ms": round((time.perf_counter() - t0) * 1000, 1),
                "exit": p.returncode,
                "stderr_tail": p.stderr.decode("utf-8", "replace")[-200:],
            }
        )

    # checkpoint.py writes CKPT_ROOT/<session_id>/index.ndjson -- a per-session SUBDIR,
    # not the root. Checking the root reported "wrote no index" while the producer was
    # working correctly; the fail-closed gate caught it instead of publishing a cost
    # number with no evidence the producer had done anything.
    found = sorted(ck.rglob("index.ndjson"))
    idx = found[0] if found else None
    wrote = bool(idx and idx.stat().st_size > 0)
    records = len(idx.read_text(encoding="utf-8").splitlines()) if wrote else 0
    refs = git(repo, "for-each-ref", "--format=%(refname)").stdout.splitlines()
    ckpt_refs = [r for r in refs if "checkpoint" in r.lower()]

    cold = rows[0]["wall_ms"]
    warm = [r["wall_ms"] for r in rows[1:]]
    warm_mean = round(sum(warm) / len(warm), 1)
    res = {
        "producer": str(PRODUCER),
        "isolated_checkpoint_dir": str(ck),
        "index_written": wrote,
        "index_records": records,
        "snapshot_refs_created": len(ckpt_refs),
        "cold_ms": cold,
        "warm_mean_ms": warm_mean,
        "warm_max_ms": max(warm),
        "runs": rows,
        "per_check_budget_s": CHECK_BUDGET_S,
        "warm_pct_of_check_budget": round(
            100.0 * (warm_mean / 1000.0) / CHECK_BUDGET_S, 1
        ),
        "live_pretooluse_event_budget_s": LIVE_PRETOOL_BUDGET_S,
        "warm_pct_of_event_budget": round(
            100.0 * (warm_mean / 1000.0) / LIVE_PRETOOL_BUDGET_S, 1
        ),
        "verdict_fits_budget": warm_mean / 1000.0 < CHECK_BUDGET_S,
    }
    (OUT / "B8-ROLLBACK-COST.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8"
    )
    shutil.rmtree(repo, ignore_errors=True)
    print(json.dumps(res, indent=2))
    if not wrote:
        print(
            "FAILED:b8-rollback-cost producer wrote no index -- cost is not the blocker"
        )
        return 1
    print("SUCCESS:b8-rollback-cost")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
