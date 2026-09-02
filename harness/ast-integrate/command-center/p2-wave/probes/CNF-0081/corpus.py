"""Load the hermetic eval registry and census live workflow files."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTRY = HERE / "fixtures" / "registry"
PRODUCTION_ESTIMATOR = Path("tools/agentspec/agentspec/budget.py")
PRODUCTION_EVALS = Path("tools/agentspec/agentspec/evals/registry.py")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hermetic_workflows() -> list[dict]:
    rows = []
    for path in sorted(REGISTRY.glob("wf.*.json")):
        wf = load_json(path)
        wf["_source_path"] = path.relative_to(REPO).as_posix()
        rows.append(wf)
    if not rows:
        raise FileNotFoundError(f"empty hermetic registry: {REGISTRY}")
    return rows


def production_inputs() -> dict:
    est = REPO / PRODUCTION_ESTIMATOR
    ev = REPO / PRODUCTION_EVALS
    return {
        "estimator_path": PRODUCTION_ESTIMATOR.as_posix(),
        "estimator_present": est.is_file(),
        "eval_registry_path": PRODUCTION_EVALS.as_posix(),
        "eval_registry_present": ev.is_file(),
    }


# Other p2-wave units write workflow fixtures concurrently. Census only
# production trees so the row set is stable under parallel delivery.
_LIVE_ROOTS = (
    REPO / "tools",
    REPO / "workflows",
    REPO / "blueprints",
    REPO / "command-center" / "workflows",
    REPO / "command-center" / "blueprints",
)


def live_workflow_files() -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    for root in _LIVE_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("workflows/*.json")):
            if any(
                part in {".git", "node_modules", "__pycache__", "p2-wave"}
                for part in path.parts
            ):
                continue
            rel = path.relative_to(REPO).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            rec = {"path": rel, "parse_ok": False, "workflow_id": path.stem}
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                rec["parse_error"] = type(exc).__name__
                found.append(rec)
                continue
            rec["parse_ok"] = True
            rec["workflow_id"] = str(doc.get("id") or path.stem)
            rec["n_stages"] = len(doc.get("stages") or [])
            found.append(rec)
    return found
