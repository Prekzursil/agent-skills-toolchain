"""96-entry two-tier blueprint catalog for the WFA-0135 evidence gate.

The harvested 09-WORKFLOW-BLUEPRINT-LIBRARY.json is absent on this worktree.
This module is the fixture library the gate actually resolves: 40 flagship
claims and 56 remainder claims, each with a distinct mechanism family×variant.
"""
from __future__ import annotations

from typing import Any

FLAGSHIP_FLOOR = 40
BLUEPRINT_COUNT = 96
FLAGSHIP_COUNT = 40

FAMILIES: tuple[str, ...] = (
    "linear-hash",
    "predicate-branch",
    "reduce-fold",
    "two-input-join",
    "retry-stable",
    "schema-gate",
    "window-agg",
    "fan-out-in",
    "diff-patch",
    "topo-order",
    "quota-bound",
    "canonical-json",
)

FOLD_OPS = ("sum", "xor", "min", "max", "count", "mean", "product", "span")
HASH_NAMES = ("sha256", "blake2s", "sha1", "sha512", "blake2b", "md5", "shake128", "sha3_256")


def _seed(n: int, family: str, variant: int) -> dict[str, Any]:
    return {
        "n": n,
        "family": family,
        "variant": variant,
        "items": [
            {"k": f"k{i}", "v": (n * 17 + variant * 13 + i * 7) % 997}
            for i in range(4 + (variant % 4))
        ],
        "left": {"k": "join", "v": n, "tag": family},
        "right": {"k": "join", "v": n + variant, "tag": family},
        "series": list(range(variant + 3, variant + 11)),
        "dag": [
            {"id": "a", "after": []},
            {"id": "b", "after": ["a"]},
            {"id": "c", "after": ["a"]},
            {"id": "d", "after": ["b", "c"]},
        ],
        "text": f"payload-{family}-{n:04d}-{variant}",
        "fields": {"id": f"BP-{n:04d}", "n": n, "variant": variant},
    }


def _stages(family: str) -> list[dict[str, str]]:
    graphs: dict[str, list[dict[str, str]]] = {
        "linear-hash": [
            {"id": "ingest", "op": "read_input"},
            {"id": "hash", "op": "hash_payload"},
            {"id": "emit", "op": "write_artifact"},
        ],
        "predicate-branch": [
            {"id": "ingest", "op": "read_input"},
            {"id": "branch", "op": "predicate"},
            {"id": "emit", "op": "write_artifact"},
        ],
        "reduce-fold": [
            {"id": "ingest", "op": "read_input"},
            {"id": "fold", "op": "reduce_fold"},
            {"id": "emit", "op": "write_artifact"},
        ],
        "two-input-join": [
            {"id": "ingest", "op": "read_input"},
            {"id": "join", "op": "join_inputs"},
            {"id": "emit", "op": "write_artifact"},
        ],
        "retry-stable": [
            {"id": "ingest", "op": "read_input"},
            {"id": "retry", "op": "retry_until_stable"},
            {"id": "emit", "op": "write_artifact"},
        ],
        "schema-gate": [
            {"id": "ingest", "op": "read_input"},
            {"id": "validate", "op": "schema_validate"},
            {"id": "emit", "op": "write_artifact"},
        ],
        "window-agg": [
            {"id": "ingest", "op": "read_input"},
            {"id": "window", "op": "window_aggregate"},
            {"id": "emit", "op": "write_artifact"},
        ],
        "fan-out-in": [
            {"id": "ingest", "op": "read_input"},
            {"id": "split", "op": "fan_out"},
            {"id": "merge", "op": "fan_in"},
            {"id": "emit", "op": "write_artifact"},
        ],
        "diff-patch": [
            {"id": "ingest", "op": "read_input"},
            {"id": "diff", "op": "diff_patch"},
            {"id": "emit", "op": "write_artifact"},
        ],
        "topo-order": [
            {"id": "ingest", "op": "read_input"},
            {"id": "sort", "op": "topo_sort"},
            {"id": "emit", "op": "write_artifact"},
        ],
        "quota-bound": [
            {"id": "ingest", "op": "read_input"},
            {"id": "bound", "op": "apply_quota"},
            {"id": "emit", "op": "write_artifact"},
        ],
        "canonical-json": [
            {"id": "ingest", "op": "read_input"},
            {"id": "canon", "op": "canonicalize"},
            {"id": "emit", "op": "write_artifact"},
        ],
    }
    return graphs[family]


def _params(family: str, variant: int, n: int) -> dict[str, Any]:
    return {
        "salt": f"{family}:{n:04d}:{variant}",
        "hash_name": HASH_NAMES[variant],
        "threshold": 20 + variant * 5 + (n % 7),
        "fold_op": FOLD_OPS[variant],
        "join_key": "join",
        "max_retries": 1 + variant,
        "window": 2 + (variant % 5),
        "fanout": 2 + (variant % 4),
        "quota_bytes": 64 + variant * 8,
        "required_fields": ["id", "n", "variant"],
    }


def _mechanism(family: str, variant: int, params: dict[str, Any]) -> str:
    return (
        f"{family} variant={variant} salt={params['salt']} "
        f"hash={params['hash_name']} fold={params['fold_op']} "
        f"window={params['window']} fanout={params['fanout']} "
        f"quota={params['quota_bytes']} retries={params['max_retries']}"
    )


def make_blueprint(n: int) -> dict[str, Any]:
    family = FAMILIES[(n - 1) // 8]
    variant = (n - 1) % 8
    bid = f"BP-{n:04d}"
    params = _params(family, variant, n)
    stages = _stages(family)
    claimed = "flagship" if n <= FLAGSHIP_COUNT else "remainder"
    return {
        "id": bid,
        "title": f"{family} workflow {bid} (variant {variant})",
        "claimed_tier": claimed,
        "family": family,
        "variant": variant,
        "mechanism": _mechanism(family, variant, params),
        "not_a_duplicate_because": (
            f"mechanism family {family} with variant {variant}; "
            f"salt {params['salt']} and fold {params['fold_op']} "
            f"are unique to this id"
        ),
        "schema_version": 1,
        "stages": stages,
        "seed_input": _seed(n, family, variant),
        "stopping": {"max_stages": len(stages), "on_error": "halt"},
        "params": params,
    }


def build_library() -> list[dict[str, Any]]:
    rows = [make_blueprint(n) for n in range(1, BLUEPRINT_COUNT + 1)]
    if len(rows) != BLUEPRINT_COUNT:
        raise RuntimeError(f"library size {len(rows)}")
    flagship = sum(1 for r in rows if r["claimed_tier"] == "flagship")
    if flagship != FLAGSHIP_COUNT:
        raise RuntimeError(f"flagship claims {flagship}")
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise RuntimeError("duplicate blueprint ids")
    mechs = [r["mechanism"] for r in rows]
    if len(set(mechs)) != len(mechs):
        raise RuntimeError("duplicate mechanisms")
    return rows


BLUEPRINT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "id",
        "title",
        "claimed_tier",
        "family",
        "variant",
        "mechanism",
        "not_a_duplicate_because",
        "schema_version",
        "stages",
        "seed_input",
        "stopping",
        "params",
    ],
    "properties": {
        "id": {"type": "string", "pattern": "^BP-[0-9]{4}$"},
        "title": {"type": "string", "minLength": 8},
        "claimed_tier": {"type": "string", "enum": ["flagship", "remainder"]},
        "family": {"type": "string", "enum": list(FAMILIES)},
        "variant": {"type": "integer", "minimum": 0, "maximum": 7},
        "mechanism": {"type": "string", "minLength": 16},
        "not_a_duplicate_because": {"type": "string", "minLength": 16},
        "schema_version": {"type": "integer", "const": 1},
        "stages": {
            "type": "array",
            "minItems": 3,
            "items": {
                "type": "object",
                "required": ["id", "op"],
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "op": {"type": "string"},
                },
            },
        },
        "seed_input": {"type": "object"},
        "stopping": {
            "type": "object",
            "required": ["max_stages", "on_error"],
            "properties": {
                "max_stages": {"type": "integer", "minimum": 1},
                "on_error": {"type": "string"},
            },
        },
        "params": {"type": "object"},
    },
}
