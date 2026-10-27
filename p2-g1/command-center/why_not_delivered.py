r"""Why is a unit not counted as DELIVERED? Print the predicate's own reason, per unit.

WHY THIS EXISTS. The partition reported `delivered 1` -- DOWN from 4 -- in the same minute that a
build lane shipped five artifacts I had independently confirmed exist, parse, and run 18-80 KB. Two
numbers that cannot both be right are a detector-failure signal, not a finding, so the instrument gets
read before either number is believed.

There are two very different explanations and they need opposite responses:
  (a) the units genuinely are not delivered by their own contract -- the stricter predicate is doing
      exactly its job and the earlier "4 delivered" was inflated by a bare exists() check; or
  (b) the predicate is looking at the wrong path -- the artifacts landed somewhere other than the
      output_path the catalog declares, so real work is being scored as absent.
`artifact_delivered` already returns a reason string for precisely this. Nobody was printing it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_ready_units():
    spec = importlib.util.spec_from_file_location(
        "ru", REPO / "command-center" / "ready_units.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str]) -> int:
    ru = load_ready_units()
    catalog = getattr(ru, "CATALOG", None)
    if catalog is None or not Path(catalog).exists():
        print(f"FAILED:why-not-delivered cannot locate the catalog (CATALOG={catalog})")
        return 1

    doc = json.loads(Path(catalog).read_text(encoding="utf-8"))
    units = doc.get("work_units") or doc.get("units") or []
    if not units:
        print(f"FAILED:why-not-delivered catalog has no work_units ({list(doc)[:8]})")
        return 1
    # MUST be the SAME resolver ready_units uses, or this tool silently disagrees with the
    # authoritative partition. It did: I guessed the factory was named `make_resolver`, hasattr
    # returned False, and the fallback passed resolver=None -- which makes artifact_delivered skip
    # its entire schema block (`if resolver is not None ...`, ready_units.py:206), i.e. conditions 4
    # and 4b. The tool was strictly MORE PERMISSIVE than the predicate it claims to explain and
    # reported 2 DELIVERED against the partition's 1. A diagnostic that disagrees with the thing it
    # diagnoses is worse than no diagnostic, and "guess the API name, fall back to a no-op on
    # AttributeError" is how that happens quietly.
    resolver = ru._load_resolver()
    if resolver is None:
        print(
            "  WARNING: resolver unavailable -- conditions 4/4b will be SKIPPED and this run is"
        )
        print(
            "           more permissive than ready_units.py. Treat the counts as an upper bound."
        )

    wanted = {a.upper() for a in argv}
    reasons: Counter[str] = Counter()
    shown = 0
    for u in units:
        uid = str(u.get("id", ""))
        try:
            ok, why = ru.artifact_delivered(u, resolver)
        except Exception as e:  # a predicate that throws is itself the finding
            ok, why = False, f"predicate-raised:{type(e).__name__}:{e}"
        reasons[("DELIVERED" if ok else why)] += 1
        if wanted and uid.upper() in wanted:
            p = u.get("output_path")
            fp = REPO / p if p else None
            exists = fp.exists() if fp else False
            size = fp.stat().st_size if exists else 0
            print(f"\n  {uid}: delivered={ok}  reason={why}")
            print(f"      declared output_path : {p}")
            print(f"      exists={exists} size={size:,}B")
            shown += 1

    if wanted and not shown:
        print(
            f"FAILED:why-not-delivered none of {sorted(wanted)} matched a unit id -- wrong ids or wrong catalog"
        )
        return 1

    print("\n  reason histogram across all units:")
    for why, n in reasons.most_common(14):
        print(f"    {n:>5}  {why}")
    print("\nSUCCESS:why-not-delivered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
