"""Deterministic planted skill/rule estate for AUD-0058 controls."""
from __future__ import annotations

from pathlib import Path

from common import (
    ALWAYS_ON_MARKER,
    BARE_MARKER,
    DEMOTED_MARKER,
    FIXTURE_ROOT,
    LAZY_MARKER,
)

ALWAYS_ON = f"""\
---
name: always-on
description: Known always-on skill. Router consumes name and description. No paths key.
---

# Always-on

{ALWAYS_ON_MARKER}
Body injected at turn zero.
"""

LAZY = f"""\
---
name: lazy-scoped
description: Path-scoped skill. Index card at turn zero; body only on a matching touch.
paths:
  - "src/**/*.py"
---

# Lazy scoped

{LAZY_MARKER}
This body must not appear in the turn-zero context bag.
"""

BARE = f"""\
# Bare rule with no frontmatter

{BARE_MARKER}
Absence of a fence is always-on, not never-loaded.
"""

DEMOTED = f"""\
---
name: demoted-star
description: Was always-on; adding paths ["**/*"] demotes it to lazy at turn zero.
paths:
  - "**/*"
---

# Demoted by star glob

{DEMOTED_MARKER}
A star glob does not keep this body in the turn-zero bag.
"""


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def ensure_fixtures() -> Path:
    root = FIXTURE_ROOT
    _write(root / "always-on" / "SKILL.md", ALWAYS_ON)
    _write(root / "lazy-scoped" / "SKILL.md", LAZY)
    _write(root / "rules" / "common" / "no-frontmatter.md", BARE)
    _write(root / "demoted-star" / "SKILL.md", DEMOTED)
    return root
