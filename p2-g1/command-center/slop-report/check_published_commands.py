r"""check_published_commands.py -- a committed document may not publish a command that a
clone cannot run.

WHY THIS EXISTS
---------------
The SLOP lane found 45 probe scripts that committed artifacts named while `.gitignore:76`
(`command-center/_*.py`) kept every one of them untracked. On the author's disk the
citations resolved; in any clone they resolved to nothing. The lane carried those 45 into
git. Nothing prevented the 46th -- and there was one, in a directory the lane never looked
at (`platform/lib/`, cited from two committed command-centre reports).

This gate is the class fix. It does not read prose and it does not trust a claim: for every
tracked document it finds each published `python <path>` invocation and requires <path> to
be TRACKED IN GIT. A tracked target is reproducible by anyone; an untracked one is a promise
only the author can keep.

COUNT THE FIELD, NOT THE DOCUMENT
---------------------------------
The obvious version of this gate is refuted, and the refutation is why the scope is narrow.
Grepping tracked artifacts for an untracked script's BASENAME reports 103-158 hits, but 157
of the citers are the SLOP lane's own census outputs (`_slop_measure*.out.json`) whose whole
job is to ENUMERATE untracked filenames. A census that lists a file is measuring it, not
depending on it -- the use-vs-mention failure this repo has already paid for twice. A JSON
array element "_foo.py" cannot match `python <path>`, so that entire noise class disappears
by construction rather than by an exception list.

RESOLUTION -- two roots, because both conventions are in live use:
  * repo-root-relative   `python command-center/slop-report/_r2_gate_now.py`
  * citer-dir-relative   `python scripts/render_docx.py` inside skills/doc/SKILL.md
A target that resolves as TRACKED under EITHER root passes. Requiring repo-root only would
report ~83 false violations across the skill packs.

CORPUS -- tracked `.md` under the paths this repo authors, minus harvested transcripts.
`command-center/grounding/harvest-split/` and `command-center/harvest/` are verbatim dumps of
past agent sessions. A transcript quoting a command another session ran is a record, not this
repo publishing an instruction; gating it would fire on the recording. That exclusion is
declared, counted and printed (`--report`), never silent.

DETECTOR CONTROLS -- this gate is itself a detector, so both states are proven:
  * fail-closed on ZERO commands found. A corpus that yields no invocations measures
    nothing, and a silent pass there is the exact defect this gate exists to prevent.
  * `--self-test` runs the resolver against a synthetic KNOWN-BAD target (an untracked
    path generated at runtime, so no committed byte can contain it) and a synthetic
    KNOWN-GOOD target (this file, which is tracked), and requires bad->violation,
    good->clean. A gate that has never gone red is indistinguishable from a no-op.
  * the sentinel is generated with `uuid4` rather than hardcoded. A fixed sentinel name
    poisons its own corpus the moment the gate and its receipt are committed -- measured on
    this lane's round-1 control, which shipped asserting `quiet == 0` and yields `quiet == 2`
    to everyone who reruns it.

PORTABILITY -- the repo root comes from `git rev-parse --show-toplevel`, not a literal. The
sibling gate `command-center/hook-audit/check_citations.py` hardcodes
`REPO = Path("C:/Users/Prekzursil/source/ast-integrate")` and therefore cannot run on a CI
runner at all, which is one reason it is not wired into any workflow.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import uuid
from pathlib import Path, PurePosixPath

BASELINE = "command-center/slop-report/published-commands-baseline.json"

# `python foo/bar.py`, `python3 -u foo/bar.py`, backticked or bare. The path must contain a
# slash: a bare `foo.py` has no unambiguous root to resolve against.
CMD = re.compile(
    r"\bpython3?(?:\.exe)?\s+(?:-[A-Za-z]\s+)*"
    r"([A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_.-]+\.py)"
)

# A document that DISCUSSES command conventions has to be able to quote one. Without an
# escape, this gate forbids its own documentation: the first report describing it quoted
# `python scripts/render_docx.py` as an example of the citer-relative convention and the gate
# flagged it -- correctly by its own rule, uselessly in fact. Discipline was tried first and
# failed inside one commit, against a DIFFERENT literal than the author was guarding.
#
# The escape is deliberately weak: it must NAME the exact target, on the same line. It cannot
# blanket-silence a file, a directory or a line, so it can suppress only the thing its author
# looked at and typed out. `--self-test` proves a marker naming a different target does NOT
# suppress.
EXAMPLE = re.compile(r"<!--\s*published-command-example:\s*(\S+?)\s*-->")

# `python` is not the only way a document publishes a runnable file. SLOP round 4 ran the
# settling experiment round 3 named -- "extend the CMD pattern beyond `python <path>`" --
# across five verb classes, and this is the part of it that survived its own evidence:
#
#   sh/ps    1 + 12 real invocations, 0 violations  -> SHIPPED here. Coverage that did not
#            exist: `pwsh -File scripts/sync-skills.ps1` and friends were published by 8
#            committed documents and guarded by nothing.
#   pytest   37 commands, 5 violations, and every one is a FALSE POSITIVE of the two-root
#            resolver, not slop: `pytest wfdsl/test_work_unit_authorization.py` resolves
#            under a third root (`platform/lib/`) the resolver does not model, and all 5
#            targets are already TRACKED. Shipping it would cost 5 baseline rows to catch
#            nothing. DECLINED, evidence in `_r4_locate.out.json`.
#   node     1 command, 1 violation, and it is a vendored `dist/index.js` under an ignored
#            third-party tree quoted by a discovery inventory. n=1 and noisy. DECLINED.
#   pybare   `python foo.py` with no slash -- 49 commands, 46 violations (94%). A detector
#            that flags almost everything it sees is measuring the wrong thing. This is the
#            slash requirement above being VINDICATED, not a hole. REFUTED, do not ship.
#
# The verb is required, and `&` / `./` were deliberately NOT accepted as verbs: with them the
# pattern matched `[`../../scripts/sync-hooks.ps1`](../../scripts/sync-hooks.ps1)` -- a
# markdown LINK, which is a mention, not an instruction. Measured: 15 matches with those
# branches, 13 without, and the 2 dropped were both that link. Same use-vs-mention discipline
# as the module docstring above.
SHELL = re.compile(
    r"\b(?:bash|sh|pwsh|powershell)(?:\.exe)?\s+(?:-[A-Za-z]+\s+)*"
    r"([A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_.-]+\.(?:sh|ps1))"
)

# (verb-label, pattern). The label reaches the violation message so a reader is told which
# command was published, not always "python".
EXTRACTORS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("python", CMD),
    ("shell", SHELL),
)

# Corpus roots this repo authors.
#
# `platform/` was added by SLOP build round 3. Leaving it out is precisely how 14
# published `python <path>` commands pointing at files that existed on ONE disk
# shipped without this gate saying a word. Measured cost of adding it, with a
# strict-superset control: corpus 288 -> 815 documents, and 19 rows surfaced that
# the narrow corpus could not see (`_r3_widen.py`).
INCLUDE_PREFIXES = ("command-center/", "docs/", "platform/")

# Verbatim recordings of other sessions -- a record, not an instruction. Counted, not hidden.
#
# `platform/routing/fixtures/` is the same category for a different reason: it is a
# fixture HOME tree of third-party skill docs, used as INPUT to the routing tests.
# Their `python scripts/foo.py` lines are relative to a deployed skill's own home,
# not to this repository, so resolving them here is a category error -- 9 of the 19
# rows above were that, and every one is a false positive. Excluding them is what
# makes the widening usable rather than a source of noise nobody can act on.
EXCLUDE_PREFIXES = (
    "command-center/grounding/harvest-split/",
    "command-center/harvest/",
    "platform/routing/fixtures/",
)


def git(root: str, *args: str, check: bool = True) -> str:
    r = subprocess.run(
        ["git", "-C", root, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and r.returncode != 0:
        raise SystemExit(
            f"FAILED:published-cmds git {args} rc={r.returncode}: {r.stderr[:400]}"
        )
    return r.stdout


def repo_root() -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        raise SystemExit("FAILED:published-cmds not inside a git work tree")
    return r.stdout.strip()


def norm(p: str) -> str:
    """Collapse `a/./b` and `a/../b` without touching the filesystem."""
    parts: list[str] = []
    for seg in PurePosixPath(p).parts:
        if seg == ".":
            continue
        if seg == ".." and parts and parts[-1] != "..":
            parts.pop()
            continue
        parts.append(seg)
    return "/".join(parts)


def in_corpus(path: str) -> bool:
    return (
        path.endswith(".md")
        and path.startswith(INCLUDE_PREFIXES)
        and not path.startswith(EXCLUDE_PREFIXES)
    )


def blob(root: str, path: str) -> str:
    r = subprocess.run(
        ["git", "-C", root, "cat-file", "-p", f"HEAD:{path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.stdout if r.returncode == 0 else ""


def resolve(target: str, citer: str, tracked: set[str]) -> tuple[bool, str | None]:
    """True + the resolved path if <target> is tracked under either root."""
    for cand in (norm(target), norm(str(PurePosixPath(citer).parent / target))):
        if cand in tracked:
            return True, cand
    return False, None


def scan(
    root: str, tracked: set[str], corpus: list[str]
) -> tuple[list[dict], int, int]:
    findings: list[dict] = []
    total = 0
    examples = 0
    for path in corpus:
        for lineno, line in enumerate(blob(root, path).splitlines(), 1):
            marked = {m.group(1) for m in EXAMPLE.finditer(line)}
            for verb, pat in EXTRACTORS:
                for m in pat.finditer(line):
                    total += 1
                    target = m.group(1)
                    if target in marked:
                        examples += 1
                        continue
                    ok, _ = resolve(target, path, tracked)
                    if not ok:
                        findings.append(
                            {
                                "citer": path,
                                "line": lineno,
                                "target": target,
                                "verb": verb,
                            }
                        )
    return findings, total, examples


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--report", action="store_true", help="print corpus stats and exit 0"
    )
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="prove the gate can FAIL: synthetic known-bad must be caught, known-good must not",
    )
    a = ap.parse_args(argv)

    root = repo_root()
    tracked = {p for p in git(root, "ls-files").splitlines() if p}
    all_md = [p for p in tracked if p.endswith(".md")]
    corpus = sorted(p for p in tracked if in_corpus(p))
    excluded = sorted(
        p
        for p in all_md
        if p.startswith(INCLUDE_PREFIXES) and p.startswith(EXCLUDE_PREFIXES)
    )

    if a.self_test:
        # Both states, against the REAL resolver, with a runtime-random sentinel so no
        # committed byte can contain it.
        bad = f"command-center/slop-report/_zz_absent_{uuid.uuid4().hex}.py"
        # Tracked since SLOP round 1. If it is ever renamed the self-test fails CLOSED,
        # which is the correct direction for a control.
        good = "command-center/slop-report/_b1_cited_probes.py"
        citer = "command-center/slop-report/SLOP-INTEGRATE-R1.md"
        bad_ok, _ = resolve(bad, citer, tracked)
        good_ok, _ = resolve(good, citer, tracked)
        # And prove the EXTRACTOR fires on a realistic line, not just the resolver.
        line = f"run `python {bad}` to regenerate"
        extracted = [m.group(1) for m in CMD.finditer(line)]
        # The escape must suppress ONLY the target it names, or it is a mute button.
        marked_same = {
            m.group(1)
            for m in EXAMPLE.finditer(f"<!-- published-command-example: {bad} -->")
        }
        other = f"command-center/slop-report/_zz_other_{uuid.uuid4().hex}.py"
        marked_other = {
            m.group(1)
            for m in EXAMPLE.finditer(f"<!-- published-command-example: {other} -->")
        }
        # The SHELL class ships with the same both-states burden as the python one, plus
        # the control for the exact mistake its first draft made: a markdown link is a
        # MENTION and must not be read as an instruction.
        shell_bad = f"scripts/_zz_absent_{uuid.uuid4().hex}.ps1"
        shell_extracted = [
            m.group(1)
            for m in SHELL.finditer(f"run `pwsh -File {shell_bad}` to deploy")
        ]
        link_extracted = [
            m.group(1)
            for m in SHELL.finditer(f"see [`../../{shell_bad}`](../../{shell_bad})")
        ]
        shell_bad_ok, _ = resolve(shell_bad, citer, tracked)

        checks = {
            "shell_extractor_finds_the_command": shell_extracted == [shell_bad],
            "shell_extractor_ignores_a_markdown_link": link_extracted == [],
            "shell_known_bad_is_flagged": not shell_bad_ok,
            "known_bad_is_flagged": not bad_ok,
            "known_good_is_clean": good_ok,
            "extractor_finds_the_command": extracted == [bad],
            "states_distinguishable": (not bad_ok) and good_ok,
            "corpus_nonempty": len(corpus) > 0,
            "example_marker_suppresses_the_target_it_names": bad in marked_same,
            "example_marker_does_NOT_suppress_another_target": bad not in marked_other,
        }
        for k, v in checks.items():
            print(f"   {'ok ' if v else 'FAIL'} {k}")
        if not all(checks.values()):
            print(
                "FAILED:published-cmds-selftest the gate cannot distinguish its two states"
            )
            return 1
        print("SUCCESS:published-cmds-selftest")
        return 0

    findings, total, examples = scan(root, tracked, corpus)

    # Baseline: violations INHERITED from another lane's tree. Keyed on (citer, target), never
    # on a line number, which drifts on every edit of the document.
    rows = json.loads((Path(root) / BASELINE).read_text(encoding="utf-8"))["entries"]
    baseline = {(r["citer"], r["target"]) for r in rows}
    live = {(f["citer"], f["target"]) for f in findings}
    new = [f for f in findings if (f["citer"], f["target"]) not in baseline]
    stale = sorted(baseline - live)

    if a.report:
        print(
            f"corpus            {len(corpus)} tracked .md under {list(INCLUDE_PREFIXES)}"
        )
        print(
            f"excluded          {len(excluded)} harvested transcripts under {list(EXCLUDE_PREFIXES)}"
        )
        print(f"commands found    {total}")
        print(
            f"example-marked    {examples} (declared quotations, each naming its target)"
        )
        print(
            f"violations        {len(findings)} "
            f"({len(baseline)} baselined, {len(new)} new, {len(stale)} stale rows)"
        )
        for f in findings:
            tag = "BASELINED" if (f["citer"], f["target"]) in baseline else "NEW"
            print(f"   [{tag}] {f['citer']}:{f['line']} -> {f['target']}")
        for c, t in stale:
            print(f"   [STALE-BASELINE] {c} -> {t}")
        return 0

    if total == 0:
        print("FAILED:published-cmds ZERO published commands found in a corpus of")
        print(
            f"       {len(corpus)} documents. A gate that measures nothing passes silently,"
        )
        print(
            "       which is the defect it exists to prevent. Fix the extractor or the corpus."
        )
        return 1

    for f in new:
        shown = (
            f"`python {f['target']}`"
            if f.get("verb", "python") == "python"
            else f"a shell invocation of `{f['target']}`"
        )
        print(
            f"!! {f['citer']}:{f['line']} publishes {shown} "
            f"but {f['target']} is NOT tracked -- unrunnable in a clone"
        )
    # A baseline that can only grow is a mute button. This makes it a ratchet.
    for c, t in stale:
        print(
            f"!! STALE BASELINE ROW: {c} -> {t} no longer violates. Delete the row from "
            f"{BASELINE} so the floor drops instead of drifting into slack."
        )
    print(
        f"\n== {total} published commands across {len(corpus)} documents; "
        f"{len(findings)} unrunnable ({len(baseline)} inherited/baselined), "
        f"{len(new)} NEW, {len(stale)} stale baseline row(s)"
    )
    if new or stale:
        if new:
            print(
                f"FAILED:published-cmds {len(new)} NEW published command(s) name an untracked path."
            )
            print(
                "       Either `git add` the target (it is evidence someone is expected to rerun)"
            )
            print("       or stop publishing it as a command.")
        if stale:
            print(f"FAILED:published-cmds {len(stale)} baseline row(s) are stale.")
        return 1
    print(
        f"SUCCESS:published-cmds no NEW unrunnable published command "
        f"({len(baseline)} inherited row(s) still open, see {BASELINE})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
