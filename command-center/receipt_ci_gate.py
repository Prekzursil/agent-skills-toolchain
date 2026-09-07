r"""CI gate: wire receipt_validate.py into the command-center quality step.

Closes IMP-0435. Measured gap before this module: `grep -rn receipt_validate
.github/workflows/` returned ZERO hits, so an invalid or missing receipt under the
scoped path could never turn CI red. Exactly the green-not-live / gate-is-noop
failure class the catalog names.

What this gate does (each probe independently falsifiable):

  P1 wiring        `.github/workflows/quality.yml` must INVOKE this file (or
                   receipt_validate.py) on a non-comment line. A prose mention
                   does not count.
  P2 self-test     `receipt_validate.py --self-test` must pass (golden ACCEPT +
                   four mutants REJECT on distinct conditions).
  P3 scope-green   Every receipt listed in `receipt_ci_scope.json` must ADMIT.
                   An empty scope list is a HARD failure (no-op mode).
  P4 planted-red   Every planted invalid fixture must REJECT. A validator that
                   accepts the planted control is broken.
  P5 no-op-mode    Invoking receipt_validate with no paths and without
                   --self-test must exit nonzero. No --noop/--dry-run/--skip
                   flag may exist that exits 0 without validating.

usage:
    python command-center/receipt_ci_gate.py
    python command-center/receipt_ci_gate.py --json

Terminal: SUCCESS:receipt-ci-gate / FAILED:receipt-ci-gate <probe ids>
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(os.environ.get("RECEIPT_CI_REPO") or Path(__file__).resolve().parents[1])
GATE_REL = "command-center/receipt_ci_gate.py"
VALIDATOR_REL = "command-center/receipt_validate.py"
SCOPE_REL = "command-center/receipt_ci_scope.json"
WORKFLOW_REL = ".github/workflows/quality.yml"

# Flags that would turn the validator into a silent pass. None of these may be
# accepted by receipt_validate.py; P5 asserts that.
FORBIDDEN_NOOP_FLAGS = ("--noop", "--dry-run", "--skip", "--pass", "--allow-empty")


def _run(argv: list[str], cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        argv,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _load_scope() -> dict[str, Any]:
    path = REPO / SCOPE_REL
    if not path.is_file():
        raise SystemExit(f"FAILED:receipt-ci-gate missing scope file {SCOPE_REL}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:receipt-ci-gate scope is not an object")
    return doc


def probe_wiring() -> dict[str, Any]:
    """P1: quality.yml must invoke this gate or receipt_validate on a live line."""
    wf = REPO / WORKFLOW_REL
    body = io.open(wf, encoding="utf-8", newline="").read().replace("\r\n", "\n")
    live = [ln for ln in body.split("\n") if ln.strip() and not ln.lstrip().startswith("#")]
    joined = "\n".join(live)
    # Match an actual python invocation, not a comment leftover.
    patterns = [
        rf"python3?\s+{re.escape(GATE_REL)}",
        rf"python3?\s+{re.escape(VALIDATOR_REL)}",
    ]
    hit = any(re.search(p, joined) for p in patterns)
    return {
        "id": "P1-wiring",
        "ok": hit,
        "detail": "quality.yml invokes receipt_ci_gate or receipt_validate"
        if hit
        else "no live invocation of receipt_ci_gate.py / receipt_validate.py in quality.yml",
    }


def probe_self_test() -> dict[str, Any]:
    rc, out = _run([sys.executable, str(REPO / VALIDATOR_REL), "--self-test"])
    ok = rc == 0 and "SUCCESS:receipt-validate self-test" in out
    return {
        "id": "P2-self-test",
        "ok": ok,
        "returncode": rc,
        "detail": out.strip().splitlines()[-1] if out.strip() else "(empty)",
    }


def probe_scope_green(scope: dict[str, Any]) -> dict[str, Any]:
    receipts = scope.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        return {
            "id": "P3-scope-green",
            "ok": False,
            "detail": "scope.receipts is empty or missing — empty walk is a no-op, not a pass",
        }
    missing = [p for p in receipts if not (REPO / p).is_file()]
    if missing:
        return {
            "id": "P3-scope-green",
            "ok": False,
            "detail": f"scoped receipt(s) missing on disk: {missing}",
        }
    rc, out = _run([sys.executable, str(REPO / VALIDATOR_REL), *receipts])
    ok = rc == 0 and "REJECT:" not in out
    return {
        "id": "P3-scope-green",
        "ok": ok,
        "returncode": rc,
        "scoped_count": len(receipts),
        "detail": out.strip().splitlines()[-1] if out.strip() else "(empty)",
        "rejects": [ln for ln in out.splitlines() if ln.startswith("REJECT:")],
    }


def probe_planted_red(scope: dict[str, Any]) -> dict[str, Any]:
    planted = scope.get("planted_invalid")
    if not isinstance(planted, list) or not planted:
        return {
            "id": "P4-planted-red",
            "ok": False,
            "detail": "scope.planted_invalid is empty — both-states control cannot fire",
        }
    missing = [p for p in planted if not (REPO / p).is_file()]
    if missing:
        return {
            "id": "P4-planted-red",
            "ok": False,
            "detail": f"planted fixture(s) missing: {missing}",
        }
    rc, out = _run([sys.executable, str(REPO / VALIDATOR_REL), *planted])
    rejects = [ln for ln in out.splitlines() if ln.startswith("REJECT:")]
    accepts = [ln for ln in out.splitlines() if ln.startswith("ACCEPT:")]
    # Every planted fixture must REJECT; none may ACCEPT; exit must be nonzero.
    ok = rc != 0 and len(rejects) == len(planted) and not accepts
    return {
        "id": "P4-planted-red",
        "ok": ok,
        "returncode": rc,
        "reject_count": len(rejects),
        "accept_count": len(accepts),
        "detail": (
            f"{len(rejects)}/{len(planted)} planted fixtures REJECTED"
            if ok
            else f"planted control did not discriminate: rc={rc} rejects={len(rejects)} accepts={len(accepts)}"
        ),
        "rejects": rejects,
    }


def probe_noop_mode() -> dict[str, Any]:
    """P5: empty invocation fails; forbidden no-op flags must not be accepted as a silent pass."""
    rc_empty, out_empty = _run([sys.executable, str(REPO / VALIDATOR_REL)])
    empty_ok = rc_empty != 0 and "no input" in out_empty

    # Forbidden flags: argparse should reject unknown flags (rc!=0), and must not
    # print SUCCESS without validating anything.
    flag_results = []
    flags_ok = True
    for flag in FORBIDDEN_NOOP_FLAGS:
        rc, out = _run([sys.executable, str(REPO / VALIDATOR_REL), flag])
        # Acceptable: argparse error / unrecognized arguments (nonzero).
        # Unacceptable: exit 0 with a SUCCESS marker and no receipt checked.
        silent_pass = rc == 0 and (
            "SUCCESS:receipt-validate" in out or "ADMITTED" in out or out.strip() == ""
        )
        flag_results.append({"flag": flag, "returncode": rc, "silent_pass": silent_pass})
        if silent_pass:
            flags_ok = False

    # Also: help text must not advertise a skip/noop mode.
    help_rc, help_out = _run([sys.executable, str(REPO / VALIDATOR_REL), "--help"])
    help_leaks = [f for f in FORBIDDEN_NOOP_FLAGS if f in help_out]
    help_ok = help_rc == 0 and not help_leaks

    ok = empty_ok and flags_ok and help_ok
    return {
        "id": "P5-noop-mode",
        "ok": ok,
        "empty_invocation": {"returncode": rc_empty, "ok": empty_ok},
        "forbidden_flags": flag_results,
        "help_leaks": help_leaks,
        "detail": "empty walk fails and no silent-pass flag exists"
        if ok
        else "validator can be invoked in a mode that validates nothing",
    }


def run_all() -> dict[str, Any]:
    scope = _load_scope()
    probes = [
        probe_wiring(),
        probe_self_test(),
        probe_scope_green(scope),
        probe_planted_red(scope),
        probe_noop_mode(),
    ]
    failed = [p["id"] for p in probes if not p.get("ok")]
    return {
        "ok": not failed,
        "failed": failed,
        "probes": probes,
        "scope_path": SCOPE_REL,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    result = run_all()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for p in result["probes"]:
            mark = "OK" if p["ok"] else "FAIL"
            print(f"  {mark}:{p['id']}  {p.get('detail', '')}")
        if result["ok"]:
            print(
                "SUCCESS:receipt-ci-gate "
                f"{len(result['probes'])} probes green "
                "(wiring + self-test + scope ADMIT + planted REJECT + no-op refused)"
            )
        else:
            print(f"FAILED:receipt-ci-gate {' '.join(result['failed'])}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
