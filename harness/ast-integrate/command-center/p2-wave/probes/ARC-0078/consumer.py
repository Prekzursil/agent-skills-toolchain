"""Consumer call site: validate a plugin manifest against ARC-0078.

A real call site, not a comment. Loads the frozen contract from disk,
validates plugin.json, and when hooks is a relative path also validates
the referenced hooks file. Host-aware Windows checks reject a missing
interpreter and a bare .sh token.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from windows_model import windows_bare_invocation

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTRACT_PATH = REPO / "command-center" / "phase4" / "contracts" / "ARC-0078.json"


@dataclass
class Issue:
    code: str
    path: str
    message: str


@dataclass
class Result:
    ok: bool
    issues: list[Issue] = field(default_factory=list)
    plugin_rel: str = ""
    hooks_rel: str | None = None
    host_os: str = "linux"

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plugin": self.plugin_rel,
            "hooks": self.hooks_rel,
            "host_os": self.host_os,
            "issues": [i.__dict__ for i in self.issues],
        }


def load_contract() -> dict:
    if not CONTRACT_PATH.is_file():
        raise FileNotFoundError(CONTRACT_PATH)
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def _hooks_schema(contract: dict) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": "#/$defs/hooks_file",
        "$defs": contract["$defs"],
    }


def _schema_issues(validator: Draft202012Validator, instance: Any, prefix: str) -> list[Issue]:
    out: list[Issue] = []
    for err in validator.iter_errors(instance):
        loc = ".".join(str(p) for p in err.absolute_path) or "<root>"
        kind = str(err.validator or "")
        msg = err.message or ""
        code = "schema"
        if kind == "required" and "interpreter" in msg:
            code = "interpreter-required"
        elif kind == "minItems" and loc.endswith("hooks"):
            code = "zero-hooks-empty"
        elif kind in {
            "additionalProperties",
            "unevaluatedProperties",
            "propertyNames",
            "not",
        } and (
            "$schema" in msg
            or (
                isinstance(instance, dict)
                and "$schema" in instance
                and loc == "<root>"
            )
        ):
            code = "zero-hooks-unknown-field"
        out.append(Issue(code=code, path=f"{prefix}:{loc}", message=err.message))
    return out


def _collect_script_tokens(plugin: dict, hooks_doc: dict | None) -> list[tuple[str, dict]]:
    rows: list[tuple[str, dict]] = []
    for i, cmd in enumerate(plugin.get("commands") or []):
        if isinstance(cmd, dict):
            rows.append((f"commands[{i}]", cmd))
    if isinstance(hooks_doc, dict):
        for i, hook in enumerate(hooks_doc.get("hooks") or []):
            if isinstance(hook, dict):
                rows.append((f"hooks[{i}]", hook))
    inline = plugin.get("hooks")
    if isinstance(inline, dict):
        for i, hook in enumerate(inline.get("hooks") or []):
            if isinstance(hook, dict):
                rows.append((f"plugin.hooks[{i}]", hook))
    return rows


def validate_plugin(
    plugin_path: Path,
    *,
    host_os: str = "linux",
    contract: dict | None = None,
) -> Result:
    """Validate plugin.json (+ referenced hooks file) against ARC-0078."""
    plugin_path = plugin_path.resolve()
    result = Result(ok=True, plugin_rel=_rel(plugin_path), host_os=host_os)
    schema = contract if contract is not None else load_contract()
    plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
    plugin_v = Draft202012Validator(schema)
    result.issues.extend(_schema_issues(plugin_v, plugin, "plugin"))

    hooks_doc: dict | None = None
    hooks_field = plugin.get("hooks")
    if isinstance(hooks_field, str):
        hooks_path = (plugin_path.parent / hooks_field).resolve()
        result.hooks_rel = _rel(hooks_path)
        if not hooks_path.is_file():
            result.issues.append(
                Issue(
                    code="hooks-missing",
                    path=f"plugin:hooks",
                    message=f"hooks path not found: {hooks_path}",
                )
            )
        else:
            hooks_doc = json.loads(hooks_path.read_text(encoding="utf-8"))
            if isinstance(hooks_doc, dict) and "$schema" in hooks_doc:
                result.issues.append(
                    Issue(
                        code="zero-hooks-unknown-field",
                        path="hooks:$schema",
                        message=(
                            "hooks file carries $schema; Codex HooksFile "
                            "deny_unknown_fields unloads every hook while the "
                            "plugin still appears installed"
                        ),
                    )
                )
            hooks_v = Draft202012Validator(_hooks_schema(schema))
            result.issues.extend(_schema_issues(hooks_v, hooks_doc, "hooks"))
    elif isinstance(hooks_field, dict):
        hooks_doc = hooks_field
        if "$schema" in hooks_field:
            result.issues.append(
                Issue(
                    code="zero-hooks-unknown-field",
                    path="plugin:hooks.$schema",
                    message="inline hooks carry $schema (zero-hooks shape)",
                )
            )

    for loc, entry in _collect_script_tokens(plugin, hooks_doc):
        interp = entry.get("interpreter")
        script = entry.get("script")
        if host_os == "windows" and not interp:
            result.issues.append(
                Issue(
                    code="interpreter-required",
                    path=loc,
                    message=(
                        "script entry with no interpreter fails validation "
                        "on Windows (no shebang, no PATHEXT for .sh)"
                    ),
                )
            )
        if host_os == "windows" and isinstance(script, str) and script.lower().endswith(".sh") and not interp:
            win = windows_bare_invocation(script)
            result.issues.append(
                Issue(
                    code="bare-sh-on-windows",
                    path=loc,
                    message=win["stderr"].splitlines()[0],
                )
            )

    result.ok = not result.issues
    return result


def validate_hooks_file(hooks_path: Path, contract: dict | None = None) -> Result:
    schema = contract if contract is not None else load_contract()
    hooks_path = hooks_path.resolve()
    result = Result(ok=True, hooks_rel=_rel(hooks_path), plugin_rel="")
    doc = json.loads(hooks_path.read_text(encoding="utf-8"))
    if isinstance(doc, dict) and "$schema" in doc:
        result.issues.append(
            Issue(
                code="zero-hooks-unknown-field",
                path="hooks:$schema",
                message="recorded zero-hooks key $schema is present",
            )
        )
    hooks_v = Draft202012Validator(_hooks_schema(schema))
    result.issues.extend(_schema_issues(hooks_v, doc, "hooks"))
    result.ok = not result.issues
    return result
