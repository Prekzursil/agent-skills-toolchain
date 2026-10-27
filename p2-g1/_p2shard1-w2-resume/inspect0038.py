import json, sys
from pathlib import Path
sys.path.insert(0, str(Path("command-center/p2-wave/probes/ADV-0038").resolve()))
import harness as H
doc = json.loads(Path(H.ARTIFACT_REL).read_text(encoding="utf-8"))
prod = doc.get("production") or {}
print("production keys:", sorted(prod.keys()))
print("note has install-path:", str(prod.get("note","")).count("install-path"))
live = H.run_scenario()["production"]
art_meta = {m["source"]: m.get("revocation_fields") for m in doc.get("source_metadata") or []}
live_meta = {m["source"]: m["revocation_fields"] for m in H.run_scenario()["source_metadata"]}
print("meta equal:", art_meta == live_meta)
print("meta detail:", json.dumps({"art": art_meta, "live": live_meta}, indent=1))
raw = Path(H.ARTIFACT_REL).read_bytes()
print("first 120 bytes:", raw[:120])
print("ends with LF:", raw.endswith(b"\n"), "has CRLF:", b"\r\n" in raw)
