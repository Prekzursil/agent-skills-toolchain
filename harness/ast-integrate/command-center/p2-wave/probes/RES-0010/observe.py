"""Apply the live-client replica to fixtures. Two independent signals.

Signal A: needle presence + sha256 of the installed cursor-agent index.js
Signal B: classified load_mode / loaded|not-loaded on fixture files
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fixtures import (
    NONMATCH_REL,
    RULE_ALWAYS,
    RULE_DESC_ONLY,
    RULE_GLOBS,
    RULE_NO_FM,
    RULE_PATHS_KEY,
    SKILL_NO_PATHS,
    SKILL_WITH_PATHS,
    TOUCH_REL,
    ensure_fixtures,
)
from loader import (
    SKILL_FRONTMATTER_FIELDS_READ,
    classify_rule,
    classify_skill,
    client_source_ok,
    observation_for_rule,
    observation_for_skill,
)

HERE = Path(__file__).resolve().parent
BUILTIN = HERE / "fixtures" / "skills-cursor"


def _rel(path: Path) -> str:
    try:
        return path.relative_to(HERE).as_posix()
    except ValueError:
        return path.as_posix()


def classify_all() -> dict[str, Any]:
    ensure_fixtures()
    src = client_source_ok()
    skills = [
        classify_skill(_rel(SKILL_NO_PATHS), SKILL_NO_PATHS.read_text(encoding="utf-8")),
        classify_skill(_rel(SKILL_WITH_PATHS), SKILL_WITH_PATHS.read_text(encoding="utf-8")),
    ]
    rules = [
        classify_rule(_rel(RULE_ALWAYS), RULE_ALWAYS.read_text(encoding="utf-8")),
        classify_rule(_rel(RULE_GLOBS), RULE_GLOBS.read_text(encoding="utf-8")),
        classify_rule(_rel(RULE_PATHS_KEY), RULE_PATHS_KEY.read_text(encoding="utf-8")),
        classify_rule(_rel(RULE_DESC_ONLY), RULE_DESC_ONLY.read_text(encoding="utf-8")),
        classify_rule(_rel(RULE_NO_FM), RULE_NO_FM.read_text(encoding="utf-8")),
    ]
    match_obs = [observation_for_skill(s, TOUCH_REL) for s in skills] + [
        observation_for_rule(r, TOUCH_REL) for r in rules
    ]
    nonmatch_obs = [observation_for_skill(s, NONMATCH_REL) for s in skills] + [
        observation_for_rule(r, NONMATCH_REL) for r in rules
    ]
    builtin_rows = []
    if BUILTIN.is_dir():
        for skill_md in sorted(BUILTIN.glob("*/SKILL.md")):
            rec = classify_skill(skill_md.as_posix(), skill_md.read_text(encoding="utf-8"))
            builtin_rows.append(
                {
                    "name": rec.get("name"),
                    "disable_model_invocation": rec.get("disable_model_invocation"),
                    "model_invocable": rec.get("model_invocable"),
                    "paths_key_present": rec.get("paths_key_present"),
                    "globs": rec.get("globs") or [],
                    "fields_present": rec.get("fields_present"),
                }
            )
    return {
        "client": src,
        "skill_fields_read": list(SKILL_FRONTMATTER_FIELDS_READ),
        "skills": skills,
        "rules": rules,
        "observations_matching_touch": match_obs,
        "observations_nonmatching_touch": nonmatch_obs,
        "touch_matching": TOUCH_REL,
        "touch_nonmatching": NONMATCH_REL,
        "builtin_skills": builtin_rows,
    }


def claimed_claude_code_inversion(rec: dict[str, Any]) -> dict[str, str]:
    """Catalog hypothesis: NO paths: => turn-0 body; WITH paths: => body only after touch."""
    if rec.get("paths_key_present"):
        return {"turn0_body": "not-loaded", "after_touch_body": "loaded"}
    return {"turn0_body": "loaded", "after_touch_body": "loaded"}
