"""Both-states regression tests for the strict-target hook-manifest emitter."""

from __future__ import annotations

import copy
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from emit_hook_manifest import (  # noqa: E402
    ManifestError,
    emit_manifest,
    main,
    render_manifest,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CURRENT_MANIFESTS = (
    REPO_ROOT / "hooks" / "hooks.json",
    REPO_ROOT / "agent-self" / "config" / "hooks" / "hooks.json",
)
HISTORICAL_BAD = (
    REPO_ROOT / "hooks" / "_fleet-backups" / "20260713-WU-A" / "hooks.json.before"
)
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "quality.yml"
TARGET = "codex-plugin"


def _load(path: pathlib.Path) -> dict[str, object]:
    source = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(source, dict)
    return source


def test_historical_schema_is_routed_without_losing_supported_hooks() -> None:
    """Known-broken pre-change: copying this fixture emits parser-rejected $schema."""
    source = _load(HISTORICAL_BAD)
    before = copy.deepcopy(source)

    assert "$schema" in source  # known-present detector control
    emitted = emit_manifest(source, target=TARGET)

    assert "$schema" not in emitted
    assert emitted == {"hooks": source["hooks"]}
    assert source == before


def test_emitted_manifest_is_deeply_detached_from_source() -> None:
    """Known-broken pre-change: there is no emitter that can promise non-mutation."""
    source = {"hooks": {"Stop": [{"hooks": [{"command": "true"}]}]}}
    before = copy.deepcopy(source)

    emitted = emit_manifest(source, target=TARGET)

    assert emitted == source
    assert emitted["hooks"] is not source["hooks"]
    assert emitted["hooks"]["Stop"] is not source["hooks"]["Stop"]
    emitted["hooks"]["Stop"].append({"hooks": []})
    assert source == before


def test_known_good_manifest_has_stable_golden_rendering() -> None:
    """Known-broken pre-change: no generation boundary guarantees canonical bytes."""
    source = {"hooks": {}, "description": "kept"}
    expected = '{\n  "description": "kept",\n  "hooks": {}\n}\n'

    first = render_manifest(source, target=TARGET)
    second = render_manifest(source, target=TARGET)

    assert first == expected
    assert second == expected
    assert source == {"hooks": {}, "description": "kept"}


def test_unknown_key_fails_closed_without_mutating_source() -> None:
    """Known-broken pre-change: prose cannot stop a future key or silent pruning."""
    source = {"description": "kept", "hooks": {}, "future_semantic": {"on": True}}
    before = copy.deepcopy(source)

    with pytest.raises(ManifestError, match="future_semantic"):
        emit_manifest(source, target=TARGET)

    assert source == before


def test_unknown_target_fails_closed_without_mutating_source() -> None:
    """Known-broken pre-change: there is no explicit target selector to reject."""
    source = {"hooks": {}}
    before = copy.deepcopy(source)

    with pytest.raises(ManifestError, match="unknown target"):
        emit_manifest(source, target="unreviewed-loader")

    assert source == before


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ({1: "metadata", "hooks": {}}, "keys must be strings"),
        ({"description": 1, "hooks": {}}, "description must be a string"),
        ({"hooks": {"bad": {1, 2}}}, "strict JSON"),
        ({"hooks": {"bad": "\ud800"}}, "strict JSON"),
    ],
    ids=("non-string-key", "description-type", "non-json-value", "lone-surrogate"),
)
def test_invalid_profile_values_fail_without_mutation(
    source: dict[object, object], message: str
) -> None:
    """Known-broken pre-change: prose cannot validate profile value types."""
    before = copy.deepcopy(source)

    with pytest.raises(ManifestError, match=message):
        emit_manifest(source, target=TARGET)  # type: ignore[arg-type]

    assert source == before


def test_non_finite_number_fails_without_mutation() -> None:
    """Known-broken pre-change: there is no strict-JSON emission boundary."""
    source = {"hooks": {"timeout": float("nan")}}

    with pytest.raises(ManifestError, match="strict JSON"):
        emit_manifest(source, target=TARGET)

    assert source["hooks"]["timeout"] != source["hooks"]["timeout"]


@pytest.mark.parametrize("source", [{}, {"hooks": []}])
def test_required_hooks_object_is_enforced(source: dict[str, object]) -> None:
    """Known-broken pre-change: prose does not enforce the required hooks object."""
    before = copy.deepcopy(source)

    with pytest.raises(ManifestError):
        emit_manifest(source, target=TARGET)

    assert source == before


@pytest.mark.parametrize("manifest", CURRENT_MANIFESTS, ids=("canonical", "agent-self"))
def test_cli_check_accepts_each_current_manifest_independently(
    manifest: pathlib.Path,
) -> None:
    """Known-broken pre-change: neither checked-in manifest has an executable guard."""
    source = _load(manifest)
    assert "hooks" in source  # known-present detector control
    assert main(["--source", str(manifest), "--target", TARGET, "--check"]) == 0


def test_cli_check_rejects_the_historical_bad_bytes(tmp_path: pathlib.Path) -> None:
    """Known-broken pre-change: this exact rejected shape has no executable guard."""
    candidate = tmp_path / "hooks.json"
    candidate.write_bytes(HISTORICAL_BAD.read_bytes())

    assert main(["--source", str(candidate), "--target", TARGET, "--check"]) == 1


def test_cli_check_normalizes_crlf(tmp_path: pathlib.Path) -> None:
    """Known-broken pre-change: there is no cross-platform canonical check."""
    candidate = tmp_path / "hooks.json"
    rendered = render_manifest({"description": "kept", "hooks": {}}, target=TARGET)
    candidate.write_bytes(rendered.replace("\n", "\r\n").encode("utf-8"))

    assert main(["--source", str(candidate), "--target", TARGET, "--check"]) == 0


def test_cli_emit_routes_schema_and_writes_deterministic_stdout(capsys) -> None:
    """Known-broken pre-change: there is no target-selective emission command."""
    assert main(["--source", str(HISTORICAL_BAD), "--target", TARGET, "--emit"]) == 0

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"hooks": _load(HISTORICAL_BAD)["hooks"]}
    assert captured.out.endswith("\n")
    assert captured.err == ""


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (None, "cannot read"),
        ("not-json", "cannot read"),
        ("[]", "must contain a JSON object"),
        ('{"hooks":{"Stop":[],"Stop":[{"hooks":[]}]}}', "duplicate key 'Stop'"),
    ],
    ids=("missing", "malformed", "non-object", "nested-duplicate"),
)
def test_cli_invalid_sources_return_controlled_error(
    tmp_path: pathlib.Path, capsys, body: str | None, message: str
) -> None:
    """Known-broken pre-change: no emitter rejects malformed or lossy JSON input."""
    candidate = tmp_path / "hooks.json"
    if body is not None:
        candidate.write_text(body, encoding="utf-8")

    assert main(["--source", str(candidate), "--target", TARGET, "--check"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert message in captured.err


def test_quality_workflow_executes_tests_and_both_manifest_checks() -> None:
    """Known-broken pre-change: M04 has no workflow reference and is inert."""
    text = WORKFLOW.read_text(encoding="utf-8")
    active_lines = {
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "python -m pytest ci/tests/test_emit_hook_manifest.py -q" in active_lines
    for manifest in CURRENT_MANIFESTS:
        relative = manifest.relative_to(REPO_ROOT).as_posix()
        command = (
            "python ci/emit_hook_manifest.py "
            f"--source {relative} --target {TARGET} --check"
        )
        assert command in active_lines
