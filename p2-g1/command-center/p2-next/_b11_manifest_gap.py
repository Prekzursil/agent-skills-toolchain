"""Is manifest_registration.registered=false a per-unit oversight, or a systemic dead end?

H1 = these 10 units simply forgot to register; some tool sets registered=true and they can run it.
H2 = nothing in the repo can set it, so EVERY unit is blocked on it and R2 ("run render.py") is
     refuted.
Discriminating probe: (a) how many receipts anywhere carry registered=true, (b) does
ARTIFACT-MANIFEST.json list unit artifacts at all or only the charter docs, (c) does any tool
write the string.
"""

import json
import pathlib
import subprocess
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]


def git(*a):
    # errors="replace": a cp1252 default decode crashed on a 0x8f byte in the tree
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True)
    return r.stdout.decode("utf-8", errors="replace")


# (a) every receipt-shaped json on disk: what does registered say?
reg = Counter()
examples = {}
scanned = 0
for p in (ROOT / "command-center").rglob("*.json"):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        continue
    if not isinstance(d, dict) or "unit_id" not in d or "state" not in d:
        continue
    scanned += 1
    mr = d.get("manifest_registration")
    v = mr.get("registered") if isinstance(mr, dict) else mr
    reg[repr(v)] += 1
    examples.setdefault(repr(v), []).append(f"{d['unit_id']} @ {p.relative_to(ROOT)}")
print(f"(a) receipt-shaped files scanned: {scanned}")
for k, n in reg.most_common():
    print(f"    manifest_registration.registered={k:<8} : {n}   e.g. {examples[k][0]}")
true_rows = examples.get("True", [])
fixture_like = [x for x in true_rows if "fixture" in x or "_tmp" in x or "probes/" in x]
print(
    f"    of the registered=True rows, how many are FIXTURES not real receipts: "
    f"{len(fixture_like)}/{len(true_rows)}"
)
for x in true_rows:
    print(f"       True -> {x}")

# (b) what does ARTIFACT-MANIFEST.json actually contain?
man = json.loads(
    (ROOT / "command-center/ARTIFACT-MANIFEST.json").read_text(encoding="utf-8")
)
print(
    f"\n(b) ARTIFACT-MANIFEST.json top keys: {list(man.keys()) if isinstance(man, dict) else type(man)}"
)
entries = man.get("artifacts") or man.get("entries") or man
if isinstance(entries, list):
    paths = [e.get("path") if isinstance(e, dict) else e for e in entries]
elif isinstance(entries, dict):
    paths = list(entries.keys())
else:
    paths = []
print(f"    entries: {len(paths)}")
print(f"    first 8: {paths[:8]}")
unit_art = [
    p
    for p in paths
    if isinstance(p, str)
    and ("/audit/" in p or "/receipts/" in p or "/adversarial/" in p)
]
print(f"    entries that are UNIT receipts/artifacts: {len(unit_art)}")

# (c) does any tool ever write registered=true?
hits = git("grep", "-rn", "registered", "--", "tools", "platform", "scripts", ".github")
lines = [ln for ln in hits.splitlines() if "registered" in ln][:20]
print(
    f"\n(c) 'registered' occurrences in tools/ platform/ scripts/ .github/: {len(hits.splitlines())}"
)
for ln in lines:
    print("    ", ln[:160])

verdict = (
    "H2 SYSTEMIC -- no receipt anywhere carries registered=true and the manifest holds no "
    "unit artifacts, so no unit can satisfy the condition today"
    if reg.get("True", 0) == 0 and len(unit_art) == 0
    else "H1 -- some units DO register; the 10 are an oversight"
)
print(f"\nVERDICT: {verdict}")
(ROOT / "command-center/p2-next/REVIEW-MANIFEST-GAP.json").write_text(
    json.dumps(
        {
            "receipts_scanned": scanned,
            "registered_histogram": dict(reg),
            "manifest_entry_count": len(paths),
            "manifest_unit_artifact_entries": len(unit_art),
            "manifest_first_entries": paths[:13],
            "tool_grep_hits": len(hits.splitlines()),
            "verdict": verdict,
        },
        indent=2,
    ),
    encoding="utf-8",
)
print("SUCCESS:manifest-gap")
