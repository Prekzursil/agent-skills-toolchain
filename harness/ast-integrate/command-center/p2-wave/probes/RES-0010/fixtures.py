"""Isolated fixture skills and rules for RES-0010.

Does not write into ~/.cursor or the workspace .cursor tree. The loader is
applied to these files in-place, the same way the client parses SKILL.md / .mdc.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
SKILLS = FIX / "skills"
RULES = FIX / "rules"
TOUCH_REL = "workspace/res0010-touch-target.py"
NONMATCH_REL = "workspace/unrelated.txt"
TOUCH_GLOB = "**/res0010-touch-target.py"

SKILL_NO_PATHS = SKILLS / "skill-no-paths" / "SKILL.md"
SKILL_WITH_PATHS = SKILLS / "skill-with-paths" / "SKILL.md"
RULE_ALWAYS = RULES / "always-on.mdc"
RULE_GLOBS = RULES / "glob-scoped.mdc"
RULE_PATHS_KEY = RULES / "paths-key-only.mdc"
RULE_DESC_ONLY = RULES / "desc-only.mdc"
RULE_NO_FM = RULES / "no-frontmatter.mdc"
TOUCH_FILE = FIX / TOUCH_REL
NONMATCH_FILE = FIX / NONMATCH_REL

MARKER_ALWAYS_SKILL = "RES0010-ALWAYS-SKILL-BODY"
MARKER_LAZY_SKILL = "RES0010-LAZY-SKILL-BODY"
MARKER_GLOB_RULE = "RES0010-GLOB-RULE-BODY"


def ensure_fixtures() -> dict[str, str]:
    SKILL_NO_PATHS.parent.mkdir(parents=True, exist_ok=True)
    SKILL_WITH_PATHS.parent.mkdir(parents=True, exist_ok=True)
    RULES.mkdir(parents=True, exist_ok=True)
    TOUCH_FILE.parent.mkdir(parents=True, exist_ok=True)

    SKILL_NO_PATHS.write_text(
        "---\n"
        "name: res0010-skill-no-paths\n"
        "description: Fixture skill with NO paths frontmatter (turn-0 catalog candidate).\n"
        "---\n\n"
        f"# No-paths skill\n\n{MARKER_ALWAYS_SKILL}\n",
        encoding="utf-8",
    )
    SKILL_WITH_PATHS.write_text(
        "---\n"
        "name: res0010-skill-with-paths\n"
        "description: Fixture skill WITH paths frontmatter (claimed lazy-on-touch).\n"
        f'paths:\n  - "{TOUCH_GLOB}"\n'
        "---\n\n"
        f"# Paths-scoped skill\n\n{MARKER_LAZY_SKILL}\n",
        encoding="utf-8",
    )
    RULE_ALWAYS.write_text(
        "---\n"
        "description: Always-on fixture rule\n"
        "alwaysApply: true\n"
        "---\n\n"
        "# Always on\n\nALWAYS-ON-BODY\n",
        encoding="utf-8",
    )
    RULE_GLOBS.write_text(
        "---\n"
        "description: Glob-scoped fixture rule\n"
        f'globs: "{TOUCH_GLOB}"\n'
        "alwaysApply: false\n"
        "---\n\n"
        f"# Glob scoped\n\n{MARKER_GLOB_RULE}\n",
        encoding="utf-8",
    )
    RULE_PATHS_KEY.write_text(
        "---\n"
        "description: Claude-Code paths: key on a Cursor .mdc rule\n"
        f'paths: "{TOUCH_GLOB}"\n'
        "alwaysApply: false\n"
        "---\n\n"
        "# Paths key only\n\nPATHS-KEY-BODY\n",
        encoding="utf-8",
    )
    RULE_DESC_ONLY.write_text(
        "---\n"
        "description: Description only, no globs, alwaysApply false\n"
        "alwaysApply: false\n"
        "---\n\n"
        "# Agent fetched\n\nDESC-ONLY-BODY\n",
        encoding="utf-8",
    )
    RULE_NO_FM.write_text("# No frontmatter at all\n\nNO-FM-BODY\n", encoding="utf-8")
    TOUCH_FILE.write_text("# res0010 matching touch target\nprint(0)\n", encoding="utf-8")
    NONMATCH_FILE.write_text("unrelated\n", encoding="utf-8")
    return {
        "skill_no_paths": str(SKILL_NO_PATHS.relative_to(HERE)).replace("\\", "/"),
        "skill_with_paths": str(SKILL_WITH_PATHS.relative_to(HERE)).replace("\\", "/"),
        "rule_always": str(RULE_ALWAYS.relative_to(HERE)).replace("\\", "/"),
        "rule_globs": str(RULE_GLOBS.relative_to(HERE)).replace("\\", "/"),
        "rule_paths_key": str(RULE_PATHS_KEY.relative_to(HERE)).replace("\\", "/"),
        "rule_desc_only": str(RULE_DESC_ONLY.relative_to(HERE)).replace("\\", "/"),
        "rule_no_fm": str(RULE_NO_FM.relative_to(HERE)).replace("\\", "/"),
        "touch": TOUCH_REL,
        "nonmatch": NONMATCH_REL,
    }
