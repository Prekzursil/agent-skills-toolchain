r"""END-TO-END RED-PROOF for the CASUALTY lane integration.

The DoD asks for one executable check that would FAIL if the integration were missing, and for
that check to be SHOWN going red. This runs the SAME command against two trees that differ in
exactly one thing -- whether `.github/workflows/quality.yml` invokes the guard -- and requires
GREEN on one and RED on the other. A probe that is silent in both states measures nothing.

Four controls, all executed:

  C1  guard, real tree             expect rc 0 + SUCCESS:casualty-guard
  C2  guard, tree with the CI line deleted (path left in a COMMENT)
                                   expect rc 1 + FAILED:casualty-guard P1-wiring
  C3  suitefloor, floor raised above the observed count
                                   expect the registered `casualty` suite to FAIL
  C4  suitefloor, tests directory emptied
                                   expect a collected-NOTHING failure, not a silent pass

C2 uses `--skip-executed` so the ONLY difference between the two trees is the wiring; leaving
P6 in would also fail in the mirror (no git there) and the discrimination would be ambiguous.
C2 leaves the path in a comment on purpose: use-vs-mention is the failure this matcher exists
to resist, and a mutation that removed the string entirely would not test it.

usage: python command-center/casualty/integration_redproof.py [--json]
Terminal: SUCCESS:integration-redproof / FAILED:integration-redproof <failing control ids>
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(os.environ.get("CASUALTY_REPO") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(REPO / "command-center" / "casualty"))

import casualty_guard as cg  # noqa: E402  (needs the sys.path line above)

GUARD = REPO / "command-center" / "casualty" / "casualty_guard.py"
SUITEFLOOR = REPO / "tools" / "measure-guard" / "suitefloor.py"


def _run(argv: list[str], cwd: Path, env: dict | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env or {})},
    )
    return proc.returncode, proc.stdout + proc.stderr


def control_1_green() -> dict:
    rc, out = _run(
        [sys.executable, str(GUARD), "--skip-executed", "--allow-uncommitted-wiring"],
        REPO,
    )
    return {
        "id": "C1-green",
        "expectation": "rc 0 and SUCCESS:casualty-guard on the real tree",
        "returncode": rc,
        "marker": "SUCCESS:casualty-guard"
        if "SUCCESS:casualty-guard" in out
        else "(absent)",
        "ok": rc == 0 and "SUCCESS:casualty-guard" in out,
        "tail": out.strip().splitlines()[-1] if out.strip() else "",
    }


def control_2_red(tmp: Path) -> dict:
    """Same command, one difference: the CI invocation is gone."""
    mirror = cg._mirror(REPO, tmp / "no-wiring")
    wf = mirror / cg.WORKFLOW_REL
    body = io.open(wf, encoding="utf-8", newline="").read().replace("\r\n", "\n")
    kept = [
        ln
        for ln in body.split("\n")
        if not re.match(r"^\s*python\s+" + re.escape(cg.GUARD_REL), ln)
    ]
    kept.append(f"# the casualty guard lives at {cg.GUARD_REL}")
    wf.write_text("\n".join(kept), encoding="utf-8", newline="")

    rc, out = _run(
        [sys.executable, str(GUARD), "--skip-executed", "--allow-uncommitted-wiring"],
        REPO,
        env={"CASUALTY_REPO": str(mirror)},
    )
    fired = rc == 1 and "FAILED:casualty-guard P1-wiring" in out
    return {
        "id": "C2-red-no-ci-line",
        "expectation": "rc 1 and FAILED:casualty-guard P1-wiring when the CI line is deleted",
        "returncode": rc,
        "marker": "FAILED:casualty-guard P1-wiring"
        if "FAILED:casualty-guard P1-wiring" in out
        else "(absent)",
        "mention_left_in_a_comment": cg.GUARD_REL in "\n".join(kept),
        "ok": fired,
        "tail": out.strip().splitlines()[-1] if out.strip() else "",
    }


def _load_suitefloor(alias: str):
    """Load suitefloor.py by path.

    `sys.modules[alias] = mod` BEFORE exec_module is load-bearing, not tidiness: suitefloor
    declares `@dataclass(frozen=True)`, and on Python 3.14 `dataclasses._is_type` resolves the
    class's `__module__` through `sys.modules`. Without the registration that lookup returns
    None and the import dies with a bare AttributeError inside dataclasses -- a failure that
    reads like a bug in suitefloor rather than in the loader.
    """
    spec = importlib.util.spec_from_file_location(alias, SUITEFLOOR)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


def control_3_floor_raised() -> dict:
    """The declared floor must be able to fail, or it is decoration."""
    mod = _load_suitefloor("_sf_probe")
    suite = mod.suite_by_name("casualty")
    if suite is None:
        return {
            "id": "C3-floor-raised",
            "expectation": "the casualty suite is registered",
            "ok": False,
            "detail": "casualty is NOT in suitefloor.SUITES -- the enrolment did not land",
        }
    real_ok, observed, real_reason = mod.check_suite(suite, cwd=REPO)
    raised = mod.Suite(
        name=suite.name,
        path=suite.path,
        minimum=observed + 50,
        observed_when_set=observed + 50,
        note=suite.note,
    )
    bad_ok, _, bad_reason = mod.check_suite(raised, cwd=REPO)
    return {
        "id": "C3-floor-raised",
        "expectation": "green at the declared floor, RED when the floor is raised above observed",
        "registered": True,
        "observed": observed,
        "declared_floor": suite.minimum,
        "green_state": {"ok": real_ok, "reason": real_reason},
        "broken_state": {"ok": bad_ok, "reason": bad_reason},
        "ok": real_ok and not bad_ok,
    }


def control_4_empty_suite(tmp: Path) -> dict:
    """An empty collection must FAIL closed, never read as a pass."""
    mod = _load_suitefloor("_sf_probe2")
    fake = tmp / "emptyrepo"
    (fake / "command-center" / "casualty" / "tests").mkdir(parents=True)
    suite = mod.suite_by_name("casualty")
    ok, observed, reason = mod.check_suite(suite, cwd=fake)
    return {
        "id": "C4-empty-suite",
        "expectation": "a tests directory with no tests FAILS closed",
        "observed": observed,
        "reason": reason,
        "ok": not ok,
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    tmp = Path(tempfile.mkdtemp(prefix="casualty_redproof_"))
    try:
        controls = [
            control_1_green(),
            control_2_red(tmp),
            control_3_floor_raised(),
            control_4_empty_suite(tmp),
        ]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if not controls:  # fail closed
        print("FAILED:integration-redproof no controls ran")
        return 1

    if "--json" in argv:
        print(json.dumps(controls, indent=2))
    else:
        for c in controls:
            print(f"  {'PASS' if c['ok'] else 'FAIL'}  {c['id']}: {c['expectation']}")
            for key in ("returncode", "marker", "observed", "reason", "tail"):
                if key in c:
                    print(f"           {key}: {c[key]}")
            if "green_state" in c:
                print(f"           green : {c['green_state']}")
                print(f"           broken: {c['broken_state']}")

    failed = [c["id"] for c in controls if not c["ok"]]
    if failed:
        print(f"FAILED:integration-redproof {','.join(failed)}")
        return 1
    print(f"SUCCESS:integration-redproof {len(controls)} control(s) discriminate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
