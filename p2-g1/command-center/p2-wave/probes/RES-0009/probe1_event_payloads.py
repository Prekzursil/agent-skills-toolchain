#!/usr/bin/env python3
# RES-0009 probe1: event roster + verbatim payload capture (resume 2026-10-25).
# Two mechanically independent signals per claim family:
#  (a) snapshot-vs-receipt roster: the frozen cli/sdk snapshots re-parsed and
#      compared to the receipt lists (names must match exactly; drift empty);
#  (b) live logging-hook run: a protocol-faithful payload per event fed to the
#      logging hook; the stored capture must equal the fed bytes verbatim
#      (sha256 match) and carry hook_event_name.
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def fail(msg):
    print("FAILED:RES-0009-probe1 " + str(msg))
    return 1


def payload_for(event):
    return {"hook_event_name": event, "session_id": "res0009-probe",
            "cwd": str(REPO), "tool_name": "Bash" if event == "PreToolUse" else None,
            "prompt": "ping" if event == "UserPromptSubmit" else None}


def main():
    rec = json.loads((REPO / "command-center/research/RES-0009.json").read_text(encoding="utf-8"))
    st = str(rec.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared:" + st)
    cli = rec.get("cli_events") or []
    sdk = rec.get("sdk_events") or []
    if len(cli) != 31 or len(sdk) != 31:
        return fail("roster-count:" + str(len(cli)) + "/" + str(len(sdk)))
    # signal (a): snapshots re-parsed against the receipt
    cli_md = (HERE / "snapshots" / "cli-hooks.md").read_text(encoding="utf-8")
    sdk_md = (HERE / "snapshots" / "sdk-hooks.md").read_text(encoding="utf-8")
    def roster(md):
        out = []
        in_events = False
        for ln in md.splitlines():
            if ln.startswith("## Events"):
                in_events = True
            elif ln.startswith("## "):
                in_events = False
            elif in_events and ln.startswith("- "):
                out.append(ln[2:].strip())
        return out
    cli_snap = roster(cli_md)
    sdk_snap = roster(sdk_md)
    if cli_snap != cli:
        return fail("cli-snapshot-drift:" + str(len(cli_snap)))
    if sdk_snap != sdk:
        return fail("sdk-snapshot-drift:" + str(len(sdk_snap)))
    drift = rec.get("naming_drift") or {}
    if drift.get("cli_only") or drift.get("sdk_only") or not drift.get("shared"):
        return fail("receipt-drift-table-broken")
    print("roster: cli=31 sdk=31 shared=" + str(len(drift["shared"])) + " drift=empty")
    # signal (b): live logging hook, verbatim capture
    tmp = Path(tempfile.mkdtemp(prefix="res0009-p1-"))
    fed = {}
    for event in cli:
        raw = json.dumps(payload_for(event)).encode("utf-8")
        fed[event] = raw
    log = tmp / "captures.jsonl"
    env = dict(os.environ)
    ok_events = 0
    for event, raw in fed.items():
        env["RES0009_LOG"] = str(log) + "." + event + ".json"
        p = subprocess.run([sys.executable, "-B", str(HERE / "hooks" / "log_payload.py")],
                           input=raw, capture_output=True, env=env, timeout=120)
        cap = json.loads(Path(env["RES0009_LOG"]).read_text(encoding="utf-8"))
        if cap["stdin_sha256"] != hashlib.sha256(raw).hexdigest():
            return fail("capture-not-verbatim:" + event)
        if cap["verbatim"].get("hook_event_name") != event:
            return fail("capture-event-drift:" + event)
        ok_events += 1
    print("payload-capture: " + str(ok_events) + "/31 verbatim (sha256-verified, hook_event_name present)")
    if ok_events != 31:
        return fail("capture-count")
    print("SUCCESS:RES-0009-probe1 event-payloads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
