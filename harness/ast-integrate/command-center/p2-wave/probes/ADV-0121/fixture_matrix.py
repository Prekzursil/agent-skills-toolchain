"""Hand-edited N-2 layout trees for ADV-0121.

Variants named by the catalog question: unknown keys, reordered sections,
comments, a different line-ending style, a value outside the current enum,
plus the required pristine control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from plugin.migration import (  # noqa: E402
    MigrationError,
    build_demo_tree,
    demo_engine,
    dump_json,
)

UNIT = "ADV-0121"
STRICT_SCHEMA_REL = (
    "command-center/p2-wave/probes/ADV-0121/fixtures/n2-config.strict.schema.json"
)
ENGINE_KEYS = frozenset({"layout", "token_file", "key_location"})
ENGINE_LAYOUTS = frozenset({"copied-skills", "v1-relocated-key"})
USER_MARK = "keep-me-adv0121"
USER_ENUM = "user-edited-layout-not-in-enum"
USER_KEY = "user_custom_key"

VARIANT_IDS = (
    "pristine",
    "unknown-key",
    "reordered",
    "comments",
    "crlf",
    "enum-out-of-range",
)


def load_strict_schema() -> dict[str, Any]:
    return json.loads((REPO / STRICT_SCHEMA_REL).read_text(encoding="utf-8"))


def strict_check(raw: bytes) -> dict[str, Any]:
    """Parse then Draft-07 additionalProperties:false (spec 11302)."""
    out: dict[str, Any] = {
        "parse_ok": False,
        "schema_ok": False,
        "errors": [],
        "crlf": b"\r\n" in raw,
    }
    try:
        text = raw.decode("utf-8")
        doc = json.loads(text)
    except Exception as exc:
        out["errors"].append(f"{type(exc).__name__}: {exc}")
        return out
    out["parse_ok"] = True
    if not isinstance(doc, dict):
        out["errors"].append("not a JSON object")
        return out
    try:
        import jsonschema
    except ImportError:
        out["errors"].append("jsonschema-unavailable")
        return out
    validator = jsonschema.Draft7Validator(load_strict_schema())
    errs = [e.message for e in validator.iter_errors(doc)]
    out["errors"] = errs
    out["schema_ok"] = not errs
    return out


def user_surface(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """User-authored configuration payload, excluding designed engine keys.

    A layout value outside the engine enum is user content. The live key path
    (token_file / key_location) is also user content.
    """
    if not isinstance(doc, dict):
        return None
    extra = {k: v for k, v in doc.items() if k not in ENGINE_KEYS}
    layout = doc.get("layout")
    if layout not in ENGINE_LAYOUTS:
        extra["$layout_user_enum"] = layout
    extra["$live_key_path"] = doc.get("key_location", doc.get("token_file"))
    return extra


def lost_user_keys(before: dict[str, Any] | None, after: dict[str, Any] | None) -> list[str]:
    if before is None:
        return ["$unparseable-pre"]
    if after is None:
        return sorted(before.keys())
    lost: list[str] = []
    for key, value in before.items():
        if key not in after:
            lost.append(key)
            continue
        if json.dumps(after[key], sort_keys=True) != json.dumps(value, sort_keys=True):
            lost.append(key)
    return lost


def _write_config(root: Path, text: str) -> None:
    (root / "config.json").write_text(text, encoding="utf-8")


def mutate_pristine(_root: Path) -> None:
    return None


def mutate_unknown_key(root: Path) -> None:
    doc = json.loads((root / "config.json").read_text(encoding="utf-8"))
    doc[USER_KEY] = USER_MARK
    _write_config(root, dump_json(doc))


def mutate_reordered(root: Path) -> None:
    # Opposite of dump_json(sort_keys=True) which emits layout then token_file.
    _write_config(
        root,
        '{\n  "token_file": "root.json",\n  "layout": "copied-skills"\n}\n',
    )


def mutate_comments(root: Path) -> None:
    _write_config(
        root,
        "{\n"
        '  "layout": "copied-skills",\n'
        "  // user hand-edit kept as a comment\n"
        '  "token_file": "root.json"\n'
        "}\n",
    )


def mutate_crlf(root: Path) -> None:
    path = root / "config.json"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))


def mutate_enum(root: Path) -> None:
    doc = json.loads((root / "config.json").read_text(encoding="utf-8"))
    doc["layout"] = USER_ENUM
    _write_config(root, dump_json(doc))


MUTATORS: dict[str, Callable[[Path], None]] = {
    "pristine": mutate_pristine,
    "unknown-key": mutate_unknown_key,
    "reordered": mutate_reordered,
    "comments": mutate_comments,
    "crlf": mutate_crlf,
    "enum-out-of-range": mutate_enum,
}


def seed_variant(parent: Path, variant_id: str) -> Path:
    if variant_id not in MUTATORS:
        raise KeyError(variant_id)
    root = build_demo_tree(parent / variant_id)
    MUTATORS[variant_id](root)
    return root


def classify(
    *,
    migrated: bool,
    exception_type: str | None,
    exception_msg: str | None,
    lost: list[str],
) -> str:
    if exception_type:
        if exception_type == "MigrationError":
            return "refused_clear"
        return "crashed"
    if not migrated:
        return "refused_clear"
    if lost:
        return "silent_loss"
    return "migrated_ok"


def run_one(parent: Path, variant_id: str) -> dict[str, Any]:
    """Migrate one hostile N-2 tree. Temp parent is the caller's."""
    root = seed_variant(parent, variant_id)
    cfg = root / "config.json"
    pre_raw = cfg.read_bytes()
    pre_strict = strict_check(pre_raw)
    pre_doc: dict[str, Any] | None = None
    if pre_strict["parse_ok"]:
        pre_doc = json.loads(pre_raw.decode("utf-8"))
    pre_user = user_surface(pre_doc)
    journal = parent / f"{variant_id}.journal.json"
    migrated = False
    status = None
    current = None
    exc_type = None
    exc_msg = None
    try:
        result = demo_engine().migrate(root, "3", journal=journal)
        migrated = result.get("status") == "complete"
        status = result.get("status")
        current = result.get("current_version")
    except MigrationError as exc:
        exc_type = "MigrationError"
        exc_msg = str(exc)
    except Exception as exc:
        exc_type = type(exc).__name__
        exc_msg = str(exc)
    post_raw = cfg.read_bytes() if cfg.is_file() else b""
    post_strict = strict_check(post_raw) if post_raw else {
        "parse_ok": False,
        "schema_ok": False,
        "errors": ["missing-post-config"],
        "crlf": False,
    }
    post_doc: dict[str, Any] | None = None
    if post_strict.get("parse_ok"):
        post_doc = json.loads(post_raw.decode("utf-8"))
    post_user = user_surface(post_doc)
    lost = lost_user_keys(pre_user, post_user) if pre_user is not None else (
        ["$unparseable-pre"] if not migrated else []
    )
    if pre_user is None:
        lost = ["$unparseable-pre"]
    outcome = classify(
        migrated=migrated,
        exception_type=exc_type,
        exception_msg=exc_msg,
        lost=[k for k in lost if k != "$unparseable-pre"] if migrated else lost,
    )
    if pre_user is None and not migrated:
        outcome = classify(
            migrated=False,
            exception_type=exc_type,
            exception_msg=exc_msg,
            lost=lost,
        )
    return {
        "variant": variant_id,
        "migrated": migrated,
        "status": status,
        "current_version": current,
        "exception_type": exc_type,
        "exception_message": exc_msg,
        "pre_strict": pre_strict,
        "post_strict": post_strict,
        "pre_user": pre_user,
        "post_user": post_user,
        "lost_user_keys": lost,
        "silent_loss": bool(migrated and [k for k in lost if k != "$unparseable-pre"]),
        "pre_crlf": pre_strict["crlf"],
        "post_crlf": bool(post_strict.get("crlf")),
        "outcome": outcome,
        "engine_validates_config": False,
    }
