#!/usr/bin/env python3
r"""wire-check/check.py — Stop / SubagentStop hook. Reachability (anti-slop) gate.

Over the SESSION GIT DIFF (uncommitted changes vs HEAD + untracked source files), it
builds a lightweight static reference graph with ripgrep and flags:

  (A) DEAD / NOT-YET-WIRED CODE: a symbol the agent ADDED this session — an exported
      function/class, a route, or a UI handler (handleX / onX) — that is referenced
      0 times anywhere else in the repo (the "dead button / built-but-not-wired" smell).

  (B) DUPLICATE-VERSION: a session-added FILE or SYMBOL named *_v2 / *_new / *_copy /
      *_2 / *V2 whose base (v1) has NO file and NO live reference — the coupons_v2-with-
      no-coupons archetype (a fork that shadow-builds instead of replacing v1).

It injects a non-accusatory "WIRING CHECK: ... referenced 0x — dead code or not-yet-
wired?" so the agent reconciles it. It NEVER blocks (a maybe-dead symbol is not a
dangerous op; many are public API) — inject-only, exit 0.

THE GAP IT FILLS (NON-DUPLICATIVE vs B1):
  * orphan-commit catches an untracked imported FILE after `git commit` (file-level,
    commit-triggered). wire-check catches orphan CODE (symbol/route/handler-level) over
    the working-tree diff, no commit required — it extends orphan-commit from files to
    symbols, exactly as the AGENTIC-PERFECTION-PLAN T1.3 specifies.
  * dark-surface needs a STUB MARKER + a completion claim. wire-check flags fully-
    implemented, marker-free, claim-free code that simply nothing calls.

LIMITATION (honest): the diff is working-tree-vs-HEAD, so work already COMMITTED earlier
this session is not re-analyzed (Stop usually fires before the commit). Set
WIRE_CHECK_BASE=<git-ref> to diff against a recorded session-start ref instead.

FAIL-OPEN (try/except -> exit 0). Anti-loop via stop_hook_active. Needs git + (ripgrep
or a stdlib fallback). Opt-out: WIRE_CHECK=off in env, or hooks/wire-check/.disabled.

settings.json (Stop, no matcher — also valid under SubagentStop):
  {"type":"command",
   "command":"python C:/Users/Prekzursil/.claude/hooks/wire-check/check.py",
   "timeout":25,"statusMessage":"Wire-check reachability (dead-code / _v2 gate)"}
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
MAX_SYMBOLS = 40
MAX_FINDINGS = 6

# Wall-clock deadline, in seconds, for analyze(). The manifest gives this check a 25 s
# per-check budget inside a 35 s whole-event budget, and dispatch.py DROPS a timed-out
# check's output entirely (`_receipt(..., "timeout"); continue`) -- so exceeding the
# budget does not degrade the hook, it SILENCES it. MEASURED on this repo: 40 symbol
# lookups x 1,687 ms mean = 67 s of ripgrep alone (86% of an 79 s run;
# command-center/hook-audit/B4-PROFILE.json). A deadline converts that silent kill into
# bounded, self-disclosing partial output. Tunable/disableable for one-off deep runs.
DEADLINE_S = 20.0
# Populated by analyze() so main() can disclose truncation instead of pretending the
# scan was exhaustive. A partial scan reported as complete is the "green but proves
# nothing" failure this hook exists to catch.
LAST_RUN: dict[str, object] = {
    "truncated": False,
    "checked": 0,
    "deadline_s": DEADLINE_S,
}
# Monotonic timestamp past which no further scanning work may START, set by analyze().
# Checking the deadline only at loop tops is NOT sufficient: one in-flight lookup can
# overrun it badly, because a ripgrep call that exceeds its own `timeout=8` raises
# TimeoutExpired, gets swallowed, and then falls through to the os.walk fallback -- so
# the "8 second" call becomes 8 s of ripgrep PLUS a full Python tree walk. That is the
# measured 12,256 ms worst-case single lookup in B4-PROFILE.json, and it is why the
# first version of this deadline still let a run reach 106% of budget. _rg_lines()
# consults this so both the child timeout and the fallback are bounded.
_HARD_DEADLINE: float | None = None


def _deadline_s() -> float:
    raw = os.environ.get("WIRE_CHECK_DEADLINE_S", "").strip()
    if not raw:
        return DEADLINE_S
    if raw.lower() in ("0", "off", "none"):
        return float("inf")
    try:
        v = float(raw)
        return v if v > 0 else float("inf")
    except ValueError:
        return DEADLINE_S


# Throwaway scratch trees: probe scripts and one-off tooling, not deliverables. Mirrors
# the segments per-edit-check/check.py already self-scopes on.
_SCRATCH_SEG = ("/scratchpad/", "/temp/claude/", "/.write-probe")
SRC_EXT = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".kt",
    ".swift",
    ".scala",
    ".php",
)
TEST_HINT = re.compile(
    r"(^|[/\\])(test_|tests?[/\\]|.*\.test\.|.*\.spec\.|conftest)", re.IGNORECASE
)

# Top-level definitions (line-anchored over the added-line block).
_DEF_TOPLEVEL = re.compile(
    r"^(?:export\s+(?:default\s+)?)?(?:async\s+)?"
    r"(?:def|class|function|func|interface|type|enum|struct|trait)\s+([A-Za-z_]\w{2,})",
    re.MULTILINE,
)
_DEF_EXPORT_CONST = re.compile(
    r"^\s*export\s+(?:const|let)\s+([A-Za-z_]\w{2,})\s*[=:]", re.MULTILINE
)
# UI handlers by naming convention (may be indented inside a component).
_HANDLER = re.compile(
    r"\b(?:const|let|var|function)\s+(handle[A-Z]\w+|on[A-Z]\w{2,})\b"
)
# Route path literals. SPLIT into a case-insensitive half (HTTP verbs and decorators,
# which real dialects write lowercase but which have historically been matched loosely)
# and a CASE-SENSITIVE half. The split exists because `re.IGNORECASE` over the whole
# pattern made the Django `path(` alternative also match pathlib's `Path(`, so
# `LIVE = Path("C:/Users/Prekzursil/.claude/hooks")` was emitted verbatim as
# `route 'C:/Users/Prekzursil/.claude/hooks' is linked/navigated 0x`. Django's `path(`
# and React Router's `<Route path=` are both case-EXACT in every real codebase, so
# matching them case-sensitively costs no dialect and kills the false positive at its
# root. (Two compiled patterns rather than an inline `(?-i:...)` group so the module
# still imports on Python < 3.11.) Regression: test_wire_check_noise.py.
_ROUTE = re.compile(
    r"(?:\.(?:get|post|put|delete|patch|use|route|all)\s*\(|@(?:app|router|bp)\.route\s*\()"
    r"\s*['\"]([^'\"]{1,80})['\"]",
    re.IGNORECASE,
)
_ROUTE_CS = re.compile(
    r"(?:\bpath\s*\(|<Route\b[^>]*\bpath=)\s*['\"]([^'\"]{1,80})['\"]"
)
# A route literal is a PATH: it contains a separator (or is the `*` catch-all). The `.get(`
# alternative above was written for `router.get("/users")` but matches EVERY Python
# `dict.get("key")`. Measured 2026-07-24 against tools/monitorcore/monitorcore/health_source.py:
# `band=str(obj.get("band", "unknown"))` at :141, `driver=str(obj.get("driver", ""))` at :142 and
# `t.get('name')` at :127 were reported as routes "linked/navigated 0x" while being ordinary dict
# lookups of dataclass field names that the module constructs and reads. (The dataclass field
# DECLARATIONS at :60-61 match `_ROUTE` zero times -- they were never the trigger.) Requiring a
# separator keeps every real dialect: Express `/users/:id`, Flask/FastAPI `@app.route("/x")`,
# Django `path("articles/<int:year>/")`, React `<Route path="/home">`.
_ROUTE_PATHLIKE = re.compile(r"/|^\*$")
# ...but a slash is ALSO in every filesystem path and URL. Defence in depth for the
# route-shaped alternatives that survive the case split above (e.g. `.use("C:/x")`):
# reject a drive-absolute Windows path, a UNC/`//` share, and any scheme-qualified URL.
# No real route literal starts with any of these. Regression: test_wire_check_noise.py.
_NOT_ROUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|//|\\\\|[A-Za-z][A-Za-z0-9+.\-]*://)")
# Version-suffix detector (requires a separator or Vn — avoids base64/sha256).
_VERSUF = re.compile(
    r"^(?P<base>.+?)(?:[._-](?:v\d+|new|copy|old|final|backup|orig|\d+)|V\d+)$",
    re.IGNORECASE,
)


def _git(cwd: str, *args, timeout=10):
    try:
        r = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            # `text=True` ALONE decodes with locale.getpreferredencoding(False) --
            # cp1252 here -- under STRICT errors, and the decode dies inside
            # subprocess._readerthread: run() does NOT raise, communicate() returns
            # "", returncode stays 0. This function would then return "" (falsy, but
            # not None), _added_block would see an empty diff, and the file would be
            # silently skipped -- a MISSED finding, not a loud failure. `git diff`
            # output here is arbitrary FILE CONTENT, so this is not the low-risk
            # "git speaks ASCII" case it looks like. Regression:
            # test_wire_check_decode.py::case_git_diff_not_emptied.
        )
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _time_left() -> float:
    """Seconds until the analyze() deadline; +inf when unset/unbounded."""
    if _HARD_DEADLINE is None:
        return float("inf")
    return _HARD_DEADLINE - time.monotonic()


def _rg_lines(cwd: str, pattern: str, fixed=False, timeout=8) -> list[str]:
    left = _time_left()
    if left <= 0:
        return []  # out of budget: do not start another full-tree walk
    if left < timeout:
        timeout = max(0.5, left)
    try:
        args = ["rg", "-w", "-n", "--no-heading", "-S"]
        if fixed:
            args = ["rg", "-F", "-n", "--no-heading"]
        args += ["-g", "!.git", pattern, cwd]
        # encoding= is LOAD-BEARING, and errors="replace" with it. `text=True` alone
        # decodes ripgrep's bytes with locale.getpreferredencoding(False) (cp1252 on
        # Windows) under strict errors. ripgrep passes invalid bytes through RAW
        # (measured: it does NOT substitute U+FFFD), so one byte outside the ANSI
        # codepage kills the decode inside subprocess._readerthread -- run() does NOT
        # raise, communicate() returns "", returncode stays 0, and the SUCCESS branch
        # below therefore returns []. Zero references is this hook's DEAD-CODE trigger,
        # and because the odds of such a byte rise with output size the failure is
        # INVERTED: most wrong about the most-referenced symbols. The os.walk fallback
        # is never reached, so nothing recovers it.
        # Regression: test_wire_check_decode.py.
        r = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if r.returncode in (0, 1):
            return [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    except Exception:
        pass
    # stdlib fallback (bounded) — reached when ripgrep is unavailable OR when it blew
    # its timeout, so it is NOT a rare path. Skip it entirely when the budget is spent:
    # a Python tree walk after an already-timed-out ripgrep is how one lookup reached
    # 12.3 s. NOTE an empty return here UNDER-reports references, i.e. it points straight
    # at a false "referenced 0x" — the exact defect class this file exists to fix. That
    # is why every zero is routed through _measured() below and never reported directly.
    if _time_left() <= 0:
        return []
    out: list[str] = []
    rx = re.compile(
        (re.escape(pattern) if fixed else r"\b" + re.escape(pattern) + r"\b")
    )
    try:
        for dp, dns, fns in os.walk(cwd):
            dns[:] = [
                d
                for d in dns
                if d
                not in (
                    ".git",
                    "node_modules",
                    ".venv",
                    "venv",
                    "__pycache__",
                    "dist",
                    "build",
                    "target",
                    ".next",
                )
            ]
            for fn in fns:
                if not fn.lower().endswith(SRC_EXT):
                    continue
                fp = os.path.join(dp, fn)
                try:
                    for i, line in enumerate(
                        Path(fp).read_text("utf-8", "replace").splitlines(), 1
                    ):
                        if rx.search(line):
                            out.append(f"{fp}:{i}:{line}")
                            if len(out) > 4000:
                                return out
                except Exception:
                    continue
    except Exception:
        pass
    return out


def _is_scratch(abs_path: str, untracked: bool) -> bool:
    """True for a throwaway probe/scratch file that is not a deliverable.

    TWO narrow rules, deliberately not one blanket suppression:

      1. the path sits in a known scratch tree (the segments per-edit-check already
         self-scopes on), OR
      2. the file is UNTRACKED *and* its basename starts with `_`.

    Rule 2 extends to FILES the private-by-convention prefix this module already
    honours for SYMBOLS (`_extract` drops any name starting with `_`). Both halves are
    required: a TRACKED `_build_thing.py` is a committed deliverable and stays in
    scope, and an untracked `feature.py` is real new code and stays in scope. This is
    the mechanism behind the measured noise -- wire-check flagged `_h1_inventory.py`,
    `_h2_unwired.py` and a sibling lane's `_s2_render_probe.py` minutes after they were
    written, which is exactly how a hook teaches its reader to ignore it.

    `WIRE_CHECK_NO_SKIP=1` turns the skip off so the suppression is auditable and can
    never permanently hide a finding from someone looking for it.
    """
    if os.environ.get("WIRE_CHECK_NO_SKIP", "").lower() in ("1", "true", "on", "yes"):
        return False
    norm = abs_path.replace("\\", "/").lower()
    if any(seg in norm for seg in _SCRATCH_SEG):
        return True
    return untracked and os.path.basename(abs_path).startswith("_")


def _changed_files(cwd: str) -> list[tuple[str, bool]]:
    """Return [(abs_path, is_untracked)] for changed SOURCE files (working tree vs HEAD).

    NOTE on untracked coverage: `git status --porcelain` COLLAPSES a wholly-untracked
    directory to a single `?? dir/` entry, which does not end in a source extension and
    is therefore dropped here. So files inside a brand-new untracked directory are not
    analysed at all -- pre-existing behaviour, recorded because it silently limits this
    hook's reach and because it made one scratch-skip test case pass for the wrong
    reason. Widening it would need `-uall`; that is a coverage decision, not a fix.
    """
    base = os.environ.get("WIRE_CHECK_BASE", "")
    files: dict[str, bool] = {}
    names = _git(cwd, "diff", "--name-only", base or "HEAD") or ""
    for n in names.splitlines():
        n = n.strip()
        if n.lower().endswith(SRC_EXT):
            files[os.path.join(cwd, n)] = False
    status = _git(cwd, "status", "--porcelain") or ""
    for line in status.splitlines():
        if line.startswith("??"):
            p = line[2:].strip().strip('"')
            if p.lower().endswith(SRC_EXT):
                files[os.path.join(cwd, p)] = True
    return [(p, u) for p, u in files.items() if not _is_scratch(p, u)]


def _added_block(cwd: str, abs_path: str, untracked: bool) -> str:
    """Return the text of lines ADDED this session for a file (best-effort)."""
    if untracked:
        try:
            return Path(abs_path).read_text("utf-8", "replace")
        except Exception:
            return ""
    base = os.environ.get("WIRE_CHECK_BASE", "") or "HEAD"
    rel = os.path.relpath(abs_path, cwd)
    diff = _git(cwd, "diff", "--unified=0", base, "--", rel) or ""
    added = []
    for ln in diff.splitlines():
        if ln.startswith("+") and not ln.startswith("+++"):
            added.append(ln[1:])
    return "\n".join(added)


def _extract(block: str):
    """Return (symbols:set[str], routes:set[str]) from an added-line block."""
    syms, routes = set(), set()
    for rx in (_DEF_TOPLEVEL, _DEF_EXPORT_CONST, _HANDLER):
        for m in rx.finditer(block):
            name = m.group(1)
            if name and not name.startswith("_") and len(name) >= 3:
                syms.add(name)
    for rx in (_ROUTE, _ROUTE_CS):
        for m in rx.finditer(block):
            p = m.group(1)
            if (
                len(p) >= 4
                and re.search(r"[A-Za-z]", p)
                and _ROUTE_PATHLIKE.search(p)
                and not _NOT_ROUTE.search(p)
            ):
                routes.add(p)
    return syms, routes


def _ref_count(cwd: str, name: str) -> int:
    """Count NON-definition references to `name` across the repo."""
    def_re = re.compile(
        r"(?:def|class|function|func|interface|type|enum|struct|trait|const|let|var)\s+"
        + re.escape(name)
        + r"\b"
        r"|\b" + re.escape(name) + r"\s*[=:]\s*(?:\(|async|function)"
    )
    refs = 0
    for line in _rg_lines(cwd, name):
        text = line.split(":", 2)[-1]
        if def_re.search(text):
            continue  # a definition of the symbol, not a use
        refs += 1
    return refs


def _literal_count(cwd: str, lit: str) -> int:
    return len(_rg_lines(cwd, lit, fixed=True))


def _base_is_live(cwd: str, base: str, all_files: list[str]) -> bool:
    blow = base.lower()
    for fp, _u in all_files:
        stem = os.path.splitext(os.path.basename(fp))[0].lower()
        if stem == blow:
            return True
    # any file in the repo named base.* ?
    for line in _rg_lines(cwd, base):  # cheap: name appears anywhere as a word
        return True
    return False


def analyze(cwd: str) -> list[str]:
    global _HARD_DEADLINE
    changed = _changed_files(cwd)
    deadline = _deadline_s()
    t_start = time.monotonic()
    # Publish the absolute deadline so _rg_lines() can bound BOTH the ripgrep child
    # timeout and the os.walk fallback. Without this line the module-level guard is
    # inert and only the loop-top checks apply, which is what let a run reach 106% of
    # a 25 s budget after one 12.3 s lookup.
    _HARD_DEADLINE = None if deadline == float("inf") else t_start + deadline
    LAST_RUN.update(truncated=False, checked=0, deadline_s=deadline)

    def _out_of_time() -> bool:
        if time.monotonic() - t_start <= deadline:
            return False
        LAST_RUN["truncated"] = True
        return True

    def _measured(zeroish: bool) -> bool:
        """Gate every 'nothing found' verdict on the budget NOT having expired.

        A lookup can start inside the deadline and finish outside it, and once the
        deadline has passed `_rg_lines` returns [] by design -- which reads as zero
        references, which is precisely this hook's dead-code trigger. Reporting that
        would manufacture the same false positive the encoding fix removed, just from a
        different cause. So an unconfirmed zero is downgraded to a truncation, never
        emitted as a finding. Regression: test_wire_check_noise.py::deadline_cases.
        """
        if not zeroish:
            return False
        if _time_left() <= 0:
            LAST_RUN["truncated"] = True
            return False
        return True

    if not changed:
        return []
    findings: list[str] = []
    seen_sym: set[str] = set()
    checked = 0

    # (A) dead/unwired added symbols + routes
    for abs_path, untracked in changed:
        if _out_of_time():
            break
        if TEST_HINT.search(abs_path):
            continue  # don't flag test-local helpers as "dead production code"
        block = _added_block(cwd, abs_path, untracked)
        if not block:
            continue
        syms, routes = _extract(block)
        for name in sorted(syms):
            if name in seen_sym or checked >= MAX_SYMBOLS:
                continue
            if _out_of_time():
                break
            seen_sym.add(name)
            checked += 1
            LAST_RUN["checked"] = checked
            if _measured(_ref_count(cwd, name) == 0):
                findings.append(
                    f"`{name}()` (added in {os.path.basename(abs_path)}) is referenced 0x"
                )
            if len(findings) >= MAX_FINDINGS:
                return findings
        for rp in sorted(routes):
            if checked >= MAX_SYMBOLS:
                break
            if _out_of_time():
                break
            checked += 1
            LAST_RUN["checked"] = checked
            if _measured(_literal_count(cwd, rp) <= 1):
                findings.append(
                    f"route '{rp}' (added in {os.path.basename(abs_path)}) is linked/navigated 0x"
                )
            if len(findings) >= MAX_FINDINGS:
                return findings

    # (B) duplicate-version: _v2/_new/_copy file or symbol with no live v1
    # Deadline-checked too: _base_is_live() and _ref_count() below each cost a full-tree
    # ripgrep walk (~1.7 s measured on this repo), so an unbounded (B) can blow the
    # budget on its own even when (A) finished inside it.
    dup_seen: set[str] = set()
    for abs_path, _u in changed:
        if _out_of_time():
            break
        stem = os.path.splitext(os.path.basename(abs_path))[0]
        m = _VERSUF.match(stem)
        if m:
            base = m.group("base")
            if base and base.lower() not in dup_seen and len(base) >= 3:
                dup_seen.add(base.lower())
                if _measured(not _base_is_live(cwd, base, changed)):
                    findings.append(
                        f"`{os.path.basename(abs_path)}` looks like a versioned fork but no live "
                        f"v1 `{base}` (file or reference) exists"
                    )
            if len(findings) >= MAX_FINDINGS:
                return findings
    # versioned SYMBOLS too
    for name in list(seen_sym):
        if _out_of_time():
            break
        m = _VERSUF.match(name)
        if m:
            base = m.group("base")
            if base and base.lower() not in dup_seen and len(base) >= 3:
                dup_seen.add(base.lower())
                if _measured(_ref_count(cwd, base) == 0):
                    findings.append(
                        f"symbol `{name}` looks versioned but base `{base}` is referenced 0x"
                    )
            if len(findings) >= MAX_FINDINGS:
                break
    return findings


def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("WIRE_CHECK", "").lower() in (
            "off",
            "0",
            "false",
        ):
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0
        if data.get("stop_hook_active"):
            return 0  # anti-loop
        cwd = str(data.get("cwd") or os.getcwd())
        if _git(cwd, "rev-parse", "--is-inside-work-tree", timeout=5) is None:
            return 0  # not a git repo -> nothing reliable to diff
        findings = analyze(cwd)
        if not findings:
            return 0
        shown = "; ".join(findings[:MAX_FINDINGS])
        # Disclose a deadline-truncated scan. Silence on a truncated run would read as
        # "nothing else is dead", which the scan did not establish.
        partial = ""
        if LAST_RUN.get("truncated"):
            partial = (
                f" NOTE: this scan stopped at its {LAST_RUN.get('deadline_s')}s deadline "
                f"after {LAST_RUN.get('checked')} symbol(s) — treat the list as PARTIAL, "
                f"not as an all-clear for the rest of the diff "
                f"(WIRE_CHECK_DEADLINE_S=0 to run unbounded)."
            )
        msg = (
            f"[wire-check] WIRING CHECK — code you added this session looks unreferenced: "
            f"{shown}. Is it dead code, or built-but-not-yet-wired? Wire it into a live call "
            f"path (import/route/handler), delete it, or confirm it is an intentional public "
            f"API / entry point. (File-level untracked imports are covered separately by "
            f"orphan-commit — which is itself wired NOWHERE today, so that referral is "
            f"currently unbacked.){partial}"
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "Stop",
                        "additionalContext": msg,
                    }
                }
            )
        )
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
