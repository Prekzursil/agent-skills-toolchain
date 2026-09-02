"""Per-unit output-schema gate at the vendor adapter boundary (IMP-0426).

The gate sits between the vendor CLI and any consumer of its typed payload:

* every vendor attempt is recorded (argv, exit code, stdout/stderr, the
  per-attempt classification and the validation errors it produced);
* the payload written through ``--output-last-message`` is validated against
  the unit's declared ``output_schema`` with a stdlib Draft-7 subset validator
  (:func:`schema_errors`), so a payload the schema rejects can never be
  mistaken for a delivered result;
* a schema-invalid payload is classified ``schema-invalid``, is never retried
  and is never handed to the consumer -- re-running the same prompt does not
  make a malformed payload conform, it only hides the vendor defect;
* the documented typed-schema x active-MCP interaction (the vendor refuses to
  apply a typed schema while MCP servers from user config are loaded, exit 3
  plus :data:`MCP_MARK` on stderr) is retried at most once, with
  ``--ignore-user-config``, and only when the caller allows it
  (``allow_mcp_retry``);
* the consumer runs only after the gate accepted the payload.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

CLASS_OK = "ok"
CLASS_SCHEMA_INVALID = "schema-invalid"
CLASS_MCP = "typed-schema-mcp-interaction"
CLASS_VENDOR_ERROR = "vendor-error"

#: Marker the vendor prints on stderr when a typed schema collides with an
#: MCP inventory loaded from user config.
MCP_MARK = "CLASSIFICATION:typed-schema-mcp-interaction"
#: Exit code the vendor uses for that interaction.
MCP_EXIT_CODE = 3
#: The only retry action the gate knows.
RETRY_IGNORE_USER_CONFIG = "ignore-user-config"
#: How many MCP-interaction retries a single dispatch may take.
MAX_MCP_RETRIES = 1

Consumer = Callable[[dict[str, Any]], None]


class SchemaGateError(ValueError):
    """The unit's declared output schema cannot be resolved or loaded."""


# --------------------------------------------------------------------------
# command-line guard
# --------------------------------------------------------------------------


def _cmdline_guard() -> Any:
    """Sibling `cmdline_guard` (tools/command-center/ is not an importable package)."""
    try:
        import cmdline_guard as cg  # type: ignore[import-not-found]

        return cg
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "cmdline_guard", Path(__file__).resolve().with_name("cmdline_guard.py")
        )
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def measure_cmdline(argv: list[str]) -> int:
    """Measure the assembled command line against the Windows CreateProcessW ceiling.

    The prompt already travels by --prompt-file, so only pathological paths can
    push argv over WINDOWS_CREATEPROCESS_CHAR_CEILING; refusing here turns a
    would-be WinError 206 from the vendor spawn into a clear guard error."""
    cg = _cmdline_guard()
    chars = int(cg.windows_cmdline_chars(argv))
    if cg.would_raise_206(chars):
        raise ValueError(
            f"assembled command line {chars}+NUL chars exceeds "
            f"WINDOWS_CREATEPROCESS_CHAR_CEILING={cg.WINDOWS_CREATEPROCESS_CHAR_CEILING}"
        )
    return chars


# --------------------------------------------------------------------------
# Draft-7 subset validator (stdlib only, deterministic error strings)
# --------------------------------------------------------------------------

_TYPE_CHECKS: dict[str, Callable[[Any], bool]] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _type_name(value: Any) -> str:
    for name, check in _TYPE_CHECKS.items():
        if name == "number":
            continue
        if check(value):
            return name
    if _TYPE_CHECKS["number"](value):
        return "number"
    return type(value).__name__


def _resolve_ref(root: Any, ref: str) -> Any:
    """Resolve a document-local JSON pointer (``#/definitions/x``)."""
    if not ref.startswith("#"):
        raise SchemaGateError(f"unsupported non-local $ref {ref!r}")
    node = root
    for raw in ref[1:].split("/"):
        if raw == "":
            continue
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            node = node[int(token)]
        elif isinstance(node, dict):
            if token not in node:
                raise SchemaGateError(f"unresolvable $ref {ref!r}")
            node = node[token]
        else:
            raise SchemaGateError(f"unresolvable $ref {ref!r}")
    return node


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def schema_errors(
    payload: Any, schema: Any, path: str = "$", root: Any = None
) -> list[str]:
    """Validate ``payload`` against a Draft-7 subset ``schema``.

    Returns a deterministic, sorted-where-order-is-arbitrary list of error
    strings; an empty list means the payload conforms. Supported keywords:
    type, const, enum, required, properties, additionalProperties,
    minProperties, maxProperties, minLength, maxLength, pattern, minimum,
    maximum, exclusiveMinimum, exclusiveMaximum, multipleOf, items, minItems,
    maxItems, uniqueItems, allOf, anyOf, oneOf, not and document-local $ref.
    """
    if root is None:
        root = schema
    if schema is True:
        return []
    if schema is False:
        return [f"{path}: schema forbids any value"]
    if not isinstance(schema, dict):
        raise SchemaGateError(f"{path}: schema node must be an object or boolean")
    if "$ref" in schema:
        return schema_errors(payload, _resolve_ref(root, str(schema["$ref"])), path, root)

    errors: list[str] = []
    typ = schema.get("type")
    if typ is not None:
        types = [str(t) for t in (typ if isinstance(typ, list) else [typ])]
        if not any(_TYPE_CHECKS.get(t, lambda _v: False)(payload) for t in types):
            errors.append(f"{path}: expected {'/'.join(types)}, got {_type_name(payload)}")
            return errors
    if "const" in schema and payload != schema["const"]:
        errors.append(f"{path}: expected const {_canon(schema['const'])}")
    if "enum" in schema and payload not in list(schema["enum"]):
        errors.append(f"{path}: {_canon(payload)} is not one of {_canon(schema['enum'])}")

    if isinstance(payload, str):
        if "minLength" in schema and len(payload) < int(schema["minLength"]):
            errors.append(f"{path}: string shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(payload) > int(schema["maxLength"]):
            errors.append(f"{path}: string longer than maxLength {schema['maxLength']}")
        if "pattern" in schema and re.search(str(schema["pattern"]), payload) is None:
            errors.append(f"{path}: {payload!r} does not match pattern {schema['pattern']!r}")

    if _is_number(payload):
        if "minimum" in schema and payload < schema["minimum"]:
            errors.append(f"{path}: {payload} is below minimum {schema['minimum']}")
        if "maximum" in schema and payload > schema["maximum"]:
            errors.append(f"{path}: {payload} is above maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and payload <= schema["exclusiveMinimum"]:
            errors.append(
                f"{path}: {payload} is not above exclusiveMinimum {schema['exclusiveMinimum']}"
            )
        if "exclusiveMaximum" in schema and payload >= schema["exclusiveMaximum"]:
            errors.append(
                f"{path}: {payload} is not below exclusiveMaximum {schema['exclusiveMaximum']}"
            )
        if "multipleOf" in schema:
            step = schema["multipleOf"]
            if step and abs(round(payload / step) * step - payload) > 1e-9:
                errors.append(f"{path}: {payload} is not a multiple of {step}")

    if isinstance(payload, list):
        if "minItems" in schema and len(payload) < int(schema["minItems"]):
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        if "maxItems" in schema and len(payload) > int(schema["maxItems"]):
            errors.append(f"{path}: more than maxItems {schema['maxItems']}")
        if schema.get("uniqueItems"):
            seen = {_canon(item) for item in payload}
            if len(seen) != len(payload):
                errors.append(f"{path}: items are not unique")
        items = schema.get("items")
        if isinstance(items, list):
            for idx, (item, sub) in enumerate(zip(payload, items)):
                errors.extend(schema_errors(item, sub, f"{path}[{idx}]", root))
            extra = schema.get("additionalItems")
            if extra is not None and len(payload) > len(items):
                for idx in range(len(items), len(payload)):
                    errors.extend(schema_errors(payload[idx], extra, f"{path}[{idx}]", root))
        elif items is not None:
            for idx, item in enumerate(payload):
                errors.extend(schema_errors(item, items, f"{path}[{idx}]", root))

    if isinstance(payload, dict):
        for key in schema.get("required") or []:
            if str(key) not in payload:
                errors.append(f"{path}: missing required property {str(key)!r}")
        if "minProperties" in schema and len(payload) < int(schema["minProperties"]):
            errors.append(f"{path}: fewer than minProperties {schema['minProperties']}")
        if "maxProperties" in schema and len(payload) > int(schema["maxProperties"]):
            errors.append(f"{path}: more than maxProperties {schema['maxProperties']}")
        props = schema.get("properties") or {}
        for key in sorted(payload):
            if key in props:
                errors.extend(schema_errors(payload[key], props[key], f"{path}.{key}", root))
        pattern_props = schema.get("patternProperties") or {}
        matched_by_pattern: set[str] = set()
        for pat, sub in pattern_props.items():
            for key in sorted(payload):
                if re.search(str(pat), key) is not None:
                    matched_by_pattern.add(key)
                    errors.extend(schema_errors(payload[key], sub, f"{path}.{key}", root))
        extras = sorted(k for k in payload if k not in props and k not in matched_by_pattern)
        additional = schema.get("additionalProperties", True)
        if extras and additional is False:
            errors.append(f"{path}: additional properties not allowed: {', '.join(extras)}")
        elif extras and isinstance(additional, dict):
            for key in extras:
                errors.extend(schema_errors(payload[key], additional, f"{path}.{key}", root))

    for sub in schema.get("allOf") or []:
        errors.extend(schema_errors(payload, sub, path, root))
    if "anyOf" in schema:
        branches = [schema_errors(payload, sub, path, root) for sub in schema["anyOf"]]
        if not any(not b for b in branches):
            errors.append(f"{path}: does not satisfy any branch of anyOf")
    if "oneOf" in schema:
        branches = [schema_errors(payload, sub, path, root) for sub in schema["oneOf"]]
        passing = sum(1 for b in branches if not b)
        if passing != 1:
            errors.append(f"{path}: satisfies {passing} branches of oneOf (need exactly 1)")
    if "not" in schema and not schema_errors(payload, schema["not"], path, root):
        errors.append(f"{path}: must not match the 'not' schema")
    return errors


def resolve_schema_path(repo: Path, unit: dict[str, Any]) -> Path:
    """Return the on-disk path of the unit's declared ``output_schema``."""
    declared = str(unit.get("output_schema") or "").strip()
    if not declared:
        raise SchemaGateError(f"unit {unit.get('id')!r} declares no output_schema")
    path = Path(declared)
    if not path.is_absolute():
        path = Path(repo) / path
    if not path.is_file():
        raise SchemaGateError(f"output_schema {declared!r} is not a file under {repo}")
    return path


def load_schema(path: Path) -> dict[str, Any]:
    """Load a JSON schema document, refusing anything that is not an object."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaGateError(f"cannot load schema {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise SchemaGateError(f"schema {path} must be a JSON object")
    return doc


def validate_payload(payload: Any, schema: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return ``(valid, errors)`` for ``payload`` under ``schema``."""
    errors = schema_errors(payload, schema)
    return (not errors, errors)


def atomic_write_json(path: Path, doc: Any, *, indent: int = 2) -> int:
    """Serialise ``doc`` to ``path`` via a same-directory temp file + ``os.replace``.

    A gated receipt must never be observable half-written, so the bytes land
    in ``<name>.tmp-<pid>`` first and are renamed into place only once fully
    flushed.  Returns the number of bytes written.
    """
    import os

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=indent, sort_keys=True, ensure_ascii=False) + "\n"
    data = text.encode("utf-8")
    tmp = target.with_name(f"{target.name}.tmp-{os.getpid()}")
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()
    return len(data)


# --------------------------------------------------------------------------
# retry policy
# --------------------------------------------------------------------------


def decide_retry(classification: str, retries_used: int, ignore_user_config: bool) -> str | None:
    """Retry policy for one classified attempt.

    ``schema-invalid`` is never retried (nor is a plain vendor error): the
    payload is a vendor defect that repetition would only mask.  The
    typed-schema x active-MCP interaction earns exactly one retry with
    ``--ignore-user-config`` -- and none at all when the failing attempt was
    already running with that flag, because the inventory was then not the
    cause.  Returns the action name or ``None`` for "do not retry".
    """
    if (
        classification == CLASS_MCP
        and int(retries_used) < MAX_MCP_RETRIES
        and not bool(ignore_user_config)
    ):
        return RETRY_IGNORE_USER_CONFIG
    return None


# --------------------------------------------------------------------------
# vendor invocation + per-attempt classification
# --------------------------------------------------------------------------


def _run_vendor(
    vendor_cli: Path,
    *,
    workdir: Path,
    unit: dict[str, Any],
    repo: Path,
    schema_path: Path,
    mcp_inventory: Path | None,
    ignore_user_config: bool,
    emit_invalid: bool,
) -> dict[str, Any]:
    """Run one vendor attempt and return its raw record (not yet classified)."""
    workdir.mkdir(parents=True, exist_ok=True)
    prompt = workdir / "prompt.txt"
    prompt.write_text("typed output please\n", encoding="utf-8")
    out = workdir / "last.json"
    argv = [
        sys.executable,
        "-B",
        str(vendor_cli),
        "--prompt-file",
        str(prompt),
        "--output-last-message",
        str(out),
        "--output-schema",
        str(schema_path),
        "--unit-id",
        str(unit.get("id") or "FIX"),
    ]
    if mcp_inventory is not None:
        argv.extend(["--mcp-inventory", str(mcp_inventory)])
    if ignore_user_config:
        argv.append("--ignore-user-config")
    if emit_invalid:
        argv.append("--emit-invalid")
    cmdline_chars = measure_cmdline(argv)
    proc = subprocess.run(argv, cwd=str(repo), capture_output=True, text=True)
    return {
        "argv": argv,
        "cmdline_chars": cmdline_chars,
        "exit_code": proc.returncode,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "output_path": str(out),
        "ignore_user_config": bool(ignore_user_config),
        "mcp_inventory_passed": mcp_inventory is not None,
        "emit_invalid": bool(emit_invalid),
    }


def classify_attempt(attempt: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Classify a raw attempt record in place and return it.

    Adds ``classification``, ``errors``, ``payload`` and ``output_bytes``.
    Order of precedence: MCP interaction (exit 3 or the marker on stderr),
    other non-zero exit (``vendor-error``), missing/unparseable/non-conforming
    payload (``schema-invalid``), conforming payload (``ok``).
    """
    stderr = str(attempt.get("stderr") or "")
    rc = int(attempt.get("exit_code") or 0)
    out_path = Path(str(attempt.get("output_path") or ""))
    payload: Any = None
    errors: list[str] = []
    output_bytes = out_path.stat().st_size if out_path.is_file() else 0

    if rc == MCP_EXIT_CODE or MCP_MARK in stderr:
        classification = CLASS_MCP
        errors.append("vendor refused typed schema while MCP inventory is loaded")
    elif rc != 0:
        classification = CLASS_VENDOR_ERROR
        errors.append(f"vendor exited {rc} without a typed payload")
    elif not out_path.is_file():
        classification = CLASS_SCHEMA_INVALID
        errors.append("vendor exited 0 but wrote no --output-last-message payload")
    else:
        try:
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            classification = CLASS_SCHEMA_INVALID
            errors.append(f"payload is not JSON: {exc.__class__.__name__}")
        else:
            valid, errors = validate_payload(payload, schema)
            classification = CLASS_OK if valid else CLASS_SCHEMA_INVALID
            if not valid:
                payload = None
    attempt["classification"] = classification
    attempt["errors"] = errors
    attempt["payload"] = payload
    attempt["output_bytes"] = output_bytes
    return attempt


# --------------------------------------------------------------------------
# dispatch
# --------------------------------------------------------------------------


def dispatch(
    unit: dict[str, Any],
    *,
    repo: Path,
    workdir: Path,
    vendor_cli: Path,
    mcp_inventory: Path | None = None,
    ignore_user_config: bool = False,
    emit_invalid: bool = False,
    allow_mcp_retry: bool = False,
    consumer: Consumer | None = None,
) -> dict[str, Any]:
    """Run the vendor for ``unit`` behind the output-schema gate.

    The consumer is invoked at most once, only with a payload the declared
    schema accepted.  ``allow_mcp_retry`` is the caller's permission for the
    single ``--ignore-user-config`` retry that :func:`decide_retry` grants on
    the MCP interaction; without it the interaction terminates the dispatch.
    """
    repo = Path(repo)
    schema_path = resolve_schema_path(repo, unit)
    schema = load_schema(schema_path)
    try:
        schema_rel = str(schema_path.resolve().relative_to(repo.resolve()))
    except ValueError:
        schema_rel = str(schema_path)

    attempts: list[dict[str, Any]] = []
    retries_used = 0
    ignore = bool(ignore_user_config)
    consumer_invoked = False
    payload: Any = None
    classification = CLASS_VENDOR_ERROR
    errors: list[str] = []
    while True:
        att = _run_vendor(
            Path(vendor_cli),
            workdir=Path(workdir) / f"attempt-{len(attempts)}",
            unit=unit,
            repo=repo,
            schema_path=schema_path,
            mcp_inventory=mcp_inventory,
            ignore_user_config=ignore,
            emit_invalid=emit_invalid,
        )
        classify_attempt(att, schema)
        attempts.append(att)
        classification = att["classification"]
        errors = list(att["errors"])
        policy = decide_retry(classification, retries_used, att["ignore_user_config"])
        action = policy if allow_mcp_retry else None
        att["retry_policy"] = policy
        att["retry_action"] = action
        if action == RETRY_IGNORE_USER_CONFIG:
            retries_used += 1
            ignore = True
            continue
        if classification == CLASS_OK:
            payload = att["payload"]
            if consumer is not None:
                consumer(payload)
                consumer_invoked = True
        break

    ok = classification == CLASS_OK
    return {
        "unit_id": str(unit.get("id") or ""),
        "terminal_kind": "SUCCESS" if ok else "FAILED",
        "classification": classification,
        "schema_gate": {
            "classification": classification,
            "valid": ok,
            "enforced": True,
            "schema_path": schema_rel,
            "retries_used": retries_used,
            "max_mcp_retries": MAX_MCP_RETRIES if allow_mcp_retry else 0,
            "consumer_invoked": consumer_invoked,
            "errors": errors,
        },
        "attempts": attempts,
        "payload": payload,
    }


__all__ = [
    "atomic_write_json",
    "CLASS_MCP",
    "CLASS_OK",
    "CLASS_SCHEMA_INVALID",
    "CLASS_VENDOR_ERROR",
    "MAX_MCP_RETRIES",
    "MCP_EXIT_CODE",
    "MCP_MARK",
    "RETRY_IGNORE_USER_CONFIG",
    "SchemaGateError",
    "classify_attempt",
    "decide_retry",
    "dispatch",
    "load_schema",
    "measure_cmdline",
    "resolve_schema_path",
    "schema_errors",
    "validate_payload",
]
