r"""Two measurements the build lane needs before it picks a unit.

(A) CONTRACT RESOLVABILITY. Which READY units declare an output_schema that actually resolves
    to a file on disk? Splits the JSON-pointer fragment (`#/$defs/x`) off correctly -- an
    earlier probe of mine wrongly counted the fragment form as missing, which was a DETECTOR
    error, not a catalog error. Reported separately here.

(B) OQ-2 ORDERING: ascending phase, then unblocking power (how many other units name this unit
    as a dependency). Emits the ranked head of the READY list.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
READY = REPO / "command-center/READY-UNITS.json"
BUCKET = re.compile(r"B\d+")


def classify_schema(s: str | None) -> tuple[str, str]:
    """Return (kind, resolved_path). kind in ok|fragment-ok|missing|prose|none."""
    if not s:
        return "none", ""
    frag = ""
    path = s
    if "#" in s:
        path, frag = s.split("#", 1)
    prose = bool(re.search(r"\s(profile=|\(required:)", path))
    path = path.strip()
    if prose:
        path = path.split(" ")[0]
    fp = REPO / path
    if not fp.exists():
        return ("prose-unresolved" if prose else "missing"), path
    if prose:
        return "prose-but-base-resolves", path
    return ("fragment" if frag else "ok"), path


def main() -> int:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = doc["work_units"]
    by_id = {u["id"]: u for u in units}
    ready = set(json.loads(READY.read_text(encoding="utf-8"))["ready_units"])

    # --- (A) contract resolvability, restricted to the READY set ---
    kinds: Counter = Counter()
    bad_examples = defaultdict(list)
    for uid in ready:
        kind, path = classify_schema(by_id[uid].get("output_schema"))
        kinds[kind] += 1
        if kind in {"missing", "prose-unresolved", "none"} and len(bad_examples[kind]) < 4:
            bad_examples[kind].append((uid, (by_id[uid].get("output_schema") or "")[:95]))
    print(f"(A) CONTRACT RESOLVABILITY over the {len(ready)} READY units")
    for k, n in kinds.most_common():
        print(f"    {n:>5}  {k}")
    for k, ex in bad_examples.items():
        for uid, s in ex:
            print(f"      e.g. {k}: {uid}  {s}")

    # --- (B) unblocking power ---
    dependents: Counter = Counter()
    for u in units:
        for dep in u.get("dependencies") or []:
            if not BUCKET.fullmatch(dep):
                dependents[dep] += 1

    def phase_of(u):
        for k in ("phase", "phase_id", "wave"):
            if k in u:
                return u[k]
        return None

    sample = by_id[next(iter(ready))]
    print(f"\n    unit keys available: {sorted(sample.keys())}")

    rows = []
    for uid in ready:
        u = by_id[uid]
        rows.append((phase_of(u), -dependents.get(uid, 0), uid))
    have_phase = sum(1 for r in rows if r[0] is not None)
    print(f"\n(B) OQ-2 ORDERING  units with a phase field: {have_phase}/{len(rows)}")
    rows.sort(key=lambda r: (r[0] if r[0] is not None else 10**9, r[1], r[2]))
    print("    ascending phase, then unblocking power (dependents desc):")
    for ph, negdep, uid in rows[:20]:
        u = by_id[uid]
        kind, _ = classify_schema(u.get("output_schema"))
        print(
            f"      phase={str(ph):<6} unblocks={-negdep:<4} {uid:<10} contract={kind:<22} "
            f"{str(u.get('output_path'))[:58]}"
        )
    print("\nSUCCESS:order-and-contracts measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
