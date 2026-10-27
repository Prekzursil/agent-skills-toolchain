r"""H8 — PROVE the /rollback producer gap by firing BOTH sides.

commands/rollback.md promises "the edit-checkpoints PreToolUse hook snapshots the
pre-edit state once per turn" and tells the reader to open
  ~/.claude/checkpoints/<session_id>/index.ndjson

Asserting "no live hook writes that" is not proof. This fires both halves:

  CONSUMER SIDE  -- enumerate ~/.claude/checkpoints/. If /rollback has ever had
                    anything to read, records exist. Report count + newest mtime.
  PRODUCER SIDE  -- run hooks/edit-checkpoints/checkpoint.py (the REPO copy, the
                    one that is not deployed) against a synthetic Edit payload
                    into an ISOLATED checkpoint root, and show that it DOES
                    write index.ndjson.

That combination distinguishes the two hypotheses that a directory listing alone
cannot:
  H_broken : the producer is broken      -> firing it writes nothing
  H_unwired: the producer works, is dark -> firing it writes, live dir is empty

CONTROL: the isolated root is created empty and asserted empty first, so a
non-empty result cannot be pre-existing state.

Writes ONLY under command-center/hook-audit/_ckpt_probe/. The live
~/.claude/checkpoints tree is read, never written.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = REPO / "command-center" / "hook-audit"
LIVE_CKPT = Path.home() / ".claude" / "checkpoints"
LIVE_HOOK = Path.home() / ".claude" / "hooks" / "edit-checkpoints" / "checkpoint.py"
REPO_HOOK = REPO / "hooks" / "edit-checkpoints" / "checkpoint.py"
SANDBOX = OUT / "_ckpt_probe"


def consumer_side() -> dict:
    if not LIVE_CKPT.exists():
        return {"root_exists": False, "sessions": 0, "index_files": 0, "records": 0}
    sessions = [p for p in LIVE_CKPT.iterdir() if p.is_dir()]
    idx = list(LIVE_CKPT.rglob("index.ndjson"))
    recs = 0
    newest = None
    for f in idx:
        try:
            recs += sum(
                1 for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()
            )
            m = f.stat().st_mtime
            newest = m if newest is None or m > newest else newest
        except OSError:
            pass
    return {
        "root_exists": True,
        "root": str(LIVE_CKPT),
        "sessions": len(sessions),
        "index_files": len(idx),
        "records": recs,
        "newest_index_mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(newest))
        if newest
        else None,
    }


def producer_side() -> dict:
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    SANDBOX.mkdir(parents=True)
    before = list(SANDBOX.rglob("*"))
    assert not before, "sandbox not empty -- control failed"

    target = OUT / "_ckpt_target.txt"
    target.write_text("original content\n", encoding="utf-8")

    payload = json.dumps(
        {
            "session_id": "hookaudit-probe",
            "cwd": str(REPO),
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "original",
                "new_string": "edited",
            },
        }
    )
    env = dict(os.environ)
    env["EDIT_CHECKPOINTS_DIR"] = str(SANDBOX)
    env.pop("EDIT_CHECKPOINTS", None)

    t0 = time.perf_counter()
    p = subprocess.run(
        [sys.executable, str(REPO_HOOK)],
        input=payload.encode("utf-8"),
        capture_output=True,
        timeout=120,
        env=env,
    )
    ms = (time.perf_counter() - t0) * 1000

    after = sorted(
        str(q.relative_to(SANDBOX)).replace("\\", "/") for q in SANDBOX.rglob("*")
    )
    idx = list(SANDBOX.rglob("index.ndjson"))
    records = []
    for f in idx:
        for ln in f.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                try:
                    records.append(json.loads(ln))
                except Exception:
                    records.append({"UNPARSEABLE": ln[:120]})
    return {
        "hook_run_ms": round(ms, 1),
        "exit": p.returncode,
        "stderr_tail": p.stderr.decode("utf-8", "replace")[-300:],
        "sandbox_files": after,
        "index_written": bool(idx),
        "records": records,
    }


def deployment() -> dict:
    def man_names(p):
        m = json.loads(p.read_text(encoding="utf-8"))
        return {
            c.get("name")
            for blob in (m.get("events") or {}).values()
            for c in (blob or {}).get("checks") or []
        }

    repo_n = man_names(REPO / "hooks/_dispatch/manifest.json")
    live_n = man_names(Path.home() / ".claude/hooks/_dispatch/manifest.json")
    st = json.loads(
        (Path.home() / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    wired_in_settings = "edit-checkpoints" in json.dumps(st.get("hooks") or {})
    return {
        "script_present_live": LIVE_HOOK.is_file(),
        "in_repo_manifest": "edit-checkpoints" in repo_n,
        "in_live_manifest": "edit-checkpoints" in live_n,
        "in_live_settings_json": wired_in_settings,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    dep = deployment()
    cons = consumer_side()
    prod = producer_side()

    print("== DEPLOYMENT")
    for k, v in dep.items():
        print(f"   {k:24s} {v}")
    print("\n== CONSUMER SIDE (/rollback reads this)")
    for k, v in cons.items():
        print(f"   {k:24s} {v}")
    print("\n== PRODUCER SIDE (repo hook fired into an isolated root)")
    print(f"   exit={prod['exit']} in {prod['hook_run_ms']} ms")
    print(f"   index_written = {prod['index_written']}")
    print(f"   files: {prod['sandbox_files']}")
    for r in prod["records"]:
        print(f"   record: {json.dumps(r)[:220]}")
    if prod["stderr_tail"].strip():
        print(f"   stderr: {prod['stderr_tail'].strip()[:200]}")

    verdict = (
        "UNWIRED-BUT-WORKING"
        if prod["index_written"] and cons["records"] == 0
        else "PRODUCER-BROKEN"
        if not prod["index_written"]
        else "PRODUCING"
    )
    print(f"\n   VERDICT: {verdict}")
    (OUT / "H8-ROLLBACK-GAP.json").write_text(
        json.dumps(
            {"deployment": dep, "consumer": cons, "producer": prod, "verdict": verdict},
            indent=2,
        ),
        encoding="utf-8",
    )
    print("SUCCESS:h8-rollback-gap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
