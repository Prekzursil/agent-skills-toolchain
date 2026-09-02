#!/usr/bin/env python3
"""Shared honesty checks for RES-0129 probes (no network)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = (
    REPO
    / "command-center"
    / "research"
    / "marketplace-ecosystem"
    / "RES-0129-cross-client-manifest-compat-matrix.json"
)
SCHEMA = REPO / "command-center" / "schema" / "compatibility-matrix.schema.json"
SENTINEL = "SUCCESS:RES-0129"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT", "PARTIAL"})

RENDER = {
    "SUPPORTED": {
        "token": "SUPPORTED",
        "glyph": "●",
        "css_class": "matrix-cell-supported",
        "color_role": "pass",
        "is_pass": True,
        "machine_status": "SUPPORTED",
    },
    "FAILED": {
        "token": "FAILED",
        "glyph": "✖",
        "css_class": "matrix-cell-failed",
        "color_role": "fail",
        "is_pass": False,
        "machine_status": "FAILED",
    },
    "INFERRED": {
        "token": "INFERRED",
        "glyph": "◇",
        "css_class": "matrix-cell-inferred",
        "color_role": "inferred",
        "is_pass": False,
        "machine_status": "INFERRED",
    },
    "NOT-CHECKED": {
        "token": "NOT-CHECKED",
        "glyph": "○",
        "css_class": "matrix-cell-not-checked",
        "color_role": "unknown",
        "is_pass": False,
        "machine_status": "NOT-CHECKED",
    },
    "NOT-APPLICABLE": {
        "token": "NOT-APPLICABLE",
        "glyph": "–",
        "css_class": "matrix-cell-na",
        "color_role": "na",
        "is_pass": False,
        "machine_status": "NOT-APPLICABLE",
    },
    "UNSUPPORTED": {
        "token": "UNSUPPORTED",
        "glyph": "■",
        "css_class": "matrix-cell-unsupported",
        "color_role": "out",
        "is_pass": False,
        "machine_status": "UNSUPPORTED",
    },
}

CLIENTS = [
    "claude-code",
    "codex-cli",
    "gemini-cli",
    "cursor",
    "continue-dev",
    "copilot-extensions",
]
CONCEPTS = [
    "name",
    "version",
    "entrypoint",
    "permissions",
    "tool_declarations",
    "hooks",
    "compatibility_ranges",
]


def load_art() -> dict:
    if not ART.is_file() or ART.stat().st_size <= 0:
        raise RuntimeError("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        raise RuntimeError("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        raise RuntimeError(f"self-declared {st}")
    if doc.get("unit_id") != "RES-0129":
        raise RuntimeError("unit_id mismatch")
    return doc


def validate_schema(doc: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(doc)


def cell_map(doc: dict) -> dict[tuple[str, str], dict]:
    out = {}
    for cell in doc.get("cells") or []:
        ax = cell.get("axes") or {}
        out[(ax.get("client"), ax.get("package_version"))] = cell
    return out


def errors_for(doc: dict, extracted: dict[str, dict] | None = None) -> list[str]:
    from extract import CONCEPTS as EX_CONCEPTS  # noqa: PLC0415
    from extract import extract_all  # noqa: PLC0415

    errs: list[str] = []
    if SENTINEL not in json.dumps(doc):
        # sentinel is also in answer text; check file-level via reload
        pass
    try:
        validate_schema(doc)
    except jsonschema.ValidationError as exc:
        errs.append(f"schema:{exc.message}")
    cells = [c for c in (doc.get("cells") or []) if isinstance(c, dict)]
    if len(cells) != 42:
        errs.append(f"cell-count:{len(cells)}!=42")
    by: dict[str, list[str]] = {c: [] for c in CLIENTS}
    for cell in cells:
        ax = cell.get("axes") or {}
        client = ax.get("client")
        concept = ax.get("package_version")
        st = cell.get("status")
        if client in by:
            by[client].append(st)
        if st == "SUPPORTED":
            if not (cell.get("evidence") or []):
                errs.append(f"{client}/{concept}:supported-without-evidence")
            if cell.get("is_pass") is not True:
                errs.append(f"{client}/{concept}:supported-not-pass")
        if st in {"UNSUPPORTED", "NOT-CHECKED", "INFERRED", "NOT-APPLICABLE"}:
            if cell.get("is_pass") is True:
                errs.append(f"{client}/{concept}:non-supported-pass")
        render = cell.get("render") or {}
        if render.get("machine_status") != st:
            errs.append(f"{client}/{concept}:render-status-drift")
        if st == "NOT-CHECKED" and render.get("token") in {
            "PASS",
            "YES",
            "RUN",
            "GREEN",
            "CHECKED",
            "OK",
            "TRUE",
            "SUPPORTED",
        }:
            errs.append(f"{client}/{concept}:not-checked-pass-token")
    for client, statuses in by.items():
        if "UNSUPPORTED" not in statuses:
            errs.append(f"{client}:all-green-no-unsupported")
    live = extracted if extracted is not None else extract_all()
    cmap = cell_map(doc)
    for client in CLIENTS:
        row = live.get(client) or {}
        live_st = row.get("statuses") or {}
        for concept in EX_CONCEPTS:
            cell = cmap.get((client, concept))
            if not cell:
                errs.append(f"missing-cell:{client}/{concept}")
                continue
            if cell.get("status") != live_st.get(concept):
                errs.append(
                    f"drift:{client}/{concept} art={cell.get('status')} live={live_st.get(concept)}"
                )
    claims = [c for c in (doc.get("claims") or []) if isinstance(c, dict)]
    measured = [c for c in claims if c.get("cited_as_measured_fact") is True]
    if len(measured) < 3:
        errs.append(f"too-few-measured-claims:{len(measured)}")
    for claim in measured:
        rails = [r for r in (claim.get("rails") or []) if isinstance(r, dict)]
        if len(rails) < 2:
            errs.append(f"{claim.get('id')}:single-rail")
            continue
        kinds = {str(r.get("kind") or "") for r in rails}
        if "structured-api-probe" not in kinds or "prose-source" not in kinds:
            errs.append(f"{claim.get('id')}:rails-not-dual-kind {kinds}")
        if len(kinds) < 2:
            errs.append(f"{claim.get('id')}:rails-same-kind")
        for r in rails:
            for field in ("permalink", "fetch_timestamp", "http_status", "sha256"):
                if r.get(field) in (None, ""):
                    errs.append(f"{claim.get('id')}:rail-missing-{field}")
            if int(r.get("http_status") or 0) != 200:
                errs.append(f"{claim.get('id')}:rail-http-{r.get('http_status')}")
            cap = r.get("capture_path")
            if cap:
                p = REPO / str(cap).replace("\\", "/")
                if not p.is_file():
                    errs.append(f"{claim.get('id')}:capture-missing")
    common = doc.get("largest_common_subset") or {}
    concepts = set(common.get("concepts") or [])
    if not concepts:
        errs.append("empty-common-subset")
    # Common subset must be intersection of SUPPORTED cells.
    supported: dict[str, set[str]] = {c: set() for c in CLIENTS}
    for cell in cells:
        ax = cell.get("axes") or {}
        if cell.get("status") == "SUPPORTED":
            supported.setdefault(ax.get("client"), set()).add(ax.get("package_version"))
    live_common = set.intersection(*supported.values()) if supported else set()
    if concepts != live_common:
        errs.append(f"common-subset-mismatch art={sorted(concepts)} live={sorted(live_common)}")
    return errs


def mention_mutant(doc: dict, mutated_statuses: dict[str, dict[str, str]]) -> dict:
    red = copy.deepcopy(doc)
    for cell in red.get("cells") or []:
        ax = cell.get("axes") or {}
        client = ax.get("client")
        concept = ax.get("package_version")
        st = (mutated_statuses.get(client) or {}).get(concept)
        if not st:
            continue
        cell["status"] = st
        cell["render"] = dict(RENDER[st])
        cell["is_pass"] = st == "SUPPORTED"
        if st == "SUPPORTED" and not cell.get("evidence"):
            cell["evidence"] = [{"note": "mention-mutant"}]
    return red
