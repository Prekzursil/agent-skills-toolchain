"""IMP-0227 dry-run executor.

Dry-run resolves routing, params, cardinality bounds, cost estimate and the
declared write set while performing no spawn, no egress, and no workspace
write. A real run on the same inputs records observed writes through a
single write recorder. Acceptance: declared_writes is a SUPERSET of
observed writes. Under-declaration is a fail, not an estimate error.
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def norm_path(rel: str) -> str:
    p = str(rel or "").replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def interp(value: str, params: dict[str, Any]) -> str:
    try:
        return value.format(**params)
    except (KeyError, IndexError, ValueError):
        return value


class DryRunViolation(RuntimeError):
    """Raised when instrumented ports observe spawn, egress, or a write."""


class InstrumentedPorts:
    """Counting fake rail + net shim. Increments are measured, not asserted."""

    def __init__(self) -> None:
        self.spawns = 0
        self.egress = 0
        self.events: list[tuple[str, str]] = []

    def note_spawn(self, detail: Any) -> None:
        self.spawns += 1
        self.events.append(("spawn", str(detail)))

    def note_egress(self, detail: Any) -> None:
        self.egress += 1
        self.events.append(("egress", str(detail)))

    def snapshot(self) -> dict[str, Any]:
        return {
            "spawns": self.spawns,
            "egress": self.egress,
            "events": list(self.events),
            "computed_not_asserted": True,
        }


class DryRunGuard:
    """Patch process/network primitives so a dry-run escape is counted."""

    def __init__(self, ports: InstrumentedPorts) -> None:
        self.ports = ports
        self._saved: dict[str, Any] = {}

    def __enter__(self) -> DryRunGuard:
        ports = self.ports

        def counted_popen(*args: Any, **kwargs: Any) -> None:
            ports.note_spawn(("Popen", args, sorted(kwargs)))
            raise DryRunViolation(f"spawn:Popen:{args!r}")

        def counted_run(*args: Any, **kwargs: Any) -> None:
            ports.note_spawn(("run", args, sorted(kwargs)))
            raise DryRunViolation(f"spawn:run:{args!r}")

        def counted_system(cmd: Any) -> int:
            ports.note_spawn(("system", cmd))
            raise DryRunViolation(f"spawn:system:{cmd!r}")

        def counted_urlopen(*args: Any, **kwargs: Any) -> None:
            ports.note_egress(("urlopen", args[:1]))
            raise DryRunViolation(f"egress:urlopen:{args[:1]!r}")

        def counted_create_connection(*args: Any, **kwargs: Any) -> None:
            ports.note_egress(("create_connection", args[:1]))
            raise DryRunViolation(f"egress:create_connection:{args[:1]!r}")

        orig_connect = socket.socket.connect

        def counted_connect(sock: socket.socket, address: Any) -> None:
            ports.note_egress(("connect", address))
            raise DryRunViolation(f"egress:connect:{address!r}")

        self._saved = {
            "Popen": subprocess.Popen,
            "run": subprocess.run,
            "system": os.system,
            "urlopen": urllib.request.urlopen,
            "create_connection": socket.create_connection,
            "connect": orig_connect,
        }
        subprocess.Popen = counted_popen  # type: ignore[assignment,misc]
        subprocess.run = counted_run  # type: ignore[assignment]
        os.system = counted_system  # type: ignore[assignment]
        urllib.request.urlopen = counted_urlopen  # type: ignore[assignment]
        socket.create_connection = counted_create_connection  # type: ignore[assignment]
        socket.socket.connect = counted_connect  # type: ignore[method-assign]
        return self

    def __exit__(self, *exc: Any) -> None:
        subprocess.Popen = self._saved["Popen"]
        subprocess.run = self._saved["run"]
        os.system = self._saved["system"]
        urllib.request.urlopen = self._saved["urlopen"]
        socket.create_connection = self._saved["create_connection"]
        socket.socket.connect = self._saved["connect"]


class WriteRecorder:
    """Every real write goes through here so observed paths are computed."""

    def __init__(self, root: Path, allow_write: bool) -> None:
        self.root = Path(root)
        self.allow_write = allow_write
        self.observed: list[str] = []

    def write(self, rel: str, data: str) -> None:
        rel_n = norm_path(rel)
        self.observed.append(rel_n)
        if not self.allow_write:
            raise DryRunViolation(f"write:{rel_n}")
        path = self.root / rel_n
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")

    def unique_observed(self) -> list[str]:
        return sorted(set(self.observed))


def resolve_routing(workflow: dict[str, Any]) -> dict[str, Any]:
    raw = workflow.get("routing") or {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        "vendor": str(raw.get("vendor") or "anthropic"),
        "model": str(raw.get("model") or "opus"),
        "role": str(raw.get("role") or "implementer"),
        "fallbacks": list(raw.get("fallbacks") or []),
    }


def resolve_params(
    workflow: dict[str, Any], overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    spec = workflow.get("params") or {}
    overrides = overrides or {}
    out: dict[str, Any] = {}
    if isinstance(spec, dict):
        for key, val in spec.items():
            if key in overrides:
                out[key] = overrides[key]
            elif isinstance(val, dict):
                out[key] = val.get("default")
            else:
                out[key] = val
    for key, val in overrides.items():
        out.setdefault(key, val)
    return out


def _declared_for_stage(stage: dict[str, Any], params: dict[str, Any]) -> list[str]:
    kind = str(stage.get("kind") or "")
    if kind == "fan-out-write":
        bound = int(stage.get("max_cardinality") or 0)
        template = str(stage.get("item_template") or "out/item-{i}.txt")
        template = interp(template, params)
        return [norm_path(template.format(i=i, **params)) for i in range(max(bound, 0))]
    if kind == "subworkflow":
        acc: list[str] = []
        for child in stage.get("stages") or []:
            if isinstance(child, dict):
                acc.extend(_declared_for_stage(child, params))
        return acc
    writes = stage.get("writes") or []
    return [norm_path(interp(str(w), params)) for w in writes if str(w).strip()]


def _interp_contents(
    contents: dict[str, Any] | None, params: dict[str, Any]
) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(contents, dict):
        return out
    for key, val in contents.items():
        out[norm_path(interp(str(key), params))] = str(val)
    return out


def resolve_stage(stage: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    kind = str(stage.get("kind") or "write-file")
    declared = _declared_for_stage(stage, params)
    children = []
    if kind == "subworkflow":
        for child in stage.get("stages") or []:
            if isinstance(child, dict):
                children.append(resolve_stage(child, params))
    items = list(stage.get("items") or [])
    bound = stage.get("max_cardinality")
    if kind == "fan-out-write":
        bound = int(bound if bound is not None else len(items))
    return {
        "id": str(stage.get("id") or ""),
        "kind": kind,
        "declared_writes": declared,
        "cardinality_bound": bound,
        "items": items,
        "item_template": interp(str(stage.get("item_template") or "out/item-{i}.txt"), params),
        "contents": _interp_contents(stage.get("contents"), params),
        "undeclared_writes": [
            norm_path(interp(str(p), params))
            for p in (stage.get("undeclared_writes") or [])
        ],
        "escape_dry_run": bool(stage.get("escape_dry_run")),
        "escape_kind": str(stage.get("escape_kind") or ""),
        "escape_path": norm_path(interp(str(stage.get("escape_path") or ""), params)),
        "argv": list(stage.get("argv") or ["true"]),
        "stages": children,
        "cost": dict(stage.get("cost") or {}),
    }


@dataclass
class Plan:
    workflow_id: str
    routing: dict[str, Any]
    params: dict[str, Any]
    stages: list[dict[str, Any]]
    declared_writes: list[str]
    flat_stages: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "routing": self.routing,
            "params": self.params,
            "stages": [
                {
                    "id": s["id"],
                    "kind": s["kind"],
                    "declared_writes": s["declared_writes"],
                    "cardinality_bound": s["cardinality_bound"],
                }
                for s in self.flat_stages
            ],
            "declared_writes": list(self.declared_writes),
        }


def _flatten(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in stages:
        if s.get("kind") == "subworkflow":
            out.extend(_flatten(s.get("stages") or []))
        else:
            out.append(s)
    return out


def resolve_plan(
    workflow: dict[str, Any], overrides: dict[str, Any] | None = None
) -> Plan:
    routing = resolve_routing(workflow)
    params = resolve_params(workflow, overrides)
    stages = [
        resolve_stage(s, params)
        for s in (workflow.get("stages") or [])
        if isinstance(s, dict)
    ]
    flat = _flatten(stages)
    declared: list[str] = []
    seen: set[str] = set()
    for s in stages:
        for p in s["declared_writes"]:
            if p not in seen:
                seen.add(p)
                declared.append(p)
    return Plan(
        workflow_id=str(workflow.get("id") or ""),
        routing=routing,
        params=params,
        stages=stages,
        declared_writes=declared,
        flat_stages=flat,
    )


def estimate_cost(plan: Plan) -> dict[str, Any]:
    n_stages = len(plan.flat_stages)
    n_writes = len(plan.declared_writes)
    extra = 0
    for s in plan.flat_stages:
        extra += int((s.get("cost") or {}).get("micro") or 0)
    return {
        "units": {
            "micro_cost": "flat_stages + declared_writes + declared_stage_micro",
            "wall_ms": "flat_stages*10 + declared_writes*2",
            "blast_radius": "posix-relative paths the plan may write",
        },
        "micro_cost": n_stages + n_writes + extra,
        "wall_ms": n_stages * 10 + n_writes * 2,
        "blast_radius": list(plan.declared_writes),
        "blast_radius_count": n_writes,
        "flat_stage_count": n_stages,
    }


def actual_cost(plan: Plan, observed: list[str], elapsed_ms: float) -> dict[str, Any]:
    extra = 0
    for s in plan.flat_stages:
        extra += int((s.get("cost") or {}).get("micro") or 0)
    uniq = sorted(set(observed))
    return {
        "micro_cost": len(plan.flat_stages) + len(uniq) + extra,
        "wall_ms": round(elapsed_ms, 3),
        "blast_radius": uniq,
        "blast_radius_count": len(uniq),
        "flat_stage_count": len(plan.flat_stages),
    }


def writes_superset(declared: list[str], observed: list[str]) -> dict[str, Any]:
    d = {norm_path(p) for p in declared if norm_path(p)}
    o = {norm_path(p) for p in observed if norm_path(p)}
    under = sorted(o - d)
    extra = sorted(d - o)
    return {
        "ok": len(under) == 0,
        "declared": sorted(d),
        "observed": sorted(o),
        "underdeclared": under,
        "declared_not_written": extra,
        "method": "set(declared) >= set(observed) after posix-normalisation",
        "computed_not_asserted": True,
    }


def _run_stage_real(stage: dict[str, Any], recorder: WriteRecorder) -> None:
    kind = stage["kind"]
    if kind == "write-file":
        for rel, body in (stage.get("contents") or {}).items():
            recorder.write(rel, body)
        for rel in stage.get("undeclared_writes") or []:
            recorder.write(rel, "undeclared-by-plan")
        return
    if kind == "fan-out-write":
        template = str(stage.get("item_template") or "out/item-{i}.txt")
        for i, item in enumerate(stage.get("items") or []):
            recorder.write(template.format(i=i, item=item), str(item))
        return
    if kind == "subworkflow":
        for child in stage.get("stages") or []:
            _run_stage_real(child, recorder)


def _trip_escape(stage: dict[str, Any], recorder: WriteRecorder) -> None:
    if not stage.get("escape_dry_run"):
        return
    kind = str(stage.get("escape_kind") or "")
    if kind == "spawn":
        subprocess.Popen(list(stage.get("argv") or ["true"]))
    elif kind == "egress":
        urllib.request.urlopen("http://127.0.0.1:1/imp-0227-dry-run-probe")
    elif kind == "write":
        recorder.write(stage.get("escape_path") or "escape.txt", "dry-run-leak")


def _run_stage_dry(stage: dict[str, Any], recorder: WriteRecorder) -> None:
    if stage.get("kind") == "subworkflow":
        for child in stage.get("stages") or []:
            _run_stage_dry(child, recorder)
        return
    _trip_escape(stage, recorder)


@dataclass
class DryRunResult:
    plan: Plan
    estimate: dict[str, Any]
    ports: InstrumentedPorts
    violation: str | None = None
    declared_writes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.as_dict(),
            "estimate": self.estimate,
            "declared_writes": list(self.declared_writes),
            "ports": self.ports.snapshot(),
            "violation": self.violation,
            "side_effects": {
                "spawns": self.ports.spawns,
                "egress": self.ports.egress,
                "zero_spawn": self.ports.spawns == 0,
                "zero_egress": self.ports.egress == 0,
            },
        }


def dry_run(
    workflow: dict[str, Any],
    *,
    workspace: Path | None = None,
    overrides: dict[str, Any] | None = None,
    ports: InstrumentedPorts | None = None,
) -> DryRunResult:
    """Resolve the plan. Never writes the workspace. Never spawns or egresses."""
    ports = ports or InstrumentedPorts()
    plan = resolve_plan(workflow, overrides)
    estimate = estimate_cost(plan)
    recorder = WriteRecorder(workspace or Path("."), allow_write=False)
    violation: str | None = None
    try:
        with DryRunGuard(ports):
            for stage in plan.stages:
                _run_stage_dry(stage, recorder)
    except DryRunViolation as exc:
        violation = str(exc)
    return DryRunResult(
        plan=plan,
        estimate=estimate,
        ports=ports,
        violation=violation,
        declared_writes=list(plan.declared_writes),
    )


@dataclass
class RealRunResult:
    plan: Plan
    observed_writes: list[str]
    actual: dict[str, Any]
    elapsed_ms: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.as_dict(),
            "observed_writes": list(self.observed_writes),
            "actual": self.actual,
            "elapsed_ms": self.elapsed_ms,
        }


def execute(
    workflow: dict[str, Any],
    workspace: Path,
    *,
    overrides: dict[str, Any] | None = None,
) -> RealRunResult:
    """Perform the writes the workflow describes. Records every path written."""
    plan = resolve_plan(workflow, overrides)
    recorder = WriteRecorder(workspace, allow_write=True)
    t0 = time.perf_counter()
    for stage in plan.stages:
        _run_stage_real(stage, recorder)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    observed = recorder.unique_observed()
    return RealRunResult(
        plan=plan,
        observed_writes=observed,
        actual=actual_cost(plan, observed, elapsed_ms),
        elapsed_ms=elapsed_ms,
    )


def tree_digest(root: Path) -> dict[str, str]:
    """Independent side-effect signal: sha256 map of every file under root."""
    import hashlib

    out: dict[str, str] = {}
    if not root.exists():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            out[rel] = hashlib.sha256(raw).hexdigest()
    return out


def compare_trees(before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    return {
        "identical": not added and not removed and not changed,
        "added": added,
        "removed": removed,
        "changed": changed,
        "file_count_before": len(before),
        "file_count_after": len(after),
        "method": "sha256 map of every file under the workspace",
        "computed_not_asserted": True,
    }
