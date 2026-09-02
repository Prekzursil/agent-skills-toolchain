#!/usr/bin/env python3
"""Tests for tools/plugin/deploy_provenance.py (IMP-0033).

Runnable standalone (``python3 -B tools/plugin/tests/test_deploy_provenance.py``) and
under pytest.  Every test deploys a committed throwaway plugin into a throwaway HOME;
nothing touches the real ``~/.claude``.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
REPO = PLUGIN.parents[1]
sys.path.insert(0, str(PLUGIN))

import deploy_provenance as dp  # noqa: E402


class _Deployed:
    def __init__(self, root: Path) -> None:
        self.src = root / "src"
        self.home = root / "home"
        self.home.mkdir()
        self.planted = dp.plant_throwaway_plugin(self.src)
        self.git_dir = Path(self.planted["git_dir"])
        self.deployed = dp.deploy_all_via_scripts(
            repo=self.src, home=self.home, git_dir=self.git_dir, worktree=REPO
        )


def _fresh() -> tuple[tempfile.TemporaryDirectory, _Deployed]:
    td = tempfile.TemporaryDirectory(prefix="imp0033-test-")
    return td, _Deployed(Path(td.name))


def test_every_deployed_file_has_a_verifiable_blob() -> None:
    td, d = _fresh()
    with td:
        ledger = json.loads((d.home / dp.LEDGER_REL).read_text(encoding="utf-8"))
        assert ledger["artifact"] == "deploy-provenance"
        assert ledger["record_count"] == d.planted["n_deployable"] == d.deployed["placed"]
        assert dp.validate_ledger(ledger) == []
        for rec in ledger["records"]:
            live = (d.home / rec["live_path"]).read_bytes()
            blob = dp.git_cat_file_p(d.git_dir, rec["source_blob_sha"])
            assert blob == live, rec["live_path"]
            assert hashlib.sha256(live).hexdigest() == rec["content_sha256"]
            assert dp.blob_id(live) == rec["source_blob_sha"]
            assert rec["version"] == d.planted["plugin_version"] == "0.0.0-test"
            assert rec["mode"] == "copy"
        result = dp.verify_deployed(d.home, d.git_dir)
        assert result.clean, result.as_dict()
        assert result.verified == sorted(r["live_path"] for r in ledger["records"])
        assert result.catfile_hash_ok == result.blob_sha_ok == result.verified


def test_independent_walk_matches_ledger_exactly() -> None:
    td, d = _fresh()
    with td:
        ledger = dp.load_ledger(d.home)
        recorded = sorted(r["live_path"] for r in ledger["records"])
        assert dp.walk_live_family_files(d.home) == recorded
        assert ".claude/skills/alpha/SKILL.md" in recorded
        assert ".claude/skills/bravo/SKILL.md" in recorded
        assert dp.LEDGER_REL not in recorded  # the ledger describes, it is not a payload


def test_hand_edit_names_exactly_that_file() -> None:
    td, d = _fresh()
    with td:
        target = d.home / ".claude/skills/alpha/SKILL.md"
        original = target.read_bytes()
        target.write_bytes(original + b"HAND-EDIT\n")
        dirty = dp.verify_deployed(d.home, d.git_dir)
        assert dirty.unverified == [".claude/skills/alpha/SKILL.md"]
        assert not dirty.clean
        assert not dirty.missing_record and not dirty.missing_file
        assert len(dirty.verified) == d.planted["n_deployable"] - 1
        target.write_bytes(original)
        assert dp.verify_deployed(d.home, d.git_dir).clean


def test_copy_without_place_file_fails_completeness_walk() -> None:
    td, d = _fresh()
    with td:
        rogue = d.home / ".claude/hooks/rogue.sh"
        shutil.copy2(d.src / "hooks" / "pre.sh", rogue)
        result = dp.verify_deployed(d.home, d.git_dir)
        assert result.missing_record == [".claude/hooks/rogue.sh"]
        assert not result.clean
        rogue.unlink()
        assert dp.verify_deployed(d.home, d.git_dir).clean


def test_deleted_live_file_is_missing_file() -> None:
    td, d = _fresh()
    with td:
        (d.home / ".claude/rules/common/harness-vcs-hygiene.md").unlink()
        result = dp.verify_deployed(d.home, d.git_dir)
        assert result.missing_file == [".claude/rules/common/harness-vcs-hygiene.md"]
        assert not result.clean


def test_place_file_is_sole_live_writer_gate() -> None:
    gate = dp.live_write_callees()
    assert gate["place_file_is_sole_live_writer"] is True
    assert gate["atomic_write_callers"] == ["place_file"]
    assert gate["unexpected_writers"] == []
    # Negative control: a second writer in the module text must trip the gate.
    rogue_src = Path(dp.__file__).read_text(encoding="utf-8") + (
        "\n\ndef rogue_writer(home, rel, data):\n"
        "    (home / rel).write_bytes(data)\n"
    )
    tripped = dp.live_write_callees(rogue_src)
    assert tripped["place_file_is_sole_live_writer"] is False
    assert tripped["unexpected_writers"] == ["rogue_writer"]
    second_caller = Path(dp.__file__).read_text(encoding="utf-8") + (
        "\n\ndef bypass(home, rel, data):\n    _atomic_write(home / rel, data)\n"
    )
    assert dp.live_write_callees(second_caller)["atomic_write_callers"] == ["bypass", "place_file"]


def test_control_plane_scripts_name_the_engine_and_refuse_when_they_do_not() -> None:
    plan = dp.control_plane(REPO)
    assert [p["family"] for p in plan] == ["skills", "hooks", "rules"]
    assert all(p["names_engine"] and p["provenance_switch"] for p in plan)
    with tempfile.TemporaryDirectory(prefix="imp0033-cp-") as td:
        fake = Path(td)
        (fake / "scripts").mkdir()
        for fam in dp.FAMILIES.values():
            shutil.copy2(REPO / fam.script, fake / fam.script)
        # Strip the engine from one script: the deploy must refuse, not silently copy.
        hooks = fake / "scripts/sync-hooks.ps1"
        hooks.write_text(
            hooks.read_text(encoding="utf-8").replace("deploy_provenance.py", "nothing.py"),
            encoding="utf-8",
        )
        try:
            dp.control_plane(fake)
        except dp.ControlPlaneError as exc:
            assert "sync-hooks.ps1" in str(exc)
        else:
            raise AssertionError("control_plane accepted a script that no longer names the engine")


def test_ledger_schema_rejects_bad_documents() -> None:
    td, d = _fresh()
    with td:
        doc = dp.load_ledger(d.home)
        bad = json.loads(json.dumps(doc))
        bad["records"][0]["source_blob_sha"] = "nothex"
        bad["records"][1]["mode"] = "teleport"
        bad["extra"] = 1
        problems = dp.validate_ledger(bad)
        assert any("source_blob_sha" in p for p in problems)
        assert any("mode" in p for p in problems)
        assert any("extra" in p for p in problems)
        short = json.loads(json.dumps(doc))
        short["record_count"] = 0
        assert any("record_count" in p for p in dp.validate_ledger(short))


def test_place_file_refuses_escaping_home() -> None:
    with tempfile.TemporaryDirectory(prefix="imp0033-esc-") as td:
        try:
            dp.place_file(Path(td), "../escape.txt", b"x")
        except dp.ProvenanceError:
            pass
        else:
            raise AssertionError("place_file wrote outside HOME")
        assert not (Path(td).parent / "escape.txt").exists()


TESTS = [
    test_every_deployed_file_has_a_verifiable_blob,
    test_independent_walk_matches_ledger_exactly,
    test_hand_edit_names_exactly_that_file,
    test_copy_without_place_file_fails_completeness_walk,
    test_deleted_live_file_is_missing_file,
    test_place_file_is_sole_live_writer_gate,
    test_control_plane_scripts_name_the_engine_and_refuse_when_they_do_not,
    test_ledger_schema_rejects_bad_documents,
    test_place_file_refuses_escaping_home,
]


def main() -> int:
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001 - report every failure, keep going
            failed += 1
            print(f"FAIL {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
