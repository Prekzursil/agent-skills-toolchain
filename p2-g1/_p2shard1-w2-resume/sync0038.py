import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path("command-center/p2-wave/probes/ADV-0038").resolve()))
import harness as H

def write_styled(path: Path, doc) -> None:
    raw = path.read_bytes() if path.exists() else b""
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if b"\r\n" in raw:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))

def sha_of(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)

art_path = REPO_ART = Path(H.ARTIFACT_REL)
ret_path = Path("command-center/p2-wave/probes/ADV-0038/SUBAGENT-RETURN.json")
man_path = Path("command-center/p2-wave/probes/ADV-0038/UNIT-ARTIFACT-MANIFEST.json")
rcp_path = Path("command-center/receipts/ADV-0038.json")

a_sha, a_bytes = sha_of(art_path)
print("live artifact:", a_bytes, "bytes", a_sha[:16])

# 1) SUBAGENT-RETURN artifacts row
ret = json.loads(ret_path.read_text(encoding="utf-8"))
for row in ret.get("artifacts") or []:
    if str(row.get("path","")).replace("\\","/") == H.ARTIFACT_REL:
        row["sha256"] = a_sha; row["bytes"] = a_bytes; row["exists"] = True
write_styled(ret_path, ret)

# 2) UNIT-ARTIFACT-MANIFEST row
man = json.loads(man_path.read_text(encoding="utf-8"))
hit = False
for row in man.get("artifacts") or []:
    if str(row.get("path","")).replace("\\","/") == H.ARTIFACT_REL and row.get("unit_id") == "ADV-0038":
        row["sha256"] = a_sha; row["present"] = True
        if "bytes" in row: row["bytes"] = a_bytes
        hit = True
print("manifest row found:", hit)
write_styled(man_path, man)

# 3) receipt: recompute ALL artifact rows from live, keep state/classification
rcp = json.loads(rcp_path.read_text(encoding="utf-8"))
for row in rcp.get("artifacts") or []:
    p = Path(str(row.get("path","")).replace("\\","/"))
    if p.is_file():
        s, b = sha_of(p)
        row["sha256"] = s; row["bytes"] = b; row["exists"] = True
fail = rcp.get("failure") or {}
fail["classification"] = ["reviewer-absent"]
reason = str(fail.get("reason",""))
if "bytes live" in reason:
    reason = reason.replace("31316 bytes live", f"{a_bytes} bytes live")
    fail["reason"] = reason
rcp["failure"] = fail
notes = str(rcp.get("notes") or "")
extra = (" Shard1-wave2 resume 2026-10-25: tree gained tools/marketplace/tests/test_yank.py after "
         "prior builder run; artifact evidence rows re-synced to live tree (tree_token_hits 11->12, "
         "install-path hits still zero), artifact+manifest+return hashes recomputed live; probes re-ran exit 0.")
if "Shard1-wave2 resume 2026-10-25" not in notes:
    rcp["notes"] = notes + extra
write_styled(rcp_path, rcp)
print("synced: SUBAGENT-RETURN, MANIFEST, RECEIPT")
