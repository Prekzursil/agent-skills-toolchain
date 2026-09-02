"""R2 gate: every control-count claim in the rule-audit prose must equal the tool's own output.

The one CONFIRMED defect of round 1 was an OVERCLAIM, not broken code: the artifact asserted
"20 detector controls" in three places (RULE-AUDIT.md :26, :401, :502) and quoted a tool line
`SUCCESS: all controls passed (20)` that the tool never printed. The measured count was 17, and
the artifact's own hand-written breakdown summed to something else again. Nothing mechanical
connected the sentence to the measurement, so the sentence was free to drift.

This gate closes that hole:

    runtime N  = parsed from `rule_audit.py --self-test` stdout (the tool prints its own count)
    static  N  = AST walk of self_test(), counting check() call sites
    groups  N  = the tool's own `CONTROL-GROUPS: ... TOTAL=n` line, whose per-group counts must
                 sum to n -- this is what catches a breakdown that disagrees with its headline
    prose   N  = every control-count claim in docs/rule-audit/*.md

All four must agree, and the verbatim CONTROL-GROUPS line must appear in RULE-AUDIT.md so the
artifact's inventory is a quoted measurement rather than a hand-maintained table.

USE-VS-MENTION. A doc legitimately QUOTES the refuted "20" while reporting that it was wrong;
flagging that would be the mislabel this program keeps making. Exemption is an explicit FIELD,
not a guess about prose: a line carrying the literal marker ``<!--count-historical-->`` is
skipped. Guessing from refutation cues was rejected -- a regex over prose is what mislabels.

Fails closed when the prose scan finds no NON-exempt claim at all: a gate that matches nothing
measures nothing, and a marker that silenced every line would otherwise read as a pass.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "rule_audit.py"
MARKER = "<!--count-historical-->"

# Each pattern captures ONE integer that is a claim about how many controls exist.
CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"all controls passed \((\d+)\)"),
    re.compile(r"(\d+)\s+detector[ -]controls?\b", re.I),
    re.compile(r"(\d+)\s+detector[ -]control assertions?\b", re.I),
    re.compile(r"[Dd]etector controls?\s*(?:—|--|-)\s*(\d+)"),
    re.compile(r"(\d+)\s+self-test controls?\b", re.I),
)


def normalise(line: str) -> str:
    """Strip markdown emphasis before matching.

    Measured on the first version of this gate: ``**17** detector-control assertions`` did NOT
    match, because the bold markers sit between the digits and the noun. A gate a ``**`` defeats
    is the weak-detector shape this program keeps re-learning, so emphasis is removed first.
    """
    return re.sub(r"[*`_]+", "", line)


def claims_in(text: str) -> list[tuple[int, int, bool]]:
    """Return ``(line_number, claimed_count, exempt)`` for every control-count claim."""
    hits: list[tuple[int, int, bool]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        exempt = MARKER in raw
        line = normalise(raw)
        seen: set[int] = set()  # two patterns can match the same number on one line
        for pattern in CLAIM_PATTERNS:
            for match in pattern.finditer(line):
                value = int(match.group(1))
                if value in seen:
                    continue
                seen.add(value)
                hits.append((lineno, value, exempt))
    return hits


def self_test_stdout() -> str | None:
    proc = subprocess.run(
        [sys.executable, str(SRC), "--self-test"],
        capture_output=True,
        text=True,
        timeout=900,
    )
    if proc.returncode != 0:
        print(f"FAILED:r2_control_count_gate --self-test exited {proc.returncode}")
        return None
    return proc.stdout


def static_count() -> int:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "self_test":
            return sum(
                1
                for sub in ast.walk(node)
                if isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Name)
                and sub.func.id == "check"
            )
    return -1


def run_controls(expected: int) -> bool:
    """Both-states proof that the extractor separates a real claim from a marked mention."""
    right = f"`--self-test` runs **{expected}** detector controls, all passing."
    wrong = f"`--self-test` runs **{expected + 3}** detector controls, all passing."
    mention = f'round 1 asserted "{expected + 3} detector controls". {MARKER}'
    silent = "This paragraph makes no numeric claim about controls at all."
    got_right = [(c, e) for _, c, e in claims_in(right)]
    got_wrong = [(c, e) for _, c, e in claims_in(wrong)]
    got_mention = [(c, e) for _, c, e in claims_in(mention)]
    got_silent = claims_in(silent)
    ok = (
        got_right == [(expected, False)]
        and got_wrong == [(expected + 3, False)]
        and got_mention == [(expected + 3, True)]
        and got_silent == []
    )
    print(f"  control  live-right {got_right}   live-wrong {got_wrong}")
    print(f"  control  marked-mention {got_mention}   no-claim {got_silent}")
    print(f"  extractor separates use / mention / silence: {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    stdout = self_test_stdout()
    if stdout is None:
        return 1
    total_match = re.search(r"all controls passed \((\d+)\)", stdout)
    groups_match = re.search(r"CONTROL-GROUPS: (.+?) TOTAL=(\d+)", stdout)
    if not total_match or not groups_match:
        print(
            "FAILED:r2_control_count_gate tool printed no count/inventory -- gate inert"
        )
        return 1

    runtime = int(total_match.group(1))
    groups_line = groups_match.group(0)
    per_group = [int(v) for v in re.findall(r"=(\d+)\b", groups_match.group(1))]
    group_total = int(groups_match.group(2))
    static = static_count()

    print(f"runtime count (tool stdout)  = {runtime}")
    print(f"static  count (AST walk)     = {static}")
    print(f"groups  line (tool stdout)   = {groups_line}")
    print(f"groups  sum                  = {sum(per_group)} (TOTAL={group_total})")

    if not run_controls(runtime):
        print(
            "FAILED:r2_control_count_gate the extractor failed its own both-states control"
        )
        return 1

    bad: list[str] = []
    if sum(per_group) != group_total:
        bad.append(f"per-group sum {sum(per_group)} != TOTAL {group_total}")
    if group_total != runtime:
        bad.append(f"TOTAL {group_total} != reported count {runtime}")
    if static != runtime:
        bad.append(f"AST count {static} != reported count {runtime}")

    audit = HERE / "RULE-AUDIT.md"
    if audit.exists() and groups_line not in audit.read_text(encoding="utf-8"):
        bad.append(
            f"RULE-AUDIT.md does not quote the tool line verbatim: {groups_line!r}"
        )

    docs = sorted(HERE.glob("*.md"))
    if not docs:
        print("FAILED:r2_control_count_gate no markdown scanned -- fail closed")
        return 1

    live_claims = 0
    exempt_claims = 0
    for doc in docs:
        for lineno, claimed, exempt in claims_in(doc.read_text(encoding="utf-8")):
            if exempt:
                exempt_claims += 1
                print(
                    f"  skip {doc.name}:{lineno} claims {claimed} (marked historical)"
                )
                continue
            live_claims += 1
            print(
                f"  {'ok ' if claimed == runtime else 'BAD'} {doc.name}:{lineno} claims {claimed}"
            )
            if claimed != runtime:
                bad.append(
                    f"{doc.name}:{lineno} claims {claimed}, tool reports {runtime}"
                )

    print(
        f"scanned {len(docs)} markdown file(s): {live_claims} live claim(s), "
        f"{exempt_claims} marked historical"
    )
    if live_claims == 0:
        print(
            "FAILED:r2_control_count_gate zero live claims -- extractor found nothing, fail closed"
        )
        return 1

    print("")
    if bad:
        for line in bad:
            print(f"  MISMATCH {line}")
        print(f"FAILED:r2_control_count_gate {len(bad)} mismatch(es)")
        return 1
    print(
        f"SUCCESS:r2_control_count_gate {live_claims} live prose claim(s) == tool {runtime} "
        f"== AST {static} == group sum {sum(per_group)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
