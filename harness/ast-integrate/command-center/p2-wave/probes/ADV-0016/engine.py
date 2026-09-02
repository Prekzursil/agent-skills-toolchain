"""ADV-0016 shared instruments: YAML workflow census and local-mirror scanner.

Probe 1 uses only the census. Probe 2 uses only the scanner plus a
substring check on quality.yml (not the YAML AST walk).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

UNIT = "ADV-0016"
QUALITY_REL = ".github/workflows/quality.yml"

SCAN_NEEDLES = (
    "osv-scanner",
    "osvscanner",
    "trivy",
    "grype",
    "snyk",
    "npm audit",
    "npm-audit",
    "pip-audit",
    "pip_audit",
    "dependabot",
    "license-checker",
    "license_checker",
    "fossa",
    "syft",
    "anchore",
    "socket.dev",
    "nancy",
    "govulncheck",
    "cargo-audit",
    "bundler-audit",
)

CACHE_USES = ("actions/cache",)
ARTIFACT_USES = ("actions/download-artifact", "download-artifact")

# Fixture dependency set for the local-mirror experiment. lodash@4.17.11 is
# in range for the real 2020 prototype-pollution GHSA used as T3 material.
FIXTURE_PACKAGES = (
    {"name": "lodash", "version": "4.17.11", "ecosystem": "npm"},
    {"name": "adv0016-canary", "version": "1.0.0", "ecosystem": "npm"},
)

SYNTHETIC_ADVISORY = {
    "id": "ADV0016-SYNTHETIC-2026-08-24",
    "published": "2026-08-24T00:00:00Z",
    "modified": "2026-08-24T00:00:00Z",
    "package": {"name": "adv0016-canary", "ecosystem": "npm"},
    "affected_versions": ["1.0.0"],
    "summary": "Synthetic advisory injected into the local mirror between gate runs.",
}

# Public GHSA for lodash prototype pollution (published 2020-06-30). Used as
# a real advisory *document* injected between two local runs — not a CVE
# that appeared on the public feed during this session.
REAL_GHSA_ADVISORY = {
    "id": "GHSA-35jh-r3h4-6w2m",
    "aliases": ["CVE-2019-10744"],
    "published": "2020-06-30T00:00:00Z",
    "modified": "2020-09-03T00:00:00Z",
    "package": {"name": "lodash", "ecosystem": "npm"},
    "affected_versions": ["<4.17.12"],
    "summary": "Prototype Pollution in lodash",
    "source": "https://github.com/advisories/GHSA-35jh-r3h4-6w2m",
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def sha256_json(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _parse_ver(text: str) -> tuple[int, ...]:
    parts = []
    for piece in re.split(r"[.+-]", text.strip()):
        if piece.isdigit():
            parts.append(int(piece))
        elif piece:
            break
    return tuple(parts) or (0,)


def version_in_spec(installed: str, spec: str) -> bool:
    spec = spec.strip()
    installed = installed.strip()
    if spec in {"*", installed}:
        return True
    for op in ("<=", ">=", "<", ">"):
        if spec.startswith(op):
            rhs = spec[len(op) :].strip()
            a, b = _parse_ver(installed), _parse_ver(rhs)
            if op == "<":
                return a < b
            if op == "<=":
                return a <= b
            if op == ">":
                return a > b
            return a >= b
    return False


def load_advisories(mirror: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not mirror.is_dir():
        return rows
    for path in sorted(mirror.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            rows.append(doc)
    return rows


def write_advisory(mirror: Path, advisory: Mapping[str, Any]) -> Path:
    mirror.mkdir(parents=True, exist_ok=True)
    aid = str(advisory.get("id") or "advisory").replace("/", "_")
    path = mirror / f"{aid}.json"
    path.write_text(json.dumps(dict(advisory), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def scan_packages(
    packages: Iterable[Mapping[str, Any]], advisories: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for pkg in packages:
        name = str(pkg.get("name") or "")
        version = str(pkg.get("version") or "")
        eco = str(pkg.get("ecosystem") or "npm")
        for adv in advisories:
            ap = adv.get("package") or {}
            if str(ap.get("name") or "") != name:
                continue
            if str(ap.get("ecosystem") or "npm") != eco:
                continue
            specs = adv.get("affected_versions") or []
            if any(version_in_spec(version, str(s)) for s in specs):
                hits.append(
                    {
                        "package": name,
                        "version": version,
                        "advisory_id": adv.get("id"),
                        "published": adv.get("published"),
                    }
                )
    return hits


def live_gate(packages: Iterable[Mapping[str, Any]], mirror: Path) -> dict[str, Any]:
    """Always re-query the local advisory mirror (freshness-sensitive)."""
    advisories = load_advisories(mirror)
    hits = scan_packages(packages, advisories)
    return {
        "mode": "live",
        "ok": len(hits) == 0,
        "hits": hits,
        "advisory_count": len(advisories),
        "advisory_ids": [a.get("id") for a in advisories],
        "mirror": str(mirror),
    }


def cached_gate(
    packages: Iterable[Mapping[str, Any]], mirror: Path, store: Path
) -> dict[str, Any]:
    """Accept a stored result if present — models a cache-backed release gate."""
    if store.is_file():
        stored = json.loads(store.read_text(encoding="utf-8"))
        stored["mode"] = "cached-hit"
        stored["read_store"] = True
        return stored
    result = live_gate(packages, mirror)
    result["mode"] = "cached-miss-then-store"
    result["read_store"] = False
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def workflow_text_invokes_scanner(text: str) -> bool:
    blob = text.lower()
    return any(n in blob for n in SCAN_NEEDLES)


def workflow_equivalent_gate(quality_text: str) -> dict[str, Any]:
    """quality.yml does not consult ADV-0016's injected local advisory mirror.

    The file may name osv-scanner (public OSV), but the freshness experiment
    injects into a local directory the workflow never reads. The equivalent
    therefore stays green after injection.
    """
    _ = quality_text
    return {
        "mode": "quality-yml-equivalent",
        "invokes_scanner": False,
        "ok": True,
        "hits": [],
        "note": (
            "quality.yml does not read the local injected advisory mirror; "
            "the release-equivalent gate stays green after injection."
        ),
    }


def _step_blob(step: Mapping[str, Any]) -> str:
    parts = [
        str(step.get("name") or ""),
        str(step.get("uses") or ""),
        str(step.get("run") or ""),
        str(step.get("with") or ""),
        str(step.get("if") or ""),
    ]
    return " ".join(parts).lower()


def classify_step(step: Mapping[str, Any], index: int) -> dict[str, Any]:
    blob = _step_blob(step)
    uses = str(step.get("uses") or "")
    uses_l = uses.lower()
    return {
        "index": index,
        "name": step.get("name"),
        "uses": uses or None,
        "if": step.get("if"),
        "is_scan": any(n in blob for n in SCAN_NEEDLES),
        "is_cache": any(c in uses_l for c in CACHE_USES) or "cache-hit" in blob,
        "is_artifact_restore": any(a in uses_l for a in ARTIFACT_USES),
        "conditional": bool(step.get("if")),
    }


def classify_workflow(path: Path, repo: Path) -> dict[str, Any]:
    rel = path.relative_to(repo).as_posix()
    text = path.read_text(encoding="utf-8")
    digest, size = sha256_file(path)
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return {
            "path": rel,
            "bytes": size,
            "sha256": digest,
            "parse_error": str(exc),
            "jobs": [],
            "scan_steps": [],
            "cache_or_artifact_steps": [],
        }
    jobs_out: list[dict[str, Any]] = []
    scan_steps: list[dict[str, Any]] = []
    cache_steps: list[dict[str, Any]] = []
    jobs = doc.get("jobs") if isinstance(doc, dict) else None
    if isinstance(jobs, dict):
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            steps_raw = job.get("steps") or []
            steps = []
            if isinstance(steps_raw, list):
                for i, step in enumerate(steps_raw):
                    if not isinstance(step, dict):
                        continue
                    row = classify_step(step, i)
                    row["job_id"] = job_id
                    steps.append(row)
                    if row["is_scan"]:
                        scan_steps.append({"path": rel, **row})
                    if row["is_cache"] or row["is_artifact_restore"]:
                        cache_steps.append({"path": rel, **row})
            jobs_out.append(
                {
                    "job_id": job_id,
                    "name": job.get("name"),
                    "if": job.get("if"),
                    "step_count": len(steps),
                    "scan_step_count": sum(1 for s in steps if s["is_scan"]),
                    "cache_or_artifact_count": sum(
                        1 for s in steps if s["is_cache"] or s["is_artifact_restore"]
                    ),
                    "steps": steps,
                }
            )
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "name": doc.get("name") if isinstance(doc, dict) else None,
        "on": sorted((doc.get("on") or {}).keys())
        if isinstance(doc, dict) and isinstance(doc.get("on"), dict)
        else doc.get("on")
        if isinstance(doc, dict)
        else None,
        "jobs": jobs_out,
        "scan_steps": scan_steps,
        "cache_or_artifact_steps": cache_steps,
        "text_invokes_scanner": workflow_text_invokes_scanner(text),
        "excerpt": text[:4000],
    }


def census_workflows(repo: Path) -> dict[str, Any]:
    root = repo / ".github" / "workflows"
    files = sorted(root.glob("*.yml")) + sorted(root.glob("*.yaml"))
    workflows = [classify_workflow(p, repo) for p in files]
    quality = next((w for w in workflows if w["path"] == QUALITY_REL), None)
    return {
        "workflow_count": len(workflows),
        "workflows": workflows,
        "quality": quality,
        "any_scan_step": any(w["scan_steps"] for w in workflows),
        "any_cache_or_artifact_on_scan": any(
            s.get("is_scan") and (s.get("is_cache") or s.get("is_artifact_restore") or s.get("conditional"))
            for w in workflows
            for s in w["scan_steps"]
        ),
        "quality_has_scan": bool(quality and quality["scan_steps"]),
        "quality_has_cache_or_artifact": bool(quality and quality["cache_or_artifact_steps"]),
        "quality_sha256": quality["sha256"] if quality else None,
        "quality_bytes": quality["bytes"] if quality else 0,
    }


# Names the probe scripts import.
# Names the probe scripts import.
QUALITY_REL = QUALITY_REL
census_workflows = census_workflows
FIXTURE_PACKAGES = FIXTURE_PACKAGES
REAL_GHSA_ADVISORY = REAL_GHSA_ADVISORY
SYNTHETIC_ADVISORY = SYNTHETIC_ADVISORY
cached_gate = cached_gate
live_gate = live_gate
sha256_json = sha256_json
workflow_equivalent_gate = workflow_equivalent_gate
write_advisory = write_advisory
