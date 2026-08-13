"""R4 gate: every command receipt in this lane's docs must be a RUNNABLE invocation.

THE DEFECT THIS EXISTS FOR
--------------------------
Round 3 committed a receipt table asserting::

    rule_audit.py --json --md           regenerated: JSON and TABLES byte-identical      rc=0

``--json --md`` is an argparse usage error: ``--md`` is consumed as the VALUE of ``--json``,
there is no second positional, and argparse exits 2 having written nothing. Measured round 4,
exit code captured unpiped::

    EXACT_RC=2 · stdout bytes 0 · "rule_audit.py: error: argument --json: expected one argument"

The paired "byte-identical (``cmp``)" was therefore VACUOUS as written -- the artifacts were
unchanged precisely because nothing was written. That is the single-signal §3c shape (a control
that cannot distinguish the two hypotheses) reproduced inside a receipt table. Both the round-3
VERIFY lane and the round-3 adversary found it independently; neither found it by reading, both
found it by EXECUTING. Nothing in the repo executed it, so it survived a commit, a verify and an
adversarial pass.

WHAT THIS GATE CHECKS, AND WHAT IT DELIBERATELY DOES NOT
--------------------------------------------------------
It checks ARGV VALIDITY -- "could this command line even start" -- against the tool's own real
parser. It does NOT check the claimed rc, and that distinction is load-bearing: ``r2_pathrefs.py``
exits 2 on a genuine finding, so an rc-equality gate would either demand that finding never
happen or need a per-command expected-rc table that rots the same way the prose does. Argv
validity is the property that is mechanically decidable, and it is the property that was violated.

Two tiers, and the tier is CHOSEN MECHANICALLY (does the module define ``build_parser()``?) so a
script cannot be silently downgraded:

* tier 1 (real parser) -- import the module, call ``build_parser().parse_args(argv)`` with stdout
  and stderr swallowed, and treat ``SystemExit`` as invalid. Catches a missing value, an unknown
  flag, a bad choice: the full argparse contract. ``rule_audit.py`` is here.
* tier 2 (flag-literal set) -- for hand-parsed scripts (``r2_pathrefs.py`` tests
  ``"--self-test" in sys.argv``; ``_r2_blobcheck.py`` scans for ``--rev``), the accepted flags are
  extracted from the module's own AST string constants. WEAKER, disclosed inline: it catches an
  unknown or misspelled flag and CANNOT catch a missing value, because a hand parser has no
  declared arity. A tier-2 script that grows a real parser is promoted automatically.

EXEMPTION IS AN EXPLICIT FIELD, NEVER A PROSE GUESS
----------------------------------------------------
A doc legitimately QUOTES the broken command while REPORTING that it is broken -- this file does
it twice above. Flagging that is the use-vs-mention mislabel this program keeps making, and the
sibling ``r2_control_count_gate.py`` already settled the shape: a line carrying the literal marker
``<!--argv-invalid-->`` is expected to be invalid. The marker is not a mute button. A marked line
whose argv actually PARSES is a violation too, so the marker cannot be used to silence a working
command, and it goes stale loudly if the tool later accepts what it used to reject.

FAIL CLOSED
-----------
Zero markdown, zero extracted invocations, or zero tier-1 validations all return non-zero. A
scan that matches nothing is a broken extractor, never "the docs agree with the tools" -- the
exact reading four probes once agreed on while iterating the wrong collection.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import importlib.util
import io
import re
import sys
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
MARKER = "<!--argv-invalid-->"

# A receipt table separates the command from its prose with a run of 2+ spaces; a markdown table
# separates it with backticks. Both are handled, because both are in this corpus.
_FIELD_SPLIT = re.compile(r"\s{2,}")
_CODE_SPAN = re.compile(r"`([^`]+)`")
# ``.py`` is OPTIONAL, and that is not cosmetic. The third site of the round-3 false receipt --
# the one that went into permanent git history -- writes ``rule_audit --json --md``, with no
# extension. The first version of this pattern required ``.py``, so it read that template and
# reported CLEAN: a gate silent in the known-broken state, measuring nothing, on the single site
# that cannot be edited after the fact. An extensionless name is only accepted when a matching
# ``<name>.py`` really exists in this directory, so prose cannot be promoted into a command.
_SCRIPT = re.compile(
    r"^(?:\$\s*)?(?:python\s+)?(?:[\w.\\/-]*[\\/])?([A-Za-z_][\w-]*(?:\.py)?)(?:\s+(.*))?$"
)
_FLAG = re.compile(r"^--?[A-Za-z][\w-]*(?:=.*)?$")
# A value is a path-ish token, a sha, or a ``<placeholder>``. Prose words ("SUCCESS",
# "regenerated", "rc=0") are deliberately NOT values: argv collection stops there, which truncates
# a receipt line at its prose instead of feeding the prose to a parser.
#
# The ``<placeholder>`` arm was added after the FIRST run of this gate reported
# ``rule_audit.py --json <path> --md <path>`` as unrunnable at four sites -- including the two
# reviewer artifacts that were prescribing the CORRECT form. Metasyntax is how a doc writes "a
# value goes here", so refusing it turns the right answer into a violation. Disclosed limit: with
# a placeholder accepted, this gate cannot tell ``--json <path>`` from a genuinely missing value.
# That is inherent -- a placeholder IS a stand-in for a value -- and it does not weaken the arm
# that matters, because the defect it was built for (``--json --md``) has no placeholder at all.
_VALUE = re.compile(
    r"^(?:[\w.\\/:*@~+-]*[./\\][\w.\\/:*@~+-]*|[0-9a-f]{7,40}|<[\w.-]+>)$"
)


class Invocation(NamedTuple):
    doc: str
    lineno: int
    script: str
    argv: tuple[str, ...]
    marked_invalid: bool


def split_candidates(line: str) -> list[str]:
    """Every substring of a line that could be a whole command, as written.

    ``_`` is NOT stripped from the field edges. The first version of this function stripped it as
    markdown emphasis and silently renamed ``_r2_blobcheck.py`` to ``r2_blobcheck.py``, which the
    gate then reported three times as "a script that is not in this directory" -- a detector
    manufacturing findings out of its own normalisation. Half this lane's scripts are ``_``-
    prefixed, so that edge is data, not decoration.
    """
    candidates = [span.strip() for span in _CODE_SPAN.findall(line)]
    stripped = _CODE_SPAN.sub(lambda m: m.group(1), line)
    candidates += [field.strip(" |*") for field in _FIELD_SPLIT.split(stripped)]
    return [c for c in candidates if c]


def parse_argv(rest: str) -> tuple[str, ...]:
    """Collect argv tokens, stopping at the first token that is prose rather than argv."""
    tokens: list[str] = []
    for token in rest.split():
        if _FLAG.match(token):
            tokens.append(token)
            continue
        if tokens and _VALUE.match(token):
            tokens.append(token)
            continue
        break
    return tuple(tokens)


def extract(text: str, doc: str, known: set[str] | None = None) -> list[Invocation]:
    """Every documented invocation, DEDUPED per (line, script, argv).

    One markdown line yields several candidates on purpose -- a code span and the 2+-space fields
    around it both get tested, so neither table style is missed. Without the dedupe the same
    receipt is counted twice and the violation total is inflated: the first run of this gate
    reported 22 violations for 11 distinct sites, which is the self-contradicting-output shape
    that has to be read as a detector fault, not a finding.
    """
    known = {p.name for p in HERE.glob("*.py")} if known is None else known
    found: list[Invocation] = []
    seen: set[tuple[int, str, tuple[str, ...]]] = set()
    for lineno, raw in enumerate(text.splitlines(), start=1):
        marked = MARKER in raw
        for candidate in split_candidates(raw.replace(MARKER, "")):
            match = _SCRIPT.match(candidate)
            if match is None:
                continue
            script, rest = match.group(1), match.group(2) or ""
            if not script.endswith(".py"):
                if f"{script}.py" not in known:
                    continue
                script = f"{script}.py"
            argv = parse_argv(rest)
            # No argv means nothing to validate: a bare filename mention is prose, not a receipt.
            # Requiring the FIRST token to be a flag is what keeps "script.py EVIDENCE IS NOT"
            # (a real sentence in this corpus) out of the command set.
            if not argv or not _FLAG.match(argv[0]):
                continue
            key = (lineno, script, argv)
            if key in seen:
                continue
            seen.add(key)
            found.append(Invocation(doc, lineno, script, argv, marked))
    return found


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(f"_r4_{path.stem}", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:  # a script that cannot import cannot be tier 1
        return None
    return module


def parser_of(path: Path) -> argparse.ArgumentParser | None:
    """Tier-1 accessor, chosen mechanically: the module must EXPOSE its real parser."""
    if "def build_parser(" not in path.read_text(encoding="utf-8"):
        return None
    module = load_module(path)
    builder = getattr(module, "build_parser", None)
    if builder is None:
        return None
    parser = builder()
    return parser if isinstance(parser, argparse.ArgumentParser) else None


def literal_flags(path: Path) -> set[str]:
    """Tier-2 accepted-flag set: every ``--flag`` string constant in the module's own AST."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and re.fullmatch(r"--[\w-]+", node.value)
    }


def argv_is_valid(parser: argparse.ArgumentParser, argv: tuple[str, ...]) -> bool:
    """Run the REAL parser. Its exit is the verdict; its noise is suppressed, not its answer."""
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            parser.parse_args(list(argv))
        except SystemExit:
            return False
        except Exception:
            return False
    return True


class Result(NamedTuple):
    violations: list[str]
    tier1: int
    tier2: int
    marked: int
    unknown: int


def check(invocations: list[Invocation], scripts: dict[str, Path]) -> Result:
    violations: list[str] = []
    tier1 = tier2 = marked = unknown = 0
    parsers: dict[str, argparse.ArgumentParser | None] = {}
    flagsets: dict[str, set[str]] = {}

    for inv in invocations:
        where = f"{inv.doc}:{inv.lineno}"
        rendered = f"{inv.script} {' '.join(inv.argv)}"
        path = scripts.get(inv.script)
        if path is None:
            unknown += 1
            violations.append(
                f"{where}: names {inv.script}, which is not in this directory"
            )
            continue
        if inv.script not in parsers:
            parsers[inv.script] = parser_of(path)
        parser = parsers[inv.script]

        if parser is not None:
            tier1 += 1
            valid = argv_is_valid(parser, inv.argv)
        else:
            tier2 += 1
            if inv.script not in flagsets:
                flagsets[inv.script] = literal_flags(path)
            accepted = flagsets[inv.script]
            bad = [
                t
                for t in inv.argv
                if t.startswith("-") and t.split("=", 1)[0] not in accepted
            ]
            valid = not bad

        if inv.marked_invalid:
            marked += 1
            if valid:
                violations.append(
                    f"{where}: marked {MARKER} but `{rendered}` parses cleanly -- "
                    "the marker is stale, or it is being used to silence a working command"
                )
        elif not valid:
            violations.append(
                f"{where}: `{rendered}` is not a runnable invocation of {inv.script}"
            )
    return Result(violations, tier1, tier2, marked, unknown)


# --------------------------------------------------------------------------
# self-test: every arm has a state in which it FIRES
# --------------------------------------------------------------------------
def self_test() -> int:
    failures: list[str] = []
    ran: list[str] = []

    def expect(label: str, got: object, want: object) -> None:
        ran.append(label)
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: got {got!r}")
        if not ok:
            failures.append(f"{label}: got {got!r}, want {want!r}")

    scripts = {p.name: p for p in HERE.glob("*.py")}
    ra = scripts["rule_audit.py"]
    parser = parser_of(ra)
    expect("tier1 accessor resolves rule_audit.py", parser is not None, True)
    assert parser is not None

    # A. the historical defect, replayed as a fixture, and its correct form.
    expect("A1 --json --md rejected", argv_is_valid(parser, ("--json", "--md")), False)
    expect(
        "A2 --json P --md P accepted",
        argv_is_valid(parser, ("--json", "a.json", "--md", "b.md")),
        True,
    )
    expect("A3 --self-test accepted", argv_is_valid(parser, ("--self-test",)), True)
    expect("A4 unknown flag rejected", argv_is_valid(parser, ("--nope",)), False)
    expect(
        "A5 --json without value rejected", argv_is_valid(parser, ("--json",)), False
    )

    # B. tier 2 discriminates a real flag from a typo of it.
    pr = scripts["r2_pathrefs.py"]
    expect("B1 r2_pathrefs is NOT tier 1", parser_of(pr) is None, True)
    flags = literal_flags(pr)
    expect("B2 --self-test is in the literal set", "--self-test" in flags, True)
    expect("B3 --self-tets is not", "--self-tets" in flags, False)

    # C. the extractor: receipt table, markdown table, prose, and a bare mention.
    table = "rule_audit.py --json --md           regenerated: byte-identical      rc=0"
    expect(
        "C1 receipt table truncates at the prose",
        extract(table, "d")[0].argv,
        ("--json", "--md"),
    )
    span = "| `rule_audit.py --json --md` | `SUCCESS`; byte-identical (`cmp`) | 0 |"
    expect(
        "C2 markdown code span extracted",
        extract(span, "d")[0].argv,
        ("--json", "--md"),
    )
    expect(
        "C3 prose sentence naming a script is not a command",
        extract("_r2_blobcheck.py EVIDENCE IS NOT a receipt", "d"),
        [],
    )
    expect(
        "C4 bare mention is not a command",
        extract("we re-ran `lazy_predict.py` and it held", "d"),
        [],
    )
    expect(
        "C5 value-taking flag keeps its path",
        extract("$ python docs/rule-audit/rule_audit.py --json out.json", "d")[0].argv,
        ("--json", "out.json"),
    )
    expect(
        "C6 sha value survives, trailing prose does not",
        extract("_r2_blobcheck.py --rev 0475e4a4   4 blobs, 0 CRLF", "d")[0].argv,
        ("--rev", "0475e4a4"),
    )
    # C7-C9 are regression arms for three detector faults this gate committed on its FIRST real
    # run. Each fired on real committed bytes before it was fixed, so each has a proven
    # broken state -- they are not decorative.
    expect(
        "C7 a leading underscore is part of the name, not emphasis",
        extract("| `_r2_blobcheck.py --rev 7770f6e8` | 6 blobs |", "d")[0].script,
        "_r2_blobcheck.py",
    )
    expect(
        "C8 <placeholder> is a value, so the prescribed form is runnable",
        argv_is_valid(
            parser, extract("`rule_audit.py --json <path> --md <path>`", "d")[0].argv
        ),
        True,
    )
    both_styles = (
        "| `rule_audit.py --self-test` | ok |   rule_audit.py --self-test   ok"
    )
    expect(
        "C9 one line, two candidate styles, ONE invocation",
        len(extract(both_styles, "d")),
        1,
    )
    # C10/C11: the commit-message template writes the tool WITHOUT ``.py``. C10 fires only if
    # the extensionless form is resolved; C11 is the guard that resolution cannot promote an
    # arbitrary prose word into a command.
    expect(
        "C10 extensionless tool name resolves to the real script",
        extract("  rule_audit --json --md   regenerated   rc=0", "d")[0],
        Invocation("d", 1, "rule_audit.py", ("--json", "--md"), False),
    )
    expect(
        "C11 an unknown bare word is prose, not a command",
        extract("  regenerated --json --md   whatever", "d"),
        [],
    )

    # D. both-states on the gate itself, on synthetic docs.
    broken = check(extract(table, "broken.md"), scripts)
    expect("D1 gate FIRES on the unmarked broken receipt", len(broken.violations), 1)
    fixed = check(
        extract(
            "rule_audit.py --json out.json --md out.md    byte-identical    rc=0",
            "fixed.md",
        ),
        scripts,
    )
    expect("D2 gate SILENT on the corrected receipt", fixed.violations, [])
    quoted = check(extract(f"{table} {MARKER}", "quoted.md"), scripts)
    expect("D3 gate SILENT on a marked quotation", quoted.violations, [])
    stale = check(
        extract(f"rule_audit.py --self-test  ok {MARKER}", "stale.md"), scripts
    )
    expect("D4 gate FIRES on a marker that no longer applies", len(stale.violations), 1)
    missing = check(extract("no_such_script.py --self-test  ok", "missing.md"), scripts)
    expect("D5 gate FIRES on a script that is not here", len(missing.violations), 1)

    # E. fail-closed: nothing scanned must never read as agreement.
    expect("E1 empty corpus extracts nothing", extract("", "empty.md"), [])
    expect("E2 main() fails closed on an empty corpus", run([]), 1)

    print("")
    if failures:
        for line in failures:
            print(f"  FAILED-CONTROL {line}")
        print(f"FAILED:r4_receipt_argv_gate-self-test {len(failures)}")
        return 1
    # COUNTED, never written down. Round 1 of this lane shipped "20 detector controls" against a
    # measured 17 for exactly the reason a literal here would rot: nothing connected the sentence
    # to the arms. ``len(ran)`` cannot disagree with the arms that ran.
    print(
        f"SUCCESS:r4_receipt_argv_gate-self-test all {len(ran)} gate-level states passed"
    )
    return 0


def run(docs: list[Path]) -> int:
    scripts = {p.name: p for p in HERE.glob("*.py")}
    if not scripts:
        print("FAILED:r4_receipt_argv_gate no scripts in this directory -- fail closed")
        return 1
    invocations: list[Invocation] = []
    for doc in docs:
        invocations += extract(doc.read_text(encoding="utf-8"), doc.name)

    # "file(s)", not "markdown file(s)": the corpus is markdown PLUS the commit-message
    # templates, and a label that names only half of what it counted is the same species of
    # wrong sentence this gate exists to catch.
    print(f"scanned {len(docs)} corpus file(s), {len(scripts)} script(s)")
    if not docs or not invocations:
        print(
            "FAILED:r4_receipt_argv_gate zero invocations extracted -- the extractor "
            "found nothing, which is a broken scan, not agreement"
        )
        return 1

    result = check(invocations, scripts)
    print(
        f"invocations: {len(invocations)}  tier1(real parser)={result.tier1}  "
        f"tier2(flag literals)={result.tier2}  marked-invalid={result.marked}"
    )
    if result.tier1 == 0:
        print(
            "FAILED:r4_receipt_argv_gate no tier-1 validation ran -- the parser path is "
            "inert, so a passing verdict would prove nothing"
        )
        return 1
    for inv in invocations:
        tag = "quoted" if inv.marked_invalid else "live  "
        print(f"  {tag} {inv.doc}:{inv.lineno}  {inv.script} {' '.join(inv.argv)}")
    print("")
    if result.violations:
        for line in result.violations:
            print(f"  VIOLATION {line}")
        print(f"FAILED:r4_receipt_argv_gate {len(result.violations)} violation(s)")
        return 1
    print(
        f"SUCCESS:r4_receipt_argv_gate {len(invocations)} documented invocation(s) parse "
        f"against the tool they name ({result.marked} quoted-as-broken, and each verified "
        "to REALLY be broken)"
    )
    return 0


def corpus() -> list[Path]:
    """Markdown AND the commit-message templates.

    The third site of the round-3 false receipt was a COMMIT MESSAGE -- unreachable and
    unfixable once written -- and its template ``_r3_commitmsg.txt`` is still on disk, ready to
    be re-emitted verbatim into the next commit. A gate that only reads ``*.md`` would watch the
    two doc sites and leave the one that writes permanent history uncovered.
    """
    return sorted(HERE.glob("*.md")) + sorted(HERE.glob("*commitmsg*.txt"))


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    return run(corpus())


if __name__ == "__main__":
    raise SystemExit(main())
