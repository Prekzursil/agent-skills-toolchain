#!/usr/bin/env python3
"""Classify CI steps: independent vs genuinely dependent (TST-0016).

A step is *genuinely dependent* on a predecessor when it consumes a
capability that predecessor uniquely provides (repo checkout, language
setup, toolchain install, collection-floor, named step outputs).

A step is *independent yet sequenced behind a fail-fast predecessor*
when GitHub Actions' default job fail-fast would skip it, but the
predecessor is not in its genuine-dependency set. Those are the N-1
defects a single red job hides.

Live `.github/workflows/*.yml` is absent on this sparse worktree.
Classification reads AUD-0041's captured YAML inventory of the same
paths, and re-parses live YAML when it is present.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
INVENTORY = (
    REPO
    / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
)
LIVE_WFDIR = REPO / ".github/workflows"
TARGET_FILES = (
    ".github/workflows/quality.yml",
    ".github/workflows/no-runtime-junk.yml",
)
CI_HYGIENE = REPO / "rules/common/ci-hygiene.md"

CHECK_MARKERS = (
    "python -m pytest",
    "python -m pytest",
    "ruff check",
    "ruff format",
    "basedpyright ",
    "npm test",
    "npm run",
    "opengrep ",
    "gitleaks ",
    "osv-scanner",
    "charter_check",
    "mutation_probe",
    "--cov=",
    "pytest --",
    "pytest tests",
    "pytest -",
    "pytest ci/",
    "pytest hooks",
    "pytest platform",
    "python test_",
    "python tools/",
    "python hooks/",
    "python ci/",
    "python .agents/",
    "python agent-self",
    "python docs/",
    "diff ",
    "diff\t",
)


def _cmd(step: dict) -> str:
    return str(step.get("command") or "")


def _name(step: dict) -> str:
    return str(step.get("name") or "")


def _cond(step: dict) -> str:
    return str(step.get("conditional_on") or "")


def continues(step: dict) -> bool:
    v = step.get("continue_on_error")
    if v is True:
        return True
    return str(v).lower() == "true"


def runs_unconditionally(step: dict) -> bool:
    s = re.sub(r"\s+", "", _cond(step).lower())
    return "always()" in s or "failure()" in s


def fail_fast_would_skip(pred: dict, step: dict) -> bool:
    if continues(pred):
        return False
    if runs_unconditionally(step):
        return False
    return True


def is_pure_install(cmd: str) -> bool:
    cl = cmd.strip().lower()
    if cl == "npm ci" or (cl.startswith("npm ci") and "npm test" not in cl and "npm run" not in cl):
        return True
    if not (cl.startswith("pip install") or cl.startswith("python -m pip install")):
        return False
    return not any(m in cl for m in CHECK_MARKERS)


def is_setup(step: dict) -> bool:
    cmd = _cmd(step)
    name = _name(step).lower()
    if "uses:actions/checkout" in cmd or "uses:actions/setup-" in cmd:
        return True
    if "setup python" in name:
        return True
    if is_pure_install(cmd):
        return True
    return False


def is_check(step: dict) -> bool:
    return not is_setup(step)


def tags_provided(step: dict) -> set[str]:
    cmd = _cmd(step)
    name = _name(step).lower()
    tags: set[str] = set()
    if "uses:actions/checkout" in cmd:
        tags.add("repo")
    if "uses:actions/setup-python" in cmd:
        tags.add("python-3.12" if "3.12" in cmd else "python")
    if "setup python 3.12" in name:
        tags.add("python-3.12")
    if "uses:actions/setup-node" in cmd:
        tags.add("node")
    cl = cmd.lower()
    if cl.strip() == "npm ci" or (
        cl.startswith("npm ci") and "npm test" not in cl and "npm run" not in cl
    ):
        tags.add("npm-deps")
    if ("pip install ruff" in cl or "pip install ruff==" in cl) and "ruff check" not in cl:
        tags.add("ruff")
    if "pip install basedpyright" in cl and "basedpyright " not in cl.split("basedpyright", 1)[-1][:1]:
        if re.search(r"pip install basedpyright==", cl) or cl.rstrip().endswith("basedpyright"):
            tags.add("basedpyright")
        elif "basedpyright " not in cl:
            tags.add("basedpyright")
    if is_pure_install(cmd) and "pytest" in cl:
        tags.add("pytest")
    if is_pure_install(cmd) and "jsonschema" in cl:
        tags.add("jsonschema")
    if "npm ci" in cl:
        tags.add("npm-deps")
    return tags


def tags_required(step: dict) -> set[str]:
    cmd = _cmd(step)
    name = _name(step).lower()
    cl = cmd.lower()
    if "uses:actions/checkout" in cmd:
        return set()
    if "uses:actions/setup-" in cmd or "setup python" in name:
        return {"repo"}

    req: set[str] = {"repo"}
    if cl.startswith("diff ") or "charter_check" in cl or "opengrep" in cl:
        return {"repo"}
    if "gitleaks" in cl or "osv-scanner" in cl:
        return {"repo"}
    if "ruff " in cl or cl.startswith("ruff"):
        req.update({"python", "ruff"})
        return req
    if "basedpyright" in cl:
        req.update({"python", "basedpyright"})
        return req
    if cl.startswith("npm ") or "npm test" in cl or "npm run" in cl or cl.startswith("npm ci"):
        req.update({"node"})
        if "npm ci" not in cl:
            req.add("npm-deps")
        return req
    if (
        "${{ steps.py312.outputs" in cmd
        or "py3.12" in name
        or "py312" in name
        or "python 3.12" in name
    ):
        req.add("python-3.12")
        return req
    if any(
        tok in cl
        for tok in ("python", "pip ", "pytest", "basedpyright", "ruff")
    ):
        req.add("python")
        if "suitefloor" in cl or "collection floor" in name:
            req.add("pytest")
        if "platform (suite)" in name:
            req.add("pytest")
    return req


def extra_dep_indices(step: dict, prev: list[dict]) -> list[int]:
    name = _name(step).lower()
    found: list[int] = []
    if "platform (suite)" in name:
        for j, p in enumerate(prev):
            if "collection floor" in _name(p).lower():
                found.append(j)
    return found


def step_id(wf_file: str, job_id: str, index: int, step: dict) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _name(step).lower()).strip("-") or "unnamed"
    stem = Path(wf_file).name.replace(".yml", "")
    return f"{stem}:{job_id}:{index}:{slug[:48]}"


def classify_job(wf_file: str, job: dict) -> dict[str, Any]:
    steps = list(job.get("steps") or [])
    provided_by: dict[str, int] = {}
    classified: list[dict[str, Any]] = []
    hidden_ids: list[str] = []
    hidden_check_ids: list[str] = []

    for i, step in enumerate(steps):
        sid = step_id(wf_file, str(job.get("job_id")), i, step)
        kind = "setup" if is_setup(step) else "check"
        req = tags_required(step)
        genuine: list[int] = []
        missing_tags: list[str] = []
        for tag in sorted(req):
            if tag in provided_by:
                genuine.append(provided_by[tag])
            else:
                missing_tags.append(tag)
        genuine.extend(extra_dep_indices(step, steps[:i]))
        genuine = sorted(set(genuine))
        genuine_ids = [
            step_id(wf_file, str(job.get("job_id")), j, steps[j]) for j in genuine
        ]

        hidden_by: list[str] = []
        justifications: list[str] = []
        for j in range(i):
            pred = steps[j]
            if not fail_fast_would_skip(pred, step):
                continue
            if j in genuine:
                continue
            pred_id = step_id(wf_file, str(job.get("job_id")), j, pred)
            hidden_by.append(pred_id)
            pred_kind = "setup" if is_setup(pred) else "check"
            justifications.append(
                f"independent of {pred_kind} {pred_id} (no tag/output edge) "
                f"but sequenced after it with default fail-fast"
            )

        if hidden_by:
            hidden_ids.append(sid)
            if kind == "check":
                hidden_check_ids.append(sid)

        classified.append(
            {
                "id": sid,
                "index": i,
                "name": _name(step) or None,
                "command": _cmd(step)[:240],
                "kind": kind,
                "dependency_class": (
                    "independent-behind-failfast" if hidden_by else (
                        "genuinely-dependent" if genuine else "root"
                    )
                ),
                "depends_on_ids": genuine_ids,
                "requires_tags": sorted(req),
                "provides_tags": sorted(tags_provided(step)),
                "missing_tags": missing_tags,
                "hidden_by_ids": hidden_by,
                "continue_on_error": continues(step),
                "conditional_on": _cond(step) or None,
                "justification": (
                    justifications[0]
                    if justifications
                    else (
                        "consumes predecessor capabilities: " + ",".join(genuine_ids)
                        if genuine_ids
                        else "no predecessor"
                    )
                ),
            }
        )
        for tag in tags_provided(step):
            provided_by[tag] = i

    return {
        "job_id": job.get("job_id"),
        "name": job.get("name"),
        "needs": job.get("needs"),
        "step_count": len(steps),
        "setup_count": sum(1 for s in classified if s["kind"] == "setup"),
        "check_count": sum(1 for s in classified if s["kind"] == "check"),
        "independent_behind_failfast": len(hidden_ids),
        "independent_checks_behind_failfast": len(hidden_check_ids),
        "hidden_step_ids": hidden_ids,
        "hidden_check_ids": hidden_check_ids,
        "steps": classified,
    }


def _inventory_from_live_yaml() -> Optional[dict]:
    if not LIVE_WFDIR.is_dir():
        return None
    try:
        import yaml  # type: ignore
    except ImportError:
        return None
    workflows = []
    for f in sorted(LIVE_WFDIR.glob("*.y*ml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        triggers = doc.get("on", doc.get(True))
        jobs_out = []
        for jn, j in (doc.get("jobs") or {}).items():
            j = j or {}
            steps = []
            for i, s in enumerate(j.get("steps") or []):
                if not isinstance(s, dict):
                    continue
                if "run" in s:
                    cmd = " ".join(str(s["run"]).split())[:600]
                elif "uses" in s:
                    w = s.get("with") or {}
                    extra = ""
                    if isinstance(w, dict):
                        extra = ",".join(
                            f"{k}={str(v)[:40]}" for k, v in list(w.items())[:6]
                        )
                    cmd = f"uses:{s['uses']}" + (f" with[{extra}]" if extra else "")
                else:
                    cmd = "<no-run-no-uses>"
                steps.append(
                    {
                        "index": i,
                        "name": s.get("name"),
                        "command": cmd,
                        "conditional_on": s.get("if"),
                        "continue_on_error": s.get("continue-on-error"),
                    }
                )
            jobs_out.append(
                {
                    "job_id": jn,
                    "name": j.get("name"),
                    "needs": j.get("needs"),
                    "steps": steps,
                }
            )
        workflows.append(
            {
                "file": f".github/workflows/{f.name}",
                "name": doc.get("name"),
                "triggers": triggers,
                "jobs": jobs_out,
            }
        )
    return {"workflows": workflows, "source": "live-yaml"}


def load_workflows() -> dict[str, Any]:
    live = _inventory_from_live_yaml()
    if live and live.get("workflows"):
        live["live_yaml_present"] = True
        return live
    if not INVENTORY.is_file():
        return {
            "workflows": [],
            "source": "absent",
            "live_yaml_present": False,
            "inventory_present": False,
        }
    data = json.loads(INVENTORY.read_text(encoding="utf-8"))
    return {
        "workflows": data.get("workflows") or [],
        "source": "AUD-0041-captured-inventory",
        "live_yaml_present": False,
        "inventory_present": True,
        "inventory_path": INVENTORY.relative_to(REPO).as_posix(),
    }


def classify_loaded(loaded: dict[str, Any]) -> dict[str, Any]:
    per_wf: list[dict[str, Any]] = []
    for wf in loaded.get("workflows") or []:
        jobs = [classify_job(str(wf.get("file")), j) for j in (wf.get("jobs") or [])]
        hidden = sum(j["independent_behind_failfast"] for j in jobs)
        hidden_checks = sum(j["independent_checks_behind_failfast"] for j in jobs)
        per_wf.append(
            {
                "file": wf.get("file"),
                "name": wf.get("name"),
                "job_count": len(jobs),
                "step_count": sum(j["step_count"] for j in jobs),
                "independent_behind_failfast": hidden,
                "independent_checks_behind_failfast": hidden_checks,
                "jobs": jobs,
            }
        )
    targets = [w for w in per_wf if w.get("file") in TARGET_FILES]
    return {
        "source": loaded.get("source"),
        "live_yaml_present": bool(loaded.get("live_yaml_present")),
        "inventory_present": bool(loaded.get("inventory_present", True)),
        "inventory_path": loaded.get("inventory_path"),
        "ci_hygiene_present": CI_HYGIENE.is_file(),
        "ci_hygiene_path": "rules/common/ci-hygiene.md",
        "target_files": list(TARGET_FILES),
        "answer_per_workflow": {
            w["file"]: {
                "independent_behind_failfast": w["independent_behind_failfast"],
                "independent_checks_behind_failfast": w[
                    "independent_checks_behind_failfast"
                ],
                "step_count": w["step_count"],
                "job_count": w["job_count"],
            }
            for w in targets
        },
        "workflows": per_wf,
        "target_workflows": targets,
    }


def measure_estate() -> dict[str, Any]:
    return classify_loaded(load_workflows())


def specs_for_job(job_row: dict, *, setups_ok: bool = True, checks_fail: bool = True):
    """Build abstract StepSpecs from a classified job (imported lazily)."""
    from aggregate import Outcome, StepSpec

    def make_fn(kind: str, sid: str):
        def fn() -> Outcome:
            if kind == "setup":
                return Outcome(0 if setups_ok else 1, [] if setups_ok else [f"SETUP-{sid}"])
            if checks_fail:
                return Outcome(1, [f"DEFECT-{sid}"])
            return Outcome(0, [])

        return fn

    specs: list[StepSpec] = []
    for s in job_row.get("steps") or []:
        specs.append(
            StepSpec(
                id=s["id"],
                depends_on=tuple(s.get("depends_on_ids") or ()),
                fn=make_fn(s["kind"], s["id"]),
                continue_on_error=bool(s.get("continue_on_error")),
                if_always=runs_unconditionally(
                    {"conditional_on": s.get("conditional_on")}
                ),
                kind=s["kind"],
            )
        )
    return specs
