"""Live completeness predicate for the ARC-0084 artifact envelope.

Reads ARTIFACT-MANIFEST.json FROM DISK. A writer-supplied registration
record, a present=true flag on the envelope, or a plausible digest is not
completion. Existence on disk is not completion.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from digest import digest_file
from floors import floors as class_floors

HEX64 = set("0123456789abcdef")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTRACT = REPO / "command-center" / "phase4" / "contracts" / "ARC-0084.json"


def _floor_map() -> dict[str, int]:
    if CONTRACT.is_file():
        try:
            doc = json.loads(CONTRACT.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            doc = None
        if isinstance(doc, dict):
            frozen = doc.get("size_floors")
            if isinstance(frozen, dict) and frozen:
                return {str(k): int(v) for k, v in frozen.items()}
    return class_floors()


@dataclass
class Verdict:
    ok: bool
    code: str
    details: str
    failed_checks: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "details": self.details,
            "failed_checks": list(self.failed_checks),
        }


def trust_writer(envelope: dict[str, Any]) -> bool:
    """Negative-control checker: believes the writer's in-memory claim.

    A unit that used this instead of evaluate() would green an unregistered
    on-disk file. Probe 1 asserts evaluate() still fails that case.
    """
    if envelope.get("registered") is True:
        return True
    rec = envelope.get("manifest_registration")
    return isinstance(rec, dict) and rec.get("present") is True


def _hex64(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in HEX64 for ch in value)
    )


def _load_manifest(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.is_file():
        return None, "manifest-absent"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"manifest-unparseable:{type(exc).__name__}"
    if not isinstance(doc, dict):
        return None, "manifest-not-object"
    rows = doc.get("artifacts")
    if not isinstance(rows, list):
        return None, "manifest-artifacts-missing"
    return doc, ""


def _row_for(doc: dict[str, Any], rel: str) -> dict[str, Any] | None:
    want = rel.replace("\\", "/")
    hits = []
    for row in doc.get("artifacts") or []:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "").replace("\\", "/")
        if path == want or path.endswith("/" + want) or path.endswith(want):
            hits.append(row)
    if not hits:
        return None
    return hits[0]


def evaluate(
    root: Path,
    envelope: dict[str, Any],
    *,
    artifact_rel: str | None = None,
) -> Verdict:
    """Evaluate completeness against files under `root`.

    `artifact_rel` defaults to envelope['path']. Manifest path comes from
    envelope['manifest_registration']['manifest_path'] and is read from disk.
    """
    failed: list[str] = []
    rel = (artifact_rel or str(envelope.get("path") or "")).replace("\\", "/")
    if not rel:
        return Verdict(False, "ENVELOPE_PATH_ABSENT", "envelope.path missing", ["path"])
    art = root / rel
    if not art.is_file():
        return Verdict(
            False,
            "ABSENT_ON_DISK",
            f"artifact {rel} is not a file",
            ["disk_exists"],
        )
    live_sha, live_bytes = digest_file(art)
    if live_bytes <= 0:
        failed.append("non_empty")

    cls = str(envelope.get("artifact_class") or "")
    floor_map = _floor_map()
    floor = int(floor_map.get(cls, 0) or 0)
    if floor <= 1:
        return Verdict(
            False,
            "FLOOR_INVALID",
            f"class {cls!r} has no real floor (>1)",
            ["size_floor"],
        )
    declared_size = envelope.get("byte_size")
    if not isinstance(declared_size, int) or declared_size != live_bytes:
        failed.append("byte_size_live")
    if live_bytes < floor:
        failed.append("size_floor")

    ch = envelope.get("content_hash")
    env_hex = ch.get("hex") if isinstance(ch, dict) else ch
    if not _hex64(env_hex) or env_hex != live_sha:
        failed.append("digest_envelope")

    rec = envelope.get("manifest_registration")
    if not isinstance(rec, dict):
        failed.append("manifest_registration_missing")
        return Verdict(
            False,
            "ENVELOPE_REGISTRATION_ABSENT",
            "manifest_registration missing",
            failed,
        )
    man_rel = str(rec.get("manifest_path") or "").replace("\\", "/")
    if not man_rel.endswith("ARTIFACT-MANIFEST.json"):
        failed.append("manifest_path_name")
        return Verdict(
            False,
            "MANIFEST_PATH_INVALID",
            f"manifest_path must end with ARTIFACT-MANIFEST.json, got {man_rel!r}",
            failed,
        )
    man_path = root / man_rel
    doc, err = _load_manifest(man_path)
    if doc is None:
        failed.append("manifest_on_disk")
        return Verdict(
            False,
            "MANIFEST_ABSENT" if err == "manifest-absent" else "MANIFEST_UNREADABLE",
            f"{man_rel}: {err} (on-disk existence of {rel} is not completion)",
            failed,
        )

    row = _row_for(doc, rel)
    if row is None:
        failed.append("registered_row")
        return Verdict(
            False,
            "UNREGISTERED",
            (
                f"{rel} exists on disk ({live_bytes} B) but has no row in "
                f"on-disk {man_rel}"
            ),
            failed,
        )
    if row.get("present") is not True:
        failed.append("registered_present")
    row_sha = str(row.get("sha256") or "")
    if not _hex64(row_sha) or row_sha != live_sha:
        failed.append("digest_manifest")
    row_bytes = row.get("bytes")
    if not isinstance(row_bytes, int) or row_bytes != live_bytes:
        failed.append("manifest_bytes")

    if failed:
        code = "DIGEST_MISMATCH" if any(x.startswith("digest_") for x in failed) else "PREDICATE_FAIL"
        if "size_floor" in failed:
            code = "SIZE_FLOOR"
        if "registered_present" in failed and "digest_manifest" not in failed:
            code = "UNREGISTERED"
        return Verdict(False, code, f"failed_checks={failed}", failed)
    return Verdict(True, "PASS", f"{rel} registered digest={live_sha} bytes={live_bytes}", [])
