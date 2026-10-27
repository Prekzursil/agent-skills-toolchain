"""Measure the THREE inbound-reference surfaces round 2 never scanned.

WHY THIS EXISTS. The lane's DoD question 3 is: "is anything POINTING at it -- a scheduled
task, a hook, a skill, a PATH entry, a config?" Round 2 scored that item PASS on the
strength of `classify_population.py`, whose SCAN_ROOTS/SCAN_FILES are config files only:
~/.claude/{hooks,skills,commands,workflows,agents,rules,plugins}, ~/.agents, ~/.codex,
~/.local/opt, plus seven named files. Windows Scheduled Tasks, the PATH, and the
environment are NOT in that corpus, so three of the five pointer kinds the DoD enumerates
were never measured -- and the 43 retire candidates were computed from that scan.

The error direction is the dangerous one: a checkout a scheduled task launches from would
be reported `inbound_exec = 0` and land in the retire list. The lane's own grounding names
this exact defect class ("a scheduled task registered against a disposable worktree").

The prior art's "0 scheduled-task hits across 330 task-actions" is NOT a substitute: it was
measured over the 25-checkout population, and the population is now 178. An inherited count
over a 7x smaller set cannot clear the larger one.

CONTROLS -- both states, per surface, and each one able to tell the two hypotheses apart:
    H1 "no scheduled task / PATH entry / env var names a checkout"
    H2 "the extractor cannot see that surface at all"
A silent surface supports H1 only if the SAME extractor fires when a known path is present.
So each surface is run twice: once over the real data, once over the real data plus ONE
synthetic row naming a real population path. The synthetic run MUST fire; the fabricated
path MUST NOT. Plus a plausibility floor on each surface (0 tasks / 0 PATH entries / 0 env
vars is a broken reader, not an empty box) -- fail closed.

The synthetic control row is built in this process's memory only. Nothing on the box is
written, no task is created, no environment variable is set, no credential is read for its
value: env vars are matched against population paths and only the VARIABLE NAME is ever
recorded.

Read-only. Writes one JSON report.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "inbound-surfaces.json"
POP_SRC = HERE / "identity-by-ancestry.json"

FABRICATED = "C:/Users/Prekzursil/source/this-path-does-not-exist-92f1a"

PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"',;<>|*?]{2,}")

# Plausibility floors. A reader that returns fewer than this is broken, not looking at an
# empty box -- fail closed rather than report a clean surface.
MIN_TASKS = 20
MIN_PATH_ENTRIES = 5
MIN_ENV_VARS = 10


def norm(p: str) -> str:
    return p.replace("\\\\", "/").replace("\\", "/").rstrip("/").rstrip('"').lower()


def ps_exe() -> str:
    for cand in ("pwsh", "powershell"):
        if shutil.which(cand):
            return cand
    raise RuntimeError("no PowerShell on PATH")


def ps_json(script: str) -> object:
    """Run a PowerShell snippet and parse its JSON stdout."""
    p = subprocess.run(
        [ps_exe(), "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    out = (p.stdout or "").strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


PS_TASKS = """
$rows = @()
foreach ($t in (Get-ScheduledTask)) {
  foreach ($a in $t.Actions) {
    $rows += [pscustomobject]@{
      TaskPath = [string]$t.TaskPath
      TaskName = [string]$t.TaskName
      State    = [string]$t.State
      Execute  = [string]$a.Execute
      Arguments= [string]$a.Arguments
      WorkDir  = [string]$a.WorkingDirectory
    }
  }
}
$rows | ConvertTo-Json -Depth 3 -Compress
"""

PS_ENV = """
$o = [ordered]@{}
foreach ($scope in @('Machine','User')) {
  $vars = [Environment]::GetEnvironmentVariables($scope)
  foreach ($k in $vars.Keys) { $o["$scope`::$k"] = [string]$vars[$k] }
}
$o | ConvertTo-Json -Depth 2 -Compress
"""


def as_list(v: object) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def hits_for(text: str, pop: set[str]) -> list[str]:
    """Population paths named by this text -- the path itself or anything under it."""
    if not text:
        return []
    found = set()
    for m in PATH_RE.findall(text):
        k = norm(m)
        for p in pop:
            if k == p or k.startswith(p + "/"):
                found.add(p)
    return sorted(found)


# --------------------------------------------------------------- surface extractors


def scan_tasks(rows: list[dict], pop: set[str]) -> list[dict]:
    out = []
    for r in rows:
        blob = " ".join(
            str(r.get(f) or "") for f in ("Execute", "Arguments", "WorkDir")
        )
        h = hits_for(blob, pop)
        if h:
            out.append(
                {
                    "task": f"{r.get('TaskPath', '')}{r.get('TaskName', '')}",
                    "state": r.get("State", ""),
                    "checkouts": h,
                }
            )
    return out


def scan_path(entries: list[str], pop: set[str]) -> list[dict]:
    out = []
    for e in entries:
        h = hits_for(e, pop)
        if h:
            out.append({"entry": e, "checkouts": h})
    return out


def scan_env(env: dict[str, str], pop: set[str]) -> list[dict]:
    """Match env VALUES against the population; record only the variable NAME."""
    out = []
    for name, val in env.items():
        h = hits_for(val or "", pop)
        if h:
            out.append({"var": name, "checkouts": h})
    return out


def main() -> int:
    paths = json.loads(POP_SRC.read_text(encoding="utf-8"))["all_checkout_paths"]
    pop = {norm(p) for p in paths}
    print(f"population: {len(paths)} checkouts ({len(pop)} normalised)")

    # A real population path, used to build the synthetic control row for every surface.
    control_path = sorted(pop)[0]
    for p in sorted(pop):
        if "ast-integrate" in p:
            control_path = p
            break
    print(f"control path (real, in population): {control_path}\n")

    report: dict = {"population": len(paths), "control_path": control_path}
    failed_controls: list[str] = []

    # ---------------------------------------------------------------- SCHEDULED TASKS
    raw = as_list(ps_json(PS_TASKS))
    rows = [r for r in raw if isinstance(r, dict)]
    n_exec = sum(1 for r in rows if (r.get("Execute") or "").strip())
    print(f"SCHEDULED TASKS: {len(rows)} action(s) read, {n_exec} with an Execute")
    if len(rows) < MIN_TASKS:
        print(
            f"FAILED:inbound-surfaces task reader returned {len(rows)} (< {MIN_TASKS})"
        )
        failed_controls.append("tasks-plausibility")
    real_tasks = scan_tasks(rows, pop)
    synth = rows + [
        {
            "TaskPath": "\\SSOT-CONTROL\\",
            "TaskName": "synthetic",
            "State": "Ready",
            "Execute": "python.exe",
            "Arguments": f"{control_path}/probe.py",
            "WorkDir": "",
        }
    ]
    synth_tasks = scan_tasks(synth, pop)
    fab_tasks = scan_tasks(
        rows
        + [
            {
                "TaskPath": "\\SSOT-CONTROL\\",
                "TaskName": "fab",
                "State": "Ready",
                "Execute": "python.exe",
                "Arguments": f"{FABRICATED}/probe.py",
                "WorkDir": "",
            }
        ],
        pop,
    )
    t_ok = len(synth_tasks) == len(real_tasks) + 1 and len(fab_tasks) == len(real_tasks)
    print(
        f"  CONTROL real={len(real_tasks)} +synthetic={len(synth_tasks)} "
        f"+fabricated={len(fab_tasks)}  discriminates: {t_ok}"
    )
    if not t_ok:
        failed_controls.append("tasks-both-states")
    for h in real_tasks:
        print(f"    HIT {h['task']} [{h['state']}] -> {h['checkouts']}")
    report["scheduled_tasks"] = {
        "actions_read": len(rows),
        "actions_with_execute": n_exec,
        "hits": real_tasks,
        "control": {
            "real": len(real_tasks),
            "with_synthetic": len(synth_tasks),
            "with_fabricated": len(fab_tasks),
            "discriminates": t_ok,
        },
    }

    # ------------------------------------------------------------------------- PATH
    pathvals = ps_json(
        "$m=[Environment]::GetEnvironmentVariable('Path','Machine');"
        "$u=[Environment]::GetEnvironmentVariable('Path','User');"
        "@{Machine=[string]$m;User=[string]$u} | ConvertTo-Json -Compress"
    )
    entries: list[str] = []
    if isinstance(pathvals, dict):
        for scope in ("Machine", "User"):
            for e in (pathvals.get(scope) or "").split(";"):
                if e.strip():
                    entries.append(e.strip())
    print(f"\nPATH: {len(entries)} entr(ies) across Machine+User")
    if len(entries) < MIN_PATH_ENTRIES:
        print(f"FAILED:inbound-surfaces PATH reader returned {len(entries)}")
        failed_controls.append("path-plausibility")
    real_path = scan_path(entries, pop)
    synth_path = scan_path(entries + [control_path.replace("/", "\\")], pop)
    fab_path = scan_path(entries + [FABRICATED.replace("/", "\\")], pop)
    p_ok = len(synth_path) == len(real_path) + 1 and len(fab_path) == len(real_path)
    print(
        f"  CONTROL real={len(real_path)} +synthetic={len(synth_path)} "
        f"+fabricated={len(fab_path)}  discriminates: {p_ok}"
    )
    if not p_ok:
        failed_controls.append("path-both-states")
    for h in real_path:
        print(f"    HIT {h['entry']} -> {h['checkouts']}")
    report["path"] = {
        "entries_read": len(entries),
        "hits": real_path,
        "control": {
            "real": len(real_path),
            "with_synthetic": len(synth_path),
            "with_fabricated": len(fab_path),
            "discriminates": p_ok,
        },
    }

    # ------------------------------------------------------------------ ENVIRONMENT
    envmap = ps_json(PS_ENV)
    env = {k: str(v) for k, v in envmap.items()} if isinstance(envmap, dict) else {}
    print(f"\nENV: {len(env)} variable(s) across Machine+User (values never recorded)")
    if len(env) < MIN_ENV_VARS:
        print(f"FAILED:inbound-surfaces env reader returned {len(env)}")
        failed_controls.append("env-plausibility")
    real_env = scan_env(env, pop)
    synth_env = scan_env({**env, "SSOT_CONTROL_SYNTHETIC": control_path}, pop)
    fab_env = scan_env({**env, "SSOT_CONTROL_FABRICATED": FABRICATED}, pop)
    e_ok = len(synth_env) == len(real_env) + 1 and len(fab_env) == len(real_env)
    print(
        f"  CONTROL real={len(real_env)} +synthetic={len(synth_env)} "
        f"+fabricated={len(fab_env)}  discriminates: {e_ok}"
    )
    if not e_ok:
        failed_controls.append("env-both-states")
    for h in real_env:
        print(f"    HIT ${h['var']} -> {h['checkouts']}")
    report["env"] = {
        "vars_read": len(env),
        "hits": real_env,
        "control": {
            "real": len(real_env),
            "with_synthetic": len(synth_env),
            "with_fabricated": len(fab_env),
            "discriminates": e_ok,
        },
    }

    # ------------------------------------------------------------------- roll-up
    newly = sorted(
        {c for h in real_tasks for c in h["checkouts"]}
        | {c for h in real_path for c in h["checkouts"]}
        | {c for h in real_env for c in h["checkouts"]}
    )
    report["checkouts_referenced_by_these_surfaces"] = newly
    report["controls_failed"] = failed_controls

    print(f"\n{'=' * 70}")
    print(f"  checkouts named by task/PATH/env : {len(newly)}")
    for c in newly:
        print(f"    {c}")

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwrote {OUT}")

    if failed_controls:
        print(f"FAILED:inbound-surfaces controls={','.join(failed_controls)}")
        return 3
    print(f"SUCCESS:inbound-surfaces surfaces=3 referenced={len(newly)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
