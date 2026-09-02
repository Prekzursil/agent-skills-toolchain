"""Planted registry + git source for IMP-0080 live probes."""

from __future__ import annotations

from contextlib import contextmanager
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))
sys.path.insert(0, str(HERE))

import provenance_store as ps  # noqa: E402

PACKAGE = "agent-skills-toolchain"
VERSION = "1.2.3"
NONE_VERSION = "1.2.4"
ARTIFACT = b"IMP-0080 live probe artifact bytes\n"


@dataclass
class World:
    root: Path
    source: Path
    store: ps.ProvenanceStore
    artifact: bytes
    digest: str
    commit: str
    tree: str
    attestation: dict
    present: dict
    none: dict


def plant(base: Path) -> World:
    source = base / "source"
    commit, tree = ps.init_source_repo(
        source,
        {
            "plugin.json": b'{"name":"agent-skills-toolchain","version":"1.2.3"}\n',
            "README.md": b"fixture source for IMP-0080\n",
        },
    )
    digest = ps.artifact_sha256(ARTIFACT)
    attestation = ps.make_attestation(
        package=PACKAGE,
        version=VERSION,
        artifact_digest=digest,
        source_repo="git+https://example.invalid/org/agent-skills-toolchain.git",
        commit_sha=commit,
        tree_hash=tree,
        builder_id="https://ast-integrate.local/builders/imp-0080-probe",
        build_parameters={"profile": "release", "unit": "IMP-0080"},
    )
    store = ps.ProvenanceStore(base / "registry")
    present = store.publish(
        package=PACKAGE,
        version=VERSION,
        artifact=ARTIFACT,
        attestation=attestation,
        source_repo=source,
    )
    none = store.publish(package=PACKAGE, version=NONE_VERSION, attestation=None)
    return World(
        root=base,
        source=source,
        store=store,
        artifact=ARTIFACT,
        digest=digest,
        commit=commit,
        tree=tree,
        attestation=attestation,
        present=present,
        none=none,
    )


@contextmanager
def planted() -> Iterator[World]:
    with TemporaryDirectory(prefix="imp-0080-probe-") as td:
        yield plant(Path(td))
