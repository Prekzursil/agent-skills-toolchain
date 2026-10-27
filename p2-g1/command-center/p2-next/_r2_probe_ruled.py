"""ROUND-2 probe: what exactly does gating rule D on a cross-vendor clause change?

Read-only. Runs BOTH the shipped (round-1) resolver and the proposed gated resolver over the
blocked population, on BOTH bases (committed HEAD blobs and the worktree), and prints every
unit whose verdict moves, with the operative text that decided it.

No writes except command-center/p2-next/_R2-PROBE-RULED.json (new scratch).
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MOD = REPO / "command-center" / "p2-next" / "vendor_satisfiability.py"

spec = importlib.util.spec_from_file_location("vs_old", MOD)
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)

# --- the proposed gate -------------------------------------------------------------------
CROSS_CLAUSE = re.compile(
    r"cross[-_ ]?vendor|cross[-_ ]?model|different\s+vendor|separate\s+vendor"
    r"|other\s+vendor|non[-_ ]?anthropic|non[-_ ]?openai"
    r"|same[-\s]?vendor\s+\w*\s*(?:reviewer|refuter)?[^.;]{0,40}"
    r"(?:does\s+not|do\s+not|cannot|is\s+not|non[-\s]?qualif)",
    re.I,
)


def resolve_new(blocked_on, notes, req, produced):
    produced = (produced or "anthropic").lower()
    if vs.CONTRADICTORY_REQ.search(req or "") and produced == "anthropic":
        return "openai", "0:cross-vendor-Anthropic req on anthropic-produced unit"
    v = vs.named_vendor(blocked_on)
    if v:
        return v, "A:blocked_on names the refuter vendor"
    m = re.search(
        r"qualif\w*\s+(?:refuter|reviewer)\s+is\s+([^.,;]{0,40})", notes or "", re.I
    )
    if m:
        v = vs.named_vendor(m.group(1))
        if v:
            return v, "B:reviewer.notes names the qualifying vendor"
    if vs.RELATIVE_PAT.search(req or ""):
        return vs.other(produced), "C:requirement relative to author"
    v = vs.named_vendor(req or "")
    if v:
        if v == produced:
            if CROSS_CLAUSE.search(req or ""):
                return (
                    vs.other(produced),
                    "D:names producer vendor AND carries a cross-vendor clause -> inverted",
                )
            return (
                v,
                "D2:names producer vendor with NO cross-vendor clause -> same-vendor is what it asks for",
            )
        return v, "D:requirement names a vendor, differs from producer"
    if vs.VENDOR_ANY.search(req or ""):
        return vs.other(produced), "E:cross-vendor undirected"
    if vs.REVIEW_ANY.search(req or ""):
        return "any", "F:review gate, no vendor constraint"
    return "any", "F:no vendor constraint"


# --- population, both bases --------------------------------------------------------------
def sh(*a):
    return subprocess.run(
        list(a), cwd=REPO, capture_output=True, text=True, encoding="utf-8"
    )


def blob(rev, path):
    r = sh("git", "show", f"{rev}:{path}")
    return r.stdout if r.returncode == 0 else None


def population(basis):
    if basis == "committed":
        raw = blob("HEAD", "command-center/WORK-UNIT-CATALOG.json")
        cat = json.loads(raw)
    else:
        cat = json.loads(
            (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
        )
    rows = []
    for u in cat["work_units"]:
        p = u.get("output_path")
        if not p or not p.lower().endswith(".json"):
            continue
        if basis == "committed":
            txt = blob("HEAD", p)
            if txt is None:
                continue
        else:
            fp = REPO / p
            if not fp.is_file():
                continue
            txt = fp.read_text(encoding="utf-8")
        try:
            rec = json.loads(txt)
        except Exception:
            continue
        if str(rec.get("state", "")).upper() not in ("BLOCKED", "FAILED"):
            continue
        pb = rec.get("produced_by")
        produced = (pb.get("vendor") if isinstance(pb, dict) else "") or ""
        rows.append(
            {
                "id": u["id"],
                "produced": produced or "anthropic",
                "produced_known": bool(produced),
                "blocked_on": vs.dig(rec.get("failure") or {}, "blocked_on"),
                "notes": (rec.get("reviewer") or {}).get("notes", "")
                if isinstance(rec.get("reviewer"), dict)
                else "",
                "req": str(u.get("reviewer_requirement") or ""),
                "path": p,
            }
        )
    return rows


report = {}
for basis in ("committed", "worktree"):
    rows = population(basis)
    moved, old_c, new_c = [], Counter(), Counter()
    for r in rows:
        ov, orule = vs.resolve(r["blocked_on"], r["notes"], r["req"], r["produced"])
        nv, nrule = resolve_new(r["blocked_on"], r["notes"], r["req"], r["produced"])
        old_c["RAIL_BLOCKED" if ov == "openai" else "SATISFIABLE"] += 1
        new_c["RAIL_BLOCKED" if nv == "openai" else "SATISFIABLE"] += 1
        if ov != nv:
            moved.append(
                {
                    "id": r["id"],
                    "old": ov,
                    "old_rule": orule,
                    "new": nv,
                    "new_rule": nrule,
                    "req": " ".join(r["req"].split())[:230],
                    "blocked_on": " ".join(r["blocked_on"].split())[:160],
                    "produced": r["produced"],
                }
            )
    report[basis] = {
        "blocked_units": len(rows),
        "old_counts": dict(old_c),
        "new_counts": dict(new_c),
        "moved": moved,
    }
    print(f"===== BASIS {basis} : {len(rows)} blocked units")
    print(f"  shipped resolver : {dict(old_c)}")
    print(f"  gated  resolver  : {dict(new_c)}")
    print(f"  units that MOVE  : {len(moved)}")
    for m in moved:
        print(f"    {m['id']}: {m['old']} -> {m['new']}")
        print(f"       old rule {m['old_rule']}")
        print(f"       new rule {m['new_rule']}")
        print(f"       req        : {m['req']}")
        print(f"       blocked_on : {m['blocked_on'] or '(empty)'}")

ids_c = {r["id"] for r in population("committed")}
ids_w = {r["id"] for r in population("worktree")}
print(f"\ncommitted-only ids: {sorted(ids_c - ids_w)}")
print(f"worktree-only ids : {sorted(ids_w - ids_c)}")
report["basis_diff"] = {
    "committed_only": sorted(ids_c - ids_w),
    "worktree_only": sorted(ids_w - ids_c),
}

cat_dirty = sh(
    "git", "status", "--porcelain", "--", "command-center/WORK-UNIT-CATALOG.json"
).stdout
print(f"catalog dirty? {cat_dirty.strip() or '(clean)'}")
report["catalog_dirty"] = cat_dirty.strip()

(REPO / "command-center/p2-next/_R2-PROBE-RULED.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n"
)
print("\nwrote command-center/p2-next/_R2-PROBE-RULED.json")
