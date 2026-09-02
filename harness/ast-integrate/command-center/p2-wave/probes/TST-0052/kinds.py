"""Live parsers for each manifest/config kind TST-0052 measures.

Production parsers are the real loaders. json.loads is the both-states
detector control: it ACCEPTS an unknown field so the unknown-field test
is capable of failing.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import jsonschema  # noqa: E402
from hook_load.load_probe import LoadRefusal, load_config  # noqa: E402
from marketplace.handoff import build_handoff, validate_handoff  # noqa: E402
from plugin.errors import PluginManifestError  # noqa: E402

try:
    from plugin.errors import HandoffValidationError  # noqa: E402
except ImportError:
    from plugin.errors import HandoffValidationError as HandoffValidationError  # noqa: E402
from plugin.exec_policy import PolicyDenied, build_policy  # noqa: E402
from plugin.exec_policy import validate_policy  # noqa: E402
from plugin.payload import load_plugin_manifest  # noqa: E402

UNKNOWN_FIELD = "__tst0052_unknown__"
UNKNOWN_VALUE = "this-value-must-not-be-applied"
UNIT = "TST-0052"

_PARSE_FAIL = (
    PluginManifestError,
    HandoffValidationError,
    LoadRefusal,
    PolicyDenied,
    jsonschema.ValidationError,
    jsonschema.SchemaError,
    ValueError,
    TypeError,
    RuntimeError,
)


def _clone(doc: dict) -> dict:
    return json.loads(json.dumps(doc))


def _with_unknown(doc: dict) -> dict:
    mutant = _clone(doc)
    mutant[UNKNOWN_FIELD] = UNKNOWN_VALUE
    return mutant


def _err_text(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _valid_plugin() -> dict:
    return {
        "name": "tst-0052-fixture",
        "version": "1.0.0",
        "description": "Known-good plugin.json for the both-states pair",
        "permissions": ["fs:write:plugins/tst-0052-fixture"],
        "skills": ["skills/demo/SKILL.md"],
        "rules": ["rules/demo.md"],
        "hooks": ["hooks/demo.json"],
    }


def parse_plugin_manifest(doc: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="tst0052-plugin-") as tmp:
        root = Path(tmp)
        (root / "plugin.json").write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return load_plugin_manifest(root)


def parse_install_handoff(doc: dict) -> dict:
    return validate_handoff(doc)


def parse_exec_policy(doc: dict) -> dict:
    validate_policy(doc)
    return doc


def parse_hooks_json(doc: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="tst0052-hooks-") as tmp:
        path = Path(tmp) / "hooks.json"
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return load_config(path)


def parse_lenient_json(doc: dict) -> dict:
    """Negative control: json.loads keeps unknown keys. Must ACCEPT the mutant."""
    return json.loads(json.dumps(doc))


def _try_parse(parse: Callable[[dict], Any], doc: dict) -> tuple[bool, str, Any]:
    try:
        got = parse(doc)
        return True, "", got
    except _PARSE_FAIL as exc:
        return False, _err_text(exc), None


def _fate_if_accepted(parsed: Any) -> str:
    if not isinstance(parsed, dict):
        return "parser returned a non-dict; extra key fate not applicable"
    if UNKNOWN_FIELD not in parsed:
        return "extra key was dropped before the caller saw the object"
    retained = parsed.get(UNKNOWN_FIELD)
    return (
        "json.loads retained the extra key on the dict "
        f"({UNKNOWN_FIELD}={retained!r}); named getters (name, version, "
        "permissions, hooks) never read it, so the client applies the known "
        "fields and silently ignores the value"
    )


def _measure_kind(
    *,
    kind: str,
    parser: str,
    production: bool,
    parse: Callable[[dict], Any],
    valid: dict,
) -> dict:
    known_ok, known_err, _known_got = _try_parse(parse, valid)
    mutant = _with_unknown(valid)
    unk_ok, unk_err, unk_got = _try_parse(parse, mutant)
    if unk_ok:
        fate = _fate_if_accepted(unk_got)
    else:
        fate = (
            "parser refused the document; the client never receives the extra "
            "value and does not apply it"
        )
    return {
        "kind": kind,
        "parser": parser,
        "production": production,
        "unknown_field": UNKNOWN_FIELD,
        "unknown_value": UNKNOWN_VALUE,
        "known_accepted": known_ok,
        "known_error": known_err,
        "unknown_accepted": unk_ok,
        "unknown_rejected": (not unk_ok),
        "unknown_error": unk_err,
        "error_names_field": (not unk_ok) and (UNKNOWN_FIELD in unk_err),
        "ignored_value_fate": fate,
        "known_keys": sorted(valid),
    }


def _valid_handoff() -> dict:
    """Keep the payload on disk: validate_handoff checks payload_path exists."""
    payload = HERE / "fixtures" / "payload"
    (payload / "skills" / "demo").mkdir(parents=True, exist_ok=True)
    (payload / "rules").mkdir(parents=True, exist_ok=True)
    (payload / "hooks").mkdir(parents=True, exist_ok=True)
    (payload / "plugin.json").write_text(
        json.dumps(_valid_plugin(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (payload / "skills" / "demo" / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    (payload / "rules" / "demo.md").write_text("# rule\n", encoding="utf-8")
    (payload / "hooks" / "demo.json").write_text("{}\n", encoding="utf-8")
    return build_handoff(payload)


def _valid_exec_policy() -> dict:
    return build_policy(
        policy_id="tst-0052-policy",
        allowed_executables=["/bin/true"],
        allowed_write_roots=["/tmp"],
        network_mode="deny",
    )


def _valid_hooks() -> dict:
    return {
        "version": 1,
        "hooks": {
            "SessionStart": [
                {"id": "session-canary", "hook": "hooks/session_canary.py"}
            ]
        },
    }


def measure_all() -> dict:
    plugin = _valid_plugin()
    handoff = _valid_handoff()
    policy = _valid_exec_policy()
    hooks = _valid_hooks()
    rows = [
        _measure_kind(
            kind="plugin.json",
            parser="plugin.payload.load_plugin_manifest",
            production=True,
            parse=parse_plugin_manifest,
            valid=plugin,
        ),
        _measure_kind(
            kind="install-handoff",
            parser="marketplace.handoff.validate_handoff",
            production=True,
            parse=parse_install_handoff,
            valid=handoff,
        ),
        _measure_kind(
            kind="exec-policy",
            parser="plugin.exec_policy.validate_policy",
            production=True,
            parse=parse_exec_policy,
            valid=policy,
        ),
        _measure_kind(
            kind="hooks.json",
            parser="hook_load.load_probe.load_config",
            production=True,
            parse=parse_hooks_json,
            valid=hooks,
        ),
        _measure_kind(
            kind="lenient-json.loads-control",
            parser="json.loads (negative control; not a production parser)",
            production=False,
            parse=parse_lenient_json,
            valid=plugin,
        ),
    ]
    production = [r for r in rows if r["production"]]
    control = [r for r in rows if not r["production"]][0]
    return {
        "unit_id": UNIT,
        "unknown_field": UNKNOWN_FIELD,
        "unknown_value": UNKNOWN_VALUE,
        "rows": rows,
        "production_count": len(production),
        "production_known_all_accepted": all(r["known_accepted"] for r in production),
        "production_unknown_all_rejected": all(r["unknown_rejected"] for r in production),
        "production_errors_all_name_field": all(r["error_names_field"] for r in production),
        "lenient_control_accepts_unknown": control["unknown_accepted"],
        "lenient_control_retains_value": UNKNOWN_VALUE
        in str(control["ignored_value_fate"]),
        "silently_accepting_production_parsers": [
            r["kind"] for r in production if r["unknown_accepted"]
        ],
    }
