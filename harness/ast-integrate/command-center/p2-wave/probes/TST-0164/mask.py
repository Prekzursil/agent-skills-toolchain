"""Up-front non-determinism mask for TST-0164.

The field list is a frozen literal. It is NOT derived from a byte-diff of two
runs. Applying a blanket mask, masking semantic payload, or covering more than
the ceiling is a typed refusal (mask-coverage-ceiling).
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Iterable, Sequence

# Declared BEFORE any run. Probe 2 AST-checks this is a tuple of string literals.
DECLARED_NONDETERMINISTIC_FIELDS: tuple[str, ...] = (
    "meta.timestamp_ns",
    "meta.pid",
    "timestamp_ns",
)

UNMASKABLE_SEGMENTS: tuple[str, ...] = (
    "payload",
    "digest",
    "records",
    "downstream",
    "stage",
    "corpus",
    "tag",
    "sha256",
    "names",
)

BLANKET_TOKENS: frozenset[str] = frozenset({"*", "**", "$", "$.*", "$..", "#", "all"})
MASK_PLACEHOLDER = "<DECLARED-ND>"
MAX_MASKED_FIELD_COUNT = 8
MAX_MASKED_LEAF_FRACTION = 0.25

HERE = Path(__file__).resolve().parent


class MaskCoverageError(ValueError):
    """Mask is a blanket, covers semantic payload, or exceeds the ceiling."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(detail or reason)


def _segments(path: str) -> list[str]:
    return [p for p in path.replace("[", ".").replace("]", "").split(".") if p]


def _is_unmaskable(path: str) -> bool:
    segs = {s.lower() for s in _segments(path)}
    return bool(segs & {u.lower() for u in UNMASKABLE_SEGMENTS})


def leaf_paths(obj: Any, prefix: str = "") -> list[str]:
    if isinstance(obj, dict):
        out: list[str] = []
        for k in sorted(obj):
            p = f"{prefix}.{k}" if prefix else str(k)
            out.extend(leaf_paths(obj[k], p))
        return out
    if isinstance(obj, list):
        out = []
        for i, item in enumerate(obj):
            p = f"{prefix}[{i}]"
            out.extend(leaf_paths(item, p))
        return out
    return [prefix or "$"]


def check_mask_coverage(
    fields: Sequence[str],
    *,
    sample: Any | None = None,
) -> None:
    """Refuse blanket / semantic / over-wide masks. Called before any apply."""
    named = [str(f).strip() for f in fields if str(f).strip()]
    if not named:
        raise MaskCoverageError("empty-mask", "mask must name at least one field")
    for f in named:
        token = f.strip().lower()
        if token in BLANKET_TOKENS or token.endswith(".*") or token.endswith(".**"):
            raise MaskCoverageError(
                "mask-coverage-ceiling",
                f"blanket token {f!r} rejected by mask-coverage ceiling",
            )
        if _is_unmaskable(f):
            raise MaskCoverageError(
                "unmaskable-semantic-field",
                f"semantic field {f!r} is not maskable",
            )
    if len(named) > MAX_MASKED_FIELD_COUNT:
        raise MaskCoverageError(
            "mask-coverage-ceiling",
            f"{len(named)} fields exceeds MAX_MASKED_FIELD_COUNT={MAX_MASKED_FIELD_COUNT}",
        )
    if sample is not None:
        leaves = leaf_paths(sample)
        if leaves:
            frac = len(named) / max(len(leaves), 1)
            if frac > MAX_MASKED_LEAF_FRACTION and len(named) >= len(leaves):
                raise MaskCoverageError(
                    "mask-coverage-ceiling",
                    f"masked {len(named)}/{len(leaves)} leaves exceeds "
                    f"MAX_MASKED_LEAF_FRACTION={MAX_MASKED_LEAF_FRACTION}",
                )


def mask_everything_rejected(sample: Any) -> dict[str, Any]:
    """Negative control: attempting to mask every leaf must be refused."""
    leaves = leaf_paths(sample)
    try:
        check_mask_coverage(leaves, sample=sample)
        return {
            "rejected": False,
            "reason": None,
            "leaf_count": len(leaves),
        }
    except MaskCoverageError as exc:
        return {
            "rejected": True,
            "reason": exc.reason,
            "detail": str(exc),
            "leaf_count": len(leaves),
            "attempted": len(leaves),
            "ceiling_fields": MAX_MASKED_FIELD_COUNT,
            "ceiling_fraction": MAX_MASKED_LEAF_FRACTION,
        }


def _under_meta(path_stack: tuple[str, ...], fields: Sequence[str], key: str) -> bool:
    if path_stack[-1:] == ("meta",) or (path_stack and path_stack[-1] == "meta"):
        target = f"meta.{key}"
        return target in fields
    return False


def apply_mask(obj: Any, fields: Sequence[str], path_stack: tuple[str, ...] = ()) -> Any:
    """Replace declared keys with MASK_PLACEHOLDER. Does not inspect diffs."""
    check_mask_coverage(fields)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            stack = path_stack + (str(k),)
            dotted = ".".join(stack)
            if dotted in fields or (
                str(k) == "timestamp_ns" and "timestamp_ns" in fields
            ):
                out[k] = MASK_PLACEHOLDER
            elif _under_meta(path_stack, fields, str(k)):
                out[k] = MASK_PLACEHOLDER
            else:
                out[k] = apply_mask(v, fields, stack)
        return out
    if isinstance(obj, list):
        return [apply_mask(x, fields, path_stack) for x in obj]
    return obj


def apply_declared_mask(obj: Any) -> Any:
    return apply_mask(obj, DECLARED_NONDETERMINISTIC_FIELDS)


def declared_fields_are_literals(source: str | None = None) -> bool:
    """True iff DECLARED_NONDETERMINISTIC_FIELDS is a tuple/list of str constants."""
    text = source if source is not None else (HERE / "mask.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in tree.body:
        targets: Iterable[ast.AST]
        value: ast.AST | None = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id != "DECLARED_NONDETERMINISTIC_FIELDS":
                continue
            value = node.value
        elif isinstance(node, ast.Assign):
            names = [
                t.id for t in node.targets if isinstance(t, ast.Name)
            ]
            if "DECLARED_NONDETERMINISTIC_FIELDS" not in names:
                continue
            value = node.value
        else:
            continue
        if value is None:
            return False
        if not isinstance(value, (ast.Tuple, ast.List)):
            return False
        if not value.elts:
            return False
        for elt in value.elts:
            if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
                return False
        return True
    return False


def mask_module_imports_diff_walker(source: str | None = None) -> bool:
    """True when mask.py imports a compare/diff helper — that would be discovery."""
    text = source if source is not None else (HERE / "mask.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.split(".")[-1] in {"compare", "diffs", "walk_diffs"}:
                return True
            for alias in node.names:
                if alias.name in {"walk_diffs", "discover_mask", "infer_mask"}:
                    return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[-1] in {"compare", "walk_diffs"}:
                    return True
    return False
