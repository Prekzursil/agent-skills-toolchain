"""Both-state tests for the D-001 skill-surface reconciliation prerequisite."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from harness import install as install_mod
from harness import surface_reconciler as surface_mod
from harness.install import deploy
from harness.surface_reconciler import (
    LIVE_DAILY,
    LIVE_VAULT,
    REPO_CANONICAL,
    REPO_CLAUDE_ONLY,
    REPO_PROJECTION,
    ROOT_ARTIFACT,
    SURFACE_ORDER,
    SurfaceReadError,
    is_deploy_excluded,
    names_only_inventory,
    reconcile_inventories,
    reconcile_paths,
    scan_surface,
)


def _roots(tmp_path: Path) -> dict[str, Path]:
    roots = {surface: tmp_path / surface for surface in SURFACE_ORDER}
    for root in roots.values():
        root.mkdir(parents=True)
    return roots


def _skill(root: Path, name: str, body: str = "same\n") -> None:
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="" keeps an LF body LF on Windows too; without it write_text
    # translates "\n" -> "\r\n", which silently breaks byte-exact EOL fixtures
    # (e.g. the eol-only-skip test). The reconciler compares EOL-normalized, so
    # this only makes the on-disk bytes deterministic across platforms.
    path.write_text(body, encoding="utf-8", newline="")


def _skill_file(root: Path, name: str, rel: str, body: bytes) -> Path:
    path = root / name / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def _records(report: dict[str, object]) -> dict[str, dict[str, object]]:
    return {record["skill"]: record for record in report["records"]}


def _signature(roots: dict[str, Path]) -> str:
    digest = hashlib.sha256()
    for surface in SURFACE_ORDER:
        root = roots[surface]
        for path in sorted(root.rglob("*")):
            if not (path.is_file() or path.is_symlink()):
                continue
            digest.update(surface.encode())
            digest.update(path.relative_to(root).as_posix().encode())
            if path.is_symlink():
                digest.update(b"symlink\0")
                digest.update(os.readlink(path).encode())
            else:
                digest.update(b"file\0")
                digest.update(path.read_bytes())
    return digest.hexdigest()


def _aligned_roots(tmp_path: Path) -> dict[str, Path]:
    roots = _roots(tmp_path)
    for surface in (REPO_CANONICAL, REPO_PROJECTION, LIVE_VAULT):
        _skill(roots[surface], "shared")
    return roots


def test_known_present_control_classifies_every_one_sided_surface(
    tmp_path: Path,
) -> None:
    """Known broken: the old coverage scan emitted live-minus-repo only."""
    roots = _aligned_roots(tmp_path)
    _skill(roots[REPO_CANONICAL], "canonical-only")
    _skill(roots[REPO_PROJECTION], "projection-only")
    _skill(roots[LIVE_VAULT], "known-live-only")

    report = reconcile_paths(roots)
    by_name = _records(report)

    assert report["verdict"] == "ROUTE"
    assert report["control"]["ok"] is True
    assert report["all_names"] == [
        "canonical-only",
        "known-live-only",
        "projection-only",
        "shared",
    ]
    assert by_name["known-live-only"]["reasons"] == ["live-only"]
    assert "canonical-not-projected" in by_name["canonical-only"]["reasons"]
    assert "projection-without-authority" in by_name["projection-only"]["reasons"]
    assert by_name["shared"]["status"] == "ALIGNED"


def test_union_deduplicates_a_name_but_preserves_every_provenance(
    tmp_path: Path,
) -> None:
    """Known broken: the old set unions discarded which repo/live roots supplied a name."""
    roots = _roots(tmp_path)
    for surface in SURFACE_ORDER:
        _skill(roots[surface], "everywhere")

    report = reconcile_paths(roots)
    record = _records(report)["everywhere"]

    assert report["verdict"] == "CLEAN"
    assert report["counts"]["union"] == 1
    assert record["sources"] == list(SURFACE_ORDER)
    assert record["status"] == "ALIGNED"
    assert report["control"]["known_present"] == "__control_live_only__"


def test_one_sided_counts_route_without_mutating_or_authorizing_removal(
    tmp_path: Path,
) -> None:
    """Known broken: repo-only had no neutral, always-read-only report state."""
    roots = _roots(tmp_path)
    for surface in (REPO_CANONICAL, REPO_PROJECTION):
        _skill(roots[surface], "repo-only")
    _skill(roots[LIVE_DAILY], "live-only")
    before = _signature(roots)

    report = reconcile_paths(roots)

    assert _signature(roots) == before
    assert report["counts"]["repo_only"] == 1
    assert report["counts"]["live_only"] == 1
    assert report["policy"] == {
        "deletion_authorized": False,
        "overwrite_authorized": False,
        "winner_selected": False,
    }
    for finding in report["findings"]:
        route = str(finding["route"])
        assert not any(
            word in route for word in ("delete", "remove", "prune", "overwrite")
        )


def test_same_size_divergence_never_selects_the_newer_copy(tmp_path: Path) -> None:
    """Known broken: stable divergent live content was overwritten by the projection."""
    roots = _roots(tmp_path)
    _skill(roots[REPO_CANONICAL], "collision", "left\n")
    _skill(roots[REPO_PROJECTION], "collision", "rite\n")
    _skill(roots[LIVE_VAULT], "collision", "left\n")
    canonical = roots[REPO_CANONICAL] / "collision" / "SKILL.md"
    projection = roots[REPO_PROJECTION] / "collision" / "SKILL.md"
    os.utime(canonical, (1, 1))
    os.utime(projection, (2_000_000_000, 2_000_000_000))
    before = _signature(roots)

    record = _records(reconcile_paths(roots))["collision"]

    assert _signature(roots) == before
    assert record["status"] == "CONFLICT"
    assert record["route"] == "manual-merge"
    assert "content-conflict" in record["reasons"]
    assert len(set(record["fingerprints"].values())) == 2
    assert record["differences"][0]["path"] == "SKILL.md"
    assert len(set(record["differences"][0]["hashes"].values())) == 2
    assert "winner" not in record


def test_case_only_names_are_one_conflict_not_two_one_sided_rows(
    tmp_path: Path,
) -> None:
    """Known broken: exact-name sets missed a Windows case-insensitive collision."""
    roots = _roots(tmp_path)
    _skill(roots[REPO_CANONICAL], "Case-Skill")
    _skill(roots[REPO_PROJECTION], "case-skill")
    _skill(roots[LIVE_VAULT], "CASE-SKILL")

    report = reconcile_paths(roots)
    record = report["records"][0]

    assert report["counts"]["union"] == 1
    assert report["counts"]["case_mismatches"] == 1
    assert record["skill"] == "Case-Skill"
    assert record["status"] == "CONFLICT"
    assert record["route"] == "manual-rename"
    assert record["surface_names"] == {
        REPO_CANONICAL: ["Case-Skill"],
        REPO_PROJECTION: ["case-skill"],
        LIVE_VAULT: ["CASE-SKILL"],
    }


def test_empty_detector_refuses_to_claim_clean(tmp_path: Path) -> None:
    """Known broken: the old coverage scanner returned a normal zero for no live skills."""
    report = reconcile_paths(_roots(tmp_path))

    assert report["verdict"] == "FAILED"
    assert {error["problem"] for error in report["errors"]} == {
        "unvalidated-empty-inventory"
    }


def test_names_only_manifest_overlap_is_unverified_not_equal() -> None:
    """Known broken: name-set overlap used to be treated as covered and therefore silent."""
    file_hash = hashlib.sha256(b"body").hexdigest()
    inventories = {
        REPO_CANONICAL: {"shared": {"SKILL.md": file_hash}},
        REPO_PROJECTION: {"shared": {"SKILL.md": file_hash}},
        REPO_CLAUDE_ONLY: {},
        LIVE_VAULT: names_only_inventory(["shared"]),
        LIVE_DAILY: {},
    }

    report = reconcile_inventories(inventories)
    record = _records(report)["shared"]

    assert report["verdict"] == "ROUTE"
    assert record["status"] == "CONFLICT"
    assert record["route"] == "content-compare-required"
    assert record["fingerprints"][LIVE_VAULT] is None


def test_reconcile_skills_cli_is_read_only_json(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: install.py did not accept a read-only skill reconcile mode."""
    roots = _aligned_roots(tmp_path)
    before = _signature(roots)
    monkeypatch.setattr(install_mod, "_default_skill_surface_roots", lambda: roots)

    code = install_mod.main(["--reconcile-skills"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["schema"] == "skill-surface-reconcile/v1"
    assert payload["verdict"] == "CLEAN"
    assert payload["read_only"] is True
    assert _signature(roots) == before


def test_skills_deploy_routes_before_lock_backup_or_write(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: skills deploy acquired its write lock with no surface pass."""
    roots = _aligned_roots(tmp_path)
    _skill(roots[LIVE_VAULT], "live-only")
    backups = tmp_path / "backups"
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", backups)
    before = _signature(roots)

    code = deploy(
        source_dir=roots[REPO_PROJECTION],
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["reason"] == "surface_reconciliation_required"
    assert "live-only" in payload["reconciliation"]["all_names"]
    assert _signature(roots) == before
    assert not backups.exists()
    assert not (roots[LIVE_VAULT] / install_mod.DEPLOY_LOCK_NAME).exists()
    assert not (roots[LIVE_VAULT] / "installed.json").exists()


def test_skills_deploy_conflict_does_not_pick_projection_mtime(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: the projection always won a stable pre-existing content conflict."""
    roots = _aligned_roots(tmp_path)
    _skill(roots[REPO_PROJECTION], "shared", "newer\n")
    projection = roots[REPO_PROJECTION] / "shared" / "SKILL.md"
    os.utime(projection, (2_000_000_000, 2_000_000_000))
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")
    before = _signature(roots)

    code = deploy(
        source_dir=roots[REPO_PROJECTION],
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["reconciliation"]["counts"]["content_conflicts"] == 1
    assert _signature(roots) == before
    assert (roots[LIVE_VAULT] / "shared" / "SKILL.md").read_text() == "same\n"


def test_clean_skill_surfaces_reach_the_existing_deploy_path(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: deploy accepted no surface inventory before this contract."""
    roots = _aligned_roots(tmp_path)
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    code = deploy(
        source_dir=roots[REPO_PROJECTION],
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "deployed"
    assert payload["target"] == "skills"
    assert payload["surface_reconciled"] is True
    assert (roots[LIVE_VAULT] / "installed.json").is_file()


def test_root_artifact_divergence_blocks_deploy_before_write(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: a divergent root file was outside the old skill-only scan."""
    roots = _aligned_roots(tmp_path)
    for surface, body in (
        (REPO_CANONICAL, b"stable\n"),
        (REPO_PROJECTION, b"candidate\n"),
        (LIVE_VAULT, b"stable\n"),
    ):
        (roots[surface] / "ROOT.txt").write_bytes(body)
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    code = deploy(
        source_dir=roots[REPO_PROJECTION],
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
    )
    payload = json.loads(capsys.readouterr().out)
    root_record = _records(payload["reconciliation"])[ROOT_ARTIFACT]

    assert code == 1
    assert payload["reason"] == "surface_reconciliation_required"
    assert root_record["kind"] == "root-artifacts"
    assert root_record["status"] == "CONFLICT"
    assert root_record["differences"][0]["path"] == "ROOT.txt"
    assert (roots[LIVE_VAULT] / "ROOT.txt").read_bytes() == b"stable\n"
    assert not (tmp_path / "backups").exists()


def test_log_divergence_is_in_the_same_managed_universe_as_deploy(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: *.log was ignored by reconciliation but copied by deploy."""
    roots = _aligned_roots(tmp_path)
    for surface, body in (
        (REPO_CANONICAL, b"stable\n"),
        (REPO_PROJECTION, b"candidate\n"),
        (LIVE_VAULT, b"stable\n"),
    ):
        _skill_file(roots[surface], "shared", "state.log", body)
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    code = deploy(
        source_dir=roots[REPO_PROJECTION],
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert is_deploy_excluded("state.log") is False
    assert payload["reconciliation"]["counts"]["content_conflicts"] == 1
    assert (roots[LIVE_VAULT] / "shared" / "state.log").read_bytes() == b"stable\n"
    assert not (tmp_path / "backups").exists()


def test_edit_after_first_reconcile_is_revalidated_under_lock(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: an edit between reconciliation and PLAN was overwritten."""
    roots = _aligned_roots(tmp_path)
    live_skill = roots[LIVE_VAULT] / "shared" / "SKILL.md"
    backups = tmp_path / "backups"
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", backups)

    code = deploy(
        source_dir=roots[REPO_PROJECTION],
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
        _after_reconcile=lambda: live_skill.write_text("manual edit\n"),
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["reason"] == "surface_changed_after_reconciliation"
    assert payload["snapshots_changed"] is True
    assert payload["revalidation"]["verdict"] == "ROUTE"
    assert live_skill.read_text() == "manual edit\n"
    assert not backups.exists()
    assert not (roots[LIVE_VAULT] / "installed.json").exists()
    assert not (roots[LIVE_VAULT] / install_mod.DEPLOY_LOCK_NAME).exists()


def test_walk_error_fails_inventory_instead_of_looking_clean(
    tmp_path: Path, monkeypatch
) -> None:
    """Known broken: os.walk silently discarded unreadable subtrees."""
    root = tmp_path / "surface"
    _skill(root, "shared")

    def denied_walk(*_args, onerror=None, **_kwargs):
        assert onerror is not None
        onerror(PermissionError("denied"))
        yield  # pragma: no cover

    monkeypatch.setattr(surface_mod.os, "walk", denied_walk)

    with pytest.raises(SurfaceReadError, match="PermissionError"):
        scan_surface(root)


def test_aligned_directory_symlink_routes_without_following_it(tmp_path: Path) -> None:
    """Known broken: matching nested directory symlinks disappeared from the scan."""
    roots = _aligned_roots(tmp_path)
    for index, surface in enumerate((REPO_CANONICAL, REPO_PROJECTION, LIVE_VAULT)):
        excluded = roots[surface] / ".venv"
        excluded.mkdir()
        (excluded / "payload.txt").write_text(f"outside-{index}\n")
        (roots[surface] / "shared" / "linked").symlink_to(
            Path("../.venv"), target_is_directory=True
        )

    report = reconcile_paths(roots)
    record = _records(report)["shared"]

    assert report["verdict"] == "ROUTE"
    assert report["counts"]["reparse_points"] == 1
    assert record["status"] == "CONFLICT"
    assert record["route"] == "materialize-review"
    assert record["reparse_paths"] == ["linked/"]
    assert all(
        difference["path"] != "linked/payload.txt"
        for difference in record["differences"]
    )


def test_aligned_file_symlink_blocks_dereferencing_deploy(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: deploy replaced an aligned live symlink with a regular file."""
    roots = _aligned_roots(tmp_path)
    target = tmp_path / "external.txt"
    target.write_text("outside\n")
    links = []
    for surface in (REPO_CANONICAL, REPO_PROJECTION, LIVE_VAULT):
        link = roots[surface] / "shared" / "asset.txt"
        link.symlink_to(target)
        links.append(link)
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    code = deploy(
        source_dir=roots[REPO_PROJECTION],
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["reason"] == "surface_reconciliation_required"
    assert payload["reconciliation"]["counts"]["reparse_points"] == 1
    assert all(link.is_symlink() for link in links)
    assert not (tmp_path / "backups").exists()


def test_text_eol_equivalence_does_not_hide_binary_difference(tmp_path: Path) -> None:
    """Known broken: raw hashes called an LF/CRLF-only text copy a conflict."""
    roots = _roots(tmp_path)
    text_lf = (b"A" * 7999) + b"\nend\n"
    text_crlf = (b"A" * 7999) + b"\r\nend\r\n"
    binary_lf = (b"A" * 7999) + b"\0\n"
    binary_crlf = (b"A" * 7999) + b"\0\r\n"
    bodies = {
        REPO_CANONICAL: (text_lf, binary_lf),
        REPO_PROJECTION: (text_crlf, binary_crlf),
        LIVE_VAULT: (text_lf, binary_lf),
    }
    for surface, (text_body, binary_body) in bodies.items():
        _skill_file(roots[surface], "text-eol", "SKILL.md", text_body)
        _skill_file(roots[surface], "binary-eol", "SKILL.md", binary_body)

    report = reconcile_paths(roots)
    by_name = _records(report)

    assert by_name["text-eol"]["status"] == "ALIGNED"
    assert by_name["text-eol"]["differences"] == []
    assert by_name["binary-eol"]["status"] == "CONFLICT"
    assert by_name["binary-eol"]["differences"][0]["path"] == "SKILL.md"


def test_detector_control_runs_the_real_surface_scanner(monkeypatch) -> None:
    """Known broken: the synthetic control bypassed scan_surface entirely."""
    calls = []

    def observed_scan(root: Path):
        calls.append(root)
        return {"masked": {"SKILL.md": "file:" + ("0" * 64)}}

    monkeypatch.setattr(surface_mod, "scan_surface", observed_scan)
    file_hash = hashlib.sha256(b"same").hexdigest()
    report = reconcile_inventories(
        {surface: {"shared": {"SKILL.md": file_hash}} for surface in SURFACE_ORDER}
    )

    assert report["verdict"] == "FAILED"
    assert report["control"]["ok"] is False
    assert report["control"]["engine"] == "scan_surface+classify"
    assert len(calls) == len(SURFACE_ORDER)


def test_plan_walk_error_cannot_authorize_an_empty_deploy(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: a silent PLAN walk error deployed zero files successfully."""
    roots = _aligned_roots(tmp_path)
    projection = roots[REPO_PROJECTION]
    real_walk = install_mod.os.walk
    projection_walks = 0

    def controlled_walk(top, *args, **kwargs):
        nonlocal projection_walks
        if Path(top) == projection:
            projection_walks += 1
            if projection_walks == 2:
                onerror = kwargs.get("onerror")
                if onerror is None:
                    return iter(())

                def denied():
                    onerror(PermissionError("denied"))
                    yield  # pragma: no cover

                return denied()
        return real_walk(top, *args, **kwargs)

    monkeypatch.setattr(install_mod.os, "walk", controlled_walk)
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    code = deploy(
        source_dir=projection,
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["reason"] == "managed_file_scan_failed"
    assert payload["problem"] == "PermissionError"
    assert (roots[LIVE_VAULT] / "shared" / "SKILL.md").read_text() == "same\n"
    assert not (tmp_path / "backups").exists()
    assert not (roots[LIVE_VAULT] / "installed.json").exists()
    assert not (roots[LIVE_VAULT] / install_mod.DEPLOY_LOCK_NAME).exists()


def test_eol_only_source_edit_is_never_copied_to_live(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: CLEAN let a post-check CRLF rewrite win over live LF."""
    roots = _aligned_roots(tmp_path)
    source = roots[REPO_PROJECTION] / "shared" / "SKILL.md"
    live = roots[LIVE_VAULT] / "shared" / "SKILL.md"
    rel = os.path.join("shared", "SKILL.md")
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    code = deploy(
        source_dir=roots[REPO_PROJECTION],
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
        _after_reconcile=lambda: source.write_bytes(b"same\r\n"),
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "deployed"
    assert payload["eol_skipped"] == [rel]
    assert rel not in payload["copied"]
    assert live.read_bytes() == b"same\n"
    assert payload["receipt"]["files"][rel] == hashlib.sha256(b"same\n").hexdigest()


def test_live_addition_after_plan_is_caught_before_write(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: candidate-only CAS ignored a new live-only path."""
    roots = _aligned_roots(tmp_path)
    intruder = roots[LIVE_VAULT] / "intruder.txt"
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    code = deploy(
        source_dir=roots[REPO_PROJECTION],
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
        _after_stage=lambda: intruder.write_text("manual\n"),
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["reason"] == "surface_changed_before_write"
    assert payload["final_reconciliation"]["verdict"] == "ROUTE"
    assert intruder.read_text() == "manual\n"
    assert not (roots[LIVE_VAULT] / "installed.json").exists()
    assert not (roots[LIVE_VAULT] / install_mod.DEPLOY_LOCK_NAME).exists()


def test_daily_root_alias_retarget_changes_bound_snapshot(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: an identical-content daily symlink retarget was invisible."""
    roots = _aligned_roots(tmp_path)
    daily_link = roots[LIVE_DAILY]
    daily_link.rmdir()
    daily_a = tmp_path / "daily-a"
    daily_b = tmp_path / "daily-b"
    daily_a.mkdir()
    daily_b.mkdir()
    daily_link.symlink_to(daily_a, target_is_directory=True)
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    def retarget() -> None:
        daily_link.unlink()
        daily_link.symlink_to(daily_b, target_is_directory=True)

    code = deploy(
        source_dir=roots[REPO_PROJECTION],
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
        _after_reconcile=retarget,
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["reason"] == "surface_changed_after_reconciliation"
    assert payload["snapshots_changed"] is True
    assert not (tmp_path / "backups").exists()
    assert not (roots[LIVE_VAULT] / "installed.json").exists()


def test_daily_alias_change_during_scan_forces_failed_report(
    tmp_path: Path, monkeypatch
) -> None:
    """Known broken: a scan could report link A after actually reading link B."""
    roots = _aligned_roots(tmp_path)
    daily_link = roots[LIVE_DAILY]
    daily_link.rmdir()
    daily_a = tmp_path / "daily-scan-a"
    daily_b = tmp_path / "daily-scan-b"
    daily_a.mkdir()
    daily_b.mkdir()
    daily_link.symlink_to(daily_a, target_is_directory=True)
    real_scan = surface_mod.scan_surface

    def retargeting_scan(root: Path):
        inventory = real_scan(root)
        if root == daily_link:
            daily_link.unlink()
            daily_link.symlink_to(daily_b, target_is_directory=True)
        return inventory

    monkeypatch.setattr(surface_mod, "scan_surface", retargeting_scan)

    report = reconcile_paths(roots)

    assert report["verdict"] == "FAILED"
    assert {(error["surface"], error["problem"]) for error in report["errors"]} >= {
        (LIVE_DAILY, "root-reparse-changed-during-scan")
    }


def test_symlinked_parent_change_during_scan_forces_failed_report(
    tmp_path: Path, monkeypatch
) -> None:
    """Known broken: only the leaf link was bound, not symlinked parent identity."""
    roots = _aligned_roots(tmp_path)
    parent_a = tmp_path / "parent-a"
    parent_b = tmp_path / "parent-b"
    (parent_a / "skills").mkdir(parents=True)
    (parent_b / "skills").mkdir(parents=True)
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(parent_a, target_is_directory=True)
    daily_root = parent_link / "skills"
    roots[LIVE_DAILY] = daily_root
    real_scan = surface_mod.scan_surface

    def retargeting_scan(root: Path):
        inventory = real_scan(root)
        if root == daily_root:
            parent_link.unlink()
            parent_link.symlink_to(parent_b, target_is_directory=True)
        return inventory

    monkeypatch.setattr(surface_mod, "scan_surface", retargeting_scan)

    report = reconcile_paths(roots)

    assert report["verdict"] == "FAILED"
    assert {(error["surface"], error["problem"]) for error in report["errors"]} >= {
        (LIVE_DAILY, "root-resolution-changed-during-scan")
    }


def test_symlinked_parent_retarget_before_write_changes_bound_surface(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: a parent-link retarget could redirect the approved surface."""
    roots = _aligned_roots(tmp_path)
    parent_a = tmp_path / "deploy-parent-a"
    parent_b = tmp_path / "deploy-parent-b"
    (parent_a / "skills").mkdir(parents=True)
    (parent_b / "skills").mkdir(parents=True)
    parent_link = tmp_path / "deploy-parent-link"
    parent_link.symlink_to(parent_a, target_is_directory=True)
    roots[LIVE_DAILY] = parent_link / "skills"
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    def retarget() -> None:
        parent_link.unlink()
        parent_link.symlink_to(parent_b, target_is_directory=True)

    code = deploy(
        source_dir=roots[REPO_PROJECTION],
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
        _after_stage=retarget,
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["reason"] == "surface_changed_before_write"
    assert payload["snapshots_changed"] is True
    assert not (roots[LIVE_VAULT] / "installed.json").exists()


def test_looping_daily_alias_is_failed_not_an_exception(tmp_path: Path) -> None:
    """Known broken: Path.resolve RuntimeError escaped instead of returning FAILED."""
    roots = _aligned_roots(tmp_path)
    daily_link = roots[LIVE_DAILY]
    daily_link.rmdir()
    daily_link.symlink_to(daily_link, target_is_directory=True)

    report = reconcile_paths(roots)

    assert report["verdict"] == "FAILED"
    assert any(error["surface"] == LIVE_DAILY for error in report["errors"])


def test_projection_root_symlink_is_rejected_before_deploy(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Known broken: resolve() hid a projection-root symlink from reconciliation."""
    roots = _aligned_roots(tmp_path)
    projection_link = roots[REPO_PROJECTION]
    projection_target = tmp_path / "projection-target"
    projection_link.rename(projection_target)
    projection_link.symlink_to(projection_target, target_is_directory=True)
    monkeypatch.setattr(install_mod, "BACKUPS_DIR", tmp_path / "backups")

    code = deploy(
        source_dir=projection_link,
        live_dir=roots[LIVE_VAULT],
        target="skills",
        skill_surface_roots=roots,
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["reason"] == "surface_reconciliation_required"
    assert {
        (error["surface"], error["problem"])
        for error in payload["reconciliation"]["errors"]
    } >= {(REPO_PROJECTION, "root-reparse-not-allowed")}
    assert not (tmp_path / "backups").exists()
    assert not (roots[LIVE_VAULT] / "installed.json").exists()
