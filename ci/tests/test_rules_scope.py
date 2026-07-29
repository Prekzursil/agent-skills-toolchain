"""D-a010 -- a globally-worded rule must not be scoped to source-code paths only.

``rules/common/performance.md`` declares model-routing, context-window and reasoning
policy for "ALL substantive subagents: coding, review, research, orchestration"
(:25-35) and prescribes extended thinking / Plan Mode / critique rounds / split-role
subagents for complex tasks (:50-64). A rule that carries ``paths:`` frontmatter is
selected only when a matching file is touched (``rules/README.md:1-4``), so while
those globs listed only source-code extensions the policy was unavailable in exactly
the research/orchestration state it claims to govern: a task that reads ``README.md``
and coordinates subagents matches none of ``**/*.py`` ... ``**/*.sh``.

The repo already ships the idiom for a doctrine that must be available everywhere --
``rules/common/owner-ops-authorization.md:2-3`` uses ``paths: - "**/*"``. This suite
pins ``performance.md`` to that class, and keeps the assertion tied to its rationale:
it demands broad scope only while the body still claims broad reach, and it accepts
frontmatter-less (unconditionally loaded) rules as equally correct.

The glob matcher is written here rather than borrowed from the audit probe that
produced the finding, so this is a mechanically independent detector: ``**/`` must
match ZERO OR MORE directories (minimatch / gitignore semantics), which ``fnmatch``
does not implement -- under ``fnmatch`` a root-level ``app.py`` would read as
unmatched by ``**/*.py`` and the whole result would be wrong in the safe-looking
direction. ``test_matcher_control_*`` is the KNOWN-POSITIVE control that proves the
matcher can still see a hit and still see a miss before any verdict is believed.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PERFORMANCE = REPO_ROOT / "rules" / "common" / "performance.md"

GLOBAL_CLAIM = "ALL substantive subagents"
# What a research / orchestration task actually touches. None carries a source-code
# extension, which is the whole point of the finding.
NON_CODE_PATHS = ("README.md", "docs/research.md", "notes/architecture.txt")


def _frontmatter_paths(path: Path) -> list[str]:
    """Return the ``paths:`` globs declared in the YAML frontmatter, or []."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    globs: list[str] = []
    in_paths = False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if re.fullmatch(r"paths:\s*", line):
            in_paths = True
            continue
        item = re.fullmatch(r'\s+-\s*"?([^"]+?)"?\s*', line)
        if in_paths and item:
            globs.append(item.group(1))
        elif line[:1] and not line[:1].isspace():
            in_paths = False
    return globs


def _glob_to_regex(glob: str) -> re.Pattern[str]:
    out = ["^"]
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def _matches(globs: list[str], candidate: str) -> bool:
    return any(_glob_to_regex(g).match(candidate) for g in globs)


def test_matcher_control_sees_a_code_glob_hit_and_a_miss() -> None:
    """Detector control: the matcher must find a known hit AND a known miss."""
    assert _matches(["**/*.py"], "src/app.py")
    assert _matches(["**/*.py"], "app.py"), "**/ must match zero directories too"
    assert not _matches(["**/*.py"], "README.md")
    assert _matches(["**/*"], "README.md"), "the maximal glob must match a root doc"


def test_globally_worded_performance_rule_loads_without_touching_source_code() -> None:
    body = PERFORMANCE.read_text(encoding="utf-8")
    assert GLOBAL_CLAIM in body, (
        f"{PERFORMANCE.name} no longer claims global reach; re-derive this gate "
        "before relaxing it"
    )
    globs = _frontmatter_paths(PERFORMANCE)
    if not globs:
        return  # no paths: frontmatter -> loaded unconditionally, nothing to gate
    unreachable = [p for p in NON_CODE_PATHS if not _matches(globs, p)]
    assert not unreachable, (
        f"{PERFORMANCE.name} says {GLOBAL_CLAIM!r} but its paths: frontmatter "
        f"{globs} never selects {unreachable} -- the policy is unavailable for the "
        "research/orchestration work it governs"
    )
