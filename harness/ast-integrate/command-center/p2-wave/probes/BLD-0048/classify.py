#!/usr/bin/env python3
"""Cross the BLD-0048 actor list against Phase 12 threat-model bytes.

A MODELED verdict needs a citation into model text on disk. Catalog prompts
are not models. B08/B10 rows without a runnable probe are named, not tests.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"

ACTORS: list[dict[str, Any]] = [
    {
        "id": "malicious-package-publisher",
        "name": "malicious package publisher",
        "own_fan_out": False,
        "phrases": [
            "malicious package publisher",
            "malicious package",
            "hostile publisher",
            "typosquat",
            "over-permissioned package",
        ],
    },
    {
        "id": "compromised-upstream-dependency",
        "name": "compromised upstream dependency",
        "own_fan_out": False,
        "phrases": [
            "compromised upstream dependency",
            "compromised upstream",
            "dependency confusion",
            "poisoned dependency",
            "typosquatted dependency",
        ],
    },
    {
        "id": "hostile-marketplace-mirror",
        "name": "hostile marketplace mirror",
        "own_fan_out": False,
        "phrases": [
            "hostile marketplace mirror",
            "hostile mirror",
            "mitm marketplace",
            "marketplace mitm",
            "tampered mirror",
        ],
    },
    {
        "id": "malicious-workflow-skill-contributor",
        "name": "malicious workflow / skill contributor",
        "own_fan_out": False,
        "phrases": [
            "malicious workflow",
            "malicious skill contributor",
            "hostile skill",
            "malicious contributor",
            "skill contributor",
        ],
    },
    {
        "id": "prompt-injecting-artifact-author",
        "name": "prompt-injecting artifact author",
        "own_fan_out": False,
        "phrases": [
            "prompt-injecting artifact author",
            "prompt-injecting",
            "prompt injection",
            "injecting artifact",
            "indirect prompt injection",
        ],
    },
    {
        "id": "compromised-misaligned-own-agent",
        "name": "compromised or misaligned agent inside our own fan-out",
        "own_fan_out": True,
        "phrases": [
            "compromised or misaligned agent",
            "misaligned agent inside",
            "own fan-out",
            "own fan out",
            "operator's own agent",
            "insider agent",
        ],
    },
    {
        "id": "curious-insider-reading-artifacts",
        "name": "curious insider reading artifacts",
        "own_fan_out": False,
        "phrases": [
            "curious insider",
            "insider reading artifacts",
            "insider reading",
            "curious operator",
        ],
    },
    {
        "id": "host-client-vendor",
        "name": "the host-client vendor itself",
        "own_fan_out": False,
        "phrases": [
            "host-client vendor",
            "host client vendor",
            "host-application vendor",
            "platform vendor itself",
            "the host-client vendor itself",
        ],
    },
    {
        "id": "local-malware-user-level",
        "name": "local malware with user-level file access",
        "own_fan_out": False,
        "phrases": [
            "local malware with user-level",
            "local malware",
            "user-level file access",
            "malware with user-level",
        ],
    },
    {
        "id": "stale-credential-thief",
        "name": "thief holding a stale credential",
        "own_fan_out": False,
        "phrases": [
            "thief holding a stale credential",
            "stale credential",
            "stolen token",
            "credential thief",
            "thief holding",
        ],
    },
]

OWN_FAN_OUT_ID = "compromised-misaligned-own-agent"

MODEL_GLOBS = (
    "command-center/adversarial/**/*.json",
    "command-center/adversarial/**/*.md",
    "command-center/phase12/**/*.json",
    "command-center/phase12/**/*.md",
    "command-center/threat-models/**/*.json",
    "command-center/threat-models/**/*.md",
)

SKIP_PY = frozenset({"emit.py", "classify.py", "write_receipts.py"})


def load_catalog(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    return json.loads((root / CATALOG_REL).read_text(encoding="utf-8"))


def units_of(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    rows = catalog.get("work_units") or catalog.get("units") or []
    return [u for u in rows if isinstance(u, dict)]


def phase12_model_units(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for u in units_of(catalog):
        if str(u.get("phase") or "") != "12":
            continue
        schema = str(u.get("output_schema") or "").replace("\\", "/").lower()
        title = str(u.get("title") or "").lower()
        if "threat-model" in schema or "threat_model" in schema:
            found.append(u)
        elif "threat model" in title or "stride threat" in title:
            found.append(u)
    return found


def hits_in(text: str, phrases: list[str]) -> list[str]:
    low = text.lower()
    return [p for p in phrases if p.lower() in low]


def citation(path: str, text: str, phrases: list[str]) -> dict[str, Any] | None:
    found = hits_in(text, phrases)
    if not found:
        return None
    needle = found[0].lower()
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line.lower():
            return {
                "path": path,
                "line": i,
                "snippet": line.strip()[:240],
                "phrase": found[0],
            }
    return {
        "path": path,
        "line": 1,
        "snippet": text[:200].replace("\n", " "),
        "phrase": found[0],
    }


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def load_phase12_models(
    repo: Path | None = None, catalog: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = repo or REPO
    cat = catalog if catalog is not None else load_catalog(root)
    docs: list[dict[str, Any]] = []
    searched: list[str] = []
    missing: list[str] = []
    present: list[str] = []
    for u in phase12_model_units(cat):
        rel = str(u.get("output_path") or "").replace("\\", "/")
        if not rel:
            continue
        searched.append(rel)
        p = root / rel
        if p.is_file() and p.stat().st_size > 0:
            present.append(rel)
            docs.append(
                {
                    "path": rel,
                    "text": _read(p),
                    "unit_id": u.get("id"),
                    "source": "phase12-artifact",
                }
            )
        else:
            missing.append(rel)
    glob_hits: list[str] = []
    for pattern in MODEL_GLOBS:
        for p in sorted(root.glob(pattern)):
            if not p.is_file() or p.stat().st_size <= 0:
                continue
            rel = p.relative_to(root).as_posix()
            glob_hits.append(rel)
            if rel in present:
                continue
            present.append(rel)
            docs.append(
                {
                    "path": rel,
                    "text": _read(p),
                    "unit_id": None,
                    "source": "glob",
                }
            )
    meta = {
        "phase12_model_unit_ids": [u.get("id") for u in phase12_model_units(cat)],
        "catalog_output_paths_searched": searched,
        "catalog_output_paths_missing": missing,
        "catalog_output_paths_present": present[:],
        "glob_patterns": list(MODEL_GLOBS),
        "glob_hits": glob_hits,
        "documents_loaded": len(docs),
        "note": (
            "MODELED cites bytes of a Phase 12 threat-model artifact. "
            "Catalog questions are work-unit prompts, not models. "
            "Phase 3 marketplace SECURITY.json is out of scope here."
        ),
    }
    return docs, meta


def _probe_py(root: Path, uid: str) -> list[str]:
    d = root / "command-center" / "p2-wave" / "probes" / uid
    if not d.is_dir():
        return []
    out: list[str] = []
    for p in sorted(d.rglob("*.py")):
        if p.name in SKIP_PY or p.name.startswith("_"):
            continue
        if p.name.startswith("probe") or p.name in {"detector.py", "run_probes.py"}:
            out.append(p.relative_to(root).as_posix())
    return out


def is_b10(u: dict[str, Any]) -> bool:
    return str(u.get("bucket") or "") == "B10"


def is_b08(u: dict[str, Any]) -> bool:
    if str(u.get("bucket") or "") == "B08":
        return True
    uid = str(u.get("id") or "")
    title = str(u.get("title") or "").lower()
    return uid.startswith("TST-") and ("mutat" in title or "abuse" in title)


def load_abuse_tests(
    repo: Path | None = None, catalog: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = repo or REPO
    cat = catalog if catalog is not None else load_catalog(root)
    tests: list[dict[str, Any]] = []
    n_b10 = n_b08 = n_exec = 0
    for u in units_of(cat):
        if is_b10(u):
            bucket = "B10"
            n_b10 += 1
        elif is_b08(u):
            bucket = "B08"
            n_b08 += 1
        else:
            continue
        schema = str(u.get("output_schema") or "").lower()
        if "threat-model" in schema:
            continue
        uid = str(u.get("id") or "")
        files = _probe_py(root, uid)
        title = str(u.get("title") or "")
        question = str(u.get("question_or_target") or "")
        tests.append(
            {
                "id": uid,
                "bucket": bucket,
                "title": title,
                "text": f"{title}\n{question}",
                "executable": bool(files),
                "probe_files": files,
            }
        )
        if files:
            n_exec += 1
    meta = {
        "b10_units_considered": n_b10,
        "b08_units_considered": n_b08,
        "tests_indexed": len(tests),
        "executable_on_this_tree": n_exec,
        "note": (
            "Executable means probe*.py or detector.py under "
            "command-center/p2-wave/probes/<id>/."
        ),
    }
    return tests, meta


def strip_actor_text(text: str, actor: dict[str, Any]) -> str:
    phrases = [p.lower() for p in actor["phrases"]]
    kept: list[str] = []
    for line in text.splitlines(keepends=True):
        low = line.lower()
        if any(p in low for p in phrases):
            continue
        kept.append(line)
    return "".join(kept)


def classify_actors(
    documents: list[dict[str, Any]],
    tests: list[dict[str, Any]] | None = None,
    searched_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    tests = tests or []
    searched_paths = searched_paths or [str(d.get("path") or "") for d in documents]
    rows: list[dict[str, Any]] = []
    for actor in ACTORS:
        model_cites: list[dict[str, Any]] = []
        for doc in documents:
            c = citation(
                str(doc.get("path") or "scratch"),
                str(doc.get("text") or ""),
                actor["phrases"],
            )
            if c:
                c["unit_id"] = doc.get("unit_id")
                c["source"] = doc.get("source")
                model_cites.append(c)
        exec_hits: list[dict[str, Any]] = []
        named_hits: list[dict[str, Any]] = []
        for t in tests:
            if not hits_in(str(t.get("text") or ""), actor["phrases"]):
                continue
            rec = {
                "id": t.get("id"),
                "bucket": t.get("bucket"),
                "executable": bool(t.get("executable")),
                "probe_files": t.get("probe_files") or [],
            }
            if t.get("executable"):
                exec_hits.append(rec)
            else:
                named_hits.append(rec)
        if model_cites and exec_hits:
            verdict = "MODELED"
        elif model_cites:
            verdict = "MODELED-BUT-UNTESTED"
        else:
            verdict = "UNMODELED"
        if verdict == "UNMODELED":
            evidence: dict[str, Any] = {
                "kind": "search-miss",
                "requirement": (
                    "UNMODELED is the search that failed to find a model, "
                    "not an assertion that none exists."
                ),
                "paths_searched": searched_paths,
                "documents_loaded": len(documents),
                "phrase_hits": [],
                "named_b08_b10_without_model": named_hits[:8],
            }
        else:
            evidence = {
                "kind": (
                    "model-citation"
                    if verdict == "MODELED"
                    else "model-without-executable-test"
                ),
                "citations": model_cites,
                "executable_abuse_tests": exec_hits,
                "catalog_named_b08_b10_not_executable": named_hits[:8],
            }
        rows.append(
            {
                "id": actor["id"],
                "name": actor["name"],
                "own_fan_out": bool(actor["own_fan_out"]),
                "verdict": verdict,
                "evidence": evidence,
            }
        )
    return rows


def live_matrix(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    cat = load_catalog(root)
    docs, model_meta = load_phase12_models(root, cat)
    tests, test_meta = load_abuse_tests(root, cat)
    searched = list(model_meta.get("catalog_output_paths_searched") or [])
    searched.extend(model_meta.get("glob_hits") or [])
    actors = classify_actors(docs, tests, searched_paths=searched)
    unmodeled = [a["id"] for a in actors if a["verdict"] == "UNMODELED"]
    modeled = [a["id"] for a in actors if a["verdict"] == "MODELED"]
    untested = [a["id"] for a in actors if a["verdict"] == "MODELED-BUT-UNTESTED"]
    own = [a for a in actors if a["own_fan_out"]]
    return {
        "actors": actors,
        "models_searched": model_meta,
        "abuse_tests_searched": test_meta,
        "counts": {
            "enumerated": len(actors),
            "MODELED": len(modeled),
            "MODELED-BUT-UNTESTED": len(untested),
            "UNMODELED": len(unmodeled),
        },
        "unmodeled_ids": unmodeled,
        "modeled_ids": modeled,
        "modeled_but_untested_ids": untested,
        "own_fan_out_in_actor_set": bool(own),
        "own_fan_out_ids": [a["id"] for a in own],
        "own_fan_out_modeled": any(a["verdict"] != "UNMODELED" for a in own),
    }


def modeled_ok(rows: list[dict[str, Any]]) -> bool:
    for a in rows:
        v = a.get("verdict")
        if v == "MODELED":
            tests = (a.get("evidence") or {}).get("executable_abuse_tests") or []
            if not tests:
                return False
        elif v not in {"MODELED-BUT-UNTESTED", "UNMODELED"}:
            return False
    return True


def map_reviewer_name(name: str) -> str | None:
    low = name.lower()
    for actor in ACTORS:
        if actor["id"] in low or actor["name"].lower() in low:
            return actor["id"]
        if hits_in(low, actor["phrases"]):
            return actor["id"]
    return None


def actor_by_id(aid: str) -> dict[str, Any]:
    for a in ACTORS:
        if a["id"] == aid:
            return a
    raise KeyError(aid)
