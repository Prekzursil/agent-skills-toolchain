#!/usr/bin/env python3
"""TST-0169 probe 2: live cold resume (rebuild, kept small and direct).

Rails:
  (a) warm control: resume in this process generation passes;
  (b) cold run: a fresh subprocess with a minimal environment (no
      previous-session env traps; TEMP/TMP pointed at a fresh reboot-temp)
      resumes from durable_root/checkpoint.json;
  (c) detector control: a planted session-temp dependency must FAIL the
      cold resume (reboot cleared the session temp);
  (d) receipt agreement: negative control fired+silent; answer affirmative.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "TST-0169.json"
UID = "TST-0169"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def run_worker(durable_root: Path, workdir: Path, *, plant: bool = False):
    fresh_temp = workdir.parent / "reboot-temp"
    fresh_temp.mkdir(parents=True, exist_ok=True)
    env = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "PATH": os.environ.get("PATH", ""),
        "TEMP": str(fresh_temp),
        "TMP": str(fresh_temp),
        "TST0169_SESSION_TMP": "" if not plant else str(fresh_temp / "session-state.json"),
    }
    argv = [sys.executable, "-B", str(HERE / "cold_worker.py"), str(durable_root), str(workdir)]
    if plant:
        argv.append("--plant-temp-dependency")
    r = subprocess.run(argv, capture_output=True, text=True, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="tst-0169-p2-") as td:
        root = Path(td)
        durable_root = root / "durable"
        durable_root.mkdir()
        (durable_root / "checkpoint.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "cursor": {"node": "reduce", "index": 2},
                    "completed_unit_ids": ["IMP-0145", "IMP-0146"],
                },
                indent=2,
            )
        )

        # (a) warm control
        rc, out = run_worker(durable_root, root / "warm")
        if rc != 0:
            return fail(f"warm resume failed: {out.strip()[:140]}")

        # (b) cold run: the session temp is wiped before the run
        rc, out = run_worker(durable_root, root / "cold")
        if rc != 0:
            return fail(f"cold resume failed: {out.strip()[:140]}")
        resumed = json.loads((root / "cold" / "resumed.json").read_text(encoding="utf-8"))
        if resumed.get("resumed") is not True:
            return fail("cold run did not write its resume record")

        # (c) detector control: plant a session-temp dependency -> must fail
        rc_p, out_p = run_worker(durable_root, root / "planted", plant=True)
        if rc_p == 0:
            return fail("planted temp dependency did not fail the cold run")
        if "planted temp dependency is gone" not in out_p:
            return fail(f"planted run failed for the wrong reason: {out_p.strip()[:140]}")

    # (d) receipt agreement
    ncs = doc.get("negative_controls") or []
    if not ncs or ncs[0].get("fired_on_bad_state") is not True or ncs[0].get("silent_on_good_state") is not True:
        return fail("receipt negative control does not discriminate")
    ans = str(doc.get("answer") or "")
    if not ans.startswith("Yes"):
        return fail("receipt answer not affirmative")
    for t in doc.get("tests") or []:
        if t.get("result") != "PASS":
            return fail(f"receipt test row not PASS: {t.get('id')}")

    print(
        json.dumps(
            {
                "probe": "probe2-cold-resume",
                "unit_id": UID,
                "warm_ok": True,
                "cold_ok": True,
                "planted_fails_cold": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UID}-probe2 cold resume from durable state; temp plant fails cold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
