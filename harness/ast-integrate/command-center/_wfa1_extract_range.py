"""Extract candidates 1-32 (index order) from the prior archaeology registry
and mechanically verify every provenance anchor. Read-only on all sources.

Two independent existence signals per path:
  S1  os.path.exists / os.stat            (filesystem)
  S2  git cat-file -e <ref>:<path>        (mirror object db)  -- for mirror-held paths
Detector control: we deliberately probe a path we KNOW is absent and require
the probe to report absent, and a path we KNOW is present and require present.
"""

import hashlib
import json
import os
import subprocess
import sys

SRC = r"C:\Users\Prekzursil\.claude\harness-restore-20260806\08-WORKFLOW-CANDIDATE-REGISTRY.json"
MIRROR = r"C:\Users\Prekzursil\.claude\harness-restore-20260806\main-mirror.git"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"

with open(SRC, encoding="utf-8") as fh:
    data = json.load(fh)
cands = data["candidates"]
mine = cands[:32]

print(f"prior registry candidates total = {len(cands)}")
print(f"my range (index 0..31)          = {len(mine)}")
print()

# ---- detector control on the mirror -------------------------------------
mirror_ok = os.path.isdir(MIRROR)
print(f"[CTRL] mirror dir present: {mirror_ok}  ({MIRROR})")


def git(*args):
    return subprocess.run(
        ["git", "--git-dir", MIRROR, *args],
        capture_output=True,
        text=True,
    )


if mirror_ok:
    r = git("cat-file", "-t", REF)
    print(f"[CTRL] ref {REF[:12]} type={r.stdout.strip()!r} rc={r.returncode}")
    r_present = git("ls-tree", "-r", "--name-only", REF, "--", "workflows/")
    print(
        f"[CTRL] known-present probe ls-tree workflows/ -> {r_present.stdout.strip()!r}"
    )
    r_absent = git(
        "ls-tree", "-r", "--name-only", REF, "--", "definitely-not-a-real-dir-xyz/"
    )
    print(
        f"[CTRL] known-absent probe -> stdout={r_absent.stdout.strip()!r} "
        f"(must be empty for the detector to be trusted)"
    )
print()


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


rows = []
for i, c in enumerate(mine, start=1):
    prov = c.get("provenance", "")
    rec = {
        "n": i,
        "id": c["id"],
        "name": c["name"],
        "family": c["family"],
        "classification": c["classification"],
        "provenance_claim": prov,
        "fs_exists": None,
        "fs_bytes": None,
        "fs_mtime": None,
        "fs_sha256": None,
        "mirror_path": None,
        "mirror_exists": None,
        "mirror_bytes": None,
    }
    # filesystem probe for absolute windows paths
    if prov and (prov[1:3] == ":\\" or prov[1:3] == ":/"):
        p = prov
        rec["fs_exists"] = os.path.exists(p)
        if rec["fs_exists"] and os.path.isfile(p):
            st = os.stat(p)
            rec["fs_bytes"] = st.st_size
            rec["fs_mtime"] = (
                __import__("datetime")
                .datetime.fromtimestamp(st.st_mtime)
                .strftime("%Y-%m-%d")
            )
            rec["fs_sha256"] = sha(p)[:16]
    # mirror probe for "<sha>:path" or "repo path" shapes
    if ":" in prov and prov.startswith(("07f465f3", "repo ")):
        mp = prov.split(":", 1)[1] if prov.startswith("07f465f3") else None
        if mp:
            rec["mirror_path"] = mp
            r = git("cat-file", "-s", f"{REF}:{mp}")
            rec["mirror_exists"] = r.returncode == 0
            rec["mirror_bytes"] = int(r.stdout.strip()) if r.returncode == 0 else None
    rows.append(rec)

for r in rows:
    print(
        f"{r['n']:>3} {r['family']:<18} {r['id']:<44} "
        f"fs={r['fs_exists']} bytes={r['fs_bytes']} mtime={r['fs_mtime']} "
        f"mirror={r['mirror_exists']}/{r['mirror_bytes']}"
    )
    print(f"      prov: {r['provenance_claim'][:150]}")

with open("command-center/_wfa1_range_probe.json", "w", encoding="utf-8") as fh:
    json.dump({"rows": rows, "raw": mine}, fh, indent=2, ensure_ascii=False)
print("\nwrote command-center/_wfa1_range_probe.json")
sys.stdout.flush()
