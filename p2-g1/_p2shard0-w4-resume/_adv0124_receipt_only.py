import json
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
PROBE_DIR = HOME / "p2-g1/command-center/p2-wave/probes/ADV-0124"
LOG_DIR = HOME / "p2-g1/_p2shard0-w4-resume"

def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

def save(p, doc):
    Path(p).write_text(
        json.dumps(doc, indent=1, sort_keys=False) + "\n",
        encoding="utf-8", newline="\n",
    )

ret_path = PROBE_DIR / "SUBAGENT-RETURN.json"
ret = load(ret_path)
for np in ret.get("named_probes", []):
    pid = np.get("id")
    name = "probe1_four_state_matrix" if pid == "probe1" else "probe2_signal_source_audit"
    raw = (LOG_DIR / ("_adv0124_" + name + ".posfix.log")).read_text(encoding="utf-8").strip()
    np["raw_output"] = raw
    np["exit_code"] = 0 if raw.splitlines()[-1].startswith("SUCCESS:") else 1
ext = ret.setdefault("extensions", {})
ext["w4s0_resume_2026-10-26"] = {
    "action": (
        "S4 suspend-drop race closed in engine.py (win32): scenario_s4 now "
        "re-verifies proc state T immediately before the classify read and "
        "re-arms (re-suspend + bounded re-wait) if psutil's "
        "suspended-enumeration flapped; a live fleet re-run had misread the "
        "suspended worker as 'R' (cpu_delta 0, never ran) and probe2 failed "
        "'/proc did not separate S2 from S4'. Both named probes re-run green "
        "post-fix; manifest engine.py sha row rebuilt; primary artifact "
        "untouched (sha unchanged); receipt stays BLOCKED/reviewer-absent "
        "per program contract."
    ),
    "builder": "w4 shard-0 builder (resume of a mid-flight-dead prior attempt)",
}
ret["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
ret["notes"] = str(ret.get("notes", "")) + (
    " W4S0 resume 2026-10-26: S4 re-arm guard added to engine.py after one "
    "live probe2 failure (transient suspend-drop race, 3/3 green re-runs "
    "pre-fix); post-fix probes 2/2 green; manifest re-hashed; state stays "
    "BLOCKED/reviewer-absent."
)
save(ret_path, ret)
print("receipt refreshed:", ret.get("status"), ret.get("state"), ret.get("failure", {}).get("classification"))
