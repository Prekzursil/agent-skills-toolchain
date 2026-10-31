"""Fix the guard by direct line insertion + LF-convert ARC-0048 artifact."""
import hashlib
import io
import json
import os

REPO = r"C:/Users/Prekzursil/p2-g1"

# 1. guard: insert right after the rec load in close_unit
P = os.path.join(REPO, "_rev2-w2-shard2", "close_shard2_w2.py")
src = io.open(P, encoding="utf-8").read()
guard = (
    '    if (rec.get("state") == "SUCCESS"\n'
    '            and (rec.get("extensions") or {}).get("reviewer_closure")):\n'
    '        print(uid + ": already closed by this reviewer; skipping")\n'
    "        return [], [], None\n"
    "    b = BATTERY[uid]\n"
)
assert "    b = BATTERY[uid]\n" in src, "anchor missing"
src = src.replace("    b = BATTERY[uid]\n", guard, 1)
assert "already closed by this reviewer" in src
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("guard inserted")

# 2. LF-convert ARC-0048 artifact (normalized-sha invariant)
ART = os.path.join(REPO, "command-center", "phase3", "A7", "SECURITY.json")
raw = open(ART, "rb").read()
n = raw.count(b"\r\n")
assert n > 0, "no CRLF in SECURITY.json?"
norm = raw.replace(b"\r\n", b"\n")
sha_norm = hashlib.sha256(norm).hexdigest()
with open(ART, "wb") as fh:
    fh.write(norm)
back = open(ART, "rb").read()
assert back == norm and len(back) == 24237, (len(back), 24237)
man = json.load(open(os.path.join(REPO, "command-center", "p2-wave", "probes",
                                  "ARC-0048", "UNIT-ARTIFACT-MANIFEST.json"),
                     encoding="utf-8"))
prim = [x for x in man["artifacts"] if x.get("role") == "primary"][0]
ok = prim["sha256"] == sha_norm and prim["bytes"] == len(back)
print("ARC-0048 artifact: %d CRLF converted; raw=%d manifest_match=%s"
      % (n, len(back), ok))
assert ok
