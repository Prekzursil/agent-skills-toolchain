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

DEMO_PROBE = lp.Probe(monitor="demo", argv_tail=(), require=MARKER, timeout_s=60.0)


@pytest.fixture
def policy(monkeypatch: pytest.MonkeyPatch):
    """Point the gate's launch policy at the throwaway `[demo]` stanza."""

    def apply(probes=(DEMO_PROBE,), exempt=None):
        monkeypatch.setattr(lp, "PROBES", tuple(probes))
        monkeypatch.setattr(lp, "EXEMPT", dict(exempt or {}))

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
