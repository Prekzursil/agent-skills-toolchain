"""Tests for Spec-3 skill consolidation analysis (no deletions)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import consolidation  # noqa: E402


def _mk(p: Path, desc: str = "one line desc", body: str = "body"):
    p.mkdir(parents=True, exist_ok=True)
    (p / "SKILL.md").write_text(f"---\nname: {p.name}\ndescription: {desc}\n---\n{body}\n", encoding="utf-8")


def test_exact_duplicate_and_collision_and_desc(tmp_path: Path):
    a = tmp_path / "rootA"
    b = tmp_path / "rootB"
    # identical content in two roots -> exact duplicate (intentional mirror)
    _mk(a / "mirror", body="same")
    _mk(b / "mirror", body="same")
    # same name, different content -> name collision (unsafe)
    _mk(a / "drift", body="v1")
    _mk(b / "drift", body="v2")
    # multi-line description -> trigger issue
    (a / "bad").mkdir()
    (a / "bad" / "SKILL.md").write_text("---\nname: bad\ndescription: line1\n  line2\n---\n", encoding="utf-8")
    # marketplace skill -> excluded
    mk = tmp_path / "plugins" / "cache" / "vendor"
    _mk(mk)

    res = consolidation.analyze_skills([a, b, tmp_path / "plugins"])
    assert res["skills_scanned"] == 5            # marketplace 'vendor' excluded
    dup_names = {Path(p).parent.name for g in res["exact_duplicate_groups"] for p in g}
    assert "mirror" in dup_names
    assert any(c["name"] == "drift" for c in res["name_collisions"])
    assert any(d["skill"] == "bad" for d in res["description_issues"])


def test_render_report_is_markdown(tmp_path: Path):
    _mk(tmp_path / "r" / "x")
    rep = consolidation.render_report(consolidation.analyze_skills([tmp_path / "r"]))
    assert rep.startswith("# Skill Consolidation Analysis")
    assert "Skills scanned" in rep
