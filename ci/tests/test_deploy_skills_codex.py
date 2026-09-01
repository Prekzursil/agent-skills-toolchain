"""Both-states tests for the allowlist-pinned Codex delivery hop."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "deploy-skills-codex.py"


def skill(root: Path, name: str, data: bytes = b"---\nname: x\n---\n") -> None:
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def run(
    tmp_path: Path, names: bytes, *, apply: bool = False
) -> subprocess.CompletedProcess[str]:
    src, dst, allow = tmp_path / "src", tmp_path / "dst", tmp_path / "allow.txt"
    src.mkdir(exist_ok=True)
    dst.mkdir(exist_ok=True)
    allow.write_bytes(names)
    args = [
        sys.executable,
        str(SCRIPT),
        "--source",
        str(src),
        "--target",
        str(dst),
        "--allowlist",
        str(allow),
        "--check",
    ]
    if apply:
        args += ["--apply"]
    return subprocess.run(args, text=True, capture_output=True, check=False)


def test_control_clean_input_stays_green(tmp_path: Path) -> None:
    skill(tmp_path / "src", "alpha")
    skill(tmp_path / "dst", "alpha")
    result = run(tmp_path, b"alpha\r\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SUCCESS:deploy-skills-codex" in result.stdout


def test_p1_non_allowlisted_skill_is_never_copied(tmp_path: Path) -> None:
    skill(tmp_path / "src", "alpha")
    skill(tmp_path / "src", "rogue")
    skill(tmp_path / "dst", "alpha")
    result = run(tmp_path, b"alpha\n", apply=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / "dst" / "rogue").exists()


def test_p1_missing_allowlisted_skill_goes_red(tmp_path: Path) -> None:
    skill(tmp_path / "src", "alpha")
    skill(tmp_path / "dst", "alpha")
    result = run(tmp_path, b"alpha\r\nmissing\r\n")
    assert result.returncode != 0
    assert "MISSING-SOURCE-SKILL missing" in result.stdout
    assert "FAILED:deploy-skills-codex" in result.stdout


def test_p2_apply_never_deletes_unrelated_target(tmp_path: Path) -> None:
    skill(tmp_path / "src", "alpha", b"new\n")
    skill(tmp_path / "dst", "alpha", b"old\n")
    skill(tmp_path / "dst", ".system", b"system\n")
    skill(tmp_path / "dst", "skill-stocktake", b"stock\n")
    result = run(tmp_path, b"alpha\n", apply=True)
    assert (tmp_path / "dst" / ".system" / "SKILL.md").read_bytes() == b"system\n"
    assert (
        tmp_path / "dst" / "skill-stocktake" / "SKILL.md"
    ).read_bytes() == b"stock\n"
    assert result.returncode == 0, result.stdout + result.stderr


def test_p2_source_contains_no_delete_primitive() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "rmtree" not in text and "unlink(" not in text and "remove(" not in text


def test_p3_dry_run_leaves_stale_target_and_check_goes_red(tmp_path: Path) -> None:
    skill(tmp_path / "src", "alpha", b"new\n")
    skill(tmp_path / "dst", "alpha", b"old\n")
    result = run(tmp_path, b"alpha\n")
    assert result.returncode != 0
    assert (tmp_path / "dst" / "alpha" / "SKILL.md").read_bytes() == b"old\n"


def test_p4_empty_walk_goes_red(tmp_path: Path) -> None:
    result = run(tmp_path, b"alpha\n")
    assert result.returncode != 0
    assert "P4 empty source walk" in result.stdout


def test_p5_content_drift_goes_red_but_crlf_only_is_green(tmp_path: Path) -> None:
    skill(tmp_path / "src", "alpha", b"same\n")
    skill(tmp_path / "dst", "alpha", b"same\r\n")
    clean = run(tmp_path, b"alpha\r\n")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    (tmp_path / "dst" / "alpha" / "SKILL.md").write_bytes(b"different\r\n")
    broken = run(tmp_path, b"alpha\r\n")
    assert broken.returncode != 0
    assert "[stale]" in broken.stdout
