"""Tests for hub.registry: snapshot reload, resolution, deny lists, halt switches."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hub import errors  # noqa: E402
from hub import registry as registry_mod  # noqa: E402
from hub.registry import (  # noqa: E402
    Registry,
    RegistrySnapshot,
    caller_family,
    effective_capabilities,
    find_repo_root,
    lattice_rank,
    lattice_state,
    registry_hash,
)
from tests import conftest_hub as helpers  # noqa: E402

seed_registry_path = helpers.seed_registry_path
registry = helpers.registry

FAKE_VALIDATOR = '''
"""Stand-in for models_control_plane written by the registry tests."""


class ModelsRegistryError(ValueError):
    pass


def validate_registry(config):
    if config.get("schemaVersion") != 1:
        raise ModelsRegistryError("schemaVersion must be 1")
    if config["policy"].get("failValidator"):
        raise ModelsRegistryError("policy.failValidator is set")
    return ["warn-1"]


def registry_hash(config):
    return "f" * 16
'''


@pytest.fixture(autouse=True)
def isolated_validator_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry_mod, "_VALIDATOR_CACHE", {})
    monkeypatch.setattr(sys, "path", list(sys.path))


def bump_mtime(path: Path, seconds: float = 10.0) -> None:
    stat = path.stat()
    os.utime(path, (stat.st_atime + seconds, stat.st_mtime + seconds))


def write_repo_validator(repo_root: Path, source: str = FAKE_VALIDATOR) -> Path:
    target = repo_root / ".agents" / "scripts" / "models_control_plane.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    return target


def test_lattice_helpers() -> None:
    assert lattice_state("native") == "native"
    assert lattice_state({"state": "probed", "at": "2026-09-02", "version": "1"}) == (
        "probed"
    )
    assert lattice_state({"state": 3}) == "absent"
    assert lattice_state(42) == "absent"
    assert lattice_state("bogus") == "absent"
    assert lattice_rank("native") == 4
    assert lattice_rank({"state": "probed"}) == 3
    assert lattice_rank("declared") == 2
    assert lattice_rank("emulated") == 1
    assert lattice_rank("absent") == 0
    assert lattice_rank(None) == 0


def test_effective_capabilities_downward_only() -> None:
    config = helpers.load_seed()
    model = config["models"]["glm-5.3"]
    model["features"] = {"tools": "absent", "streaming": "native", "vision": "native"}
    model["wire"] = {"completions": {"state": "probed", "at": "x", "version": "1"}}
    caps = effective_capabilities(config, "glm-5.3")
    assert caps["features"]["tools"] == "absent"
    assert caps["features"]["streaming"] == "native"
    assert caps["features"]["vision"] == "declared"
    assert caps["wire"]["completions"] == {"state": "probed", "at": "x", "version": "1"}
    assert caps["wire"]["responses"] == "declared"
    assert set(caps) == {"wire", "features"}
    plain = effective_capabilities(config, "qwen2.5-7b")
    assert plain == {
        "wire": config["endpoints"]["ollama"]["wire"],
        "features": config["endpoints"]["ollama"]["features"],
    }
    assert plain["wire"] is not config["endpoints"]["ollama"]["wire"]


def test_registry_hash_is_canonical_prefix() -> None:
    config = helpers.load_seed()
    digest = registry_hash(config)
    assert len(digest) == 16
    assert digest == registry_hash(json.loads(json.dumps(config)))
    config["description"] = "changed"
    assert registry_hash(config) != digest


def test_find_repo_root_walks_up_to_models_json(tmp_path: Path) -> None:
    assert find_repo_root() == helpers.REPO_ROOT
    assert find_repo_root(tmp_path / "a" / "b") is None
    repo = helpers.make_repo_layout(tmp_path)
    assert find_repo_root(repo / "tools" / "x" / "y.py") == repo


def test_caller_family_collapses_client_names() -> None:
    assert caller_family("claude-code") == "claude"
    assert caller_family("claude") == "claude"
    assert caller_family("claude-code/2.1.x") == "claude"
    assert caller_family("Cursor") == "cursor"
    assert caller_family("cursor-vscode") == "cursor"
    assert caller_family("Codex CLI") == "codex"
    assert caller_family("gemini_cli") == "gemini"
    assert caller_family("  agy ") == "agy"
    assert caller_family("") == ""
    assert caller_family(None) == ""


def test_path_resolution_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    explicit = helpers.make_registry_copy(tmp_path, name="explicit.json")
    assert Registry(explicit, environ={}).path == explicit
    assert Registry(str(explicit), environ={}).path == explicit
    from_env = Registry(environ={registry_mod.REGISTRY_ENV: str(explicit)})
    assert from_env.path == explicit
    repo = helpers.make_repo_layout(tmp_path)
    scoped = Registry(environ={}, repo_root=repo)
    assert scoped.path == repo / ".agents" / "models.json"
    assert scoped.repo_root == repo
    default = Registry(environ={})
    assert default.path == helpers.SEED_REGISTRY
    assert default.repo_root == helpers.REPO_ROOT
    monkeypatch.setattr(registry_mod, "find_repo_root", lambda *_: None)
    with pytest.raises(errors.HubError) as excinfo:
        Registry(environ={})
    assert excinfo.value.klass == errors.REGISTRY_UNAVAILABLE
    rootless = Registry(explicit, environ={})
    assert rootless.repo_root == explicit.parent


def test_snapshot_without_validator_is_structural_only(
    registry: Registry, seed_registry_path: Path
) -> None:
    snap = registry.snapshot()
    assert isinstance(snap, RegistrySnapshot)
    assert snap.path == seed_registry_path
    assert snap.validated is False
    assert snap.warnings == []
    assert snap.hash == registry_hash(snap.config)
    assert snap.mtime == seed_registry_path.stat().st_mtime_ns
    assert snap.config["schemaVersion"] == 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.validated = True  # type: ignore[misc]
    assert registry.hash() == snap.hash


def test_snapshot_reloads_only_when_mtime_changes(
    registry: Registry, seed_registry_path: Path
) -> None:
    first = registry.snapshot()
    assert registry.snapshot() is first
    config = json.loads(seed_registry_path.read_text(encoding="utf-8"))
    config["models"]["glm-5.3"]["label"] = "relabelled"
    helpers.write_json(seed_registry_path, config)
    bump_mtime(seed_registry_path)
    second = registry.snapshot()
    assert second is not first
    assert second.config["models"]["glm-5.3"]["label"] == "relabelled"
    assert second.hash != first.hash
    assert registry.resolve("glm-5.3").model["label"] == "relabelled"


def test_snapshot_missing_or_invalid_file(tmp_path: Path) -> None:
    missing = Registry(tmp_path / "absent.json", environ={}, repo_root=tmp_path)
    with pytest.raises(errors.HubError) as excinfo:
        missing.snapshot()
    assert excinfo.value.klass == errors.REGISTRY_UNAVAILABLE
    assert "absent.json" in excinfo.value.message
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(errors.HubError) as excinfo:
        Registry(broken, environ={}, repo_root=tmp_path).snapshot()
    assert excinfo.value.klass == errors.REGISTRY_UNAVAILABLE
    listy = tmp_path / "list.json"
    listy.write_text("[]", encoding="utf-8")
    with pytest.raises(errors.HubError) as excinfo:
        Registry(listy, environ={}, repo_root=tmp_path).snapshot()
    assert "mapping" in excinfo.value.message


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda c: c.__setitem__("schemaVersion", 2), "schemaVersion"),
        (lambda c: c.pop("endpoints"), "endpoints"),
        (lambda c: c.__setitem__("models", []), "models"),
        (lambda c: c.__setitem__("aliases", "x"), "aliases"),
        (lambda c: c.__setitem__("policy", None), "policy"),
        (lambda c: c["models"]["glm-5.3"].__setitem__("endpoint", "ghost"), "ghost"),
        (lambda c: c["models"].__setitem__("bad", "not-a-row"), "bad"),
        (lambda c: c["endpoints"].__setitem__("bad", 3), "bad"),
        (lambda c: c["aliases"].__setitem__("loose", "missing-model"), "loose"),
    ],
)
def test_structural_check_rejects_malformed_registry(
    tmp_path: Path, mutate: Any, fragment: str
) -> None:
    path = helpers.make_registry_copy(tmp_path, mutate)
    with pytest.raises(errors.HubError) as excinfo:
        Registry(path, environ={}, repo_root=tmp_path).snapshot()
    assert excinfo.value.klass == errors.REGISTRY_UNAVAILABLE
    assert fragment in excinfo.value.message


def test_structural_check_accepts_missing_aliases(tmp_path: Path) -> None:
    path = helpers.make_registry_copy(tmp_path, lambda c: c.pop("aliases"))
    reg = Registry(path, environ={}, repo_root=tmp_path)
    assert reg.snapshot().validated is False
    with pytest.raises(errors.HubError) as excinfo:
        reg.resolve("glm53")
    assert excinfo.value.klass == errors.UNKNOWN_MODEL


def test_snapshot_with_validator_present(tmp_path: Path) -> None:
    repo = helpers.make_repo_layout(tmp_path)
    write_repo_validator(repo)
    reg = Registry(environ={}, repo_root=repo)
    snap = reg.snapshot()
    assert snap.validated is True
    assert snap.warnings == ["warn-1"]
    assert snap.hash == "f" * 16
    assert registry_mod.load_validator(repo) is registry_mod.load_validator(repo)


def test_validator_error_becomes_registry_unavailable(tmp_path: Path) -> None:
    repo = helpers.make_repo_layout(
        tmp_path, lambda c: c["policy"].__setitem__("failValidator", True)
    )
    write_repo_validator(repo)
    reg = Registry(environ={}, repo_root=repo)
    with pytest.raises(errors.HubError) as excinfo:
        reg.snapshot()
    assert excinfo.value.klass == errors.REGISTRY_UNAVAILABLE
    assert "policy.failValidator is set" in excinfo.value.message
    assert registry_mod.load_validator(repo) is not None


def test_validator_import_failure_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = helpers.make_repo_layout(tmp_path)
    write_repo_validator(repo)
    monkeypatch.setattr(
        importlib.util, "spec_from_file_location", lambda *_a, **_k: None
    )
    reg = Registry(environ={}, repo_root=repo)
    snap = reg.snapshot()
    assert snap.validated is False
    assert registry_mod.load_validator(repo) is None


def test_validator_syntax_error_falls_back(tmp_path: Path) -> None:
    repo = helpers.make_repo_layout(tmp_path)
    write_repo_validator(repo, "def broken(:\n")
    assert registry_mod.load_validator(repo) is None
    assert Registry(environ={}, repo_root=repo).snapshot().validated is False


def test_validator_loader_reuses_sys_path_entry(tmp_path: Path) -> None:
    repo = helpers.make_repo_layout(tmp_path)
    write_repo_validator(repo)
    scripts_dir = str(repo / ".agents" / "scripts")
    assert registry_mod.load_validator(repo) is not None
    assert sys.path.count(scripts_dir) == 1
    registry_mod._VALIDATOR_CACHE.clear()
    assert registry_mod.load_validator(repo) is not None
    assert sys.path.count(scripts_dir) == 1


def test_resolve_id_alias_and_endpoint_suffix(registry: Registry) -> None:
    resolved = registry.resolve("glm-5.3")
    assert resolved.model_id == "glm-5.3"
    assert resolved.endpoint_id == "hf-router"
    assert resolved.remote_id == "zai-org/GLM-5.3:zai-org"
    assert resolved.endpoint["baseUrl"] == "https://router.huggingface.co/v1"
    assert resolved.capabilities["wire"]["completions"] == "native"
    assert resolved.capabilities["features"]["tools"] == "declared"
    assert registry.resolve("glm53").model_id == "glm-5.3"
    assert registry.resolve("fabric-default").model_id == "glm-5.3"
    assert registry.resolve(" glm-5.3@hf-router ").endpoint_id == "hf-router"
    assert registry.resolve("local-default").remote_id == "qwen2.5:7b"


@pytest.mark.parametrize(
    ("ref", "klass"),
    [
        ("no-such-model", errors.UNKNOWN_MODEL),
        ("glm-5.3@ollama", errors.UNKNOWN_MODEL),
        ("glm53@ollama", errors.UNKNOWN_MODEL),
        ("glm-5.3@", errors.UNKNOWN_MODEL),
        ("", errors.INVALID_ARGUMENT),
        ("   ", errors.INVALID_ARGUMENT),
        (None, errors.INVALID_ARGUMENT),
        (7, errors.INVALID_ARGUMENT),
    ],
)
def test_resolve_rejects_bad_references(
    registry: Registry, ref: Any, klass: str
) -> None:
    with pytest.raises(errors.HubError) as excinfo:
        registry.resolve(ref)
    assert excinfo.value.klass == klass
    assert excinfo.value.retryable is False


def test_resolve_disabled_model_and_endpoint(tmp_path: Path) -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["models"]["glm-5.3"]["enabled"] = False
        config["endpoints"]["ollama"]["enabled"] = False

    reg = Registry(
        helpers.make_registry_copy(tmp_path, mutate), environ={}, repo_root=tmp_path
    )
    with pytest.raises(errors.HubError) as excinfo:
        reg.resolve("glm-5.3")
    assert excinfo.value.klass == errors.MODEL_DISABLED
    assert excinfo.value.model == "glm-5.3"
    assert excinfo.value.endpoint == "hf-router"
    with pytest.raises(errors.HubError) as excinfo:
        reg.resolve("glm53")
    assert excinfo.value.klass == errors.MODEL_DISABLED
    with pytest.raises(errors.HubError) as excinfo:
        reg.resolve("qwen2.5-7b")
    assert excinfo.value.klass == errors.ENDPOINT_DISABLED
    assert excinfo.value.endpoint == "ollama"


def test_resolve_denied_callers(registry: Registry, tmp_path: Path) -> None:
    for caller in (
        "claude-code",
        "claude",
        "Claude-Code/2.1.x",
        "cursor",
        "Cursor-vscode",
    ):
        with pytest.raises(errors.HubError) as excinfo:
            registry.resolve("glm-5.2-free", caller=caller)
        assert excinfo.value.klass == errors.CALLER_DENIED
        assert excinfo.value.model == "glm-5.2-free"
        assert excinfo.value.endpoint == "openrouter"
    assert registry.resolve("glm-5.2-free", caller="codex").model_id == "glm-5.2-free"
    assert registry.resolve("glm-5.3", caller="claude-code").model_id == "glm-5.3"
    assert registry.resolve("glm-5.3").model_id == "glm-5.3"
    with pytest.raises(errors.HubError) as excinfo:
        registry.resolve("cursor-grok-4.6", caller="cursor")
    assert excinfo.value.klass == errors.CALLER_DENIED

    def mutate(config: dict[str, Any]) -> None:
        config["models"]["glm-5.3"]["denyCallers"] = ["codex"]

    reg = Registry(
        helpers.make_registry_copy(tmp_path, mutate), environ={}, repo_root=tmp_path
    )
    with pytest.raises(errors.HubError) as excinfo:
        reg.resolve("glm-5.3", caller="codex")
    assert excinfo.value.klass == errors.CALLER_DENIED
    assert reg.resolve("glm-5.3", caller="claude").model_id == "glm-5.3"


def test_models_list_shape_filter_and_truthful_denial(registry: Registry) -> None:
    rows = registry.models_list()
    assert [row["id"] for row in rows] == [
        "glm-5.3",
        "glm-5.2-free",
        "cursor-grok-4.6",
        "qwen2.5-7b",
        "qwen3-4b-instruct",
        "qwen3-8b",
    ]
    assert set(rows[0]) == {
        "id",
        "endpoint",
        "remote_id",
        "enabled",
        "status",
        "tier",
        "label",
        "capabilities",
        "cost",
        "deny_callers",
        "callable",
    }
    assert rows[0]["callable"] is True
    assert rows[0]["cost"] == {
        "inputPer1M": None,
        "outputPer1M": None,
        "basis": "table_estimate",
    }
    assert rows[1]["deny_callers"] == ["claude", "claude-code", "cursor"]
    assert rows[1]["capabilities"]["features"]["streaming"] == "native"
    assert [row["id"] for row in registry.models_list("glm")] == [
        "glm-5.3",
        "glm-5.2-free",
    ]
    assert [row["id"] for row in registry.models_list("OLLAMA")] == [
        "qwen2.5-7b",
        "qwen3-4b-instruct",
        "qwen3-8b",
    ]
    assert [row["id"] for row in registry.models_list("thinking off")] == [
        "qwen3-4b-instruct",
        "qwen3-8b",
    ]
    assert registry.models_list("no-match") == []
    denied = {
        row["id"]: row["callable"] for row in registry.models_list(caller="claude-code")
    }
    assert denied["glm-5.2-free"] is False
    assert denied["glm-5.3"] is True
    assert denied["cursor-grok-4.6"] is True
    cursor = {
        row["id"]: row["callable"] for row in registry.models_list(caller="cursor")
    }
    assert cursor["cursor-grok-4.6"] is False
    assert cursor["glm-5.2-free"] is False
    assert cursor["qwen2.5-7b"] is True


def test_models_list_marks_disabled_rows_not_callable(tmp_path: Path) -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["models"]["glm-5.3"]["enabled"] = False
        config["endpoints"]["ollama"]["enabled"] = False

    reg = Registry(
        helpers.make_registry_copy(tmp_path, mutate), environ={}, repo_root=tmp_path
    )
    rows = {row["id"]: row for row in reg.models_list()}
    assert rows["glm-5.3"]["enabled"] is False
    assert rows["glm-5.3"]["callable"] is False
    assert rows["qwen2.5-7b"]["enabled"] is True
    assert rows["qwen2.5-7b"]["callable"] is False
    assert rows["glm-5.2-free"]["callable"] is True


def test_credential_names_only_enabled_endpoints(
    registry: Registry, tmp_path: Path
) -> None:
    assert registry.credential_names() == [
        "HUGGINGFACE_TOKEN_INFERENCE",
        "OPENROUTER_API_KEY_CLI_GRUNT",
        "OPENROUTER_API_KEY_CODEX_SIDECAR",
        "OPENROUTER_API_KEY_IDE_OPENCODE",
    ]

    def mutate(config: dict[str, Any]) -> None:
        config["endpoints"]["openrouter"]["enabled"] = False
        config["endpoints"]["ollama"]["auth"] = {"env": "OLLAMA_KEY"}

    reg = Registry(
        helpers.make_registry_copy(tmp_path, mutate), environ={}, repo_root=tmp_path
    )
    assert reg.credential_names() == ["HUGGINGFACE_TOKEN_INFERENCE", "OLLAMA_KEY"]


def test_concurrency_limit_and_endpoint_lookup(
    registry: Registry, tmp_path: Path
) -> None:
    assert registry.concurrency_limit("hf-router") == 4
    assert registry.concurrency_limit("ollama") == 1
    assert registry.endpoint("openrouter")["sidecarOnly"] is True
    with pytest.raises(errors.HubError) as excinfo:
        registry.concurrency_limit("ghost")
    assert excinfo.value.klass == errors.INVALID_ARGUMENT
    with pytest.raises(errors.HubError):
        registry.endpoint("ghost")

    def mutate(config: dict[str, Any]) -> None:
        del config["endpoints"]["hf-router"]["concurrency"]

    reg = Registry(
        helpers.make_registry_copy(tmp_path, mutate), environ={}, repo_root=tmp_path
    )
    assert reg.concurrency_limit("hf-router") == 1


def test_policy_returns_a_copy(registry: Registry) -> None:
    policy = registry.policy()
    assert policy["hub"]["port"] == 8901
    policy["hub"]["port"] = 1
    assert registry.policy()["hub"]["port"] == 8901
    assert registry.snapshot().config["policy"]["hub"]["port"] == 8901


def test_halted_by_env_and_file(tmp_path: Path) -> None:
    repo = helpers.make_repo_layout(tmp_path)
    reg = Registry(environ={}, repo_root=repo)
    assert reg.halted() is False
    for value in ("1", "true", "YES", "on", "anything"):
        assert reg.halted({"INFERENCE_HALT": value}) is True
    for value in ("0", "false", "no", "off", ""):
        assert reg.halted({"INFERENCE_HALT": value}) is False
    assert Registry(environ={"INFERENCE_HALT": "1"}, repo_root=repo).halted() is True
    halt_file = repo / ".agents" / "INFERENCE-HALT"
    halt_file.write_text("stop\n", encoding="utf-8")
    assert reg.halted() is True
    halt_file.unlink()
    assert reg.halted() is False


def test_halted_uses_policy_names_and_survives_bad_registry(tmp_path: Path) -> None:
    def mutate(config: dict[str, Any]) -> None:
        config["policy"]["hub"]["haltEnv"] = "CUSTOM_HALT"
        config["policy"]["hub"]["haltFile"] = "halt/STOP"

    repo = helpers.make_repo_layout(tmp_path, mutate)
    reg = Registry(environ={}, repo_root=repo)
    assert reg.halted({"INFERENCE_HALT": "1"}) is False
    assert reg.halted({"CUSTOM_HALT": "1"}) is True
    (repo / "halt").mkdir()
    (repo / "halt" / "STOP").write_text("", encoding="utf-8")
    assert reg.halted() is True
    plain = helpers.make_registry_copy(tmp_path, lambda c: c.__setitem__("policy", {}))
    assert Registry(plain, environ={"INFERENCE_HALT": "1"}, repo_root=tmp_path).halted()
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    fallback = Registry(broken, environ={}, repo_root=tmp_path)
    assert fallback.halted() is False
    assert fallback.halted({"INFERENCE_HALT": "1"}) is True
    (tmp_path / ".agents").mkdir(exist_ok=True)
    (tmp_path / ".agents" / "INFERENCE-HALT").write_text("", encoding="utf-8")
    assert fallback.halted() is True


def test_resolved_model_is_frozen(registry: Registry) -> None:
    resolved = registry.resolve("qwen2.5-7b")
    with pytest.raises(dataclasses.FrozenInstanceError):
        resolved.model_id = "other"  # type: ignore[misc]
    assert resolved.model["tier"] == "M"
    assert resolved.endpoint["kind"] == "local"
