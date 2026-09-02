"""Load TEST-REGISTRY, CC-0014 mutation records, B08/Phase-10 inventory, SYN-0001.

Missing inputs are recorded ABSENT. A live mention is never upgraded to COVERED.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

TEST_REGISTRY = "command-center/TEST-REGISTRY.json"
CC0014 = "command-center/receipts/CC-0014.json"
SYN0001 = "command-center/synthesis/SYN-0001.root-cause-hierarchy.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
PHASE_GRAPH = "command-center/PHASE-GRAPH.json"

SPEC_LINE_RE = re.compile(r":(113\d{2})\b")
FC_RE = re.compile(r"\bFC-113\d{2}\b", re.I)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _rel(path: Path, repo: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return str(path)


def _present(rel: str, repo: Path) -> dict:
    path = repo / rel
    return {
        "path": rel,
        "present": path.is_file() and path.stat().st_size > 0,
        "bytes": path.stat().st_size if path.is_file() else 0,
    }


def _blob(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    try:
        return json.dumps(obj, ensure_ascii=True)
    except (TypeError, ValueError):
        return str(obj)


def _iter_units(catalog: Any) -> list[dict]:
    if not isinstance(catalog, dict):
        return []
    units: list[dict] = []
    for key in ("work_units", "items"):
        for u in catalog.get(key) or []:
            if isinstance(u, dict) and u.get("id"):
                units.append(u)
    return units


def _covers_from_text(text: str) -> list[str]:
    covers: list[str] = []
    for m in FC_RE.finditer(text):
        covers.append(m.group(0).upper())
    for m in SPEC_LINE_RE.finditer(text):
        covers.append(f"FC-{m.group(1)}")
    return list(dict.fromkeys(covers))


def load_test_registry(repo: Path | None = None) -> dict:
    repo = repo or REPO
    rel = TEST_REGISTRY
    path = repo / rel
    info: dict = {"path": rel, "present": False, "tests": [], "mutations": []}
    data = _load_json(path)
    if not isinstance(data, dict):
        return info
    info["present"] = True
    entries = data.get("tests") or data.get("entries") or data.get("suites") or []
    if isinstance(data.get("tests"), dict):
        entries = [{"id": k, **v} for k, v in data["tests"].items() if isinstance(v, dict)]
    tests: list[dict] = []
    mutations: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        tid = str(
            entry.get("id")
            or entry.get("test_id")
            or entry.get("name")
            or entry.get("path")
            or ""
        )
        if not tid:
            continue
        mut = entry.get("mutation_record") or entry.get("mutation")
        status = str(entry.get("status") or "").upper()
        text = _blob(entry)[:4000]
        tests.append(
            {
                "id": tid,
                "path": entry.get("path") or rel,
                "kind": "registry",
                "covers": entry.get("covers") or entry.get("failure_classes") or _covers_from_text(text),
                "text": text,
                "has_mutation_record": bool(mut) or status in {"PROTECTING", "FIRED", "KILLED"},
            }
        )
        if isinstance(mut, dict):
            mutations.append(
                {
                    "test_id": tid,
                    "mutation_id": mut.get("id") or f"{tid}-mutation",
                    "result": mut.get("result") or mut.get("status") or status or "UNPROVEN",
                    "broken_fails": mut.get("broken_fails"),
                    "good_passes": mut.get("good_passes"),
                    "source": rel,
                }
            )
        elif status in {"PROTECTING", "FIRED", "KILLED"}:
            mutations.append(
                {
                    "test_id": tid,
                    "mutation_id": f"{tid}-registry-status",
                    "result": status,
                    "source": rel,
                }
            )
    info["tests"] = tests
    info["mutations"] = mutations
    return info


def load_cc0014(repo: Path | None = None) -> dict:
    repo = repo or REPO
    rel = CC0014
    path = repo / rel
    info: dict = {"path": rel, "present": False, "mutations": []}
    data = _load_json(path)
    if not isinstance(data, dict):
        return info
    info["present"] = True
    muts: list[dict] = []
    for key in ("mutations", "mutation_records", "entries", "tests"):
        for item in data.get(key) or []:
            if not isinstance(item, dict):
                continue
            tid = str(item.get("test_id") or item.get("id") or "")
            if not tid:
                continue
            muts.append(
                {
                    "test_id": tid,
                    "mutation_id": item.get("mutation_id") or item.get("id") or tid,
                    "result": item.get("result") or item.get("status") or "UNPROVEN",
                    "broken_fails": item.get("broken_fails"),
                    "good_passes": item.get("good_passes"),
                    "source": rel,
                }
            )
    info["mutations"] = muts
    return info


def load_syn0001(repo: Path | None = None) -> dict:
    repo = repo or REPO
    rel = SYN0001
    info: dict = {
        "path": rel,
        "present": False,
        "status": "ABSENT",
        "nodes": [],
        "note": (
            "SYN-0001 hierarchy is not on this worktree. Reverse unmatched-cause "
            "list is 0/0 from that source; SYN-0001 is not rebuilt here (no ADV circle)."
        ),
    }
    data = _load_json(repo / rel)
    if not isinstance(data, dict):
        return info
    info["present"] = True
    info["status"] = "PRESENT"
    info["note"] = "loaded SYN-0001 hierarchy"
    nodes: list[dict] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            ntype = str(obj.get("type") or obj.get("kind") or "").upper()
            nid = obj.get("id") or obj.get("node_id")
            if nid and (
                ntype in {"CAUSE", "MECHANISM", "ROOT-CAUSE", "ROOT", "SYMPTOM"}
                or obj.get("name")
            ):
                nodes.append(
                    {
                        "id": str(nid),
                        "name": obj.get("name") or obj.get("label") or str(nid),
                        "type": ntype or "CAUSE",
                        "text": _blob(
                            {k: obj.get(k) for k in ("id", "name", "label", "type", "mechanism")}
                        ),
                    }
                )
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data.get("nodes") or data.get("hierarchy") or data.get("graph") or data)
    seen: set[str] = set()
    uniq: list[dict] = []
    for n in nodes:
        if n["id"] in seen:
            continue
        seen.add(n["id"])
        uniq.append(n)
    info["nodes"] = uniq
    return info


def catalog_phase10_tests(repo: Path | None = None) -> dict:
    repo = repo or REPO
    catalog = _load_json(repo / CATALOG)
    units = _iter_units(catalog)
    tests: list[dict] = []
    b08_ids: list[str] = []
    phase10: list[str] = []
    for u in units:
        uid = str(u.get("id") or "")
        phase = str(u.get("phase") or "")
        blob = _blob(u)
        if "B08" in blob:
            b08_ids.append(uid)
        if phase == "10" or uid.startswith("TST-"):
            phase10.append(uid)
            text = _blob(
                {
                    "id": uid,
                    "title": u.get("title"),
                    "question": u.get("question_or_target"),
                    "tests_required": u.get("tests_required"),
                    "inputs": u.get("inputs"),
                    "failure_classification": u.get("failure_classification"),
                }
            )[:6000]
            tests.append(
                {
                    "id": uid,
                    "path": CATALOG,
                    "kind": "phase10-catalog",
                    "covers": _covers_from_text(text),
                    "text": text,
                    "has_mutation_record": False,
                }
            )
    return {
        "phase_graph": _present(PHASE_GRAPH, repo),
        "b08_from_catalog_mentions": sorted(set(b08_ids)),
        "phase10_or_tst_count": len(set(phase10)),
        "tests": tests,
    }


def scan_live_tests(repo: Path | None = None) -> list[dict]:
    repo = repo or REPO
    tests: list[dict] = []
    roots = [repo / "tools", repo / "command-center" / "p2-wave" / "probes"]
    files: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        files.extend(root.rglob("test_*.py"))
        files.extend(root.rglob("probe*.py"))
    for path in sorted(set(files)):
        if not path.is_file() or path.stat().st_size > 400_000:
            continue
        rel = _rel(path, repo)
        if "/SYN-0047/" in rel.replace("\\", "/"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        tests.append(
            {
                "id": rel,
                "path": rel,
                "kind": "live-file",
                "covers": _covers_from_text(text),
                "text": text[:8000],
                "has_mutation_record": False,
            }
        )
    return tests


def collect_inventory(repo: Path | None = None) -> dict:
    repo = repo or REPO
    registry = load_test_registry(repo)
    cc = load_cc0014(repo)
    syn = load_syn0001(repo)
    b08 = catalog_phase10_tests(repo)
    live = scan_live_tests(repo)
    tests = list(registry["tests"]) + list(b08["tests"]) + live
    mutations = list(registry["mutations"]) + list(cc["mutations"])
    return {
        "test_registry": {
            "path": registry["path"],
            "present": registry["present"],
            "count": len(registry["tests"]),
        },
        "cc0014": {
            "path": cc["path"],
            "present": cc["present"],
            "count": len(cc["mutations"]),
        },
        "syn0001": syn,
        "b08": {
            "phase_graph_present": b08["phase_graph"]["present"],
            "catalog_b08_mentions": len(b08["b08_from_catalog_mentions"]),
            "phase10_or_tst_count": b08["phase10_or_tst_count"],
        },
        "live_scan_count": len(live),
        "tests": tests,
        "mutations": mutations,
        "causes": syn.get("nodes") or [],
    }
