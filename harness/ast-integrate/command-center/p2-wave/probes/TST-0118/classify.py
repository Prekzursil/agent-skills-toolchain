"""Three-layer classification: JSON lexer, grammar syntax, semantic.

A grammar-derived document must reach SEMANTIC. Byte-level noise dies in
LEXER or SYNTAX; a low semantic reach-rate means the campaign is testing
the lexer, not the DSL.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
GRAMMAR_PATH = HERE / "grammar.json"
_GRAMMAR: dict[str, Any] | None = None
IDENT_RE = re.compile(r"^[a-z][a-z0-9-]{0,23}$")

LAYER_LEXER = "LEXER"
LAYER_SYNTAX = "SYNTAX"
LAYER_SEMANTIC = "SEMANTIC"


def load_grammar() -> dict[str, Any]:
    global _GRAMMAR
    if _GRAMMAR is None:
        _GRAMMAR = json.loads(GRAMMAR_PATH.read_text(encoding="utf-8"))
    return _GRAMMAR


def grammar_sha256() -> str:
    import hashlib

    raw = GRAMMAR_PATH.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _match(value: Any, spec: Any, g: dict[str, Any], path: str, errs: list[str]) -> None:
    productions = g["productions"]
    if isinstance(spec, str):
        if spec == "Ident":
            if not isinstance(value, str) or not IDENT_RE.match(value):
                errs.append(f"{path}: not Ident")
            return
        prod = productions.get(spec)
        if prod is None:
            errs.append(f"{path}: unknown symbol {spec}")
            return
        _match(value, prod, g, path, errs)
        return

    if not isinstance(spec, dict):
        errs.append(f"{path}: malformed production")
        return

    kind = spec.get("type")
    if kind == "token":
        pat = re.compile(str(spec.get("pattern") or ""))
        if not isinstance(value, str) or not pat.match(value):
            errs.append(f"{path}: token mismatch")
        return

    if kind == "oneOf":
        saved = list(errs)
        for opt in spec.get("options") or []:
            trial: list[str] = []
            _match(value, opt, g, path, trial)
            if not trial:
                return
        errs.extend(saved)
        errs.append(f"{path}: no oneOf alternative matched")
        return

    if kind == "array":
        if not isinstance(value, list):
            errs.append(f"{path}: expected array")
            return
        mn = spec.get("minItems")
        mx = spec.get("maxItems")
        if mn is not None and len(value) < int(mn):
            errs.append(f"{path}: array shorter than {mn}")
        if mx is not None and len(value) > int(mx):
            errs.append(f"{path}: array longer than {mx}")
        items = spec.get("items")
        if items is not None:
            for i, item in enumerate(value):
                _match(item, items, g, f"{path}/{i}", errs)
        return

    if kind == "object":
        if not isinstance(value, dict):
            errs.append(f"{path}: expected object")
            return
        props = spec.get("properties") or {}
        required = spec.get("required") or []
        for key in required:
            if key not in value:
                errs.append(f"{path}: missing {key}")
        if spec.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errs.append(f"{path}: unexpected {key}")
        for key, sub in props.items():
            if key in value:
                _match(value[key], sub, g, f"{path}/{key}", errs)
        return

    if "const" in spec:
        if value != spec["const"]:
            errs.append(f"{path}: expected const {spec['const']!r}")
        return

    if "enum" in spec:
        if value not in spec["enum"]:
            errs.append(f"{path}: {value!r} not in enum")
        return

    if spec.get("type") == "string":
        if not isinstance(value, str):
            errs.append(f"{path}: expected string")
        elif spec.get("minLength") and len(value) < int(spec["minLength"]):
            errs.append(f"{path}: string too short")
        return

    if spec.get("type") == "integer":
        if type(value) is not int:
            errs.append(f"{path}: expected integer")
        elif spec.get("minimum") is not None and value < int(spec["minimum"]):
            errs.append(f"{path}: integer below minimum")
        return

    errs.append(f"{path}: unhandled spec {kind}")


def grammar_errors(value: Any) -> list[str]:
    g = load_grammar()
    errs: list[str] = []
    if not isinstance(value, dict):
        return ["/: not an object"]
    kind = value.get("kind")
    start = "Library" if kind == "workflow-library" else "Manifest" if kind == "component-manifest" else None
    if start is None:
        return ["/: kind is neither workflow-library nor component-manifest"]
    _match(value, start, g, "", errs)
    return errs


def classify_text(text: str) -> dict[str, Any]:
    """Return layer + parse payload. Never raises."""
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError) as exc:
        return {
            "layer": LAYER_LEXER,
            "value": None,
            "syntax_errors": [f"json:{type(exc).__name__}"],
        }
    errs = grammar_errors(value)
    if errs:
        return {"layer": LAYER_SYNTAX, "value": value, "syntax_errors": errs[:12]}
    return {"layer": LAYER_SEMANTIC, "value": value, "syntax_errors": []}


def classify_bytes(data: bytes) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "layer": LAYER_LEXER,
            "value": None,
            "syntax_errors": ["utf8"],
        }
    return classify_text(text)
