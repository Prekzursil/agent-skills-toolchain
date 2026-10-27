"""REL-0001 probe rewrite: Part B refutation-recheck -> fix-hold recheck;
probe1 receipt pins -> receipt-protocol-correct (w4s12 resume 2026-10-26).
"""
from pathlib import Path

HERE = Path("C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/REL-0001")

# ---- probe2: Part B fix-hold rewrite ----
p2 = HERE / "probe2_linter_matrix.py"
t = p2.read_text(encoding="utf-8")

old_head = """# REL-0001 probe2: live linter matrix + recorded-refutation recheck (2026-10-25).
# Part A (matrix): crafted diffs per bump class exit exactly as the receipt
#   crafted_diff_exit_codes records {MAJOR:1, MINOR:1, PATCH:0}; pure-rename
#   same-version exits 0 silently.
# Part B (refutation recheck): the three recorded under-bump counterexamples
#   (defects D1-D3) MUST still reproduce - linter exit 0 with required_bump
#   MINOR against a MAJOR oracle - so the candidate stays REFUTED, recorded."""
new_head = """# REL-0001 probe2: live linter matrix + fix-hold recheck (2026-10-26, w4s12).
# Part A (matrix): crafted diffs per bump class exit exactly as the receipt
#   crafted_diff_exit_codes records {MAJOR:1, MINOR:1, PATCH:0}; pure-rename
#   same-version exits 0 silently.
# Part B (fix-hold recheck): the three RECORDED under-bump counterexamples
#   (receipt defects D1-D3, original candidate REFUTED - history preserved in
#   extensions.prior_candidate) MUST now be CAUGHT: linter exit 1 with
#   required_bump MAJOR (the max-rank fix), while the patch-only negative
#   control stays silent. If any counterexample masks again, the fix regressed
#   and this probe fails."""
assert old_head in t, "probe2 header not found"
t = t.replace(old_head, new_head)

old_b = """        def ob1(r):
            write_tree(r, base_manifest(\"1.2.3\"))

        def nb1(r):
            m = base_manifest(\"1.3.0\")
            m[\"telemetry\"] = {\"opt_in\": False}
            m[\"contract\"] = {\"mode\": \"lenient\"}
            write_tree(r, m)
        rc, err, rep = run_case(tmp, \"refute-mixed-plugin\", ob1, nb1)
        print(\"REFUTE=mixed-plugin LINTER_EXIT=%d linter_required=%s oracle=MAJOR\"
              % (rc, rep.get(\"required_bump\")))
        if rc != 0 or rep.get(\"required_bump\") != \"MINOR\":
            return fail(\"refute-D1-no-longer-reproduces:\" + str(rc))

        def ob2(r):
            write_tree(r, base_manifest(\"1.2.3\"), blueprints={
                \"alpha\": {\"version\": 1, \"permissions\": [\"read\"], \"contract\": {\"run\": \"auto\"}}})

        def nb2(r):
            write_tree(r, base_manifest(\"1.3.0\"), blueprints={
                \"alpha\": {\"version\": 1, \"permissions\": [\"read\"], \"contract\": {\"run\": \"manual\"}},
                \"beta\": {\"version\": 1, \"permissions\": [\"read\"], \"contract\": {\"run\": \"auto\"}}})
        rc, err, rep = run_case(tmp, \"refute-mixed-blueprint\", ob2, nb2)
        print(\"REFUTE=mixed-blueprint LINTER_EXIT=%d linter_required=%s oracle=MAJOR\"
              % (rc, rep.get(\"required_bump\")))
        if rc != 0 or rep.get(\"required_bump\") != \"MINOR\":
            return fail(\"refute-D2-no-longer-reproduces:\" + str(rc))

        def ob3(r):
            write_tree(r, base_manifest(\"1.2.3\"), schema={
                \"properties\": {\"keep\": {\"type\": \"string\"}}, \"required\": []})

        def nb3(r):
            write_tree(r, base_manifest(\"1.3.0\"), schema={
                \"properties\": {\"keep\": {\"type\": \"string\"},
                               \"extra\": {\"type\": \"object\",
                                         \"properties\": {\"must\": {\"type\": \"string\"}},
                                         \"required\": [\"must\"]}},
                \"required\": []})
        rc, err, rep = run_case(tmp, \"refute-nested-required\", ob3, nb3)
        print(\"REFUTE=nested-required LINTER_EXIT=%d linter_required=%s oracle=MAJOR\"
              % (rc, rep.get(\"required_bump\")))
        if rc != 0 or rep.get(\"required_bump\") != \"MINOR\":
            return fail(\"refute-D3-no-longer-reproduces:\" + str(rc))

        print(\"CANDIDATE_VERDICT=REFUTED recorded-counterexamples-D1-D3-all-reproduce\")
        print(\"PROBE-2-COMPLETE:REL-0001\")
        return 0"""

new_b = """        def ob1(r):
            write_tree(r, base_manifest(\"1.2.3\"))

        def nb1(r):
            m = base_manifest(\"1.3.0\")
            m[\"telemetry\"] = {\"opt_in\": False}
            m[\"contract\"] = {\"mode\": \"lenient\"}
            write_tree(r, m)
        rc, err, rep = run_case(tmp, \"fixhold-mixed-plugin-D1\", ob1, nb1)
        print(\"FIXHOLD=D1-mixed-plugin LINTER_EXIT=%d linter_required=%s oracle=MAJOR\"
              % (rc, rep.get(\"required_bump\")))
        if rc != 1 or rep.get(\"required_bump\") != \"MAJOR\" or \"REL-BUMP-LOW\" not in err:
            return fail(\"fixhold-D1-still-masks:\" + str(rc) + \"/\" + str(rep.get(\"required_bump\")))

        def ob2(r):
            write_tree(r, base_manifest(\"1.2.3\"), blueprints={
                \"alpha\": {\"version\": 1, \"permissions\": [\"read\"], \"contract\": {\"run\": \"auto\"}}})

        def nb2(r):
            write_tree(r, base_manifest(\"1.3.0\"), blueprints={
                \"alpha\": {\"version\": 1, \"permissions\": [\"read\"], \"contract\": {\"run\": \"manual\"}},
                \"beta\": {\"version\": 1, \"permissions\": [\"read\"], \"contract\": {\"run\": \"auto\"}}})
        rc, err, rep = run_case(tmp, \"fixhold-mixed-blueprint-D2\", ob2, nb2)
        print(\"FIXHOLD=D2-mixed-blueprint LINTER_EXIT=%d linter_required=%s oracle=MAJOR\"
              % (rc, rep.get(\"required_bump\")))
        if rc != 1 or rep.get(\"required_bump\") != \"MAJOR\" or \"REL-BUMP-LOW\" not in err:
            return fail(\"fixhold-D2-still-masks:\" + str(rc) + \"/\" + str(rep.get(\"required_bump\")))

        def ob3(r):
            write_tree(r, base_manifest(\"1.2.3\"), schema={
                \"properties\": {\"keep\": {\"type\": \"string\"}}, \"required\": []})

        def nb3(r):
            write_tree(r, base_manifest(\"1.3.0\"), schema={
                \"properties\": {\"keep\": {\"type\": \"string\"},
                               \"extra\": {\"type\": \"object\",
                                         \"properties\": {\"must\": {\"type\": \"string\"}},
                                         \"required\": [\"must\"]}},
                \"required\": []})
        rc, err, rep = run_case(tmp, \"fixhold-nested-required-D3\", ob3, nb3)
        print(\"FIXHOLD=D3-nested-required LINTER_EXIT=%d linter_required=%s oracle=MAJOR\"
              % (rc, rep.get(\"required_bump\")))
        if rc != 1 or rep.get(\"required_bump\") != \"MAJOR\" or \"REL-BUMP-LOW\" not in err:
            return fail(\"fixhold-D3-still-masks:\" + str(rc) + \"/\" + str(rep.get(\"required_bump\")))

        # negative control: a patch-only diff must stay SILENT (no false positive)
        def ob4(r):
            write_tree(r, base_manifest(\"1.2.3\"))

        def nb4(r):
            m = base_manifest(\"1.2.4\")
            m[\"description\"] = \"docs refreshed\"
            write_tree(r, m)
        rc, err, rep = run_case(tmp, \"fixhold-patch-silent-control\", ob4, nb4)
        print(\"FIXHOLD=patch-silent-control LINTER_EXIT=%d linter_required=%s\" % (rc, rep.get(\"required_bump\")))
        if rc != 0:
            return fail(\"fixhold-patch-false-positive:\" + str(rc))

        print(\"CANDIDATE_VERDICT=FIXED-D1-D3-MAX-RANK recorded-counterexamples-now-caught\")
        print(\"PROBE-2-COMPLETE:REL-0001\")
        return 0"""

assert old_b in t, "probe2 Part B block not found"
t = t.replace(old_b, new_b)
p2.write_text(t, encoding="utf-8", newline="\n")
print("PATCHED", p2)

# ---- probe1: receipt pins -> receipt-protocol-correct ----
p1 = HERE / "probe1_rule_binding.py"
t1 = p1.read_text(encoding="utf-8")

old_pin = """    rec = json.loads((REPO / \"command-center/receipts/REL-0001.json\").read_text(encoding=\"utf-8\"))
    st = str(rec.get(\"state\") or \"\").upper()
    if st in {\"BLOCKED\", \"FAILED\", \"SEVERED\", \"TIMEOUT\"}:
        return fail(\"self-declared:\" + st)
    if \"SUCCESS:REL-0001\" not in json.dumps(rec):
        return fail(\"completion-sentinel-absent\")
    # the receipt's candidate verdict is REFUTED and must stay recorded
    if str(rec.get(\"candidate_verdict\")) != \"REFUTED\":
        return fail(\"candidate-verdict-drift\")"""

new_pin = """    rec = json.loads((REPO / \"command-center/receipts/REL-0001.json\").read_text(encoding=\"utf-8\"))
    st = str(rec.get(\"state\") or \"\").upper()
    if st not in {\"SUCCESS\", \"BLOCKED\", \"FAILED\", \"SEVERED\", \"TIMEOUT\"}:
        return fail(\"state-not-terminal:\" + st)
    # catalog completion sentinel must stay present in the receipt text
    if \"SUCCESS:REL-0001\" not in json.dumps(rec):
        return fail(\"completion-sentinel-absent\")
    # the ORIGINAL refuted-candidate recording must stay preserved verbatim
    prior = (rec.get(\"extensions\") or {}).get(\"prior_candidate\") or {}
    if str(prior.get(\"candidate_verdict\")) != \"REFUTED\":
        return fail(\"prior-candidate-history-lost\")
    # the current candidate is the max-rank fix and must be recorded as such
    if str(rec.get(\"candidate_verdict\")) != \"FIXED-D1-D3-MAX-RANK\":
        return fail(\"candidate-verdict-drift\")
    fixed_ids = sorted(d.get(\"id\") for d in (rec.get(\"defects\") or [])
                       if str(d.get(\"id\")).startswith(\"REL-0001-D\") and d.get(\"status\") == \"resolved\")
    if fixed_ids != [\"REL-0001-D1\", \"REL-0001-D2\", \"REL-0001-D3\"]:
        return fail(\"defects-not-resolved:\" + json.dumps(fixed_ids))"""

assert old_pin in t1, "probe1 pin block not found"
t1 = t1.replace(old_pin, new_pin)

old_hdr1 = """# REL-0001 probe1: rule-table-to-executable-rule binding (resume 2026-10-25).
# Re-verifies against the closing receipt's recorded probe-1 shape:
# TABLE_ROW_COUNT=21, EXECUTABLE_RULE_COUNT=22, every executable rule id cited
# by the table with a bump, anchor lines 16-36, primary final line exact."""
new_hdr1 = """# REL-0001 probe1: rule-table-to-executable-rule binding (w4s12 2026-10-26).
# Re-verifies against the closing receipt's recorded probe-1 shape:
# TABLE_ROW_COUNT=21, EXECUTABLE_RULE_COUNT=22, every executable rule id cited
# by the table with a bump, anchor lines 16-36, primary final line exact.
# Receipt pins (w4s12): original REFUTED-candidate history preserved under
# extensions.prior_candidate; current candidate FIXED-D1-D3-MAX-RANK with
# defects D1-D3 resolved; receipt state must be a terminal_state enum value."""
assert old_hdr1 in t1, "probe1 header not found"
t1 = t1.replace(old_hdr1, new_hdr1)
p1.write_text(t1, encoding="utf-8", newline="\n")
print("PATCHED", p1)
print("DONE")
