"""Measure the lazily-injected set observed in-session after touching .py files.

OBSERVED (first-party system-reminder injection, Claude Code 2.1.228, cwd =
ast-integrate, after Write/Edit of docs/rule-audit/*.py): the files listed in
OBSERVED below were injected. common/hooks.md was NOT. This probe prints their
glob selectors and token cost so the selective-match hypothesis can be checked.
"""

import os
import re

import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")
LIVE = r"C:/Users/Prekzursil/.claude/rules"

OBSERVED = [
    "common/ci-hygiene.md",
    "common/code-review.md",
    "common/coding-style.md",
    "common/development-workflow.md",
    "common/git-workflow.md",
    "common/owner-ops-authorization.md",
    "common/patterns.md",
    "common/performance.md",
    "common/security.md",
    "common/static-analyzer.md",
    "common/testing.md",
    "python/coding-style.md",
    "python/hooks.md",
    "python/patterns.md",
    "python/security.md",
    "python/testing.md",
]
NOT_OBSERVED = ["common/hooks.md"]


def info(rel):
    p = os.path.join(LIVE, rel)
    with open(p, "rb") as fh:
        t = fh.read().replace(b"\r\n", b"\n").decode("utf-8", errors="replace")
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    globs = re.findall(r'-\s*"([^"]+)"', m.group(1)) if m else []
    return len(ENC.encode(t)), globs


tot = 0
print("INJECTED on a .py touch:")
for rel in OBSERVED:
    n, g = info(rel)
    tot += n
    print("  %-38s %5d tok  %s" % (rel, n, g))
print("  %-38s %5d tok  TOTAL" % ("", tot))

print("\nNOT injected (control - proves selectors are evaluated, not 'load all'):")
for rel in NOT_OBSERVED:
    n, g = info(rel)
    print("  %-38s %5d tok  %s" % (rel, n, g))

print(
    "\nAlways-on floor 15141 + lazy %d = %d tok once a .py file is touched"
    % (tot, 15141 + tot)
)
