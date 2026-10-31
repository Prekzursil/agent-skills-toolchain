#!/usr/bin/env python3
"""Typed WFA registry query interface (WFA-0084).

Hides four graph-file conventions behind versioned query types:
disposition, family, mechanism, licence_class, task_class, fusibility.

A miss is an explicit empty result (ok=True, empty=True, ids=[]).
An error is ok=False with ids=None so a caller cannot read it as zero.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

INTERFACE_VERSION = "1.0.0"
QUERY_TYPES = (
    "disposition",
    "family",
    "mechanism",
    "licence_class",
    "task_class",
    "fusibility",
)

RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "ok",
        "empty",
        "status",
        "error",
        "query_type",
        "selector",
        "ids",
        "artifact_version",
        "interface_version",
        "schema_fingerprint",
    ],
    "properties": {
        "ok": {"type": "boolean"},
        "empty": {"type": "boolean"},
        "status": {"type": "string", "enum": ["OK", "EMPTY", "ERROR"]},
        "error": {"type": ["string", "null"]},
        "query_type": {"type": "string"},
        "selector": {"type": ["string", "null"]},
        "ids": {"type": ["array", "null"], "items": {"type": "string"}},
        "artifact_version": {"type": ["object", "null"]},
        "interface_version": {"type": "string"},
        "schema_fingerprint": {"type": "string"},
    },
}


def schema_fingerprint(schema: dict[str, Any] | None = None) -> str:
    payload = json.dumps(
        schema if schema is not None else RESULT_SCHEMA,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


SCHEMA_FINGERPRINT = schema_fingerprint(RESULT_SCHEMA)
# Frozen at authoring. Updating RESULT_SCHEMA without bumping INTERFACE_VERSION
# and this ledger entry is the contract failure the version probe asserts.
VERSION_LEDGER = {
    "1.0.0": "11fde232c377042a8f3d4a2f71dc8ea2160601cebee77038b4b527debd6b1665",
}


def version_lock_holds(
    schema: dict[str, Any] | None = None,
    version: str | None = None,
    ledger: dict[str, str] | None = None,
) -> tuple[bool, str]:
    schema = RESULT_SCHEMA if schema is None else schema
    version = INTERFACE_VERSION if version is None else version
    ledger = VERSION_LEDGER if ledger is None else ledger
    fp = schema_fingerprint(schema)
    locked = ledger.get(version)
    if locked is None:
        return False, "version-not-in-ledger"
    if locked != fp:
        return False, "schema-changed-without-version-bump"
    return True, "ok"


def pair_key(a: str, b: str) -> str:
    x, y = sorted((str(a), str(b)))
    return f"{x}::{y}"


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


class QueryError(RuntimeError):
    """Caller used an ERROR result as if it were an id list."""


def require_ids(result: dict[str, Any]) -> list[str]:
    """The prescribed consumer helper: never treat an error as zero hits."""
    if not result.get("ok"):
        raise QueryError(str(result.get("error") or "query-error"))
    ids = result.get("ids")
    if ids is None:
        raise QueryError("ok-result-missing-ids")
    return [str(x) for x in ids]


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object in {path}")
    return data


class RegistryQueryInterface:
    """Stable query contract over the four graph artifacts (or a fixture corpus)."""

    def __init__(
        self,
        corpus_dir: Path,
        *,
        subtract_conflicts: bool = True,
    ) -> None:
        self.corpus_dir = Path(corpus_dir)
        self.subtract_conflicts = subtract_conflicts
        self._files = {
            "registry": self.corpus_dir / "registry.json",
            "provenance": self.corpus_dir / "provenance.json",
            "components": self.corpus_dir / "components.json",
            "compat": self.corpus_dir / "compat.json",
        }
        missing = [k for k, p in self._files.items() if not p.is_file()]
        if missing:
            raise FileNotFoundError(f"corpus missing {missing} under {corpus_dir}")
        self._registry_doc = _load_json(self._files["registry"])
        self._provenance_doc = _load_json(self._files["provenance"])
        self._components_doc = _load_json(self._files["components"])
        self._compat_doc = _load_json(self._files["compat"])
        self.artifact_version = self._artifact_version()
        self._records = self._index_records()
        self._licence_of = self._index_licences()
        self._conflicts = self._index_conflicts()
        self._compat_pairs = self._index_compat()

    def _artifact_version(self) -> dict[str, Any]:
        files: dict[str, Any] = {}
        hasher = hashlib.sha256()
        versions: list[str] = []
        for name, path in self._files.items():
            sha, size = digest_file(path)
            doc = _load_json(path)
            ver = str(doc.get("artifact_version") or "")
            versions.append(ver)
            files[name] = {
                "path": path.name,
                "sha256": sha,
                "bytes": size,
                "artifact_version": ver,
            }
            hasher.update(sha.encode("utf-8"))
            hasher.update(b"|")
        corpus_ver = versions[0] if versions and len(set(versions)) == 1 else "|".join(versions)
        return {
            "corpus_id": corpus_ver,
            "files": files,
            "corpus_sha256": hasher.hexdigest(),
        }

    def _index_records(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for rec in self._registry_doc.get("records") or []:
            if not isinstance(rec, dict):
                continue
            rid = str(rec.get("id") or "")
            if rid:
                out[rid] = rec
        return out

    def _index_licences(self) -> dict[str, str]:
        graph = self._provenance_doc.get("graph") or {}
        class_of: dict[str, str] = {}
        for node in graph.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            if node.get("kind") == "licence_class":
                class_of[str(node.get("id"))] = str(node.get("licence_class") or "")
        licence_of: dict[str, str] = {}
        for edge in graph.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            if edge.get("rel") != "has_licence":
                continue
            src = str(edge.get("src") or "")
            dst = str(edge.get("dst") or "")
            klass = class_of.get(dst)
            if src and klass:
                licence_of[src] = klass
        return licence_of

    def _index_conflicts(self) -> set[str]:
        pairs: set[str] = set()
        for link in self._components_doc.get("links") or []:
            if not isinstance(link, dict):
                continue
            if link.get("kind") != "conflicts-with":
                continue
            a = str(link.get("from") or "")
            b = str(link.get("to") or "")
            if a and b and a != b:
                pairs.add(pair_key(a, b))
        return pairs

    def _index_compat(self) -> set[str]:
        pairs: set[str] = set()
        for item in self._compat_doc.get("declared_compat") or []:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            a, b = str(item[0]), str(item[1])
            if a and b and a != b:
                pairs.add(pair_key(a, b))
        return pairs

    def _mechanisms(self, bid: str) -> set[str]:
        rec = self._records.get(bid) or {}
        return {str(m) for m in (rec.get("mechanisms") or [])}

    def _pair_conflicts(self, a: str, b: str) -> bool:
        if not self.subtract_conflicts:
            return False
        left = self._mechanisms(a)
        right = self._mechanisms(b)
        for m1 in left:
            for m2 in right:
                if m1 != m2 and pair_key(m1, m2) in self._conflicts:
                    return True
        return False

    def fusible_pairs(self) -> set[str]:
        out: set[str] = set()
        for pk in self._compat_pairs:
            a, b = pk.split("::", 1)
            if not self._pair_conflicts(a, b):
                out.add(pk)
        return out

    def incompatible_pairs(self) -> set[str]:
        return {pk for pk in self._compat_pairs if pk not in self.fusible_pairs()}

    def _result(
        self,
        *,
        ok: bool,
        empty: bool,
        status: str,
        error: str | None,
        query_type: str,
        selector: str | None,
        ids: list[str] | None,
    ) -> dict[str, Any]:
        return {
            "ok": ok,
            "empty": empty,
            "status": status,
            "error": error,
            "query_type": query_type,
            "selector": selector,
            "ids": ids,
            "artifact_version": None if not ok else self.artifact_version,
            "interface_version": INTERFACE_VERSION,
            "schema_fingerprint": SCHEMA_FINGERPRINT,
        }

    def _ok(self, query_type: str, selector: str, ids: list[str]) -> dict[str, Any]:
        if not ids:
            return self._result(
                ok=True,
                empty=True,
                status="EMPTY",
                error=None,
                query_type=query_type,
                selector=selector,
                ids=[],
            )
        return self._result(
            ok=True,
            empty=False,
            status="OK",
            error=None,
            query_type=query_type,
            selector=selector,
            ids=sorted(ids),
        )

    def _error(self, code: str, query_type: str, selector: str | None) -> dict[str, Any]:
        return self._result(
            ok=False,
            empty=False,
            status="ERROR",
            error=code,
            query_type=query_type,
            selector=selector,
            ids=None,
        )

    def query(self, query_type: str, selector: str) -> dict[str, Any]:
        q = str(query_type or "")
        sel = str(selector)
        if q not in QUERY_TYPES:
            return self._error("unknown-query-type", q, sel)
        if q == "disposition":
            ids = [
                rid
                for rid, rec in self._records.items()
                if str(rec.get("disposition") or "") == sel
            ]
            return self._ok(q, sel, ids)
        if q == "family":
            ids = [
                rid
                for rid, rec in self._records.items()
                if str(rec.get("family") or "") == sel
            ]
            return self._ok(q, sel, ids)
        if q == "mechanism":
            ids = [
                rid
                for rid, rec in self._records.items()
                if sel in {str(m) for m in (rec.get("mechanisms") or [])}
            ]
            return self._ok(q, sel, ids)
        if q == "licence_class":
            ids = [rid for rid, klass in self._licence_of.items() if klass == sel]
            return self._ok(q, sel, ids)
        if q == "task_class":
            ids = [
                rid
                for rid, rec in self._records.items()
                if str(rec.get("task_class") or "") == sel
            ]
            return self._ok(q, sel, ids)
        if q == "fusibility":
            if sel == "fusible":
                return self._ok(q, sel, list(self.fusible_pairs()))
            if sel in {"incompatible", "conflicted"}:
                return self._ok(q, sel, list(self.incompatible_pairs()))
            partners = [
                pk.split("::", 1)[1] if pk.split("::", 1)[0] == sel else pk.split("::", 1)[0]
                for pk in self.fusible_pairs()
                if sel in pk.split("::", 1)
            ]
            return self._ok(q, sel, partners)
        return self._error("unknown-query-type", q, sel)


def load_fixture_interface(
    probe_dir: Path | None = None,
    *,
    subtract_conflicts: bool = True,
) -> RegistryQueryInterface:
    root = Path(probe_dir) if probe_dir is not None else HERE
    return RegistryQueryInterface(
        root / "fixtures",
        subtract_conflicts=subtract_conflicts,
    )
