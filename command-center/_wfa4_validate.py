"""Independent readback validator for workflow-candidates-4.json.

Reads the FILE ON DISK (not the generator's memory), re-resolves every provenance anchor
against the filesystem and the bare mirror, and checks the spec's countable rules.
Ends with a BOTH-STATES control: a deliberately corrupted in-memory copy must FAIL.
"""

import json
import pathlib
import re
import subprocess
import sys

OUT = pathlib.Path(
    r"C:/Users/Prekzursil/source/ast-integrate/platform/registry/workflow-candidates-4.json"
)
MIRROR = pathlib.Path(
    r"C:/Users/Prekzursil/.claude/harness-restore-20260806/main-mirror.git"
)
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"

VOCAB = {
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "TRANSLATE",
    "REPAIR",
    "EXTEND",
    "MERGE",
    "COMPOSE",
    "CLEAN-ROOM-REIMPLEMENT",
    "DISTILL",
    "SPECIALIZE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "RETIRE",
    "REJECT",
    "UNKNOWN-NEEDS-PROBE",
}
REQUIRED = [
    "id",
    "name",
    "registry_index",
    "provenance",
    "primary_anchor",
    "license",
    "license_source",
    "maintenance_state",
    "task_fit",
    "stages",
    "roles",
    "tools",
    "stop_rules",
    "failure_behaviour",
    "benchmark_evidence",
    "classification",
    "classification_basis",
    "distinctness",
]


def git(*a):
    r = subprocess.run(
        ["git", "--git-dir", str(MIRROR), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout or ""


def resolve(anchor):
    """Return (ok, detail) for a provenance anchor string.

    Accepts '<sha12>:<repo/path>[:LINE]' (mirror) and 'C:/abs/path[:LINE]' (live). For a
    mirror anchor the trailing ':LINE' must be split off BEFORE ls-tree, or the path never
    resolves -- that was a real bug in the first version of this validator, which reported
    19 false violations against a correct registry.
    """
    m = re.match(r"^([0-9a-f]{12}):(.+?)(?::(\d+))?$", anchor)
    if m and "/" in m.group(2):
        path, line = m.group(2), m.group(3)
        rc, o = git("ls-tree", "--name-only", REF, "--", path)
        if rc != 0 or o.strip() == "":
            return False, "mirror-path-missing"
        if line:
            rc2, blob = git("cat-file", "-p", f"{REF}:{path}")
            if rc2 != 0:
                return False, "mirror-blob-unreadable"
            total = blob.count("\n") + 1
            n = int(line)
            return (1 <= n <= total), f"mirror line {n} of {total}"
        return True, "mirror"
    # live path form  C:/...:LINE  or plain C:/...
    m2 = re.match(r"^([A-Za-z]:/.+?)(?::(\d+))?$", anchor)
    if m2:
        f = pathlib.Path(m2.group(1))
        if not f.is_file():
            return False, "missing-file"
        if m2.group(2):
            n = int(m2.group(2))
            total = f.read_text("utf-8", errors="replace").count("\n") + 1
            return (1 <= n <= total), f"line {n} of {total}"
        return True, "file"
    return False, "unparseable-anchor"


def check(rows):
    v = []
    slice_rows = [r for r in rows if not r.get("is_extension")]
    ext_rows = [r for r in rows if r.get("is_extension")]
    if len(slice_rows) != 32:
        v.append(f"COUNT: expected 32 spine-slice entries, got {len(slice_rows)}")
    ids = [r.get("id") for r in rows]
    if len(set(ids)) != len(ids):
        v.append(f"IDS: duplicates present ({len(ids) - len(set(ids))})")
    idx = [r.get("registry_index") for r in slice_rows]
    if sorted(idx) != list(range(97, 129)):
        v.append(
            f"INDEX: slice registry_index set is not 97..128 -> {sorted(idx)[:5]}..."
        )
    for r in ext_rows:
        if r.get("registry_index") in range(97, 129):
            v.append(
                f"{r.get('id')}: extension entry sits inside the 97-128 slice range "
                "(would double-count a spine position)"
            )
    # the countable deliverable: materially distinct candidates
    md = [r for r in rows if r.get("materially_distinct")]
    if len(md) < 32:
        v.append(f"MATERIALLY-DISTINCT: only {len(md)} of a required 32")
    for r in rows:
        rid = r.get("id", "<no id>")
        for k in REQUIRED:
            if k not in r:
                v.append(f"{rid}: missing required field '{k}'")
            elif r[k] in (None, "", [], {}):
                v.append(f"{rid}: empty required field '{k}'")
        c = r.get("classification")
        if c not in VOCAB:
            v.append(f"{rid}: classification '{c}' not in the 15-term vocabulary")
        blob = json.dumps(r)
        if "UNKNOWN - not yet measured" in blob or "SKELETON" in blob:
            v.append(f"{rid}: still carries skeleton placeholder text")
        pa = r.get("primary_anchor", "")
        ok, detail = resolve(pa)
        if not ok:
            v.append(f"{rid}: primary_anchor does not resolve ({pa} -> {detail})")
        for a in r.get("provenance", []):
            path = a.split(" :: ")[1] if " :: " in a else a
            path = path.split(" :: ")[0]
            ok2, d2 = resolve(path)
            if not ok2:
                v.append(f"{rid}: provenance anchor does not resolve ({path} -> {d2})")
        # every file:line citation inside anchored lists must point at a real line
        for k in ("stages", "stop_rules", "failure_behaviour", "benchmark_evidence"):
            for item in r.get(k, []):
                for cit in re.findall(r"\[([^\]]+:\d+)\]", item):
                    ok3, d3 = resolve(cit)
                    if not ok3:
                        v.append(f"{rid}: {k} citation unresolvable ({cit} -> {d3})")
    return v


rows = json.loads(OUT.read_text(encoding="utf-8"))
print(f"read back {OUT}")
print(f"  entries on disk = {len(rows)}")
viol = check(rows)
print(f"  violations = {len(viol)}")
for x in viol[:25]:
    print("   -", x)

md = sum(1 for r in rows if r.get("materially_distinct"))
print(f"\n  materially_distinct = {md} of {len(rows)}")
from collections import Counter  # noqa: E402

print("  classifications:", dict(Counter(r["classification"] for r in rows)))
print(
    "  reclassified vs prior registry:",
    sum(1 for r in rows if r.get("classification_changed")),
)
print(
    "  undeployed (mirror-only):",
    [r["name"] for r in rows if "MIRROR-ONLY" in r["deployment_state"]],
)
print("  UNDECLARED license:", sum(1 for r in rows if r["license"] == "UNDECLARED"))
cits = sum(
    len(re.findall(r"\[([^\]]+:\d+)\]", item))
    for r in rows
    for k in ("stages", "stop_rules", "failure_behaviour", "benchmark_evidence")
    for item in r.get(k, [])
)
print(f"  resolvable file:line citations across anchored fields = {cits}")

print("\n=== BOTH-STATES CONTROL: corrupt a copy, the validator must FIRE ===")
bad = json.loads(json.dumps(rows))
bad[0]["classification"] = "TOTALLY-MADE-UP"
bad[1]["primary_anchor"] = "C:/Users/Prekzursil/does-not-exist-9f2a.md"
bad[2]["stop_rules"] = ["fake  [C:/Users/Prekzursil/nope.md:9999]"]
del bad[3]["license_source"]
bad.pop(4)  # remove a SPINE-slice entry so the COUNT and INDEX checks are exercised too
bad[-1]["registry_index"] = 100  # push the extension into the slice range
bv = check(bad)
for must in ("COUNT", "INDEX", "MATERIALLY-DISTINCT"):
    assert any(x.startswith(must) for x in bv), (
        f"control did not exercise the {must} check"
    )
print(f"  violations on the corrupted copy = {len(bv)} (must be > 0)")
for x in bv[:6]:
    print("   -", x)
assert bv, "DETECTOR FAILURE: validator is silent on a known-broken input"

print()
if viol:
    print(f"FAILED:wfa4-validate {len(viol)} violation(s)")
    sys.exit(1)
print(
    "SUCCESS:wfa4-validate 32/32 entries, 0 violations, control fired on the broken copy"
)
