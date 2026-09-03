"""Red-proof (V1..V20) and behavioural tests for the models registry validator.

Every failing fixture mutates a deep copy of the committed seed, so the tests
double as a specification of how far a row may drift before the SSOT rejects it.
Fake credential values are assembled at runtime and never match a real token
shape (``hf_[A-Za-z0-9]{10,}``, ``sk-...``, ``ghp_...``, AWS, Slack).
"""

from __future__ import annotations

import copy
import importlib
import json
import pathlib
import re
import runpy
import subprocess
import sys
from collections.abc import Mapping
from typing import Any

import pytest


AGENTS_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = AGENTS_ROOT / "scripts"
SEED_PATH = AGENTS_ROOT / "models.json"
CLI_PATH = SCRIPTS_ROOT / "validate_models_control_plane.py"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
models = importlib.import_module("models_control_plane")
cli = importlib.import_module("validate_models_control_plane")

SEED: dict[str, Any] = json.loads(SEED_PATH.read_text(encoding="utf-8"))
HEX16 = re.compile(r"^[0-9a-f]{16}$")
PROBED = {"state": "probed", "at": "2026-09-02T07:00:00Z", "version": "0.1.0"}

FAKE_HF = "hf_" + "FAKE_VALUE_NOT_A_TOKEN"
FAKE_SK = "sk-" + "FAKE_VALUE_NOT_A_TOKEN"
FAKE_GHP = "ghp_" + "FAKE_VALUE_NOT_A_TOKEN"
FAKE_AWS = "AKIA" + "NOTAREALKEYFAKE0"
FAKE_SLACK = "xoxb-" + "FAKE-NOT-A-TOKEN"
FAKE_PEM = "-----BEGIN " + "RSA PRIVATE KEY-----"


def seed() -> dict[str, Any]:
    return copy.deepcopy(SEED)


def rejects(config: Mapping[str, Any], fragment: str) -> None:
    with pytest.raises(models.ModelsRegistryError, match=re.escape(fragment)):
        models.validate_registry(config)


def probed_hf_router_responses(config: dict[str, Any]) -> dict[str, Any]:
    config["endpoints"]["hf-router"]["wire"]["responses"] = dict(PROBED)
    return config


# --- the seed -------------------------------------------------------------------


def test_seed_validates_with_zero_warnings() -> None:
    assert models.validate_registry(seed()) == []


def test_seed_loads_from_the_default_path() -> None:
    assert models.DEFAULT_REGISTRY_PATH == SEED_PATH
    assert models.load_registry() == SEED
    assert models.load_registry(str(SEED_PATH)) == SEED


def test_glm53_capability_preserved() -> None:
    """L7 receipt: GLM-5.3 stays reachable after the glm53-space lane is deleted."""
    model = SEED["models"]["glm-5.3"]
    assert model["endpoint"] == "hf-router"
    assert model["remoteId"] == "zai-org/GLM-5.3:zai-org"
    assert model["enabled"] is True
    assert (
        SEED["endpoints"]["hf-router"]["baseUrl"] == "https://router.huggingface.co/v1"
    )
    assert SEED["endpoints"]["hf-router"]["enabled"] is True
    assert "L7" in SEED["endpoints"]["hf-router"]["locks"]
    model_id, _, endpoint_id, _ = models.resolve_model(SEED, "glm53")
    assert (model_id, endpoint_id) == ("glm-5.3", "hf-router")
    assert "glm-5.3" in models.select_target_models(SEED, "fabric")


# --- V1..V20 red-proof fixtures ------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [FAKE_HF, FAKE_SK, FAKE_GHP, FAKE_AWS, FAKE_SLACK, FAKE_PEM, f"(token={FAKE_HF})"],
)
def test_v1_literal_secret_anywhere_is_rejected(value: str) -> None:
    config = seed()
    config["endpoints"]["hf-router"]["description"] += " " + value
    with pytest.raises(models.ModelsRegistryError, match="literal secret") as info:
        models.validate_registry(config)
    assert "FAKE" not in str(info.value)


def test_v1_literal_secret_in_a_key_or_list_is_rejected_before_schema_checks() -> None:
    config = seed()
    config["endpoints"]["hf-router"][FAKE_HF] = True
    rejects(config, "literal secret")
    config = seed()
    config["endpoints"]["hf-router"]["tags"].append(FAKE_SK)
    rejects(config, "literal secret")


def test_v1_environment_names_are_never_mistaken_for_secrets() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["auth"]["altEnv"] = ["HF_TOKEN"]
    config["endpoints"]["hf-router"]["description"] += " reads HF_TOKEN or GHS_ALT_NAME"
    assert models.validate_registry(config) == []


def test_v2_auth_env_must_be_an_environment_name() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["auth"]["env"] = "huggingface-token"
    rejects(config, "auth.env must be an environment variable name")
    config = seed()
    config["endpoints"]["openrouter"]["auth"]["altEnv"] = ["ok_lowercase"]
    rejects(config, "auth.altEnv must be a list of environment variable names")


def test_v3_http_base_url_must_be_loopback() -> None:
    config = seed()
    config["endpoints"]["ollama"]["baseUrl"] = "http://192.168.1.10:11434/v1"
    rejects(config, "ollama: http:// baseUrl is only allowed for loopback hosts")


def test_v4_openai_compatible_base_url_must_end_in_v1() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["baseUrl"] = "https://router.huggingface.co"
    rejects(config, "hf-router: baseUrl must end in /v1")
    config = seed()
    config["endpoints"]["hf-router"]["baseUrl"] = "https://router.huggingface.co/v1/"
    rejects(config, "hf-router: baseUrl must end in /v1")


def test_v5_model_lattice_may_not_exceed_the_endpoint() -> None:
    config = seed()
    config["models"]["glm-5.3"]["wire"] = {"responses": "native"}
    rejects(config, "glm-5.3: wire.responses 'native' exceeds endpoint hf-router")


def test_v6_two_enabled_endpoints_may_not_share_a_singleton_key() -> None:
    config = seed()
    clone = copy.deepcopy(config["endpoints"]["cursor-auth2api"])
    clone["baseUrl"] = "http://127.0.0.1:8318/v1"
    config["endpoints"]["cursor-auth2api-shadow"] = clone
    rejects(config, "singletonKey 'cursor-bridge' is shared with enabled endpoint")
    clone["enabled"] = False
    assert models.validate_registry(config) == []


@pytest.mark.parametrize("runtime", ["cursor", "claude"])
@pytest.mark.parametrize("value", ["native", "fallback"])
def test_v7_openrouter_never_targets_cursor_or_claude(runtime: str, value: str) -> None:
    config = seed()
    config["endpoints"]["openrouter"]["targets"][runtime] = value
    rejects(
        config, f"openrouter: targets.{runtime} must be unsupported or excluded (L1)"
    )


@pytest.mark.parametrize(
    ("endpoint_id", "base_url"),
    [
        ("hf-router", "https://router.huggingface.co:8765/v1"),
        ("hf-router", "https://router.huggingface.co:8812/v1"),
        ("hf-router", "https://router.huggingface.co:8770/v1"),
        ("ollama", "http://127.0.0.1:8317/v1"),
        ("ollama", "http://127.0.0.1:8901/v1"),
    ],
)
def test_v8_owned_ports_are_rejected(endpoint_id: str, base_url: str) -> None:
    config = seed()
    config["endpoints"][endpoint_id]["baseUrl"] = base_url
    rejects(config, f"{endpoint_id}: baseUrl port")
    rejects(config, "(L4)")


def test_v8_cursor_auth2api_keeps_its_own_port() -> None:
    assert SEED["endpoints"]["cursor-auth2api"]["baseUrl"] == "http://127.0.0.1:8317/v1"
    assert models.validate_registry(seed()) == []


def test_v9_extension_blocks_are_closed() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["x_codex"] = {"wire_api": "responses", "bogus": 1}
    rejects(config, "hf-router: unknown x_codex key 'bogus'")
    config = seed()
    config["endpoints"]["ollama"]["x_ollama"]["keepAliveForever"] = True
    rejects(config, "ollama: unknown x_ollama key 'keepAliveForever'")
    config = seed()
    config["endpoints"]["hf-router"]["x_bogus"] = {}
    rejects(config, "hf-router: unknown extension block 'x_bogus'")
    config = seed()
    config["models"]["glm-5.3"]["x_bogus"] = {}
    rejects(config, "glm-5.3: unknown extension block 'x_bogus'")


def test_v10_local_ram_over_budget_is_a_warning_not_an_error() -> None:
    config = seed()
    config["models"]["qwen3-8b"]["resource"]["ramBytes"] = 8 * 1024**3
    warnings = models.validate_registry(config)
    assert len(warnings) == 1
    assert "policy.localRamBudgetBytes" in warnings[0]
    assert "'qwen3-8b'" in warnings[0]
    assert "8589934592" in warnings[0]


def test_v10_disabled_rows_do_not_count_against_the_budget() -> None:
    config = seed()
    config["models"]["qwen3-8b"]["resource"]["ramBytes"] = 8 * 1024**3
    config["models"]["qwen3-8b"]["enabled"] = False
    assert models.validate_registry(config) == []
    config["models"]["qwen3-8b"]["enabled"] = True
    config["models"]["qwen3-8b"]["endpoint"] = "llamacpp"
    assert models.validate_registry(config) == []


def test_v11_probed_requires_at_and_version() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["wire"]["responses"] = "probed"
    rejects(config, "hf-router: wire.responses probed value requires an object")
    config = seed()
    config["endpoints"]["hf-router"]["wire"]["responses"] = {
        "state": "probed",
        "at": "2026-09-02T07:00:00Z",
    }
    rejects(config, "wire.responses probed value is missing required key 'version'")
    config = seed()
    config["endpoints"]["hf-router"]["wire"]["responses"] = {
        "state": "probed",
        "version": "0.1.0",
    }
    rejects(config, "wire.responses probed value is missing required key 'at'")


def test_v12_aliases_must_name_an_enabled_model() -> None:
    config = seed()
    config["aliases"]["glm53"] = "no-such-model"
    rejects(config, "aliases: glm53 names unknown model 'no-such-model'")
    config = seed()
    config["models"]["glm-5.3"]["enabled"] = False
    rejects(config, "aliases: glm53 names disabled model 'glm-5.3'")


def test_v13_cursor_auth2api_must_say_when_it_retires() -> None:
    config = seed()
    del config["endpoints"]["cursor-auth2api"]["retiresWhen"]
    rejects(config, "cursor-auth2api: retiresWhen is required (L3)")


def test_v14_openrouter_must_be_sidecar_only() -> None:
    config = seed()
    config["endpoints"]["openrouter"]["sidecarOnly"] = False
    rejects(config, "openrouter: sidecarOnly must be true (L1)")
    config = seed()
    del config["endpoints"]["openrouter"]["sidecarOnly"]
    rejects(config, "openrouter: sidecarOnly must be true (L1)")


def test_v15_cursor_must_be_denied_on_openrouter_and_cursor_endpoints() -> None:
    config = seed()
    config["endpoints"]["openrouter"]["denyCallers"] = ["claude"]
    rejects(config, "openrouter: denyCallers must include 'cursor'")
    config = seed()
    config["endpoints"]["cursor-auth2api"]["denyCallers"] = []
    rejects(config, "cursor-auth2api: denyCallers must include 'cursor'")
    config = seed()
    config["models"]["glm-5.2-free"]["denyCallers"] = ["claude"]
    rejects(config, "glm-5.2-free: denyCallers must include 'cursor'")
    config = seed()
    config["models"]["cursor-grok-4.6"]["denyCallers"] = []
    rejects(config, "cursor-grok-4.6: denyCallers must include 'cursor'")
    config = seed()
    config["endpoints"]["openrouter"]["denyCallers"] = ["cursor"]
    rejects(config, "openrouter: denyCallers must include 'claude'")
    config = seed()
    config["models"]["glm-5.2-free"]["denyCallers"] = ["cursor"]
    rejects(
        config,
        "glm-5.2-free: denyCallers must include 'claude' (V15, endpoint openrouter)",
    )
    config = seed()
    config["endpoints"]["cursor-auth2api"]["denyCallers"] = ["cursor"]
    config["models"]["cursor-grok-4.6"]["denyCallers"] = ["cursor"]
    assert models.validate_registry(config) == []


def test_v16_lock_references_must_be_declared() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["locks"].append("L99")
    rejects(config, "hf-router: locks reference undeclared lock 'L99'")


def test_v17_models_must_name_a_declared_endpoint() -> None:
    config = seed()
    config["models"]["glm-5.3"]["endpoint"] = "nope"
    rejects(config, "glm-5.3: endpoint 'nope' is not declared")


def test_v18_targets_are_closed_over_runtimes_and_values() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["targets"]["bogus"] = "native"
    rejects(config, "hf-router: unknown targets key 'bogus'")
    config = seed()
    del config["endpoints"]["hf-router"]["targets"]["agy"]
    rejects(config, "hf-router: targets is missing required key 'agy'")
    config = seed()
    config["endpoints"]["hf-router"]["targets"]["codex"] = "maybe"
    rejects(config, "hf-router: targets.codex has unsupported value 'maybe'")


def test_v19_issuer_hosts_must_cover_the_base_url_host() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["auth"]["issuerHosts"] = ["example.invalid"]
    rejects(config, "hf-router: auth.issuerHosts ['example.invalid'] do not cover")
    config = seed()
    config["endpoints"]["hf-router"]["auth"]["issuerHosts"] = ["*.huggingface.co"]
    assert models.validate_registry(config) == []
    config["endpoints"]["hf-router"]["baseUrl"] = "https://huggingface.co/v1"
    rejects(config, "do not cover baseUrl host 'huggingface.co'")


def test_v20_unknown_keys_are_errors_at_every_level() -> None:
    config = seed()
    config["extra"] = 1
    rejects(config, "registry: unknown registry key 'extra'")
    config = seed()
    config["endpoints"]["hf-router"]["bogus"] = 1
    rejects(config, "hf-router: unknown endpoint key 'bogus'")
    config = seed()
    config["models"]["glm-5.3"]["bogus"] = 1
    rejects(config, "glm-5.3: unknown model key 'bogus'")
    config = seed()
    config["models"]["glm-5.3"]["quirks"] = {"openai": {"bogus": True}}
    rejects(config, "glm-5.3: unknown quirks.openai key 'bogus'")
    config = seed()
    del config["endpoints"]["hf-router"]["health"]
    rejects(config, "hf-router: endpoint is missing required key 'health'")


# --- lattice ----------------------------------------------------------------------


def test_lattice_states_ranks_and_floors() -> None:
    assert models.LATTICE_STATES == (
        "native",
        "probed",
        "declared",
        "emulated",
        "absent",
    )
    assert [models.LATTICE_RANK[state] for state in models.LATTICE_STATES] == [
        4,
        3,
        2,
        1,
        0,
    ]
    assert models.lattice_state("native") == "native"
    assert models.lattice_state(dict(PROBED)) == "probed"
    assert models.lattice_rank(dict(PROBED, evidence="curl /v1/responses")) == 3
    assert models.lattice_at_least("native", "probed") is True
    assert models.lattice_at_least(dict(PROBED), "probed") is True
    assert models.lattice_at_least("declared", "probed") is False
    assert models.lattice_at_least("absent", "absent") is True
    with pytest.raises(models.ModelsRegistryError, match="unknown floor state"):
        models.lattice_at_least("native", "verified")


@pytest.mark.parametrize(
    ("value", "fragment"),
    [
        ("sometimes", "unknown lattice value 'sometimes'"),
        (3, "must be a lattice state or a probed object"),
        (dict(PROBED, state="native"), "object form requires state probed"),
        (dict(PROBED, at="yesterday"), "value.at must be an ISO-8601 timestamp"),
        (dict(PROBED, evidence=7), "value.evidence must be a nonempty string"),
    ],
)
def test_lattice_rejects_malformed_values(value: object, fragment: str) -> None:
    with pytest.raises(models.ModelsRegistryError, match=re.escape(fragment)):
        models.lattice_state(value)


def test_effective_capabilities_apply_downward_overrides_only() -> None:
    config = seed()
    config["models"]["glm-5.3"]["features"] = {"tools": "absent", "vision": "emulated"}
    assert models.validate_registry(config) == []
    capabilities = models.effective_capabilities(config, "glm53@hf-router")
    assert set(capabilities) == {"wire", "features"}
    assert capabilities["features"]["tools"] == "absent"
    assert capabilities["features"]["vision"] == "emulated"
    assert capabilities["features"]["streaming"] == "native"
    assert capabilities["wire"] == config["endpoints"]["hf-router"]["wire"]
    config["models"]["glm-5.3"]["features"]["tools"] = dict(PROBED)
    rejects(
        config,
        "glm-5.3: features.tools 'probed' exceeds endpoint hf-router value 'declared'",
    )
    config["models"]["glm-5.3"]["features"] = {"bogus": "absent"}
    rejects(config, "glm-5.3: unknown features key 'bogus'")


# --- resolution and selection ---------------------------------------------------------


def test_resolve_model_accepts_ids_qualified_ids_and_aliases() -> None:
    for ref in ("glm-5.3", "glm-5.3@hf-router", "glm53", "fabric-default@hf-router"):
        model_id, model, endpoint_id, endpoint = models.resolve_model(SEED, ref)
        assert model_id == "glm-5.3"
        assert model is SEED["models"]["glm-5.3"]
        assert endpoint_id == "hf-router"
        assert endpoint is SEED["endpoints"]["hf-router"]
    with pytest.raises(
        models.ModelsRegistryError, match="served by endpoint 'hf-router', not 'ollama'"
    ):
        models.resolve_model(SEED, "glm-5.3@ollama")
    with pytest.raises(
        models.ModelsRegistryError, match="unknown model reference 'nope'"
    ):
        models.resolve_model(SEED, "nope")
    with pytest.raises(models.ModelsRegistryError, match="unknown model reference ''"):
        models.resolve_model(SEED, "")


def test_runtime_constants_match_the_contract() -> None:
    assert models.RUNTIMES == (
        "codex", "grok", "goose", "opencode", "aider", "fabric",
        "cursor", "claude", "agy", "gemini",
    )  # fmt: skip
    assert set(models.NATIVE_RUNTIMES) | set(models.MCP_ONLY_RUNTIMES) == set(
        models.RUNTIMES
    )
    assert not set(models.NATIVE_RUNTIMES) & set(models.MCP_ONLY_RUNTIMES)
    assert models.RUNTIME_FLOORS["codex"] == {"wire.responses": "probed"}
    assert all(
        models.RUNTIME_FLOORS[runtime] == {}
        for runtime in models.RUNTIMES
        if runtime != "codex"
    )


def test_codex_selects_nothing_until_responses_is_probed() -> None:
    """The D9 gate: every seed endpoint declares wire.responses, none is probed."""
    assert models.select_target_endpoints(SEED, "codex") == {}
    assert models.select_target_models(SEED, "codex") == {}
    config = probed_hf_router_responses(seed())
    assert list(models.select_target_endpoints(config, "codex")) == ["hf-router"]
    assert list(models.select_target_models(config, "codex")) == [
        "glm-5.3",
        "hermes-3-70b",
        "qwen3.6-35b-a3b",
    ]


def test_grok_selects_native_and_fallback_endpoints_but_not_disabled_ones() -> None:
    selected = models.select_target_endpoints(SEED, "grok")
    assert list(selected) == [
        "cursor-auth2api",
        "hf-router",
        "hf-router-featherless",
        "lmstudio",
        "ollama",
        "openrouter",
    ]
    assert "llamacpp" not in selected
    assert selected["hf-router"] is SEED["endpoints"]["hf-router"]
    assert list(models.select_target_models(SEED, "grok")) == [
        "cursor-grok-4.6",
        "glm-5.2-free",
        "glm-5.3",
        "hermes-3-70b",
        "huihui-cyberstrike-35b",
        "huihui-qwen3.8-27b-abliterated",
        "qwen2.5-7b",
        "qwen3-4b-instruct",
        "qwen3-8b",
        "qwen3.6-35b-a3b",
        "qwythos-9b",
        "wrn-2.5-coder-7b",
        "wrn-coder-7b",
    ]
    assert list(models.select_target_endpoints(SEED, "goose")) == [
        "cursor-auth2api",
        "hf-router",
        "hf-router-featherless",
        "lmstudio",
        "ollama",
    ]


def test_mcp_only_runtimes_select_nothing_and_are_pointed_at_the_hub() -> None:
    for runtime in models.MCP_ONLY_RUNTIMES:
        assert models.select_target_endpoints(SEED, runtime) == {}
        assert models.select_target_models(SEED, runtime) == {}
    rows = {row["endpoint"]: row for row in models.routing_report(SEED, "cursor")}
    assert set(rows) == set(SEED["endpoints"])
    assert all(row["decision"] == "excluded" for row in rows.values())
    assert all(row["reason"] == "runtime:mcp-only" for row in rows.values())
    assert rows["hf-router"]["alternative"] == "inference-hub"
    assert rows["ollama"]["alternative"] == "inference-hub"
    assert rows["openrouter"]["alternative"] is None
    assert rows["cursor-auth2api"]["alternative"] is None
    assert rows["llamacpp"]["alternative"] is None


def test_unknown_runtime_is_rejected_everywhere() -> None:
    for function in (
        models.select_target_endpoints,
        models.select_target_models,
        models.routing_report,
    ):
        with pytest.raises(
            models.ModelsRegistryError, match="unsupported runtime 'vim'"
        ):
            function(SEED, "vim")


def test_selection_refuses_an_invalid_registry() -> None:
    config = seed()
    config["extra"] = 1
    with pytest.raises(models.ModelsRegistryError, match="unknown registry key"):
        models.select_target_endpoints(config, "grok")


def test_routing_report_rows_have_the_contract_shape() -> None:
    rows = models.routing_report(SEED, "codex")
    assert [row["endpoint"] for row in rows] == sorted(SEED["endpoints"])
    for row in rows:
        assert set(row) == {
            "endpoint",
            "runtime",
            "decision",
            "reason",
            "alternative",
            "wrappers",
        }
        assert row["runtime"] == "codex"
        assert row["decision"] == "excluded"
    by_endpoint = {row["endpoint"]: row for row in rows}
    assert by_endpoint["hf-router"]["reason"] == "wire:responses=declared<probed"
    assert by_endpoint["hf-router"]["alternative"] == "inference-hub"
    assert by_endpoint["hf-router"]["wrappers"] == "unprobed"
    assert by_endpoint["cursor-auth2api"]["reason"] == "wire:responses=declared<probed"
    assert by_endpoint["llamacpp"]["reason"] == "enabled:false"
    assert by_endpoint["llamacpp"]["alternative"] is None
    assert by_endpoint["llamacpp"]["wrappers"] == "broken"


def test_routing_report_marks_included_rows_and_wrapper_states() -> None:
    config = probed_hf_router_responses(seed())
    rows = {row["endpoint"]: row for row in models.routing_report(config, "codex")}
    assert rows["hf-router"]["decision"] == "included"
    assert rows["hf-router"]["reason"] == "targets:native"
    assert rows["hf-router"]["alternative"] is None
    assert rows["hf-router"]["wrappers"] == "ok"
    grok = {row["endpoint"]: row for row in models.routing_report(SEED, "grok")}
    assert grok["hf-router"]["wrappers"] == "ok"
    assert grok["cursor-auth2api"]["wrappers"] == "unprobed"
    assert grok["cursor-auth2api"]["decision"] == "included"
    assert grok["openrouter"]["decision"] == "included"
    goose = {row["endpoint"]: row for row in models.routing_report(SEED, "goose")}
    assert goose["openrouter"]["decision"] == "excluded"
    assert goose["openrouter"]["reason"] == "targets:excluded"
    assert goose["openrouter"]["alternative"] == "inference-hub"
    claude = {row["endpoint"]: row for row in models.routing_report(SEED, "claude")}
    assert claude["hf-router"]["wrappers"] == "broken"
    assert claude["cursor-auth2api"]["wrappers"] == "unprobed"
    assert claude["openrouter"]["alternative"] is None


def test_credential_names_are_the_sorted_union_over_enabled_endpoints() -> None:
    assert models.credential_names(SEED) == [
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN_INFERENCE",
        "OPENROUTER_API_KEY_CLI_GRUNT",
        "OPENROUTER_API_KEY_CODEX_SIDECAR",
        "OPENROUTER_API_KEY_IDE_OPENCODE",
    ]
    config = seed()
    config["endpoints"]["openrouter"]["enabled"] = False
    assert models.credential_names(config) == [
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN_INFERENCE",
    ]


def test_registry_hash_is_stable_short_and_content_sensitive() -> None:
    digest = models.registry_hash(SEED)
    assert HEX16.match(digest)
    assert models.registry_hash(seed()) == digest
    assert models.registry_hash(json.loads(json.dumps(SEED, sort_keys=True))) == digest
    config = seed()
    config["description"] += "."
    assert models.registry_hash(config) != digest


# --- loading --------------------------------------------------------------------------


def test_load_registry_rejects_malformed_files(tmp_path: pathlib.Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(models.ModelsRegistryError, match="invalid JSON"):
        models.load_registry(broken)
    array = tmp_path / "array.json"
    array.write_text("[]", encoding="utf-8")
    with pytest.raises(models.ModelsRegistryError, match="must be a JSON object"):
        models.load_registry(array)
    with pytest.raises(OSError):
        models.load_registry(tmp_path / "missing.json")
    with pytest.raises(
        models.ModelsRegistryError, match="registry: must be a JSON object"
    ):
        models.validate_registry([])  # type: ignore[arg-type]


# --- schema details the contract fixes -------------------------------------------------


def test_top_level_schema_is_closed_and_versioned() -> None:
    config = seed()
    config["schemaVersion"] = 2
    rejects(config, "registry: schemaVersion must be 1")
    config = seed()
    del config["slots"]
    rejects(config, "registry: registry is missing required key 'slots'")
    config = seed()
    config["locks"] = {}
    rejects(config, "registry: registry.locks must be a list")


def test_policy_block_is_validated() -> None:
    config = seed()
    config["policy"]["hub"]["host"] = "0.0.0.0"
    rejects(config, "policy: hub.host must be a loopback address (L4)")
    config = seed()
    config["policy"]["hub"]["port"] = 8765
    rejects(config, "policy: hub.port 8765 is owned by another process (L4)")
    config = seed()
    config["policy"]["hub"]["port"] = 70000
    rejects(config, "policy: hub.port 70000 is not a valid TCP port")
    config = seed()
    config["policy"]["hub"]["port"] = 8317
    rejects(config, "policy: hub.port 8317 is owned by another process (L4)")
    config = seed()
    config["policy"]["capabilityProbe"]["ttlHours"] = 0
    rejects(config, "policy: capabilityProbe.ttlHours must be an integer >= 1")
    config = seed()
    config["policy"]["hub"]["haltEnv"] = "inference-halt"
    rejects(config, "policy: hub.haltEnv must be an environment variable name")
    config = seed()
    config["policy"]["localRamBudgetBytes"] = True
    rejects(config, "policy: policy.localRamBudgetBytes must be an integer >= 0")


def test_locks_are_well_formed_and_unique() -> None:
    config = seed()
    config["locks"].append({"id": "L1", "rule": "again", "enforcedBy": ["review"]})
    rejects(config, "locks: duplicate lock id 'L1'")
    config = seed()
    config["locks"][0]["id"] = "lock-one"
    rejects(config, "locks: locks[0].id 'lock-one' must look like L1")
    config = seed()
    config["locks"][0]["enforcedBy"] = []
    rejects(
        config, "locks: locks[0].enforcedBy must be a nonempty list of nonempty strings"
    )
    config = seed()
    config["locks"].append("L8")
    rejects(config, "locks: locks[7] must be an object")


def test_endpoint_scalar_fields_are_typed() -> None:
    config = seed()
    config["endpoints"]["hf-router"] = []
    rejects(config, "hf-router: endpoint must be an object")
    config = seed()
    config["endpoints"]["hf-router"]["kind"] = "cloud"
    rejects(config, "hf-router: kind 'cloud' must be one of bridge, hosted, local")
    config = seed()
    config["endpoints"]["hf-router"]["enabled"] = "yes"
    rejects(config, "hf-router: endpoint.enabled must be a boolean")
    config = seed()
    config["endpoints"]["hf-router"]["api"] = [
        "openai-completions",
        "openai-completions",
    ]
    rejects(config, "hf-router: api must not repeat values")
    config = seed()
    config["endpoints"]["hf-router"]["api"] = ["grpc"]
    rejects(config, "hf-router: api value 'grpc' is unsupported")
    config = seed()
    config["endpoints"]["hf-router"]["api"] = []
    rejects(
        config, "hf-router: endpoint.api must be a nonempty list of nonempty strings"
    )
    config = seed()
    config["endpoints"]["hf-router"]["tags"] = []
    rejects(config, "hf-router: endpoint.tags must be a nonempty list")


def test_base_url_shapes() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["baseUrl"] = "router.huggingface.co/v1"
    rejects(config, "hf-router: baseUrl must be an http(s) URL with a host")
    config = seed()
    config["endpoints"]["hf-router"]["baseUrl"] = "http://127.0.0.1:8081/v1"
    rejects(config, "hf-router: hosted baseUrl must use https://")
    config = seed()
    config["endpoints"]["ollama"]["baseUrl"] = "http://127.0.0.1:port/v1"
    rejects(config, "ollama: baseUrl port is invalid")
    config = seed()
    config["endpoints"]["ollama"]["api"] = ["ollama-native"]
    config["endpoints"]["ollama"]["baseUrl"] = "http://localhost:11434"
    assert models.validate_registry(config) == []
    config["endpoints"]["ollama"]["baseUrl"] = "http://[::1]:11434"
    assert models.validate_registry(config) == []


def test_auth_block_is_closed_and_typed() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["auth"] = "bearer"
    rejects(config, "hf-router: endpoint.auth must be an object or null")
    config = seed()
    config["endpoints"]["hf-router"]["auth"]["token"] = "NAME_ONLY"
    rejects(config, "hf-router: unknown auth key 'token'")
    config = seed()
    del config["endpoints"]["hf-router"]["auth"]["issuerHosts"]
    rejects(config, "hf-router: auth is missing required key 'issuerHosts'")
    config = seed()
    config["endpoints"]["hf-router"]["auth"]["issuerHosts"] = []
    rejects(config, "hf-router: auth.issuerHosts must be a nonempty list")


def test_wire_features_and_nested_blocks_are_closed() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["wire"] = "native"
    rejects(config, "hf-router: endpoint.wire must be an object")
    config = seed()
    del config["endpoints"]["hf-router"]["wire"]["messages"]
    rejects(config, "hf-router: wire is missing required key 'messages'")
    config = seed()
    config["endpoints"]["hf-router"]["features"]["speed"] = "native"
    rejects(config, "hf-router: unknown features key 'speed'")
    config = seed()
    config["endpoints"]["hf-router"]["concurrency"]["maxInFlight"] = 0
    rejects(config, "hf-router: concurrency.maxInFlight must be an integer >= 1")
    config = seed()
    config["endpoints"]["hf-router"]["budget"]["costBasis"] = "guess"
    rejects(config, "hf-router: budget.costBasis 'guess' is unsupported")
    config = seed()
    config["endpoints"]["hf-router"]["budget"]["dailyUsdCap"] = "2"
    rejects(config, "hf-router: budget.dailyUsdCap must be a number or null")
    config = seed()
    config["endpoints"]["hf-router"]["resource"]["ramBytes"] = -1
    rejects(config, "hf-router: resource.ramBytes must be an integer >= 0")
    config = seed()
    config["endpoints"]["hf-router"]["targets"] = []
    rejects(config, "hf-router: endpoint.targets must be an object")


def test_discovery_and_health_blocks() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["discovery"]["type"] = "guess"
    rejects(config, "hf-router: discovery.type 'guess' is unsupported")
    config = seed()
    config["endpoints"]["hf-router"]["discovery"]["injectV1"] = "yes"
    rejects(config, "hf-router: discovery.injectV1 must be a boolean")
    config = seed()
    config["endpoints"]["hf-router"]["discovery"]["injectV1"] = True
    assert models.validate_registry(config) == []
    config = seed()
    config["endpoints"]["hf-router"]["health"]["kind"] = "ping"
    rejects(config, "hf-router: health.kind 'ping' is unsupported")
    config = seed()
    del config["endpoints"]["ollama"]["health"]["path"]
    rejects(config, "ollama: health.path is required when health.kind is http")
    config = seed()
    config["endpoints"]["ollama"]["health"]["path"] = "api/version"
    rejects(config, "ollama: health.path must start with /")


def test_quirks_are_closed_and_typed() -> None:
    config = seed()
    config["endpoints"]["ollama"]["quirks"] = {"openai": {"stream_tool_calls": "no"}}
    rejects(config, "ollama: quirks.openai.stream_tool_calls must be a boolean")
    config = seed()
    config["endpoints"]["ollama"]["quirks"] = {"google": {}}
    rejects(config, "ollama: unknown quirks key 'google'")
    config = seed()
    config["endpoints"]["ollama"]["quirks"] = {
        "openai": {"compat": {"supportsStore": False}, "tools_stream": True},
        "anthropic": {"thinking_off_for_tools": True},
    }
    assert models.validate_registry(config) == []


def test_extension_blocks_are_typed_per_name() -> None:
    config = seed()
    config["endpoints"]["hf-router"]["x_codex"] = {"wire_api": "chat"}
    rejects(config, "hf-router: x_codex.wire_api must be 'responses'")
    config = seed()
    config["endpoints"]["hf-router"]["x_codex"] = {
        "env_key": "HUGGINGFACE_TOKEN_INFERENCE",
        "wire_api": "responses",
        "http_headers": {"X-Trace": "HF_TRACE_HEADER"},
        "query_params": {
            "api-version": "2026-09-02",
            "api_key": "HUGGINGFACE_TOKEN_INFERENCE",
        },
    }
    assert models.validate_registry(config) == []
    config["endpoints"]["hf-router"]["x_codex"]["http_headers"]["Authorization"] = (
        "Bearer x"
    )
    rejects(
        config,
        "hf-router: x_codex.http_headers.Authorization must be an environment variable name",
    )
    config = seed()
    config["endpoints"]["hf-router"]["x_codex"] = {
        "query_params": {"api_key": "literal-value"}
    }
    rejects(
        config,
        "hf-router: x_codex.query_params.api_key must be an environment variable name",
    )
    config = seed()
    config["endpoints"]["hf-router"]["x_codex"] = {"env_key": "lowercase"}
    rejects(config, "hf-router: x_codex.env_key must be an environment variable name")
    config = seed()
    config["endpoints"]["ollama"]["x_ollama"] = "2m"
    rejects(config, "ollama: x_ollama must be an object")
    config = seed()
    config["endpoints"]["ollama"]["x_ollama"]["maxLoadedModels"] = 0
    rejects(config, "ollama: x_ollama.maxLoadedModels must be an integer >= 1")
    config = seed()
    config["endpoints"]["lmstudio"]["x_lmstudio"]["jit"] = "on"
    rejects(config, "lmstudio: x_lmstudio.jit must be a boolean")
    config = seed()
    config["endpoints"]["hf-router"]["x_grok"] = {
        "api_backend": "openai",
        "context_window": 131072,
    }
    config["endpoints"]["hf-router"]["x_goose"] = {
        "engine": "openai",
        "requires_auth": True,
    }
    config["endpoints"]["hf-router"]["x_opencode"] = {
        "npm": "@ai-sdk/openai-compatible"
    }
    config["endpoints"]["hf-router"]["x_aider"] = {
        "litellm_provider": "openai",
        "alias": "hf",
    }
    config["endpoints"]["hf-router"]["x_fabric"] = {
        "vendor": "openai",
        "disable_responses_api": True,
    }
    config["endpoints"]["hf-router"]["x_hub"] = {
        "profile_root": "skills",
        "max_result_chars": 20000,
    }
    assert models.validate_registry(config) == []


def test_openrouter_extension_keys_must_be_declared_credentials() -> None:
    config = seed()
    config["endpoints"]["openrouter"]["x_openrouter"]["keys"][0]["env"] = (
        "OPENROUTER_API_KEY_OTHER"
    )
    rejects(
        config,
        "openrouter: x_openrouter.keys[0].env 'OPENROUTER_API_KEY_OTHER' must be declared",
    )
    config = seed()
    del config["endpoints"]["openrouter"]["x_openrouter"]["keys"][1]["consumers"]
    rejects(
        config, "openrouter: x_openrouter.keys[1] is missing required key 'consumers'"
    )
    config = seed()
    config["endpoints"]["openrouter"]["x_openrouter"]["keys"][2]["optional"] = "yes"
    rejects(config, "openrouter: x_openrouter.keys[2].optional must be a boolean")
    config = seed()
    config["endpoints"]["openrouter"]["x_openrouter"]["guardrail"]["limitUsd"] = None
    rejects(
        config,
        "openrouter: x_openrouter.guardrail.limitUsd must be a number or a string",
    )
    config = seed()
    config["endpoints"]["openrouter"]["x_openrouter"]["guardrail"]["limitUsd"] = 5
    del config["endpoints"]["openrouter"]["x_openrouter"]["keys"]
    assert models.validate_registry(config) == []
    del config["endpoints"]["openrouter"]["x_openrouter"]["guardrail"]
    assert models.validate_registry(config) == []


def test_model_rows_are_typed_and_coherent() -> None:
    config = seed()
    config["models"]["glm-5.3"] = "hf-router/glm"
    rejects(config, "glm-5.3: model must be an object")
    config = seed()
    config["models"]["glm-5.3"]["status"] = "shipped"
    rejects(config, "glm-5.3: status 'shipped' is unsupported")
    config = seed()
    config["models"]["glm-5.3"]["tier"] = "XL"
    rejects(config, "glm-5.3: tier 'XL' is unsupported")
    config = seed()
    config["models"]["glm-5.3"]["context"] = 0
    rejects(config, "glm-5.3: model.context must be an integer >= 1")
    config = seed()
    config["models"]["glm-5.3"]["modalities"]["input"] = []
    rejects(config, "glm-5.3: modalities.input must be a nonempty list")
    config = seed()
    config["models"]["glm-5.3"]["cost"]["basis"] = "free"
    rejects(config, "glm-5.3: cost.basis 'free' is unsupported")
    config = seed()
    config["models"]["cursor-grok-4.6"]["cost"]["inputPer1M"] = 0
    rejects(config, "cursor-grok-4.6: quota-billed rows must carry null cost, never 0")
    config = seed()
    del config["models"]["qwen2.5-7b"]["resource"]
    rejects(config, "qwen2.5-7b: resource.ramBytes is required on local endpoints")
    config = seed()
    config["models"]["qwen2.5-7b"]["resource"]["ramBytes"] = "5G"
    rejects(config, "qwen2.5-7b: resource.ramBytes must be an integer >= 0")
    config = seed()
    config["models"]["glm-5.3"]["resource"] = {"ramBytes": 0}
    config["models"]["glm-5.3"]["modelsDev"] = "zai/glm-5.3"
    config["models"]["glm-5.3"]["x_aider"] = {"alias": "glm"}
    assert models.validate_registry(config) == []


def test_slots_are_exactly_six_and_name_enabled_models() -> None:
    config = seed()
    config["slots"]["vision"] = None
    rejects(config, "slots: unknown slots key 'vision'")
    config = seed()
    del config["slots"]["embed"]
    rejects(config, "slots: slots is missing required key 'embed'")
    config = seed()
    config["slots"]["large"] = "nope"
    rejects(config, "slots: large names unknown model 'nope'")
    config = seed()
    config["slots"]["small"] = 7
    rejects(config, "slots: small must be a nonempty string")
    config = seed()
    config["aliases"]["local-default"] = 7
    rejects(config, "aliases: local-default must be a nonempty string")
    config = seed()
    config["models"]["glm-5.3"]["enabled"] = False
    del config["aliases"]["glm53"]
    del config["aliases"]["fabric-default"]
    rejects(config, "slots: large names disabled model 'glm-5.3'")
    config["slots"]["large"] = None
    assert models.validate_registry(config) == []


# --- CLI --------------------------------------------------------------------------------


def success_line(stdout: str) -> str:
    lines = [line for line in stdout.splitlines() if line.startswith("SUCCESS:")]
    assert len(lines) == 1, stdout
    return lines[0]


def test_cli_success_line_and_read_only_behaviour(
    capsys: pytest.CaptureFixture[str],
) -> None:
    before = SEED_PATH.read_bytes()
    assert cli.main(["--registry", str(SEED_PATH)]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == success_line(captured.out)
    assert captured.out.strip() == (
        "SUCCESS:models-registry endpoints=7 models=15 warnings=0 "
        f"hash={models.registry_hash(SEED)}"
    )
    assert captured.err == ""
    assert SEED_PATH.read_bytes() == before
    assert cli.main([]) == 0
    assert success_line(capsys.readouterr().out).startswith("SUCCESS:models-registry")


def test_cli_json_report(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--registry", str(SEED_PATH), "--json"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out[: out.index("SUCCESS:")])
    assert set(payload) == {"warnings", "credential_names", "routing"}
    assert payload["warnings"] == []
    assert payload["credential_names"] == models.credential_names(SEED)
    assert set(payload["routing"]) == set(models.RUNTIMES)
    assert payload["routing"]["codex"] == models.routing_report(SEED, "codex")
    assert all(row["decision"] == "excluded" for row in payload["routing"]["codex"])
    assert "FAKE" not in out


def test_cli_runtime_text_report(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--registry", str(SEED_PATH), "--runtime", "codex"]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0].split() == [
        "endpoint",
        "runtime",
        "decision",
        "reason",
        "alternative",
        "wrappers",
    ]
    hf_router = next(line for line in lines if line.startswith("hf-router"))
    assert hf_router.split() == [
        "hf-router",
        "codex",
        "excluded",
        "wire:responses=declared<probed",
        "inference-hub",
        "unprobed",
    ]
    llamacpp = next(line for line in lines if line.startswith("llamacpp"))
    assert llamacpp.split() == [
        "llamacpp",
        "codex",
        "excluded",
        "enabled:false",
        "-",
        "broken",
    ]
    assert lines[-1].startswith("SUCCESS:models-registry")
    assert cli.main(["--registry", str(SEED_PATH), "--runtime", "vim"]) == 2
    out = capsys.readouterr().out
    assert out.startswith(
        "FAILED:models-registry unsupported runtime 'vim'; expected one of codex"
    )
    assert "SUCCESS:" not in out


def test_cli_reports_warnings_on_stderr(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = seed()
    config["models"]["qwen3-8b"]["resource"]["ramBytes"] = 8 * 1024**3
    path = tmp_path / "models.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    assert cli.main(["--registry", str(path)]) == 0
    captured = capsys.readouterr()
    assert "warnings=1" in success_line(captured.out)
    assert captured.err.startswith("WARNING:models-registry local RAM")


def test_cli_failed_paths(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = seed()
    config["extra"] = 1
    path = tmp_path / "models.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    assert cli.main(["--registry", str(path)]) == 2
    assert capsys.readouterr().out.strip() == (
        "FAILED:models-registry registry: unknown registry key 'extra'"
    )
    assert cli.main(["--registry", str(tmp_path / "missing.json")]) == 2
    out = capsys.readouterr().out
    assert out.startswith("FAILED:models-registry ")
    assert "missing.json" in out
    assert "SUCCESS:" not in out


def test_cli_module_entrypoint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", [str(CLI_PATH), "--registry", str(SEED_PATH)])
    with pytest.raises(SystemExit) as info:
        runpy.run_path(str(CLI_PATH), run_name="__main__")
    assert info.value.code == 0
    assert success_line(capsys.readouterr().out).endswith(models.registry_hash(SEED))


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_subprocess_success_failed_and_json(tmp_path: pathlib.Path) -> None:
    completed = run_cli("--registry", str(SEED_PATH))
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert success_line(completed.stdout) == (
        "SUCCESS:models-registry endpoints=7 models=15 warnings=0 "
        f"hash={models.registry_hash(SEED)}"
    )

    config = seed()
    del config["endpoints"]["cursor-auth2api"]["retiresWhen"]
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(config), encoding="utf-8")
    failed = run_cli("--registry", str(broken))
    assert failed.returncode == 2, failed.stdout + failed.stderr
    assert failed.stdout.strip() == (
        "FAILED:models-registry cursor-auth2api: retiresWhen is required (L3)"
    )

    as_json = run_cli("--registry", str(SEED_PATH), "--json")
    assert as_json.returncode == 0, as_json.stdout + as_json.stderr
    payload = json.loads(as_json.stdout[: as_json.stdout.index("SUCCESS:")])
    assert payload["routing"]["grok"] == models.routing_report(SEED, "grok")
    assert payload["credential_names"] == models.credential_names(SEED)
