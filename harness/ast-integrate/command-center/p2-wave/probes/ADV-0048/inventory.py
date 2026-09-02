#!/usr/bin/env python3
"""ADV-0048 two-tier license identification (shared by emit and named probes).

Probe 1 (this module's `identify_component` / `automated_inventory`): SPDX-ish
fingerprints plus package metadata. Conflicts become custom/unknown.

Probe 2 (`clause_readings`): reads LICENSE bytes and extracts a distribution
constraint clause. It does not reuse the fingerprint SPDX label as the clause.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
UNKNOWN_RATE_THRESHOLD = 0.15
ESCALATE_FAMILIES = frozenset({"copyleft", "weak-copyleft", "unknown", "custom"})
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".cursor",
        ".venv",
        "dist",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "htmlcov",
        ".tox",
    }
)
LICENSE_FILENAMES = frozenset(
    {
        "license",
        "license.md",
        "license.txt",
        "licence",
        "licence.md",
        "licence.txt",
        "copying",
        "copying.txt",
        "copying.md",
        "notice",
        "notice.md",
        "notice.txt",
    }
)
TEXT_SUFFIXES = frozenset(
    {".py", ".md", ".txt", ".ts", ".js", ".go", ".rs", ".c", ".h", ".hpp", ".java"}
)
SPDX_HEADER_RE = re.compile(
    r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)", re.IGNORECASE
)

FINGERPRINTS: list[tuple[str, str, str, tuple[str, ...]]] = [
    (
        "MIT",
        "permissive",
        "mit-fingerprint",
        (
            "permission is hereby granted, free of charge",
            'the software is provided "as is"',
            "without warranty of any kind",
        ),
    ),
    (
        "Apache-2.0",
        "permissive",
        "apache-2.0-fingerprint",
        ("apache license", "version 2.0, january 2004"),
    ),
    (
        "BSD-3-Clause",
        "permissive",
        "bsd-3-fingerprint",
        (
            "redistribution and use in source and binary forms",
            "neither the name of",
        ),
    ),
    (
        "ISC",
        "permissive",
        "isc-fingerprint",
        (
            "permission to use, copy, modify, and/or distribute this software for any purpose with or without fee",
        ),
    ),
    (
        "GPL-3.0-only",
        "copyleft",
        "gpl-3-fingerprint",
        ("gnu general public license", "version 3, 29 june 2007"),
    ),
    (
        "GPL-2.0-only",
        "copyleft",
        "gpl-2-fingerprint",
        ("gnu general public license", "version 2, june 1991"),
    ),
    (
        "AGPL-3.0-only",
        "copyleft",
        "agpl-3-fingerprint",
        ("gnu affero general public license", "version 3"),
    ),
    (
        "LGPL-3.0-only",
        "weak-copyleft",
        "lgpl-3-fingerprint",
        ("gnu lesser general public license", "version 3"),
    ),
    (
        "LGPL-2.1-only",
        "weak-copyleft",
        "lgpl-2.1-fingerprint",
        ("gnu lesser general public license", "version 2.1"),
    ),
    (
        "MPL-2.0",
        "weak-copyleft",
        "mpl-2-fingerprint",
        ("mozilla public license version 2.0",),
    ),
    (
        "Unlicense",
        "public-domain",
        "unlicense-fingerprint",
        ("this is free and unencumbered software released into the public domain",),
    ),
]

SPDX_FAMILY = {
    "MIT": "permissive",
    "ISC": "permissive",
    "BSD-2-Clause": "permissive",
    "BSD-3-Clause": "permissive",
    "Apache-2.0": "permissive",
    "0BSD": "public-domain",
    "Unlicense": "public-domain",
    "CC0-1.0": "public-domain",
    "GPL-2.0": "copyleft",
    "GPL-2.0-only": "copyleft",
    "GPL-2.0-or-later": "copyleft",
    "GPL-3.0": "copyleft",
    "GPL-3.0-only": "copyleft",
    "GPL-3.0-or-later": "copyleft",
    "AGPL-3.0": "copyleft",
    "AGPL-3.0-only": "copyleft",
    "LGPL-2.1": "weak-copyleft",
    "LGPL-2.1-only": "weak-copyleft",
    "LGPL-3.0": "weak-copyleft",
    "LGPL-3.0-only": "weak-copyleft",
    "MPL-2.0": "weak-copyleft",
    "EPL-2.0": "weak-copyleft",
}

COPYLEFT_CLAUSE_RES = [
    (
        "gpl-entire-work",
        re.compile(
            r"you must license the entire work[^\n.]{0,80}as a whole[^\n.]{0,200}",
            re.IGNORECASE,
        ),
    ),
    (
        "agpl-network",
        re.compile(
            r"if you modify the program[^\n.]{0,120}remote network interaction",
            re.IGNORECASE,
        ),
    ),
    (
        "lgpl-library",
        re.compile(
            r"you may convey a combined work under terms of your choice",
            re.IGNORECASE,
        ),
    ),
    (
        "share-alike",
        re.compile(r"share[- ]alike|copyleft", re.IGNORECASE),
    ),
]


def rel_posix(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def is_skipped(rel: Path) -> bool:
    if any(part in SKIP_DIR_NAMES for part in rel.parts):
        return True
    if "probes" in rel.parts:
        try:
            i = rel.parts.index("probes")
        except ValueError:
            return False
        uid = rel.parts[i + 1] if i + 1 < len(rel.parts) else ""
        # probes/ itself must remain walkable so ADV-0048 can be entered.
        if uid == "":
            return False
        if uid != "ADV-0048":
            return True
    return False


def is_product_scope(rel: Path) -> bool:
    if is_skipped(rel):
        return False
    if "ADV-0048" in rel.parts and "fixtures" in rel.parts:
        return False
    return True


def read_text(path: Path, limit: int = 200_000) -> str:
    try:
        data = path.read_bytes()[:limit]
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def fingerprint_license(text: str) -> dict[str, Any] | None:
    blob = text.lower()
    best: tuple[int, dict[str, Any]] | None = None
    for spdx, family, method, markers in FINGERPRINTS:
        hits = [m for m in markers if m in blob]
        need = max(1, (len(markers) + 1) // 2)
        if len(hits) >= need and hits:
            rec = {
                "spdx": spdx,
                "family": family,
                "method": method,
                "markers_hit": hits,
            }
            if best is None or len(hits) > best[0]:
                best = (len(hits), rec)
    return None if best is None else best[1]


def metadata_license(pkg_json: Path) -> dict[str, Any] | None:
    if not pkg_json.is_file():
        return None
    try:
        doc = json.loads(pkg_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    raw = doc.get("license")
    if isinstance(raw, dict):
        raw = raw.get("type")
    if not isinstance(raw, str) or not raw.strip():
        return None
    spdx = raw.strip()
    family = SPDX_FAMILY.get(spdx)
    if family is None:
        family = "custom" if (" " in spdx or "SEE LICENSE" in spdx.upper()) else "unknown"
    if spdx.upper() in {"UNLICENSED", "SEE LICENSE IN LICENSE"}:
        family = "unknown"
    return {
        "spdx": spdx,
        "family": family,
        "method": "package.json-license-field",
        "raw": spdx,
    }


def combine_signals(
    file_hit: dict[str, Any] | None,
    meta_hit: dict[str, Any] | None,
    extra_evidence: list[str],
) -> dict[str, Any]:
    bits = list(extra_evidence)
    if file_hit and meta_hit:
        bits.append(
            f"file={file_hit['method']}:{file_hit['spdx']}; "
            f"metadata={meta_hit['method']}:{meta_hit['spdx']}"
        )
        same = (
            file_hit["spdx"] == meta_hit["spdx"]
            and file_hit["family"] == meta_hit["family"]
        )
        if not same:
            return {
                "automated_spdx": "NOASSERTION",
                "automated_family": "custom",
                "evidence_string": "identifier-text-conflict: " + "; ".join(bits),
                "conflict": True,
                "file_hit": file_hit,
                "meta_hit": meta_hit,
            }
        return {
            "automated_spdx": file_hit["spdx"],
            "automated_family": file_hit["family"],
            "evidence_string": "; ".join(bits),
            "conflict": False,
            "file_hit": file_hit,
            "meta_hit": meta_hit,
        }
    if file_hit:
        bits.append(f"file={file_hit['method']}:{file_hit['spdx']}")
        if file_hit.get("markers_hit"):
            bits.append("markers=" + ",".join(file_hit["markers_hit"][:4]))
        return {
            "automated_spdx": file_hit["spdx"],
            "automated_family": file_hit["family"],
            "evidence_string": "; ".join(bits),
            "conflict": False,
            "file_hit": file_hit,
            "meta_hit": None,
        }
    if meta_hit:
        bits.append(f"metadata={meta_hit['method']}:{meta_hit['spdx']}")
        return {
            "automated_spdx": meta_hit["spdx"],
            "automated_family": meta_hit["family"],
            "evidence_string": "; ".join(bits),
            "conflict": False,
            "file_hit": None,
            "meta_hit": meta_hit,
        }
    bits.append(
        "no LICENSE/COPYING/NOTICE fingerprint and no package.json license field"
    )
    return {
        "automated_spdx": "NOASSERTION",
        "automated_family": "unknown",
        "evidence_string": "; ".join(bits),
        "conflict": False,
        "file_hit": None,
        "meta_hit": None,
    }


def identify_dir(component_dir: Path) -> dict[str, Any]:
    extra: list[str] = []
    texts: list[tuple[str, str]] = []
    if not component_dir.is_dir():
        return combine_signals(None, None, [f"missing-dir={rel_posix(component_dir)}"])
    for name in sorted(p.name for p in component_dir.iterdir() if p.is_file()):
        if name.lower() in LICENSE_FILENAMES:
            path = component_dir / name
            texts.append((name, read_text(path)))
            extra.append(f"license-file={rel_posix(path)}")
    file_hit = None
    for _name, text in texts:
        hit = fingerprint_license(text)
        if hit:
            file_hit = hit
            break
    meta_hit = metadata_license(component_dir / "package.json")
    return combine_signals(file_hit, meta_hit, extra)


def identify_component(component_dir: Path) -> dict[str, Any]:
    return identify_dir(component_dir)


def scan_product() -> dict[str, Any]:
    license_files: list[str] = []
    spdx_headers: list[dict[str, str]] = []
    files_considered = 0
    for dirpath, dirnames, filenames in os.walk(REPO, followlinks=False):
        try:
            rel_dir = Path(dirpath).relative_to(REPO)
        except ValueError:
            dirnames[:] = []
            continue
        keep: list[str] = []
        for name in dirnames:
            child = Path(name) if rel_dir.as_posix() == "." else rel_dir / name
            if is_skipped(child):
                continue
            keep.append(name)
        dirnames[:] = keep
        for name in filenames:
            path = Path(dirpath) / name
            try:
                rel = path.relative_to(REPO)
            except ValueError:
                continue
            if not is_product_scope(rel):
                continue
            files_considered += 1
            if path.name.lower() in LICENSE_FILENAMES:
                license_files.append(rel.as_posix())
            if path.suffix.lower() in TEXT_SUFFIXES and path.stat().st_size <= 512_000:
                head = read_text(path, limit=4096)
                m = SPDX_HEADER_RE.search(head)
                if m:
                    spdx_headers.append({"path": rel.as_posix(), "spdx": m.group(1)})
    evidence = (
        f"product-walk files_considered={files_considered}; "
        f"license_files={len(license_files)}; "
        f"spdx_headers={len(spdx_headers)}"
    )
    if license_files:
        evidence += "; files=" + ",".join(license_files[:12])
    if spdx_headers:
        evidence += "; headers=" + ",".join(
            f"{h['path']}:{h['spdx']}" for h in spdx_headers[:8]
        )
    else:
        evidence += "; no SPDX-License-Identifier in scanned first-party text"
    hits: list[dict[str, Any]] = []
    for lf in license_files:
        hit = fingerprint_license(read_text(REPO / lf))
        if hit:
            hits.append(hit)
    if len(hits) == 1 and not spdx_headers and len(license_files) == 1:
        combined = combine_signals(hits[0], None, [evidence])
    elif not hits and not spdx_headers:
        combined = combine_signals(None, None, [evidence])
    else:
        combined = combine_signals(
            None, None, [evidence + "; mixed-or-absent-product-licenses"]
        )
        combined["automated_family"] = "unknown"
        combined["automated_spdx"] = "NOASSERTION"
    return {
        **combined,
        "files_considered": files_considered,
        "license_files": license_files,
        "spdx_headers": spdx_headers,
    }


def component_record(
    cid: str,
    scope: str,
    path: str,
    ident: dict[str, Any],
    outbound_spdx: str | None,
) -> dict[str, Any]:
    family = ident["automated_family"]
    escalate = family in ESCALATE_FAMILIES
    if outbound_spdx is None or family == "unknown":
        compatible: bool | None = None
    elif family in {"permissive", "public-domain"}:
        compatible = True
    elif family in {"copyleft", "weak-copyleft", "custom"}:
        compatible = False
    else:
        compatible = None
    return {
        "id": cid,
        "scope": scope,
        "path": path,
        "automated_spdx": ident["automated_spdx"],
        "automated_family": family,
        "evidence_string": ident["evidence_string"][:2000],
        "compatible_with_outbound": compatible,
        "escalates_to_probe2": escalate,
        "conflict": bool(ident.get("conflict")),
    }


def automated_inventory() -> dict[str, Any]:
    outbound_spdx = None
    outbound_reason = (
        "no root LICENSE, COPYING, NOTICE, SPDX header, or package.json license "
        "declares an outbound identifier on this worktree"
    )
    product = scan_product()
    controls = [
        (
            "control:known-unambiguous-mit",
            "control",
            "command-center/p2-wave/probes/ADV-0048/fixtures/control-mit",
            identify_dir(FIXTURES / "control-mit"),
        ),
        (
            "control:known-gpl3",
            "control",
            "command-center/p2-wave/probes/ADV-0048/fixtures/control-gpl",
            identify_dir(FIXTURES / "control-gpl"),
        ),
        (
            "control:mislabeled-mit-metadata-gpl-text",
            "control",
            "command-center/p2-wave/probes/ADV-0048/fixtures/control-mislabeled",
            identify_dir(FIXTURES / "control-mislabeled"),
        ),
        (
            "control:not-a-license",
            "control",
            "command-center/p2-wave/probes/ADV-0048/fixtures/control-not-a-license",
            identify_dir(FIXTURES / "control-not-a-license"),
        ),
    ]
    components = [
        component_record(
            "first-party:ast-integrate",
            "product",
            "(repo-root)",
            product,
            outbound_spdx,
        )
    ]
    for cid, scope, path, ident in controls:
        components.append(component_record(cid, scope, path, ident, outbound_spdx))

    unknown_n = sum(1 for c in components if c["automated_family"] == "unknown")
    unknown_rate = unknown_n / max(1, len(components))
    matrix_clean = unknown_rate <= UNKNOWN_RATE_THRESHOLD
    copyleft_product = [
        c
        for c in components
        if c["scope"] == "product"
        and c["automated_family"] in {"copyleft", "weak-copyleft"}
    ]
    return {
        "outbound_spdx": outbound_spdx,
        "outbound_reason": outbound_reason,
        "unknown_rate_threshold": UNKNOWN_RATE_THRESHOLD,
        "unknown_n": unknown_n,
        "component_n": len(components),
        "unknown_rate": round(unknown_rate, 4),
        "matrix_cleanliness": "clean" if matrix_clean else "NOT-CHECKED",
        "copyleft_in_product": copyleft_product,
        "product_scan": {
            "files_considered": product["files_considered"],
            "license_files": product["license_files"],
            "spdx_headers": product["spdx_headers"],
        },
        "components": components,
    }


def license_bytes_for(component: dict[str, Any]) -> tuple[str, str]:
    rel = component.get("path") or ""
    if rel in {"", "."}:
        return "", ""
    base = REPO / rel
    if not base.is_dir():
        return rel, ""
    for name in ("LICENSE", "LICENSE.md", "COPYING", "COPYING.txt", "NOTICE"):
        cand = base / name
        if cand.is_file():
            return rel_posix(cand), read_text(cand)
    for path in sorted(base.iterdir()):
        if path.is_file() and path.name.lower() in LICENSE_FILENAMES:
            return rel_posix(path), read_text(path)
    return rel, ""


def extract_clauses(text: str) -> list[dict[str, str]]:
    """Obligation extraction: mechanically different from SPDX fingerprints."""
    if not text.strip():
        return [
            {
                "kind": "absence",
                "clause": (
                    "no license text at the recorded path; "
                    "distribution constraint cannot be read"
                ),
            }
        ]
    found: list[dict[str, str]] = []
    for kind, rx in COPYLEFT_CLAUSE_RES:
        m = rx.search(text)
        if m:
            clause = re.sub(r"\s+", " ", m.group(0)).strip()
            found.append({"kind": kind, "clause": clause[:500]})
    if found:
        return found
    lowered = text.lower()
    if (
        "all rights reserved" in lowered
        and "permission is hereby granted" not in lowered
    ):
        return [
            {
                "kind": "proprietary-reservation",
                "clause": (
                    "text reserves rights and grants no redistribution permission"
                ),
            }
        ]
    snippet = re.sub(r"\s+", " ", text.strip())[:280]
    return [
        {
            "kind": "unmatched-obligation",
            "clause": (
                "no well-known copyleft/share-alike sentence matched; snippet="
                + snippet
            ),
        }
    ]


def clause_readings(
    components: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if components is None:
        components = automated_inventory()["components"]
    out: list[dict[str, Any]] = []
    for comp in components:
        if not comp.get("escalates_to_probe2"):
            continue
        path, text = license_bytes_for(comp)
        clauses = extract_clauses(text)
        out.append(
            {
                "component_id": comp["id"],
                "method": "clause-extraction",
                "license_path": path,
                "text_bytes": len(text.encode("utf-8")) if text else 0,
                "clauses": clauses,
                "automated_spdx_ignored": True,
                "automated_family_at_escalation": comp["automated_family"],
            }
        )
    return out


def mit_control_ok(inv: dict[str, Any] | None = None) -> dict[str, Any]:
    inv = inv or automated_inventory()
    mit = next(
        c for c in inv["components"] if c["id"] == "control:known-unambiguous-mit"
    )
    bad = next(c for c in inv["components"] if c["id"] == "control:not-a-license")
    ok = (
        mit["automated_spdx"] == "MIT"
        and mit["automated_family"] == "permissive"
        and "mit-fingerprint" in mit["evidence_string"]
        and bad["automated_spdx"] != "MIT"
        and bad["automated_family"] != "permissive"
    )
    return {
        "ok": ok,
        "mit": {
            "spdx": mit["automated_spdx"],
            "family": mit["automated_family"],
            "evidence": mit["evidence_string"],
        },
        "not_a_license": {
            "spdx": bad["automated_spdx"],
            "family": bad["automated_family"],
            "evidence": bad["evidence_string"],
        },
    }


def _has_entire_work(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    blob = " ".join(c["clause"].lower() for c in row.get("clauses") or [])
    return "entire work" in blob and "as a whole" in blob


def gpl_clause_ok(readings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    readings = readings if readings is not None else clause_readings()
    gpl = next((r for r in readings if r["component_id"] == "control:known-gpl3"), None)
    mis = next(
        (
            r
            for r in readings
            if r["component_id"] == "control:mislabeled-mit-metadata-gpl-text"
        ),
        None,
    )
    return {
        "ok": _has_entire_work(gpl) and _has_entire_work(mis),
        "gpl_present": gpl is not None,
        "mislabeled_present": mis is not None,
        "gpl_has_entire_work": _has_entire_work(gpl),
        "mislabeled_has_entire_work": _has_entire_work(mis),
        "gpl_method": None if gpl is None else gpl.get("method"),
    }
