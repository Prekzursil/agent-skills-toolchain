#!/usr/bin/env python3
"""Named probe 2: broken input yields a typed failure (both-states), not a looks-right workflow."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as FX  # noqa: E402
from forge import forge  # noqa: E402
from operators import splice_replace  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0212.json"
UNIT = "IMP-0212"


def _fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def leaked(result: dict) -> bool:
    wf = result.get("workflow")
    if wf is None:
        return False
    if isinstance(wf, dict) and wf.get("stages"):
        return True
    return False


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("catalog artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0212" not in json.dumps(doc):
        return _fail("sentinel absent")

    good = forge(FX.GOAL, FX.good_scout())
    if not good.get("ok"):
        return _fail(f"GOOD state failed: {good.get('error_code')}")
    if leaked(good) is False:
        return _fail("GOOD state missing workflow")
    if not (good.get("simulation_receipt") or {}).get("ok"):
        return _fail("GOOD state missing passing simulation receipt")

    missing = forge("", FX.good_scout())
    if missing.get("ok") or missing.get("error_code") != "MISSING_GOAL":
        return _fail(f"empty goal was not MISSING_GOAL: {missing.get('error_code')}")
    if leaked(missing):
        return _fail("MISSING_GOAL leaked a workflow")

    not_obj = forge(FX.GOAL, ["not-an-object"])  # type: ignore[arg-type]
    if not_obj.get("ok") or not_obj.get("error_code") != "INVALID_SCOUT":
        return _fail(f"bad scout was not INVALID_SCOUT: {not_obj.get('error_code')}")
    if leaked(not_obj):
        return _fail("INVALID_SCOUT leaked a workflow")

    cycle = forge(FX.GOAL, FX.broken_scout_cycle(), allow_build=False)
    if cycle.get("ok"):
        return _fail("cyclic pretty workflow was forged")
    if leaked(cycle):
        return _fail("cyclic pretty workflow leaked to caller")
    if cycle.get("error_type") != "ForgeTypedFailure":
        return _fail(f"cycle refusal not typed: {cycle.get('error_type')}")
    if cycle.get("error_code") not in {"STATIC_INVALID", "LOOKS_RIGHT_REFUSED"}:
        return _fail(f"cycle error_code {cycle.get('error_code')}")

    unemu = forge(FX.GOAL, FX.broken_scout_unemulatable(), allow_build=False)
    if unemu.get("ok") or leaked(unemu):
        return _fail("unemulatable pretty workflow reached caller")
    if unemu.get("error_code") not in {"UNEMULATABLE_CAPABILITY", "LOOKS_RIGHT_REFUSED"}:
        return _fail(f"unemulatable error_code {unemu.get('error_code')}")
    # Must not be the live-network workflow even if some other path forged.
    if isinstance(unemu.get("workflow"), dict):
        return _fail("unemulatable payload still carried a workflow object")

    schema_bad = forge(FX.GOAL, FX.broken_scout_schema(), allow_build=False)
    if schema_bad.get("ok") or leaked(schema_bad):
        return _fail("schema-invalid pretty workflow reached caller")
    if schema_bad.get("error_code") not in {"SCHEMA_INVALID", "LOOKS_RIGHT_REFUSED"}:
        return _fail(f"schema-invalid error_code {schema_bad.get('error_code')}")

    # allow_build=True on unemulatable scout may BUILD, but must not return the pretty wf.
    maybe_build = forge(FX.GOAL, FX.broken_scout_unemulatable(), allow_build=True)
    if maybe_build.get("ok"):
        returned_id = (maybe_build.get("workflow") or {}).get("id")
        if returned_id == FX.pretty_unemulatable_workflow()["id"]:
            return _fail("BUILD path returned the unemulatable pretty id")
        if maybe_build.get("operator") != "BUILD":
            return _fail("expected BUILD rather than the pretty candidate")
        caps = {
            s.get("capability") for s in (maybe_build.get("workflow") or {}).get("stages") or []
        }
        if "live-network" in caps:
            return _fail("caller received live-network capability")
    elif leaked(maybe_build):
        return _fail("failed forge still leaked workflow")

    _merged, mismatch = splice_replace(
        FX.slow_transform_workflow(), "rank", FX.mismatch_donor_stage()
    )
    if mismatch is None or mismatch.get("error_code") != "CONTRACT_MISMATCH":
        return _fail("contract mismatch did not yield typed splice failure")

    both_states = (
        good.get("ok") is True
        and missing.get("ok") is False
        and cycle.get("ok") is False
        and unemu.get("ok") is False
        and schema_bad.get("ok") is False
    )
    if not both_states:
        return _fail("both-states control did not discriminate")

    summary = {
        "probe": "probe2-typed-failure",
        "unit_id": UNIT,
        "pass": True,
        "good_ok": True,
        "missing_goal": missing.get("error_code"),
        "invalid_scout": not_obj.get("error_code"),
        "cycle_refused": cycle.get("error_code"),
        "unemulatable_refused": unemu.get("error_code"),
        "schema_refused": schema_bad.get("error_code"),
        "contract_mismatch": mismatch.get("error_code"),
        "workflow_leaked_on_bad": False,
        "both_states_discriminates": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"GOOD ok={good.get('ok')} BAD missing={missing.get('error_code')} "
        f"cycle={cycle.get('error_code')} unemu={unemu.get('error_code')} "
        f"schema={schema_bad.get('error_code')} leaked=False"
    )
    print(f"SUCCESS:{UNIT}-probe2 broken input yields typed failure (both-states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
