import json, sys, hashlib
from pathlib import Path
sys.path.insert(0, str(Path("command-center/p2-wave/probes/ADV-0038").resolve()))
import harness as H
art_path = Path(H.ARTIFACT_REL)
raw = art_path.read_bytes()
doc = json.loads(raw.decode("utf-8"))
live = H.run_scenario()["production"]["tree_token_hits"]
old = doc["production"].get("tree_token_hits")
print("old rows:", len(old or []), "-> new rows:", len(live or []))
doc["production"]["tree_token_hits"] = live
text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
data = text.replace("\n", "\r\n").encode("utf-8")
art_path.write_bytes(data)
sha = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
print("new bytes:", len(data), "new sha256(CRLF-normalized):", sha)
print("verification re-read parses:", bool(json.loads(art_path.read_bytes().decode("utf-8"))))
