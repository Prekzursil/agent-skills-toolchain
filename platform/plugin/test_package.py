"""Tests for manifest strictness, payload selection, and the deterministic packer.

The load-bearing assertions here are the *negative* ones: an unknown manifest field must be
REJECTED (not ignored), a forbidden path must fail the build even when an allowlist rule selected
it, and a zip-slip entry must be refused before any byte lands on disk.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from plugin import build as build_mod
from plugin import manifest as manifest_mod
from plugin import packager, payload
from plugin.errors import PluginError
from plugin.manifest import MANIFEST_RELPATH

GOOD = {
    "name": "demo-plugin",
    "version": "1.2.3",
    "description": "a demo",
    "author": {"name": "Owner"},
    "license": "MIT",
    "compatibility": {
        "min_client": "1.0.0",
        "platforms": ["windows", "linux"],
        "schema_version": 1,
    },
    "interpreters": [{"id": "python3", "floor": "3.10.0", "required": True}],
    "entrypoints": [
        {"id": "cli", "kind": "command", "path": "bin/x.py", "interpreter": "python3"}
    ],
}


def _text(doc: dict) -> str:
    return json.dumps(doc, indent=2)


# --------------------------------------------------------------------------- manifest


def test_good_manifest_parses_and_round_trips() -> None:
    m = manifest_mod.parse(_text(GOOD))
    assert (m.name, m.version, m.semver) == ("demo-plugin", "1.2.3", (1, 2, 3))
    again = manifest_mod.parse(manifest_mod.dumps(m))
    assert again.as_dict() == m.as_dict()


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda d: d.pop("license"), "missing required field"),
        (lambda d: d.update(name="Demo_Plugin"), "kebab-case"),
        (lambda d: d.update(version="1.2"), "semver"),
        (lambda d: d.update(description="  "), "non-empty"),
        (lambda d: d.update(author={"nickname": "x"}), "unknown field"),
        (lambda d: d.update(unexpected=True), "unknown field"),
        (
            lambda d: d["compatibility"].update(platforms=["solaris"]),
            "unsupported platform",
        ),
        (lambda d: d["compatibility"].pop("min_client"), "min_client is required"),
        (lambda d: d["compatibility"].update(schema_version=0), "positive integer"),
        (
            lambda d: d["entrypoints"][0].pop("interpreter"),
            "must declare an interpreter",
        ),
        (
            lambda d: d["entrypoints"][0].update(interpreter="ruby"),
            "not in interpreters[]",
        ),
        (lambda d: d["entrypoints"][0].update(kind="daemon"), "kind must be one of"),
        (
            lambda d: d["entrypoints"].append(dict(d["entrypoints"][0])),
            "duplicate entrypoint id",
        ),
    ],
)
def test_strict_parser_rejects_each_defect(mutate, needle: str) -> None:
    doc = json.loads(json.dumps(GOOD))
    mutate(doc)
    with pytest.raises(PluginError) as exc:
        manifest_mod.parse(_text(doc))
    assert exc.value.code == "E_MANIFEST"
    assert needle in exc.value.detail, f"expected {needle!r} in {exc.value.detail!r}"


def test_reserved_extension_namespace_is_accepted() -> None:
    doc = json.loads(json.dumps(GOOD))
    doc["x-internal"] = {"anything": 1}
    m = manifest_mod.parse(_text(doc))
    assert m.extensions == {"x-internal": {"anything": 1}}
    assert m.as_dict()["x-internal"] == {"anything": 1}


def test_case_distinct_duplicate_keys_are_rejected() -> None:
    raw = (
        '{"name":"a-b","Name":"c-d","version":"1.0.0","description":"x",'
        '"author":{"name":"o"},"license":"MIT","compatibility":{"min_client":"1.0.0"}}'
    )
    with pytest.raises(PluginError) as exc:
        manifest_mod.parse(raw)
    assert "case-distinct" in exc.value.detail


def test_case_guard_fires_at_nested_depth() -> None:
    doc = json.loads(json.dumps(GOOD))
    raw = _text(doc).replace('"name": "Owner"', '"name": "Owner", "NAME": "Owner"')
    with pytest.raises(PluginError) as exc:
        manifest_mod.parse(raw)
    assert "case-distinct" in exc.value.detail


def test_client_negotiation_both_directions() -> None:
    doc = json.loads(json.dumps(GOOD))
    doc["compatibility"]["max_client"] = "2.0.0"
    m = manifest_mod.parse(_text(doc))
    assert m.negotiate("1.5.0")[0] is True
    assert m.negotiate("0.9.0")[0] is False
    assert m.negotiate("2.1.0")[0] is False
    assert m.negotiate("not-a-version")[0] is False


def test_invalid_json_reports_as_manifest_error() -> None:
    with pytest.raises(PluginError) as exc:
        manifest_mod.parse("{not json")
    assert exc.value.code == "E_MANIFEST"


# --------------------------------------------------------------------------- payload


@pytest.mark.parametrize(
    ("rel", "klass"),
    [
        (".git/config", "vcs"),
        ("sub/.git/HEAD", "vcs"),
        ("__pycache__/x.pyc", "cache"),
        ("lib/__pycache__/y.pyc", "cache"),
        ("node_modules/pkg/index.js", "cache"),
        ("run.log", "log"),
        ("session.jsonl", "transcript"),
        (".env", "credential"),
        ("secrets/id_rsa", "credential"),
        ("a.bak", "backup"),
        ("bundle.tar.gz", "archive"),
    ],
)
def test_forbidden_classifier_finds_known_present(rel: str, klass: str) -> None:
    assert payload.classify_forbidden(rel) == klass


@pytest.mark.parametrize(
    "rel", ["lib/astplugin/cli.py", "README.md", "schema/x.schema.json", "LICENSE"]
)
def test_forbidden_classifier_passes_legitimate_paths(rel: str) -> None:
    assert payload.classify_forbidden(rel) is None


def test_payload_is_deny_by_default(tmp_path: Path) -> None:
    (tmp_path / "keep.md").write_text("kept\n", encoding="utf-8")
    (tmp_path / "surprise.txt").write_text("not selected\n", encoding="utf-8")
    got = payload.collect(
        tmp_path,
        [payload.AllowRule("keep.md", "wanted")],
        budget_bytes=0,
        budget_files=0,
    )
    assert [e.relpath for e in got.entries] == ["keep.md"]
    assert got.rejected == [("surprise.txt", "not matched by any allowlist rule")]


def test_allowlist_selecting_forbidden_content_fails_the_build(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    with pytest.raises(PluginError) as exc:
        payload.collect(
            tmp_path,
            [payload.AllowRule("*", "everything (deliberately wrong)")],
            budget_bytes=0,
            budget_files=0,
        )
    assert exc.value.code == "E_PAYLOAD" and "forbidden content" in exc.value.detail


def test_secret_gate_blocks_and_never_echoes_the_value(tmp_path: Path) -> None:
    secret = "ghp_" + "b" * 40
    (tmp_path / "cfg.py").write_text(f'TOKEN = "{secret}"\n', encoding="utf-8")
    with pytest.raises(PluginError) as exc:
        payload.collect(
            tmp_path,
            [payload.AllowRule("*.py", "code")],
            budget_bytes=0,
            budget_files=0,
        )
    assert exc.value.code == "E_SECRET"
    rendered = exc.value.render("build")
    assert secret not in rendered, "the gate echoed the secret it found"
    assert "github_token" in rendered


def test_secret_gate_can_be_measured_without_enforcing(tmp_path: Path) -> None:
    (tmp_path / "cfg.py").write_text(
        'TOKEN = "sk-' + "c" * 30 + '"\n', encoding="utf-8"
    )
    got = payload.collect(
        tmp_path,
        [payload.AllowRule("*.py", "code")],
        budget_bytes=0,
        budget_files=0,
        enforce_secrets=False,
    )
    doc = payload.secret_findings_document(got)
    assert doc["blocking"] >= 1
    assert all("entropy=" in f["excerpt_shape"] for f in doc["findings"])  # type: ignore[index]


def test_identifier_suppression_does_not_blind_the_entropy_rule(tmp_path: Path) -> None:
    """Both-states control for the URL/identifier suppression added to kill 14 false positives.

    STATE A (must be SILENT): a long all-lowercase slash/kebab path — a schema URL.
    STATE B (must FIRE):      a same-length mixed-case base64-ish token.
    A suppression that silenced both would have disabled the rule while looking like a cleanup.
    """
    quiet = tmp_path / "quiet.py"
    quiet.write_text(
        '"""See tools/plugin/schema/drift-classification.schema.json."""\n',
        encoding="utf-8",
        newline="\n",
    )
    assert payload.scan_secrets(quiet, "quiet.py") == []

    loud = tmp_path / "loud.py"
    loud.write_text(
        # NOT named BLOB: `_looks_like_hash_literal` treats "blob" as a hash-context word and
        # suppressed the finding, so the first draft of this control failed on its own test data.
        'VALUE = "aZ9+bY8/cX7=dW6+eV5/fU4=gT3+hS2/iR1="\n',
        encoding="utf-8",
        newline="\n",
    )
    findings = payload.scan_secrets(loud, "loud.py")
    assert [f.rule for f in findings] == ["high_entropy_token"], findings
    assert findings[0].severity == "advisory"


def test_there_is_no_secret_gate_exemption_list() -> None:
    """The removed DOCUMENTED_PATTERN_FILES must not come back: an untested widening of a
    security gate is worse than no widening, and this one never matched the shipped path."""
    assert not hasattr(payload, "DOCUMENTED_PATTERN_FILES")
    assert "documented" not in {v for v in schemas_severity_enum()}, (
        "the schema still allows a 'documented' severity nothing can produce"
    )


def schemas_severity_enum() -> list[str]:
    from plugin.schemas import SCHEMAS

    return SCHEMAS["secret-finding"]["properties"]["findings"]["items"]["properties"][
        "severity"
    ]["enum"]


def test_clean_payload_produces_zero_blocking_findings(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    got = payload.collect(
        tmp_path, [payload.AllowRule("*.py", "code")], budget_bytes=0, budget_files=0
    )
    assert [f for f in got.findings if f.severity == "blocking"] == []


def test_file_count_budget_is_hard(tmp_path: Path) -> None:
    for i in range(4):
        (tmp_path / f"f{i}.md").write_text("x\n", encoding="utf-8")
    with pytest.raises(PluginError) as exc:
        payload.collect(
            tmp_path,
            [payload.AllowRule("*.md", "docs")],
            budget_bytes=0,
            budget_files=3,
        )
    assert exc.value.code == "E_BUDGET" and "4 files" in exc.value.detail


def test_byte_budget_is_hard(tmp_path: Path) -> None:
    (tmp_path / "big.md").write_text("x" * 5000, encoding="utf-8")
    with pytest.raises(PluginError) as exc:
        payload.collect(
            tmp_path,
            [payload.AllowRule("*.md", "docs")],
            budget_bytes=100,
            budget_files=0,
        )
    assert exc.value.code == "E_BUDGET"


def test_inventory_diff_reports_all_three_directions() -> None:
    prev = {
        "entries": [{"path": "a", "sha256": "1"}, {"path": "b", "sha256": "2"}],
        "total_bytes": 10,
        "file_count": 2,
    }
    cur = {
        "entries": [{"path": "b", "sha256": "9"}, {"path": "c", "sha256": "3"}],
        "total_bytes": 20,
        "file_count": 2,
    }
    d = payload.inventory_diff(prev, cur)
    assert d["added"] == ["c"] and d["removed"] == ["a"] and d["changed"] == ["b"]


# --------------------------------------------------------------------------- packager


def test_archive_is_byte_identical_across_two_builds(
    tmp_path: Path, repo_root: Path
) -> None:
    a, _ = build_mod.build(repo_root, tmp_path / "one")
    b, _ = build_mod.build(repo_root, tmp_path / "two")
    assert a.sha256 == b.sha256, "the packer is not deterministic"
    assert (tmp_path / "one").exists() and (tmp_path / "two").exists()


def test_archive_entries_are_sorted_with_a_fixed_timestamp(built_package: Path) -> None:
    with zipfile.ZipFile(built_package) as zf:
        infos = zf.infolist()
    names = [i.filename for i in infos]
    assert names == sorted(names), "entries are not in sorted order"
    assert {i.date_time for i in infos} == {packager.ZIP_EPOCH}


def test_crlf_source_does_not_change_the_archive(tmp_path: Path) -> None:
    """A CRLF working tree must produce the same archive as an LF one (line-ending policy)."""
    m = manifest_mod.parse(_text(GOOD))
    results = []
    for eol in ("\n", "\r\n"):
        root = tmp_path / f"src{len(results)}"
        root.mkdir()
        (root / "note.md").write_bytes(f"one{eol}two{eol}".encode())
        p = payload.collect(
            root, [payload.AllowRule("*.md", "docs")], budget_bytes=0, budget_files=0
        )
        res = packager.build_archive(
            p, m, tmp_path / f"out{len(results)}.zip", allowlist_doc={"artifact": "x"}
        )
        results.append(res.sha256)
    assert results[0] == results[1]


def test_unpack_refuses_a_zip_slip_entry(tmp_path: Path) -> None:
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../escaped.txt", b"pwned")
    with pytest.raises(PluginError) as exc:
        packager.unpack(evil, tmp_path / "dest")
    assert exc.value.code == "E_IO"
    assert not (tmp_path / "escaped.txt").exists(), (
        "a byte landed outside the destination"
    )


def test_unpack_refuses_a_reserved_device_entry(tmp_path: Path) -> None:
    evil = tmp_path / "dev.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("nul", b"x")
    with pytest.raises(PluginError):
        packager.unpack(evil, tmp_path / "dest")


def test_read_member_reports_a_missing_member_as_conformance(
    built_package: Path,
) -> None:
    with pytest.raises(PluginError) as exc:
        packager.read_member(built_package, "not/there.txt")
    assert exc.value.code == "E_CONFORM"


def test_a_non_archive_is_reported_not_crashed(tmp_path: Path) -> None:
    junk = tmp_path / "junk.zip"
    junk.write_bytes(b"this is not a zip")
    with pytest.raises(PluginError) as exc:
        packager.list_members(junk)
    assert exc.value.code == "E_CONFORM"


# --------------------------------------------------------------------------- the real package


def test_declared_version_matches_the_package_dunder() -> None:
    import plugin

    assert plugin.__version__ == build_mod.PLUGIN_VERSION


def test_every_staged_file_is_covered_by_an_allowlist_rule(
    tmp_path: Path, repo_root: Path
) -> None:
    stage = build_mod.stage(repo_root, tmp_path / "stage")
    rels = build_mod.staged_relpaths(stage)
    assert rels, "the staging tree is empty"
    uncovered = [
        r for r in rels if not any(rule.matches(r) for rule in build_mod.ALLOW_RULES)
    ]
    assert uncovered == [], f"staged files no rule selects: {uncovered}"


def test_package_contains_no_forbidden_member(built_package: Path) -> None:
    hits = [
        (m, payload.classify_forbidden(m)) for m in packager.list_members(built_package)
    ]
    assert [h for h in hits if h[1]] == []


def test_package_ships_its_manifest_and_it_is_strict(built_package: Path) -> None:
    m = manifest_mod.parse(
        packager.read_member(built_package, MANIFEST_RELPATH).decode("utf-8")
    )
    assert m.name == build_mod.PLUGIN_NAME
    assert {e.ident for e in m.entrypoints} == {
        build_mod.ENTRYPOINT_CONSOLE,
        build_mod.ENTRYPOINT_HOOK,
    }


def test_package_size_is_measured_and_small(built_package: Path) -> None:
    size = built_package.stat().st_size
    members = packager.list_members(built_package)
    assert size < build_mod.MAX_BYTES, f"archive is {size} bytes"
    assert len(members) <= build_mod.MAX_FILES
