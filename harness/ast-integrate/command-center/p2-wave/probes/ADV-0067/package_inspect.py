"""Inspect a fixture package into the score's published components."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TRIVIAL_ASSERT = re.compile(
    r"assert\s+(True|1|0\s*==\s*0|\"ok\"|'ok')\b", re.IGNORECASE
)
ANY_ASSERT = re.compile(r"\bassert\b")
HEADING = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
TOKEN = re.compile(r"[A-Za-z]{4,}")


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _readme_completeness(text: str) -> float:
    raw = text.encode("utf-8")
    byte_score = min(1.0, len(raw) / 800.0)
    heading_score = min(1.0, len(HEADING.findall(text)) / 5.0)
    return round(0.6 * byte_score + 0.4 * heading_score, 6)


def _doc_substance(text: str) -> dict[str, Any]:
    tokens = TOKEN.findall(text.lower())
    unique = sorted(set(tokens))
    return {
        "bytes": len(text.encode("utf-8")),
        "unique_tokens": len(unique),
        "token_count": len(tokens),
        "heading_count": len(HEADING.findall(text)),
    }


def _test_stats(test_dir: Path) -> dict[str, Any]:
    files = sorted(test_dir.glob("test_*.py")) if test_dir.is_dir() else []
    trivial = 0
    nontrivial = 0
    passed = 0
    total = 0
    for path in files:
        body = path.read_text(encoding="utf-8")
        asserts = ANY_ASSERT.findall(body)
        total += max(len(asserts), 1 if "def test_" in body else 0)
        for match in re.finditer(r"assert[^\n]+", body):
            if TRIVIAL_ASSERT.search(match.group(0)):
                trivial += 1
                passed += 1
            else:
                nontrivial += 1
                passed += 1
        if "def test_" in body and not asserts:
            passed += 1
    presence = 1.0 if files else 0.0
    pass_rate = 1.0 if total == 0 and presence else (passed / total if total else 0.0)
    if presence and total == 0:
        pass_rate = 1.0
        total = len(files)
        passed = len(files)
    return {
        "test_files": [p.name for p in files],
        "test_file_count": len(files),
        "test_presence": presence,
        "test_pass_rate": round(min(1.0, pass_rate), 6),
        "assert_total": total,
        "assert_trivial": trivial,
        "assert_nontrivial": nontrivial,
        "passed": passed,
    }


def _benchmarks(doc: Any) -> dict[str, Any]:
    if not isinstance(doc, dict):
        rows = doc if isinstance(doc, list) else []
    else:
        rows = doc.get("benchmarks") or doc.get("claims") or []
    declared = 0
    reproduced = 0
    names: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        declared += 1
        names.append(str(row.get("id") or row.get("name") or f"b{declared}"))
        result = row.get("result") or row.get("reproduction") or {}
        if isinstance(result, dict) and result.get("executed") and result.get("within_tolerance"):
            reproduced += 1
        elif row.get("reproduced") is True and row.get("executed") is True:
            reproduced += 1
    return {
        "declared_benchmarks": declared,
        "reproduced_benchmarks": reproduced,
        "names": names,
    }


def _conformance(root: Path, manifest: Any) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(cid: str, ok: bool, detail: str) -> None:
        checks.append({"id": cid, "pass": ok, "detail": detail})

    add(
        "manifest-name",
        isinstance(manifest, dict) and bool(str(manifest.get("name") or "").strip()),
        "manifest.json has a non-empty name",
    )
    entry = ""
    if isinstance(manifest, dict):
        entry = str(manifest.get("entrypoint") or manifest.get("main") or "")
    entry_path = (root / entry) if entry else None
    add(
        "entrypoint-exists",
        bool(entry_path and entry_path.is_file()),
        f"entrypoint {entry!r} exists as a file",
    )
    parsed_ok = True
    json_files = list(root.glob("*.json"))
    for path in json_files:
        if _load_json(path) is None:
            parsed_ok = False
            break
    add("json-files-parse", parsed_ok and bool(json_files), "top-level json files parse")
    passed = sum(1 for c in checks if c["pass"])
    return {
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "conformance_pass_rate": round(passed / len(checks), 6) if checks else 0.0,
    }


def inspect_package(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _load_json(root / "manifest.json") or {}
    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""
    tests = _test_stats(root / "tests")
    sbom_path = root / "sbom.json"
    prov_path = root / "provenance.json"
    adv_doc = _load_json(root / "advisories.json")
    if isinstance(adv_doc, dict):
        advisories = adv_doc.get("open") or adv_doc.get("advisories") or []
    elif isinstance(adv_doc, list):
        advisories = adv_doc
    else:
        advisories = [] if (root / "advisories.json").is_file() else ["UNDECLARED"]
    benches = _benchmarks(_load_json(root / "benchmarks.json"))
    conf = _conformance(root, manifest)
    src_files = list((root / "src").glob("*.py")) if (root / "src").is_dir() else []
    src_loc = 0
    for path in src_files:
        src_loc += len(
            [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.strip().startswith("#")]
        )
    downloads = 0
    if isinstance(manifest, dict):
        try:
            downloads = int(manifest.get("downloads") or manifest.get("popularity") or 0)
        except (TypeError, ValueError):
            downloads = 0
    doc = _doc_substance(readme)
    components = {
        "conformance_pass_rate": conf["conformance_pass_rate"],
        "test_presence": tests["test_presence"],
        "test_pass_rate": tests["test_pass_rate"],
        "documentation_completeness": _readme_completeness(readme),
        "sbom_present": 1.0 if sbom_path.is_file() else 0.0,
        "provenance_present": 1.0 if prov_path.is_file() else 0.0,
        "advisory_cleanliness": 1.0 if (root / "advisories.json").is_file() and len(advisories) == 0 else 0.0,
        "declared_benchmarks": benches["declared_benchmarks"],
        "downloads": downloads,
    }
    substance = {
        "assert_nontrivial": tests["assert_nontrivial"],
        "assert_trivial": tests["assert_trivial"],
        "unique_doc_tokens": doc["unique_tokens"],
        "doc_bytes": doc["bytes"],
        "reproduced_benchmarks": benches["reproduced_benchmarks"],
        "declared_benchmarks": benches["declared_benchmarks"],
        "src_loc": src_loc,
        "sbom_bytes": sbom_path.stat().st_size if sbom_path.is_file() else 0,
        "provenance_bytes": prov_path.stat().st_size if prov_path.is_file() else 0,
    }
    return {
        "root": str(root),
        "name": (manifest or {}).get("name"),
        "components": components,
        "substance": substance,
        "tests": tests,
        "conformance": conf,
        "benchmarks": benches,
        "documentation": doc,
        "downloads": downloads,
        "sbom_present": bool(sbom_path.is_file()),
        "provenance_present": bool(prov_path.is_file()),
        "open_advisories": advisories,
    }
