"""Doc-vs-code contracts for the rule/command surface (cluster C26).

Five adjudicated findings all had the same shape: a rule or command file states a
contract that the code, a sibling rule, or the language runtime does not honour.  Prose
has no compiler, so each is pinned here against the OTHER side of the contract -- the
shipped hook source, the sibling rule text, or a measured runtime behaviour -- rather
than against a snapshot of itself.  A test that only re-reads the sentence it is
guarding proves nothing.

Findings pinned:
  D-a003  rules/common/static-analyzer.md recommended a bare
          ``gather(..., return_exceptions=True)``, which swallows every unexpected
          failure and contradicts rules/common/coding-style.md "Never silently swallow
          errors".  Measured on py3.14.6: the bare form let RuntimeError("cleanup
          failed") vanish and reported a successful shutdown.
  D-a028  rules/typescript/hooks.md described PostToolUse Prettier/tsc/console.log
          coverage without disclosing that the shipped per-edit checker deliberately
          SKIPS .ts/.tsx.  Measured: a .ts fixture with 18 console.log calls and a
          syntax error returns exit 0 and empty output.
  D-a038  rules/web/hooks.md shipped a PreToolUse recipe that ``process.exit(2)``s on
          any Write over 800 lines.  AGENTS.md section 6 reserves exit 2 for
          irreversible/dangerous operations; measured, an 801-line generated parser was
          denied purely for length.
  D-a046  rules/perl/patterns.md module examples used subroutine signatures without
          ``use v5.36``.  Measured on perl 5.38.2: copying that example verbatim dies
          with "Illegal character in prototype" + exit 255.
  D-a127  commands/context-budget.md hard-coded a 200K denominator, overstating pressure
          5x in a 1M session (100K overhead reads as 50.0% instead of 10.0%).
  D-a021  commands/model-route.md treated the router tier as authoritative, while
          rules/common/performance.md defaults every substantive subagent to Opus.
          Measured at this commit with lizard present, the router returns ``haiku`` for
          ci/emit_hook_manifest.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Root docs whose agent-self/config copy is a BYTE mirror.  Scoped deliberately: repo-wide
# rules parity does NOT hold (measured at 27fb388 -- rules/common/performance.md and
# rules/common/hooks.md both differ from their agent-self copies), so asserting it
# globally would be a false invariant.  These five are byte-identical and must stay so,
# because agent-self/config is the committed deploy surface for the live ~/.claude.
MIRRORED_DOCS = (
    "rules/perl/patterns.md",
    "rules/web/hooks.md",
    "rules/typescript/hooks.md",
    "commands/context-budget.md",
    "commands/model-route.md",
)


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _perl_blocks(text: str) -> list[str]:
    return re.findall(r"```perl\n(.*?)```", text, re.S)


def _json_block(text: str, after_heading: str) -> str:
    match = re.search(
        re.escape(after_heading) + r".*?```json\n(\{.*?\n\})\n```", text, re.S
    )
    assert match, f"no json block found under {after_heading!r}"
    return match.group(1)


# ── D-a003: gather(return_exceptions=True) may not be recommended bare ──────────


def test_static_analyzer_gather_recipe_requires_reraise():
    """The sibling rule forbids silently swallowing errors; this one must not teach it."""

    analyzer = _read("rules/common/static-analyzer.md")
    assert "return_exceptions=True" in analyzer, (
        "anchor moved -- this test guards the return_exceptions recipe"
    )
    assert "Never silently swallow errors" in _read("rules/common/coding-style.md"), (
        "the sibling rule this one must not contradict has moved"
    )
    assert "raise outcome" in analyzer, (
        "static-analyzer.md recommends gather(..., return_exceptions=True) without "
        "showing the caller inspecting the results and re-raising what it did not "
        "expect -- that turns an unrelated RuntimeError into a silent success and "
        "contradicts coding-style.md 'Never silently swallow errors'"
    )


# ── D-a028: the TS rule must disclose what the shipped hook actually skips ──────


def test_typescript_hook_rule_discloses_the_shipped_ts_skip():
    """Cross-checked against the hook SOURCE, not against the rule's own wording."""

    check_src = _read("hooks/per-edit-check/check.py")
    skips_ts = 'if ext in (".ts", ".tsx"):\n        return [], False' in check_src
    assert skips_ts, (
        "hooks/per-edit-check/check.py no longer skips .ts/.tsx -- if the hook gained "
        "real TypeScript coverage, update rules/typescript/hooks.md and this test "
        "together"
    )

    rule = _read("rules/typescript/hooks.md")
    assert "per-edit-check" in rule, (
        "rules/typescript/hooks.md must name the hook that actually runs on an edit"
    )
    assert re.search(r"skips?\s+\*?\*?`?\.ts`?", rule), (
        "rules/typescript/hooks.md promises Prettier/tsc/console.log coverage without "
        "disclosing that the shipped per-edit checker returns 'no issues' for .ts/.tsx"
    )


# ── D-a038: the file-size guard must inject, never exit 2 ───────────────────────


def test_web_file_size_guard_injects_instead_of_blocking():
    """AGENTS.md section 6: exit 2 is for irreversible/dangerous only."""

    hooks_rule = _read("rules/web/hooks.md")
    block = _json_block(hooks_rule, "### Guard File Size")
    command = block

    assert "process.exit(2)" not in command, (
        "the Guard File Size recipe blocks with exit 2; file length is neither "
        "irreversible nor dangerous, so AGENTS.md section 6 requires exit 0 plus "
        "additionalContext (an 801-line generated parser is legitimate work)"
    )
    assert "additionalContext" in command, (
        "the Guard File Size recipe must inject additionalContext instead of blocking"
    )
    assert "800" in command, "anchor moved -- this test guards the 800-line recipe"


# ── the same recipe must also be structurally capable of running at all ─────────


def test_web_hook_examples_use_the_nested_typed_handler():
    """An inject-only recipe that never fires is not an improvement over a blocker.

    A hook entry has three levels -- event -> matcher group -> ``hooks: [{"type":
    "command", ...}]``.  A bare ``command`` on the matcher group is not a recognized
    handler: the entry is invalid and the command never spawns, silently.  Verified
    against the two in-repo emitters rather than against a spec summary:
    ``agent-self/harness/registration.py:82-102`` (_command_group) and ``:151-169``
    (build_hooks) both write the nested form, and ``hooks/hooks.json`` -- the hooks this
    repo actually ships -- uses it too.

    Scoped to rules/web/hooks.md on purpose.  Measured by PARSING every ```json fence in
    every ``rules/**/hooks.md`` and ``agent-self/config/rules/**/hooks.md`` on the base
    commit (not by grepping): this file and its deploy mirror hold 6 flat groups each and
    every other hooks doc holds 0.  So this file is the whole population, and a repo-wide
    version of the check adds surface without adding coverage.
    """

    text = _read("rules/web/hooks.md")
    blocks = [json.loads(m) for m in re.findall(r"```json\n(.*?)```", text, re.S)]
    assert blocks, "anchor moved -- no json examples found in rules/web/hooks.md"

    problems: list[str] = []
    for doc in blocks:
        for event, groups in (doc.get("hooks") or {}).items():
            for idx, group in enumerate(groups):
                where = f"{event}[{idx}]"
                if "command" in group:
                    problems.append(f"{where}: bare 'command' on the matcher group")
                    continue
                handlers = group.get("hooks")
                if not isinstance(handlers, list) or not handlers:
                    problems.append(f"{where}: no 'hooks' handler array")
                    continue
                for h_idx, handler in enumerate(handlers):
                    if handler.get("type") != "command":
                        problems.append(f"{where}.hooks[{h_idx}]: missing type=command")
                    elif not handler.get("command"):
                        problems.append(f"{where}.hooks[{h_idx}]: empty command")
    assert not problems, problems


def test_web_hook_examples_do_not_reference_a_nonexistent_shell_variable():
    """Hooks read JSON on stdin; nothing exports ``$FILE_PATH``, so a command
    interpolating it runs against an empty path.  Scan the FENCES, not the prose --
    the doc legitimately MENTIONS the token while telling you not to use it.
    """

    fences = re.findall(r"```json\n(.*?)```", _read("rules/web/hooks.md"), re.S)
    offenders = [f for f in fences if "$FILE_PATH" in f]
    assert not offenders, f"{len(offenders)} example(s) interpolate $FILE_PATH"


# ── D-a046: perl module examples must enable the signature feature bundle ───────


@pytest.mark.parametrize("index", range(2))
def test_perl_module_examples_enable_v5_36(index: int):
    """A ``package``-shaped example is copy-pasteable; without v5.36 it will not load."""

    blocks = [
        b for b in _perl_blocks(_read("rules/perl/patterns.md")) if "package " in b
    ]
    assert len(blocks) > index, (
        f"expected at least {index + 1} package-shaped perl examples; anchor moved"
    )
    block = blocks[index]
    assert "use v5.36" in block, (
        "rules/perl/coding-style.md says to ALWAYS `use v5.36`, and without it a "
        "`sub name ($self, $id)` signature parses as a malformed prototype "
        "(measured perl 5.38.2: exit 255). Example:\n" + block
    )


# ── D-a127: the context-budget denominator may not be hard-coded ────────────────


def test_context_budget_does_not_hardcode_the_window():
    budget = _read("commands/context-budget.md")
    assert "Assume a 200K context window" not in budget, (
        "commands/context-budget.md hard-codes a 200K denominator; in a 1M session "
        "that overstates pressure 5x (100,000 tokens of overhead reads as 50.0% "
        "instead of 10.0%) and manufactures removal recommendations"
    )
    assert "autoCompactWindow" in budget, (
        "the command must say where to READ the real window from, not merely drop the "
        "old assumption"
    )


# ── D-a021: the router tier may not under-route substantive work ────────────────


def test_model_route_carries_the_opus_floor():
    performance = _read("rules/common/performance.md")
    assert "NOT for coding, review" in performance, (
        "anchor moved -- the owner policy this floor derives from"
    )

    route = _read("commands/model-route.md")
    assert (
        "max(`recommended_tier`, opus)" in route
        or "max(recommended_tier, opus)" in (route)
    ), (
        "commands/model-route.md treats the router tier as the subagent selector, but "
        "rules/common/performance.md defaults every substantive subagent to Opus and "
        "says that overrides generic cost routing. The command must state the floor."
    )
    assert "performance.md" in route, (
        "the floor must cite the governing rule so a reader can check it"
    )


# ── deploy-surface parity for the docs touched above ────────────────────────────


@pytest.mark.parametrize("rel", MIRRORED_DOCS)
def test_agent_self_mirror_is_byte_identical(rel: str):
    root = REPO_ROOT / rel
    mirror = REPO_ROOT / "agent-self" / "config" / rel
    assert mirror.is_file(), f"missing deploy mirror for {rel}"
    assert root.read_bytes() == mirror.read_bytes(), (
        f"{rel} and its agent-self/config copy have drifted; agent-self/config is the "
        "committed deploy surface for the live ~/.claude, so a fix applied to only one "
        "side ships half-deployed"
    )
