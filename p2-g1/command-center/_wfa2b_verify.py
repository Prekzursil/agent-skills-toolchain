"""Independent verification of platform/registry/workflow-candidates-2.json.

Deliberately does NOT import the builder. It re-reads the artifact off disk and
re-derives the load-bearing numbers from the ORIGINAL sources (bare mirror + live
trees), so a builder bug cannot certify itself.

Three parts:
  1. READ-BACK: count and shape, straight off disk.
  2. RE-DERIVATION: 6 spot-checked provenance anchors re-measured from source with a
     mechanically different probe than the builder used.
  3. MUTATION BATTERY: plant a violation of each contract check in a COPY and confirm
     the gate rejects it. A gate never shown to fail is a gate that measures nothing.
"""

from __future__ import annotations

import copy
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
ART = REPO / "platform" / "registry" / "workflow-candidates-2.json"
MIRROR = r"C:/Users/Prekzursil/.claude/harness-restore-20260806/main-mirror.git"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"

CLASSES = {
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
    "n",
    "id",
    "name",
    "family",
    "classification",
    "provenance",
    "license",
    "maintenance",
    "task_fit",
    "stages",
    "roles",
    "tools",
    "stop_rules",
    "failure_behaviour",
    "benchmark_evidence",
    "reusable_mechanisms",
    "prior_doc08",
    "verdict_basis",
]

failures: list[str] = []


def contract_gate(entries: list[dict]) -> list[str]:
    """This unit's registry contract. Deliberately SEPARATE from
    agent-self/harness/tests/test_register_gate.py:gate -- that gate validates the
    command-center register; this one validates a Phase-2A candidate registry. Different
    schema, different artifact, no shared surface to import.
    Returns a list of violations (empty == pass)."""
    v: list[str] = []
    if [e.get("n") for e in entries] != list(range(33, 65)):
        v.append("n not sequential 33..64")
    if len({e.get("id") for e in entries}) != len(entries):
        v.append("duplicate id")
    for e in entries:
        for k in REQUIRED:
            if k not in e or e[k] in (None, "", [], {}):
                v.append(f"{e.get('id')}: missing/empty {k}")
        if e.get("classification") not in CLASSES:
            v.append(f"{e.get('id')}: bad classification")
        p = e.get("provenance")
        if not isinstance(p, dict) or not p.get("anchor"):
            v.append(f"{e.get('id')}: no provenance anchor")
        elif not re.search(r"(/|\\|\.py|\.md|\.json)", str(p["anchor"])):
            v.append(f"{e.get('id')}: anchor not path-shaped")
        lic = e.get("license")
        if not isinstance(lic, dict) or not lic.get("source"):
            v.append(f"{e.get('id')}: license has no source")
        if not isinstance(e.get("maintenance"), dict) or not e["maintenance"].get(
            "state"
        ):
            v.append(f"{e.get('id')}: maintenance has no state")
    return v


# ------------------------------------------------------- 1. read-back off disk
print("=" * 78)
print("1. READ-BACK (straight off disk, no builder import)")
print("=" * 78)
if not ART.exists():
    print(f"FAILED: artifact absent at {ART}")
    sys.exit(1)
doc = json.loads(ART.read_text(encoding="utf-8"))
cands = doc["candidates"]
print(f"  path            : {ART}")
print(f"  bytes           : {ART.stat().st_size}")
print(f"  candidates      : {len(cands)}")
print(f"  declared count  : {doc['counts']['candidates']}")
print(f"  n range         : {min(c['n'] for c in cands)}..{max(c['n'] for c in cands)}")
print(f"  unique ids      : {len({c['id'] for c in cands})}")
by_fam: dict[str, int] = {}
for c in cands:
    by_fam[c["family"]] = by_fam.get(c["family"], 0) + 1
print(f"  by family       : {json.dumps(by_fam)}")
print(f"  by class        : {json.dumps(doc['counts']['by_classification'])}")

if len(cands) != 32:
    failures.append(f"expected 32 candidates on disk, found {len(cands)}")
if doc["counts"]["candidates"] != len(cands):
    failures.append("declared count disagrees with the array length")
base_violations = contract_gate(cands)
print(f"  gate on real doc: {len(base_violations)} violations")
if base_violations:
    failures.append(f"gate rejects the shipped artifact: {base_violations[:5]}")

# ------------------------------------------------- 2. independent re-derivation
print()
print("=" * 78)
print("2. RE-DERIVATION of 6 anchors, mechanically different probe")
print("=" * 78)


def git_out(*a: str) -> tuple[int, str]:
    p = subprocess.run(
        ["git", "--git-dir", MIRROR, *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.returncode, p.stdout


byid = {c["id"]: c for c in cands}

# (a) builder used `ls-tree -r --name-only`; verifier uses `cat-file -e` on a
#     specific blob -- a different plumbing command answering the same question.
rc, _ = git_out("cat-file", "-e", f"{REF}:tools/harness-corpus-mirror-ci")
rc_ctl, _ = git_out("cat-file", "-e", f"{REF}:tools/stdin-server/README.md")
print(
    f"  (a) cat-file -e {REF[:8]}:tools/harness-corpus-mirror-ci -> rc={rc} (expect non-zero = absent)"
)
print(f"      CONTROL known-present README.md               -> rc={rc_ctl} (expect 0)")
if rc == 0:
    failures.append(
        "phantom path claim REFUTED: tools/harness-corpus-mirror-ci resolves"
    )
if rc_ctl != 0:
    failures.append("DETECTOR BROKEN: cat-file -e fails on a known-present blob")

# (b) ci/harness file count via a different command shape
rc, out = git_out("ls-tree", "-r", "--name-only", REF, "--", "ci/harness")
n_ci = len([x for x in out.splitlines() if x.strip()])
claimed_ci = byid["mirror-ci-harness"]["provenance"]["n_files"]
print(f"  (b) ci/harness files re-counted = {n_ci}; registry claims {claimed_ci}")
if n_ci != claimed_ci:
    failures.append(f"ci/harness count mismatch {n_ci} != {claimed_ci}")

# (c) modules.py drift re-derived with difflib opcodes, not set-of-lines
live = (
    Path(r"C:/Users/Prekzursil/.agents/harness/modules.py")
    .read_text(encoding="utf-8", errors="replace")
    .splitlines()
)
rc, repo_txt = git_out("cat-file", "-p", f"{REF}:agent-self/harness/modules.py")
repo = repo_txt.splitlines()
sm = difflib.SequenceMatcher(a=repo, b=live, autojunk=False)
added = sum(
    j2 - j1 for tag, _, _, j1, j2 in sm.get_opcodes() if tag in ("insert", "replace")
)
removed = sum(
    i2 - i1 for tag, i1, i2, _, _ in sm.get_opcodes() if tag in ("delete", "replace")
)
print(f"  (c) modules.py difflib: live-added={added} repo-removed={removed}")
print(
    f"      -> live ahead? {added > removed}  (registry claims drift_direction="
    f"{byid['harness-modules']['provenance']['drift_direction']})"
)
if (added > removed) is not (
    byid["harness-modules"]["provenance"]["drift_direction"] == "live-ahead"
):
    failures.append("modules.py drift direction not reproduced by difflib")

# (d) the codex.md bare-string tools anomaly, re-derived by YAML-ish parse count
n_array, n_bare = 0, 0
rc, out = git_out("ls-tree", "--name-only", REF, "--", "agents/")
agent_files = [x for x in out.splitlines() if x.endswith(".md")]
for f in agent_files:
    rc, body = git_out("cat-file", "-p", f"{REF}:{f}")
    m = re.search(r"^tools:\s*(.*)$", body[:1200], re.M)
    if not m:
        continue
    if m.group(1).lstrip().startswith("["):
        n_array += 1
    else:
        n_bare += 1
print(
    f"  (d) agents/*.md at ref = {len(agent_files)}; tools: as JSON array = {n_array}, bare string = {n_bare}"
)
if not (n_array == 17 and n_bare == 1):
    failures.append(
        f"tools-format anomaly not reproduced: array={n_array} bare={n_bare}"
    )

# (e) no root LICENSE, re-derived with cat-file -e on each plausible name
lic_found = []
for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "NOTICE", "LICENCE"):
    rc, _ = git_out("cat-file", "-e", f"{REF}:{name}")
    if rc == 0:
        lic_found.append(name)
rc_ctl, _ = git_out("cat-file", "-e", f"{REF}:README.md")
print(
    f"  (e) root license files found = {lic_found or 'NONE'};  CONTROL README.md rc={rc_ctl} (expect 0)"
)
if lic_found:
    failures.append(f"no-license claim REFUTED: {lic_found}")
if rc_ctl != 0:
    failures.append("DETECTOR BROKEN: README.md not resolvable at root")

# (f) the 3 divergent agents re-derived by byte comparison
div = []
for a in ("chief-of-staff", "tdd-guide", "codex", "architect"):
    lp = Path(rf"C:/Users/Prekzursil/.claude/agents/{a}.md")
    rc, rb = git_out("cat-file", "-p", f"{REF}:agents/{a}.md")
    same = lp.read_text(encoding="utf-8", errors="replace") == rb
    div.append((a, same))
print(f"  (f) byte-identical live-vs-repo: {div}")
expect = {
    "chief-of-staff": False,
    "tdd-guide": False,
    "codex": False,
    "architect": True,
}
for a, same in div:
    if same != expect[a]:
        failures.append(f"{a}: identity {same} != expected {expect[a]}")

# ------------------------------------------------------- 3. mutation battery
print()
print("=" * 78)
print("3. MUTATION BATTERY (a gate never shown to fail measures nothing)")
print("=" * 78)
print(f"  CONTROL: unmutated doc -> {len(base_violations)} violations (expect 0)")

MUTATIONS = [
    ("drop a candidate", lambda d: d["candidates"].pop(5)),
    (
        "duplicate an id",
        lambda d: d["candidates"][1].__setitem__("id", d["candidates"][0]["id"]),
    ),
    (
        "blank a required field",
        lambda d: d["candidates"][3].__setitem__("task_fit", []),
    ),
    ("delete a required field", lambda d: d["candidates"][4].pop("stop_rules")),
    (
        "invent a classification",
        lambda d: d["candidates"][2].__setitem__("classification", "PROBABLY-FINE"),
    ),
    (
        "strip a provenance anchor",
        lambda d: d["candidates"][6]["provenance"].__setitem__("anchor", ""),
    ),
    (
        "make an anchor non-path prose",
        lambda d: d["candidates"][7]["provenance"].__setitem__(
            "anchor", "a plausible sounding tool"
        ),
    ),
    (
        "remove the license source",
        lambda d: d["candidates"][8]["license"].pop("source"),
    ),
    (
        "blank the maintenance state",
        lambda d: d["candidates"][9]["maintenance"].__setitem__("state", ""),
    ),
    ("renumber out of sequence", lambda d: d["candidates"][10].__setitem__("n", 999)),
]

killed = 0
for label, mut in MUTATIONS:
    d2 = copy.deepcopy(doc)
    try:
        mut(d2)
    except Exception as exc:  # a mutation that cannot even apply is not a test
        print(f"  [SKIP] {label}: could not apply ({exc})")
        failures.append(f"mutation '{label}' inapplicable")
        continue
    v = contract_gate(d2["candidates"])
    ok = len(v) > 0
    killed += ok
    print(
        f"  [{'KILL' if ok else 'SURVIVED'}] {label}: {len(v)} violation(s)"
        + (f" e.g. {v[0]}" if v else "  <-- GATE IS BLIND HERE")
    )
    if not ok:
        failures.append(f"mutation SURVIVED: {label}")

print(
    f"\n  mutations: {len(MUTATIONS)}  killed: {killed}  survived: {len(MUTATIONS) - killed}"
)

# ------------------------------------------------------------------ verdict
print()
print("=" * 78)
if failures:
    print(f"FAILED:build/wfa-2-verify {len(failures)} problem(s)")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print(
    f"SUCCESS:build/wfa-2-verify 32 candidates read back off disk; "
    f"6/6 anchors re-derived independently; {killed}/{len(MUTATIONS)} mutations killed; "
    f"0 survivors"
)
sys.exit(0)
