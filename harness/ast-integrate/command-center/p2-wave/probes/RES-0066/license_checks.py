#!/usr/bin/env python3
"""Shared license-file checks: content must be the file, not the SPDX classifier."""
from __future__ import annotations

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "research" / "RES-0066.json"
SENTINEL = (
    "SUCCESS:RES-0066 in the receipt AND per-project LICENSE file contents "
    "(read, not classified) plus a copy-versus-reimplement verdict"
)
REQUIRED_IDS = {"langgraph", "microsoft-autogen", "ag2", "crewai"}
SPDX_ONLY = {"MIT", "Apache-2.0", "CC-BY-4.0", "CC-BY-4.0", "NOASSERTION"}


def load_art() -> dict:
    return json.loads(ART.read_text(encoding="utf-8"))


def errors_for(doc: dict) -> list[str]:
    err: list[str] = []
    blob = json.dumps(doc, sort_keys=True)
    if SENTINEL not in blob:
        err.append("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        err.append(f"self-declared:{st}")
    if doc.get("unit_id") != "RES-0066":
        err.append("unit_id")
    projects = {p.get("id"): p for p in (doc.get("projects") or []) if isinstance(p, dict)}
    missing = REQUIRED_IDS - set(projects)
    if missing:
        err.append(f"projects-missing:{sorted(missing)}")
    for pid, proj in projects.items():
        if pid not in REQUIRED_IDS:
            continue
        spdx = str(proj.get("github_api_spdx") or "").strip()
        files = [f for f in (proj.get("license_files") or []) if isinstance(f, dict)]
        if not files:
            err.append(f"{pid}:no-license-files")
            continue
        if not spdx:
            err.append(f"{pid}:classifier-spdx-unrecorded")
        for lf in files:
            body = str(lf.get("content") or "")
            path = str(lf.get("path_in_repo") or "?")
            if len(body.strip()) < 200:
                err.append(f"{pid}:{path}:body-too-short")
            stripped = body.strip()
            if stripped in SPDX_ONLY or stripped == spdx:
                err.append(f"{pid}:{path}:classifier-used-as-body")
            if not lf.get("sha256") or not lf.get("permalink"):
                err.append(f"{pid}:{path}:missing-lineage")
            cap = lf.get("capture_path")
            if cap:
                p = REPO / str(cap)
                if not p.is_file():
                    err.append(f"{pid}:{path}:capture-missing")
                elif p.read_text(encoding="utf-8") != body:
                    err.append(f"{pid}:{path}:content-ne-capture")
    auto = projects.get("microsoft-autogen") or {}
    auto_files = {f.get("path_in_repo"): f for f in (auto.get("license_files") or [])}
    if "LICENSE" not in auto_files or "LICENSE-CODE" not in auto_files:
        err.append("autogen:need-LICENSE-and-LICENSE-CODE")
    else:
        lic = auto_files["LICENSE"]["content"]
        code = auto_files["LICENSE-CODE"]["content"]
        if "Creative Commons" not in lic and "Attribution 4.0" not in lic:
            err.append("autogen:LICENSE-not-cc-by-text")
        if "Permission is hereby granted" not in code:
            err.append("autogen:LICENSE-CODE-not-mit-grant")
        if auto.get("github_api_spdx") not in {"CC-BY-4.0", "CC-BY-4.0"}:
            err.append(f"autogen:expected-classifier-CC-BY-4.0 got {auto.get('github_api_spdx')}")
        if lic.strip() == code.strip():
            err.append("autogen:LICENSE-files-identical")
    for pid, needle, label in (
        ("langgraph", "Permission is hereby granted", "mit-grant"),
        ("ag2", "Apache License", "apache-text"),
        ("crewai", "Permission is hereby granted", "mit-grant"),
    ):
        body = (((projects.get(pid) or {}).get("license_files") or [{}])[0].get("content") or "")
        if needle not in body:
            err.append(f"{pid}:LICENSE-missing-{label}")
    cvr = doc.get("copy_versus_reimplement") or {}
    if str(cvr.get("verdict") or "").upper() != "REIMPLEMENT":
        err.append("copy-versus-reimplement-verdict")
    if cvr.get("any_mechanism_requires_copying_code") is not False:
        err.append("copy-versus-reimplement-requires-copy")
    return err


def classifier_only_mutant(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    for proj in mutant.get("projects") or []:
        spdx = str(proj.get("github_api_spdx") or "NOASSERTION")
        for lf in proj.get("license_files") or []:
            lf["content"] = spdx
            lf["first_line"] = spdx
    return mutant
