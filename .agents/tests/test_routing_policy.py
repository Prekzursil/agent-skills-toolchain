"""Red-proof tests for ``.agents/scripts/routing_policy.py`` (D11: policy + PACE)."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import pathlib
import re
import runpy
import sys
import types
from collections.abc import Callable
from typing import Any

import pytest


AGENTS_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = AGENTS_ROOT / "scripts"
MODULE_PATH = SCRIPTS_ROOT / "routing_policy.py"
POLICY_PATH = AGENTS_ROOT / "routing-policy.json"
REGISTRY_PATH = AGENTS_ROOT / "models.json"

Mutator = Callable[[dict[str, Any], dict[str, Any]], None]


def _load_module() -> Any:
    if str(SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_ROOT))
    spec = importlib.util.spec_from_file_location("routing_policy", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["routing_policy"] = module
    spec.loader.exec_module(module)
    return module


rp = _load_module()
POLICY: dict[str, Any] = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
REGISTRY: dict[str, Any] = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
EXPECTED_CLASSES = {
    "simple",
    "code-edit",
    "extract-json",
    "long-context",
    "summarize",
    "cli-grunt",
}
HANDOFF = "handoff: basic-memory :8765 note + agent-mail :8812 message to the owner"


def _fresh() -> tuple[dict[str, Any], dict[str, Any]]:
    return copy.deepcopy(POLICY), copy.deepcopy(REGISTRY)


def _set(*path: str, value: Any) -> Mutator:
    def mutate(policy: dict[str, Any], _registry: dict[str, Any]) -> None:
        target: Any = policy
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return mutate


def _delete(*path: str) -> Mutator:
    def mutate(policy: dict[str, Any], _registry: dict[str, Any]) -> None:
        target: Any = policy
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return mutate


def _set_registry(*path: str, value: Any) -> Mutator:
    def mutate(_policy: dict[str, Any], registry: dict[str, Any]) -> None:
        target: Any = registry
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return mutate


def _many(*mutators: Mutator) -> Mutator:
    def mutate(policy: dict[str, Any], registry: dict[str, Any]) -> None:
        for mutator in mutators:
            mutator(policy, registry)

    return mutate


def _rename_class(old: str, new: str) -> Mutator:
    def mutate(policy: dict[str, Any], _registry: dict[str, Any]) -> None:
        policy["classes"][new] = policy["classes"].pop(old)

    return mutate


def _credential_shaped() -> str:
    return "hf" + "_" + "x" * 24


RED_PROOF: list[tuple[str, str, Mutator]] = [
    ("V-P1", "unknown top-level key", _set("$comment", value="explain here")),
    ("V-P1", "missing top-level key", _delete("review")),
    ("V-P1", "policy not an object", lambda p, _r: p.update(classes=None)),
    ("V-P1", "schemaVersion", _set("schemaVersion", value=2)),
    ("V-P1", "classes empty", _set("classes", value={})),
    ("V-P1", "class name case", _rename_class("simple", "Simple")),
    ("V-P1", "class not an object", _set("classes", "simple", value=[])),
    ("V-P1", "unknown class key", _set("classes", "simple", "notes", value="x")),
    ("V-P1", "missing class key", _delete("classes", "simple", "justification")),
    ("V-P1", "primary not a string", _set("classes", "simple", "primary", value=7)),
    (
        "V-P1",
        "escalate_to not a list",
        _set("classes", "simple", "escalate_to", value="glm-5.3"),
    ),
    (
        "V-P1",
        "escalate_to repeats",
        _set("classes", "simple", "escalate_to", value=["glm-5.3", "glm-5.3"]),
    ),
    (
        "V-P1",
        "escalate_to repeats primary",
        _set("classes", "simple", "escalate_to", value=["qwen2.5-7b"]),
    ),
    (
        "V-P1",
        "justification empty",
        _set("classes", "simple", "justification", value=" "),
    ),
    ("V-P1", "callers empty", _set("classes", "cli-grunt", "callers", value=[])),
    (
        "V-P1",
        "callers unknown",
        _set("classes", "cli-grunt", "callers", value=["codex", "telnet"]),
    ),
    (
        "V-P1",
        "unknown exponent key",
        _set("classes", "simple", "exponents", "latency", value=0),
    ),
    (
        "V-P1",
        "unknown pace key",
        _set("classes", "simple", "pace", "F", value="glm-5.3"),
    ),
    ("V-P1", "rung not a string", _set("classes", "simple", "pace", "A", value=3)),
    ("V-P1", "triggers empty", _set("classes", "simple", "pace", "triggers", value=[])),
    (
        "V-P1",
        "unknown trigger",
        _set("classes", "simple", "pace", "triggers", value=["timeout", "bad-mood"]),
    ),
    ("V-P1", "unknown review key", _set("review", "notes", value="x")),
    ("V-P1", "review cadence", _set("review", "cadence", value="whenever")),
    ("V-P2", "primary unknown", _set("classes", "simple", "primary", value="gpt-9")),
    (
        "V-P2",
        "primary endpoint pin mismatch",
        _set("classes", "simple", "primary", value="qwen2.5-7b@lmstudio"),
    ),
    (
        "V-P2",
        "escalation unknown",
        _set("classes", "simple", "escalate_to", value=["glm-9"]),
    ),
    (
        "V-P2",
        "rung unknown",
        _set("classes", "simple", "pace", "A", value="glm-9@hf-router"),
    ),
    (
        "V-P2",
        "model names a missing endpoint",
        _set_registry("models", "glm-5.3", "endpoint", value="gone"),
    ),
    (
        "V-P3",
        "exponents sum",
        _set("classes", "simple", "exponents", "cost", value=0.9),
    ),
    (
        "V-P3",
        "exponent range",
        _set("classes", "simple", "exponents", "cost", value=-0.3),
    ),
    (
        "V-P3",
        "exponent bool",
        _set("classes", "simple", "exponents", "cost", value=True),
    ),
    ("V-P4", "spend_share sum", _set("classes", "simple", "spend_share", value=0.5)),
    ("V-P4", "spend_share range", _set("classes", "simple", "spend_share", value=1.5)),
    (
        "V-P4",
        "spend_share type",
        _set("classes", "simple", "spend_share", value="0.05"),
    ),
    (
        "V-P5",
        "two cursor rungs",
        _set("classes", "simple", "pace", "A", value="cursor-grok-4.6"),
    ),
    (
        "V-P6",
        "no local or procedure rung",
        _set(
            "classes", "code-edit", "pace", "C", value="cursor-grok-4.6@cursor-auth2api"
        ),
    ),
    (
        "V-P7",
        "E is a model",
        _set("classes", "simple", "pace", "E", value="qwen2.5-7b"),
    ),
    (
        "V-P7",
        "E lacks agent-mail",
        _set(
            "classes", "simple", "pace", "E", value="handoff: basic-memory :8765 note"
        ),
    ),
    (
        "V-P7",
        "E lacks basic-memory",
        _set(
            "classes", "simple", "pace", "E", value="handoff: agent-mail :8812 message"
        ),
    ),
    (
        "V-P8",
        "two rungs one endpoint",
        _set("classes", "simple", "pace", "C", value="glm-5.3@hf-router"),
    ),
    (
        "V-P9",
        "openrouter escalation without callers",
        _set("classes", "simple", "escalate_to", value=["glm-5.2-free"]),
    ),
    (
        "V-P9",
        "openrouter primary with cursor caller",
        _set("classes", "cli-grunt", "callers", value=["cursor"]),
    ),
    (
        "V-P9",
        "openrouter rung with claude caller",
        _set("classes", "code-edit", "callers", value=["codex", "claude"]),
    ),
    (
        "V-P10",
        "retiring primary without a durable escalation",
        _many(
            _set_registry("models", "cursor-grok-4.6", "status", value="live"),
            _set("classes", "extract-json", "primary", value="cursor-grok-4.6"),
            _set("classes", "extract-json", "escalate_to", value=[]),
            _set(
                "classes",
                "extract-json",
                "pace",
                "P",
                value="cursor-grok-4.6@cursor-auth2api",
            ),
            _set("classes", "extract-json", "pace", "A", value="glm-5.3@hf-router"),
        ),
    ),
    (
        "V-P11",
        "floor not an object",
        _set("classes", "simple", "floors", value=["features.tools"]),
    ),
    (
        "V-P11",
        "floor unknown capability",
        _set("classes", "simple", "floors", value={"features.telepathy": "declared"}),
    ),
    (
        "V-P11",
        "floor not a lattice state",
        _set("classes", "simple", "floors", value={"features.tools": "strong"}),
    ),
    (
        "V-P11",
        "floor state not a string",
        _set("classes", "simple", "floors", value={"features.tools": ["declared"]}),
    ),
    (
        "V-P12",
        "pinned_until free text",
        _set("classes", "simple", "pinned_until", value="next month"),
    ),
    (
        "V-P12",
        "pinned_until impossible date",
        _set("classes", "simple", "pinned_until", value="2026-02-30"),
    ),
    (
        "V-P12",
        "pinned_until not a string",
        _set("classes", "simple", "pinned_until", value=20261001),
    ),
    ("V-P12", "review last_review", _set("review", "last_review", value="yesterday")),
    (
        "V-P13",
        "eval-gated primary",
        _many(
            _set("classes", "simple", "primary", value="qwen3-8b"),
            _set("classes", "simple", "pace", "P", value="qwen3-8b@ollama"),
        ),
    ),
    (
        "V-P13",
        "disabled primary model",
        _set_registry("models", "qwen2.5-7b", "enabled", value=False),
    ),
    (
        "V-P13",
        "primary on a disabled endpoint",
        _set_registry("endpoints", "ollama", "enabled", value=False),
    ),
    (
        "V-P14",
        "P differs from primary",
        _set("classes", "simple", "pace", "P", value="glm53"),
    ),
    (
        "V-P14",
        "P is a procedure",
        _set("classes", "simple", "pace", "P", value="procedure: think harder"),
    ),
    (
        "L6",
        "url in justification",
        _set("classes", "simple", "justification", value="see https://example.invalid"),
    ),
    (
        "L6",
        "credential-shaped rung text",
        _set(
            "classes", "simple", "pace", "E", value=f"{HANDOFF} {_credential_shaped()}"
        ),
    ),
    (
        "L6",
        "url inside a list",
        _set("classes", "simple", "escalate_to", value=["ftp://glm-5.3"]),
    ),
]


@pytest.mark.parametrize(
    ("rule", "mutate"),
    [(rule, mutate) for rule, _label, mutate in RED_PROOF],
    ids=[f"{rule}:{label}" for rule, label, _mutate in RED_PROOF],
)
def test_red_proof_every_rule_has_a_failing_fixture(rule: str, mutate: Mutator) -> None:
    policy, registry = _fresh()
    mutate(policy, registry)

    with pytest.raises(rp.PolicyError, match=re.escape(rule)):
        rp.validate_policy(policy, registry)


def test_committed_policy_validates_against_committed_registry() -> None:
    policy = rp.load_policy(POLICY_PATH)
    registry = rp.load_registry(REGISTRY_PATH)

    warnings = rp.validate_policy(policy, registry)

    assert set(policy["classes"]) == EXPECTED_CLASSES
    assert policy["review"]["owner"] == "human write-back only"
    assert policy["review"]["cadence"] == "monthly"
    assert warnings, "the unprobed cursor rung must surface as a warning, not be hidden"
    assert all(
        "V-P13" in warning and "cursor-grok-4.6" in warning for warning in warnings
    )
    assert len(warnings) == sum(
        1
        for spec in policy["classes"].values()
        for rung in ("P", "A", "C")
        if spec["pace"][rung].startswith("cursor-grok-4.6")
    )


def test_committed_policy_pins_the_pace_shape() -> None:
    for name, spec in POLICY["classes"].items():
        pace = spec["pace"]
        assert set(pace) == {"P", "A", "C", "E", "triggers"}, name
        assert pace["E"].startswith("handoff:"), name
        assert "basic-memory :8765" in pace["E"] and "agent-mail :8812" in pace["E"], (
            name
        )
        cursor_rungs = [r for r in ("P", "A", "C") if pace[r].startswith("cursor-")]
        assert len(cursor_rungs) <= 1, name
        assert abs(sum(spec["exponents"].values()) - 1.0) < 1e-9, name
    assert (
        abs(sum(spec["spend_share"] for spec in POLICY["classes"].values()) - 1.0)
        < 1e-9
    )
    assert POLICY["classes"]["cli-grunt"]["callers"] == ["codex", "cli"]
    assert POLICY["classes"]["code-edit"]["callers"] == ["codex", "cli"]
    openrouter_classes = {
        name
        for name, spec in POLICY["classes"].items()
        if any(
            "glm-5.2-free" in ref
            for ref in [
                spec["primary"],
                *spec["escalate_to"],
                *(spec["pace"][r] for r in ("P", "A", "C")),
            ]
        )
    }
    assert openrouter_classes == {"code-edit", "cli-grunt"}
    assert all("callers" in POLICY["classes"][name] for name in openrouter_classes)


def test_policy_file_carries_names_only() -> None:
    text = POLICY_PATH.read_text(encoding="utf-8")

    assert "http" not in text
    assert "://" not in text
    assert rp.LITERAL_SECRET_RE.search(text) is None
    assert (
        re.search(r"(?i)(api[_-]?key|secret|token|password|bearer)\s*[:=]", text)
        is None
    )
    assert re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", text) is None


def test_validate_policy_rejects_a_registry_without_models_or_endpoints() -> None:
    with pytest.raises(rp.PolicyError, match="endpoints and models"):
        rp.validate_policy(copy.deepcopy(POLICY), {"endpoints": {}})


def test_aliases_resolve_and_a_malformed_alias_table_is_ignored() -> None:
    policy, registry = _fresh()
    registry["aliases"] = None

    model_id, _model, endpoint_id, _endpoint = rp.resolve_ref(registry, "glm-5.3")
    assert (model_id, endpoint_id) == ("glm-5.3", "hf-router")
    with pytest.raises(rp.PolicyError, match="V-P2"):
        rp.resolve_ref(registry, "glm53")

    _policy, registry = _fresh()
    assert rp.resolve_ref(registry, "glm53")[0] == "glm-5.3"
    assert rp.resolve_ref(registry, "glm53@hf-router")[2] == "hf-router"
    assert rp.validate_policy(policy, registry)


def test_eval_gated_escalations_and_disabled_rungs_are_warnings_not_errors() -> None:
    policy, registry = _fresh()
    policy["classes"]["code-edit"]["escalate_to"] = ["qwen3-8b"]
    registry["endpoints"]["cursor-auth2api"]["enabled"] = False

    warnings = rp.validate_policy(policy, registry)

    assert any(
        "classes.code-edit.escalate_to" in w and "'qwen3-8b' is eval-gated" in w
        for w in warnings
    )
    assert any("classes.simple.pace.C" in w and "is disabled" in w for w in warnings)
    assert not any("is unprobed" in w for w in warnings)


def test_retiring_primary_passes_with_a_durable_escalation() -> None:
    policy, registry = _fresh()
    registry["models"]["cursor-grok-4.6"]["status"] = "live"
    spec = policy["classes"]["extract-json"]
    spec["primary"] = "cursor-grok-4.6"
    spec["escalate_to"] = ["qwen2.5-7b"]
    spec["pace"]["P"] = "cursor-grok-4.6@cursor-auth2api"
    spec["pace"]["A"] = "glm-5.3@hf-router"

    assert rp.validate_policy(policy, registry) == []


def test_openrouter_is_allowed_when_callers_stay_within_codex_and_cli() -> None:
    policy, registry = _fresh()
    policy["classes"]["cli-grunt"]["callers"] = ["cli"]

    rp.validate_policy(policy, registry)


def test_route_returns_ordered_rungs_without_skipping_unprobed_ones() -> None:
    policy, registry = _fresh()

    rungs = rp.route(policy, registry, "simple")

    assert [rung["rung"] for rung in rungs] == ["P", "A", "C", "E"]
    assert rungs[0] == {
        "rung": "P",
        "ref": "qwen2.5-7b@ollama",
        "kind": "model",
        "model_id": "qwen2.5-7b",
        "endpoint": "ollama",
        "status": "live",
    }
    assert rungs[1]["endpoint"] == "hf-router"
    assert rungs[2]["model_id"] == "cursor-grok-4.6"
    assert rungs[2]["status"] == "unprobed"
    assert rungs[3] == {
        "rung": "E",
        "ref": POLICY["classes"]["simple"]["pace"]["E"],
        "kind": "procedure",
        "status": "procedure",
    }


def test_route_reports_a_procedure_contingency_and_disabled_rungs_truthfully() -> None:
    policy, registry = _fresh()
    registry["models"]["cursor-grok-4.6"]["enabled"] = False

    rungs = rp.route(policy, registry, "long-context")

    assert rungs[1]["status"] == "disabled"
    assert rungs[2]["kind"] == "procedure"
    assert rungs[2]["ref"].startswith("procedure:")
    assert "model_id" not in rungs[2]


def test_route_rejects_unknown_or_malformed_classes() -> None:
    policy, registry = _fresh()

    with pytest.raises(rp.PolicyError, match="unknown task class"):
        rp.route(policy, registry, "telepathy")
    with pytest.raises(rp.PolicyError, match="unknown task class"):
        rp.route({"classes": []}, registry, "simple")
    policy["classes"]["simple"]["pace"] = "later"
    with pytest.raises(rp.PolicyError, match="pace: must be an object"):
        rp.route(policy, registry, "simple")
    with pytest.raises(rp.PolicyError, match="endpoints and models"):
        rp.route(POLICY, {}, "simple")


def test_load_registry_prefers_the_sibling_registry_module(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    calls: list[pathlib.Path] = []

    def fake_load_registry(path: pathlib.Path) -> dict[str, Any]:
        calls.append(path)
        return copy.deepcopy(REGISTRY)

    fake = types.SimpleNamespace(load_registry=fake_load_registry)
    monkeypatch.setitem(sys.modules, "models_control_plane", fake)

    loaded = rp.load_registry(tmp_path / "never-read.json")

    assert calls == [tmp_path / "never-read.json"]
    assert set(loaded["models"]) == set(REGISTRY["models"])


def test_load_registry_wraps_sibling_failures_as_policy_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    def failing_load_registry(_path: pathlib.Path) -> dict[str, Any]:
        raise ValueError("schemaVersion must be 1")

    fake = types.SimpleNamespace(load_registry=failing_load_registry)
    monkeypatch.setitem(sys.modules, "models_control_plane", fake)

    with pytest.raises(rp.PolicyError, match="registry .*schemaVersion must be 1"):
        rp.load_registry(tmp_path / "models.json")


def test_load_registry_falls_back_to_json_when_the_sibling_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.setitem(sys.modules, "models_control_plane", None)
    monkeypatch.setattr(
        sys, "path", [entry for entry in sys.path if entry != str(SCRIPTS_ROOT)]
    )
    registry_file = tmp_path / "models.json"
    registry_file.write_text(json.dumps(REGISTRY), encoding="utf-8")

    loaded = rp.load_registry(str(registry_file))

    assert set(loaded["endpoints"]) == set(REGISTRY["endpoints"])
    assert sys.path[0] == str(SCRIPTS_ROOT)


def test_load_registry_rejects_registries_without_the_two_tables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.setitem(sys.modules, "models_control_plane", None)
    registry_file = tmp_path / "models.json"
    registry_file.write_text(json.dumps({"models": {}}), encoding="utf-8")

    with pytest.raises(rp.PolicyError, match="endpoints and models"):
        rp.load_registry(registry_file)


def test_load_policy_reports_missing_unreadable_and_non_object_files(
    tmp_path: pathlib.Path,
) -> None:
    with pytest.raises(rp.PolicyError, match="missing"):
        rp.load_policy(tmp_path / "absent.json")
    directory = tmp_path / "dir.json"
    directory.mkdir()
    with pytest.raises(rp.PolicyError, match="unreadable"):
        rp.load_policy(directory)
    listing = tmp_path / "list.json"
    listing.write_text("[]", encoding="utf-8")
    with pytest.raises(rp.PolicyError, match="JSON object"):
        rp.load_policy(listing)


def test_loud_fallback_on_a_missing_file(tmp_path: pathlib.Path) -> None:
    stderr = io.StringIO()

    policy, source = rp.load_policy_or_fallback(
        tmp_path / "routing-policy.json", REGISTRY, stderr=stderr
    )

    assert (policy, source) == (None, "fallback")
    lines = stderr.getvalue().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("FAILED:routing-policy missing ")
    assert lines[0].endswith("; falling back to registry slots")


def test_loud_fallback_on_invalid_json(tmp_path: pathlib.Path) -> None:
    broken = tmp_path / "routing-policy.json"
    broken.write_text('{"schemaVersion": 1,', encoding="utf-8")
    stderr = io.StringIO()

    policy, source = rp.load_policy_or_fallback(broken, REGISTRY, stderr=stderr)

    assert (policy, source) == (None, "fallback")
    lines = stderr.getvalue().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("FAILED:routing-policy invalid JSON in ")
    assert "falling back to registry slots" in lines[0]


def test_loud_fallback_on_a_policy_that_fails_validation(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    policy, _registry = _fresh()
    policy["classes"]["simple"]["pace"]["C"] = "glm-5.3@hf-router"
    path = tmp_path / "routing-policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")

    loaded, source = rp.load_policy_or_fallback(path, REGISTRY)

    assert (loaded, source) == (None, "fallback")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("\n") == 1
    assert captured.err.startswith("FAILED:routing-policy V-P8 ")


def test_valid_policy_loads_quietly() -> None:
    stderr = io.StringIO()

    policy, source = rp.load_policy_or_fallback(POLICY_PATH, REGISTRY, stderr=stderr)

    assert source == "policy"
    assert policy is not None and set(policy["classes"]) == EXPECTED_CLASSES
    assert stderr.getvalue() == ""


def _run_main(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = rp.main(argv)
    return code, capsys.readouterr().out


def test_cli_success_prints_one_summary_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out = _run_main(
        ["--policy", str(POLICY_PATH), "--registry", str(REGISTRY_PATH)], capsys
    )

    assert code == 0
    assert out.splitlines() == ["SUCCESS:routing-policy classes=6 warnings=4"]


def test_cli_json_report_for_one_class(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _run_main(
        [
            "--policy",
            str(POLICY_PATH),
            "--registry",
            str(REGISTRY_PATH),
            "--json",
            "--class",
            "cli-grunt",
        ],
        capsys,
    )

    assert code == 0
    *body, summary = out.splitlines()
    assert (
        summary == "SUCCESS:routing-policy classes=6 warnings=4 class=cli-grunt rungs=4"
    )
    report = json.loads("\n".join(body))
    assert set(report) == {"policy", "registry", "classes", "warnings", "routes"}
    assert set(report["classes"]) == EXPECTED_CLASSES
    assert list(report["routes"]) == ["cli-grunt"]
    assert [rung["rung"] for rung in report["routes"]["cli-grunt"]] == [
        "P",
        "A",
        "C",
        "E",
    ]
    assert report["routes"]["cli-grunt"][0]["endpoint"] == "openrouter"
    assert len(report["warnings"]) == 4


def test_cli_json_report_covers_every_class(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _run_main(
        ["--policy", str(POLICY_PATH), "--registry", str(REGISTRY_PATH), "--json"],
        capsys,
    )

    assert code == 0
    *body, summary = out.splitlines()
    assert summary == "SUCCESS:routing-policy classes=6 warnings=4"
    assert set(json.loads("\n".join(body))["routes"]) == EXPECTED_CLASSES


def test_cli_fails_closed_on_unknown_class_missing_policy_and_bad_registry(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = _run_main(
        [
            "--policy",
            str(POLICY_PATH),
            "--registry",
            str(REGISTRY_PATH),
            "--class",
            "x",
        ],
        capsys,
    )
    assert code == 2
    assert out.splitlines() == ["FAILED:routing-policy unknown task class 'x'"]

    code, out = _run_main(
        ["--policy", str(tmp_path / "absent.json"), "--registry", str(REGISTRY_PATH)],
        capsys,
    )
    assert code == 2
    assert out.startswith("FAILED:routing-policy missing ")

    code, out = _run_main(
        ["--policy", str(POLICY_PATH), "--registry", str(tmp_path / "absent.json")],
        capsys,
    )
    assert code == 2
    assert out.startswith("FAILED:routing-policy ")
    assert out.count("\n") == 1


def test_cli_defaults_point_at_the_committed_files() -> None:
    assert rp.DEFAULT_POLICY_PATH == POLICY_PATH
    assert rp.DEFAULT_REGISTRY_PATH == REGISTRY_PATH
    assert rp.main([]) == 0


def test_module_entry_point_runs_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "routing_policy.py",
            "--policy",
            str(POLICY_PATH),
            "--registry",
            str(REGISTRY_PATH),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(MODULE_PATH), run_name="__main__")

    assert excinfo.value.code == 0
    assert capsys.readouterr().out.startswith("SUCCESS:routing-policy ")
