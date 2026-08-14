"""Compile every tracked .py at the LOWEST python-version this repo's CI pins.

WHY THIS EXISTS
---------------
This repo runs a SPLIT interpreter surface. `.github/workflows/*.yml` pins several
`python-version:` values at once, and code authored against the newest one parses fine
locally, passes review, and then fails at import time on a job pinned to the oldest.

That is not hypothetical here -- it is the same defect twice, both caught only by CI:

  * `command-center/mcp-audit/_r4_*.py` used a backslash inside an f-string expression.
    Legal from 3.12 (PEP 701), a SyntaxError on the 3.11 pin the mcp-audit workflow uses.
    The gate had never parsed on the interpreter that runs it.
  * `ci/tests/test_command_doc_promises.py` called `Path.read_text(newline=...)`, a 3.13
    keyword, on the same 3.11 pin.

Neither is a logic bug and neither is reachable by a linter that parses with the ambient
interpreter -- `ruff` and `basedpyright` both accept the newer syntax under their own
target settings. The only instrument that separates "valid Python" from "valid on the
interpreter that will actually run it" is compiling on that interpreter.

WHY THE FLOOR IS DISCOVERED, NOT HARDCODED
------------------------------------------
An earlier report in this lane asserted "9 of 11 python-version pins are 3.11". That was
true at the revision it was measured on and false two commits later, because siblings kept
adding workflows -- the count reached 13 within a day and every new pin was 3.11. A
hardcoded floor would rot exactly the same way, so the floor is read from the workflows on
every run and printed in the output.

WHY EVERY NUMBER CARRIES A REVISION ANCHOR
------------------------------------------
The same rot then bit this gate's OWN output. Its first run reported "2,618 tracked .py",
that number was copied into a durable doc, and the true count is 2,619 at both commits the
sentence could have meant -- the sweep had run before the gate's own file was staged. The
defect is not the digit: an unanchored count cannot be told apart from a stale one, so a
reader has no way to know which of the two it is holding.

So the sweep reports WHAT IT MEASURED, not just how many: the commit, plus how many tracked
`.py` differ from it. Both halves are needed and neither is redundant -- the file LIST comes
from the index (`git ls-files`) while the BYTES come from the working tree, so a bare sha
does not identify what was scanned. `--self-test` proves the anchor tracks reality by
building a throwaway repo and reading it clean, then dirty.

WHY EXCLUSIONS COME FROM ruff.toml AND ARE PRINTED, NOT DROPPED
--------------------------------------------------------------
The first version of this gate was left unwired for an honest reason: run over EVERY tracked
`.py` it reported 4 files that do not parse at the floor, so wiring it would have taken `main`
red on arrival. Two of the four are `command-center/ssot/salvaged-from-scratch/*.py`, frozen
byte-identical evidence that must not be edited at all; the other two are the vendored
Databricks notebook export in both dual-write mirrors.

All four are ALREADY excluded by the repository's own `ruff.toml`, each with a written
rationale. So the exclusion list is READ FROM `ruff.toml` rather than restated here -- a second
list would drift from the first, and the drift would be invisible. The sweep then splits:

  * BLOCKING  -- tracked `.py` that `ruff.toml` does NOT exclude. These set the exit code.
  * ADVISORY  -- the excluded ones. They are still compiled and still PRINTED with their error
    and the pattern that excused them; they just do not fail the build.

Advisory is deliberately not silence. `ruff` does not even parse these files, so this gate
reports strictly more than the linter does, and the day the notebook export is fixed its two
advisory lines disappear on their own. A gate whose exclusions are invisible is the
silent-pass shape this repo has been bitten by; printing them is what keeps this one honest.

Guarded against becoming a rubber stamp: if the exclusion patterns ever swallow more than
`EXCLUDE_CEILING` of the tracked tree the sweep FAILS instead of reporting a comfortable green,
so silencing this gate by widening `ruff.toml` is loud. Measured 225 of 2,664 tracked `.py`
excluded (8.4%) at `ea51f7e1`+1 -- and per the rule above that figure carries its anchor
because it WILL rot; `--report` recomputes it and prints the per-pattern breakdown every run,
so read that rather than this sentence.

FAIL-CLOSED, because a gate that cannot run must not report clean (ci-hygiene section 1):
  * no `python-version:` pin found            -> exit 1
  * zero tracked .py discovered               -> exit 1
  * the floor interpreter cannot be located   -> exit 1
  * exclusions cover more than the ceiling    -> exit 1
A missing or unparseable `ruff.toml` is fail-closed by construction rather than by a special
case: no patterns load, so every file becomes BLOCKING and the four known-bad ones turn the
gate red.

WIRED INTO CI by `.github/workflows/interpreter-floor.yml`, which runs `--self-test` (the
both-states control) before the sweep, on push to main and on every pull request. That wiring
is itself pinned by `ci/tests/test_interpreter_floor_wiring.py`, whose red-proof cuts each
wire in a scratch copy and requires the specific code to fire -- so deleting the workflow step
fails a test rather than silently retiring the gate.

USAGE
    python command-center/ci/interpreter_floor_gate.py --self-test   # both-states control
    python command-center/ci/interpreter_floor_gate.py               # the sweep
    python command-center/ci/interpreter_floor_gate.py --report      # sweep + inventory
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

PIN = re.compile(r"""python-version:\s*['"]?([0-9]+\.[0-9]+)['"]?""")

#: Largest share of the tracked tree the `ruff.toml` exclusions may cover before the sweep
#: refuses to report a verdict. Measured at wiring time: 231/2,658 = 0.087. The ceiling is not
#: a tuning knob for the current number -- it is the tripwire for someone widening a pattern
#: (a stray `**`) until this gate inspects nothing and still exits 0.
EXCLUDE_CEILING = 0.35

#: Compiled by a worker so the sweep costs ONE process, not one per file.
WORKER = r"""
import json, sys
bad = []
for p in json.load(sys.stdin):
    try:
        with open(p, "rb") as fh:
            compile(fh.read(), p, "exec")
    except SyntaxError as e:
        bad.append({"path": p, "line": e.lineno, "msg": str(e.msg)})
    except Exception as e:
        bad.append({"path": p, "line": None, "msg": type(e).__name__ + ": " + str(e)})
json.dump(bad, sys.stdout)
"""


def _ver(v: str) -> tuple[int, ...]:
    """`"3.9"` -> `(3, 9)`. Ordering versions as STRINGS puts 3.9 above 3.11; this does not."""
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return ()


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parent,
    )
    return Path(out.stdout.strip())


def discover_floor(root: Path) -> tuple[str | None, dict[str, list[str]]]:
    """Return (lowest pinned version, {version: [workflow files]})."""
    seen: dict[str, list[str]] = {}
    wf = root / ".github" / "workflows"
    for path in sorted(wf.glob("*.yml")) + sorted(wf.glob("*.yaml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for version in PIN.findall(text):
            seen.setdefault(version, []).append(path.name)
    if not seen:
        return None, seen
    floor = min(seen, key=_ver)
    return floor, seen


def describe_tree(root: Path) -> tuple[str, int]:
    """Return (HEAD sha, count of tracked `.py` whose bytes differ from HEAD).

    Both halves are load-bearing. The sweep takes its file LIST from the index and its
    BYTES from the working tree, so on a dirty tree the commit alone names something
    that was never scanned. Untracked files are excluded because `git ls-files` does
    not return them, so they are not scanned either.

    Fails soft to `UNKNOWN`/0 rather than raising: an anchor is context on a result,
    and losing it must not take the sweep down with it. `--self-test` is what proves
    the values are measured rather than stubbed.
    """

    def g(*args: str) -> str:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=root, check=False
        )
        return out.stdout.strip() if out.returncode == 0 else ""

    head = g("rev-parse", "HEAD") or "UNKNOWN"
    status = g(
        "status", "--porcelain", "--no-renames", "--untracked-files=no", "--", "*.py"
    )
    return head, len([ln for ln in status.splitlines() if ln.strip()])


def anchor_str(head: str, dirty: int) -> str:
    """Compact form for the terminal marker, so a copied number carries its revision."""
    return head[:12] + (f"+{dirty}dirty" if dirty else "")


def load_exclusions(root: Path) -> list[str]:
    """Read the exclusion patterns out of `ruff.toml`, or `[]` if it cannot be read.

    `[]` is the SAFE direction and is why this never raises: with no patterns every file is
    BLOCKING, so a deleted or corrupt `ruff.toml` reddens this gate instead of quietly
    excusing the files it used to cover.

    ONLY `extend-exclude` is read -- NOT the narrower `[format].exclude`.

    That distinction was got wrong first and corrected by measurement, so the reasoning is
    recorded rather than the conclusion alone. The first version read both tables, on the
    argument that the six `[format].exclude` entries are format-frozen evidence and a parse
    failure in them is therefore not build-stopping. `ruff check --show-files` refuted it:
    those six files are still LINTED by ruff, deliberately, and `ruff.toml` says why in its
    own comment -- a format-only exclusion is used "because it is strictly narrower: `ruff
    check` stays live on these files, so a real defect introduced later is still caught".

    A SyntaxError at the floor is exactly such a defect. Excusing them here would have made
    this gate BROADER than the linter it borrows its list from -- silently downgrading six
    files on the strength of an exclusion ruff does not apply to them. Reading one table
    keeps the ADVISORY set a strict subset of what ruff already ignores.
    """
    try:
        data = tomllib.loads((root / "ruff.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    return [p for p in data.get("extend-exclude", []) if isinstance(p, str)]


def exclusion_for(path: str, patterns: list[str]) -> str | None:
    """Return the pattern excusing `path` (repo-relative, posix), else None.

    A deliberately small subset of ruff's matcher, covering the four shapes `ruff.toml`
    actually uses: an exact file path, a directory name, a `dir/**` subtree, and a pattern
    with a `*` segment. It is intentionally never BROADER than ruff -- a path this returns
    None for is one ruff also lints, so a file cannot become advisory here while staying
    blocking there.
    """
    for pat in patterns:
        stem = pat.rstrip("/")
        if stem.endswith("/**"):
            stem = stem[:-3]
        if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path, stem):
            return pat
        if path.startswith(stem + "/"):
            return pat
        if "*" in stem and fnmatch.fnmatch(path, stem + "/*"):
            return pat
    return None


def partition(
    paths: list[str], patterns: list[str]
) -> tuple[list[str], dict[str, str]]:
    """Split tracked paths into (blocking, {advisory path: excusing pattern})."""
    blocking: list[str] = []
    advisory: dict[str, str] = {}
    for p in paths:
        hit = exclusion_for(p, patterns)
        if hit is None:
            blocking.append(p)
        else:
            advisory[p] = hit
    return blocking, advisory


# ------------------------------------------------------------------------------ wiring

#: The gate's own repo-relative path. A workflow must name THIS for the gate to be reachable.
GATE_REL = "command-center/ci/interpreter_floor_gate.py"

#: Every way this gate can be committed but unreachable. A code with no red-proof in
#: `ci/tests/test_interpreter_floor_wiring.py` is a code nobody has ever seen fire, and that
#: suite asserts the two lists match.
WIRING_CHECKS = {
    "W1-no-workflow-invokes-gate": "no .github/workflows/*.yml runs the gate script",
    "W2-invoked-without-self-test": "invoked, but never with --self-test (both-states control)",
    "W3-gate-path-does-not-exist": "a workflow names a gate path that is not on disk",
    "W4-not-run-on-push-to-main": "no invoking workflow triggers on push to main",
    "W5-not-run-on-pull-request": "no invoking workflow triggers on pull_request",
}


def _on_map(text: str) -> dict[str, str]:
    """Return the `on:` mapping of a workflow as {trigger: body}, comments stripped.

    Textual rather than parsed: no CI step in this repo installs a YAML library, and adding a
    dependency to a wiring check would make the check the thing most likely to break. The
    trade is recorded rather than hidden -- this reads indentation, so it would misread an
    inline-flow `on: {push: ...}`. No workflow here uses that form, and the red-proofs cut the
    real shape.

    Comments are dropped BEFORE the split, on purpose. This file's own `on:` block carries a
    comment explaining why `pull_request` has no `branches: [main]` filter -- and that comment
    contains the word `main`. A naive substring test over the raw block would therefore read
    "push to main" as satisfied even after `branches: [main]` was deleted, which is a checker
    that passes because of its own documentation. `mut_w4b` pins that.
    """
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    body: list[str] = []
    inside = False
    for line in lines:
        if not inside:
            if re.match(r"^on:\s*$", line):
                inside = True
            continue
        if line[:1].strip():
            break  # next top-level key
        body.append(line)

    out: dict[str, list[str]] = {}
    key: str | None = None
    indent = None
    for line in body:
        if not line.strip():
            continue
        cur = len(line) - len(line.lstrip())
        m = re.match(r"^\s*([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m and (indent is None or cur <= indent):
            indent = cur
            key = m.group(1)
            out[key] = [m.group(2)]
        elif key is not None:
            out[key].append(line.strip())
    return {k: "\n".join(v) for k, v in out.items()}


def wiring_violations(root: Path) -> list[str]:
    """Return the WIRING_CHECKS codes currently violated. Empty means the gate is reachable."""
    wf_dir = root / ".github" / "workflows"
    workflows = sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml"))

    invoking: list[tuple[Path, str]] = []
    named_paths: set[str] = set()
    for path in workflows:
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"[\w./-]*interpreter_floor_gate\.py", text):
            named_paths.add(m.group(0))
        if GATE_REL in text:
            invoking.append((path, text))

    bad: list[str] = []
    if not invoking:
        # W2/W4/W5 are properties OF the invoking workflows, so with none they would all fire
        # at once and no mutation could be shown to cut exactly one wire. W1 is the finding.
        bad.append("W1-no-workflow-invokes-gate")
    else:
        if not any(
            re.search(r"interpreter_floor_gate\.py\s+--self-test", t)
            for _, t in invoking
        ):
            bad.append("W2-invoked-without-self-test")
        ons = [_on_map(t) for _, t in invoking]
        if not any("main" in o.get("push", "") for o in ons):
            bad.append("W4-not-run-on-push-to-main")
        if not any("pull_request" in o for o in ons):
            bad.append("W5-not-run-on-pull-request")

    # Checked independently of W1: a workflow naming a MOVED gate is reachable-looking and
    # broken, which is the failure a path rename produces.
    if any(not (root / p).exists() for p in named_paths):
        bad.append("W3-gate-path-does-not-exist")
    return sorted(bad)


def tracked_py(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "*.py"],
        capture_output=True,
        check=True,
        cwd=root,
    )
    return [p for p in out.stdout.decode("utf-8").split("\0") if p]


def floor_interpreter(floor: str) -> list[str] | None:
    """Locate an interpreter for `floor`, or None. Never falls back to `sys.executable`."""
    if ".".join(str(x) for x in sys.version_info[:2]) == floor:
        return [sys.executable]
    candidates: list[list[str]] = []
    if os.name == "nt":
        candidates.append(["py", "-" + floor])
    candidates.append(["python" + floor])
    for cmd in candidates:
        try:
            probe = subprocess.run(
                [*cmd, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        if probe.returncode == 0 and probe.stdout.strip() == floor:
            return cmd
    return None


def sweep(interp: list[str], paths: list[str], cwd: Path) -> list[dict]:
    proc = subprocess.run(
        [*interp, "-c", WORKER],
        input=json.dumps(paths),
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------- self-test

GOOD = "x = 1\nprint(f'{x}')\n"
#: Backslash inside an f-string expression: legal from 3.12 (PEP 701), SyntaxError before.
BAD_312 = "rows = ['a']\nprint(f\"{'\\n'.join(rows)}\")\n"
#: `Path.read_text(newline=)` is 3.13+, but it is a RUNTIME TypeError, not a SyntaxError --
#: it is here to document the limit of this gate, not as a case it is expected to catch.
BAD_313_RUNTIME = "from pathlib import Path\nPath('x').read_text(newline='')\n"


def anchor_control(check) -> None:
    """Read the anchor off a throwaway repo, clean and then dirty.

    Hermetic on purpose. Reading THIS repo would race the siblings committing into the
    shared worktree, and a control that can fail for a reason unrelated to the claim is
    worse than none. A stub cannot pass both halves: a hardcoded 0 fails the dirty read,
    a hardcoded 1 fails the clean one, a fixed string fails the commit-id shape.
    """
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)

        def g(*args: str) -> None:
            subprocess.run(
                ["git", *args], cwd=d, capture_output=True, text=True, check=False
            )

        g("init", "-q")
        g("config", "user.email", "gate@invalid")
        g("config", "user.name", "interp-floor-gate")
        (d / "m.py").write_text(GOOD, encoding="utf-8")
        g("add", "m.py")
        g("-c", "commit.gpgsign=false", "commit", "-qm", "seed")

        head_clean, dirty_clean = describe_tree(d)
        (d / "m.py").write_text(GOOD + "y = 2\n", encoding="utf-8")
        head_dirty, dirty_dirty = describe_tree(d)

        check(
            "anchor is a real commit id",
            bool(re.fullmatch("[0-9a-f]{40}", head_clean)),
            True,
        )
        check("clean tree reports 0 modified .py", dirty_clean, 0)
        check("edited tree reports 1 modified .py", dirty_dirty, 1)
        check(
            "the commit does not move when only the worktree does",
            head_dirty == head_clean,
            True,
        )


def exclusion_control(check) -> None:
    """Prove the exclusion split fires, stays silent, and fails CLOSED -- on a scratch tree.

    Hermetic for the same reason as `anchor_control`: reading this repository's real
    `ruff.toml` would race the siblings editing it, and a control that can fail for a reason
    unrelated to the claim is worse than no control.

    The two directions that matter are asserted against each other. A matcher that excused
    everything would pass the "is excused" row and fail "is NOT excused"; one that excused
    nothing fails the reverse. The `**` row is the rubber-stamp tripwire, and the missing /
    corrupt rows pin the direction a broken config leans.
    """
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "ruff.toml").write_text(
            'extend-exclude = ["vendor/**", "frozen", "one/exact.py"]\n'
            '[format]\nexclude = ["fmt/only.py"]\n',
            encoding="utf-8",
        )
        pats = load_exclusions(d)
        check("extend-exclude is read, [format].exclude is NOT", len(pats), 3)

        for path, want in (
            ("vendor/deep/nested/mod.py", "vendor/**"),
            ("frozen/evidence.py", "frozen"),
            ("one/exact.py", "one/exact.py"),
        ):
            check(f"excused: {path}", exclusion_for(path, pats), want)
        # MUST STAY BLOCKING, or the rows above could be passed by excusing everything.
        for path in ("src/real.py", "vendored/notvendor.py", "one/other.py"):
            check(f"still blocking: {path}", exclusion_for(path, pats), None)
        # REGRESSION. The first version read `[format].exclude` too, which made this gate
        # BROADER than ruff on six files ruff still lints. `ruff check --show-files` refuted
        # it; this row is what stops it coming back.
        check(
            "a [format].exclude entry stays BLOCKING",
            exclusion_for("fmt/only.py", pats),
            None,
        )

        files = ["src/a.py", "src/b.py", "vendor/c.py", "frozen/d.py"]
        blocking, advisory = partition(files, pats)
        check("partition splits 2/2", (len(blocking), len(advisory)), (2, 2))

        # Fail-closed: no config, or an unreadable one, must excuse NOTHING.
        (d / "ruff.toml").unlink()
        check("missing ruff.toml excuses nothing", load_exclusions(d), [])
        (d / "ruff.toml").write_text("this is not = = toml\n", encoding="utf-8")
        check("corrupt ruff.toml excuses nothing", load_exclusions(d), [])

        # The rubber-stamp tripwire: a pattern that swallows the tree exceeds the ceiling.
        wide = ["**"]
        _, all_adv = partition(files, wide)
        check(
            "a tree-wide pattern trips the ceiling",
            len(all_adv) / len(files) > EXCLUDE_CEILING,
            True,
        )


def self_test(interp: list[str], floor: str) -> int:
    """Both states. A checker that cannot fail, and one that fails everything, both lose."""
    fails = 0

    def check(label: str, got, want) -> None:
        nonlocal fails
        ok = got == want
        fails += not ok
        print(f"  {'OK' if ok else 'XX'} [{label}] got={got} want={want}")

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "good.py").write_text(GOOD, encoding="utf-8")
        (d / "bad312.py").write_text(BAD_312, encoding="utf-8")
        (d / "runtime.py").write_text(BAD_313_RUNTIME, encoding="utf-8")
        names = ["good.py", "bad312.py", "runtime.py"]
        found = {b["path"] for b in sweep(interp, names, d)}

        # MUST FIRE: the newer-syntax file is the whole reason this gate exists.
        check("known-BROKEN file is flagged at the floor", "bad312.py" in found, True)
        # MUST STAY SILENT: otherwise it could pass the line above by flagging everything.
        check("known-GOOD file is NOT flagged", "good.py" in found, False)
        # Scope disclosure, asserted rather than claimed in prose.
        check(
            "runtime-only defect is NOT a syntax finding", "runtime.py" in found, False
        )

        # The floor really is the floor: on a NEWER interpreter the bad file must parse,
        # which is what makes "it compiles for me" an unreliable local signal.
        #
        # Two defects lived in this loop until the gate was actually wired and ran on Linux
        # for the first time. Both are kept in the comment rather than silently corrected:
        #   * `subprocess.run` RAISES FileNotFoundError for a missing executable, it does not
        #     return non-zero. `py` is the Windows launcher and does not exist on ubuntu, so
        #     the very first probe crashed the whole self-test. It never showed locally
        #     because `py` is present here -- an unwired gate cannot be wrong on a platform
        #     it has never run on. `floor_interpreter` already had the try/except; this did not.
        #   * the version test was a STRING comparison, and "3.9" > "3.11" is True
        #     lexicographically while 3.9 < 3.11 numerically. A runner offering only 3.9 would
        #     have been selected as "newer", and the row below would then demand that
        #     3.12-only syntax parse on 3.9 -- inverting the control into a false failure.
        newer = None
        for probe in (["py", "-3.12"], ["python3.12"], [sys.executable]):
            try:
                got = subprocess.run(
                    [*probe, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                continue
            if got.returncode == 0 and _ver(got.stdout.strip()) > _ver(floor):
                newer = probe
                break
        if newer is None:
            print(
                "  -- no newer interpreter available; skew half of the control not run"
            )
        else:
            still = {b["path"] for b in sweep(newer, ["bad312.py"], d)}
            check(
                "same file PARSES on a newer interpreter (the skew is real)",
                still,
                set(),
            )

    # Regression for a defect that shipped in this file's OWN control: version strings were
    # ordered lexicographically, which puts 3.9 ABOVE 3.11 and would have selected an older
    # interpreter as "newer". Both rows are needed -- the first fails under a string compare,
    # the second fails under any comparator that simply inverts.
    check(
        "3.9 orders BELOW 3.11 (a string compare inverts this)",
        _ver("3.9") < _ver("3.11"),
        True,
    )
    check("3.12 orders ABOVE 3.11", _ver("3.12") > _ver("3.11"), True)

    anchor_control(check)
    exclusion_control(check)

    print(
        f"SUCCESS:interp-floor-selftest floor={floor}"
        if not fails
        else f"FAILED:interp-floor-selftest {fails}"
    )
    return 1 if fails else 0


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--self-test", action="store_true", help="both-states control, then exit"
    )
    ap.add_argument(
        "--report", action="store_true", help="also print the pin inventory"
    )
    ap.add_argument(
        "--verify-wiring",
        action="store_true",
        help="assert a workflow actually runs this gate, then exit",
    )
    a = ap.parse_args(argv)

    root = repo_root()

    if a.verify_wiring:
        bad = wiring_violations(root)
        for code in bad:
            print(f"  {code}: {WIRING_CHECKS[code]}")
        if bad:
            print(f"FAILED:interp-floor-wiring {len(bad)}")
            return 1
        print(f"SUCCESS:interp-floor-wiring {len(WIRING_CHECKS)} invariants hold")
        return 0

    floor, pins = discover_floor(root)
    if floor is None:
        print("FAILED:interp-floor no python-version pin found in .github/workflows")
        return 1

    interp = floor_interpreter(floor)
    if interp is None:
        print(
            f"FAILED:interp-floor no interpreter for the {floor} floor (refusing to guess)."
            " A workflow now pins a version lower than the one this job installs: bump"
            " `python-version` in .github/workflows/interpreter-floor.yml to match the floor."
        )
        return 1

    head, dirty = describe_tree(root)

    if a.report:
        total = sum(len(v) for v in pins.values())
        print(
            f"pins: {total} across {len({f for v in pins.values() for f in v})} workflow files"
        )
        for version in sorted(pins, key=lambda v: tuple(int(x) for x in v.split("."))):
            print(f"  {version}  x{len(pins[version]):<3} {sorted(set(pins[version]))}")
        print(f"floor: {floor}   interpreter: {' '.join(interp)}")
        print(f"revision: {head}   tracked .py differing from it: {dirty}")
        pats = load_exclusions(root)
        _, adv = partition(tracked_py(root), pats)
        used: dict[str, int] = {}
        for hit in adv.values():
            used[hit] = used.get(hit, 0) + 1
        print(
            f"ruff.toml exclusion patterns: {len(pats)}  (ceiling {EXCLUDE_CEILING:.0%})"
        )
        for pat in sorted(used, key=lambda p: (-used[p], p)):
            print(f"  advisory x{used[pat]:<4} {pat}")

    if a.self_test:
        return self_test(interp, floor)

    paths = tracked_py(root)
    if not paths:
        print("FAILED:interp-floor zero tracked .py discovered (detector is blind)")
        return 1

    patterns = load_exclusions(root)
    blocking, advisory = partition(paths, patterns)

    share = len(advisory) / len(paths)
    if share > EXCLUDE_CEILING:
        print(
            f"FAILED:interp-floor ruff.toml excludes {len(advisory)}/{len(paths)}"
            f" ({share:.1%}) of tracked .py, over the {EXCLUDE_CEILING:.0%} ceiling"
            " -- refusing to report a verdict on what is left"
        )
        return 1

    at = anchor_str(head, dirty)
    bad = sweep(interp, blocking, root)
    excused = sweep(interp, sorted(advisory), root) if advisory else []

    print(
        f"scanned {len(blocking)} blocking + {len(advisory)} advisory tracked .py"
        f" at the {floor} floor @ {at} -> {len(bad)} blocking, {len(excused)} advisory"
        " that do not parse"
    )
    for b in sorted(bad, key=lambda x: x["path"]):
        print(f"  BLOCKING {b['path']}:{b['line']}  {b['msg']}")
    # Printed, never dropped: these are excused by ruff.toml, not unknown to this gate.
    for b in sorted(excused, key=lambda x: x["path"]):
        print(
            f"  advisory {b['path']}:{b['line']}  {b['msg']}"
            f"   [excluded by ruff.toml: {advisory[b['path']]}]"
        )
    if bad:
        print(f"FAILED:interp-floor {len(bad)} @ {at}")
        return 1
    print(
        f"SUCCESS:interp-floor {len(blocking)} files parse at {floor} @ {at}"
        f" ({len(excused)} advisory not-parsing, excused by ruff.toml)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
