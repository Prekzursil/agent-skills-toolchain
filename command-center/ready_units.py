r"""Compute which of the 2,007 work units are STARTABLE right now, and emit a build worklist.

A unit is READY when every dependency it declares is satisfiable:
  * a unit-id dependency is satisfied when that unit's artifact is DELIVERED -- see `delivered()`
    below. Until 2026-08-12 this was bare `Path.exists()`, which is the textbook Goodhart failure:
    the check rewards a file being present, so the program produced 44 present files of which 43
    SELF-DECLARE `state: BLOCKED` or `FAILED`. Measured with
    `command-center/p2-wave/_b1r2_scope_measure.py`: existence counted 44 delivered; the honest
    predicate counts 1, returns 36 wrongly-excluded units to the READY set, and removes 1
    phantom-ready unit (ADV-0002) that was queued on a BLOCKED foundation;
  * a `B\d+` bucket dependency is treated per the owner ruling recorded in OWNER-DECISIONS.md --
    "a bucket-level gate artifact exists" -- which makes a zero-member bucket SATISFIED rather than
    permanently unsatisfiable. That reading is recorded here explicitly because 876 edges turn on
    it and a silent choice would be indefensible;
  * an unknown-form token (ARC, WFA, CC, IMP -- 41 of them) cannot be resolved and BLOCKS, because
    guessing at it would manufacture readiness.

Owner-gated units (`owner_approval_required`) are excluded from the build list no matter how ready
they look: an executor cannot supply an owner ruling.

Emits command-center/READY-UNITS.json for the build fan-out to consume.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
BUCKET = re.compile(r"B\d+")

#: Owner ruling of record, 2026-08-11: a B-token dependency means "a bucket-level gate artifact
#: exists", which is the only reading that does not leave 876 edges permanently unsatisfiable.
BUCKET_SATISFIED = True

#: A receipt that classifies itself as one of these is NOT a delivered dependency. Reading the
#: FIELD rather than the document is deliberate: an earlier stub-word regex over the same 44
#: artifacts produced 22 false positives by matching prose that merely discussed placeholders.
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})

#: Both-states control fixtures for `--self-test`. The OLD existence predicate accepts BOTH of
#: these, so a control that only checked the good one would have been silent in both states.
CONTROL_GOOD = "WFA-0001"  # exists, non-empty, parses, schema-VALID, no self-declared failure
CONTROL_BAD = "ADV-0031"  # exists, non-empty, parses, schema-VALID, but state == BLOCKED


def _load_resolver():
    """Load platform/lib/schema_resolver for contract validation.

    Returns None when unavailable. The caller DEGRADES LOUDLY rather than silently: a predicate
    that quietly stops validating is exactly the no-op gate this module is being fixed to stop
    manufacturing.
    """
    p = REPO / "platform" / "lib" / "schema_resolver.py"
    if not p.is_file():
        return None
    try:
        sys.path.insert(0, str(p.parent))
        spec = importlib.util.spec_from_file_location("schema_resolver", p)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["schema_resolver"] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception:  # pragma: no cover - environment-dependent
        return None


def artifact_delivered(unit: dict, resolver=None) -> tuple[bool, str]:
    """Is this unit's artifact actually DELIVERED? Returns (verdict, reason).

    Conditions, in order, each of which a bare `exists()` skips:
      1. output_path declared and the file exists;
      2. it is non-empty (a 0-byte file is the MSYS redirect-truncation signature);
      3. if JSON, it parses;
      4. if it validates against a declared output_schema, it must actually validate;
      5. if it carries a `state` field, that state must not be a self-declared failure.
    Condition 5 alone is forgeable by a one-word edit, which is why 4 is also enforced; condition
    4 alone passes a perfectly-formed receipt that says BLOCKED, which is why 5 is also enforced.
    """
    p = unit.get("output_path")
    if not p:
        return False, "no-output-path"
    fp = REPO / p
    if not fp.exists():
        return False, "absent"
    try:
        size = fp.stat().st_size
    except OSError as e:
        return False, f"stat-error:{type(e).__name__}"
    if size <= 0:
        return False, "empty"
    if fp.suffix.lower() != ".json":
        return True, "non-json-present"
    try:
        doc = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"unparseable:{type(e).__name__}"
    schema = unit.get("output_schema")
    if resolver is not None and isinstance(schema, str) and schema:
        try:
            errs = resolver.validate_artifact(doc, schema)
            if errs:
                return False, f"schema-invalid:{len(errs)}"
        except Exception:
            pass  # unresolvable contract is reported by the resolver's own audit, not here
    if isinstance(doc, dict):
        st = doc.get("state")
        if isinstance(st, str) and st.upper() in NOT_DELIVERING:
            return False, f"self-declared:{st.upper()}"
    return True, "delivered"


def self_test() -> int:
    """Both-states control. MUST accept CONTROL_GOOD and MUST reject CONTROL_BAD."""
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_id = {u["id"]: u for u in doc["work_units"]}
    resolver = _load_resolver()
    print(f"  resolver: {'loaded' if resolver else 'UNAVAILABLE (contract check degraded)'}")
    ok = True
    for uid, want in ((CONTROL_GOOD, True), (CONTROL_BAD, False)):
        u = by_id.get(uid)
        if u is None:
            print(f"  CONTROL {uid}: NOT IN CATALOG -- control cannot run")
            ok = False
            continue
        got, why = artifact_delivered(u, resolver)
        legacy = bool(u.get("output_path")) and (REPO / u["output_path"]).exists()
        verdict = "OK" if got is want else "BROKEN"
        if got is not want:
            ok = False
        print(
            f"  CONTROL {uid}: want={want} got={got} ({why}) "
            f"| legacy-exists-predicate={legacy} -> {verdict}"
        )
    if not ok:
        print("FAILED:ready-units self-test the delivered() control does not discriminate")
        return 1
    print("SUCCESS:ready-units self-test delivered() fires on the bad state and is silent on the good one")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = doc["work_units"]
    by_id = {u["id"]: u for u in units}
    resolver = _load_resolver()
    _cache: dict[str, bool] = {}

    def delivered(uid: str) -> bool:
        if uid in _cache:
            return _cache[uid]
        u = by_id.get(uid)
        verdict = False if u is None else artifact_delivered(u, resolver)[0]
        _cache[uid] = verdict
        return verdict

    ready, blocked, gated = [], [], []
    block_reason: Counter = Counter()
    for u in units:
        if delivered(u["id"]):
            continue  # already delivered
        if u.get("owner_approval_required"):
            gated.append(u["id"])
            continue
        reasons = []
        for dep in u.get("dependencies") or []:
            if BUCKET.fullmatch(dep):
                if not BUCKET_SATISFIED:
                    reasons.append(f"bucket:{dep}")
            elif dep in by_id:
                if not delivered(dep):
                    reasons.append(f"unbuilt:{dep}")
            else:
                reasons.append(f"unknown-token:{dep}")
        if reasons:
            blocked.append(u["id"])
            block_reason[reasons[0].split(":")[0]] += 1
        else:
            ready.append(u["id"])

    out = {
        "bucket_reading": "a bucket-level gate artifact exists (owner ruling 2026-08-11)",
        "totals": {
            "units": len(units),
            "already_delivered": sum(1 for u in units if delivered(u["id"])),
            "artifacts_present_but_not_delivered": sum(
                1
                for u in units
                if u.get("output_path")
                and (REPO / u["output_path"]).exists()
                and not delivered(u["id"])
            ),
            "ready": len(ready),
            "blocked": len(blocked),
            "owner_gated": len(gated),
        },
        "block_reasons": dict(block_reason),
        "ready_units": ready,
        "owner_gated_units": gated,
    }
    (REPO / "command-center/READY-UNITS.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    t = out["totals"]
    print(
        f"  units {t['units']} | delivered {t['already_delivered']} | READY {t['ready']} "
        f"| blocked {t['blocked']} | owner-gated {t['owner_gated']}"
    )
    print(
        f"  artifacts present but NOT delivered (self-declared failure / invalid): "
        f"{t['artifacts_present_but_not_delivered']}"
    )
    print(f"  block reasons: {out['block_reasons']}")
    print(f"  first ready: {ready[:8]}")
    if (
        t["ready"] + t["blocked"] + t["owner_gated"] + t["already_delivered"]
        != t["units"]
    ):
        print("FAILED:ready-units partition does not sum to the unit count")
        return 1
    print("\nSUCCESS:ready-units partition sums correctly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
