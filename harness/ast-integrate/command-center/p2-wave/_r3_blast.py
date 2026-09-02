"""Round-3 blast radius: does closing D1 and D2 move any verdict on an artifact that EXISTS?

A fix that silently re-classifies a sibling lane's delivered work is worse than the hole it
closes, so this is measured over every present artifact rather than argued. The PRE-fix predicate
is reconstructed from the COMMITTED blob at HEAD (read with `git ls-files -s` + `git cat-file -p`,
the stored-blob recipe -- never `git archive`, which converts EOL on Windows) and executed in a
throwaway module, so the comparison is against what actually shipped, not against my memory.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
REL = "command-center/ready_units.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sha = subprocess.run(
    ["git", "ls-files", "-s", REL], cwd=REPO, capture_output=True, text=True
).stdout.split()[1]
blob = subprocess.run(
    ["git", "cat-file", "-p", sha], cwd=REPO, capture_output=True
).stdout
tmp = Path(tempfile.mkdtemp(prefix="r3blast")) / "ready_units_head.py"
tmp.write_bytes(blob)
print(f"HEAD blob {sha[:12]}  {len(blob)} B  CR-bytes={blob.count(bytes([13]))}")

old = load(tmp, "ru_head")
new = load(REPO / REL, "ru_new")
# The HEAD copy resolves REPO from __file__, which now points at the temp dir. Repoint it, or the
# old predicate would report every artifact absent and "no movement" would be a measurement of
# nothing -- the detector failure this program keeps hitting.
old.REPO = REPO
print(f"old.REPO={old.REPO}  new.REPO={new.REPO}")

catalog = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
units = catalog["work_units"]
res_old, res_new = old._load_resolver(), new._load_resolver()

present, changed = 0, []
for u in units:
    p = u.get("output_path")
    if not p or not (REPO / p).exists() or (REPO / p).stat().st_size <= 0:
        continue
    present += 1
    a, why_a = old.artifact_delivered(u, res_old)
    b, why_b = new.artifact_delivered(u, res_new)
    if a != b:
        changed.append((u["id"], a, b, why_a, why_b))

print(f"\nartifacts present and non-empty: {present}")
print(f"verdict CHANGES under the round-3 fix: {len(changed)}")
for row in changed:
    print(f"  {row[0]}: {row[1]} -> {row[2]}   old={row[3][:40]!r} new={row[4][:60]!r}")

# The control: the fix MUST change a verdict somewhere, or it is inert. The known-broken states
# live in --self-test, but assert here that the same module rejects the exact bypass document.
META = "https://json-schema.org/draft/2020-12/schema"
bypass = {"$schema": META, "totally": "unrelated", "passing_tests": 999999}
print("\nCONTROL, same run, on the bypass document itself:")
print(f"  old instrument accepts it : {old.looks_like_schema_doc(bypass)}")
print(f"  new instrument accepts it : {new.looks_like_schema_doc(bypass, res_new)}")

ok = (
    len(changed) == 0
    and old.looks_like_schema_doc(bypass) is True
    and new.looks_like_schema_doc(bypass, res_new) is False
)
print(
    "\nSUCCESS:r3-blast the fix closes the bypass and moves 0 verdicts on present artifacts"
    if ok
    else "FAILED:r3-blast unexpected movement or an inert fix"
)
raise SystemExit(0 if ok else 1)
