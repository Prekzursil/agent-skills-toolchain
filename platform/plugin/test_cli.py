"""CLI tests: every verb runs, every failure exits with its taxonomy code, dry-run writes nothing.

The exit-code contract is only real if it is exercised through ``main()``, which is what a user
and a CI gate actually call. These tests drive ``main()`` in-process (fast, and the return value
IS the exit code) and the rehearsal script drives it as a subprocess (slower, proves the argv path).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from plugin.build import PLUGIN_NAME, build
from plugin.cli import main
from plugin.errors import BY_CODE


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def env(tmp_path: Path, repo_root: Path) -> dict[str, Path]:
    result, _ = build(repo_root, tmp_path / "dist")
    newer, _ = build(repo_root, tmp_path / "dist101", version="1.0.1")
    return {
        "repo": repo_root,
        "pkg": result.archive,
        "pkg2": newer.archive,
        "prefix": tmp_path / "prefix",
        "out": tmp_path / "out",
    }


def test_build_verb_writes_a_package_and_reports_its_size(
    tmp_path: Path, repo_root: Path
) -> None:
    out = tmp_path / "json" / "build.json"
    code = main(
        [
            "build",
            "--repo-root",
            str(repo_root),
            "--out",
            str(tmp_path / "dist"),
            "--json",
            str(out),
        ]
    )
    assert code == 0
    doc = _read(out)
    assert doc["archive"].endswith(".zip") and Path(doc["archive"]).exists()
    assert doc["archive_bytes"] > 0 and doc["payload_file_count"] > 0
    assert doc["secret_findings_blocking"] == 0


def test_build_explain_payload_lists_every_rule(
    tmp_path: Path, repo_root: Path
) -> None:
    out = tmp_path / "b.json"
    main(
        [
            "build",
            "--repo-root",
            str(repo_root),
            "--out",
            str(tmp_path / "d"),
            "--explain-payload",
            "--json",
            str(out),
        ]
    )
    doc = _read(out)
    assert doc["allowlist"] and all("reason" in r for r in doc["allowlist"])
    assert doc["entries"]


def test_schemas_check_is_green_in_the_repo(repo_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "s.json"
    code = main(["schemas", "--repo-root", str(repo_root), "--json", str(out)])
    assert code == 0 and _read(out)["in_sync"] is True


def test_schemas_check_fails_on_an_empty_tree(tmp_path: Path) -> None:
    out = tmp_path / "s.json"
    code = main(["schemas", "--repo-root", str(tmp_path), "--json", str(out)])
    assert code == BY_CODE["E_CONFORM"].exit_code
    assert _read(out)["in_sync"] is False


def test_conform_verb_exit_codes_both_ways(
    env: dict[str, Path], tmp_path: Path
) -> None:
    good = tmp_path / "good.json"
    assert main(["conform", "--package", str(env["pkg"]), "--json", str(good)]) == 0
    assert _read(good)["ok"] is True
    junk = tmp_path / "junk.zip"
    junk.write_bytes(b"nope")
    bad = tmp_path / "bad.json"
    assert (
        main(["conform", "--package", str(junk), "--json", str(bad)])
        == BY_CODE["E_CONFORM"].exit_code
    )
    assert _read(bad)["ok"] is False


def test_full_lifecycle_through_the_cli(env: dict[str, Path], tmp_path: Path) -> None:
    prefix = str(env["prefix"])
    j = tmp_path / "j"
    assert (
        main(["install", "--package", str(env["pkg"]), "--prefix", prefix, "--dry-run"])
        == 0
    )
    assert not (env["prefix"] / "versions").exists()

    assert (
        main(
            [
                "install",
                "--package",
                str(env["pkg"]),
                "--prefix",
                prefix,
                "--json",
                str(j / "i.json"),
            ]
        )
        == 0
    )
    assert _read(j / "i.json")["version"] == "1.0.0"

    assert (
        main(
            [
                "health-check",
                "--prefix",
                prefix,
                "--controls",
                "--json",
                str(j / "h.json"),
            ]
        )
        == 0
    )
    health = _read(j / "h.json")
    assert health["ok"] is True and health["control_summary"]["invalid"] == 0

    assert main(["projection", "--prefix", prefix, "--json", str(j / "p.json")]) == 0
    assert _read(j / "p.json")["plugin"] == PLUGIN_NAME

    assert (
        main(
            [
                "update",
                "--package",
                str(env["pkg2"]),
                "--prefix",
                prefix,
                "--json",
                str(j / "u.json"),
            ]
        )
        == 0
    )
    assert _read(j / "u.json")["version"] == "1.0.1"

    assert main(["rollback", "--prefix", prefix, "--json", str(j / "r.json")]) == 0
    assert _read(j / "r.json")["version"] == "1.0.0"

    assert main(["repair", "--prefix", prefix, "--json", str(j / "rep.json")]) == 0
    assert (
        main(
            [
                "cache",
                "--prefix",
                prefix,
                "--refresh",
                "--verify",
                "--json",
                str(j / "c.json"),
            ]
        )
        == 0
    )
    cache = _read(j / "c.json")
    assert cache["actions"]["refreshed"] > 0 and cache["actions"]["quarantined"] == []

    assert main(["journal", "--prefix", prefix, "--json", str(j / "jr.json")]) == 0
    assert _read(j / "jr.json")["open_transactions"] == []

    assert (
        main(
            [
                "diagnose",
                "--prefix",
                prefix,
                "--client-version",
                "1.2.3",
                "--json",
                str(j / "d.json"),
            ]
        )
        == 0
    )
    assert _read(j / "d.json")["compatible"] is True

    assert main(["uninstall", "--prefix", prefix]) == BY_CODE["E_USAGE"].exit_code
    assert (
        main(
            [
                "uninstall",
                "--prefix",
                prefix,
                "--retain-user-data",
                "--json",
                str(j / "un.json"),
            ]
        )
        == 0
    )
    assert _read(j / "un.json")["user_data"] == "retain"


def test_sync_exits_e_drift_when_a_decision_is_required(
    env: dict[str, Path], tmp_path: Path
) -> None:
    prefix = str(env["prefix"])
    main(["install", "--package", str(env["pkg"]), "--prefix", prefix])
    live = env["prefix"] / "live" / "commands" / "astplugin.md"
    live.write_text(
        live.read_text(encoding="utf-8") + "\nlocal\n", encoding="utf-8", newline="\n"
    )
    src = env["prefix"] / "versions" / "1.0.0" / "commands" / "astplugin.md"
    src.write_text(
        src.read_text(encoding="utf-8") + "\nupstream\n", encoding="utf-8", newline="\n"
    )
    decisions = tmp_path / "decisions.json"
    out = tmp_path / "sync.json"
    code = main(
        ["sync", "--prefix", prefix, "--decisions", str(decisions), "--json", str(out)]
    )
    assert code == BY_CODE["E_DRIFT"].exit_code
    packet = _read(decisions)
    assert packet["auto_resolved"] is False and packet["decision_required"] == 1
    assert _read(out)["drift"]["counts"]["diverged"] == 1


def test_install_of_an_absent_package_reports_usage(tmp_path: Path) -> None:
    assert (
        main(
            [
                "install",
                "--package",
                str(tmp_path / "nope.zip"),
                "--prefix",
                str(tmp_path / "p"),
            ]
        )
        == 2
    )


def test_health_check_on_an_empty_prefix_is_not_a_false_green(tmp_path: Path) -> None:
    out = tmp_path / "h.json"
    code = main(
        ["health-check", "--prefix", str(tmp_path / "fresh"), "--json", str(out)]
    )
    doc = _read(out)
    assert code == 0
    assert doc["skipped"] >= 3, (
        "an empty prefix must SKIP the installed-state probes, not pass them"
    )
    assert all(p["status"] != "FAIL" for p in doc["probes"])


def test_doctor_exit_code_tracks_health(env: dict[str, Path], tmp_path: Path) -> None:
    prefix = str(env["prefix"])
    main(["install", "--package", str(env["pkg"]), "--prefix", prefix])
    assert (
        main(["doctor", "--prefix", prefix, "--json", str(tmp_path / "ok.json")]) == 0
    )
    (env["prefix"] / "live" / "hooks" / "plugin_health.py").unlink()
    out = tmp_path / "bad.json"
    assert (
        main(["doctor", "--prefix", prefix, "--json", str(out)])
        == BY_CODE["E_HEALTH"].exit_code
    )
    assert _read(out)["actions"][0]["run"].startswith("astplugin ")


def test_errors_and_policies_verbs_emit_their_documents(tmp_path: Path) -> None:
    e = tmp_path / "e.json"
    assert main(["errors", "--json", str(e)]) == 0
    assert _read(e)["artifact"] == "error-taxonomy"
    p = tmp_path / "p.json"
    assert main(["policies", "--json", str(p)]) == 0
    doc = _read(p)
    assert doc["taxonomy_agreement_problems"] == []


def test_migrate_verb_is_a_noop_on_a_modern_prefix(
    env: dict[str, Path], tmp_path: Path
) -> None:
    prefix = str(env["prefix"])
    main(["install", "--package", str(env["pkg"]), "--prefix", prefix])
    out = tmp_path / "m.json"
    assert main(["migrate", "--prefix", prefix, "--json", str(out)]) == 0
    assert _read(out)["detected_layout"] == "none"


def test_unknown_verb_is_a_usage_error() -> None:
    assert main(["teleport"]) == 2


def test_every_verb_is_reachable_and_declares_json() -> None:
    from plugin.cli import build_parser

    parser = build_parser()
    choices = parser._subparsers._group_actions[0].choices  # noqa: SLF001
    assert len(choices) >= 15
    for name, sub in choices.items():
        opts = {a.option_strings[0] for a in sub._actions if a.option_strings}  # noqa: SLF001
        assert "--json" in opts, f"verb {name} has no --json output"
