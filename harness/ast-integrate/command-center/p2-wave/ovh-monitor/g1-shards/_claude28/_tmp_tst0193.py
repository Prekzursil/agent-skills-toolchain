import json
import hashlib
from pathlib import Path

repo = Path(r"C:\Users\Prekzursil\source\ast-integrate")
d = repo / "command-center/p2-wave/probes/TST-0193"
sr = json.loads((d / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
print(sr["named_probes"][1]["raw_output"][1500:4000])
print("---- manifest vs live shas ----")
man = json.loads((d / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
for r in man["artifacts"]:
    p = repo / r["path"]
    if p.is_file():
        sha = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        status = "match" if sha == r["sha256"] else "MISMATCH live=%d want=%d" % (len(p.read_bytes()), r["bytes"])
        print(r["path"], status)
    else:
        print(r["path"], "MISSING")
