#!/usr/bin/env python3
r"""Both-states regression tests for wire-check's SUBPROCESS DECODE path.

MEASURED DEFECT (2026-08-12). `check.py` called

    subprocess.run(args, capture_output=True, text=True, timeout=...)

at BOTH subprocess sites (`_rg_lines` for ripgrep, `_git` for git) with `text=True`
and NO `encoding=`. `text=True` alone decodes the child's bytes with
`locale.getpreferredencoding(False)` -- cp1252 on this box -- under STRICT errors.

The failure is silent, and the silence is the whole problem:

    subprocess.run does NOT raise. The decode dies inside subprocess._readerthread,
    the threading excepthook prints a traceback nobody reads, communicate() returns
    "", and returncode stays 0.

So `_rg_lines` takes its `if r.returncode in (0, 1)` SUCCESS branch and returns [],
and `_git` returns "" instead of None. The documented os.walk fallback is NEVER
reached. Measured with an ASCII control proving the invocation itself is sound
(command-center/hook-audit/B0-DECODE-PROBE.json):

    trigger file, shipped text=True : rc=0, stdout_len=0     <- silently emptied
    trigger file, encoding="utf-8"  : rc=0, stdout_len=84
    ascii control, either shape     : 88 bytes both ways

CONSEQUENCE, both directions:
  * `_rg_lines` emptied  -> zero references -> wire-check's DEAD-CODE trigger fires on
    a symbol that is very much alive. Because the odds of a non-cp1252 byte rise with
    output size, the hook is INVERTED: most wrong about the most-referenced symbols.
  * `_git` emptied -> `_added_block` returns "" -> the file is never analysed, so a
    genuinely dead symbol is MISSED. Note `_git` here carries `git diff` output, i.e.
    arbitrary FILE CONTENT, so for wire-check it is not the low-risk "git is ASCII"
    case it looks like from the call site.

TRIGGER CHOICE -- why this test is not Windows-only. A lone 0x81 byte is BOTH an
invalid UTF-8 sequence (a continuation byte with no lead) AND undefined in cp1252, so
strict decode raises under either locale; and ripgrep passes it through RAW rather than
substituting U+FFFD (measured, B0 q1: contains_raw_0x81=true, contains_fffd=false).
The cp1252-specific case (valid UTF-8 whose bytes are undefined in cp1252) is kept as a
second, ecological case and SKIPS loudly off cp1252 -- and the runner FAILS CLOSED if
the universal cases did not execute, so an all-skipped run can never read as a pass.

RED-FIRST: run against the unfixed check.py, every FIRE case below returns the wrong
answer. Proven before the fix landed; see docs/hook-audit/HOOK-AUDIT.md.

Run:  python test_wire_check_decode.py
"""

from __future__ import annotations

import importlib.util
import json
import locale
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

_CHECK = Path(__file__).resolve().parent / "check.py"
_spec = importlib.util.spec_from_file_location("wire_check_decode_under_test", _CHECK)
check = importlib.util.module_from_spec(_spec)
sys.modules["wire_check_decode_under_test"] = check
_spec.loader.exec_module(check)

# Lone 0x81: invalid UTF-8 AND undefined in cp1252 -> strict decode raises everywhere.
UNIVERSAL_BAD = b"\x81"
# Cyrillic 'e' U+044D = D1 8D. Valid UTF-8; 0x8D is undefined in cp1252.
CP1252_ONLY_BAD = "э"

_UTF8_ALIASES = {"utf-8", "utf8", "utf_8", "cp65001"}


def _preferred_is_utf8() -> bool:
    return locale.getpreferredencoding(False).lower().replace("-", "-") in _UTF8_ALIASES


def _tmpdir(tag: str) -> Path:
    p = Path(tempfile.gettempdir()) / f"wcd-{tag}-{uuid.uuid4().hex[:8]}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _git(cwd: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def _new_repo(tag: str) -> Path:
    repo = _tmpdir(tag)
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("# baseline\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")
    return repo


def _run_hook(cwd: Path) -> str:
    """Fire check.py as a real Stop hook and return its stdout."""
    payload = json.dumps(
        {
            "session_id": "wcd-" + uuid.uuid4().hex[:8],
            "cwd": str(cwd),
            "stop_hook_active": False,
        }
    )
    env = dict(os.environ)
    env.pop("WIRE_CHECK", None)
    env.pop("WIRE_CHECK_NO_SKIP", None)
    p = subprocess.run(
        [sys.executable, str(_CHECK)],
        input=payload.encode("utf-8"),
        capture_output=True,
        timeout=180,
        env=env,
        cwd=str(cwd),
    )
    return p.stdout.decode("utf-8", "replace")


# ---------------------------------------------------------------------------------
# unit level: _rg_lines must survive undecodable child output
# ---------------------------------------------------------------------------------
def case_rg_universal() -> list[tuple[str, bool, bool]]:
    d = _tmpdir("rg-uni")
    (d / "hit.py").write_bytes(b"sym_universal_zz = 1  # " + UNIVERSAL_BAD + b" tail\n")
    got = check._rg_lines(str(d), "sym_universal_zz")

    ctl = _tmpdir("rg-ctl")
    (ctl / "hit.py").write_bytes(b"sym_universal_zz = 1  # ascii tail\n")
    ctl_got = check._rg_lines(str(ctl), "sym_universal_zz")

    absent = check._rg_lines(str(ctl), "sym_that_is_nowhere_qq")
    out = [
        (
            "[universal] _rg_lines finds the symbol despite a raw 0x81 byte",
            bool(got),
            True,
        ),
        (
            "[control] ASCII-only sibling is found (invocation is sound)",
            bool(ctl_got),
            True,
        ),
        (
            "[control] an absent symbol is still NOT found (detector not blind-true)",
            bool(absent),
            False,
        ),
    ]
    shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(ctl, ignore_errors=True)
    return out


def case_rg_cp1252() -> tuple[list[tuple[str, bool, bool]], int]:
    """Ecological cp1252 case. SKIPS LOUDLY when the ambient encoding is already UTF-8."""
    if _preferred_is_utf8():
        print(
            f"  SKIP [cp1252] preferred encoding is "
            f"{locale.getpreferredencoding(False)!r}; the valid-UTF-8-undefined-in-cp1252 "
            f"trigger cannot fire here. The universal 0x81 cases above still ran."
        )
        return [], 1
    d = _tmpdir("rg-1252")
    (d / "hit.py").write_text(
        f"sym_cp1252_zz = 1  # {CP1252_ONLY_BAD} tail\n", encoding="utf-8"
    )
    got = check._rg_lines(str(d), "sym_cp1252_zz")
    shutil.rmtree(d, ignore_errors=True)
    return (
        [
            (
                "[cp1252] _rg_lines finds the symbol despite a cp1252-undefined byte",
                bool(got),
                True,
            )
        ],
        0,
    )


# ---------------------------------------------------------------------------------
# hook level: the emitted FALSE POSITIVE and the silent MISS
# ---------------------------------------------------------------------------------
def case_false_positive_suppressed() -> list[tuple[str, bool, bool]]:
    """A referenced symbol must NOT be reported dead just because a hit line has a bad byte."""
    repo = _new_repo("fp")
    (repo / "caller.py").write_bytes(
        b"from mod import widget_alpha\nwidget_alpha()  # " + UNIVERSAL_BAD + b" note\n"
    )
    _git(repo, "add", "caller.py")
    _git(repo, "commit", "-q", "-m", "caller exists before the session")
    # session-added definition of a symbol the (already committed) caller USES
    (repo / "mod.py").write_text(
        "def widget_alpha():\n    return 1\n", encoding="utf-8"
    )
    out = _run_hook(repo)
    shutil.rmtree(repo, ignore_errors=True)
    return [
        (
            "[hook FP] a symbol whose only caller carries a bad byte is NOT called dead",
            "widget_alpha" in out,
            False,
        )
    ]


def case_true_positive_kept() -> list[tuple[str, bool, bool]]:
    """Paired FIRE side: the guard is not disarmed -- a genuinely dead symbol still fires."""
    repo = _new_repo("tp")
    (repo / "mod.py").write_text(
        "def widget_beta_unused():\n    return 1\n", encoding="utf-8"
    )
    out = _run_hook(repo)
    shutil.rmtree(repo, ignore_errors=True)
    return [
        (
            "[hook TP] a genuinely unreferenced session-added symbol still fires",
            "widget_beta_unused" in out,
            True,
        )
    ]


def case_git_diff_not_emptied() -> list[tuple[str, bool, bool]]:
    """_git carries `git diff` output = file content. A bad byte must not blank the analysis."""
    repo = _new_repo("gitdiff")
    tracked = repo / "mod.py"
    tracked.write_text("# baseline module\n", encoding="utf-8")
    _git(repo, "add", "mod.py")
    _git(repo, "commit", "-q", "-m", "add mod")
    # MODIFY the tracked file: a dead symbol plus a line git will still call text.
    tracked.write_bytes(
        b"# baseline module\n"
        b"# note " + UNIVERSAL_BAD + b"\n"
        b"def widget_gamma_unused():\n    return 1\n"
    )
    out = _run_hook(repo)
    shutil.rmtree(repo, ignore_errors=True)
    return [
        (
            "[hook MISS] a dead symbol is still found when the DIFF holds a bad byte",
            "widget_gamma_unused" in out,
            True,
        )
    ]


def main() -> int:
    cases: list[tuple[str, bool, bool]] = []
    universal_ran = 0

    for fn in (
        case_rg_universal,
        case_false_positive_suppressed,
        case_true_positive_kept,
        case_git_diff_not_emptied,
    ):
        rows = fn()
        universal_ran += len(rows)
        cases.extend(rows)

    cp_rows, skipped = case_rg_cp1252()
    cases.extend(cp_rows)

    ok = True
    for name, got, want in cases:
        if got != want:
            ok = False
        print(f"  {'OK ' if got == want else 'XX '} {name}: got={got} want={want}")

    # FAIL CLOSED: an all-skipped run must never read as a pass.
    if universal_ran == 0:
        print("FAILED:wire-check-decode no universal case executed (all skipped)")
        return 1

    fires = sum(1 for _, _, w in cases if w)
    print(
        f"\nRESULT: {'ALL PASS' if ok else 'FAILURES PRESENT'}  "
        f"({len(cases)} cases: {fires} must hold, {len(cases) - fires} must stay empty, "
        f"{skipped} skipped, {universal_ran} locale-independent)"
    )
    print("SUCCESS:wire-check-decode" if ok else "FAILED:wire-check-decode")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
