"""Reviewer-side library for wave1 shard2 independent verification (12 AUD units)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BAD_STATES = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
SLICE = "command-center/catalog-slices/AUD-1.json"
FOREIGN = "file:///C:/Users/Prekzursil/source/ast-integrate/"
REPO = Path.home() / "p2-g1"


def load_catalog_entries(ids):
    sl = json.loads((REPO / SLICE).read_text(encoding="utf-8"))
    by = {e["id"]: e for e in sl}
    missing = [i for i in ids if i not in by]
    if missing:
        raise SystemExit(f"catalog slice missing: {missing}")
    return {i: by[i] for i in ids}


def sha_lf(raw: bytes):
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def _retrieve(uri: str):
    """Map file:// URIs of the canonical checkout onto THIS repo's copies."""
    if uri.startswith(FOREIGN):
        local = REPO / uri[len(FOREIGN):]
    elif uri.startswith("file:///"):
        local = Path(uri[len("file:///"):])
    else:
        raise FileNotFoundError(uri)
    return Resource_from_contents(local)


def Resource_from_contents(local: Path):
    from referencing import Resource
    return Resource.from_contents(json.loads(local.read_text(encoding="utf-8")))


def validate_against_schema(repo: Path, doc, schema_rel: str):
    try:
        import jsonschema
        from referencing import Registry
        schema = json.loads((repo / schema_rel).read_text(encoding="utf-8"))
        reg = Registry(retrieve=_retrieve)
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        v = cls(schema, registry=reg)
        errs = sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))
        if errs:
            e0 = errs[0]
            return False, (
                f"{len(errs)} errors; first at {list(e0.absolute_path)[:6]}: "
                + str(e0.message)[:300]
            )
        return True, f"valid against {schema_rel} ({cls.__name__})"
    except Exception as ex:
        return False, f"validator error: {ex!r}"
