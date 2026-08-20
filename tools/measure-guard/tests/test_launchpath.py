"""Both-states controls for the registered-monitor launch gate.

Every "the gate is quiet" assertion here is paired with a case that makes the SAME gate fire, so
a quiet reading means something. A probe that is silent in the broken state measures nothing.

The single most important case is `test_the_gate_reads_the_commit_not_the_working_tree`, in both
directions: a repo whose COMMITTED entry crashes must be reported RED even after the working-tree
copy is repaired, and a repo whose committed entry is good must stay GREEN even after the
working-tree copy is broken. That is the whole reason this gate reads blobs - `git archive` and a
plain worktree read both answer a question CI never asks on this Windows box.

`core.autocrlf` is forced OFF in every throwaway repo. That is a detector control, not tidiness:
this box has `core.autocrlf=true` globally, which normalises CRLF to LF at `git add`, so the
byte-exactness test would pass while comparing two LF blobs and proving nothing.

Nothing here touches this repository: `commit_all` uses `git add -A`, banned against the shared
worktree and correct here, because every call targets a fresh repo under `tmp_path`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import launchpath as lp  # noqa: E402
from conftest import commit_all as _commit  # noqa: E402
from conftest import make_git_repo  # noqa: E402

REGISTRY = "skills/monitor-launcher/monitors.toml"
SKILL_DIR = "skills/demo-skill"
MARKER = "DEMO-BOARD-RENDERED"

GOOD_ENTRY = f'print("{MARKER}")\n'
SILENT_ENTRY = "import sys\n\nsys.exit(0)\n"
CRASHING_ENTRY = "import nonexistent_module_xyz  # noqa: F401\n"
SLOW_ENTRY = "import time\n\ntime.sleep(30)\n"
NONZERO_RENDER = f'import sys\nprint("{MARKER}")\nsys.exit(1)\n'
HERMETIC_ENTRY = (
    f'RENDER_MARKER = "{MARKER}"\n'
    "import os\n"
    'if __name__ == "__main__":\n'
    '    dest = os.environ.get("EMON_SENTINEL", "SPAWNED")\n'
    '    open(dest, "w", encoding="utf-8").write("bad")\n'
    "    raise SystemExit(1)\n"
)

DEMO_PROBE = lp.Probe(monitor="demo", argv_tail=(), require=MARKER, timeout_s=60.0)
DEMO_HERMETIC = lp.Probe(
    monitor="demo",
    argv_tail=(),
    require=MARKER,
    mode="import_render",
    timeout_s=60.0,
)


@pytest.fixture
def policy(monkeypatch: pytest.MonkeyPatch):
    """Point the gate's launch policy at the throwaway `[demo]` stanza."""

    def apply(probes=(DEMO_PROBE,), exempt=None, hermetic=()):
        monkeypatch.setattr(lp, "PROBES", tuple(probes))
        monkeypatch.setattr(lp, "EXEMPT", dict(exempt or {}))
        # The shipped HERMETIC names [agentmon]; a throwaway [demo] registry
        # would otherwise look like a stale policy entry.
        monkeypatch.setattr(lp, "HERMETIC", tuple(hermetic))

    return apply


def _repo(tmp_path: Path) -> Path:
    root = make_git_repo(tmp_path / "r")
    subprocess.run(
        ["git", "-C", str(root), "config", "core.autocrlf", "false"],
        check=True,
        capture_output=True,
    )
    return root


def _plant(root: Path, rel: str, data: bytes) -> Path:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def _registry(
    stanzas: str = '[demo]\ndir = "demo-skill"\nentry = "board.py"\n',
) -> bytes:
    return stanzas.encode("utf-8")


def _fixture_repo(
    tmp_path: Path, entry: str = GOOD_ENTRY, *, registry: bytes | None = None
) -> Path:
    root = _repo(tmp_path)
    _plant(root, REGISTRY, registry if registry is not None else _registry())
    _plant(root, f"{SKILL_DIR}/board.py", entry.encode("utf-8"))
    _commit(root)
    return root


# --------------------------------------------------------------------------------------------
# the green leg, and the three broken legs that must NOT be green
# --------------------------------------------------------------------------------------------


def test_a_registered_entry_that_renders_passes(tmp_path: Path, policy) -> None:
    policy()
    result = lp.scan(_fixture_repo(tmp_path))
    assert result.ok, result.findings
    assert len(result.launched) == 1
    assert "[demo]" in result.launched[0]


def test_an_entry_that_exits_zero_without_rendering_is_a_finding(
    tmp_path: Path, policy
) -> None:
    """The silent-no-op shape: exit 0, no output, no error - every byte-level gate stays green."""
    policy()
    result = lp.scan(_fixture_repo(tmp_path, SILENT_ENTRY))
    assert not result.ok
    assert "lacks" in result.findings[0]


def test_an_entry_that_crashes_on_import_is_a_finding(tmp_path: Path, policy) -> None:
    policy()
    result = lp.scan(_fixture_repo(tmp_path, CRASHING_ENTRY))
    assert not result.ok
    assert "did NOT launch" in result.findings[0]
    assert "exit 1" in result.findings[0]


def test_an_entry_that_hangs_is_a_finding_not_a_hang(tmp_path: Path, policy) -> None:
    policy(
        probes=(lp.Probe(monitor="demo", argv_tail=(), require=MARKER, timeout_s=1.0),)
    )
    result = lp.scan(_fixture_repo(tmp_path, SLOW_ENTRY))
    assert not result.ok
    assert "timed out" in result.findings[0]


def test_empty_dir_token_becomes_an_existing_empty_directory(tmp_path: Path) -> None:
    entry = tmp_path / "argv.py"
    entry.write_text(
        "import pathlib, sys\n"
        "p = pathlib.Path(sys.argv[1])\n"
        "print(f'ARG={p};DIR={p.is_dir()};COUNT={len(list(p.iterdir()))}')\n",
        encoding="utf-8",
    )
    ok, detail = lp.run_probe(
        entry, lp.Probe("demo", (lp.EMPTY_DIR,), "DIR=True;COUNT=0"), tmp_path
    )
    assert ok, detail
    created = list(tmp_path.glob("empty-*"))
    assert len(created) == 1
    assert created[0].is_dir() and not list(created[0].iterdir())
    assert lp.EMPTY_DIR not in created[0].as_posix()


def test_two_empty_dir_tokens_become_distinct_directories(tmp_path: Path) -> None:
    entry = tmp_path / "argv.py"
    entry.write_text(
        "import sys\nprint('DISTINCT' if sys.argv[1] != sys.argv[2] else 'ALIASED')\n",
        encoding="utf-8",
    )
    ok, detail = lp.run_probe(
        entry,
        lp.Probe("demo", (lp.EMPTY_DIR, lp.EMPTY_DIR), "DISTINCT"),
        tmp_path,
    )
    assert ok, detail
    assert len(list(tmp_path.glob("empty-*"))) == 2


def test_probe_without_empty_dir_token_is_unchanged(tmp_path: Path) -> None:
    entry = tmp_path / "argv.py"
    entry.write_text("import sys\nprint('|'.join(sys.argv[1:]))\n", encoding="utf-8")
    ok, detail = lp.run_probe(
        entry, lp.Probe("demo", ("alpha", "beta"), "alpha|beta"), tmp_path
    )
    assert ok, detail
    assert not list(tmp_path.glob("empty-*"))


# --------------------------------------------------------------------------------------------
# the reason the gate exists: it must grade the COMMIT, not this box's working tree
# --------------------------------------------------------------------------------------------


def test_the_gate_reads_the_commit_not_the_working_tree(tmp_path: Path, policy) -> None:
    policy()
    # Direction 1: committed-good, worktree-broken -> still GREEN.
    good = _fixture_repo(tmp_path / "a", GOOD_ENTRY)
    (good / SKILL_DIR / "board.py").write_bytes(CRASHING_ENTRY.encode("utf-8"))
    assert lp.scan(good).ok, (
        "a worktree-only break must not fail a gate that grades the commit"
    )

    # Direction 2: committed-broken, worktree-repaired -> still RED.
    bad = _fixture_repo(tmp_path / "b", CRASHING_ENTRY)
    (bad / SKILL_DIR / "board.py").write_bytes(GOOD_ENTRY.encode("utf-8"))
    assert not lp.scan(bad).ok, "a worktree-only repair must not turn the gate green"


def test_read_blobs_returns_stored_bytes_including_crlf(tmp_path: Path) -> None:
    """`git archive` converts EOLs on Windows; this route must not. Control: the OIDs differ."""
    root = _repo(tmp_path)
    _plant(root, "lf.txt", b"a\nb\n")
    _plant(root, "crlf.txt", b"a\r\nb\r\n")
    _commit(root)
    oids = lp.index_oids(root)
    assert oids["lf.txt"] != oids["crlf.txt"], (
        "autocrlf normalised the fixture; control failed"
    )
    blobs = lp.read_blobs(root, [oids["lf.txt"], oids["crlf.txt"]])
    assert blobs[oids["crlf.txt"]] == b"a\r\nb\r\n"
    assert blobs[oids["lf.txt"]] == b"a\nb\n"


# --------------------------------------------------------------------------------------------
# the registry itself
# --------------------------------------------------------------------------------------------


def test_an_untracked_entry_is_a_finding(tmp_path: Path, policy) -> None:
    policy()
    root = _repo(tmp_path)
    _plant(root, REGISTRY, _registry())
    _plant(root, f"{SKILL_DIR}/other.py", b"print('x')\n")
    _commit(root)
    _plant(
        root, f"{SKILL_DIR}/board.py", GOOD_ENTRY.encode("utf-8")
    )  # present but NEVER committed
    result = lp.scan(root)
    assert not result.ok
    assert "UNTRACKED" in result.findings[0]


def test_a_skill_dir_with_no_tracked_files_is_a_finding(tmp_path: Path, policy) -> None:
    policy()
    root = _repo(tmp_path)
    _plant(root, REGISTRY, _registry())
    _plant(root, "keep.txt", b"x\n")
    _commit(root)
    result = lp.scan(root)
    assert not result.ok
    assert "ZERO tracked files" in result.findings[0]


def test_a_stanza_that_is_neither_probed_nor_exempt_fails(
    tmp_path: Path, policy
) -> None:
    policy()
    extra = '[demo]\ndir = "demo-skill"\nentry = "board.py"\n\n[newcomer]\ndir = "d"\nentry = "e.py"\n'
    result = lp.scan(_fixture_repo(tmp_path, registry=_registry(extra)))
    assert not result.ok
    assert any("neither probed nor exempt" in f for f in result.findings)


def test_an_exempt_stanza_is_accounted_for_and_not_launched(
    tmp_path: Path, policy
) -> None:
    policy(exempt={"newcomer": "declared reason"})
    extra = '[demo]\ndir = "demo-skill"\nentry = "board.py"\n\n[newcomer]\ndir = "d"\nentry = "e.py"\n'
    result = lp.scan(_fixture_repo(tmp_path, registry=_registry(extra)))
    assert result.ok, result.findings
    assert result.exempted == ["newcomer"]


def test_a_policy_entry_naming_a_vanished_stanza_fails(tmp_path: Path, policy) -> None:
    policy(exempt={"retired": "reason kept after the stanza was deleted"})
    result = lp.scan(_fixture_repo(tmp_path))
    assert not result.ok
    assert any("gone stale" in f for f in result.findings)


def test_a_stanza_without_string_dir_or_entry_is_a_finding(
    tmp_path: Path, policy
) -> None:
    policy()
    result = lp.scan(_fixture_repo(tmp_path, registry=_registry("[demo]\ndir = 3\n")))
    assert not result.ok
    assert "no string dir/entry" in result.findings[0]


# --------------------------------------------------------------------------------------------
# fail closed: "0 findings" must be unreachable by having found nothing to run
# --------------------------------------------------------------------------------------------


def test_zero_registries_raises_rather_than_reporting_green(
    tmp_path: Path, policy
) -> None:
    policy()
    root = _repo(tmp_path)
    _plant(root, "readme.md", b"no registry here\n")
    _commit(root)
    with pytest.raises(lp.LaunchPathError, match="discovery is broken"):
        lp.scan(root)


def test_an_empty_index_raises(tmp_path: Path) -> None:
    with pytest.raises(lp.LaunchPathError, match="listed NOTHING"):
        lp.index_oids(_repo(tmp_path))


def test_a_registry_with_zero_stanzas_raises(tmp_path: Path, policy) -> None:
    policy()
    with pytest.raises(lp.LaunchPathError, match="ZERO stanzas"):
        lp.scan(_fixture_repo(tmp_path, registry=_registry("# only a comment\n")))


def test_an_unparseable_registry_raises(tmp_path: Path, policy) -> None:
    policy()
    with pytest.raises(lp.LaunchPathError, match="not parseable as TOML"):
        lp.scan(_fixture_repo(tmp_path, registry=_registry("[demo\n")))


def test_index_oids_on_a_non_repo_raises(tmp_path: Path) -> None:
    bare = tmp_path / "nogit"
    bare.mkdir()
    with pytest.raises(lp.LaunchPathError):
        lp.index_oids(bare)


def test_read_blobs_rejects_an_unknown_oid(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _plant(root, "a.txt", b"x\n")
    _commit(root)
    with pytest.raises(lp.LaunchPathError):
        lp.read_blobs(root, ["0" * 40])


def test_read_blobs_of_nothing_is_empty_not_an_error(tmp_path: Path) -> None:
    assert lp.read_blobs(_repo(tmp_path), []) == {}


# --------------------------------------------------------------------------------------------
# discovery rules, with the positive control that the matcher fires
# --------------------------------------------------------------------------------------------


def test_the_registry_suffix_excludes_a_test_fixture_and_includes_a_real_mirror() -> (
    None
):
    oids = {
        "skills/monitor-launcher/monitors.toml": "a",
        ".agents/skills/monitor-launcher/monitors.toml": "b",
        "tools/monitorcore/tests/fixtures/monitors.toml": "c",  # a FIXTURE, not a registry
    }
    found = lp.registry_paths(oids)
    assert found == [
        ".agents/skills/monitor-launcher/monitors.toml",
        "skills/monitor-launcher/monitors.toml",
    ]
    assert "tools/monitorcore/tests/fixtures/monitors.toml" not in found


def test_skills_root_is_derived_per_mirror_not_hardcoded() -> None:
    assert lp.skills_root("skills/monitor-launcher/monitors.toml") == "skills"
    assert (
        lp.skills_root(".agents/skills/monitor-launcher/monitors.toml")
        == ".agents/skills"
    )


def test_both_mirrors_are_measured_independently(tmp_path: Path, policy) -> None:
    """One mirror good, the other stale: the gate must report the stale one, not average them."""
    policy()
    root = _repo(tmp_path)
    _plant(root, REGISTRY, _registry())
    _plant(root, f"{SKILL_DIR}/board.py", GOOD_ENTRY.encode("utf-8"))
    _plant(root, f".agents/{REGISTRY}", _registry())
    _plant(root, f".agents/{SKILL_DIR}/board.py", CRASHING_ENTRY.encode("utf-8"))
    _commit(root)
    result = lp.scan(root)
    assert len(result.registries) == 2
    assert len(result.launched) == 1
    assert not result.ok
    assert ".agents/" in result.findings[0]


# --------------------------------------------------------------------------------------------
# accept_nonzero (csmon renders then exits 1) and import-render (agentmon must not exec)
# --------------------------------------------------------------------------------------------


def test_nonzero_exit_with_marker_passes_when_accepted(tmp_path: Path, policy) -> None:
    policy(
        probes=(
            lp.Probe(
                monitor="demo",
                argv_tail=(),
                require=MARKER,
                accept_nonzero=True,
                timeout_s=60.0,
            ),
        )
    )
    result = lp.scan(_fixture_repo(tmp_path, NONZERO_RENDER))
    assert result.ok, result.findings
    assert "nonzero accepted" in result.launched[0]


def test_nonzero_exit_without_marker_is_a_finding_even_when_accepted(
    tmp_path: Path, policy
) -> None:
    policy(
        probes=(
            lp.Probe(
                monitor="demo",
                argv_tail=(),
                require=MARKER,
                accept_nonzero=True,
                timeout_s=60.0,
            ),
        )
    )
    result = lp.scan(
        _fixture_repo(tmp_path, SILENT_ENTRY.replace("sys.exit(0)", "sys.exit(1)"))
    )
    assert not result.ok
    assert "lacks" in result.findings[0]


def test_hermetic_import_render_passes_without_running_main(
    tmp_path: Path, policy, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = tmp_path / "SPAWNED"
    monkeypatch.setenv("EMON_SENTINEL", str(sentinel))
    policy(probes=(), hermetic=(DEMO_HERMETIC,))
    root = _fixture_repo(tmp_path, HERMETIC_ENTRY)
    result = lp.scan(root)
    assert result.ok, result.findings
    assert "import-render marker present" in result.launched[0]
    assert not sentinel.exists(), (
        "__main__ ran; the hermetic probe opened the side-effecting path"
    )


def test_hermetic_import_render_is_red_when_marker_missing(
    tmp_path: Path, policy
) -> None:
    policy(probes=(), hermetic=(DEMO_HERMETIC,))
    result = lp.scan(_fixture_repo(tmp_path, 'RENDER_MARKER = "NOPE"\n'))
    assert not result.ok
    assert "lacks" in result.findings[0]


def test_hermetic_import_render_is_red_when_import_crashes(
    tmp_path: Path, policy
) -> None:
    policy(probes=(), hermetic=(DEMO_HERMETIC,))
    result = lp.scan(_fixture_repo(tmp_path, CRASHING_ENTRY))
    assert not result.ok
    assert "import-render" in result.findings[0]


def test_wfmon_named_driver_prints_title_without_app_run(tmp_path: Path) -> None:
    """The wfmon driver imports the module; it must never call App.run / main."""
    skill = tmp_path / "workflow-monitor"
    skill.mkdir()
    (skill / "workflow_run.py").write_text(
        "def iter_manifest_paths(projects):\n    return []\n"
        "def parse_manifest(path):\n    return None\n"
        "def fleet_rollup(runs):\n    return {'runs': 0, 'active_runs': 0}\n",
        encoding="utf-8",
    )
    (skill / "workflow_monitor.py").write_text(
        "class WorkflowMonitor:\n"
        "    TITLE = 'Workflow Cockpit'\n"
        "def _run_label(run, now):\n"
        "    return 'label'\n"
        "def main():\n"
        "    raise SystemExit('wfmon main ran')\n",
        encoding="utf-8",
    )
    ok, detail = lp.run_import_render(
        skill / "workflow_monitor.py",
        lp.Probe(
            monitor="wfmon",
            argv_tail=(),
            require="Workflow Cockpit",
            mode="import_render",
            timeout_s=30.0,
        ),
        tmp_path,
    )
    assert ok, detail


def test_wfmon_named_driver_is_red_when_title_missing(tmp_path: Path) -> None:
    skill = tmp_path / "workflow-monitor"
    skill.mkdir()
    (skill / "workflow_run.py").write_text(
        "def iter_manifest_paths(projects):\n    return []\n"
        "def parse_manifest(path):\n    return None\n"
        "def fleet_rollup(runs):\n    return {'runs': 0, 'active_runs': 0}\n",
        encoding="utf-8",
    )
    (skill / "workflow_monitor.py").write_text(
        "class WorkflowMonitor:\n    TITLE = 'MUTANT COCKPIT'\n",
        encoding="utf-8",
    )
    ok, detail = lp.run_import_render(
        skill / "workflow_monitor.py",
        lp.Probe(
            monitor="wfmon",
            argv_tail=(),
            require="Workflow Cockpit",
            mode="import_render",
            timeout_s=30.0,
        ),
        tmp_path,
    )
    assert not ok
    assert "lacks" in detail


def test_csmon_named_driver_renders_without_main(tmp_path: Path) -> None:
    entry = tmp_path / "cs_monitor.py"
    entry.write_text(
        "def render(status, doctor, errors, cs):\n"
        "    return '  Claude Science - csmon  (fixture)\\n  NOT-CHECKED rows'\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit('csmon main ran')\n",
        encoding="utf-8",
    )
    ok, detail = lp.run_import_render(
        entry,
        lp.Probe(
            monitor="csmon",
            argv_tail=(),
            require="Claude Science - csmon",
            mode="import_render",
            timeout_s=30.0,
        ),
        tmp_path,
    )
    assert ok, detail


def test_csmon_named_driver_is_red_on_failed_locate_string(tmp_path: Path) -> None:
    """The live entry prints FAILED:csmon when cs.ps1 is missing. That is not a render."""
    entry = tmp_path / "cs_monitor.py"
    entry.write_text(
        "def render(status, doctor, errors, cs):\n"
        "    return 'FAILED:csmon cannot locate cs.ps1 - nothing was measured'\n",
        encoding="utf-8",
    )
    ok, detail = lp.run_import_render(
        entry,
        lp.Probe(
            monitor="csmon",
            argv_tail=(),
            require="Claude Science - csmon",
            mode="import_render",
            timeout_s=30.0,
        ),
        tmp_path,
    )
    assert not ok
    assert "lacks" in detail


def test_hermetic_extra_dirs_are_materialised(tmp_path: Path, policy) -> None:
    policy(
        probes=(),
        hermetic=(
            lp.Probe(
                monitor="demo",
                argv_tail=(),
                require=MARKER,
                mode="import_render",
                extra_dirs=("workflow-monitor",),
                timeout_s=30.0,
            ),
        ),
    )
    root = _repo(tmp_path)
    _plant(root, REGISTRY, _registry())
    _plant(
        root,
        f"{SKILL_DIR}/board.py",
        (
            "import sys\n"
            "from pathlib import Path\n"
            "sib = Path(__file__).resolve().parent.parent / 'workflow-monitor'\n"
            "sys.path.insert(0, str(sib))\n"
            "import helper\n"
            "RENDER_MARKER = helper.MARKER\n"
        ).encode("utf-8"),
    )
    _plant(
        root,
        "skills/workflow-monitor/helper.py",
        f'MARKER = "{MARKER}"\n'.encode("utf-8"),
    )
    _commit(root)
    result = lp.scan(root)
    assert result.ok, result.findings


def test_hermetic_extra_dirs_missing_is_a_finding(tmp_path: Path, policy) -> None:
    """Same entry as the extra_dirs green leg, but the sibling is never committed."""
    policy(
        probes=(),
        hermetic=(
            lp.Probe(
                monitor="demo",
                argv_tail=(),
                require=MARKER,
                mode="import_render",
                extra_dirs=("workflow-monitor",),
                timeout_s=30.0,
            ),
        ),
    )
    root = _repo(tmp_path)
    _plant(root, REGISTRY, _registry())
    _plant(
        root,
        f"{SKILL_DIR}/board.py",
        (
            "import sys\n"
            "from pathlib import Path\n"
            "sib = Path(__file__).resolve().parent.parent / 'workflow-monitor'\n"
            "sys.path.insert(0, str(sib))\n"
            "import helper\n"
            "RENDER_MARKER = helper.MARKER\n"
        ).encode("utf-8"),
    )
    _commit(root)
    result = lp.scan(root)
    assert not result.ok
    assert "import-render" in result.findings[0]


def test_shipped_policy_covers_committed_registry_stanzas() -> None:
    """Both registry mirrors, every stanza: exec / import-render / NOT-CHECKED."""
    oids = lp.index_oids(lp.REPO)
    registries = lp.registry_paths(oids)
    assert registries, "detector control: the real repo must have registry mirrors"
    blobs = lp.read_blobs(lp.REPO, {oids[path] for path in registries})
    expected = {"wfmon", "agentmon", "codexmon", "crcp", "csmon", "cockpit"}
    accounted = {probe.monitor for probe in lp.all_probes()} | set(lp.EXEMPT)
    assert accounted == expected
    for registry in registries:
        stanzas = set(lp.parse_stanzas(blobs[oids[registry]], registry))
        assert stanzas == expected, registry
    exec_names = {probe.monitor for probe in lp.PROBES}
    hermetic_names = {probe.monitor for probe in lp.HERMETIC}
    assert exec_names.isdisjoint({"wfmon", "agentmon", "crcp"})
    assert hermetic_names == {"agentmon", "csmon"}
    assert set(lp.EXEMPT) == {"wfmon", "crcp"}
    assert exec_names.isdisjoint(hermetic_names)
    assert hermetic_names.isdisjoint(set(lp.EXEMPT))
    assert all(probe.mode == "import_render" for probe in lp.HERMETIC)
    csmon = next(probe for probe in lp.HERMETIC if probe.monitor == "csmon")
    assert csmon.require == "Claude Science - csmon"
    assert csmon.require != "csmon"


def test_not_checked_is_printed_and_is_not_called_pass(
    tmp_path: Path, policy, capsys: pytest.CaptureFixture[str]
) -> None:
    policy(exempt={"newcomer": "declared reason"})
    extra = (
        '[demo]\ndir = "demo-skill"\nentry = "board.py"\n\n'
        '[newcomer]\ndir = "d"\nentry = "e.py"\n'
    )
    code = lp.main(["--repo", str(_fixture_repo(tmp_path, registry=_registry(extra)))])
    out = capsys.readouterr().out
    assert code == 0
    assert "NOT-CHECKED [newcomer]: declared reason" in out
    assert "NOT-CHECKED (not PASS)" in out
    assert "stanza(s) exempt" not in out


# --------------------------------------------------------------------------------------------
# CLI surface
# --------------------------------------------------------------------------------------------


def test_cli_prints_a_terminal_marker_and_exits_zero(
    tmp_path: Path, policy, capsys: pytest.CaptureFixture[str]
) -> None:
    policy()
    code = lp.main(["--repo", str(_fixture_repo(tmp_path))])
    assert code == 0
    assert "SUCCESS:launchpath" in capsys.readouterr().out


def test_cli_prints_a_failed_marker_and_exits_one(
    tmp_path: Path, policy, capsys: pytest.CaptureFixture[str]
) -> None:
    policy()
    code = lp.main(["--repo", str(_fixture_repo(tmp_path, CRASHING_ENTRY))])
    assert code == 1
    assert "FAILED:launchpath" in capsys.readouterr().out


def test_cli_turns_a_discovery_collapse_into_a_failed_marker(
    tmp_path: Path, policy, capsys: pytest.CaptureFixture[str]
) -> None:
    policy()
    root = _repo(tmp_path)
    _plant(root, "readme.md", b"x\n")
    _commit(root)
    code = lp.main(["--repo", str(root)])
    assert code == 1
    assert "FAILED:launchpath" in capsys.readouterr().out


def test_cli_json_is_machine_readable(
    tmp_path: Path, policy, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    policy()
    code = lp.main(["--repo", str(_fixture_repo(tmp_path)), "--json"])
    out = capsys.readouterr().out
    # The terminal marker (AGENTS.md 4) is printed AFTER the payload and is not part of it, so a
    # caller splits on the closing brace rather than json.loads-ing the whole stream. Both halves
    # are asserted so neither can be dropped silently.
    split = out.rindex("}") + 1
    payload = json.loads(out[:split])
    assert code == 0
    assert payload["ok"] is True
    assert payload["registries"] == [REGISTRY]
    assert "SUCCESS:launchpath" in out[split:]
