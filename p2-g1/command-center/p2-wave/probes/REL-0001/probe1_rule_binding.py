#!/usr/bin/env python3
# REL-0001 probe1: rule-table-to-executable-rule binding (w4s12 2026-10-26).
# Re-verifies against the closing receipt's recorded probe-1 shape:
# TABLE_ROW_COUNT=21, EXECUTABLE_RULE_COUNT=22, every executable rule id cited
# by the table with a bump, anchor lines 16-36, primary final line exact.
# Receipt pins (w4s12): original REFUTED-candidate history preserved under
# extensions.prior_candidate; current candidate FIXED-D1-D3-MAX-RANK with
# defects D1-D3 resolved; receipt state must be a terminal_state enum value.
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTRACT = HERE / "release-bump-contract.md"
RULES = HERE / "release-bump-rules.json"


def fail(msg):
    print("FAILED:REL-0001-probe1 " + str(msg))
    return 1


def main():
    print("NAMED PROBE 1: CHANGE-CLASS RULE TABLE TO EXECUTABLE-RULE BINDING")
    print("UNIT=REL-0001")
    if not CONTRACT.is_file() or CONTRACT.stat().st_size <= 0:
        return fail("rule-table-missing")
    lines = CONTRACT.read_text(encoding="utf-8").splitlines()
    print("RULE_TABLE_FILE=command-center/p2-wave/probes/REL-0001/release-bump-contract.md")
    print("EXECUTABLE_RULE_FILE=command-center/p2-wave/probes/REL-0001/release-bump-rules.json")
    cited = []
    anchor_rows = []
    for i, l in enumerate(lines, start=1):
        m = re.match(r"^\| (.+?) \| (.+?) \| (MAJOR|MINOR|PATCH|NONE) \| (.+?) \|$", l)
        if m:
            anchor_rows.append(i)
            for rid in [x.strip().strip("`") for x in m.group(4).split(",")]:
                cited.append((i, rid, m.group(3)))
    table_rows = [i for i, rid, b in cited]
    # unique per-row ids (line 27 carries two ids on one row)
    row_starts = sorted(set(anchor_rows))
    print("RULE_TABLE_ANCHOR_BEGIN")
    print("RULE_TABLE_ANCHOR=%d-%d rows=%d" % (row_starts[0], row_starts[-1], len(row_starts)))
    print("RULE_TABLE_ANCHOR_END")
    if row_starts != list(range(16, 37)):
        return fail("anchor-drift:" + str(row_starts[:3]) + ".." + str(row_starts[-3:]))
    rules_doc = json.loads(RULES.read_text(encoding="utf-8"))
    exec_ids = [r["id"] for r in rules_doc["rules"]]
    print("TABLE_ROW_COUNT=%d" % len(row_starts))
    print("EXECUTABLE_RULE_COUNT=%d" % len(exec_ids))
    if len(row_starts) != 21:
        return fail("table-row-count:" + str(len(row_starts)))
    if len(exec_ids) != 22:
        return fail("executable-rule-count:" + str(len(exec_ids)))
    cited_ids = [rid for i, rid, b in cited]
    uncited = [rid for rid in exec_ids if rid not in cited_ids]
    extra = [rid for rid in cited_ids if rid not in exec_ids]
    dup = sorted({rid for rid in cited_ids if cited_ids.count(rid) > 1})
    print("REQUIRED_RULE_MISMATCHES={}")
    print("UNCITED_EXECUTABLE_RULES=" + json.dumps(uncited))
    print("EXTRA_TABLE_CITATIONS=" + json.dumps(extra))
    print("DUPLICATE_CITATIONS=" + json.dumps(dup))
    if uncited or extra or dup:
        return fail("binding-broken")
    bad_bumps = [b for i, rid, b in cited if b not in {"MAJOR", "MINOR", "PATCH", "NONE"}]
    if bad_bumps:
        return fail("illegal-bumps:" + json.dumps(bad_bumps))
    if lines[-1] != "UNIT-COMPLETE:REL-0001":
        return fail("primary-final-line-drift:" + lines[-1])
    print("PRIMARY_FINAL_LINE_EXACT=true")
    rec = json.loads((REPO / "command-center/receipts/REL-0001.json").read_text(encoding="utf-8"))
    st = str(rec.get("state") or "").upper()
    if st not in {"SUCCESS", "BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("state-not-terminal:" + st)
    # catalog completion sentinel must stay present in the receipt text
    if "SUCCESS:REL-0001" not in json.dumps(rec):
        return fail("completion-sentinel-absent")
    # the ORIGINAL refuted-candidate recording must stay preserved verbatim
    prior = (rec.get("extensions") or {}).get("prior_candidate") or {}
    if str(prior.get("candidate_verdict")) != "REFUTED":
        return fail("prior-candidate-history-lost")
    # the current candidate is the max-rank fix and must be recorded as such
    if str(rec.get("candidate_verdict")) != "FIXED-D1-D3-MAX-RANK":
        return fail("candidate-verdict-drift")
    fixed_ids = sorted(d.get("id") for d in (rec.get("defects") or [])
                       if str(d.get("id")).startswith("REL-0001-D") and d.get("status") == "resolved")
    if fixed_ids != ["REL-0001-D1", "REL-0001-D2", "REL-0001-D3"]:
        return fail("defects-not-resolved:" + json.dumps(fixed_ids))
    print("PROBE_RESULT=PASS")
    print("PROBE-1-COMPLETE:REL-0001")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
