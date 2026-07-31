#!/usr/bin/env python3
"""The module docstring is a CONTRACT; pin it to measured behaviour.

Three adjudicated findings (D-a069 Swift, D-a041 Kotlin, D-a072 TypeScript) all
reported the same shape: "a rules file demands a check, per-edit-check does not
run it."  Re-measured at 27fb388, each rests on the same premise error --
``rules/<lang>/hooks.md`` opens with "Configure in ``~/.claude/settings.json``"
(``rules/typescript/hooks.md:13``, ``rules/kotlin/hooks.md:12``,
``rules/swift/hooks.md:12``), i.e. it is portable operator guidance, not a
specification binding this hook.

What DID survive re-measurement is narrower and is what this suite pins:

  1. The dispatch table documented three deliberate skips and said nothing
     about the catch-all at the end of ``_run_check``, so ``.kt``, ``.swift``,
     ``.dart`` and friends were silently indistinguishable from both a
     documented decision and a clean file.  (Measured: all return
     ``([], False)``.)
  2. The "Exit protocol" section advertised "exit 2 + decision:block JSON"
     (D-a078) for syntax errors.  Measured: stdout is EMPTY on that path and
     always has been -- the emit branch writes plain text to stderr because
     Claude Code ignores stdout at exit 2.  A contract that promises a payload
     the code never produces is how a reader concludes the AGENTS.md §6
     question is settled when it is not.

NOT asserted here: that exit 2 for a syntax error is right or wrong.  That
tension is real, is documented inline in ``check.py``, and is a policy call for
the contract owner -- five existing assertions in ``test_check.py`` enshrine the
current behaviour and one of them records the opposite choice as a past bug.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

CHECK_PY = Path(__file__).resolve().parent / "check.py"

# Extensions the hook reaches no checker for.  The first three are documented
# decisions; the rest were never considered and hit the same catch-all.
SILENT_EXTENSIONS = (".ts", ".tsx", ".rs", ".kt", ".kts", ".swift", ".dart", ".xyz")


def _load():
    spec = importlib.util.spec_from_file_location("per_edit_check_contract", CHECK_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("ext", SILENT_EXTENSIONS)
def test_unchecked_extensions_are_all_the_same_silent_result(ext: str):
    """The measured fact the docstring must not misrepresent."""
    assert _load()._run_check("probe" + ext) == ([], False)


def test_docstring_discloses_the_catch_all_skip():
    doc = _load().__doc__ or ""
    assert "catch-all" in doc, (
        "the Language dispatch table must say that every UNLISTED extension is "
        "silently skipped; without it .kt/.swift/.dart read as oversights or as "
        "passes rather than as out of scope"
    )


def test_docstring_does_not_promise_a_payload_the_code_never_emits():
    doc = _load().__doc__ or ""
    promise = "decision:block JSON"
    # The docstring may DESCRIBE the retracted claim, but must not still make it
    # as the live contract in the exit-protocol table.
    protocol = doc.split("Exit protocol", 1)[-1]
    offending = [
        line
        for line in protocol.splitlines()
        if promise in line and "never" not in line and "advertised" not in line
    ]
    assert not offending, (
        f"exit-protocol section still advertises {promise!r}: {offending}"
    )


def test_exit_two_path_really_emits_nothing_on_stdout(tmp_path: Path):
    """Both halves of the claim above, measured rather than asserted."""
    target = tmp_path / "bom.json"
    target.write_bytes(b"\xef\xbb\xbf{}\n")
    payload = json.dumps(
        {"tool_name": "Edit", "tool_input": {"file_path": str(target)}}
    )
    module = _load()
    saved = (sys.stdin, sys.stdout, sys.stderr)
    sys.stdin, sys.stdout, sys.stderr = (
        io.StringIO(payload),
        io.StringIO(),
        io.StringIO(),
    )
    try:
        code = module.main()
        out, err = sys.stdout.getvalue(), sys.stderr.getvalue()
    finally:
        sys.stdin, sys.stdout, sys.stderr = saved
    assert code == 2
    assert out == "", "stdout must stay clean at exit 2 (Claude Code ignores it)"
    assert "bom.json" in err
