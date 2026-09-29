"""Both-states tests for the destructive-verdict gate (check.py).

Run:  python test_destructive_verdict.py
The both-states contract: the sensor FIRES on the defect state (evidence-free
destructive verdict in a durable doc), PASSES the compliant state (RECALL+DEPS
present), does NOT fire on past-tense completion records, non-durable paths,
or non-markdown files, and FAILS OPEN on garbage.
"""
import importlib.util
import os
import sys
import tempfile

SPEC = importlib.util.spec_from_file_location(
    "check_dv", os.path.join(os.path.dirname(os.path.abspath(__file__)), "check.py")
)
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

DV = check._check_destructive_verdict

FAILS = []


def case(name, got, want_fired):
    fired = bool(got[0])
    ok = fired == want_fired
    print(("PASS " if ok else "FAIL ") + name + (" -> " + got[0][0][:70] if fired else ""))
    if not ok:
        FAILS.append(name)


with tempfile.TemporaryDirectory() as td:
    # 1. DEFECT: evidence-free destructive verdict in a knowledge doc -> FIRES
    p1 = os.path.join(td, "knowledge", "x.md")
    os.makedirs(os.path.dirname(p1), exist_ok=True)
    open(p1, "w", encoding="utf-8").write("# Plan\n\nWe retire McpHub middleman next wave.\n")
    case("defect fires", DV(p1), True)

    # 2. COMPLIANT: same verdict + RECALL: and DEPS: -> clean
    p2 = os.path.join(td, "knowledge", "y.md")
    open(p2, "w", encoding="utf-8").write(
        "# Plan\n\nWe retire McpHub middleman next wave.\n\n"
        "RECALL: basic-memory search 'McpHub restore 2026-09-20'\n"
        "DEPS: 40 hub-only backends (angr, ghidra-mcp, ...) vs 37 user-scope entries\n"
    )
    case("compliant passes", DV(p2), False)

    # 3. PAST-TENSE completion record -> clean (records done work)
    p3 = os.path.join(td, "knowledge", "z.md")
    open(p3, "w", encoding="utf-8").write(
        "portproxy deleted, .mcp.json removed from project scope, locks cleared, "
        "daemon restored 2026-09-29.\n"
    )
    case("past-tense passes", DV(p3), False)

    # 4. NON-DURABLE path -> clean even with verdict lines
    p4 = os.path.join(td, "notes.md")
    open(p4, "w", encoding="utf-8").write("We retire McpHub middleman next wave.\n")
    case("non-durable path passes", DV(p4), False)

    # 5. NON-MARKDOWN ext -> clean
    p5 = os.path.join(td, "knowledge", "data.json")
    open(p5, "w", encoding="utf-8").write('{"note": "retire the hub"}')
    case("non-md ext passes", DV(p5), False)

# 6. FAIL-OPEN: garbage path / unreadable -> no crash, no fire
case("fail-open on nonexistent", DV(os.path.join(td, "nope", "deep", "census.md")), False)

# 7. REAL DOC regression guard: tonight's census (has the REGRESSION-RISK section,
#    past-tense lines) must not fire — it records done work.
census = r"C:\Users\Prekzursil\.agents\knowledge\MCP-UNIFICATION-CENSUS-2026-09-29.md"
if os.path.isfile(census):
    got = DV(census)
    print(("NOTE " if got[0] else "PASS ") + "real census: " + (got[0][0][:80] if got[0] else "clean"))

if FAILS:
    print("FAILED:", FAILS)
    sys.exit(1)
print("ALL BOTH-STATES TESTS PASS")
