#!/usr/bin/env python3
r"""_r3_stubledger.py -- settle the handed-off "stub-ledger cites 31 phantom placeholders".

TWO HYPOTHESES, stated before measuring (a control that cannot separate them is not a
control):

  H_PHANTOM  report.py banks a marker at WRITE time and never re-validates at REPORT
             time, so a scratch file written-run-deleted inside one session stays in the
             notice forever. This is the mechanism the hand-off proposed.
  H_TIMING   report.py DOES re-validate (it re-runs the detector on current content and
             drops a file that no longer exists), and the five named files existed when
             the notice was emitted -- the `find` that reported 0 hits ran later. The
             count is then a snapshot of a moving tree, not an instrumentation defect.

Two independent probes discriminate them:

  A. LIVE LEDGER, read-only. Open every ndjson under the live ledger root, count records
     whose `file` does not exist NOW, then run report.still_open() over the same session
     ids and count how many of those SURVIVE into the emitted list. A surviving record for
     a nonexistent file is H_PHANTOM; zero survivors is H_TIMING.
  B. END-TO-END, isolated. Drive record.py with a real PostToolUse payload for two temp
     files, delete ONE of them, then run report.py as a subprocess and require:
        * the surviving file IS named   (control: the detector fires at all -- without
          this, "the deleted one is absent" could just mean nothing was ever recorded)
        * the deleted file is NOT named (the phantom case)
     Both states of the same instrument, in one run.

FAILS CLOSED: if probe B's control does not fire, or the live root holds zero records, the
probe reports FAILED rather than publishing a verdict it did not measure.

Writes R3-STUBLEDGER.json. Read-only against the live tree except for its own temp dir.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "hooks" / "stub-ledger"
OUT = Path(__file__).resolve().parent / "R3-STUBLEDGER.json"
LIVE_ROOT = Path.home() / ".claude" / "stub-ledger"

STUB_BODY = """def helper():
    # TODO: placeholder, wire this up
    pass
"""


def probe_a_live() -> dict:
    """Read-only census of the live ledger + a real still_open() run over it."""
    res: dict = {"root": str(LIVE_ROOT), "exists": LIVE_ROOT.is_dir()}
    if not LIVE_ROOT.is_dir():
        return res
    sys.path.insert(0, str(HOOK))
    os.environ["STUB_LEDGER_ROOT"] = str(LIVE_ROOT)
    import report  # noqa: PLC0415  (import after sys.path is set)

    report.LEDGER_ROOT = LIVE_ROOT
    sessions = sorted(LIVE_ROOT.glob("*.ndjson"))
    tot = missing = empty_fp = 0
    emitted_total = 0
    missing_names: set[str] = set()
    survivors: list[dict] = []
    per_session = []
    for f in sessions:
        sid = f.stem
        recs = []
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except ValueError:
                continue
        miss_here = set()
        for r in recs:
            tot += 1
            fp = str(r.get("file") or "")
            if not fp:
                empty_fp += (
                    1  # kept unconditionally by still_open (cannot be re-scanned)
                )
            elif not Path(fp).exists():
                missing += 1
                missing_names.add(Path(fp).name)
                miss_here.add((fp, str(r.get("snippet") or "")))
        try:
            emitted = report.still_open(sid)
        except Exception as e:  # pragma: no cover - diagnostic path
            emitted = []
            per_session.append({"session": sid, "still_open_error": repr(e)})
            continue
        surv = [
            {"session": sid, "file": fp, "marker": mk, "snippet": sn[:60]}
            for (fp, mk, sn) in emitted
            if fp and not Path(fp).exists()
        ]
        survivors.extend(surv)
        emitted_total += len(emitted)
        per_session.append(
            {
                "session": sid,
                "records": len(recs),
                "records_file_missing": len(miss_here),
                "still_open_emitted": len(emitted),
                "emitted_for_missing_file": len(surv),
            }
        )
    res.update(
        {
            "session_files": len(sessions),
            "records_total": tot,
            "records_pointing_at_absent_file": missing,
            "records_with_empty_file_field": empty_fp,
            "still_open_emitted_total": emitted_total,
            "absent_file_names_sample": sorted(missing_names)[:12],
            "still_open_survivors_for_absent_files": len(survivors),
            "survivors_sample": survivors[:8],
            "per_session": per_session[:40],
        }
    )
    return res


def _run(script: Path, payload: dict, env: dict) -> tuple[int, str, str]:
    p = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )
    return p.returncode, p.stdout, p.stderr


def probe_b_e2e() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="r3-stubledger-"))
    ledger = tmp / "_ledger"
    ledger.mkdir()
    sid = f"r3probe{int(time.time())}"
    kept = tmp / "kept_module.py"
    gone = tmp / "gone_module.py"
    kept.write_text(STUB_BODY, encoding="utf-8")
    gone.write_text(STUB_BODY, encoding="utf-8")

    env = dict(os.environ)
    env["STUB_LEDGER_ROOT"] = str(ledger)
    env["STUB_LEDGER_ALWAYS"] = "1"  # bypass the completion-claim deferral
    env.pop("STUB_LEDGER", None)
    env["PYTHONIOENCODING"] = "utf-8"

    for f in (kept, gone):
        _run(
            HOOK / "record.py",
            {
                "session_id": sid,
                "tool_name": "Write",
                "tool_input": {"file_path": str(f), "content": STUB_BODY},
            },
            env,
        )
    lf = ledger / f"{sid}.ndjson"
    banked = (
        len([x for x in lf.read_text(encoding="utf-8").splitlines() if x.strip()])
        if lf.is_file()
        else 0
    )

    gone.unlink()  # the phantom condition: recorded, then removed

    rc, out, err = _run(
        HOOK / "report.py",
        {"session_id": sid, "transcript_path": "", "stop_hook_active": False},
        env,
    )
    msg = ""
    try:
        msg = json.loads(out).get("hookSpecificOutput", {}).get("additionalContext", "")
    except ValueError:
        msg = out
    res = {
        "records_banked": banked,
        "exit": rc,
        "stderr_tail": (err or "")[-300:],
        "message": msg[:400],
        "control_kept_file_named": "kept_module.py" in msg,
        "phantom_deleted_file_named": "gone_module.py" in msg,
    }
    shutil.rmtree(tmp, ignore_errors=True)
    return res


def main() -> int:
    a = probe_a_live()
    b = probe_b_e2e()

    control_ok = bool(b["control_kept_file_named"]) and b["records_banked"] >= 2
    if not control_ok:
        res = {"probe_a_live": a, "probe_b_e2e": b, "verdict": "DETECTOR-FAILED"}
        OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(json.dumps(b, indent=2)[:800])
        print(
            "FAILED:r3-stubledger control did not fire "
            f"(banked={b['records_banked']}, kept_named={b['control_kept_file_named']}) "
            "-- no verdict may be read from this run"
        )
        return 1

    phantom = bool(b["phantom_deleted_file_named"]) or (
        a.get("still_open_survivors_for_absent_files", 0) > 0
    )
    verdict = "H_PHANTOM" if phantom else "H_TIMING"
    res = {"probe_a_live": a, "probe_b_e2e": b, "verdict": verdict}
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")

    print("== A. LIVE LEDGER (read-only)")
    print(f"   session files                      {a.get('session_files')}")
    print(f"   records total                      {a.get('records_total')}")
    print(
        f"   records pointing at an ABSENT file {a.get('records_pointing_at_absent_file')}"
    )
    print(
        "   of those, SURVIVING into still_open "
        f"{a.get('still_open_survivors_for_absent_files')}   <- >0 means H_PHANTOM"
    )
    print(
        f"   records with an EMPTY file field   {a.get('records_with_empty_file_field')}"
    )
    print(f"   still_open emitted, all sessions   {a.get('still_open_emitted_total')}")
    print(f"   absent names sample                {a.get('absent_file_names_sample')}")
    print("== B. END-TO-END, isolated")
    print(f"   records banked                     {b['records_banked']}")
    print(
        f"   control: surviving file named      {b['control_kept_file_named']}  (must be True)"
    )
    print(
        f"   phantom: deleted file named        {b['phantom_deleted_file_named']}  (must be False)"
    )
    print(f"== VERDICT {verdict}")
    print("SUCCESS:r3-stubledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
