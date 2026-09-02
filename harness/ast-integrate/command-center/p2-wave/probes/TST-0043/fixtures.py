#!/usr/bin/env python3
"""Build conforming and malformed skill trees for TST-0043 probes."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
STATIC = HERE / "fixtures"


CONFORMING_ALWAYS = """---
name: echo-skill
description: Repeat the user's last phrase unchanged. Use when asked to echo.
load: always-on
---

# Echo

Repeat the phrase. No tools. No network.
"""

CONFORMING_LAZY = """---
name: scoped-skill
description: Path-scoped helper loaded only on Python sources.
load: lazy
paths:
  - "**/*.py"
  - "src/**/*.py"
---

# Scoped

Activated when a matching path is touched.
"""

MISSING_NAME = """---
description: Has a description and load class but no name field.
load: always-on
---

# Missing name
"""

EMPTY_NAME = """---
name:
description: Name is present as an empty scalar.
load: always-on
---

# Empty name
"""

UNRESOLVABLE_NAME = """---
name: Not A Valid Skill
description: Name contains spaces and capitals; the router cannot bind it.
load: always-on
---

# Unresolvable name
"""

NAME_MISMATCH = """---
name: other-skill
description: Frontmatter name does not match the directory name.
load: always-on
---

# Name/dir mismatch
"""

MISSING_DESCRIPTION = """---
name: nodesc-skill
load: always-on
---

# Missing description
"""

EMPTY_DESCRIPTION = """---
name: emptydesc-skill
description:
load: always-on
---

# Empty description
"""

MISSING_TRIGGER = """---
name: notrigger-skill
description: Name and description but no load/paths trigger surface.
---

# Missing trigger
"""

INVALID_LOAD = """---
name: badload-skill
description: Load class is not always-on or lazy.
load: sometimes
---

# Invalid load
"""

LAZY_NO_PATHS = """---
name: nopath-skill
description: Declares lazy load without a paths trigger surface.
load: lazy
---

# Lazy without paths
"""

LAZY_EMPTY_PATHS = """---
name: emptypath-skill
description: Declares lazy load with an empty paths list.
load: lazy
paths: []
---

# Lazy empty paths
"""

ALWAYS_WITH_PATHS = """---
name: conflict-skill
description: Always-on plus paths is the demotion accident ARC-0089 names.
load: always-on
paths:
  - "**/*"
---

# Conflict
"""

BROKEN_YAML = """---
name: [this is : broken
description: nope
load: always-on
---

# Broken YAML
"""

UNCLOSED = """---
name: unclosed-skill
description: Frontmatter never closes.
load: always-on
# no closing fence

# Unclosed
"""

NO_FRONTMATTER = """# demo skill
Typed handoff only. No frontmatter at all.
"""

EMPTY_FRONTMATTER = """---
---

# Empty frontmatter
"""


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8")
    return path


def write_static_fixtures() -> dict[str, Path]:
    """Checked-in fixtures for evidence line citations."""
    mapping = {
        "conforming/skills/echo-skill/SKILL.md": CONFORMING_ALWAYS,
        "conforming/skills/scoped-skill/SKILL.md": CONFORMING_LAZY,
        "malformed/skills/broken-yaml/SKILL.md": BROKEN_YAML,
        "malformed/skills/no-frontmatter/SKILL.md": NO_FRONTMATTER,
        "malformed/skills/missing-name/SKILL.md": MISSING_NAME,
    }
    out = {}
    for rel, text in mapping.items():
        out[rel] = _write(STATIC / rel, text)
    return out


def write_tree(root: Path, skills: dict[str, str]) -> Path:
    for skill_id, text in skills.items():
        _write(root / "skills" / skill_id / "SKILL.md", text)
    return root


def conforming_tree(root: Path) -> Path:
    return write_tree(
        root,
        {
            "echo-skill": CONFORMING_ALWAYS,
            "scoped-skill": CONFORMING_LAZY,
        },
    )


def mixed_tree(root: Path) -> Path:
    """One conforming skill plus one malformed skill (both-states on one deploy)."""
    return write_tree(
        root,
        {
            "echo-skill": CONFORMING_ALWAYS,
            "broken-yaml": BROKEN_YAML,
        },
    )


NEGATIVES: list[tuple[str, str, str]] = [
    ("missing-name", MISSING_NAME, "NAME_MISSING"),
    ("empty-name", EMPTY_NAME, "NAME_EMPTY"),
    ("unresolvable-name", UNRESOLVABLE_NAME, "NAME_UNRESOLVABLE"),
    ("mismatch-skill", NAME_MISMATCH, "NAME_DIR_MISMATCH"),
    ("nodesc-skill", MISSING_DESCRIPTION, "DESCRIPTION_MISSING"),
    ("emptydesc-skill", EMPTY_DESCRIPTION, "DESCRIPTION_EMPTY"),
    ("notrigger-skill", MISSING_TRIGGER, "TRIGGER_MISSING"),
    ("badload-skill", INVALID_LOAD, "LOAD_INVALID"),
    ("nopath-skill", LAZY_NO_PATHS, "PATHS_MISSING_FOR_LAZY"),
    ("emptypath-skill", LAZY_EMPTY_PATHS, "PATHS_EMPTY_FOR_LAZY"),
    ("conflict-skill", ALWAYS_WITH_PATHS, "PATHS_FORBIDDEN_FOR_ALWAYS"),
    ("broken-yaml", BROKEN_YAML, "FRONTMATTER_UNPARSEABLE"),
    ("unclosed-skill", UNCLOSED, "FRONTMATTER_UNCLOSED"),
    ("no-frontmatter", NO_FRONTMATTER, "FRONTMATTER_ABSENT"),
    ("empty-fm-skill", EMPTY_FRONTMATTER, "FRONTMATTER_EMPTY"),
]
