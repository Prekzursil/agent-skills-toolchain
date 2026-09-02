#!/usr/bin/env python3
"""Load a plugin.json through the client's published strict contract.

Not a hand-written field list. The accepted keys and types come from the
pinned SchemaStore schema ($id = json.schemastore.org/claude-code-plugin-manifest.json),
which is the published Claude Code plugin manifest schema.

Runtime load is documented as lenient (unknown fields warn; the plugin still
loads). The STRICT parser is `claude plugin validate --strict`, which treats
those warnings as errors. This loader overlays additionalProperties=false on
the published schema — the same overlay --strict applies — and, when the
claude CLI is on PATH, also invokes it out of process.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = (
    "command-center/p2-wave/probes/TST-0033/fixtures/"
    "claude-code-plugin-manifest.schema.json"
)
SCHEMA_PATH = REPO / SCHEMA_REL
SCHEMA_ID = "https://json.schemastore.org/claude-code-plugin-manifest.json"
UNKNOWN_PROBE_KEY = "notARealField"


def _drop_repo_from_syspath() -> None:
    """Keep stdlib `platform` from being shadowed by repo/platform/."""
    repo = REPO.resolve()
    cleaned: list[str] = []
    for p in sys.path:
        if p in ("", "."):
            continue
        try:
            if Path(p).resolve() == repo:
                continue
        except OSError:
            pass
        cleaned.append(p)
    sys.path[:] = cleaned


_drop_repo_from_syspath()
from jsonschema import Draft7Validator  # noqa: E402


@dataclass
class LoadResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    parser: str = "schema-store-strict-overlay"
    named_unknown_fields: list[str] = field(default_factory=list)
    cli: dict[str, Any] | None = None
    parsed: Any = None


def official_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def strict_schema() -> dict[str, Any]:
    schema = official_schema()
    schema["additionalProperties"] = False
    return schema


def lenient_schema() -> dict[str, Any]:
    """Published schema as-is: additionalProperties omitted => extra keys allowed."""
    return official_schema()


def _validator(schema: dict[str, Any]) -> Draft7Validator:
    return Draft7Validator(schema)


def parse_json(raw: str) -> tuple[Any | None, str | None]:
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc}"


def _collect(validator: Draft7Validator, instance: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    named: list[str] = []
    for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        errors.append(err.message)
        if "additional properties" in err.message.lower():
            for k in err.instance.keys() if isinstance(err.instance, dict) else []:
                if k not in (err.schema.get("properties") or {}):
                    named.append(str(k))
    return errors, named


def load_obj(obj: Any, *, strict: bool = True) -> LoadResult:
    schema = strict_schema() if strict else lenient_schema()
    if not isinstance(obj, dict):
        return LoadResult(
            ok=False,
            errors=[f"manifest must be a JSON object, got {type(obj).__name__}"],
            parser="schema-store-strict-overlay" if strict else "schema-store-lenient",
        )
    errors, named = _collect(_validator(schema), obj)
    return LoadResult(
        ok=not errors,
        errors=errors,
        parser="schema-store-strict-overlay" if strict else "schema-store-lenient",
        named_unknown_fields=named,
        parsed=obj,
    )


def load_text(raw: str, *, strict: bool = True) -> LoadResult:
    obj, err = parse_json(raw)
    if err:
        return LoadResult(ok=False, errors=[err])
    return load_obj(obj, strict=strict)


def load_path(path: Path, *, strict: bool = True) -> LoadResult:
    if not path.is_file():
        return LoadResult(ok=False, errors=[f"absent: {path}"], parser="filesystem")
    return load_text(path.read_text(encoding="utf-8"), strict=strict)


def try_claude_cli(manifest_obj: dict[str, Any], *, strict: bool = True) -> dict[str, Any] | None:
    """Invoke the real client out of process when `claude` is on PATH."""
    exe = shutil.which("claude")
    if not exe:
        return None
    with tempfile.TemporaryDirectory(prefix="tst0033-plugin-") as tmp:
        root = Path(tmp)
        plug = root / ".claude-plugin"
        plug.mkdir()
        (plug / "plugin.json").write_text(
            json.dumps(manifest_obj, indent=2) + "\n", encoding="utf-8"
        )
        cmd = [exe, "plugin", "validate", str(root)]
        if strict:
            cmd.append("--strict")
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "invoked": True,
                "executable": exe,
                "command": cmd,
                "error": f"{type(exc).__name__}: {exc}",
            }
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return {
            "invoked": True,
            "executable": exe,
            "command": cmd,
            "exit_code": proc.returncode,
            "output": out[-4000:],
            "ok": proc.returncode == 0,
        }


def load_with_optional_cli(obj: Any, *, strict: bool = True) -> LoadResult:
    result = load_obj(obj, strict=strict)
    if isinstance(obj, dict):
        result.cli = try_claude_cli(obj, strict=strict)
    return result
