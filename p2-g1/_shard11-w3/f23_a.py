import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

home = Path.home()
REPO = home / "p2-g1"
PROBE_DIR = REPO / "command-center/p2-wave/probes/IMP-0223"
UID = "IMP-0223"
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
    ("probe1", "command-center/p2-wave/probes/IMP-0223/probe1_disjoint_indexes.py",
     "probe1-disjoint.raw.json"),
    ("probe2", "command-center/p2-wave/probes/IMP-0223/probe2_teardown_refused.py",
     "probe2-teardown.raw.json"),
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


def computed(pid):
    text = raws[pid][2]
    end = text.rfind("}")
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[: i + 1])
    return json.loads(text[: end + 1])
