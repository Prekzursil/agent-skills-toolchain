"""Fixture package (vulnerable v1 / fixed v2), advisory, and indices."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from resolver import PACKAGE, V1, V2

HERE = Path(__file__).resolve().parent
NOW = datetime(2026, 8, 24, 20, 0, 0, tzinfo=timezone.utc)

ADVISORY = {
    "id": "ADV0066-001",
    "package": PACKAGE,
    "vulnerable_versions": [V1],
    "fixed_version": V2,
    "revoked": False,
    "summary": (
        "v1.0.0 is old and known-vulnerable. v2.0.0 is the fix. "
        "This is not a revocation (ADV-0038); no yank/withdraw signal exists."
    ),
}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def package_doc(version: str) -> dict[str, Any]:
    vulnerable = version == V1
    return {
        "name": PACKAGE,
        "version": version,
        "vulnerable": vulnerable,
        "marker": "VULN=1" if vulnerable else "VULN=0",
        "notes": (
            "planted known-vulnerable release for ADV-0066"
            if vulnerable
            else "fixed release; advisory names this as the floor"
        ),
    }


def package_sha(version: str) -> str:
    blob = json.dumps(package_doc(version), sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def listing(version: str) -> dict[str, Any]:
    return {
        "name": PACKAGE,
        "version": version,
        "vulnerable": version == V1,
        "sha256": package_sha(version),
        "path": f"packages/{version}/package.json",
    }


def make_index(
    versions: list[str],
    *,
    generated_at: datetime,
    expires_at: datetime,
    label: str,
) -> dict[str, Any]:
    return {
        "name": PACKAGE,
        "label": label,
        "generated_at": _iso(generated_at),
        "expires_at": _iso(expires_at),
        "packages": [listing(v) for v in versions],
    }


def fresh_index() -> dict[str, Any]:
    return make_index(
        [V1, V2],
        generated_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(days=1),
        label="fresh-both-versions",
    )


def v1_only_index() -> dict[str, Any]:
    """Same clock as fresh, but the index never lists v2. Proves consultation."""
    return make_index(
        [V1],
        generated_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(days=1),
        label="v1-only-unexpired",
    )


def stale_index() -> dict[str, Any]:
    """Expired mirror that never mentions v2."""
    return make_index(
        [V1],
        generated_at=NOW - timedelta(days=30),
        expires_at=NOW - timedelta(days=7),
        label="stale-expired-omits-v2",
    )


def incomplete_unexpired_index() -> dict[str, Any]:
    """Omits v2 but is not expired — freshness ≠ completeness."""
    return make_index(
        [V1],
        generated_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(days=7),
        label="unexpired-omits-v2",
    )


def v1_first_index() -> dict[str, Any]:
    """Both versions present; v1 listed first (REL-0004 first-match)."""
    idx = fresh_index()
    idx["label"] = "v1-listed-first"
    idx["packages"] = [listing(V1), listing(V2)]
    return idx


def materialize(root: Path | None = None) -> dict[str, str]:
    root = root or (HERE / "fixtures")
    written: dict[str, str] = {}

    def dump(rel: str, obj: Any) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(obj, indent=2, sort_keys=True) + "\n"
        path.write_text(text, encoding="utf-8")
        written[rel] = str(path)

    dump("advisory.json", ADVISORY)
    dump("packages/1.0.0/package.json", package_doc(V1))
    dump("packages/2.0.0/package.json", package_doc(V2))
    dump("mirrors/fresh/index.json", fresh_index())
    dump("mirrors/v1-only/index.json", v1_only_index())
    dump("mirrors/stale/index.json", stale_index())
    dump("mirrors/incomplete-unexpired/index.json", incomplete_unexpired_index())
    dump("mirrors/v1-first/index.json", v1_first_index())
    return written
