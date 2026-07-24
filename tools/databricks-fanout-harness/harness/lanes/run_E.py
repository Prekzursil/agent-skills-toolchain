"""Program E orchestrator (driver).

Databricks-side functions built on the tested harness modules. Three collaboration points are
OPERATOR/agent actions performed BETWEEN calls, because local `gh`/`git` is a read-only PAT that
401s on write (use the GitHub MCP instead):
  * Step 3 collision re-check  -> mcp__github__list_pull_requests(owner, repo, state=open)
  * Step 5 local landing       -> mcp__github__create_pull_request(...)
  * the node push itself uses the WRITE-scoped `github_token` secret (Program E prereq 1).

Usage (once the write github_token is in scope codex-harness-prekzursil):
    from harness.lanes import run_E
    ok, ver, msg = run_E.node_preflight()                 # Step 1  (no github needed)
    ok2, gaps, art = run_E.runnability("env-inspector",
                                       "https://github.com/Prekzursil/env-inspector")  # Step 2
    # [operator] GitHub MCP: abort if any open coverage PR
    verdicts = run_E.run_coverage_fanout("env-inspector", gaps)   # Step 3-4
    # [operator] GitHub MCP: open one PR from the green agent/ branches
"""
from __future__ import annotations
import json
import subprocess
import time
from pathlib import Path

from harness.contract import RAIL
from harness import build_batch, submit, poll, harvest
from harness.lanes import preflight_units, coverage


def run_cmd(argv):
    p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=1800)
    return p.returncode, p.stdout, p.stderr


def _dbfs(posix: str) -> str:
    return posix.replace("/dbfs/", "dbfs:/", 1)


def submit_and_gate(units, name, run_cmd=run_cmd, extra_env=None, timeout_s=None, poll_s=30):
    """Build+upload+submit a batch, poll to terminal, harvest, apply the 5-clause gate.
    Returns {uid: (verdict, local_path_or_None)}. The node writes {RESULT_DIR}/{uid}.md, so every
    unit's artifact basename must be {uid}.md and they must share one result dir (our convention).

    timeout_s=None (DEFAULT) => NO wall-clock cap: poll until the Databricks job reaches a terminal
    state (jobs always terminate; cluster autotermination is the backstop). Pass an explicit
    timeout_s ONLY to opt into a cap. A hard cap previously produced a FALSE-NEGATIVE `TIMEOUT` on a
    run whose artifacts were complete + gate-valid but whose cluster took >45min end-to-end
    (2026-07-24 e2e dogfood); large fan-out waves legitimately run for hours."""
    result_posix = str(Path(units[0].artifact).parent).replace("\\", "/")   # /dbfs/tmp/<prog>/results
    root_posix = str(Path(result_posix).parent).replace("\\", "/")          # /dbfs/tmp/<prog>
    dbfs_result, dbfs_root = _dbfs(result_posix), _dbfs(root_posix)
    batch_posix = f"{root_posix}/batch.json"
    local = Path(__file__).resolve().parents[2] / "e2e" / f"_E_{name}"
    local.mkdir(parents=True, exist_ok=True)

    bp = build_batch.write_batch(build_batch.build_batch(units, name), local / "batch.json")
    for d in (dbfs_root, dbfs_result):
        run_cmd(["databricks", "fs", "mkdirs", d, "--profile", RAIL["profile"]])
    run_cmd(["databricks", "fs", "cp", str(bp), f"{dbfs_root}/batch.json",
             "--overwrite", "--profile", RAIL["profile"]])
    pf = local / "payload.json"
    pf.write_text(json.dumps(submit.build_payload(len(units), batch_posix, result_posix, extra_env),
                             indent=2), encoding="utf-8")
    run_id = submit.submit(pf, run_cmd)
    if not run_id:
        return {u.id: ("FAILED", None) for u in units}
    print(f"[run_E:{name}] run_id={run_id} n={len(units)}")

    dest = local / "results"
    expected = {Path(u.artifact).name for u in units}

    def fetch(u):
        h = harvest.harvest(dbfs_result, dest, [u], run_cmd)
        p = dest / Path(u.artifact).name
        return p if (h[u.id][0] == "harvested" and p.exists()) else None

    def landed_count():   # realtime: only THIS batch's expected artifacts (not stale siblings)
        rc, out, _ = run_cmd(["databricks", "fs", "ls", dbfs_result, "--profile", RAIL["profile"]])
        if rc != 0:
            return 0
        got = {ln.split("/")[-1].strip() for ln in out.splitlines()}
        return len(expected & got)

    def fmt(sec):
        m, s = divmod(int(sec), 60)
        return f"{m}m{s:02d}s"

    t0 = time.time()
    while timeout_s is None or time.time() - t0 < timeout_s:
        rc, out, _ = run_cmd(["databricks", "jobs", "get-run", str(run_id), "--profile", RAIL["profile"]])
        state, msg = "?", ""
        try:
            st = json.loads(out).get("state") or {}
            state = st.get("life_cycle_state", "?")
            msg = (st.get("state_message", "") or "").strip()
        except json.JSONDecodeError:
            pass
        landed, elapsed = landed_count(), time.time() - t0
        phase = msg[:44] if msg else ("spinning up cluster" if state == "PENDING" else "in run")
        eta = f" · eta ~{fmt((len(units) - landed) * (elapsed / landed))}" if 0 < landed < len(units) else ""
        print(f"[run_E:{name}] {state} · {phase} · {landed}/{len(units)} landed · {fmt(elapsed)}{eta}",
              flush=True)
        if state in poll._TERMINAL:
            for _ in range(3):   # grace re-harvest for DBFS eventual consistency
                verdicts = {u.id: (poll.classify(state, u, fetch(u)), dest / Path(u.artifact).name)
                            for u in units}
                if all(v[0] == "DONE" for v in verdicts.values()):
                    break
                time.sleep(20)
            done = sum(1 for v in verdicts.values() if v[0] == "DONE")
            print(f"[run_E:{name}] === {done}/{len(units)} DONE · state={state} · {fmt(elapsed)} ===")
            return verdicts
        time.sleep(poll_s)
    return {u.id: ("TIMEOUT", None) for u in units}


def node_preflight(run_cmd=run_cmd) -> tuple[bool, str, str]:
    """Step 1: submit the node behavioral preflight; gate on ultra-accepted AND bogus-rejected."""
    u = preflight_units.node_preflight_unit()
    verdicts = submit_and_gate([u], "preflight-node", run_cmd)  # no cap; opt in via timeout_s
    verdict, path = verdicts[u.id]
    if verdict != "DONE" or path is None or not Path(path).exists():
        return False, "unknown", f"node preflight not DONE (verdict={verdict})"
    from harness import preflight
    return preflight.check_node_preflight(Path(path).read_text(encoding="utf-8", errors="replace"))


def runnability(repo, clone_url, run_cmd=run_cmd, extra_env=None):
    """Step 2: submit the runnability+push preflight; on DONE, parse the uncovered-file gaps.
    Returns (ok, gaps, artifact_text). Needs the write github_token for the push-probe half."""
    u = preflight_units.runnability_unit(repo, clone_url)
    verdicts = submit_and_gate([u], f"preflight-run-{repo}", run_cmd, extra_env=extra_env)
    verdict, path = verdicts[u.id]
    if verdict != "DONE" or path is None or not Path(path).exists():
        return False, [], ""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return True, preflight_units.parse_gaps(text), text


def run_coverage_fanout(repo, gaps, run_cmd=run_cmd, github_token_ref=None):
    """Steps 3-4: one unit per gap, fanned out on the node (up to 48 concurrent), 5-clause gated.
    Requires the write github_token so units can push to agent/ branches. Returns {uid: (verdict, path)}.
    [operator] BEFORE calling: GitHub MCP list_pull_requests(state=open) -> abort if a coverage PR is live."""
    token = github_token_ref or "{{secrets/codex-harness-prekzursil/github_token}}"
    units = coverage.coverage_units(repo, gaps)
    if not units:
        print(f"[run_E] no gaps for {repo} -> nothing to fan out")
        return {}
    return submit_and_gate(units, f"coverage-{repo}", run_cmd,
                           extra_env={"GITHUB_TOKEN": token})
