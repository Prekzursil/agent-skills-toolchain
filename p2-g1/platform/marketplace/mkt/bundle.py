"""Offline export / import.

WHY THE REVOCATION AND ADVISORY LISTS TRAVEL WITH THE BUNDLE
    An air-gapped import that carried packages but not the revocation list would install
    exactly the versions the online path refuses. That is the same failure mode as a
    revocation that does not block, arriving through a different door. So
    :func:`export_bundle` copies both lists by default, records in ``includes`` whether it
    did, and :func:`import_bundle` REFUSES a bundle that omits a list the consumer's trust
    policy requires.

FORMAT
    A directory tree, not an archive. The bundle is a small registry root plus a signed
    ``bundle.json``, so an import is an ordinary install against a local registry and reuses
    every gate in :mod:`mkt.install` rather than inventing a second, weaker path. Turning it
    into a single file is a packaging concern (``shutil.make_archive``) and is left to the
    caller precisely so the verification path does not depend on an archive reader.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from . import registry as reg
from . import schemas
from .canon import ensure_within, iso_now, read_json, write_json
from .crypto import sign_document, verify_document

BUNDLE_NAME = "bundle.json"


class BundleError(RuntimeError):
    """The bundle is malformed, unsigned, or omits something the consumer requires."""


def bundle_id(source_registry_id: str, coordinates: list[tuple[str, str]]) -> str:
    seed = (
        source_registry_id + "|" + ";".join(f"{n}@{v}" for n, v in sorted(coordinates))
    )
    return "bun:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def export_bundle(
    registry_root: str | Path,
    out_dir: str | Path,
    *,
    packages: list[tuple[str, str]],
    maintainer_secret_hex: str,
    include_revocation: bool = True,
    include_advisory: bool = True,
    now: str | None = None,
) -> dict[str, Any]:
    """Export the named ``(name, version)`` coordinates into a self-contained bundle root."""
    src = Path(registry_root).resolve()
    out = Path(out_dir).resolve()
    timestamp = now or iso_now()
    index = reg.load_index(src)

    selected = []
    for name, version in packages:
        entry = next(
            (
                e
                for e in index["entries"]
                if e["name"] == name and e["version"] == version
            ),
            None,
        )
        if entry is None:
            raise BundleError(f"cannot export {name}@{version}: not in the index")
        selected.append(entry)
    if not selected:
        raise BundleError("refusing to export an empty bundle")

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    sub_index = dict(index)
    sub_index["entries"] = sorted(selected, key=lambda e: (e["name"], e["version"]))
    sub_index.pop("mirrors", None)
    sub_index.pop("collections", None)
    for entry in selected:
        rel = f"packages/{entry['name']}/{entry['version']}"
        shutil.copytree(ensure_within(src, rel), ensure_within(out, rel))

    includes = {"revocation": False, "advisory": False, "publishers": True}
    if include_revocation:
        rev = reg.load_revocation(src, index)
        if rev is not None:
            write_json(ensure_within(out, index["revocation_path"]), rev)
            includes["revocation"] = True
        else:
            sub_index.pop("revocation_path", None)
    else:
        sub_index.pop("revocation_path", None)
    if include_advisory:
        adv = reg.load_advisories(src, index)
        if adv is not None:
            write_json(ensure_within(out, index["advisory_path"]), adv)
            includes["advisory"] = True
        else:
            sub_index.pop("advisory_path", None)
    else:
        sub_index.pop("advisory_path", None)

    from .publish import sign_index

    sign_index(sub_index, maintainer_secret_hex, now=timestamp)
    write_json(reg.index_path(out), sub_index)

    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "bundle_id": bundle_id(
            index["registry_id"], [(e["name"], e["version"]) for e in selected]
        ),
        "source_registry_id": index["registry_id"],
        "exported_at": timestamp,
        "index_digest": reg.index_digest(sub_index),
        "packages": [
            {
                "name": e["name"],
                "version": e["version"],
                "manifest_digest": e["manifest_digest"],
                "payload_digest": e["payload_digest"],
            }
            for e in selected
        ],
        "includes": includes,
    }
    manifest["signature"] = sign_document(
        manifest, "mkt.bundle.v1", maintainer_secret_hex, signed_at=timestamp
    )
    schemas.validate("offline-bundle", manifest)
    write_json(out / BUNDLE_NAME, manifest)
    return manifest


def verify_bundle(
    bundle_root: str | Path, trust_policy: dict[str, Any]
) -> dict[str, Any]:
    """Verify a bundle's signature, its index, its digests and its ``includes`` against policy."""
    root = Path(bundle_root).resolve()
    path = root / BUNDLE_NAME
    if not path.is_file():
        raise BundleError(f"no {BUNDLE_NAME} at {root}")
    manifest = read_json(path)
    schemas.validate("offline-bundle", manifest)

    key = (manifest.get("signature") or {}).get("public_key")
    if key not in trust_policy["registry_maintainer_keys"]:
        raise BundleError(
            f"bundle signed by {key!r}, which is not a declared registry-maintainer key"
        )
    ok, why = verify_document(manifest, "mkt.bundle.v1", expected_public_key=key)
    if not ok:
        raise BundleError(f"bundle signature does not verify: {why}")

    index = reg.load_index(root)
    if reg.index_digest(index) != manifest["index_digest"]:
        raise BundleError("bundle index_digest does not match the index in the bundle")

    on_missing = trust_policy["on_missing"]
    if (
        not manifest["includes"]["revocation"]
        and on_missing["revocation_list"] == "refuse"
    ):
        raise BundleError(
            "bundle omits the revocation list and the trust policy is fail-closed on it. An offline "
            "import that carried packages but not their revocations would install exactly the "
            "versions the online path refuses."
        )
    if not manifest["includes"]["advisory"] and on_missing["advisory_list"] == "refuse":
        raise BundleError(
            "bundle omits the advisory list and the trust policy is fail-closed on it"
        )

    for row in manifest["packages"]:
        entry = next(
            (
                e
                for e in index["entries"]
                if e["name"] == row["name"] and e["version"] == row["version"]
            ),
            None,
        )
        if entry is None:
            raise BundleError(
                f"bundle claims {row['name']}@{row['version']} which its own index omits"
            )
        if (
            entry["manifest_digest"] != row["manifest_digest"]
            or entry["payload_digest"] != row["payload_digest"]
        ):
            raise BundleError(
                f"bundle digests disagree with its index for {row['name']}@{row['version']}"
            )
    return manifest


def import_bundle(
    bundle_root: str | Path,
    registry_root: str | Path,
    *,
    trust_policy: dict[str, Any],
    maintainer_secret_hex: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Verify a bundle then merge it into ``registry_root``, re-signing the destination index."""
    manifest = verify_bundle(bundle_root, trust_policy)
    src = Path(bundle_root).resolve()
    dst = Path(registry_root).resolve()
    timestamp = now or iso_now()

    bundle_index = reg.load_index(src)
    if reg.index_path(dst).is_file():
        index = reg.load_index(dst)
    else:
        index = dict(bundle_index)
        index["entries"] = []

    from .publish import upsert_entry, sign_index

    for entry in bundle_index["entries"]:
        rel = f"packages/{entry['name']}/{entry['version']}"
        target = ensure_within(dst, rel)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(ensure_within(src, rel), target)
        upsert_entry(index, entry)
    known = {p["id"] for p in index.get("publishers", [])}
    for pub in bundle_index.get("publishers", []):
        if pub["id"] not in known:
            index.setdefault("publishers", []).append(pub)

    for key in ("revocation_path", "advisory_path"):
        rel = bundle_index.get(key)
        if rel and ensure_within(src, rel).is_file():
            shutil.copy2(ensure_within(src, rel), ensure_within(dst, rel))
            index[key] = rel

    sign_index(index, maintainer_secret_hex, now=timestamp)
    write_json(reg.index_path(dst), index)
    return manifest
