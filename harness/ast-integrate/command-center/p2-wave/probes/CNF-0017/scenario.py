"""Run the identical command set in loaded vs fresh isolated homes and diff."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checks as C  # noqa: E402
import profiles as P  # noqa: E402

RUN_CHECK = HERE / "run_check.py"


def classify(fid: str, loaded: str, fresh: str) -> str:
    if loaded == "FAIL" and fresh == "PASS":
        return "local-state-dependent"
    if loaded == "FAIL" and fresh == "FAIL":
        if fid.startswith("BL-POSIX"):
            return "platform"
        return "code-or-tree"
    if loaded == "PASS" and fresh == "FAIL":
        return "fresh-only"
    return "not-reproduced"


def command_set() -> list[dict]:
    argv_prefix = [sys.executable, "-B", str(RUN_CHECK)]
    return [{"id": cid, "argv": argv_prefix + [cid]} for cid in C.CHECK_IDS]


def run_one(env: dict[str, str], argv: list[str]) -> dict:
    p = subprocess.run(
        argv,
        cwd=str(HERE.parents[3]),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    payload = None
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = None
            break
    observed = p.returncode == 1
    if isinstance(payload, dict) and "outcome" in payload:
        outcome = str(payload["outcome"])
    else:
        outcome = "FAIL" if observed else ("PASS" if p.returncode == 0 else "FAIL")
    return {
        "exit_code": p.returncode,
        "outcome": outcome,
        "tail": text[-800:],
    }


def run_scenario() -> dict:
    C.ensure_tree_fixtures()
    homes = P.build_homes()
    if not homes["fresh"]["empty_at_start"]:
        raise SystemExit("FAILED:CNF-0017 fresh home not empty at start")
    cmds = command_set()
    loaded_env = P.profile_env(Path(homes["loaded"]["path"]), extra_bin=True)
    fresh_env = P.profile_env(Path(homes["fresh"]["path"]), extra_bin=False)
    rows = []
    for spec in cmds:
        loaded = run_one(loaded_env, spec["argv"])
        fresh = run_one(fresh_env, spec["argv"])
        lo, fo = loaded["outcome"], fresh["outcome"]
        rows.append(
            {
                "id": spec["id"],
                "argv": spec["argv"],
                "loaded_outcome": lo,
                "fresh_outcome": fo,
                "classification": classify(spec["id"], lo, fo),
                "loaded_exit": loaded["exit_code"],
                "fresh_exit": fresh["exit_code"],
                "loaded_tail": loaded["tail"],
                "fresh_tail": fresh["tail"],
            }
        )
    local_dep = [r["id"] for r in rows if r["classification"] == "local-state-dependent"]
    survived = [
        r["id"]
        for r in rows
        if r["classification"] in {"code-or-tree", "platform"}
    ]
    return {
        "homes": homes,
        "command_set": [{"id": c["id"], "argv": c["argv"]} for c in cmds],
        "failures": rows,
        "local_state_dependent": local_dep,
        "survived_fresh_profile": survived,
        "identical_command_set": True,
    }


def artifact_view(doc: dict) -> dict:
    """Merge report payload over the receipt so probes read one shape."""
    if not isinstance(doc, dict):
        return {}
    view = dict(doc)
    rpt = doc.get("report")
    if isinstance(rpt, dict):
        view.update(rpt)
    return view
