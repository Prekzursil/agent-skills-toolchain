"""Controls for the gap-check Stop hook.

The control that matters most is CLEAN -> SILENT. A gate that fires every turn is
noise, gets tuned out, and is then worse than no gate at all. A suite that only
proved "it detects a gap" would pass against a hook that always fires.

Run: python -m pytest test_gap_check.py -q
"""
import datetime
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "gap_check.py")

_spec = importlib.util.spec_from_file_location("gc", HOOK)
gc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gc)

FUTURE = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
PAST = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()

HEADER = "| ID | Item | Why | Owner | Review by | Status | Evidence |\n|---|---|---|---|---|---|---|\n"


def run_with(register_text):
    """Run the hook's checks against a temp register, return the findings list."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "OPEN-LOOPS.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(register_text)
        orig = gc.REGISTER
        gc.REGISTER = p
        try:
            findings = []
            gc.check_register(findings)
            return findings
        finally:
            gc.REGISTER = orig


# ---------- THE control: clean means silent ----------

def test_clean_register_is_silent():
    txt = HEADER + (
        "| L-01 | **thing** | why | O | %s | OPEN | |\n"
        "| L-02 | **other** | why | C | %s | **CLOSED 2026-09-24** | proof on disk |\n"
    ) % (FUTURE, FUTURE)
    assert run_with(txt) == [], "a clean register must produce NO output"


def test_no_rows_is_silent():
    assert run_with(HEADER) == []


def test_missing_register_is_silent():
    orig = gc.REGISTER
    gc.REGISTER = os.path.join(tempfile.gettempdir(), "does-not-exist-open-loops.md")
    try:
        findings = []
        gc.check_register(findings)
        assert findings == []
    finally:
        gc.REGISTER = orig


# ---------- it must actually detect real gaps ----------

def test_expired_review_by_fires():
    txt = HEADER + "| L-07 | **stale** | why | B | %s | OPEN | |\n" % PAST
    out = run_with(txt)
    assert any("past review-by" in f for f in out), out
    assert any("L-07" in f for f in out), out


def test_closed_without_evidence_fires():
    txt = HEADER + "| L-11 | **done?** | why | C | %s | **CLOSED 2026-09-24** | |\n" % FUTURE
    out = run_with(txt)
    assert any("EMPTY evidence" in f for f in out), out


def test_open_with_no_date_fires():
    txt = HEADER + "| L-20 | **undated** | why | O | | OPEN | |\n"
    out = run_with(txt)
    assert any("no review-by" in f for f in out), out


def test_closed_with_evidence_does_NOT_fire():
    """Guard against over-firing: a properly closed row is not a gap."""
    txt = HEADER + "| L-03 | **done** | why | O | %s | **CLOSED 2026-09-24** | owner said C2 |\n" % FUTURE
    assert run_with(txt) == []


def test_expired_but_CLOSED_does_NOT_fire():
    """A closed loop past its review-by is not an open gap."""
    txt = HEADER + "| L-05 | **done** | why | O | %s | **CLOSED 2026-09-24** | evidence here |\n" % PAST
    assert run_with(txt) == []


# ---------- the no-downsides contract ----------

def test_never_exits_nonzero_even_on_garbage():
    for payload in [b"", b"not json", b'{"x":1}', b"\xff\xfe\x00"]:
        p = subprocess.run([sys.executable, HOOK], input=payload,
                           capture_output=True, timeout=20)
        assert p.returncode == 0, (payload, p.returncode, p.stderr[:200])


def test_output_is_valid_json_or_empty():
    txt = HEADER + "| L-07 | **stale** | why | B | %s | OPEN | |\n" % PAST
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "OPEN-LOOPS.md")
        open(p, "w", encoding="utf-8").write(txt)
        env = dict(os.environ)
        r = subprocess.run([sys.executable, "-c",
                            "import importlib.util,sys,json;"
                            "s=importlib.util.spec_from_file_location('gc', r'%s');"
                            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                            "m.REGISTER=r'%s';sys.exit(m.main())" % (HOOK, p)],
                           capture_output=True, text=True, timeout=20, env=env)
        assert r.returncode == 0
        if r.stdout.strip():
            d2 = json.loads(r.stdout)
            assert d2["hookSpecificOutput"]["hookEventName"] == "Stop"
            assert "additionalContext" in d2["hookSpecificOutput"]


def test_no_permissionDecision_key_it_must_never_block():
    """Exit 2 / deny is reserved for dangerous actions. A gap is not dangerous."""
    src = open(HOOK, encoding="utf-8").read()
    assert "permissionDecision" not in src, "gap-check must never emit a block decision"
    assert "sys.exit(2)" not in src and "return 2" not in src


def test_is_state_based_not_text_based():
    """The hook must not inspect the conversation.

    An earlier version of THIS test grepped the source for the word "TODO" and
    failed on the docstring that explains the false positive -- the same
    use-vs-mention defect it was written to guard against. Prose is not
    behaviour, so assert on STRUCTURE instead:

      1. stdin is read and DISCARDED (never parsed for content)
      2. no transcript/message field is ever accessed
      3. the only inputs are the register path and git
    """
    import ast
    src = open(HOOK, encoding="utf-8").read()
    tree = ast.parse(src)

    # 1. stdin must be read bare, never assigned and inspected
    reads = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "read"
             and isinstance(n.func.value, ast.Attribute) and n.func.value.attr == "stdin"]
    assert reads, "expected stdin to be drained"
    for r in reads:
        parent_assigns = [n for n in ast.walk(tree)
                          if isinstance(n, ast.Assign) and r in ast.walk(n)]
        assert not parent_assigns, "stdin content must be discarded, not captured"

    # 2. no conversation/transcript field access anywhere in the AST
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names |= {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for bad in ("transcript_path", "last_message", "assistant_message", "messages", "prompt"):
        assert bad not in names, "hook must not touch %s" % bad

    # 3. the only subprocess calls are git
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "run":
            first = n.args[0] if n.args else None
            if isinstance(first, ast.List) and first.elts:
                e0 = first.elts[0]
                if isinstance(e0, ast.Constant):
                    assert e0.value == "git", "unexpected subprocess: %r" % (e0.value,)


# ---------- regressions for the two live false positives ----------

def test_open_row_whose_prose_contains_the_word_closed():
    """L-10 is OPEN but its why-text says 'must be done with the session closed'.
    A substring scan across all cells misread it as silently closed."""
    txt = HEADER + (
        "| L-10 | **mcp collision** | Must be done with the session closed; "
        "editing .claude.json while Claude runs clobbers it | C | %s | OPEN | |\n"
    ) % FUTURE
    out = run_with(txt)
    assert not any("EMPTY evidence" in f for f in out), out


def test_table_without_a_review_by_column_is_not_nagged():
    """The academic-calendar table has Date/Owner/Status and NO Review-by or
    Evidence column. Demanding those of it is noise."""
    txt = ("| ID | Item | Date | Owner | Status |\n|---|---|---|---|---|\n"
           "| L-16 | **contact supervisors** | by Dec 2026 | O | OPEN |\n"
           "| L-18 | **confirm ECTS** | Oct 2026 | O | OPEN |\n")
    assert run_with(txt) == [], "a table with no review-by column must not be nagged"


def test_month_granularity_date_is_understood():
    """'by Dec 2026' is a real date. Treated as end-of-month so it does not
    expire early."""
    txt = ("| ID | Item | Review by | Owner | Status | Evidence |\n|---|---|---|---|---|---|\n"
           "| L-30 | **future** | by Dec 2099 | O | OPEN | |\n")
    assert run_with(txt) == []


def test_month_granularity_in_the_past_still_fires():
    txt = ("| ID | Item | Review by | Owner | Status | Evidence |\n|---|---|---|---|---|---|\n"
           "| L-31 | **stale** | Jan 2020 | O | OPEN | |\n")
    out = run_with(txt)
    assert any("past review-by" in f for f in out), out
