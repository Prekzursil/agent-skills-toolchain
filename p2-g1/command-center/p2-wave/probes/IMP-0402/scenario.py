"""Fixture trees for IMP-0402 probes."""

from __future__ import annotations

from pathlib import Path

PAINT_BEFORE = "mixes RED-PIGMENT for interior walls"
PAINT_AFTER = "mixes BLUE-PIGMENT for interior walls"
GLOSS_STABLE = "applies GLOSS-COAT after the pigment has cured"
QUERY_RED = "RED-PIGMENT"
QUERY_BLUE = "BLUE-PIGMENT"
QUERY_GLOSS = "GLOSS-COAT"


def write_skill(path: Path, name: str, description: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return path


def build_capability_tree(root: Path) -> dict[str, Path]:
    """Two skills: paint (edited in probe1) and gloss (unchanged control)."""
    root = Path(root)
    paint = write_skill(root / "skills" / "paint" / "SKILL.md", "paint", PAINT_BEFORE)
    gloss = write_skill(root / "skills" / "gloss" / "SKILL.md", "gloss", GLOSS_STABLE)
    plugin = root / "plugins" / "plugin.json"
    plugin.parent.mkdir(parents=True, exist_ok=True)
    plugin.write_text(
        '{"name": "plugin-brush", "description": "selects a BRUSH-HEAD for the paint pass"}\n',
        encoding="utf-8",
    )
    return {"paint": paint, "gloss": gloss, "plugin": plugin}


def edit_paint_description(paint_path: Path, description: str = PAINT_AFTER) -> None:
    write_skill(paint_path, "paint", description)
