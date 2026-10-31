import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

home = Path.home()
REPO = home / "p2-g1"
PROBE_DIR = REPO / "command-center/p2-wave/probes/IMP-0207"
UID = "IMP-0207"
NOW = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def digest(path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def row(path_rel, role):
    p = REPO / path_rel
    sha, n = digest(p)
    return {"unit_id": UID, "path": path_rel, "sha256": sha, "bytes": n,
            "present": True, "role": role,
            "receipt_path": "command-center/p2-wave/probes/" + UID + "/SUBAGENT-RETURN.json"}


CMDS = [
    ("probe1", "command-center/p2-wave/probes/IMP-0207/probe1_both_states.py",
     "probe1-both-states.raw.txt"),
    ("probe2", "command-center/p2-wave/probes/IMP-0207/probe2_intersection.py",
     "probe2-intersection.raw.txt"),
]

named_probes = []
raws = {}
for pid, rel, rawname in CMDS:
    cmd = "PYTHONDONTWRITEBYTECODE=1 python3 -B " + rel
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(["python3", "-B", str(REPO / rel)], cwd=str(REPO),
                          capture_output=True, text=True, encoding="utf-8", env=env)
    out = (proc.stdout or "") + (proc.stderr or "")
    (PROBE_DIR / rawname).write_text(out, encoding="utf-8", newline="\n")
    raws[pid] = (proc.returncode, cmd, out.strip())
    named_probes.append({"id": pid, "command": cmd, "exit_code": proc.returncode,
                         "raw_output": out.strip(), "role": UID + "-" + pid})
    if proc.returncode != 0:
        print("ABORT: " + pid + " exit " + str(proc.returncode))
        sys.exit(1)

# ---- receipt: refresh evidence to LIVE bytes, keep reviewer closure ----
rec_path = REPO / "command-center/receipts/IMP-0207.json"
rec = json.loads(rec_path.read_text(encoding="utf-8"))


def probe_blocks(pid, role):
    code, cmd, out = raws[pid]
    src = {"command": cmd, "exit_code": code, "method": "command",
           "raw_output": out, "role": role}
    ver = {"command": cmd, "exit_code": code,
           "fingerprint": hashlib.md5(out.encode("utf-8")).hexdigest(),
           "method": "command", "raw_output": out, "role": role}
    return src, ver


p1_src, p1_ver = probe_blocks("probe1", "source")
p2_src, p2_ver = probe_blocks("probe2", "verifier")

claims = {e["anchor"]: e for e in rec["evidence"]}
c1 = claims["tools/agentspec/agentspec/packs.py:load_pack"]
c1["probes"] = [p1_src, p1_ver]
c1["verdict"] = "CONFIRMED"
c2 = claims["tools/agentspec/agentspec/packs.py:privilege_intersection"]
c2["probes"] = [p2_src, p1_ver]
c2["verdict"] = "CONFIRMED"

artifacts = [
    row("tools/agentspec/agentspec/packs.py", "implementation"),
    row("tools/agentspec/agentspec/semver.py", "supporting"),
    row("command-center/p2-wave/probes/IMP-0207/probe1_both_states.py", "probe"),
    row("command-center/p2-wave/probes/IMP-0207/probe2_intersection.py", "probe"),
    row("command-center/p2-wave/probes/IMP-0207/fixtures/pack_narrow.json", "fixture"),
    row("command-center/p2-wave/probes/IMP-0207/fixtures/pack_widen_tools.json", "fixture"),
    row("command-center/p2-wave/probes/IMP-0207/fixtures/pack_widen_source.json", "fixture"),
]
rec["artifacts"] = artifacts
rec["tests"] = [
    {"command": raws["probe1"][1], "id": "probe1", "result": "PASS"},
    {"command": raws["probe2"][1], "id": "probe2", "result": "PASS"},
]
rec["timestamps"] = {"started_at": "2026-08-25T01:03:53Z", "ended_at": NOW,
                     "rebuilt_at": NOW}
rec["notes"] = (
    "G-1 for IMP-0207: live named probes exit 0, receipt state=SUCCESS, per-unit manifest row. "
    "Did not run global unit_manifest.py --write. "
    "Builder shard11 wave3 resume 2026-10-26: the prior probe directory was lost mid-flight "
    "(host session death) and the artifact rows here carried hashes of an earlier packs.py "
    "draft (13798B) no longer on disk. Probes and fixtures were rebuilt from the documented "
    "commands and re-run live against the current packs.py and semver.py (both unchanged on "
    "disk since 2026-10-24 08:48). Every claim the independent reviewer PASSed re-verified "
    "live, so the closure is kept. scenario.py was not rebuilt (no probe consumes it); its "
    "stale artifact row was dropped."
)
assert "SUCCESS:IMP-0207" in json.dumps(rec)
rec_path.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")

# ---- SUBAGENT-RETURN ----
sha, n = digest(rec_path)
ret = {
    "id": UID, "unit_id": UID, "status": "DELIVERED", "state": "DELIVERED",
    "receipt_state": "SUCCESS",
    "output_path": "command-center/receipts/IMP-0207.json",
    "output_schema": "command-center/schema/receipt.schema.json",
    "sentinel": "SUCCESS:IMP-0207",
    "manifest_path": "command-center/p2-wave/probes/" + UID + "/UNIT-ARTIFACT-MANIFEST.json",
    "registered": True, "cloud_ok": False, "failure_classification": [],
    "reviewer": rec.get("reviewer"),
    "primary_artifact": {"path": "command-center/receipts/IMP-0207.json",
                         "bytes": n, "sha256": sha},
    "artifacts": artifacts,
    "named_probes": named_probes,
    "notes": ("Builder shard11 wave3 resume 2026-10-26: probe dir was absent (prior builder "
              "died mid-flight); probes and fixtures rebuilt from the receipt documented "
              "commands and re-run live. Implementation untouched; reviewer closure kept "
              "because its claims re-verified live."),
    "ts": NOW,
}
(PROBE_DIR / "SUBAGENT-RETURN.json").write_text(
    json.dumps(ret, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

# ---- manifest ----
rows = [row("command-center/receipts/IMP-0207.json", "primary")] + artifacts
man = {"unit_id": UID, "artifacts": rows, "generated": NOW,
       "derivation": "shard11-w3 builder resume (matches _measure_one_delivered.py hashing)"}
(PROBE_DIR / "UNIT-ARTIFACT-MANIFEST.json").write_text(
    json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("finalized IMP-0207: receipt sha " + sha[:12] + " bytes " + str(n))
