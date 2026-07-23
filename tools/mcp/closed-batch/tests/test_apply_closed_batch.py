"""Tests for apply_closed_batch - additive, scoped, reversible, and guarded.

The load-bearing claims these pin down:
  * a full --apply changes ONLY the four intended sites; every other byte is identical
  * the ~33 unrelated project blocks keep serena disabled, byte-for-byte
  * --revert-from restores the file byte-for-byte
  * the live-session guard REFUSES to write (both-states: fires when a claude image is
    present, silent when it is not)
  * accounts.json - and every path that is not the target or its backup - is never opened
"""

from __future__ import annotations

import builtins
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import apply_closed_batch as m  # noqa: E402

FIXTURE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixture_claude.json"
)

SCOPED_KEYS = {
    "C:/Users/Prekzursil/source/agent-skills-toolchain",
    "C:/Users/Prekzursil/Documents/GitHub/Reframe",
    "C:/Users/Prekzursil/Documents/GitHub/Reframe/app",
    "C:/Users/Prekzursil/Documents/github/Reframe",
    "C:/Users/Prekzursil/Downloads/momentstudio",
}
UNSCOPED_KEYS = {
    "C:/Users/Prekzursil/Documents/GitHub/momentstudio-fix",
    "C:/Users/Prekzursil/Downloads/puric",
    "D:/Research",
}


@pytest.fixture
def target(tmp_path):
    dest = tmp_path / ".claude.json"
    shutil.copy2(FIXTURE, dest)
    return str(dest)


@pytest.fixture
def closed(monkeypatch):
    """Pretend no Claude session is alive."""
    monkeypatch.setattr(m, "_tasklist_names", lambda: ["python.exe", "node.exe"])


@pytest.fixture
def running(monkeypatch):
    """Pretend a Claude session IS alive."""
    monkeypatch.setattr(m, "_tasklist_names", lambda: ["python.exe", "claude.exe"])


def run(argv, capsys):
    rc = m.run(m.parse_args(argv))
    return rc, capsys.readouterr().out


# ------------------------------------------------------------------ detector shape


def test_detect_claude_fires_on_a_live_image():
    assert m.detect_claude(lambda: ["node.exe", "claude.exe"]) == ["claude.exe"]


def test_detect_claude_silent_without_one():
    assert m.detect_claude(lambda: ["node.exe", "python.exe"]) == []


def test_detect_claude_matches_image_name_not_command_line():
    """A path containing '.claude' must NOT be read as a live session (self-match)."""
    assert (
        m.detect_claude(lambda: ["python.exe", "C:/Users/x/.claude/hooks/run.exe"])
        == []
    )


def test_detect_claude_is_case_insensitive_and_deduped():
    assert m.detect_claude(lambda: ["CLAUDE.EXE", "claude.exe"]) == ["claude.exe"]


# ------------------------------------------------------------------------ matching


def test_match_projects_is_segment_exact():
    cfg = m.load_config(FIXTURE)
    hits = m.match_projects(cfg, m.DEFAULT_SCOPED_REPOS)
    assert set(hits["Reframe"]) == {
        "C:/Users/Prekzursil/Documents/GitHub/Reframe",
        "C:/Users/Prekzursil/Documents/GitHub/Reframe/app",
        "C:/Users/Prekzursil/Documents/github/Reframe",
    }
    assert hits["momentstudio"] == ["C:/Users/Prekzursil/Downloads/momentstudio"]
    assert hits["agent-skills-toolchain"] == [
        "C:/Users/Prekzursil/source/agent-skills-toolchain"
    ]
    assert hits["metaswarm"] == []


def test_case_colliding_project_keys_are_kept_distinct():
    """Documents/GitHub/Reframe and Documents/github/Reframe are DIFFERENT keys."""
    cfg = m.load_config(FIXTURE)
    keys = m.match_projects(cfg, ["Reframe"])["Reframe"]
    assert len(keys) == len(set(keys)) == 3


def test_momentstudio_fix_is_a_near_miss_not_a_match():
    cfg = m.load_config(FIXTURE)
    assert "C:/Users/Prekzursil/Documents/GitHub/momentstudio-fix" in m.near_misses(
        cfg, m.DEFAULT_SCOPED_REPOS
    )


def test_extra_project_widens_scope_deliberately():
    cfg = m.load_config(FIXTURE)
    hits = m.match_projects(cfg, [*m.DEFAULT_SCOPED_REPOS, "momentstudio-fix"])
    assert hits["momentstudio-fix"] == [
        "C:/Users/Prekzursil/Documents/GitHub/momentstudio-fix"
    ]


# ---------------------------------------------------------------- additive + scoped


def test_apply_touches_only_the_intended_sites(target, closed, capsys):
    before_raw = open(target, encoding="utf-8", newline="").read()
    before = json.loads(before_raw)
    rc, _ = run(["--target", target, "--apply"], capsys)
    assert rc == 0
    after = json.loads(open(target, encoding="utf-8", newline="").read())

    # 1. root list lost exactly serena, order otherwise preserved
    assert before["disabledMcpServers"] == [
        "angr",
        "apify",
        "serena",
        "social-hub",
        "sonarqube",
    ]
    assert after["disabledMcpServers"] == ["angr", "apify", "social-hub", "sonarqube"]

    # 2. scoped project blocks lost exactly serena
    for key in SCOPED_KEYS:
        assert m.SERENA not in after["projects"][key]["disabledMcpServers"]
        assert [
            s for s in before["projects"][key]["disabledMcpServers"] if s != m.SERENA
        ] == (after["projects"][key]["disabledMcpServers"])

    # 3. unscoped project blocks are byte-identical (still disabling serena)
    for key in UNSCOPED_KEYS:
        assert after["projects"][key] == before["projects"][key]
        assert m.SERENA in after["projects"][key]["disabledMcpServers"]

    # 4. grep added, playwright flagged
    assert after["mcpServers"]["grep"] == {
        "type": "http",
        "url": "https://mcp.grep.app",
    }
    assert after["mcpServers"]["playwright"]["args"] == [
        "-y",
        "@playwright/mcp",
        "--extension",
    ]

    # 5. EVERY other top-level key is untouched
    for key in before:
        if key in {"disabledMcpServers", "mcpServers", "projects"}:
            continue
        assert after[key] == before[key]
    assert set(after) == set(before)


def test_unrelated_mcp_curation_is_never_wiped(target, closed, capsys):
    before = m.load_config(target)
    run(["--target", target, "--apply"], capsys)
    after = m.load_config(target)
    for name, entry in before["mcpServers"].items():
        if name == "playwright":
            continue
        assert after["mcpServers"][name] == entry
    assert set(after["mcpServers"]) == set(before["mcpServers"]) | {"grep"}


def test_only_subset_applies_just_that_op(target, closed, capsys):
    before = m.load_config(target)
    rc, _ = run(["--target", target, "--only", "serena-projects", "--apply"], capsys)
    assert rc == 0
    after = m.load_config(target)
    assert after["disabledMcpServers"] == before["disabledMcpServers"]  # root untouched
    assert "grep" not in after["mcpServers"]
    assert after["mcpServers"]["playwright"] == before["mcpServers"]["playwright"]
    assert (
        m.SERENA
        not in after["projects"]["C:/Users/Prekzursil/source/agent-skills-toolchain"][
            "disabledMcpServers"
        ]
    )


def test_unknown_op_is_rejected():
    with pytest.raises(SystemExit):
        m.parse_args(["--only", "serena-projects,wipe-everything"])


# --------------------------------------------------------------------- idempotence


def test_second_apply_is_a_no_op(target, closed, capsys):
    run(["--target", target, "--apply"], capsys)
    first = open(target, encoding="utf-8", newline="").read()
    rc, out = run(["--target", target, "--apply"], capsys)
    assert rc == 0
    assert "nothing to do" in out
    assert open(target, encoding="utf-8", newline="").read() == first


def test_dry_run_is_the_default_and_writes_nothing(target, closed, capsys):
    before = open(target, encoding="utf-8", newline="").read()
    rc, out = run(["--target", target], capsys)
    assert rc == 0
    assert "dry-run" in out
    assert open(target, encoding="utf-8", newline="").read() == before
    assert not [p for p in os.listdir(os.path.dirname(target)) if ".bak-" in p]


def test_list_mode_writes_nothing_and_reports_scope(target, capsys):
    before = open(target, encoding="utf-8", newline="").read()
    rc, out = run(["--target", target, "--list"], capsys)
    assert rc == 0
    assert "root disables serena    : True" in out
    assert "metaswarm: 0" in out
    assert "momentstudio-fix" in out  # surfaced as a near miss
    assert open(target, encoding="utf-8", newline="").read() == before


# ------------------------------------------------------------------- reversibility


def test_backup_is_written_before_the_change_and_reverts_byte_exactly(
    target, closed, capsys
):
    original = open(target, encoding="utf-8", newline="").read()
    rc, out = run(["--target", target, "--apply"], capsys)
    assert rc == 0
    backups = [p for p in os.listdir(os.path.dirname(target)) if ".bak-" in p]
    assert len(backups) == 1
    backup_path = os.path.join(os.path.dirname(target), backups[0])
    assert open(backup_path, encoding="utf-8", newline="").read() == original
    assert open(target, encoding="utf-8", newline="").read() != original
    assert backup_path.replace("\\", "/") in out.replace("\\", "/")

    rc, _ = run(["--target", target, "--revert-from", backup_path], capsys)
    assert rc == 0
    assert open(target, encoding="utf-8", newline="").read() == original


def test_writer_round_trips_the_fixture_exactly():
    """The claim that untouched regions survive rests on this.

    Newlines are normalised because core.autocrlf=true checks this LF fixture out as
    CRLF on Windows; the invariant under test is the SERIALISED FORM, not the checkout
    EOL. test_write_config_emits_lf_only pins the byte-level behaviour separately, and
    the same round-trip was measured byte-exact against the real 234,595-byte
    ~/.claude.json (see README).
    """
    raw = open(FIXTURE, encoding="utf-8", newline="").read().replace("\r\n", "\n")
    assert m.dumps_config(m.load_config(FIXTURE)) == raw


def test_write_config_emits_lf_only_and_no_trailing_newline(target, tmp_path):
    """Self-contained byte check, immune to how git checked the fixture out."""
    cfg = m.load_config(target)
    dest = str(tmp_path / "out.json")
    m.write_config(dest, cfg)
    raw = open(dest, encoding="utf-8", newline="").read()
    assert "\r\n" not in raw
    assert raw == m.dumps_config(cfg)
    assert not raw.endswith("\n")  # matches Claude Code's own file exactly


# --------------------------------------------------------------------- the guard


def test_apply_refuses_while_claude_is_running(target, running, capsys):
    before = open(target, encoding="utf-8", newline="").read()
    rc, out = run(["--target", target, "--apply"], capsys)
    assert rc == 3
    assert "REFUSING" in out and "claude.exe" in out
    assert open(target, encoding="utf-8", newline="").read() == before
    assert not [p for p in os.listdir(os.path.dirname(target)) if ".bak-" in p]


def test_revert_refuses_while_claude_is_running(target, running, tmp_path, capsys):
    bak = tmp_path / "some.bak-20260724-000000"
    bak.write_text("{}", encoding="utf-8")
    before = open(target, encoding="utf-8", newline="").read()
    rc, out = run(["--target", target, "--revert-from", str(bak)], capsys)
    assert rc == 3
    assert "REFUSING" in out
    assert open(target, encoding="utf-8", newline="").read() == before


def test_preview_still_works_while_claude_is_running(target, running, capsys):
    rc, out = run(["--target", target], capsys)
    assert rc == 0
    assert "PRE-FLIGHT" in out
    assert "REFUSING" not in out


def test_guard_fails_closed_when_the_process_probe_breaks(target, monkeypatch, capsys):
    def boom():
        raise OSError("tasklist not found")

    monkeypatch.setattr(m, "_tasklist_names", boom)
    before = open(target, encoding="utf-8", newline="").read()
    rc, out = run(["--target", target, "--apply"], capsys)
    assert rc == 3
    assert "failing closed" in out
    assert open(target, encoding="utf-8", newline="").read() == before


def test_ignore_flag_overrides_the_guard_with_a_loud_warning(target, running, capsys):
    rc, out = run(["--target", target, "--apply", "--ignore-claude-check"], capsys)
    assert rc == 0
    assert "WARNING" in out
    assert "grep" in m.load_config(target)["mcpServers"]


# ------------------------------------------------------------- blast-radius limits


def test_apply_opens_only_the_target_and_its_backup(
    target, closed, monkeypatch, capsys
):
    touched: list[str] = []
    real_open = builtins.open
    real_copy = shutil.copy2

    def spy_open(file, *a, **kw):
        touched.append(str(file))
        return real_open(file, *a, **kw)

    def spy_copy(src, dst, **kw):
        touched.extend([str(src), str(dst)])
        return real_copy(src, dst, **kw)

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(shutil, "copy2", spy_copy)
    run(["--target", target, "--apply"], capsys)
    monkeypatch.undo()

    allowed = os.path.abspath(target)
    for path in touched:
        abs_path = os.path.abspath(path)
        assert abs_path == allowed or abs_path.startswith(allowed + ".bak-"), path
    assert not any("accounts.json" in p for p in touched)


# ------------------------------------------------------------------ per-op verdicts


def test_grep_refuses_to_clobber_a_different_existing_entry():
    cfg = m.load_config(FIXTURE)
    cfg["mcpServers"]["grep"] = {"type": "stdio", "command": "grep-mcp"}
    result = m.op_grep(cfg)
    assert result.status == m.Status.CONFLICT
    assert not result.changes


def test_grep_is_a_no_op_when_already_identical():
    cfg = m.load_config(FIXTURE)
    cfg["mcpServers"]["grep"] = dict(m.GREP_ENTRY)
    assert m.op_grep(cfg).status == m.Status.NOOP


def test_playwright_is_na_when_the_server_is_absent():
    cfg = m.load_config(FIXTURE)
    del cfg["mcpServers"]["playwright"]
    assert m.op_playwright(cfg).status == m.Status.NA


def test_playwright_refuses_an_entry_with_no_args_list():
    cfg = m.load_config(FIXTURE)
    cfg["mcpServers"]["playwright"] = {"type": "http", "url": "http://x"}
    assert m.op_playwright(cfg).status == m.Status.CONFLICT


def test_playwright_preflight_states_the_extension_prerequisite():
    cfg = m.load_config(FIXTURE)
    assert any("PREREQUISITE" in line for line in m.op_playwright(cfg).detail)


def test_serena_root_is_a_no_op_when_already_enabled():
    cfg = m.load_config(FIXTURE)
    cfg["disabledMcpServers"] = ["angr"]
    assert m.op_serena_root(cfg).status == m.Status.NOOP


def test_serena_root_is_na_without_the_list():
    cfg = m.load_config(FIXTURE)
    del cfg["disabledMcpServers"]
    assert m.op_serena_root(cfg).status == m.Status.NA


def test_serena_projects_is_na_when_nothing_is_scoped():
    cfg = m.load_config(FIXTURE)
    assert m.op_serena_projects(cfg, ["no-such-repo"]).status == m.Status.NA


def test_preflight_counts_the_untouched_blocks_that_keep_serena_disabled():
    cfg = m.load_config(FIXTURE)
    detail = m.op_serena_projects(cfg, m.DEFAULT_SCOPED_REPOS).detail
    assert any("3 project blocks KEEP serena disabled" in line for line in detail)


def test_apply_plan_never_mutates_the_input_config():
    cfg = m.load_config(FIXTURE)
    snapshot = json.dumps(cfg, sort_keys=True)
    plan = m.build_plan(cfg, list(m.OP_NAMES), m.DEFAULT_SCOPED_REPOS)
    m.apply_plan(cfg, plan)
    assert json.dumps(cfg, sort_keys=True) == snapshot


def test_main_entrypoint_wires_argv(target, closed, capsys):
    assert m.main(["--target", target, "--list"]) == 0
    assert "LIVE STATE" in capsys.readouterr().out
