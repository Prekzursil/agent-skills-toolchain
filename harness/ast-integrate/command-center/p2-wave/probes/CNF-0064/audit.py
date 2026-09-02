#!/usr/bin/env python3
"""License-blob auditor: SPDX and riders from file bytes, never from badges."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SENTINEL = (
    "SUCCESS:CNF-0064 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every candidate has a "
    "license blob SHA recorded, not merely an SPDX string copied from the "
    "registry. Any other terminal state is FAILED:CNF-0064 <classification> "
    "with the diagnostic tail attached."
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

RIDER_SPECS = (
    (
        "commons-clause",
        "restrictive-rider",
        re.compile(r"commons clause", re.I),
        re.compile(
            r".{0,120}does not grant to you, the right to Sell the Software.{0,80}",
            re.I | re.S,
        ),
    ),
    (
        "sustainable-use",
        "restrictive-primary",
        re.compile(r"sustainable use license", re.I),
        re.compile(
            r".{0,40}internal business purposes.{0,80}non-commercial.{0,80}",
            re.I | re.S,
        ),
    ),
    (
        "rsal-sspl",
        "restrictive-primary",
        re.compile(
            r"redis source available license|server side public license",
            re.I,
        ),
        re.compile(
            r"Redis Source Available License 2\.0.{0,80}|Server Side Public License",
            re.I | re.S,
        ),
    ),
    (
        "no-ml-training",
        "restrictive-rider",
        re.compile(r"train\s+machine\s+learning\s+models", re.I),
        re.compile(
            r".{0,80}shall not be used to train\s+machine\s+learning\s+models.{0,80}",
            re.I | re.S,
        ),
    ),
    (
        "evaluation-only",
        "restrictive-rider",
        re.compile(r"evaluation(?: use| only| license)", re.I),
        re.compile(r".{0,40}evaluation(?: use| only| license).{0,40}", re.I | re.S),
    ),
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_spdx(text: str) -> str:
    tl = text.replace("\r\n", "\n").lower()
    m = re.search(r"spdx-license-identifier:\s*([A-Za-z0-9.+_-]+)", text, re.I)
    if m:
        return m.group(1).strip()
    if "redis source available license" in tl or "rsalv2" in tl.replace(" ", ""):
        if "server side public license" in tl or "sspl" in tl:
            return "LicenseRef-RSALv2 OR SSPL-1.0"
        return "LicenseRef-RSALv2"
    if "sustainable use license" in tl:
        return "LicenseRef-SustainableUse-1.0"
    if "commons clause" in tl and "apache" in tl:
        return "Apache-2.0 WITH Commons-Clause"
    if "gnu general public license" in tl:
        if "version 3" in tl:
            return "GPL-3.0-only"
        return "GPL-2.0-only"
    if "apache license" in tl and "version 2.0" in tl:
        return "Apache-2.0"
    if "permission is hereby granted, free of charge" in tl:
        return "MIT"
    if (
        "redistribution and use in source and binary forms" in tl
        and "neither the name" in tl
    ):
        return "BSD-3-Clause"
    return "NOASSERTION"


def extract_verbatim(text: str, cre: re.Pattern, fallback: str) -> str:
    m = cre.search(text)
    if not m:
        return re.sub(r"\s+", " ", fallback)[:400]
    return re.sub(r"\s+", " ", m.group(0)).strip()[:400]


def detect_riders(text: str) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    for rid, kind, hit, grab in RIDER_SPECS:
        if not hit.search(text) or rid in seen:
            continue
        seen.add(rid)
        found.append(
            {
                "id": rid,
                "kind": kind,
                "verbatim": extract_verbatim(text, grab, text[:240]),
            }
        )
    return found


def spdx_equal(a: str, b: str) -> bool:
    aliases = {
        "MIT License": "MIT",
        "Apache License 2.0": "Apache-2.0",
        "Apache-2": "Apache-2.0",
        "BSD-3": "BSD-3-Clause",
        "BSD 3-Clause": "BSD-3-Clause",
    }
    na = aliases.get((a or "").strip(), (a or "").strip())
    nb = aliases.get((b or "").strip(), (b or "").strip())
    return na == nb


def load_registry() -> dict:
    return json.loads((HERE / "registry.json").read_text(encoding="utf-8"))


def resolve_blob(rel: str) -> Path:
    path = HERE / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    return path


def audit_candidate(row: dict) -> dict:
    pinned_rel = str(row["pinned_blob"])
    pinned_path = resolve_blob(pinned_rel)
    pinned_raw = pinned_path.read_bytes()
    pinned_text = pinned_raw.decode("utf-8", errors="replace")
    spdx_blob = parse_spdx(pinned_text)
    registry_spdx = str(row["registry_spdx"])
    earliest_rel = str(row.get("earliest_blob") or pinned_rel)
    earliest_path = resolve_blob(earliest_rel)
    earliest_text = earliest_path.read_text(encoding="utf-8", errors="replace")
    spdx_earliest = parse_spdx(earliest_text)
    riders = detect_riders(pinned_text)
    if earliest_rel != pinned_rel:
        for extra in detect_riders(earliest_text):
            extra = dict(extra)
            extra["id"] = extra["id"] + "@earliest"
            riders.append(extra)
    changed = not spdx_equal(spdx_earliest, spdx_blob)
    return {
        "id": row["id"],
        "name": row.get("name") or row["id"],
        "kind": row.get("kind") or "candidate",
        "source_repo": row.get("source_repo") or "",
        "pinned_ref": row.get("pinned_ref") or "",
        "pinned_git_sha": row.get("pinned_git_sha") or "",
        "license_path": row.get("license_path") or "LICENSE",
        "license_blob_path": (
            "command-center/p2-wave/probes/CNF-0064/" + pinned_rel.replace("\\", "/")
        ),
        "license_blob_sha256": sha256_bytes(pinned_raw),
        "license_blob_bytes": len(pinned_raw.replace(b"\r\n", b"\n")),
        "registry_spdx": registry_spdx,
        "spdx_from_blob": spdx_blob,
        "spdx_from_earliest_blob": spdx_earliest,
        "match_registry": spdx_equal(registry_spdx, spdx_blob),
        "license_identity_changed": changed,
        "blob_sha_changed": sha256_file(earliest_path) != sha256_bytes(pinned_raw),
        "riders": riders,
        "classifications": _classes(registry_spdx, spdx_blob, spdx_earliest, riders),
        "badge_metadata_ignored": True,
    }


def _classes(reg: str, blob: str, earliest: str, riders: list) -> list[str]:
    out: list[str] = []
    if not spdx_equal(reg, blob):
        out.append("license-mismatch")
    if not spdx_equal(earliest, blob):
        out.append("license-changed")
    if riders:
        out.append("restrictive-rider")
    if not out:
        out.append("confirmed-match")
    return out


def audit_all() -> list[dict]:
    return [audit_candidate(c) for c in load_registry()["candidates"]]


def artifact_payload(doc: dict) -> dict:
    """Domain rows live under report.* on a receipt_core document."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    return {
        "candidates": list(report.get("candidates") or doc.get("candidates") or []),
        "summary": dict(report.get("summary") or doc.get("summary") or {}),
        "method": dict(report.get("method") or doc.get("method") or {}),
    }
