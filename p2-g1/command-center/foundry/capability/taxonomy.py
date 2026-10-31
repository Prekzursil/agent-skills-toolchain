"""Capability taxonomy, lock, and unversioned-edit guard (IMP-0177)."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


class UnversionedTaxonomyEdit(RuntimeError):
    code = "unversioned-taxonomy-edit"

    def __init__(self, message: str = "unversioned-taxonomy-edit") -> None:
        super().__init__(message)
        self.code = UnversionedTaxonomyEdit.code


def _default_taxonomy() -> dict[str, Any]:
    families = {
        "research/evidence": ["watchlist", "gem-hunt", "citation"],
        "engineering/debug": ["root-cause", "repro"],
        "ops/release": ["rollback", "freeze"],
    }
    caps = [c for ids in families.values() for c in ids]
    version = "1.0.0"
    return {
        "version": version,
        "families": families,
        "capabilities": caps,
        "capability_count": len(caps),
        "capability_sha256": hashlib.sha256("|".join(sorted(caps)).encode("utf-8")).hexdigest(),
    }


def load_taxonomy(path: Path | None = None) -> dict[str, Any]:
    for cand in (
        path,
        HERE / "taxonomy.json",
        HERE.parent / "taxonomy.json",
    ):
        if cand is not None and Path(cand).is_file():
            doc = json.loads(Path(cand).read_text(encoding="utf-8"))
            if "capability_count" not in doc:
                caps = capability_ids(doc)
                doc["capability_count"] = len(caps)
            if "version" not in doc:
                doc["version"] = "1.0.0"
            return doc
    return _default_taxonomy()


def load_lock(path: Path | None = None) -> dict[str, Any]:
    tax = load_taxonomy()
    for cand in (path, HERE / "taxonomy.lock.json"):
        if cand is not None and Path(cand).is_file():
            return json.loads(Path(cand).read_text(encoding="utf-8"))
    return {
        "version": tax["version"],
        "capability_count": tax["capability_count"],
        "capability_ids": capability_ids(tax),
        "capability_sha256": tax.get("capability_sha256"),
    }


def load_spec() -> dict[str, list[str]]:
    return dict(load_taxonomy().get("families") or {})


def capability_ids(tax: dict[str, Any]) -> list[str]:
    if isinstance(tax.get("capabilities"), list) and tax["capabilities"]:
        return list(tax["capabilities"])
    families = tax.get("families") or {}
    out: list[str] = []
    for ids in families.values():
        out.extend(list(ids))
    return out


def spec_matches_taxonomy(families: dict[str, list[str]], tax: dict[str, Any]) -> tuple[bool, str]:
    tax_ids = set(capability_ids(tax))
    spec_ids = {c for ids in families.values() for c in ids}
    if spec_ids != tax_ids:
        return False, f"spec-taxonomy-mismatch spec={sorted(spec_ids)} tax={sorted(tax_ids)}"
    return True, "ok"


def check_guard(tax: dict[str, Any], lock: dict[str, Any], raise_on_fail: bool = False) -> dict[str, Any]:
    lock_ids = set(lock.get("capability_ids") or [])
    tax_ids = set(capability_ids(tax))
    version_ok = tax.get("version") != lock.get("version") or tax_ids == lock_ids
    if tax_ids != lock_ids and tax.get("version") == lock.get("version"):
        out = {"ok": False, "code": UnversionedTaxonomyEdit.code}
        if raise_on_fail:
            raise UnversionedTaxonomyEdit()
        return out
    if tax_ids == lock_ids:
        return {"ok": True, "code": None}
    if version_ok:
        return {"ok": True, "code": None}
    out = {"ok": False, "code": UnversionedTaxonomyEdit.code}
    if raise_on_fail:
        raise UnversionedTaxonomyEdit()
    return out


def mutate_add_capability(
    tax: dict[str, Any],
    *,
    family_id: str,
    capability_id: str,
    bump_version: bool,
) -> dict[str, Any]:
    out = copy.deepcopy(tax)
    families = dict(out.get("families") or {})
    ids = list(families.get(family_id) or [])
    if capability_id not in ids:
        ids.append(capability_id)
    families[family_id] = ids
    out["families"] = families
    caps = capability_ids(out)
    if capability_id not in caps:
        caps.append(capability_id)
    out["capabilities"] = caps
    out["capability_count"] = len(caps)
    if bump_version:
        ver = str(out.get("version") or "1.0.0")
        parts = ver.split(".")
        try:
            parts[-1] = str(int(parts[-1]) + 1)
        except ValueError:
            parts.append("1")
        out["version"] = ".".join(parts)
    return out
