#!/usr/bin/env python3
r"""Both-states tests for wire-check's two FALSE-POSITIVE NOISE sources (R5).

A hook that fires on the reader's own scratch tooling trains the reader to ignore it,
which costs more than the finding is worth. Two mechanisms were MEASURED firing against
this repo (command-center/hook-audit/GROUNDING.md §4), independent of the cp1252 decode
defect covered by test_wire_check_decode.py:

  N1  A pathlib literal is reported as an unlinked ROUTE. `_ROUTE` carries a
      `\bpath\s*\(` alternative for Django's `path("articles/<int:year>/")`, and the
      whole pattern is re.IGNORECASE -- so it also matches pathlib's `Path(`. Emitted
      verbatim: `route 'C:/Users/Prekzursil/.claude/hooks' is linked/navigated 0x`
      from a line of the shape `LIVE = Path("C:/Users/Prekzursil/.claude/hooks")`.
      `_ROUTE_PATHLIKE = re.compile(r"/|^\*$")` then waves it through because it does
      contain a slash.

  N2  It fires on UNTRACKED SCRATCH. Every symbol flagged in the observed emission came
      from `_h1_inventory.py`, `_h2_unwired.py`, `_s2_render_probe.py` -- audit probes,
      one of them belonging to a different lane, flagged minutes after being written.

FIX SHAPE, and why each is narrow rather than a blanket suppression:
  N1  make the Django alternative case-SENSITIVE via `(?-i:path)` so `Path(` stops
      matching while `path(` still does, AND reject drive-absolute / UNC / URL-scheme
      literals in `_ROUTE_PATHLIKE` as defence in depth for the other route-shaped
      alternatives (`.use("C:/x")`).
  N2  skip a changed file only when it is BOTH untracked AND named `_*` -- the
      private-by-convention prefix this module already honours for SYMBOLS
      (`_extract` drops names starting with `_`), now extended to files. A TRACKED
      `_build_thing.py` is a deliberate deliverable and is still analysed. Plus the
      scratch path segments `per-edit-check` already self-scopes on.
      `WIRE_CHECK_NO_SKIP=1` disables the skip so the suppression is auditable and
      never silently hides a real finding from someone looking for it.

EVERY suppression case below is paired with a FIRE case, so a "fix" that merely stops
the hook finding things fails this file.

RED-FIRST: run against the unfixed check.py and the N1 cases plus every scratch-skip
case return the wrong answer.

Run:  python test_wire_check_noise.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

_CHECK = Path(__file__).resolve().parent / "check.py"
_spec = importlib.util.spec_from_file_location("wire_check_noise_under_test", _CHECK)
check = importlib.util.module_from_spec(_spec)
sys.modules["wire_check_noise_under_test"] = check
_spec.loader.exec_module(check)

DEAD = "def orphan_widget_zz():\n    return 1\n"


# --- N1: pathlib literals are not routes; real dialects survive -------------------
NOT_ROUTES = [
    (
        "pathlib drive-absolute (the emitted FP)",
        'LIVE = Path("C:/Users/Prekzursil/.claude/hooks")',
        "C:/Users/Prekzursil/.claude/hooks",
    ),
    (
        "pathlib forward-slash relative",
        'p = Path("command-center/hook-audit")',
        "command-center/hook-audit",
    ),
    (
        "pathlib lowercase drive",
        'p = Path("d:/knowledge/corpus")',
        "d:/knowledge/corpus",
    ),
    ("UNC share literal", 'p = Path("//server/share/thing")', "//server/share/thing"),
    ("http url in .use", 'app.use("https://example.com/cb")', "https://example.com/cb"),
]

STILL_ROUTES = [
    (
        "django path lowercase",
        "path('articles/<int:year>/', views.year_archive)",
        "articles/<int:year>/",
    ),
    ("django path with slash prefix", 'path("/admin/panel", v)', "/admin/panel"),
    ("express get", "router.get('/checkout_xyz', h)", "/checkout_xyz"),
    ("flask decorator", '@app.route("/admin/users")', "/admin/users"),
    ("react router", '<Route path="/settings" element={<S/>} />', "/settings"),
    ("fastapi templated", '@router.route("/items/{item_id}")', "/items/{item_id}"),
]


# --- N2: scratch skip, end to end -------------------------------------------------
def _git(cwd: Path, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def _new_repo(tag: str) -> Path:
    repo = Path(tempfile.gettempdir()) / f"wcn-{tag}-{uuid.uuid4().hex[:8]}"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("# baseline\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")
    return repo


def _fire(repo: Path, env_extra: dict | None = None) -> str:
    payload = json.dumps(
        {
            "session_id": "wcn-" + uuid.uuid4().hex[:8],
            "cwd": str(repo),
            "stop_hook_active": False,
        }
    )
    env = dict(os.environ)
    env.pop("WIRE_CHECK", None)
    env.pop("WIRE_CHECK_NO_SKIP", None)
    if env_extra:
        env.update(env_extra)
    p = subprocess.run(
        [sys.executable, str(_CHECK)],
        input=payload.encode("utf-8"),
        capture_output=True,
        timeout=300,
        env=env,
        cwd=str(repo),
    )
    return p.stdout.decode("utf-8", "replace")


def scratch_cases() -> list[tuple[str, bool, bool]]:
    out: list[tuple[str, bool, bool]] = []

    # (1) untracked _probe file -> SILENT
    r = _new_repo("untracked-us")
    (r / "_probe_zz.py").write_text(DEAD, encoding="utf-8")
    out.append(
        (
            "untracked `_probe_zz.py` is NOT flagged",
            "orphan_widget_zz" in _fire(r),
            False,
        )
    )
    shutil.rmtree(r, ignore_errors=True)

    # (2) PAIRED FIRE: untracked ordinary name -> FIRES (guard not disarmed)
    r = _new_repo("untracked-plain")
    (r / "feature.py").write_text(DEAD, encoding="utf-8")
    out.append(
        ("untracked `feature.py` STILL fires", "orphan_widget_zz" in _fire(r), True)
    )
    shutil.rmtree(r, ignore_errors=True)

    # (3) PAIRED FIRE: TRACKED underscore file is a deliverable -> FIRES
    r = _new_repo("tracked-us")
    f = r / "_build_thing.py"
    f.write_text("# baseline\n", encoding="utf-8")
    _git(r, "add", "_build_thing.py")
    _git(r, "commit", "-q", "-m", "add tracked underscore module")
    f.write_text("# baseline\n" + DEAD, encoding="utf-8")
    out.append(
        ("TRACKED `_build_thing.py` STILL fires", "orphan_widget_zz" in _fire(r), True)
    )
    shutil.rmtree(r, ignore_errors=True)

    # (4) scratch path segment -> SILENT.
    #     The file must be TRACKED-and-modified, not untracked-in-a-new-directory:
    #     `git status --porcelain` COLLAPSES a wholly-untracked directory to `?? scratchpad/`,
    #     which has no source extension and is dropped by _changed_files. An untracked
    #     variant of this case therefore passes on the UNFIXED code too -- it is a control
    #     that cannot distinguish the two hypotheses, and the first version of this file
    #     shipped exactly that. Case (6) pins the collapsing behaviour separately.
    r = _new_repo("scratchpad")
    d = r / "scratchpad"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "thing.py"
    f.write_text("# baseline\n", encoding="utf-8")
    _git(r, "add", "scratchpad/thing.py")
    _git(r, "commit", "-q", "-m", "track the scratchpad file")
    f.write_text("# baseline\n" + DEAD, encoding="utf-8")
    out.append(
        (
            "TRACKED file under `scratchpad/` is NOT flagged",
            "orphan_widget_zz" in _fire(r),
            False,
        )
    )
    # ...and the SAME repo fires once the skip is disabled, proving case (4) measures
    # the skip and not the directory-collapsing artefact.
    out.append(
        (
            "...and WIRE_CHECK_NO_SKIP=1 makes that scratchpad file fire",
            "orphan_widget_zz" in _fire(r, {"WIRE_CHECK_NO_SKIP": "1"}),
            True,
        )
    )
    shutil.rmtree(r, ignore_errors=True)

    # (5) the suppression is AUDITABLE: WIRE_CHECK_NO_SKIP=1 restores the finding
    r = _new_repo("noskip")
    (r / "_probe_zz.py").write_text(DEAD, encoding="utf-8")
    out.append(
        (
            "WIRE_CHECK_NO_SKIP=1 makes the skipped `_probe_zz.py` fire again",
            "orphan_widget_zz" in _fire(r, {"WIRE_CHECK_NO_SKIP": "1"}),
            True,
        )
    )
    shutil.rmtree(r, ignore_errors=True)

    # (6) pin the untracked-directory collapsing so nobody re-derives it as a fix
    r = _new_repo("collapsed")
    d = r / "brandnew"
    d.mkdir(parents=True, exist_ok=True)
    (d / "thing.py").write_text(DEAD, encoding="utf-8")
    status = _git(r, "status", "--porcelain").stdout
    out.append(
        (
            "`git status --porcelain` collapses a new untracked dir to `?? brandnew/`",
            "brandnew/thing.py" in status,
            False,
        )
    )
    out.append(
        (
            "...so a file in a brand-new untracked dir is unreachable even with NO_SKIP",
            "orphan_widget_zz" in _fire(r, {"WIRE_CHECK_NO_SKIP": "1"}),
            False,
        )
    )
    shutil.rmtree(r, ignore_errors=True)
    return out


def deadline_cases() -> list[tuple[str, bool, bool]]:
    """The deadline must truncate AND disclose, and must not truncate when generous.

    Deterministic: `_ref_count` is stubbed to a fixed sleep, so the number of symbols
    resolved before the deadline is arithmetic rather than a race with real ripgrep.
    """
    out: list[tuple[str, bool, bool]] = []
    r = _new_repo("deadline")
    # THREE files, not two: the deadline is tested at the TOP of each loop iteration, so
    # with only two files the scan finishes before any check can fire and `truncated`
    # stays False even though the wall clock is past the deadline. That is arithmetic,
    # not a bug -- but the first version of this case got it wrong and read as a defect.
    (r / "a.py").write_text("def dead_one_zz():\n    return 1\n", encoding="utf-8")
    (r / "b.py").write_text("def dead_two_zz():\n    return 1\n", encoding="utf-8")
    (r / "c.py").write_text("def dead_three_zz():\n    return 1\n", encoding="utf-8")

    orig_ref, orig_dl = check._ref_count, check._deadline_s
    try:
        check._ref_count = lambda cwd, name: (time.sleep(0.3), 0)[1]

        check._deadline_s = lambda: 0.5  # 0.3 s/symbol -> expires entering the 3rd file
        tight = check.analyze(str(r))
        out.append(
            (
                "tight deadline sets LAST_RUN['truncated']",
                bool(check.LAST_RUN["truncated"]),
                True,
            )
        )
        out.append(
            ("tight deadline still returns what it did resolve", len(tight) >= 1, True)
        )
        out.append(("tight deadline did NOT resolve all three", len(tight) < 3, True))

        check._deadline_s = lambda: float("inf")  # generous
        wide = check.analyze(str(r))
        out.append(
            (
                "generous deadline does NOT report truncation",
                bool(check.LAST_RUN["truncated"]),
                False,
            )
        )
        out.append(
            ("generous deadline finds ALL THREE dead symbols", len(wide) >= 3, True)
        )

        # A zero that arrives AFTER the deadline is a truncation, not a measurement, and
        # must never be emitted -- otherwise the deadline manufactures the very
        # "referenced 0x" false positive the encoding fix removed.
        check._deadline_s = lambda: 0.4
        check._ref_count = lambda cwd, name: (time.sleep(0.6), 0)[1]
        starved = check.analyze(str(r))
        out.append(
            ("a post-deadline zero is NOT emitted as a finding", bool(starved), False)
        )
        out.append(
            (
                "...and that run is reported as truncated",
                bool(check.LAST_RUN["truncated"]),
                True,
            )
        )
    finally:
        check._ref_count, check._deadline_s = orig_ref, orig_dl
        shutil.rmtree(r, ignore_errors=True)

    # The module-level hard deadline must actually be CONSULTED by _rg_lines. It was
    # declared and never assigned in the first version of this change, so the guard was
    # inert while every other case still passed -- both states are checked here.
    probe = Path(tempfile.gettempdir()) / f"wcn-hd-{uuid.uuid4().hex[:8]}"
    probe.mkdir(parents=True, exist_ok=True)
    (probe / "f.py").write_text("sym_hardline_zz = 1\n", encoding="utf-8")
    prev_hd = check._HARD_DEADLINE
    try:
        check._HARD_DEADLINE = None
        out.append(
            (
                "_rg_lines finds the symbol with no hard deadline",
                bool(check._rg_lines(str(probe), "sym_hardline_zz")),
                True,
            )
        )
        check._HARD_DEADLINE = time.monotonic() - 1.0  # already expired
        out.append(
            (
                "_rg_lines refuses to start once the hard deadline passed",
                bool(check._rg_lines(str(probe), "sym_hardline_zz")),
                False,
            )
        )
    finally:
        check._HARD_DEADLINE = prev_hd
        shutil.rmtree(probe, ignore_errors=True)

    # env parsing, both directions
    for val, want_inf in (("0", True), ("off", True), ("", False), ("7.5", False)):
        prev = os.environ.get("WIRE_CHECK_DEADLINE_S")
        if val:
            os.environ["WIRE_CHECK_DEADLINE_S"] = val
        else:
            os.environ.pop("WIRE_CHECK_DEADLINE_S", None)
        got_inf = check._deadline_s() == float("inf")
        if prev is None:
            os.environ.pop("WIRE_CHECK_DEADLINE_S", None)
        else:
            os.environ["WIRE_CHECK_DEADLINE_S"] = prev
        out.append((f"WIRE_CHECK_DEADLINE_S={val!r} -> unbounded", got_inf, want_inf))
    return out


def main() -> int:
    cases: list[tuple[str, bool, bool]] = []

    for label, snippet, lit in NOT_ROUTES:
        _s, routes = check._extract(snippet)
        cases.append((f"NOT a route: {label} -> {lit!r}", lit in routes, False))
    for label, snippet, lit in STILL_ROUTES:
        _s, routes = check._extract(snippet)
        cases.append((f"route kept: {label} -> {lit!r}", lit in routes, True))

    cases.extend(scratch_cases())
    cases.extend(deadline_cases())

    ok = True
    for name, got, want in cases:
        if got != want:
            ok = False
        print(f"  {'OK ' if got == want else 'XX '} {name}: got={got} want={want}")

    fires = sum(1 for _, _, w in cases if w)
    if fires == 0:
        print("FAILED:wire-check-noise no FIRE case present -- suppression-only suite")
        return 1
    print(
        f"\nRESULT: {'ALL PASS' if ok else 'FAILURES PRESENT'}  "
        f"({len(cases)} cases: {fires} must hold, {len(cases) - fires} must stay empty)"
    )
    print("SUCCESS:wire-check-noise" if ok else "FAILED:wire-check-noise")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
