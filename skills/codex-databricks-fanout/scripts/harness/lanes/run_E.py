"""Program E orchestrator (driver).

Databricks-side functions built on the tested harness modules. Three collaboration points are
OPERATOR/agent actions performed BETWEEN calls, because local `gh`/`git` is a read-only PAT that
401s on write (use the GitHub MCP instead):
  * Step 3 collision re-check  -> mcp__github__list_pull_requests(owner, repo, state=open)
  * Step 5 local landing       -> mcp__github__create_pull_request(...)
  * the curated push is OUT-OF-BAND via engine.tokens (short-lived, single-repo token; wiring
    deferred). The node gets NO write token and only commits agent/ branches LOCALLY (R1).

R1 SUPERSEDES the earlier shape of this driver, in which the node pushed its own branches using a
WRITE-scoped `github_token` secret injected as GITHUB_TOKEN (then documented as "Program E
prereq 1"). That plumbing is deliberately gone: a long-lived write token materialised into a
48-way job-cluster environment is exactly the exposure R1 removes. Re-adding it is a security
regression, not a convenience.

Usage (the node needs NO write token — R1; the out-of-band curated push is a deferred engine step):
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

try:
    # `engine` is the backend-agnostic CSIE core (engine.verify = clauses 2-5, CSIE-DESIGN §4/§8).
    # It is NOT present in every checkout that carries this harness -- the skill mirror ships
    # harness/ + lanes/ without engine/ -- so the import is guarded and `_verdict` falls back to
    # the equally-complete harness.poll.classify. A hard import here would make the whole driver
    # unimportable in the mirror, which is how a module acquires zero test coverage.
    from engine import verify
except ImportError:
    verify = None


def run_cmd(argv):
    p = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
    )
    return p.returncode, p.stdout, p.stderr


def _dbfs(posix: str) -> str:
    return posix.replace("/dbfs/", "dbfs:/", 1)


def cancel_run(run_id, run_cmd=run_cmd) -> bool:
    """Stop a submitted Databricks run. Returns True when the cancel call succeeded.

    Killing the local poller does NOT stop the remote job. Measured 2026-07-26: a 3-unit
    coverage fan-out was stopped locally at ~5m with all artifacts already landed at 3m04s; the
    run stayed RUNNING and was still billing an r5d.2xlarge ~15 minutes later, found only by a
    manual sweep. At the configured concurrency of 48 that is a real cost exposure.

    Never raises — a failed cancel must not mask the interrupt that triggered it.
    """
    try:
        rc, _, _ = run_cmd(
            [
                "databricks",
                "jobs",
                "cancel-run",
                str(run_id),
                "--profile",
                RAIL["profile"],
            ]
        )
        return rc == 0
    except Exception:
        return False


def _verdict(state: str, unit, artifact_path: str | None) -> str:
    """Clauses 2-5 for ONE unit. Clause 1 (job terminal) is the CALLER's precondition.

    TWO complete gate implementations are live in this tree, so this selects by availability
    instead of claiming there is one:
      * `engine.verify.and_gate` (clauses 2-5; verdicts DONE/FAILED) -- the intended production
        path (CSIE-DESIGN §4/§8), used whenever the `engine` package is importable.
      * `harness.poll.classify` otherwise -- a SECOND, complete clause-1-5 implementation with a
        verdict vocabulary engine.verify does not have (it can return "UNKNOWN" for an unreadable
        artifact). It is NOT retired and nothing deprecates it: it lives at harness/poll.py:10 and
        is called from harness/poll.py:22 (`poll_once`) and e2e/smoke_2unit.py:97, where this whole
        submit->poll->harvest->gate loop is hand-duplicated. Migrating those two call sites onto
        engine.verify.and_gate is Roadmap work; until then do not assume a single gate.
        (Those three anchors were RE-DERIVED against this tree: the DBX-side copy of this note
        cited poll.py:8/:26 and smoke_2unit.py:51, which are its own unformatted line numbers and
        are wrong here.)
    Both delegate the same predicates in `harness.contract` (`and_gate_artifact`, `schema_valid`,
    `floor_for`), so the DONE/FAILED decision agrees; only the UNKNOWN verdict is exclusive to the
    fallback.
    """
    if verify is not None:
        return "DONE" if verify.and_gate(unit, artifact_path).ok else "FAILED"
    return poll.classify(state, unit, artifact_path)


def submit_and_gate(
    units, name, run_cmd=run_cmd, extra_env=None, timeout_s=None, poll_s=30
):
    """Build+upload+submit a batch, poll to terminal, harvest, apply the 5-clause gate: clause 1
    (job terminal) here, clauses 2-5 via `_verdict` (engine.verify.and_gate when importable, else
    harness.poll.classify -- see `_verdict`; both impls are live, neither is deprecated).
    Returns {uid: (verdict, local_path_or_None)}. The node writes {RESULT_DIR}/{uid}.md, so every
    unit's artifact basename must be {uid}.md and they must share one result dir (our convention).

    timeout_s=None (DEFAULT) => NO wall-clock cap: poll until the Databricks job reaches a terminal
    state (jobs always terminate; cluster autotermination is the backstop). Pass an explicit
    timeout_s ONLY to opt into a cap. A hard cap previously produced a FALSE-NEGATIVE `TIMEOUT` on a
    run whose artifacts were complete + gate-valid but whose cluster took >45min end-to-end
    (2026-07-24 e2e dogfood); large fan-out waves legitimately run for hours. Cost control on an
    interrupt is `cancel_run`, NOT the cap -- a cap that fires returns TIMEOUT and leaves the remote
    run billing."""
    result_posix = str(Path(units[0].artifact).parent).replace(
        "\\", "/"
    )  # /dbfs/tmp/<prog>/results
    root_posix = str(Path(result_posix).parent).replace("\\", "/")  # /dbfs/tmp/<prog>
    dbfs_result, dbfs_root = _dbfs(result_posix), _dbfs(root_posix)
    batch_posix = f"{root_posix}/batch.json"
    local = Path(__file__).resolve().parents[2] / "e2e" / f"_E_{name}"
    local.mkdir(parents=True, exist_ok=True)

    bp = build_batch.write_batch(
        build_batch.build_batch(units, name), local / "batch.json"
    )
    for d in (dbfs_root, dbfs_result):
        run_cmd(["databricks", "fs", "mkdirs", d, "--profile", RAIL["profile"]])
    run_cmd(
        [
            "databricks",
            "fs",
            "cp",
            str(bp),
            f"{dbfs_root}/batch.json",
            "--overwrite",
            "--profile",
            RAIL["profile"],
        ]
    )
    pf = local / "payload.json"
    pf.write_text(
        json.dumps(
            submit.build_payload(len(units), batch_posix, result_posix, extra_env),
            indent=2,
        ),
        encoding="utf-8",
    )
    run_id = submit.submit(pf, run_cmd)
    if not run_id:
        # Cluster/submit rejection (bad node type, DBU cap, dead auth). This used to return
        # all-FAILED SILENTLY, so a rejected cluster read as "48 units failed" and a whole
        # 6-shard chain flew past as 0/48 with no clue why. Say it loudly, once, and with a
        # verdict that cannot be confused with a unit that actually ran and failed its gate.
        print(
            f"[run_E:{name}] SUBMIT REJECTED — no run_id. Cluster/policy/auth rejected the "
            f"job; NOT a unit failure. Nothing ran. Check node_type vs the DBU cap and the "
            f"secret-scope auth token.",
            flush=True,
        )
        return {u.id: ("SUBMIT-FAILED", None) for u in units}
    print(f"[run_E:{name}] run_id={run_id} n={len(units)}")

    dest = local / "results"
    expected = {Path(u.artifact).name for u in units}

    def fetch(u) -> str | None:
        h = harvest.harvest(dbfs_result, dest, [u], run_cmd)
        p = dest / Path(u.artifact).name
        return str(p) if (h[u.id][0] == "harvested" and p.exists()) else None

    def landed_count():  # realtime: only THIS batch's expected artifacts (not stale siblings)
        rc, out, _ = run_cmd(
            ["databricks", "fs", "ls", dbfs_result, "--profile", RAIL["profile"]]
        )
        if rc != 0:
            return 0
        got = {ln.split("/")[-1].strip() for ln in out.splitlines()}
        return len(expected & got)

    def fmt(sec):
        m, s = divmod(int(sec), 60)
        return f"{m}m{s:02d}s"

    t0 = time.time()
    try:
        while timeout_s is None or time.time() - t0 < timeout_s:
            rc, out, _ = run_cmd(
                [
                    "databricks",
                    "jobs",
                    "get-run",
                    str(run_id),
                    "--profile",
                    RAIL["profile"],
                ]
            )
            state, msg = "?", ""
            try:
                st = json.loads(out).get("state") or {}
                state = st.get("life_cycle_state", "?")
                msg = (st.get("state_message", "") or "").strip()
            except json.JSONDecodeError:
                pass
            landed, elapsed = landed_count(), time.time() - t0
            phase = (
                msg[:44]
                if msg
                else ("spinning up cluster" if state == "PENDING" else "in run")
            )
            eta = (
                f" · eta ~{fmt((len(units) - landed) * (elapsed / landed))}"
                if 0 < landed < len(units)
                else ""
            )
            print(
                f"[run_E:{name}] {state} · {phase} · {landed}/{len(units)} landed · {fmt(elapsed)}{eta}",
                flush=True,
            )
            # clause 1 (job terminal) is the CALLER's precondition, checked HERE — neither
            # engine.verify nor `_verdict` re-checks it; `_verdict` covers clauses 2-5 only
            if state in poll._TERMINAL:
                for _ in range(3):  # grace re-harvest for DBFS eventual consistency
                    verdicts = {
                        u.id: (
                            _verdict(state, u, fetch(u)),
                            dest / Path(u.artifact).name,
                        )
                        for u in units
                    }
                    if all(v[0] == "DONE" for v in verdicts.values()):
                        break
                    time.sleep(20)
                done = sum(1 for v in verdicts.values() if v[0] == "DONE")
                print(
                    f"[run_E:{name}] === {done}/{len(units)} DONE · state={state} · {fmt(elapsed)} ==="
                )
                return verdicts
            time.sleep(poll_s)
    except (KeyboardInterrupt, SystemExit):
        # Killing the poller does NOT stop the remote job — see cancel_run.
        ok = cancel_run(run_id, run_cmd)
        print(
            f"[run_E:{name}] interrupted -> cancel run {run_id}: "
            f"{'sent' if ok else 'FAILED, cancel it manually'}. Artifacts already on DBFS are kept.",
            flush=True,
        )
        raise
    return {u.id: ("TIMEOUT", None) for u in units}


def node_preflight(run_cmd=run_cmd) -> tuple[bool, str, str]:
    """Step 1: submit the node behavioral preflight; gate on ultra-accepted AND bogus-rejected."""
    u = preflight_units.node_preflight_unit()
    # no cap; opt in via timeout_s
    verdicts = submit_and_gate([u], "preflight-node", run_cmd)
    verdict, path = verdicts[u.id]
    if verdict != "DONE" or path is None or not Path(path).exists():
        return False, "unknown", f"node preflight not DONE (verdict={verdict})"
    from harness import preflight

    return preflight.check_node_preflight(
        Path(path).read_text(encoding="utf-8", errors="replace")
    )


def runnability(repo, clone_url, run_cmd=run_cmd, extra_env=None):
    """Step 2: submit the runnability preflight; on DONE, parse the uncovered-file gaps.
    Returns (ok, gaps, artifact_text). The node proves a LOCAL commit works (commit_probe) — no
    push, no write token on the node (R1)."""
    u = preflight_units.runnability_unit(repo, clone_url)
    verdicts = submit_and_gate(
        [u], f"preflight-run-{repo}", run_cmd, extra_env=extra_env
    )
    verdict, path = verdicts[u.id]
    if verdict != "DONE" or path is None or not Path(path).exists():
        return False, [], ""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return True, preflight_units.parse_gaps(text), text


def run_coverage_fanout(repo, gaps, run_cmd=run_cmd):
    """Steps 3-4: one unit per gap, fanned out on the node (up to 48 concurrent), 5-clause gated.
    The node clones READ-ONLY and commits the agent/ branch LOCALLY (branch_ready); the curated
    out-of-band push is the engine adoption step (deferred). No write token on the node (R1).
    Returns {uid: (verdict, path)}.
    [operator] BEFORE calling: GitHub MCP list_pull_requests(state=open) -> abort if a coverage PR is live."""
    units = coverage.coverage_units(repo, gaps)
    if not units:
        print(f"[run_E] no gaps for {repo} -> nothing to fan out")
        return {}
    return submit_and_gate(units, f"coverage-{repo}", run_cmd)
