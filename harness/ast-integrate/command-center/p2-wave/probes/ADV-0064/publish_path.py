"""Live marketplace publish path used by ADV-0064 probes.

Publish is pack_package + BlobStore.put + PackageIndex.record_blob, the same
index mutation marketplace tests use. There is no name-grammar gate on that
path (IMP-0069's test_name_grammar.py is absent).
"""
from __future__ import annotations

import inspect
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from marketplace.blob_store import BlobStore  # noqa: E402
from marketplace.index import PackageIndex  # noqa: E402
from marketplace.testing_support import PKG as LIVE_MARKETPLACE_PKG  # noqa: E402
from plugin.payload import (  # noqa: E402
    blob_identity,
    pack_package,
    projection_of,
    unpack_package,
)

INDEX_REL = "tools/marketplace/index.py"
PAYLOAD_REL = "tools/plugin/payload.py"
SUPPORT_REL = "tools/marketplace/testing_support.py"
# First-party name the IMP-0069 grammar unit treats as a live existing name.
FIRST_PARTY_ESTATE = "agent-skills-toolchain"
DISTINCT_CONTROL = "quartz-beacon"
VERSION = "1.0.0"
NEEDLES = (
    "confusable",
    "homoglyph",
    "typosquat",
    "lookalike",
    "name_grammar",
    "reserved-name",
    "reserved_name",
)


def existing_seed_names() -> list[str]:
    names = [str(LIVE_MARKETPLACE_PKG), FIRST_PARTY_ESTATE]
    # Preserve order, drop duplicates.
    out: list[str] = []
    for name in names:
        if name and name not in out:
            out.append(name)
    return out


def protected_set() -> list[str]:
    return list(existing_seed_names())


def live_module_paths() -> dict[str, str]:
    return {
        "PackageIndex": inspect.getsourcefile(PackageIndex) or "",
        "record_blob": inspect.getsourcefile(PackageIndex.record_blob) or "",
        "pack_package": inspect.getsourcefile(pack_package) or "",
        "BlobStore": inspect.getsourcefile(BlobStore) or "",
    }


def source_scan() -> dict[str, Any]:
    files = {
        INDEX_REL: (REPO / INDEX_REL).read_text(encoding="utf-8"),
        PAYLOAD_REL: (REPO / PAYLOAD_REL).read_text(encoding="utf-8"),
        SUPPORT_REL: (REPO / SUPPORT_REL).read_text(encoding="utf-8"),
        "tools/plugin/pack.py": (REPO / "tools/plugin/pack.py").read_text(
            encoding="utf-8"
        ),
    }
    hits: dict[str, list[str]] = {}
    for rel, text in files.items():
        low = text.lower()
        found = [n for n in NEEDLES if n in low]
        hits[rel] = found
    grammar_test = REPO / "tools/marketplace/tests/test_name_grammar.py"
    pack_is_path_gate = "nfc+casefold" in files["tools/plugin/pack.py"].lower()
    return {
        "needles": list(NEEDLES),
        "hits": hits,
        "confusable_gate_present": any(hits[INDEX_REL]) or any(hits[PAYLOAD_REL]),
        "name_grammar_test_present": grammar_test.is_file(),
        "pack_py_is_payload_path_casefold_not_package_name": pack_is_path_gate,
        "live_marketplace_json_present": (REPO / ".claude-plugin/marketplace.json").is_file(),
        "catalog_schema_present": (
            REPO / "command-center/schema/supply-chain-attestation.schema.json"
        ).is_file(),
    }


def names_on_disk(index: PackageIndex) -> list[str]:
    data = json.loads(index.path.read_text(encoding="utf-8"))
    packages = data.get("packages") or {}
    if not isinstance(packages, dict):
        return []
    return sorted(packages.keys())


@dataclass
class World:
    root: Path
    store: BlobStore
    index: PackageIndex
    existing: list[str]


def _put_name(world: World, name: str, version: str = VERSION) -> dict[str, Any]:
    blob = pack_package(name, version, {"payload.txt": b"adv-0064-fixture\n"})
    unpacked = unpack_package(blob)
    ident_name, ident_ver = blob_identity(unpacked)
    digest = world.store.put(blob)
    world.index.record_blob(name, version, digest, projection_of(unpacked))
    present = name in names_on_disk(world.index)
    return {
        "outcome": "PUBLISHED",
        "refused": False,
        "name": name,
        "version": version,
        "digest": digest,
        "blob_identity_name": ident_name,
        "blob_identity_version": ident_ver,
        "index_present": present,
        "code": None,
        "error": None,
    }


def seed_world(root: Path | None = None) -> World:
    tmp = Path(root) if root else Path(tempfile.mkdtemp(prefix="adv0064-"))
    store = BlobStore(tmp / "blobs")
    index = PackageIndex(tmp / "index.json")
    world = World(root=tmp, store=store, index=index, existing=existing_seed_names())
    for name in world.existing:
        row = _put_name(world, name)
        if not row["index_present"]:
            raise RuntimeError(f"seed failed to index {name}")
    return world


def publish_name(world: World, name: str, version: str = VERSION) -> dict[str, Any]:
    """Attempt a real index publish. Exceptions are recorded as REFUSED."""
    try:
        return _put_name(world, name, version)
    except Exception as exc:  # noqa: BLE001 — publish outcome is the measurement
        return {
            "outcome": "REFUSED",
            "refused": True,
            "name": name,
            "version": version,
            "digest": None,
            "blob_identity_name": None,
            "blob_identity_version": None,
            "index_present": name in names_on_disk(world.index)
            if world.index.path.is_file()
            else False,
            "code": type(exc).__name__,
            "error": str(exc)[:500],
        }
