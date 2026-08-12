r"""BUILD-lane pre-flight measurement for the two scope-expansion items.

(A) delivered() predicate tiers -- how many units each tier moves, measured, not asserted.
(B) missing output_path parent directories -- and a CONTROL proving the failure mode is real
    (open(path,'w') into a missing parent raises, i.e. a unit would exit non-zero / SEVERED).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
BUCKET = re.compile(r"B\d+")
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def load():
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    return doc["work_units"]


def tier_exists(p: Path) -> bool:
    return p.exists()


def tier_nonempty(p: Path) -> bool:
    return p.exists() and p.stat().st_size > 0


def parse_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def tier_strict(p: Path) -> bool:
    """exists AND non-empty AND (if .json: parses AND state is a delivering state)."""
    if not tier_nonempty(p):
        return False
    if p.suffix.lower() != ".json":
        return True  # non-JSON artifacts: existence+non-empty is all this tier can check
    doc = parse_json(p)
    if doc is None:
        return False
    if isinstance(doc, dict):
        st = doc.get("state")
        if isinstance(st, str) and st.upper() in NOT_DELIVERING:
            return False
    return True


def ready_under(units, pred) -> set[str]:
    by_id = {u["id"]: u for u in units}

    def delivered(uid: str) -> bool:
        u = by_id.get(uid)
        if not u:
            return False
        p = u.get("output_path")
        return bool(p) and pred(REPO / p)

    ready = set()
    for u in units:
        p = u.get("output_path")
        if p and pred(REPO / p):
            continue
        if u.get("owner_approval_required"):
            continue
        ok = True
        for dep in u.get("dependencies") or []:
            if BUCKET.fullmatch(dep):
                continue
            if dep in by_id:
                if not delivered(dep):
                    ok = False
                    break
            else:
                ok = False
                break
        if ok:
            ready.add(u["id"])
    return ready


def main() -> int:
    units = load()
    print("=" * 90)
    print("(A) delivered() PREDICATE TIERS")
    tiers = {
        "T0 exists (current shipped predicate)": tier_exists,
        "T1 exists+nonempty": tier_nonempty,
        "T2 exists+nonempty+parses+state-not-blocked/failed": tier_strict,
    }
    sets = {}
    for name, pred in tiers.items():
        delivered_n = sum(
            1
            for u in units
            if u.get("output_path") and pred(REPO / u["output_path"])
        )
        r = ready_under(units, pred)
        sets[name] = r
        print(f"  {name:<52} delivered={delivered_n:<4} READY={len(r)}")
    t0 = sets["T0 exists (current shipped predicate)"]
    t2 = sets["T2 exists+nonempty+parses+state-not-blocked/failed"]
    print(f"  T0->T2 newly READY : {len(t2 - t0)}")
    print(f"  T0->T2 dropped from READY (phantom-ready): {sorted(t0 - t2)}")

    # state tally over the artifacts T0 counts as delivered
    tally: Counter = Counter()
    for u in units:
        p = u.get("output_path")
        if not p:
            continue
        fp = REPO / p
        if not fp.exists():
            continue
        if fp.suffix.lower() != ".json":
            tally["<non-json>"] += 1
            continue
        d = parse_json(fp)
        if d is None:
            tally["<unparseable>"] += 1
        elif isinstance(d, dict) and "state" in d:
            tally[str(d["state"])] += 1
        else:
            tally["<no-state-field>"] += 1
    print(f"  STATE TALLY over T0-delivered artifacts: {dict(tally)}")

    print("=" * 90)
    print("(B) MISSING output_path PARENT DIRECTORIES")
    missing: Counter = Counter()
    undelivered_using = Counter()
    for u in units:
        p = u.get("output_path")
        if not p:
            continue
        parent = (REPO / p).parent
        if not parent.exists():
            rel = parent.relative_to(REPO).as_posix()
            missing[rel] += 1
            if u["id"] in t0:
                undelivered_using[rel] += 1
    print(f"  distinct missing parent dirs: {len(missing)}")
    for d, n in sorted(missing.items()):
        print(f"    {d:<58} units={n:<4} of which READY(T0)={undelivered_using[d]}")
    print(f"  total units writing into a missing dir: {sum(missing.values())}")
    print(f"  of which READY under T0                : {sum(undelivered_using.values())}")

    print("-" * 90)
    print("  CONTROL (both-states) for the missing-dir failure mode:")
    if missing:
        victim = REPO / sorted(missing)[0] / "_ctl_probe.tmp"
        try:
            with open(victim, "w", encoding="utf-8") as fh:
                fh.write("x")
            print("    BAD-STATE  open(w) into missing parent: SUCCEEDED -> control INERT")
            victim.unlink()
        except OSError as e:
            print(f"    BAD-STATE  open(w) into missing parent: {type(e).__name__} -> control FIRES")
        good = REPO / "command-center/p2-wave/_ctl_probe.tmp"
        try:
            with open(good, "w", encoding="utf-8") as fh:
                fh.write("x")
            print("    GOOD-STATE open(w) into existing parent: SUCCEEDED -> control SILENT")
            good.unlink()
        except OSError as e:
            print(f"    GOOD-STATE open(w) into existing parent: {type(e).__name__} -> control OVER-FIRES")
    else:
        print("    no missing dirs -- control not applicable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
