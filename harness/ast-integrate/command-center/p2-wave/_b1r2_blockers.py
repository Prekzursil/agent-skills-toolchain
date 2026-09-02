r"""Enumerate READY units that a BUILD lane still cannot deliver, with the PRECISE blocker.

"READY" in ready_units.py means only that a unit's DEPENDENCY EDGES are satisfied. It says
nothing about whether the unit's contract is resolvable, its substrate reachable, or its
reviewer suppliable. This probe separates those.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUCKET = re.compile(r"B\d+")
OFF_LIMITS = (
    "Documents/GitHub/Reframe",
    ".claude/agent-worktrees",
    "command-center/adversarial",
)


def main() -> int:
    p = REPO / "command-center" / "ready_units.py"
    spec = importlib.util.spec_from_file_location("ready_units", p)
    ru = importlib.util.module_from_spec(spec)
    sys.modules["ready_units"] = ru
    spec.loader.exec_module(ru)
    sr = ru._load_resolver()

    units = json.loads(ru.CATALOG.read_text(encoding="utf-8"))["work_units"]
    by_id = {u["id"]: u for u in units}
    cache: dict[str, bool] = {}

    def delivered(uid: str) -> bool:
        if uid not in cache:
            u = by_id.get(uid)
            cache[uid] = False if u is None else ru.artifact_delivered(u, sr)[0]
        return cache[uid]

    ready = [
        u
        for u in units
        if not delivered(u["id"])
        and not u.get("owner_approval_required")
        and all(
            BUCKET.fullmatch(d) or (d in by_id and delivered(d))
            for d in (u.get("dependencies") or [])
        )
    ]
    print(f"READY (dependency-edges satisfied): {len(ready)}")

    blockers: dict[str, list[str]] = {}

    def add(uid: str, why: str) -> None:
        blockers.setdefault(uid, []).append(why)

    # B1 -- contract not resolvable: the declared output_schema cannot be turned into a validator
    for u in ready:
        sch = u.get("output_schema")
        if not sch:
            add(u["id"], "no-output-schema-declared")
            continue
        try:
            sr.validator_for(sch)
        except Exception as e:  # noqa: BLE001
            add(u["id"], f"contract-unresolvable: {type(e).__name__}: {str(e)[:120]}")

    # B2 -- substrate this lane did not verify reachable
    for u in ready:
        sub = str(u.get("execution_substrate") or "")
        if sub == "cloud-batch":
            add(
                u["id"],
                "substrate cloud-batch NOT-CHECKED: no reachability probe was run for it",
            )

    # B3 -- inputs point outside the lane's permitted surface
    for u in ready:
        for inp in u.get("inputs") or []:
            if any(
                o.lower() in str(inp).replace("\\", "/").lower() for o in OFF_LIMITS
            ):
                add(u["id"], f"input is off-limits to this wave: {str(inp)[:90]}")
                break

    # B4 -- reviewer requirement a build lane structurally cannot satisfy
    rev_needed = [u for u in ready if u.get("reviewer_requirement")]

    print(
        f"\nB1 contract unresolvable      : {sum(1 for v in blockers.values() if any('contract' in x or 'no-output-schema' in x for x in v))}"
    )
    print(
        f"B2 cloud-batch substrate      : {sum(1 for v in blockers.values() if any('cloud-batch' in x for x in v))}"
    )
    print(
        f"B3 off-limits input           : {sum(1 for v in blockers.values() if any('off-limits' in x for x in v))}"
    )
    print(
        f"B4 reviewer_requirement set   : {len(rev_needed)} of {len(ready)} "
        f"({100 * len(rev_needed) // max(len(ready), 1)}%)"
    )

    print("\n--- B1 detail (all) ---")
    for uid, v in sorted(blockers.items()):
        if any("contract" in x or "no-output-schema" in x for x in v):
            u = by_id[uid]
            print(
                f"  {uid} phase={u.get('phase')} schema={str(u.get('output_schema'))[:110]}"
            )
            for x in v:
                if "contract" in x or "no-output-schema" in x:
                    print(f"      -> {x}")

    print("\n--- B3 detail (all) ---")
    for uid, v in sorted(blockers.items()):
        for x in v:
            if "off-limits" in x:
                print(f"  {uid} phase={by_id[uid].get('phase')} -> {x}")

    # detector control: a known-good schema must resolve, a known-bad one must raise
    ok_err = bad_err = None
    try:
        sr.validator_for("command-center/schema/receipt.schema.json")
    except Exception as e:  # noqa: BLE001
        ok_err = f"{type(e).__name__}: {e}"
    try:
        sr.validator_for("command-center/schema/definitely-not-a-real-schema.json")
    except Exception as e:  # noqa: BLE001
        bad_err = f"{type(e).__name__}"
    print(
        f"\nCONTROL validator_for: known-good -> "
        f"{'resolves' if ok_err is None else 'FAILED ' + ok_err} (want resolves); "
        f"known-bad -> {bad_err or 'RESOLVED ** INERT **'} (want an exception)"
    )
    if ok_err is not None or bad_err is None:
        print(
            "FAILED:p2-blockers contract-resolvability detector does not discriminate"
        )
        return 1

    out = {
        "ready_count": len(ready),
        "blockers": blockers,
        "reviewer_gated_count": len(rev_needed),
        "substrate_histogram": dict(
            Counter(str(u.get("execution_substrate")) for u in ready)
        ),
    }
    (REPO / "command-center/p2-wave/P2-BLOCKED-UNITS.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"\nsubstrate histogram over READY: {out['substrate_histogram']}")
    print(f"units with at least one hard blocker: {len(blockers)}")
    print("SUCCESS:p2-blockers enumerated with precise blockers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
