#!/usr/bin/env python3
"""Probe 2: both-states on the census detector (mechanically independent of probe 1).

Does not read fixtures/registry.json or fixtures/ledger.json.
Constructs in-memory twins, executes a genuine control, and requires:
  * observed-FAILING control → covered, no manual override
  * planted missing path → flagged, not covered
  * pass-only observation → not covered
A detector that is silent in both states (or always-on) is rejected.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402

ART = REPO / "command-center/receipts/TST-0327.json"
GENUINE = HERE / "fixtures" / "controls" / "genuine_failing.py"
PASS_ONLY = HERE / "fixtures" / "controls" / "pass_only.py"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0327-probe2 {msg}")
    return 1


def check_artifact_if_present() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0327" not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    both = doc.get("both_states") or {}
    if both.get("covered_on_observed_failing") is not True:
        return "artifact both_states missing covered_on_observed_failing"
    if both.get("not_covered_on_planted_missing") is not True:
        return "artifact both_states missing not_covered_on_planted_missing"
    return None


def run_control(path: Path, *, suite_id: str, control_id: str) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    rel = path.relative_to(REPO).as_posix()
    outcome = "FAIL" if proc.returncode != 0 else "PASS"
    raw = ((proc.stdout or "") + (proc.stderr or "")).strip()
    run_id = "run-" + hashlib.sha256(f"{rel}:{outcome}:{proc.returncode}".encode()).hexdigest()[:12]
    return {
        "run_id": run_id,
        "suite_id": suite_id,
        "control_id": control_id,
        "control_path": rel,
        "outcome": outcome,
        "exit_code": proc.returncode,
        "output_tail": raw[-400:],
    }


def suite(sid: str, control_path: str, control_id: str) -> dict:
    return {
        "id": sid,
        "path": f"virtual/{sid}.py",
        "tests": 1,
        "negative_control": {"id": control_id, "path": control_path},
    }


def main() -> int:
    art_err = check_artifact_if_present()
    if art_err:
        return fail(art_err)

    if not GENUINE.is_file() or not PASS_ONLY.is_file():
        return fail("control artifacts missing")

    fail_obs = run_control(GENUINE, suite_id="live.covered", control_id="genuine_failing")
    pass_obs = run_control(PASS_ONLY, suite_id="live.pass-only", control_id="pass_only")
    if fail_obs["outcome"] != "FAIL":
        return fail(f"genuine control did not FAIL: {fail_obs}")
    if pass_obs["outcome"] != "PASS":
        return fail(f"pass-only control did not PASS: {pass_obs}")

    genuine_rel = GENUINE.relative_to(REPO).as_posix()
    pass_rel = PASS_ONLY.relative_to(REPO).as_posix()
    ghost_rel = "command-center/p2-wave/probes/TST-0327/fixtures/controls/NO-SUCH-CONTROL.py"

    good_reg = {
        "suites": [suite("live.covered", genuine_rel, "genuine_failing")],
    }
    good_led = {"runs": [fail_obs]}
    good = C.census(registry=good_reg, ledger=good_led, repo=REPO)

    bad_reg = {
        "suites": [suite("live.ghost", ghost_rel, "ghost")],
    }
    bad = C.census(registry=bad_reg, ledger={"runs": []}, repo=REPO)

    silent_reg = {
        "suites": [suite("live.pass-only", pass_rel, "pass_only")],
    }
    silent = C.census(registry=silent_reg, ledger={"runs": [pass_obs]}, repo=REPO)

    good_row = good["rows"][0]
    bad_row = bad["rows"][0]
    silent_row = silent["rows"][0]

    if not good_row["counts_as_covered"]:
        return fail("observed-failing suite was not covered without manual intervention")
    if good_row["bucket"] != C.OBSERVED_FAILING:
        return fail(f"good bucket={good_row['bucket']}")
    gdecl = good_row["declarations"][0]
    if not gdecl.get("resolved_path") or not gdecl.get("run_id"):
        return fail("good state missing path+run_id")
    if gdecl["run_id"] != fail_obs["run_id"]:
        return fail("good run_id did not come from the live FAIL observation")

    if bad_row["counts_as_covered"]:
        return fail("planted missing path counted as covered")
    if not bad_row.get("planted_path_missing"):
        return fail("planted missing path not flagged")
    if bad_row["bucket"] != "declared_never_failed":
        return fail(f"bad bucket={bad_row['bucket']}")

    if silent_row["counts_as_covered"]:
        return fail("pass-only observation counted as covered")
    if silent_row["bucket"] != "declared_never_failed":
        return fail(f"silent bucket={silent_row['bucket']}")

    # Vacuous-detector traps: always-covered / never-covered.
    if good_row["counts_as_covered"] == bad_row["counts_as_covered"]:
        return fail("census silent in both states (or always-on)")
    if good["counts"]["observed_failing"] != 1 or bad["counts"]["observed_failing"] != 0:
        return fail("three-count covered bucket did not track both states")

    # Independence: this probe must not have opened the fixture registry.
    fixture_reg = C.FIXTURE_REGISTRY.read_text(encoding="utf-8")
    if "suite.planted-ghost" not in fixture_reg:
        return fail("fixture registry drifted; independence check cannot bind")
    if any(r["suite_id"] == "suite.planted-ghost" for r in good["rows"] + bad["rows"] + silent["rows"]):
        return fail("probe2 imported fixture suite ids; not independent")

    out = {
        "probe": "probe2-both-states",
        "unit_id": "TST-0327",
        "pass": True,
        "fired_on_bad": True,
        "silent_on_good": False,
        "covered_on_observed_failing": True,
        "not_covered_on_planted_missing": True,
        "not_covered_on_pass_only": True,
        "live_fail_run_id": fail_obs["run_id"],
        "live_fail_exit_code": fail_obs["exit_code"],
        "live_pass_run_id": pass_obs["run_id"],
        "independence": "in-memory twins; no fixtures/registry.json",
        "good_counts": good["counts"],
        "bad_counts": bad["counts"],
        "silent_counts": silent["counts"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "both-states covered_on_fail=True planted_not_covered=True "
        f"pass_only_not_covered=True live_fail_rc={fail_obs['exit_code']}"
    )
    print("SUCCESS:TST-0327-probe2 both-states: observed-failing covers; planted ghost does not")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
