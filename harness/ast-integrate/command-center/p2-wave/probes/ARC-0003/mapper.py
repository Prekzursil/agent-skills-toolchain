"""A1 config-first expressibility mapper.

Two independently written implementations must agree. A capability is EXPRESSIBLE
when every field is finite static JSON with no runtime evaluator. The FIRST
inexpressible construct this mapper names is a stopping rule that requires
runtime evaluation of a predicate over prior rounds.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterator

BANNED_KEYS = frozenset(
    {
        "runtime_predicate",
        "executable_policy",
        "expression_tree",
        "sem_expr",
        "sem_expression",
        "eval",
        "predicate_over_prior_rounds",
        "js_expr",
        "python_expr",
        "when_expr",
        "typed_tree",
    }
)

RUNTIME_STOPPING_RULES = frozenset(
    {"runtime_predicate", "eval", "predicate_over_prior_rounds"}
)


def _is_runtime_stopping(node: dict[str, Any]) -> bool:
    rule = node.get("rule")
    pred = node.get("predicate")
    over = node.get("over")
    if rule in RUNTIME_STOPPING_RULES:
        return True
    if over == "prior_rounds" and isinstance(pred, str) and pred.strip():
        if any(
            tok in pred
            for tok in ("prior_rounds", "eval(", "score(", "threshold", "runtime")
        ):
            return True
    if node.get("runtime") is True and over == "prior_rounds":
        return True
    return False


def find_inexpressible_author(obj: Any, path: str = "$") -> str | None:
    """Author walk: insertion-order, depth-first. Returns first banned path."""
    if isinstance(obj, dict):
        if _is_runtime_stopping(obj) and (
            "stopping" in path.split(".") or path.endswith("stopping") or "predicate" in obj
        ):
            if path.endswith("stopping") or obj.get("rule") in RUNTIME_STOPPING_RULES:
                return f"{path}:runtime-stopping-predicate-over-prior-rounds"
        for key, val in obj.items():
            kl = str(key).lower()
            child = f"{path}.{key}"
            if kl in BANNED_KEYS:
                return f"{child}:banned-key"
            if kl == "stopping" and isinstance(val, dict) and _is_runtime_stopping(val):
                return f"{child}:runtime-stopping-predicate-over-prior-rounds"
            hit = find_inexpressible_author(val, child)
            if hit:
                return hit
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            hit = find_inexpressible_author(item, f"{path}[{i}]")
            if hit:
                return hit
    elif isinstance(obj, str):
        lowered = obj.lower()
        if lowered.startswith("eval(") or "predicate over prior rounds" in lowered:
            return f"{path}:runtime-eval-string"
    return None


def _iter_independent(obj: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    """Independent walk: reverse-sorted keys, then lists. Yields (path, node)."""
    yield path, obj
    if isinstance(obj, dict):
        for key in sorted(obj.keys(), reverse=True):
            yield from _iter_independent(obj[key], f"{path}.{key}")
    elif isinstance(obj, list):
        for i in range(len(obj) - 1, -1, -1):
            yield from _iter_independent(obj[i], f"{path}[{i}]")


def find_inexpressible_independent(obj: Any) -> str | None:
    """Second implementation: reverse-sorted walk + explicit marker set copy."""
    markers = set(BANNED_KEYS)
    for path, node in _iter_independent(obj):
        if isinstance(node, dict):
            keys_l = {str(k).lower() for k in node}
            banned = keys_l & markers
            if banned:
                return f"{path}.{sorted(banned)[0]}:banned-key"
            stopping = node.get("stopping")
            if isinstance(stopping, dict) and _is_runtime_stopping(stopping):
                return f"{path}.stopping:runtime-stopping-predicate-over-prior-rounds"
            if (
                path.endswith(".stopping") or path.endswith("stopping")
            ) and _is_runtime_stopping(node):
                return f"{path}:runtime-stopping-predicate-over-prior-rounds"
        elif isinstance(node, str):
            low = node.lower()
            if low.startswith("eval(") or "predicate over prior rounds" in low:
                return f"{path}:runtime-eval-string"
    return None


def canonical_bytes(doc: Any) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def digest(doc: Any) -> str:
    return hashlib.sha256(canonical_bytes(doc)).hexdigest()


def _strip_none(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_none(x) for x in obj]
    return obj


def transcribe_author(capability: dict[str, Any]) -> dict[str, Any]:
    body = capability.get("body", capability)
    hit = find_inexpressible_author(body)
    if hit:
        return {
            "verdict": "INEXPRESSIBLE",
            "first_construct": hit,
            "id": capability.get("id"),
            "kind": capability.get("kind"),
            "source_id": capability.get("source_id"),
            "mapper": "author-dfs-insertion-order",
        }
    form = {
        "form": "static-config/v1",
        "kind": capability.get("kind"),
        "id": capability.get("id"),
        "source_id": capability.get("source_id"),
        "config": _strip_none(body),
    }
    return {
        "verdict": "EXPRESSIBLE",
        "first_construct": None,
        "id": capability.get("id"),
        "kind": capability.get("kind"),
        "source_id": capability.get("source_id"),
        "mapper": "author-dfs-insertion-order",
        "config_form": form,
        "sha256": digest(form),
    }


def transcribe_independent(capability: dict[str, Any]) -> dict[str, Any]:
    body = capability.get("body", capability)
    # Re-parse through sorted JSON so key order cannot leak author insertion order.
    body2 = json.loads(json.dumps(body, sort_keys=True))
    hit = find_inexpressible_independent(body2)
    if hit:
        return {
            "verdict": "INEXPRESSIBLE",
            "first_construct": hit,
            "id": capability.get("id"),
            "kind": capability.get("kind"),
            "source_id": capability.get("source_id"),
            "mapper": "independent-reverse-sorted-walk",
        }
    form = {
        "form": "static-config/v1",
        "kind": capability.get("kind"),
        "id": capability.get("id"),
        "source_id": capability.get("source_id"),
        "config": _strip_none(body2),
    }
    return {
        "verdict": "EXPRESSIBLE",
        "first_construct": None,
        "id": capability.get("id"),
        "kind": capability.get("kind"),
        "source_id": capability.get("source_id"),
        "mapper": "independent-reverse-sorted-walk",
        "config_form": form,
        "sha256": digest(form),
    }


def same_verdict(a: dict[str, Any], b: dict[str, Any]) -> tuple[bool, str]:
    if a.get("verdict") != b.get("verdict"):
        return False, f"verdict {a.get('verdict')} != {b.get('verdict')}"
    if a.get("verdict") == "EXPRESSIBLE":
        if a.get("sha256") != b.get("sha256"):
            return False, f"sha256 {a.get('sha256')} != {b.get('sha256')}"
    else:
        # Both inexpressible: require the same construct class, not identical path
        # (walk order may name a nested path first).
        ka = str(a.get("first_construct") or "")
        kb = str(b.get("first_construct") or "")
        token = "runtime-stopping-predicate-over-prior-rounds"
        if token in ka and token in kb:
            return True, "inexpressible-same-construct-class"
        if ka.split(":")[-1] != kb.split(":")[-1]:
            return False, f"first_construct class {ka!r} vs {kb!r}"
    return True, "match"
