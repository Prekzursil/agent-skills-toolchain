"""P11 - Wave 3 claims (D1 cross-vendor, D3 test-mutates-tree) plus the two Wave-2 rows left open.

D1 is probed with an alias matrix this unit BUILT, not the D1 lane's 45-row matrix: the alias
surface is read out of the registry at each commit and every (alias_of_X, alias_of_X) pair is a
KNOWN same-vendor pair that MUST answer SAME-VENDOR, while every (alias_of_X, alias_of_Y) pair is a
KNOWN cross-vendor pair that MUST answer CROSS-VENDOR. A same-vendor pair answered CROSS-VENDOR is
the false green D1 names; answered NOT-COMPUTABLE it is a refusal.

Two arms, both from committed bytes: 29f4c72a (the pinned Wave-3 state) and the working tree.
Detector control is asserted in EVERY arm before any count is reported.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import time
from itertools import combinations
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
W3_PIN = "29f4c72a"
W2_END = "0aa6f8fa"
OUT: dict[str, object] = {}


def cat(rev: str, rel: str) -> bytes | None:
    r = subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{rel}"],
        cwd=str(REPO),
        capture_output=True,
        check=False,
    )
    return None if r.returncode else r.stdout


def load_vendor_module(rev: str | None, tmp: Path):
    """Materialise vendor_identity.py + VENDOR-REGISTRY.json at `rev` and import it in isolation."""
    root = tmp / (rev or "worktree")
    (root / "platform" / "lib").mkdir(parents=True, exist_ok=True)
    (root / "platform" / "registry").mkdir(parents=True, exist_ok=True)
    if rev:
        mod = cat(rev, "platform/lib/vendor_identity.py")
        reg = cat(rev, "platform/registry/VENDOR-REGISTRY.json")
        if mod is None or reg is None:
            return None, None
    else:
        mod = (REPO / "platform/lib/vendor_identity.py").read_bytes()
        reg = (REPO / "platform/registry/VENDOR-REGISTRY.json").read_bytes()
    mp = root / "platform" / "lib" / "vendor_identity.py"
    mp.write_bytes(mod)
    (root / "platform" / "registry" / "VENDOR-REGISTRY.json").write_bytes(reg)
    name = f"vid_{(rev or 'wt').replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(name, mp)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m, json.loads(reg.decode("utf-8"))


def alias_surface(reg: dict) -> dict[str, list[str]]:
    """canonical_id -> [every spelling the registry says means it]. Shape-agnostic."""
    out: dict[str, list[str]] = {}

    def add(cid: str, val) -> None:
        if isinstance(val, str) and val.strip():
            out.setdefault(cid, [])
            if val not in out[cid]:
                out[cid].append(val)
        elif isinstance(val, list):
            for v in val:
                add(cid, v)

    vendors = reg.get("vendors") or reg.get("entries") or reg
    if isinstance(vendors, dict):
        items = vendors.items()
    elif isinstance(vendors, list):
        items = [
            (str(v.get("canonical_id") or v.get("id")), v)
            for v in vendors
            if isinstance(v, dict)
        ]
    else:
        return out
    for cid, rec in items:
        if not isinstance(rec, dict):
            continue
        if rec.get("establishes_distinctness") is False:
            continue
        add(cid, cid)
        for k in (
            "aliases",
            "alias",
            "spellings",
            "also_known_as",
            "display_name",
            "name",
            "legal_name",
        ):
            if k in rec:
                add(cid, rec[k])
    return {c: v for c, v in out.items() if v}


def probe_arm(label: str, mod, reg: dict) -> dict[str, object]:
    if mod is None:
        return {"arm": label, "error": "module or registry missing at this rev"}
    surface = alias_surface(reg)
    C = mod.Comparison
    ctl_cross = mod.compare("anthropic", "openai")[0]
    ctl_same = mod.compare("anthropic", "anthropic")[0]
    control_ok = ctl_cross == C.CROSS_VENDOR and ctl_same == C.SAME_VENDOR
    same_pairs, cross_pairs = [], []
    for cid, spellings in surface.items():
        for a, b in combinations(spellings, 2):
            same_pairs.append((cid, a, b))
    cids = sorted(surface)
    for x, y in combinations(cids, 2):
        cross_pairs.append((x, y, surface[x][0], surface[y][0]))
    rows_same = {"SAME-VENDOR": 0, "CROSS-VENDOR": 0, "NOT-COMPUTABLE": 0}
    false_green, refusals = [], []
    for cid, a, b in same_pairs:
        v = mod.compare(a, b)[0].value
        rows_same[v] = rows_same.get(v, 0) + 1
        if v == "CROSS-VENDOR":
            false_green.append({"canonical": cid, "a": a, "b": b})
        elif v == "NOT-COMPUTABLE":
            refusals.append({"canonical": cid, "a": a, "b": b})
    rows_cross = {"SAME-VENDOR": 0, "CROSS-VENDOR": 0, "NOT-COMPUTABLE": 0}
    wrong_cross = []
    for x, y, a, b in cross_pairs:
        v = mod.compare(a, b)[0].value
        rows_cross[v] = rows_cross.get(v, 0) + 1
        if v == "SAME-VENDOR":
            wrong_cross.append({"x": x, "y": y})
    return {
        "arm": label,
        "detector_control": {
            "anthropic_vs_openai": ctl_cross.value,
            "anthropic_vs_anthropic": ctl_same.value,
            "verdict": "PASS" if control_ok else "FAIL - counts below are void",
        },
        "canonical_ids_with_a_spelling": len(surface),
        "same_vendor_alias_pairs": len(same_pairs),
        "same_vendor_pair_answers": rows_same,
        "FALSE_GREEN_same_vendor_accepted_as_cross": len(false_green),
        "false_green_detail": false_green[:15],
        "same_vendor_pairs_refused_NOT_COMPUTABLE": len(refusals),
        "refusal_detail": refusals[:15],
        "cross_vendor_pairs": len(cross_pairs),
        "cross_vendor_pair_answers": rows_cross,
        "cross_pairs_wrongly_called_same": wrong_cross[:10],
    }


with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    arms = []
    for rev, label in (
        (W2_END, f"{W2_END} pre-D1-fix"),
        (W3_PIN, f"{W3_PIN} Wave-3 pin"),
        (None, "worktree now"),
    ):
        m, r = load_vendor_module(rev, tmp)
        arms.append(probe_arm(label, m, r or {}))
    OUT["W3_01_D1_alias_matrix"] = arms

# ------------------------------------------------------------------ W3-03: D3 test-mutates-tree
gen_targets = sorted((REPO / "command-center" / "schema").glob("*.json"))
before = {p.name: p.stat().st_mtime_ns for p in gen_targets}
t0 = time.time()
r = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "test_schema_resolver.py",
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
    ],
    cwd=str(REPO / "platform" / "lib"),
    capture_output=True,
    text=True,
    check=False,
)
after = {
    p.name: p.stat().st_mtime_ns
    for p in sorted((REPO / "command-center" / "schema").glob("*.json"))
}
changed = [k for k in before if before[k] != after.get(k)]
old_test = (cat(W2_END, "platform/lib/test_schema_resolver.py") or b"").decode(
    "utf-8", "replace"
)
new_test = (REPO / "platform/lib/test_schema_resolver.py").read_text(encoding="utf-8")
OUT["W3_03_D3"] = {
    "claim": "Wave 3: D3 CLOSED - the test no longer repairs the tree it measures",
    "pytest_exit": r.returncode,
    "pytest_tail": (r.stdout + r.stderr).strip().splitlines()[-1:],
    "generator_outputs_watched": len(before),
    "outputs_whose_mtime_CHANGED_during_the_run": len(changed),
    "changed_sample": changed[:10],
    "elapsed_s": round(time.time() - t0, 1),
    "old_test_ran_generator_with_repo_cwd": "cwd=str(REPO)"
    in old_test.replace(" ", ""),
    "new_test_ran_generator_with_repo_cwd": "cwd=str(REPO)"
    in new_test.replace(" ", ""),
    "old_test_invokes_gen_schema_substrate": "_gen_schema_substrate" in old_test,
    "new_test_invokes_gen_schema_substrate": "_gen_schema_substrate" in new_test,
}

# ------------------------------------------------------------------ W2-03: architectures + dissent
arch = sorted((REPO / "platform" / "architecture").glob("*.md"))
verdict = REPO / "platform" / "architecture" / "TOURNAMENT-VERDICT.md"
vt = verdict.read_text(encoding="utf-8", errors="replace") if verdict.exists() else ""
named = [p.stem for p in arch if p.name != "TOURNAMENT-VERDICT.md"]
OUT["W2_03_architecture"] = {
    "claim": "Wave 2: 9 architectures + TOURNAMENT-VERDICT.md with preserved dissent",
    "md_files": [p.name for p in arch],
    "architecture_docs_excluding_verdict": len(named),
    "verdict_exists": verdict.exists(),
    "verdict_bytes": len(vt.encode("utf-8")) if vt else 0,
    "each_named_in_verdict": {n: vt.count(n) for n in named},
    "architectures_never_mentioned": [n for n in named if vt.count(n) == 0],
    "dissent_occurrences": vt.lower().count("dissent"),
    "minority_report_occurrences": vt.lower().count("minority report"),
    "has_minority_section_heading": any(
        line.startswith("#") and "minority" in line.lower() for line in vt.splitlines()
    ),
}

# ------------------------------------------------------------------ W2-09: stopping-rule axis
bps = []
for p in sorted((REPO / "platform" / "workflows").glob("*.json")):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        continue
    if isinstance(d, dict) and "dsl_version" in d and "stages" in d:
        bps.append((p.name, d.get("stopping_rules")))


def shape(v) -> str:
    """Type/key skeleton only - values erased. A defensible, disclosed normalisation."""
    if isinstance(v, dict):
        return "{" + ",".join(f"{k}:{shape(v[k])}" for k in sorted(v)) + "}"
    if isinstance(v, list):
        return "[" + ",".join(sorted({shape(x) for x in v})) + "]"
    return type(v).__name__


raw = {json.dumps(s, sort_keys=True) for _, s in bps}
shapes: dict[str, int] = {}
for _, s in bps:
    shapes[shape(s)] = shapes.get(shape(s), 0) + 1
OUT["W2_09_stopping_rules"] = {
    "claim": "Wave 2: stopping_rules take 2 distinct NORMALISED values across all 97 blueprints",
    "blueprints_considered": len(bps),
    "distinct_raw_values": len(raw),
    "distinct_type_key_shapes": len(shapes),
    "largest_shape_cluster": max(shapes.values()) if shapes else 0,
    "shape_histogram": dict(sorted(shapes.items(), key=lambda kv: -kv[1])[:6]),
}

dest = REPO / "command-center" / "P11-WAVE3.json"
dest.write_text(json.dumps(OUT, indent=2, default=str), encoding="utf-8")
print(json.dumps(OUT, indent=2, default=str))
print(f"SUCCESS:p11-wave3 {dest}")
