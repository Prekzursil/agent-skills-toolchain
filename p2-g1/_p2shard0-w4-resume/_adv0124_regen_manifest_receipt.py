"""Refresh ADV-0124 manifest engine.py row + receipt after the S4 re-arm fix.

Keeps: status=DELIVERED, state=BLOCKED, failure.classification=["reviewer-absent"]
(contract: only the independent reviewer closes; the builder-authored probe2
closure stays demoted in extensions.prev_closure).
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "p2-g1"
PROBE_DIR = REPO / "command-center/p2-wave/probes/ADV-0124"
ENGINE_REL = "command-center/p2-wave/probes/ADV-0124/engine.py"
OUT_REL = "command-center/adversarial/ADV-0124-monitor-liveness-four-state-matrix.json"


def digest(path: Path):
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save(p, doc):
    Path(p).write_text(
        json.dumps(doc, indent=1, sort_keys=False) + "\n", encoding="utf-8", newline="\n"
    )


# --- manifest: re-hash engine.py row ---
man_path = PROBE_DIR / "UNIT-ARTIFACT-MANIFEST.json"
man = load(man_path)
sha, size = digest(REPO / ENGINE_REL)
hit = False
for row in man["artifacts"]:
    if str(row.get("path", "")).replace("\\", "/") == ENGINE_REL:
        row["sha256"] = sha
        row["bytes"] = size
        row["present"] = True
        row["exists"] = True
        row["eol"] = "LF"
        hit = True
if not hit:
    raise SystemExit("FAILED:engine row not found in manifest")
save(man_path, man)
print("manifest engine.py row ->", sha[:12], size)

# --- receipt: refresh probe raw outputs + add resume extension ---
ret_path = PROBE_DIR / "SUBAGENT-RETURN.json"
ret = load(ret_path)
probe_logs = {
    "probe1": PROBE_DIR.parent / "ADV-0124" / "probe1_four_state_matrix.py",
}
for np in ret.get("named_probes", []):
    pid = np.get("id")
    log = Path.home() / (
        "_p2shard0-w4-resume/_adv0124_"
        + ("probe1_four_state_matrix" if pid == "probe1" else "probe2_signal_source_audit")
        + ".posfix.log"
    )
    raw = log.read_text(encoding="utf-8").strip()
    np["raw_output"] = raw
    np["exit_code"] = 0 if "SUCCESS:" in raw.splitlines()[-1] else 1
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
notes = str(ret.get("notes", "")) + (
    " W4S0 resume 2026-10-26: S4 re-arm guard added to engine.py after one "
    "live probe2 failure (transient suspend-drop race, 3/3 green re-runs "
    "pre-fix); post-fix probes 2/2 green; manifest re-hashed; state stays "
    "BLOCKED/reviewer-absent."
)
ret["notes"] = notes
save(ret_path, ret)
print("receipt refreshed, state:", ret.get("state"), "status:", ret.get("status"))
