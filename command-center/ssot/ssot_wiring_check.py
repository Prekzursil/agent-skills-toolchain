"""SSOT wiring check — is the SSOT lane's output actually REACHABLE, or just committed?

WHY THIS FILE EXISTS. The SSOT lane produced two artifacts and wired neither of them:

  * ``docs/ssot/SSOT-CLONE-INVENTORY.md`` -- 25 checkouts classified, and in sec.5 the
    one-sentence rule a future agent is supposed to obey. Nothing loads ``docs/``.
  * ``command-center/ssot/ssot_drift_gate.py`` -- a gate that fires correctly and that
    nothing invokes. Its own round-1 report lists "the drift gate is a script, not yet
    enforced" as the highest-value follow-up.

A rule nobody reads and a gate nobody runs are indistinguishable from not having done the
work. This checker is what makes the wiring mechanical: each code below is one wire, and
``ci/tests/test_ssot_wiring.py`` proves every one of them fires when that wire is cut.

WHY ``CLAUDE.md`` IS THE WIRE AND ``rules/common/`` IS NOT. The obvious home for a standing
rule is an always-on file under ``rules/common/``. It was measured and REJECTED: the live
tree an agent actually reads (``~/.claude/rules/common/harness-vcs-hygiene.md``, 2149 bytes)
is 993 bytes BEHIND its repo source (3142 bytes), so a repo-only rule edit would not reach a
session until somebody runs a deploy. Writing there would have produced a wire that looks
connected and is not. ``CLAUDE.md`` at the repo root is git-tracked AND injected into any
session whose cwd is this checkout, with no deploy hop in between -- verified by observing it
in a live session's own context. That is why the rule text lives there.

Exit codes:  0 all wires intact - 1 one or more wires cut - 3 checker misconfigured
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re

CLAUDE_MD = "CLAUDE.md"
INVENTORY = "docs/ssot/SSOT-CLONE-INVENTORY.md"
WORKFLOW = ".github/workflows/skill-dual-write.yml"
SUITE = "ci/tests/test_ssot_wiring.py"
# The machine-readable classification the block points at. W3 resolves only `.md`/`.py`
# paths, so before W7 nothing required this artifact to exist at all -- the block named
# the SSOT of the whole lane and no wire held it.
POPULATION_JSON = "command-center/ssot/population-classified.json"

# The marker-delimited block in CLAUDE.md that carries the wire. Marker-delimited rather
# than heading-matched so a heading reword cannot silently orphan the section.
BLOCK_START = "<!-- SSOT-WIRE:start -->"
BLOCK_END = "<!-- SSOT-WIRE:end -->"

# The heading in the inventory whose blockquote is the canonical rule sentence.
RULE_HEADING = "## 5. Q4"

# Every code this checker can emit. `test_every_invariant_has_a_red_proof` fails if a code
# is added here without a paired mutation, so a code nobody has seen fire cannot ship.
CHECKS: tuple[tuple[str, str], ...] = (
    ("W1-claude-md-no-ssot-block", "CLAUDE.md has no SSOT-WIRE block"),
    ("W2-rule-sentence-drift", "CLAUDE.md rule sentence != inventory sec.5 sentence"),
    ("W3-referenced-path-missing", "a path named inside the block does not exist"),
    ("W4-gate-unreferenced", "the block does not name the drift gate"),
    ("W5-gate-not-runnable", "the gate has no working __main__ entry point"),
    ("W6-ci-suite-unwired", "no workflow step runs this suite"),
    ("W7-count-drift", "CLAUDE.md counts != population-classified.json"),
)

# --- W7 ----------------------------------------------------------------------------------
# WHY W7 EXISTS. W1-W6 gate the rule's TEXT. They say nothing about the NUMBERS in the same
# block, and the numbers are what a future agent actually acts on: whether a checkout may be
# retired depends on "132 hold unpushed commits" and "5 have no remote", not on the rule
# sentence. This lane restated its headline count four times -- 25, then 170, then 177, then
# 178 -- and round 4's central defect was an arithmetic that did not close (9 + 168 = 177
# against a population of 178) which every reviewer read past because nothing added it up.
# W7 makes that mechanical: an exact algorithm, not a judgement call.

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

# Each claim is (human label, pattern, measured keys aligned to the capture groups).
# Anchored on the specific phrase rather than "every integer in the block" on purpose: the
# block deliberately PRESERVES refuted figures (177, 25, 170) inside blockquotes so a dead
# end is not re-walked, and a scanner that treated those as live claims would fire on
# correct content. Counting the field, not the document.
COUNT_CLAIMS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "population / object stores",
        r"\*\*(\d+)\s+checkouts\s+across\s+(\d+)\s+object\s+stores\*\*",
        ("population", "distinct_object_stores"),
    ),
    ("linked worktrees", r"(\d+)\s+linked\s+worktrees", ("linked_worktrees",)),
    ("independent clones", r"(\d+)\s+independent\s+clones", ("independent_clones",)),
    ("severed worktree", r"\*\*(\d+)\s+severed\s+worktree\*\*", ("severed_worktrees",)),
    (
        "kind arithmetic",
        r"(\d+)\s*\+\s*(\d+)\s*\+\s*(\d+)\s*=\s*(\d+)",
        ("linked_worktrees", "independent_clones", "severed_worktrees", "population"),
    ),
    (
        "uncommitted-work surface / no remote",
        r"\*\*(\d+)\s+of\s+them\s+hold\s+unpushed\s+commits[^*]*?;"
        r"\s*(\d+)\s+have\s+no\s+remote\s+at\s+all\.\*\*",
        ("with_unique_or_uncommitted", "no_remote"),
    ),
    (
        "named by live harness config",
        r"([A-Za-z]+|\d+)\s+are\s+named\s+by\s+live\s+harness\s+config",
        ("referenced_by_exec_config",),
    ),
)


def _live_prose(body: str) -> str:
    """Drop blockquote lines before matching a live numeric claim.

    The block keeps every superseded figure as a `>` quoted REFUTED note rather than
    deleting it. Those numbers are MENTIONS of a retired measurement, not assertions about
    the tree, and a gate that could not tell the two apart would go red on the honesty.
    """
    return "\n".join(ln for ln in body.splitlines() if not ln.lstrip().startswith(">"))


def _as_int(token: str) -> int | None:
    return int(token) if token.isdigit() else NUMBER_WORDS.get(token.lower())


def _measured(pc: dict) -> tuple[dict[str, int | None], list[str]]:
    """Measured counts plus any way the artifact disagrees with ITSELF.

    Self-consistency is checked first and separately. Comparing prose against an artifact
    whose own accounting does not close would certify the prose against a broken ruler.
    """

    def _len(v: object) -> int | None:
        return len(v) if isinstance(v, list) else None

    arith = pc.get("kind_arithmetic") or {}
    vals: dict[str, int | None] = {
        "population": pc.get("population"),
        "distinct_object_stores": pc.get("distinct_object_stores"),
        "linked_worktrees": arith.get("linked_worktrees"),
        "independent_clones": arith.get("independent_clones"),
        "severed_worktrees": arith.get("severed_worktrees"),
        "with_unique_or_uncommitted": _len(pc.get("with_unique_or_uncommitted")),
        "no_remote": _len(pc.get("no_remote")),
        "referenced_by_exec_config": _len(pc.get("referenced_by_exec_config")),
    }

    internal: list[str] = []
    rows = pc.get("rows")
    if not isinstance(rows, list):
        internal.append("`rows` is not a list")
    elif len(rows) != pc.get("population"):
        internal.append(f"len(rows)={len(rows)} != population={pc.get('population')}")
    if arith.get("closes") is not True:
        internal.append("kind_arithmetic.closes is not true")
    terms = [
        arith.get(k)
        for k in (
            "linked_worktrees",
            "independent_clones",
            "severed_worktrees",
            "unresolved",
        )
    ]
    if all(isinstance(t, int) for t in terms) and sum(terms) != pc.get("on_disk"):
        internal.append(
            f"kind_arithmetic terms sum to {sum(terms)} != on_disk {pc.get('on_disk')}"
        )
    if _len(pc.get("severed_worktrees")) != arith.get("severed_worktrees"):
        internal.append("severed_worktrees list length != its kind_arithmetic term")
    return vals, internal


def _check_counts(root: pathlib.Path, body: str) -> list[str]:
    """Return W7 detail lines. Empty means every live count matches the measurement."""
    path = root / POPULATION_JSON
    if not path.exists():
        return [f"{POPULATION_JSON} does not exist; the block's counts rest on nothing"]
    try:
        pc = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        return [f"{POPULATION_JSON} is unreadable: {exc}"]
    if not isinstance(pc, dict):
        return [f"{POPULATION_JSON} is not an object"]

    vals, internal = _measured(pc)
    details = [f"{POPULATION_JSON} disagrees with itself: {d}" for d in internal]
    if not body:
        return details

    prose = _live_prose(body)
    for label, pattern, keys in COUNT_CLAIMS:
        found = list(re.finditer(pattern, prose))
        if not found:
            details.append(
                f"the sentence carrying '{label}' is gone from the block, "
                "so a future agent reads no number for it"
            )
            continue
        # Every occurrence must agree: a second live sentence repeating a stale figure is
        # the exact drift this check exists to catch.
        for m in found:
            for token, key in zip(m.groups(), keys):
                claimed = _as_int(token)
                measured = vals.get(key)
                if claimed != measured:
                    details.append(
                        f"'{label}': block says {token} for {key}, measured {measured}"
                    )
    return details


def _canon_md(text: str) -> str:
    """Normalise a markdown sentence so wrapping/emphasis cannot fake a mismatch."""
    text = text.replace("`", "").replace("*", "").replace(">", " ")
    return re.sub(r"\s+", " ", text).strip()


def _block(claude_md: str) -> str | None:
    """Return the SSOT-WIRE block body, or None when the markers are absent."""
    if BLOCK_START not in claude_md or BLOCK_END not in claude_md:
        return None
    body = claude_md.split(BLOCK_START, 1)[1].split(BLOCK_END, 1)[0]
    return body


def _inventory_rule(inventory: str) -> str | None:
    """Return the canonical rule sentence: the first blockquote after the sec.5 heading."""
    if RULE_HEADING not in inventory:
        return None
    tail = inventory.split(RULE_HEADING, 1)[1]
    quoted: list[str] = []
    for line in tail.splitlines()[1:]:
        stripped = line.strip()
        if stripped.startswith(">"):
            quoted.append(stripped)
        elif quoted:
            break
    return _canon_md(" ".join(quoted)) if quoted else None


def _has_main_entry(source: str) -> bool:
    """True when the module really executes something as a script.

    A `python <script>` gate that defines main() but never calls it exits 0 forever --
    the no-op-gate class in rules/common/ci-hygiene.md sec.1. Parsing the AST rather than
    grepping for the string keeps a mention inside a docstring from counting as a wire.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare) or not isinstance(test.left, ast.Name):
            continue
        if test.left.id != "__name__":
            continue
        for comparator in test.comparators:
            if isinstance(comparator, ast.Constant) and comparator.value == "__main__":
                return True
    return False


def _runs_suite(workflow: str) -> bool:
    """True when some step in the workflow actually collects this suite.

    Either shape counts: the explicit filename, or a bare `ci/tests` directory argument
    to pytest. `ci/tests/` appearing only inside a comment must NOT count, so comment
    lines are stripped before matching -- otherwise the prose explaining the wire would
    satisfy the check for it (use-vs-mention, in the instrument).
    """
    live = []
    for line in workflow.splitlines():
        code = line.split("#", 1)[0]
        if code.strip():
            live.append(code)
    body = "\n".join(live)
    if SUITE in body:
        return True
    return bool(re.search(r"pytest[^\n]*(?<![\w/])ci/tests(?![\w/])", body))


def run(root: pathlib.Path) -> list[tuple[str, str]]:
    """Return the list of (code, detail) failures. Empty means every wire is intact."""
    fails: list[tuple[str, str]] = []

    claude_path = root / CLAUDE_MD
    inv_path = root / INVENTORY
    wf_path = root / WORKFLOW

    claude_md = claude_path.read_text(encoding="utf-8") if claude_path.exists() else ""
    body = _block(claude_md)
    if body is None:
        fails.append((CHECKS[0][0], f"{CLAUDE_MD} is missing {BLOCK_START}"))
        # Every remaining block-scoped code reads `body`; with no block there is nothing
        # to read, so report the one real defect instead of six derived ones.
        body = ""

    # --- W2: the rule sentence in CLAUDE.md must match the inventory verbatim ---------
    inventory = inv_path.read_text(encoding="utf-8") if inv_path.exists() else ""
    canonical = _inventory_rule(inventory)
    if body:
        if canonical is None:
            fails.append(
                (
                    CHECKS[1][0],
                    f"{INVENTORY} has no rule blockquote under {RULE_HEADING}",
                )
            )
        elif canonical not in _canon_md(body):
            fails.append(
                (
                    CHECKS[1][0],
                    "the CLAUDE.md sentence is not the inventory sec.5 sentence",
                )
            )

    # --- W3: every repo path named inside the block must exist ------------------------
    # Scan INSIDE each backtick span rather than requiring the whole span to be a path.
    # Measured on the first run of this checker: the anchored form missed
    # `python command-center/ssot/ssot_drift_gate.py` -- i.e. the single commonest way to
    # name a gate, an invocation -- and W4 fired against a CLAUDE.md that did reference it.
    # Only code spans count, so a path merely discussed in prose is still a mention, not a
    # reference.
    spans = re.findall(r"`([^`]+)`", body)
    named = sorted(
        {
            m
            for span in spans
            for m in re.findall(r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:md|py)", span)
        }
    )
    for rel in named:
        if not (root / rel).exists():
            fails.append(
                (CHECKS[2][0], f"{CLAUDE_MD} names {rel}, which does not exist")
            )

    # --- W4/W5: the gate must be named, and must actually be runnable -----------------
    gates = [p for p in named if p.endswith("ssot_drift_gate.py")]
    if body and not gates:
        fails.append((CHECKS[3][0], f"{CLAUDE_MD} block does not name the drift gate"))
    for rel in gates:
        gate = root / rel
        if not gate.exists():
            continue  # already reported as W3; do not double-count one broken wire
        if not _has_main_entry(gate.read_text(encoding="utf-8")):
            fails.append((CHECKS[4][0], f"{rel} has no working __main__ entry point"))

    # --- W6: something in CI must actually run this suite -----------------------------
    workflow = wf_path.read_text(encoding="utf-8") if wf_path.exists() else ""
    if not _runs_suite(workflow):
        fails.append(
            (CHECKS[5][0], f"{WORKFLOW} runs neither {SUITE} nor `pytest ci/tests`")
        )

    # --- W7: the block's COUNTS must match the artifact they claim to summarise -------
    for detail in _check_counts(root, body):
        fails.append((CHECKS[6][0], detail))

    return fails


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repo root to check")
    ap.add_argument("--json", dest="as_json", action="store_true")
    args = ap.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    if not (root / CLAUDE_MD).exists() and not (root / INVENTORY).exists():
        # Fail CLOSED: an empty or wrong --root must never read as "all wires intact".
        print(f"FAILED:ssot-wiring-check {root} does not look like this repo")
        return 3

    fails = run(root)
    if args.as_json:
        print(json.dumps({"root": str(root), "failures": fails}, indent=2))
    else:
        print(f"=== SSOT wiring check ({len(CHECKS)} wires) ===")
        for code, desc in CHECKS:
            hit = [d for c, d in fails if c == code]
            mark = "CUT " if hit else " ok "
            print(f"  [{mark}] {code:28s} {desc}")
            for detail in hit:
                print(f"            - {detail}")

    if fails:
        print(f"FAILED:ssot-wiring-check cut={len(fails)}")
        return 1
    print(f"SUCCESS:ssot-wiring-check wires={len(CHECKS)} all intact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
