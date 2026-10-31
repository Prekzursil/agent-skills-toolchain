"""Canonical serialisation, digests, and path containment for the marketplace.

WHY THIS EXISTS
    Signatures, lockfiles and drift detection all rest on one question: *what exactly are
    the bytes?* Every other module in :mod:`mkt` gets that answer from here and nowhere
    else, so there is exactly ONE canonical form in the build.

DESIGN RULES THIS MODULE KEEPS

* **FLOATS ARE FORBIDDEN.** JSON gives no portable float spelling, so a signed document
  containing ``0.95`` may re-serialise to different bytes on a different runtime and its
  signature stops verifying for no security reason. The marketplace schemas therefore use
  integers only (``score_0_100``, ``value_milli``) and :func:`canonical_bytes` raises on a
  float rather than silently rounding one.

* **NEVER HASH WORKING-TREE BYTES TO COMPARE AGAINST GIT.** git stores LF, Windows checks
  out CRLF, so a working-tree hash is platform-dependent. The digests here are only ever
  compared against *another digest computed on the same machine in the same run* -- a
  published payload against the copy just installed from it. No expected digest is ever
  baked into a committed test or a committed index; the fixture registry is generated into
  a temp root at test time for exactly this reason.

* **CONTAINMENT IS REUSED, NOT RE-DERIVED.** :func:`ensure_within` is the idiom already
  proven at ``platform/lib/schema_resolver.py:147``
  (``str(target).startswith(str(root.resolve()) + os.sep)``), generalised to an arbitrary
  root. The trailing ``os.sep`` is load-bearing: without it ``C:/site-evil`` passes a
  containment check against ``C:/site``. That sibling-prefix bug has been shipped on this
  estate before, so the check is written once and imported everywhere.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class CanonError(ValueError):
    """A document cannot be put into canonical form (float, bad key, exotic type)."""


class ContainmentError(ValueError):
    """A path resolved outside the root it was required to stay inside."""


# --------------------------------------------------------------------------- #
# canonical form
# --------------------------------------------------------------------------- #


def _assert_canonicalisable(node: Any, path: str) -> None:
    if isinstance(node, bool) or node is None or isinstance(node, (int, str)):
        return
    if isinstance(node, float):
        raise CanonError(
            f"float at {path}: the canonical form forbids floats because JSON has no "
            "portable float spelling and a re-serialised float breaks its own signature"
        )
    if isinstance(node, dict):
        for key, value in node.items():
            if not isinstance(key, str):
                raise CanonError(f"non-string object key at {path}: {key!r}")
            _assert_canonicalisable(value, f"{path}.{key}")
        return
    if isinstance(node, list):
        for i, value in enumerate(node):
            _assert_canonicalisable(value, f"{path}[{i}]")
        return
    raise CanonError(f"unserialisable type {type(node).__name__} at {path}")


def canonical_bytes(doc: Any) -> bytes:
    """UTF-8 bytes of ``doc`` in canonical form: sorted keys, no whitespace, no floats."""
    _assert_canonicalisable(doc, "$")
    return json.dumps(
        doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def canonical_text(doc: Any) -> str:
    """Canonical form as text, for the human-readable on-disk artifacts."""
    return canonical_bytes(doc).decode("utf-8")


# --------------------------------------------------------------------------- #
# digests
# --------------------------------------------------------------------------- #


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def digest_doc(doc: Any) -> str:
    return digest_bytes(canonical_bytes(doc))


def hex_digest_file(path: str | Path) -> str:
    """Bare lowercase hex digest of a file's bytes (the SBOM ``hashes[].content`` form)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def digest_file(path: str | Path) -> str:
    """Prefixed digest of a file's bytes."""
    return "sha256:" + hex_digest_file(path)


def strip_signature(doc: dict[str, Any]) -> dict[str, Any]:
    """The document as it was when signed: a shallow copy without ``signature``."""
    return {k: v for k, v in doc.items() if k != "signature"}


def payload_digest(files: list[dict[str, Any]]) -> str:
    """Digest over a payload file list.

    Covers BOTH the path and the content hash of every file, sorted by path, so the
    digest changes if a file is added, removed, renamed or edited. Signing a manifest
    therefore transitively commits to the payload without the signer hashing a tarball.
    """
    rows = sorted([[str(f["path"]), str(f["sha256"])] for f in files])
    return digest_doc(rows)


# --------------------------------------------------------------------------- #
# paths
# --------------------------------------------------------------------------- #


def ensure_within(root: str | Path, candidate: str | Path) -> Path:
    """Resolve ``candidate`` and refuse if it is not strictly inside ``root``.

    The idiom is the one already proven at ``platform/lib/schema_resolver.py:147``. The
    trailing ``os.sep`` is what stops ``<root>-evil`` from passing as ``<root>``.
    """
    root_resolved = Path(root).resolve()
    target = (
        (root_resolved / candidate).resolve()
        if not Path(candidate).is_absolute()
        else Path(candidate).resolve()
    )
    if str(target) != str(root_resolved) and not str(target).startswith(
        str(root_resolved) + os.sep
    ):
        raise ContainmentError(
            f"path escapes its root: {candidate!r} -> {target} (root {root_resolved})"
        )
    return target


def read_json(path: str | Path) -> Any:
    """Read UTF-8 JSON. Bytes -> decode -> parse, so a BOM or CRLF cannot change the parse."""
    return json.loads(Path(path).read_bytes().decode("utf-8"))


def write_json(path: str | Path, doc: Any, *, canonical: bool = False) -> Path:
    """Write JSON atomically (tmp + replace) so a crash cannot leave a half document.

    ``canonical=True`` writes the exact signed bytes; otherwise a 2-space indented form
    is written for reviewability. The *signature* is always computed from the canonical
    form, never from the file bytes, so indentation can never change a verdict.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (
        canonical_bytes(doc)
        if canonical
        else (
            json.dumps(
                doc, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
            ).encode("utf-8")
            + b"\n"
        )
    )
    tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
    tmp.write_bytes(data)
    os.replace(tmp, target)
    return target


def iso_now() -> str:
    """UTC second-resolution ISO-8601 with a ``Z``, matching ``common.schema.json``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    if not ISO_RE.match(value):
        raise CanonError(f"not a canonical ISO-8601 UTC timestamp: {value!r}")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
