#!/usr/bin/env python3
"""Probe 2: catalog tests + planted mutants. Independent of probe 1's verdict.

Controls:
  * known-present option-universe:M-40 is IMPLEMENTED with an on-disk anchor
  * architecture-mechanism:MECH-16 is IMPLEMENTED (unambiguous MECH- prefix)
  * bare M-16 is NOT-CHECKED and is not assigned a terminal state
  * four-way counts sum to selected-set size; states exclusive and exhaustive
  * planted double disposition on M-40 becomes NOT-CHECKED / DOUBLE-DISPOSITION
  * forcing IMPLEMENTED onto bare M-16 is rejected by the bare-token checker
  * schema rejects garbage
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import close as C  # noqa: E402

ART = REPO / C.OUTPUT_REL


def rows_by_id(doc: dict, selected_id: str) -> list[dict]:
    return [
        d
        for d in (doc.get("dispositions") or [])
        if d.get("selected_id") == selected_id
    ]


def main() -> int:
    if not ART.is_file():
        print("FAILED:SYN-0028-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if C.SENTINEL not in json.dumps(doc):
        print("FAILED:SYN-0028-probe2 sentinel-absent")
        return 1

    control = C.close(REPO)
    ctrl_rows = control["control"]["dispositions"]
    ctrl_doc = {"dispositions": ctrl_rows, "counts": control["control"]["counts"]}

    m40 = [d for d in ctrl_rows if d["selected_id"] == C.KNOWN_PRESENT_ID]
    print(
        f"known_present n={len(m40)} state={[d.get('terminal_state') for d in m40]} "
        f"anchor={[d.get('anchor') for d in m40]}"
    )
    if len(m40) != 1 or m40[0]["terminal_state"] != C.IMPLEMENTED:
        print("FAILED:SYN-0028-probe2 known-present M-40 is not IMPLEMENTED")
        return 1
    if "implemented-M-40.md" not in str(m40[0].get("anchor") or ""):
        print("FAILED:SYN-0028-probe2 known-present missing implementation anchor")
        return 1
    if not m40[0].get("resolved"):
        print("FAILED:SYN-0028-probe2 known-present was not namespace-resolved")
        return 1

    mech = [d for d in ctrl_rows if d["selected_id"] == "architecture-mechanism:MECH-16"]
    print(f"mech16 n={len(mech)} state={[d.get('terminal_state') for d in mech]}")
    if len(mech) != 1 or mech[0]["terminal_state"] != C.IMPLEMENTED:
        print("FAILED:SYN-0028-probe2 MECH-16 did not resolve to IMPLEMENTED")
        return 1

    bare = [d for d in ctrl_rows if d["selected_id"] == C.BARE_AMBIGUOUS_ID]
    print(
        f"bare_M-16 n={len(bare)} state={[d.get('terminal_state') for d in bare]} "
        f"reason={[d.get('not_checked_reason') for d in bare]} "
        f"cands={[d.get('candidate_namespaces') for d in bare]}"
    )
    if len(bare) != 1:
        print("FAILED:SYN-0028-probe2 planted bare M-16 missing from selected set")
        return 1
    if bare[0]["terminal_state"] != C.NOT_CHECKED:
        print("FAILED:SYN-0028-probe2 bare M-16 was assigned a terminal state")
        return 1
    if bare[0].get("not_checked_reason") != "NAMESPACE-AMBIGUOUS":
        print("FAILED:SYN-0028-probe2 bare M-16 reason is not NAMESPACE-AMBIGUOUS")
        return 1
    if len(bare[0].get("candidate_namespaces") or []) < 2:
        print("FAILED:SYN-0028-probe2 bare M-16 does not collide two namespaces")
        return 1
    if bare[0].get("resolved"):
        print("FAILED:SYN-0028-probe2 bare M-16 was marked resolved")
        return 1

    art_bare = rows_by_id(doc, C.BARE_AMBIGUOUS_ID)
    if not art_bare or art_bare[0].get("terminal_state") in C.TERMINAL:
        print("FAILED:SYN-0028-probe2 artifact assigned a state to bare M-16")
        return 1

    counts = control["control"]["counts"]
    print(
        f"control_counts impl={counts['implemented']} sup={counts['superseded']} "
        f"rej={counts['rejected_with_owner_reasoning']} "
        f"amb={counts['ambiguous_not_checked']} n={counts['selected_set_size']} "
        f"sum={counts['sum']}"
    )
    if counts["sum"] != counts["selected_set_size"]:
        print("FAILED:SYN-0028-probe2 control four-way sum mismatch")
        return 1
    if counts["implemented"] < 1 or counts["superseded"] < 1:
        print("FAILED:SYN-0028-probe2 control missing terminal variety")
        return 1
    if counts["rejected_with_owner_reasoning"] < 1:
        print("FAILED:SYN-0028-probe2 control missing owner-rejected row")
        return 1
    if counts["ambiguous_not_checked"] < 1:
        print("FAILED:SYN-0028-probe2 control missing ambiguous row")
        return 1
    if counts["silently_dropped"] != 0:
        print("FAILED:SYN-0028-probe2 control silently dropped a selected id")
        return 1

    ids = [d["selected_id"] for d in ctrl_rows]
    if len(ids) != len(set(ids)):
        print("FAILED:SYN-0028-probe2 duplicate selected_id in control dispositions")
        return 1
    buckets = {C.IMPLEMENTED: [], C.SUPERSEDED: [], C.REJECTED: [], C.NOT_CHECKED: []}
    for d in ctrl_rows:
        buckets[d["terminal_state"]].append(d["selected_id"])
    overlap = set(buckets[C.IMPLEMENTED]) & set(buckets[C.SUPERSEDED])
    overlap |= set(buckets[C.IMPLEMENTED]) & set(buckets[C.REJECTED])
    overlap |= set(buckets[C.SUPERSEDED]) & set(buckets[C.REJECTED])
    print(f"exclusive_overlap={sorted(overlap)}")
    if overlap:
        print("FAILED:SYN-0028-probe2 an id occupies two terminal buckets")
        return 1

    # Planted double disposition: M-40 must not be silently collapsed to one state.
    planted_trace = C.load_json(C.PLANTED / "double-disposition.json")["rows"]
    base_trace = [
        r
        for r in C.load_trace_control()
        if str(r.get("option_id") or "") != C.KNOWN_PRESENT_ID
    ]
    mutant_pack = C.pack_corpus(
        repo=REPO,
        corpus="control-reconstruction",
        namespaces=C.namespace_table(C.control_declarations(REPO)),
        selected_items=C.load_selected_control()[0],
        selected_source="planted-double-disposition",
        trace_rows=base_trace + planted_trace,
    )
    mutant_m40 = [
        d for d in mutant_pack["dispositions"] if d["selected_id"] == C.KNOWN_PRESENT_ID
    ]
    print(
        f"double_disp n={len(mutant_m40)} state={[d.get('terminal_state') for d in mutant_m40]} "
        f"reason={[d.get('not_checked_reason') for d in mutant_m40]}"
    )
    if (
        len(mutant_m40) != 1
        or mutant_m40[0]["terminal_state"] != C.NOT_CHECKED
        or mutant_m40[0].get("not_checked_reason") != "DOUBLE-DISPOSITION"
    ):
        print("FAILED:SYN-0028-probe2 double disposition was silently collapsed")
        return 1
    if not mutant_pack["counts_sum_equals_selected"]:
        print("FAILED:SYN-0028-probe2 double-disposition pack broke the four-way sum")
        return 1

    # Forcing a terminal state onto bare M-16 must be caught.
    forced = copy.deepcopy(ctrl_doc)
    mutated = False
    for d in forced["dispositions"]:
        if d.get("selected_id") == C.BARE_AMBIGUOUS_ID:
            d["terminal_state"] = C.IMPLEMENTED
            d["resolved"] = True
            d["not_checked_reason"] = None
            mutated = True
    if not mutated:
        print("FAILED:SYN-0028-probe2 no bare M-16 row to mutate")
        return 1
    viol = C.bare_assigned_terminal(forced["dispositions"])
    print(f"bare_mutant_violations={len(viol)}")
    if not viol:
        print("FAILED:SYN-0028-probe2 bare-token checker accepted IMPLEMENTED on M-16")
        return 1

    garbage_ok = False
    try:
        import jsonschema

        schema = json.loads((REPO / C.SCHEMA_REL).read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(schema).validate({"totally": "unrelated"})
    except Exception:
        garbage_ok = True
    print(f"schema_rejects_garbage={garbage_ok}")
    if not garbage_ok:
        print("FAILED:SYN-0028-probe2 schema accepts garbage")
        return 1

    rej = [d for d in ctrl_rows if d["terminal_state"] == C.REJECTED]
    if not rej or "owner-decisions.md" not in str(rej[0].get("owner_approval_anchor") or rej[0].get("anchor") or ""):
        print("FAILED:SYN-0028-probe2 rejection lacks owner-approval anchor")
        return 1

    print("SUCCESS:SYN-0028-probe2 controls reviewer-independent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
