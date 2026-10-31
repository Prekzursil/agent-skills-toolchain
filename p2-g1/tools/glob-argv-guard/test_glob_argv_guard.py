"""Tests for glob_argv_guard — the Glob/Grep ENAMETOOLONG guard.

Measured ground truth this suite encodes (2026-07-18, Claude Code 2.1.214, Win11):
  * Windows CreateProcess argv cap, measured empirically via libuv spawn:
    32,745 chars OK -> 32,774 chars ENAMETOOLONG.
  * Claude Code builds one `--glob !**/<dir>/**` PAIR per `.orphaned_at` marker
    found by `rg --files --hidden --no-ignore --max-depth 4 --glob .orphaned_at`
    rooted at <pluginRoot>/cache, and appends them to EVERY Glob/Grep whose
    search path is an ancestor-or-descendant of that cache dir.
  * On this box that was 1,293 markers -> 82,893 argv chars = 2.5x over the cap.
  * 1,191 of those 1,293 (92.7% of the bytes) were spurious markers written
    inside `temp_subdir_*` git-clone husks; only 102 were genuine plugin
    versions, which alone never breach the cap.
"""

import os
import shutil
import subprocess

import pytest

from glob_argv_guard import (
    WINDOWS_CMDLINE_CAP,
    build_exclusions,
    classify_marker,
    diagnose,
    exclusion_argv_bytes,
    plan_remediation,
    render_rg_config,
    restore_manifest_roundtrip,
    scan_markers,
    terminal_state,
)


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
def _write_marker(path, epoch_ms=b"1782688521253"):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, ".orphaned_at"), "wb") as fh:
        fh.write(epoch_ms)  # 13 bytes, exactly as the real marker


@pytest.fixture
def real_shape_cache(tmp_path):
    """Reproduces the measured shape of the live cache that broke Glob."""
    cache = tmp_path / "cache"
    for i in range(239):  # 239 husks x 5 .git subdirs = 1,195 spurious markers
        for sub in (
            ".git/refs",
            ".git/objects",
            ".git/info",
            ".git/hooks",
            ".git/logs",
        ):
            _write_marker(
                str(cache / f"temp_subdir_178268852{i:04d}_abcdef.clone" / sub)
            )
    for i in range(102):  # genuine orphaned plugin versions
        _write_marker(
            str(cache / "claude-plugins-official" / f"plugin{i:03d}" / "1.0.0")
        )
    return cache


@pytest.fixture
def genuine_only_cache(tmp_path):
    # NOTE: distinct subdir from real_shape_cache -- pytest hands both fixtures the
    # same tmp_path within one test, so sharing "cache" silently merged the two
    # populations and made the genuine-only case unrepresentable.
    cache = tmp_path / "cache_genuine_only"
    for i in range(102):
        _write_marker(
            str(cache / "claude-plugins-official" / f"plugin{i:03d}" / "1.0.0")
        )
    return cache


# --------------------------------------------------------------------------
# 1. the defect must REPRODUCE
# --------------------------------------------------------------------------
def test_measured_cap_matches_libuv_boundary():
    """32,745 was OK and 32,774 failed -> the cap sits at 32,767."""
    assert WINDOWS_CMDLINE_CAP == 32767
    assert 32745 < WINDOWS_CMDLINE_CAP < 32774


def test_real_shape_cache_reproduces_enametoolong(real_shape_cache):
    markers = scan_markers(str(real_shape_cache), max_depth=4)
    argv = exclusion_argv_bytes(build_exclusions(markers))
    assert argv > WINDOWS_CMDLINE_CAP, (
        f"fixture must reproduce the overflow, got {argv} <= {WINDOWS_CMDLINE_CAP}"
    )
    assert argv > 2 * WINDOWS_CMDLINE_CAP  # measured 2.5x on the live tree


def test_genuine_markers_alone_never_breach_the_cap(genuine_only_cache):
    """The briefed premise blamed orphaned PLUGIN dirs. They are not the cause."""
    markers = scan_markers(str(genuine_only_cache), max_depth=4)
    argv = exclusion_argv_bytes(build_exclusions(markers))
    assert argv < WINDOWS_CMDLINE_CAP


# --------------------------------------------------------------------------
# 2. scan fidelity -- depth semantics and rg cross-check
# --------------------------------------------------------------------------
def test_scan_honours_max_depth_4(tmp_path):
    """Markers deeper than 4 are INVISIBLE to Claude Code -> removing them saves 0."""
    cache = tmp_path / "cache"
    _write_marker(str(cache / "mkt" / "plugin" / "1.0.0"))  # depth 4 -> found
    _write_marker(
        str(cache / "mkt" / "a" / "b" / "c" / "1.0.0")
    )  # depth 6 -> not found
    found = scan_markers(str(cache), max_depth=4)
    assert len(found) == 1
    assert "1.0.0/.orphaned_at" in found[0].replace("\\", "/")
    assert not any("/c/" in f.replace("\\", "/") for f in found)


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not on PATH")
def test_pure_python_scan_agrees_with_real_ripgrep(real_shape_cache):
    """Two mechanically-independent implementations must agree (single-signal rule)."""
    ours = sorted(p.replace("\\", "/") for p in scan_markers(str(real_shape_cache), 4))
    proc = subprocess.run(
        [
            "rg",
            "--files",
            "--hidden",
            "--no-ignore",
            "--max-depth",
            "4",
            "--glob",
            ".orphaned_at",
        ],
        cwd=str(real_shape_cache),
        capture_output=True,
        text=True,
    )
    theirs = sorted(
        ln.strip().replace("\\", "/") for ln in proc.stdout.splitlines() if ln.strip()
    )
    assert ours == theirs, f"scan disagreement: ours={len(ours)} rg={len(theirs)}"


def test_exclusion_shape_matches_claude_code(tmp_path):
    """Bundle: `!**/${relative(cache, dirname(marker)).replaceAll('\\\\','/')}/**`"""
    cache = tmp_path / "cache"
    _write_marker(str(cache / "mkt" / "plugin" / "1.0.0"))
    excl = build_exclusions(scan_markers(str(cache), 4))
    assert excl == ["!**/mkt/plugin/1.0.0/**"]


def test_argv_accounting_counts_two_entries_per_exclusion():
    """Claude Code pushes '--glob' AND the pattern -> two argv entries."""
    one = exclusion_argv_bytes(["!**/a/**"])
    assert one == len("--glob") + 1 + len("!**/a/**") + 1


# --------------------------------------------------------------------------
# 3. classification -- husk vs genuine
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel,expected",
    [
        ("temp_subdir_1782707339413_dolltx.clone/.git/refs/.orphaned_at", "husk"),
        ("temp_subdir_1783746708193_qk0lrs/.git/objects/.orphaned_at", "husk"),
        ("claude-plugins-official/superpowers/6.0.3/.orphaned_at", "genuine"),
        ("openai-codex/codex/1.0.4/.orphaned_at", "genuine"),
        ("metaswarm-marketplace/metaswarm/0.11.0/.orphaned_at", "genuine"),
    ],
)
def test_classify_marker(rel, expected):
    assert classify_marker(rel) == expected


def test_husks_dominate_the_overflow(real_shape_cache):
    d = diagnose(str(real_shape_cache))
    assert d.by_class["husk"] > d.by_class["genuine"]
    husk_share = d.argv_bytes_by_class["husk"] / d.argv_bytes
    assert husk_share > 0.9, f"husks should dominate, got {husk_share:.1%}"


# --------------------------------------------------------------------------
# 4. the remediation must WORK and must be SAFE
# --------------------------------------------------------------------------
def test_rg_config_brings_argv_under_cap(real_shape_cache):
    plan = plan_remediation(str(real_shape_cache))
    assert plan.projected_argv_bytes < WINDOWS_CMDLINE_CAP
    assert plan.projected_argv_bytes < plan.current_argv_bytes


def test_remediation_deletes_nothing(real_shape_cache):
    before = sum(len(fs) for _, _, fs in os.walk(str(real_shape_cache)))
    plan_remediation(str(real_shape_cache))
    after = sum(len(fs) for _, _, fs in os.walk(str(real_shape_cache)))
    assert before == after, "planning must be strictly read-only"
    assert plan_remediation(str(real_shape_cache)).deletes == []


def test_remediation_never_targets_a_genuine_plugin_dir(real_shape_cache):
    plan = plan_remediation(str(real_shape_cache))
    for pat in plan.rg_config_patterns:
        assert "temp_subdir" in pat, f"pattern must not touch plugin dirs: {pat}"


def test_rg_config_render_is_valid_ripgrep_syntax():
    text = render_rg_config(["!temp_subdir_*/**"])
    assert text.splitlines() == ["--glob=!temp_subdir_*/**"]
    assert not text.startswith("#")  # rg config: one arg per line, no shell quoting


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep not on PATH")
def test_rg_config_actually_prunes_under_real_ripgrep(real_shape_cache, tmp_path):
    """End-to-end: the emitted config must really shrink Claude Code's own scan."""
    plan = plan_remediation(str(real_shape_cache))
    cfg = tmp_path / "rgconfig"
    cfg.write_text(render_rg_config(plan.rg_config_patterns), encoding="utf-8")
    env = dict(os.environ)
    env["RIPGREP_CONFIG_PATH"] = str(cfg)
    proc = subprocess.run(
        [
            "rg",
            "--files",
            "--hidden",
            "--no-ignore",
            "--max-depth",
            "4",
            "--glob",
            ".orphaned_at",
        ],
        cwd=str(real_shape_cache),
        capture_output=True,
        text=True,
        env=env,
    )
    remaining = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    argv = exclusion_argv_bytes(build_exclusions(remaining))
    assert argv < WINDOWS_CMDLINE_CAP
    assert all("temp_subdir" not in ln for ln in remaining)


def test_ignore_files_are_NOT_a_valid_fix(real_shape_cache):
    """Claude Code hardcodes --no-ignore in the scan, so .ignore/.rgignore cannot help.

    Guards against a future 'simplification' that swaps the config file for an
    ignore file. Measured: .rgignore/.ignore/.gitignore all left 1,297 markers.
    """
    plan = plan_remediation(str(real_shape_cache))
    assert plan.mechanism == "RIPGREP_CONFIG_PATH"
    assert "--no-ignore" in plan.why_not_ignore_files


# --------------------------------------------------------------------------
# 5. reversibility + terminal state
# --------------------------------------------------------------------------
def test_restore_manifest_roundtrips_markers_byte_exactly(tmp_path):
    cache = tmp_path / "cache"
    _write_marker(str(cache / "mkt" / "plugin" / "1.0.0"), b"1782688521253")
    assert restore_manifest_roundtrip(str(cache)) is True


def test_terminal_state_is_success_or_failed(real_shape_cache, genuine_only_cache):
    bad = terminal_state(diagnose(str(real_shape_cache)))
    good = terminal_state(diagnose(str(genuine_only_cache)))
    assert bad.startswith("FAILED:glob-argv-guard")
    assert good.startswith("SUCCESS:glob-argv-guard")
    assert "82" in bad or "argv" in bad
