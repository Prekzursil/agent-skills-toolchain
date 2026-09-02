"""P11 - W3-01 (D1 cross-vendor), pass 2.

Pass 1's alias-surface extractor guessed the registry shape (`vendors`/`entries`) and found
neither, so it walked the top-level keys as if they were vendor records: 2 "canonical ids", 0
same-vendor pairs, and cross-vendor pairs answering NOT-COMPUTABLE while its own control answered
CROSS-VENDOR. A probe that contradicts its own control is a detector failure, so pass 1's counts
are void. Real shape: `identities: [{id, aliases[], establishes_distinctness, ...}]`.

Controls asserted in EVERY arm before a count is reported:
  C1 a known cross-vendor pair (anthropic, openai) -> CROSS-VENDOR
  C2 a known identical pair (anthropic, anthropic) -> SAME-VENDOR
  C3 the extractor must find >= 10 identities and >= 20 alias spellings, else it is blind
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from itertools import combinations
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
ARMS = [
    ("29f4c72a", "Wave-3 pin (D1 declared CLOSED here)"),
    (None, "worktree now (post Wave-4 D1 close)"),
]
OUT: dict[str, object] = {}


def blob(rev: str, rel: str) -> bytes | None:
    r = subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{rel}"],
        cwd=str(REPO),
        capture_output=True,
        check=False,
    )
    return None if r.returncode else r.stdout


def load(rev: str | None, tmp: Path):
    root = tmp / (rev or "wt")
    (root / "platform" / "lib").mkdir(parents=True, exist_ok=True)
    (root / "platform" / "registry").mkdir(parents=True, exist_ok=True)
    if rev:
        mod, reg = (
            blob(rev, "platform/lib/vendor_identity.py"),
            blob(rev, "platform/registry/VENDOR-REGISTRY.json"),
        )
    else:
        mod = (REPO / "platform/lib/vendor_identity.py").read_bytes()
        reg = (REPO / "platform/registry/VENDOR-REGISTRY.json").read_bytes()
    if mod is None or reg is None:
        return None, None
    mp = root / "platform" / "lib" / "vendor_identity.py"
    mp.write_bytes(mod)
    (root / "platform" / "registry" / "VENDOR-REGISTRY.json").write_bytes(reg)
    nm = f"vid2_{rev or 'wt'}"
    spec = importlib.util.spec_from_file_location(nm, mp)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[nm] = m
    spec.loader.exec_module(m)
    return m, json.loads(reg.decode("utf-8"))


def surface(reg: dict) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """-> (distinctness-establishing identities, non-identity entries) as id -> spellings."""
    good: dict[str, list[str]] = {}
    other: dict[str, list[str]] = {}
    for rec in reg.get("identities", []):
        if not isinstance(rec, dict):
            continue
        cid = str(rec.get("id"))
        sp = [cid] + [
            a for a in (rec.get("aliases") or []) if isinstance(a, str) and a.strip()
        ]
        seen, uniq = set(), []
        for s in sp:
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        (good if rec.get("establishes_distinctness") else other)[cid] = uniq
    return good, other


def arm(label: str, m, reg: dict) -> dict[str, object]:
    if m is None:
        return {"arm": label, "error": "missing at this rev"}
    good, other = surface(reg)
    c1 = m.compare("anthropic", "openai")[0].value
    c2 = m.compare("anthropic", "anthropic")[0].value
    total_spellings = sum(len(v) for v in good.values())
    ctl = {
        "C1_anthropic_vs_openai": c1,
        "C2_anthropic_vs_anthropic": c2,
        "C3_identities_found": len(good),
        "C3_alias_spellings_found": total_spellings,
        "verdict": "PASS"
        if c1 == "CROSS-VENDOR"
        and c2 == "SAME-VENDOR"
        and len(good) >= 10
        and total_spellings >= 20
        else "FAIL - counts void",
    }
    same_pairs = [
        (cid, a, b) for cid, sp in good.items() for a, b in combinations(sp, 2)
    ]
    tally_same = {"SAME-VENDOR": 0, "CROSS-VENDOR": 0, "NOT-COMPUTABLE": 0}
    false_green, refused = [], []
    for cid, a, b in same_pairs:
        v = m.compare(a, b)[0].value
        tally_same[v] = tally_same.get(v, 0) + 1
        if v == "CROSS-VENDOR":
            false_green.append({"canonical": cid, "a": a, "b": b})
        elif v == "NOT-COMPUTABLE":
            refused.append({"canonical": cid, "a": a, "b": b})
    cross_pairs = [
        (x, y, good[x][0], good[y][0]) for x, y in combinations(sorted(good), 2)
    ]
    tally_cross = {"SAME-VENDOR": 0, "CROSS-VENDOR": 0, "NOT-COMPUTABLE": 0}
    wrong = []
    for x, y, a, b in cross_pairs:
        v = m.compare(a, b)[0].value
        tally_cross[v] = tally_cross.get(v, 0) + 1
        if v != "CROSS-VENDOR":
            wrong.append({"x": x, "y": y, "answer": v})
    # a non-identity entry (hosting plane / placeholder) MUST refuse, never establish distinctness
    plane = {"pairs": 0, "correctly_refused": 0, "leaked_a_verdict": []}
    for cid, sp in other.items():
        for g in sorted(good):
            plane["pairs"] += 1
            v = m.compare(sp[0], good[g][0])[0].value
            if v == "NOT-COMPUTABLE":
                plane["correctly_refused"] += 1
            else:
                plane["leaked_a_verdict"].append(
                    {"non_identity": cid, "vs": g, "answer": v}
                )
    return {
        "arm": label,
        "detector_control": ctl,
        "identities_establishing_distinctness": len(good),
        "non_identity_entries": sorted(other),
        "same_vendor_alias_pairs": len(same_pairs),
        "same_vendor_answers": tally_same,
        "FALSE_GREEN_same_vendor_called_cross": len(false_green),
        "false_green_detail": false_green[:20],
        "same_vendor_pairs_REFUSED": len(refused),
        "refused_detail": refused[:20],
        "cross_vendor_pairs": len(cross_pairs),
        "cross_vendor_answers": tally_cross,
        "cross_pairs_not_answered_CROSS": wrong[:20],
        "hosting_plane_refusal_check": plane,
    }


with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    OUT["W3_01_D1_pass2"] = [arm(lbl, *load(rev, tmp)) for rev, lbl in ARMS]

# The specific alias the briefing names: "Anthropic PBC" must not be a refusal after the close.
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    named = {}
    for rev, lbl in ARMS:
        m, _ = load(rev, tmp)
        if m is None:
            continue
        named[lbl] = {
            probe: m.compare(*probe.split(" || "))[0].value
            for probe in (
                "Anthropic PBC || anthropic",
                "Anthropic, PBC || anthropic",
                "OpenAI, Inc. || openai",
                "Google DeepMind || google",
                "anthropic || Anthropic",
            )
        }
    OUT["W3_01_named_alias_probes"] = named

dest = REPO / "command-center" / "P11-D1.json"
dest.write_text(json.dumps(OUT, indent=2, default=str), encoding="utf-8")
print(json.dumps(OUT, indent=2, default=str))
print(f"SUCCESS:p11-d1 {dest}")
