"""IMP-0423 degradation-contract tests (stdlib only, no pytest)."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0]))

from degrade_loudly import DegradeLoudly, VERDICT_DEGRADED, VERDICT_SUCCESS

MOD = HERE.parents[0] / "degrade_loudly.py"
RESULTS = []


def test_mismatch_is_degraded_not_success():
    d = DegradeLoudly()
    out = d.dispatch(d.mismatch_request(Path("x")), d.openai_fixture())
    assert out.verdict == VERDICT_DEGRADED, out.verdict
    assert out.ordinary_looking_success is False
    assert out.mismatches, "mismatch list must be non-empty"


def test_matched_dispatch_is_success():
    d = DegradeLoudly()
    out = d.dispatch(d.matched_request(Path("x")), d.anthropic_fixture())
    assert out.verdict == VERDICT_SUCCESS, out.verdict


def test_partial_artifact_preserved_after_mismatch():
    d = DegradeLoudly()
    with tempfile.TemporaryDirectory() as td:
        partial = Path(td) / "partial.json"
        body = b'{"kind":"partial"}'
        d.seed_partial(partial, body)
        d.dispatch(d.mismatch_request(partial), d.openai_fixture())
        d.assert_partial_preserved(partial, body)


def test_discard_mutation_turns_preservation_test_red():
    src = MOD.read_text(encoding="utf-8")
    mutant = src.replace(
        "if not live_path.is_file():",
        "live_path.unlink(missing_ok=True)" + chr(10) + "        if False:",
        1,
    )
    assert mutant != src, "mutation anchor not found"
    with tempfile.TemporaryDirectory() as td:
        mdir = Path(td)
        (mdir / "degrade_loudly.py").write_text(mutant, encoding="utf-8")
        loader = (
            "import sys" + chr(10) +
            "sys.path.insert(0, r'%s')" % str(mdir).replace(chr(92), "/") + chr(10) +
            "from pathlib import Path" + chr(10) +
            "from degrade_loudly import DegradeLoudly" + chr(10) +
            "d = DegradeLoudly()" + chr(10) +
            "p = Path(sys.argv[1]); body = b'p'" + chr(10) +
            "d.seed_partial(p, body)" + chr(10) +
            "d.dispatch(d.mismatch_request(p), d.openai_fixture())" + chr(10) +
            "d.assert_partial_preserved(p, body)" + chr(10) +
            "print('MUTANT-KEPT')" + chr(10)
        )
        (mdir / "mut_check.py").write_text(loader, encoding="utf-8")
        partial = mdir / "partial.json"
        proc = subprocess.run(
            [sys.executable, "-B", str(mdir / "mut_check.py"), str(partial)],
            capture_output=True, text=True, timeout=60,
        )
        assert "MUTANT-KEPT" not in proc.stdout, "discard mutant escaped the contract"
        assert proc.returncode != 0, "discard mutation must turn preservation red"


def test_silent_substitution_is_refused():
    d = DegradeLoudly()
    out = d.dispatch_with_fallback(
        d.mismatch_request(Path("x")), d.openai_fixture(), d.anthropic_fixture()
    )
    assert out.verdict == VERDICT_DEGRADED, "fallback vendor must not mask the mismatch"
    assert out.substitution_refused is True
    assert out.ordinary_looking_success is False


def test_retry_cannot_promote_mismatch_to_success():
    d = DegradeLoudly()
    first = d.dispatch(d.mismatch_request(Path("x")), d.openai_fixture())
    again = d.retry_mismatch(first)
    assert again.verdict == VERDICT_DEGRADED
    assert again.retry_refused is True


def test_source_never_unlinks_partials():
    src = MOD.read_text(encoding="utf-8")
    for bad in ("unlink(", "rmdir(", "os.remove(", "shutil.rmtree"):
        assert bad not in src, "discard path present in source: " + bad


ALL = [
    test_mismatch_is_degraded_not_success,
    test_matched_dispatch_is_success,
    test_partial_artifact_preserved_after_mismatch,
    test_discard_mutation_turns_preservation_test_red,
    test_silent_substitution_is_refused,
    test_retry_cannot_promote_mismatch_to_success,
    test_source_never_unlinks_partials,
]

if __name__ == "__main__":
    for fn in ALL:
        try:
            fn()
            RESULTS.append("PASS " + fn.__name__)
        except Exception as exc:
            RESULTS.append("FAIL " + fn.__name__ + ": " + repr(exc))
    for line in RESULTS:
        print(line)
    npass = sum(1 for l in RESULTS if l.startswith("PASS"))
    if npass != len(ALL):
        print("FAILED:IMP-0423 tests %d/%d" % (npass, len(ALL)))
        raise SystemExit(1)
    print("SUCCESS:IMP-0423 tests %d/%d" % (len(ALL), len(ALL)))
