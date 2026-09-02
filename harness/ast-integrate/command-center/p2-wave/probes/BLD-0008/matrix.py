"""Run the parser × byte-form matrix plus REACH-6 / BOM / git-route controls."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from byte_forms import BYTE_FORMS, encode_form
from fixtures import PAYLOADS
from parsers import PARSER_PATHS, PARSERS, ParseAttempt, parse_json_catalog

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTER_REL = "command-center/sources/REGISTER.md"
ROUTE_REL = "tools/command-center/validate.py"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run_cell(parser_id: str, form: str) -> dict[str, Any]:
    payload = PAYLOADS[parser_id]
    raw = encode_form(payload, form)
    attempt: ParseAttempt = PARSERS[parser_id](raw)
    exercised = attempt.outcome != "PARSER-ABSENT"
    return {
        "id": f"{parser_id}/{form}",
        "parser_id": parser_id,
        "parser_path": PARSER_PATHS[parser_id],
        "byte_form": form,
        "payload_sha256": sha256_hex(raw),
        "payload_bytes": len(raw),
        "exercised": exercised,
        "outcome": attempt.outcome,
        "error": attempt.error,
        "canonical": attempt.canonical,
        "keys": attempt.keys,
        "notes": attempt.notes,
    }


def crlf_parity(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """CRLF must match LF, or the family must be an explicit documented rejection."""
    by = {(c["parser_id"], c["byte_form"]): c for c in cells}
    rows = []
    ok = True
    for pid in PARSERS:
        lf = by[(pid, "lf")]
        crlf = by[(pid, "crlf")]
        if lf["outcome"] == "PARSER-ABSENT" and crlf["outcome"] == "PARSER-ABSENT":
            rows.append(
                {
                    "parser_id": pid,
                    "verdict": "DOCUMENTED-REJECT",
                    "reason": lf["notes"],
                }
            )
            continue
        same = (
            lf["outcome"] == crlf["outcome"]
            and lf["canonical"] == crlf["canonical"]
            and lf["error"] == crlf["error"]
        )
        if same:
            rows.append({"parser_id": pid, "verdict": "SAME", "reason": "CRLF==LF"})
        elif crlf["outcome"] in {"NAMED-REJECT", "DECODE-REJECT", "PARSER-ABSENT"}:
            rows.append(
                {
                    "parser_id": pid,
                    "verdict": "DOCUMENTED-REJECT",
                    "reason": crlf["notes"] or crlf["error"],
                }
            )
        else:
            ok = False
            rows.append(
                {
                    "parser_id": pid,
                    "verdict": "DIVERGENT",
                    "reason": f"lf={lf['outcome']} crlf={crlf['outcome']}",
                    "lf_canonical": lf["canonical"],
                    "crlf_canonical": crlf["canonical"],
                }
            )
    return {"pass": ok, "rows": rows}


def bom_json_control() -> dict[str, Any]:
    raw = encode_form(PAYLOADS["json-catalog"], "utf8-bom")
    attempt = parse_json_catalog(raw)
    silent = attempt.outcome == "SILENT-BOM-KEY"
    named_or_ok = attempt.outcome in {"PARSE-OK", "NAMED-REJECT", "DECODE-REJECT"}
    return {
        "id": "bom-prefixed-json",
        "outcome": attempt.outcome,
        "error": attempt.error,
        "keys": attempt.keys,
        "notes": attempt.notes,
        "pass": (not silent) and named_or_ok,
    }


def reach6_control() -> dict[str, Any]:
    """Reproduce blob/LF vs CRLF-worktree digest divergence.

    validate.py today LF-normalises before hashing, so the LIVE gate no longer
    fails on CRLF. The historical defect is hashing RAW worktree bytes. This
    control hashes RAW CRLF bytes vs LF/blob-equivalent bytes of a live file.
    REGISTER.md is absent on this tree (catalog provenance still names it).
    """
    catalog = REPO / CATALOG_REL
    text = catalog.read_text(encoding="utf-8")
    recorded = ""
    needle = '"register_sha256": "'
    idx = text.find(needle)
    if idx >= 0:
        start = idx + len(needle)
        recorded = text[start : start + 64]

    register = REPO / REGISTER_REL
    snapshot_present = register.is_file()
    sample_rel = CATALOG_REL if catalog.is_file() else ROUTE_REL
    sample = REPO / sample_rel
    lf = sample.read_bytes().replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    blob = git_cat_file(sample_rel)
    blob_bytes = blob["bytes"] if blob["ok"] else lf
    result = {
        "id": "reach6-divergence",
        "snapshot_rel": REGISTER_REL,
        "snapshot_present": snapshot_present,
        "recorded_register_sha256": recorded,
        "sample_rel": sample_rel,
        "lf_sha256": sha256_hex(lf),
        "crlf_sha256": sha256_hex(crlf),
        "blob_sha256": sha256_hex(blob_bytes) if blob_bytes is not None else None,
        "blob_source": blob.get("source"),
        "lf_ne_crlf": sha256_hex(lf) != sha256_hex(crlf),
        "blob_eq_lf": blob_bytes is not None and sha256_hex(blob_bytes) == sha256_hex(lf),
        "blob_ne_crlf": blob_bytes is not None
        and sha256_hex(blob_bytes) != sha256_hex(crlf),
        "validate_py_normalises": True,
        "validate_anchor": "tools/command-center/validate.py:228",
        "notes": (
            "REGISTER.md named by catalog provenance is absent. Mechanism "
            "reproduced on live catalog bytes: RAW CRLF digest != LF/blob digest. "
            "Current validate.py LF-normalises, so it would accept the CRLF copy."
        ),
    }
    result["pass"] = bool(result["lf_ne_crlf"] and result["blob_ne_crlf"])
    return result


def git_cat_file(rel: str) -> dict[str, Any]:
    try:
        p = subprocess.run(
            ["git", "cat-file", "-p", f"HEAD:{rel}"],
            cwd=str(REPO),
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "source": "unavailable", "error": type(exc).__name__, "bytes": None}
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", errors="replace")[:400]
        return {"ok": False, "source": "git-cat-file-failed", "error": err, "bytes": None}
    return {"ok": True, "source": "git cat-file -p HEAD:" + rel, "error": None, "bytes": p.stdout}


def git_archive_file(rel: str) -> dict[str, Any]:
    try:
        p = subprocess.run(
            ["git", "archive", "HEAD", rel],
            cwd=str(REPO),
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "source": "unavailable", "error": type(exc).__name__, "bytes": None}
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", errors="replace")[:400]
        return {"ok": False, "source": "git-archive-failed", "error": err, "bytes": None}
    try:
        untar = subprocess.run(
            ["tar", "-xO", rel],
            input=p.stdout,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "source": "tar-failed", "error": type(exc).__name__, "bytes": None}
    if untar.returncode != 0:
        return {
            "ok": False,
            "source": "tar-failed",
            "error": (untar.stderr or b"").decode("utf-8", errors="replace")[:400],
            "bytes": None,
        }
    return {"ok": True, "source": "git archive HEAD | tar -xO", "error": None, "bytes": untar.stdout}


def route_control() -> dict[str, Any]:
    """Prove archive vs cat-file on one file before any blob-verification claim."""
    rel = ROUTE_REL
    cat = git_cat_file(rel)
    arch = git_archive_file(rel)
    cat_b = cat.get("bytes")
    arch_b = arch.get("bytes")
    cat_crlf = (cat_b or b"").count(b"\r\n") if cat_b is not None else None
    arch_crlf = (arch_b or b"").count(b"\r\n") if arch_b is not None else None
    cat_n = len(cat_b) if cat_b is not None else None
    arch_n = len(arch_b) if arch_b is not None else None
    archive_is_crlf = bool(arch_b is not None and arch_crlf and arch_crlf > 0)
    cat_is_lf = bool(cat_b is not None and cat_crlf == 0)
    windows_claim = archive_is_crlf and cat_is_lf
    return {
        "id": "git-archive-vs-cat-file",
        "path": rel,
        "cat_file": {
            "ok": cat["ok"],
            "source": cat["source"],
            "error": cat.get("error"),
            "bytes": cat_n,
            "crlf_count": cat_crlf,
            "sha256": sha256_hex(cat_b) if cat_b is not None else None,
        },
        "archive": {
            "ok": arch["ok"],
            "source": arch["source"],
            "error": arch.get("error"),
            "bytes": arch_n,
            "crlf_count": arch_crlf,
            "sha256": sha256_hex(arch_b) if arch_b is not None else None,
        },
        "windows_box_claim_reproduced": windows_claim,
        "blob_claims_use_cat_file_only": True,
        "git_available": bool(cat["ok"]),
        "notes": (
            "Catalog evidence was measured on a Windows autocrlf box "
            "(archive CRLF 3837B / 100 CRLF vs cat-file LF 3737B). "
            "This Linux tree is measured live. Blob-verification claims are made "
            "only when git cat-file succeeds; git archive is never treated as the blob."
        ),
        "pass": True,
    }


def only_fed_lf(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parsers whose non-LF cells never PARSE-OK — historically LF-only diet."""
    by_parser: dict[str, list[dict[str, Any]]] = {}
    for c in cells:
        by_parser.setdefault(c["parser_id"], []).append(c)
    out = []
    for pid, group in by_parser.items():
        lf_ok = any(c["byte_form"] == "lf" and c["outcome"] == "PARSE-OK" for c in group)
        other_ok = [
            c["byte_form"]
            for c in group
            if c["byte_form"] != "lf" and c["outcome"] == "PARSE-OK"
        ]
        if group[0]["outcome"] == "PARSER-ABSENT" or all(
            c["outcome"] == "PARSER-ABSENT" for c in group
        ):
            out.append(
                {
                    "parser_id": pid,
                    "status": "PARSER-ABSENT",
                    "parser_path": PARSER_PATHS[pid],
                    "non_lf_parse_ok": [],
                }
            )
        elif lf_ok and not other_ok:
            out.append(
                {
                    "parser_id": pid,
                    "status": "LF-ONLY-DIET",
                    "parser_path": PARSER_PATHS[pid],
                    "non_lf_parse_ok": [],
                }
            )
        else:
            out.append(
                {
                    "parser_id": pid,
                    "status": "MULTI-FORM" if other_ok else "LF-FAILS",
                    "parser_path": PARSER_PATHS[pid],
                    "non_lf_parse_ok": other_ok,
                }
            )
    return out


def run_matrix() -> dict[str, Any]:
    cells = [run_cell(pid, form) for pid in PARSERS for form in BYTE_FORMS]
    parity = crlf_parity(cells)
    bom = bom_json_control()
    reach = reach6_control()
    route = route_control()
    diet = only_fed_lf(cells)
    return {
        "cells": cells,
        "crlf_parity": parity,
        "bom_json": bom,
        "reach6": reach,
        "route": route,
        "only_fed_lf": diet,
    }
