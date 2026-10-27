"""IMP-0166 probe 1 (source): the 6 spec-named stopping expressions parse and
evaluate on synthetic stop/continue states; Kleene UNKNOWN and the weighted
variant are held; the two recorded negative controls fire.

Exit 0 iff every assertion below passes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import algebra  # noqa: E402
from candidates import SPEC_EXPRESSIONS  # noqa: E402

RAW = HERE / "probe1-six-expressions.raw.txt"

STOP_STATES = {
    "spec-10937": {"unique_ideas": 150, "completeness_score": 0.95},
    "spec-10938": {"consensus": 0.97, "no_new_objection_rounds": 3},
    "spec-10939": {"unanimity": True, "max_rounds": 6},
    "spec-10940": {"quality_gate": "PASS", "unresolved_load_bearing_counterexample": 0},
    "spec-10941": {"evidence_saturation": True, "time_minutes": 60},
    "spec-10942": {"proof_of_impossibility": True},
}
CONTINUE_STATES = {
    "spec-10937": {"unique_ideas": 10, "completeness_score": 0.5},
    "spec-10938": {"consensus": 0.5, "no_new_objection_rounds": 0},
    "spec-10939": {"unanimity": False, "max_rounds": 6},
    "spec-10940": {"quality_gate": "FAIL", "unresolved_load_bearing_counterexample": 2},
    "spec-10941": {"evidence_saturation": False, "time_minutes": 60},
    "spec-10942": {"proof_of_impossibility": False},
}
ALT_STATES = {  # one conjunct satisfied, the other not (ALL) / the other disjunct (ANY)
    "spec-10937": {"unique_ideas": 150, "completeness_score": 0.5},
    "spec-10938": {"consensus": 0.97, "no_new_objection_rounds": 0},
    "spec-10939": {"unanimity": False, "max_rounds": 12},
    "spec-10940": {"quality_gate": "PASS", "unresolved_load_bearing_counterexample": 1},
    "spec-10941": {"evidence_saturation": False, "time_minutes": 200},
    "spec-10942": {"proof_of_impossibility": False},
}
PARTIAL_STATES = {  # one metric absent -> Kleene UNKNOWN, never TRUE/FALSE
    "spec-10937": {"unique_ideas": 150},
    "spec-10938": {"consensus": 0.97},
    "spec-10939": {"unanimity": False},
    "spec-10940": {"quality_gate": "PASS"},
    "spec-10941": {"evidence_saturation": False},
    "spec-10942": {},
}

lines, results, ok_all = [], [], True
for e in SPEC_EXPRESSIONS:
    eid = e["id"]
    tree = algebra.parse(e["text"])
    stop_tri = algebra.evaluate(tree, STOP_STATES[eid])
    cont_tri = algebra.evaluate(tree, CONTINUE_STATES[eid])
    alt_tri = algebra.evaluate(tree, ALT_STATES[eid])
    part_tri = algebra.evaluate(tree, PARTIAL_STATES[eid])
    # For an OR rule a partially-satisfied alternative state still TRUEs the
    # stop side (stop_alt_tri); for AND/CMP rules it stays FALSE (continue_alt_tri).
    is_or = tree["kind"] == "ANY"
    alt_key = "stop_alt_tri" if is_or else "continue_alt_tri"
    alt_expected = "TRUE" if is_or else "FALSE"
    row = {
        "id": f"spec-{e['spec_line']}", "spec_line": e["spec_line"], "text": e["text"],
        "tree": tree,
        "stop_tri": stop_tri, "continue_tri": cont_tri, alt_key: alt_tri,
        "partial_unknown_tri": part_tri,
        "stop_decision": algebra.decide(stop_tri),
        "continue_decision": algebra.decide(cont_tri),
    }
    ok = (stop_tri == "TRUE" and cont_tri == "FALSE" and alt_tri == alt_expected
          and part_tri == "UNKNOWN"
          and row["stop_decision"] == "STOP" and row["continue_decision"] == "CONTINUE")
    row["ok"] = ok
    ok_all = ok_all and ok
    results.append(row)
    lines.append(json.dumps(row))

weighted = algebra.parse(
    "WEIGHTED(0.7, unique_ideas >= 100: 0.4, completeness_score >= 0.90: 0.4, "
    "consensus >= 0.95: 0.3)")
w_stop = algebra.evaluate(weighted, {"unique_ideas": 150, "completeness_score": 0.95, "consensus": 0.97})
w_cont = algebra.evaluate(weighted, {"unique_ideas": 0, "completeness_score": 0.1, "consensus": 0.0})
w_part = algebra.evaluate(weighted, {"unique_ideas": 150})
lines.append(json.dumps({"weighted": {"stop": w_stop, "continue": w_cont, "partial": w_part}}))
assert (w_stop, w_cont, w_part) == ("TRUE", "FALSE", "UNKNOWN"), "weighted Kleene broke"
ok_all = ok_all and True

# Negative control: an unsuccessful search is NOT proof of impossibility.
proof = algebra.parse("proof_of_impossibility == true")
bad = algebra.evaluate(proof, {"search_exhausted": True, "proof_of_impossibility": False})
assert bad == "FALSE", "unsuccessful-search control failed"
good = algebra.evaluate(proof, {"search_exhausted": True, "proof_of_impossibility": True})
assert good == "TRUE", "proof control failed"

# Negative control: TRUE AND UNKNOWN is UNKNOWN, never TRUE (AND-as-OR detector).
kleene = algebra.parse("unique_ideas >= 100 AND completeness_score >= 0.90")
kres = algebra.evaluate(kleene, {"unique_ideas": 150})
assert kres == "UNKNOWN", "kleene AND held as UNKNOWN"
kres2 = algebra.evaluate(kleene, {"unique_ideas": 150, "completeness_score": 0.95})
assert kres2 == "TRUE", "both-bound control failed"

parsed_n = sum(1 for r in results)
lines.append(f"parsed_and_evaluated={parsed_n}/6 kleene_unknown=held weighted=held ANY=held")
assert parsed_n == 6 and ok_all, "not all 6 spec expressions behaved as specified"
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"parsed_and_evaluated": f"{parsed_n}/6",
                              "kleene_unknown": "held", "weighted": "held",
                              "negative_controls": ["unsuccessful-search-is-not-impossibility",
                                                    "kleene-and-not-or"]}))
print(f"SUCCESS:IMP-0166-probe1 6/6 spec expressions parse and evaluate")
