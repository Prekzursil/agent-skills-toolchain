r"""The settling experiment the last refutation named, executed over ALL artifacts.

The adversarial verifier's recommendation, quoted: "extend the control loop to run the garbage +
field-deletion probe on EVERY unit's declared schema, not on one hand-picked unit, and fail loudly
when a schema accepts garbage." The build lane's verifier ran that control on AUD-0020 only, and the
audit found that on IMP-0433 -- whose declared contract is the draft-2020-12 meta-schema -- the real
artifact, unrelated garbage, and the artifact minus `sentinel` all returned 0 errors.

WHY THE OBVIOUS FORM OF THIS PROBE IS A NO-OP, and what is measured instead. Every one of the 53
artifacts self-declares `state: "BLOCKED"`, so `artifact_delivered` rejects all of them at condition
5 no matter what is done to their bodies. A corruption control over the FULL predicate would
therefore report a perfect 53/53 "rejected" while measuring nothing -- the exact vacuous-green shape
this program keeps finding. So this probes the CONTRACT LAYER directly, which is the layer the
refutation was about:

    discriminating declared contract -> validate the corrupted doc against it, require errors > 0
    vacuous declared contract        -> run condition 4b's fallback, require it to refuse

Three mutations per artifact, each a different way to be wrong, plus the unmutated document as the
per-artifact control -- a contract that rejects the REAL artifact is broken in the other direction
and is reported separately rather than counted as a success.

TWO SCOPE CORRECTIONS MADE AFTER THE FIRST RUN, recorded rather than quietly folded in.

1. `drop-first-key` IS NOT A CORRUPTION FOR A SCHEMA-DOCUMENT ARTIFACT, and run 1 reported it as a
   surviving mutation anyway. WFA-0001's artifact is a JSON Schema pack whose first key is
   `$schema`; it also carries `$id`, and a schema with `$id` and no `$schema` is still a valid,
   still-discriminating schema. So the contract was right to accept it and my mutation was the
   thing that was wrong. That is an overclaim in the probe, not a defect in the predicate, and the
   honest fix is to narrow the CLAIM: single-key deletion is only required to be rejected for
   artifacts that are not themselves schema documents. The two garbage mutations still apply to
   every artifact, and those are the ones the refutation was actually about.

2. A CONTRACT THAT REJECTS ITS OWN REAL ARTIFACT IS REPORTED, NOT FAILED. Measured: 4 such
   artifacts, all under `command-center/adversarial/`, which the wave floor forbids this lane from
   touching and which a live sibling wave is still writing. Failing on them would make an unrelated
   sibling commit a red build -- the same reasoning `suitefloor`'s `casualty` note already records
   for this exact directory -- and none of them is a live false green, because all four are
   rejected by the predicate today. They are a finding for the owner, carried in the report.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "measure-guard"))

import blobread  # noqa: E402
import unitgate as ug  # noqa: E402


def load_ru():
    spec = importlib.util.spec_from_file_location(
        "ru_i4", REPO / "command-center" / "ready_units.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ru_i4"] = mod
    spec.loader.exec_module(mod)
    return mod


def mutations(doc: dict) -> list[tuple[str, object]]:
    """Three ways to be wrong. `state` is skipped: it is condition 5's job, not the contract's."""
    out: list[tuple[str, object]] = []
    keys = [k for k in doc if k != "state"]
    if keys:
        stripped = {k: v for k, v in doc.items() if k != keys[0]}
        out.append((f"drop-first-key({keys[0]})", stripped))
    out.append(("unrelated-garbage", {"totally": "unrelated", "passing_tests": 999999}))
    out.append(("empty-object", {}))
    return out


def contract_refuses(ru, resolver, schema: str, doc) -> bool:
    """Does the contract that ACTUALLY governs this artifact reject `doc`?"""
    if (
        isinstance(schema, str)
        and schema
        and ru.contract_discriminates(resolver, schema)
    ):
        try:
            return bool(resolver.validate_artifact(doc, schema))
        except Exception:
            return True
    ok, _why = ru._fallback_contract(doc, resolver)
    return not ok


def main() -> int:
    ru = load_ru()
    resolver = ru._load_resolver()
    if resolver is None:
        print(
            "FAILED:i4-percontract resolver unavailable; the probe would measure nothing"
        )
        return 1

    catalog = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text("utf-8")
    )
    tracked = ug.tracked_paths("HEAD")

    survivors: list[tuple[str, str, str]] = []
    exempt: list[tuple[str, str, str]] = []
    false_reds: list[tuple[str, str]] = []
    checked = 0
    per_unit_all_three = 0

    for unit in catalog["work_units"]:
        path = unit.get("output_path")
        if not path or path not in tracked:
            continue
        try:
            doc = json.loads(blobread.read_blob(path, "HEAD").decode("utf-8"))
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        checked += 1
        schema = unit.get("output_schema")

        # Control in the OTHER direction: the real artifact must be ACCEPTED by its contract.
        if contract_refuses(ru, resolver, schema, doc):
            false_reds.append((unit["id"], path))

        # Is the artifact itself a schema document? If so, a single-key deletion is not required
        # to invalidate it -- see scope correction 1 in the module docstring.
        is_schema_doc = ru.schema_doc_verdict(doc, resolver)[0]

        fired = 0
        muts = mutations(doc)
        for label, mutant in muts:
            if contract_refuses(ru, resolver, schema, mutant):
                fired += 1
            elif label.startswith("drop-first-key") and is_schema_doc:
                exempt.append((unit["id"], path, label))
            else:
                survivors.append((unit["id"], path, label))
        if fired == len(muts):
            per_unit_all_three += 1

    report = {
        "artifacts_checked": checked,
        "artifacts_where_all_three_mutations_were_rejected": per_unit_all_three,
        "surviving_mutations": survivors,
        "exempt_schema_document_key_deletions": exempt,
        "contracts_that_reject_their_own_real_artifact": false_reds,
    }
    Path(__file__).with_suffix(".out.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print(f"  artifacts checked (from the COMMITTED blob): {checked}")
    print(f"  artifacts rejecting all 3 mutations         : {per_unit_all_three}")
    print(f"  SURVIVING mutations (a vacuous contract)    : {len(survivors)}")
    for uid, path, label in survivors[:10]:
        print(f"     SURVIVOR {uid} {label} -> accepted at {path}")
    print(f"  EXEMPT key-deletions on schema documents    : {len(exempt)}")
    for uid, path, label in exempt[:10]:
        print(
            f"     EXEMPT {uid} {label} -- optional key on a schema doc, not a corruption"
        )
    print(f"  REPORTED contracts rejecting their own real artifact: {len(false_reds)}")
    for uid, path in false_reds[:10]:
        print(f"     REPORT {uid} -> {path}")

    # Fail closed on a collapsed read BEFORE any count is believed.
    if checked < ug.MIN_ARTIFACTS:
        print(
            f"FAILED:i4-percontract only {checked} artifacts read; the probe collapsed"
        )
        return 1
    # The load-bearing half: nothing may accept unrelated garbage or the empty object, and no
    # NON-schema-document artifact may accept a single-key deletion.
    if survivors:
        print(
            f"FAILED:i4-percontract {len(survivors)} mutation(s) survived a real contract"
        )
        return 1
    print(
        f"SUCCESS:i4-percontract all {checked} committed artifacts reject unrelated garbage and "
        f"the empty object; {checked - len(exempt)} also reject a single-key deletion "
        f"({len(exempt)} exempt as schema documents). {len(false_reds)} contract(s) reject their "
        "own real artifact -- REPORTED, not gated, see the docstring"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
