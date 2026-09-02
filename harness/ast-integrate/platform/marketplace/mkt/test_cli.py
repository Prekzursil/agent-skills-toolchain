"""CLI tests: the exit code must agree with the printed terminal marker.

A CLI whose marker says FAILED while it exits 0 is worse than one with no marker: a caller that
branches on the exit code and a human reading the log will disagree, and the log wins arguments
it should lose. Every case here asserts BOTH.
"""

from __future__ import annotations

import json

import pytest

from mkt import cli, fixture, registry


def run(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr().out
    marker = out.strip().splitlines()[-1]
    return code, marker, out


def parse(out: str) -> dict:
    """The JSON body, i.e. everything before the trailing terminal marker line(s)."""
    lines = out.rstrip().splitlines()
    while lines and (
        lines[-1].startswith("SUCCESS:") or lines[-1].startswith("FAILED:")
    ):
        lines.pop()
    return json.loads("\n".join(lines))


@pytest.fixture(scope="module")
def registry_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("cli-fixture")
    fixture.build(root, now=fixture.T0)
    return root / "registry"


def test_selfcheck_reports_n_of_n(capsys):
    code, marker, out = run(capsys, ["selfcheck"])
    assert code == 0
    assert marker.startswith("SUCCESS:mkt-selfcheck")
    payload = parse(out)
    assert payload["checked"] == payload["declared"]


def test_validate_accepts_a_good_document_and_rejects_a_bad_one(
    capsys, registry_root, tmp_path
):
    code, marker, _ = run(
        capsys,
        ["validate", str(registry_root / "index.json"), "--schema", "registry-index"],
    )
    assert (code, marker) == (0, "SUCCESS:mkt-validate")

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": "0.0.1"}), encoding="utf-8")
    code, marker, _ = run(capsys, ["validate", str(bad), "--schema", "registry-index"])
    assert code == 1
    assert marker.startswith("FAILED:mkt-validate")


def test_validate_reports_a_missing_file_rather_than_passing(capsys, tmp_path):
    code, marker, _ = run(
        capsys, ["validate", str(tmp_path / "nope.json"), "--schema", "publisher"]
    )
    assert code == 1
    assert "no such file" in marker


def test_search_and_lint(capsys, registry_root):
    code, marker, out = run(
        capsys, ["search", "--registry", str(registry_root), "--tag", "fixture"]
    )
    assert (code, marker) == (0, "SUCCESS:mkt-search")
    assert parse(out)["count"] >= 3

    code, marker, _ = run(capsys, ["lint", str(registry_root), "--fixture-policy"])
    assert code == 0
    assert marker.startswith("SUCCESS:mkt-lint")


def test_install_then_revoke_then_install_refuses(capsys, tmp_path):
    """The headline sequence, driven entirely through the CLI."""
    work = tmp_path / "w"
    code, marker, _ = run(capsys, ["fixture", "--into", str(work)])
    assert (code, marker) == (0, "SUCCESS:mkt-fixture")
    reg_root = str(work / "registry")

    args = [
        "install",
        "hello-skill",
        "--registry",
        reg_root,
        "--site",
        str(tmp_path / "site"),
        "--range",
        "=1.0.0",
        "--channel",
        "stable",
        "--fixture-policy",
        "--platform",
        "win32",
    ]
    code, marker, _ = run(capsys, args)
    assert (code, marker) == (0, "SUCCESS:mkt-install")

    code, marker, _ = run(
        capsys,
        [
            "revoke",
            "--registry",
            reg_root,
            "--scope",
            "version",
            "--name",
            "hello-skill",
            "--version",
            "1.0.0",
            "--reason",
            "CLI test: the install path must refuse after this.",
            "--authority",
            "pub:moderation-board",
            "--fixture-key",
            "pub:registry-root",
        ],
    )
    assert (code, marker) == (0, "SUCCESS:mkt-revoke")

    args[args.index(str(tmp_path / "site"))] = str(tmp_path / "site2")
    code, marker, _ = run(capsys, args)
    assert code == 1, "the exit code must agree with the marker"
    assert marker == "FAILED:mkt-install MKT-I04"
    assert not (tmp_path / "site2" / "packages" / "hello-skill").exists()


def test_keygen_refuses_to_overwrite(capsys, tmp_path):
    key = tmp_path / "keys" / "publisher.key"
    code, marker, out = run(capsys, ["keygen", "--out", str(key)])
    assert (code, marker) == (0, "SUCCESS:mkt-keygen")
    assert parse(out)["public_key"].startswith("ed25519:")
    assert "do not commit" in key.read_text(encoding="utf-8")

    code, marker, _ = run(capsys, ["keygen", "--out", str(key)])
    assert code == 1
    assert "refusing to overwrite" in marker


def test_scaffold_emits_a_complete_package(capsys, tmp_path):
    code, marker, out = run(
        capsys, ["scaffold", "--name", "cli-demo", "--into", str(tmp_path)]
    )
    assert (code, marker) == (0, "SUCCESS:mkt-scaffold")
    files = parse(out)["files"]
    assert "package.json" in files
    assert any(f.startswith("payload/") for f in files)


def test_export_import_round_trip(capsys, tmp_path):
    work = tmp_path / "w"
    run(capsys, ["fixture", "--into", str(work)])
    reg_root = str(work / "registry")
    code, marker, _ = run(
        capsys,
        [
            "export",
            "--registry",
            reg_root,
            "--out",
            str(tmp_path / "bundle"),
            "--package",
            "hello-skill@1.0.0",
            "--fixture-key",
            "pub:registry-root",
        ],
    )
    assert (code, marker) == (0, "SUCCESS:mkt-export")
    code, marker, _ = run(
        capsys,
        [
            "import",
            str(tmp_path / "bundle"),
            "--registry",
            str(tmp_path / "dest"),
            "--fixture-policy",
            "--fixture-key",
            "pub:registry-root",
        ],
    )
    assert (code, marker) == (0, "SUCCESS:mkt-import")
    assert registry.load_index(tmp_path / "dest")["entries"]


def test_lint_on_a_path_that_is_neither_registry_nor_manifest(capsys, tmp_path):
    code, marker, _ = run(capsys, ["lint", str(tmp_path)])
    assert code == 1
    assert "not a registry root" in marker


def test_publish_requires_a_maintainer_key_distinct_from_the_publisher_key(
    capsys, tmp_path
):
    """Role separation: without a maintainer key the CLI must refuse, not fall back."""
    work = tmp_path / "w"
    run(capsys, ["fixture", "--into", str(work)])
    from mkt import scaffold

    src = scaffold.scaffold(tmp_path / "src", name="needs-maintainer", now=fixture.T0)
    key = tmp_path / "pub.key"
    key.write_text("0" * 64 + "\n", encoding="utf-8")
    code, marker, _ = run(
        capsys,
        [
            "publish",
            str(src),
            "--registry",
            str(work / "registry"),
            "--publisher",
            "pub:alpha-tools",
            "--key-file",
            str(key),
            "--fixture-policy",
        ],
    )
    assert code == 1
    assert "maintainer-key-file" in marker
