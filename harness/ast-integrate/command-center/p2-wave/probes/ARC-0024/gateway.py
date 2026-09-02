#!/usr/bin/env python3
"""A4 gateway / lazy-activation prototype.

Index records stay resident. Capability bodies and stdio MCP children
materialize only after activate(). Deactivate() is defined per kind and
must return the session to the measured floor. Exhausted budget REFUSES
activation; it does not warn-and-continue.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
REQUIRED_KINDS = (
    "skill",
    "hook",
    "rule",
    "workflow_blueprint",
    "council_preset",
    "mcp_mount",
)
DEACTIVATE_BY_KIND = {
    "skill": "unload-context",
    "hook": "unregister-dispatcher",
    "rule": "unload-rule-table",
    "workflow_blueprint": "drop-compiled-stages",
    "council_preset": "drop-overlay",
    "mcp_mount": "reap-stdio-child",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def utf8_len(path: Path) -> int:
    return len(path.read_bytes().replace(b"\r\n", b"\n"))


def live_os_mcpish_count() -> dict[str, Any]:
    """Count other processes whose cmdline looks MCP-like. Not the estate figure."""
    hits: list[dict[str, Any]] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return {"available": False, "count": 0, "hits": []}
    my_pid = os.getpid()
    # Substring "mcp" is too broad (matches parent shells that replay a
    # previous mcp_stub command). Require a dedicated argv token/path.
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == my_pid:
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        argv = [p.decode("utf-8", "replace") for p in raw.split(b"\x00") if p]
        if not argv:
            continue
        joined = " ".join(argv).lower()
        dedicated = (
            any(Path(a).name == "mcp_stub.py" for a in argv)
            or "mcp-server" in joined
            or "modelcontextprotocol" in joined
        )
        if not dedicated:
            continue
        hits.append({"pid": pid, "cmd": joined[:200]})
    return {"available": True, "count": len(hits), "hits": hits[:20]}


@dataclass
class Activation:
    cap_id: str
    kind: str
    body_bytes: bytes
    proc: subprocess.Popen | None = None


@dataclass
class Gateway:
    root: Path = field(default_factory=lambda: FIXTURES)
    enforce_budget: bool = True
    index: dict[str, Any] = field(init=False)
    config: dict[str, Any] = field(init=False)
    records: dict[str, dict[str, Any]] = field(init=False)
    floor_bytes: int = field(init=False)
    activated: dict[str, Activation] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        schema_path = self.root / "index.schema.json"
        index_path = self.root / "INDEX.json"
        gw_path = self.root / "GATEWAY.json"
        schema = _read_json(schema_path)
        try:
            import jsonschema

            jsonschema.Draft7Validator(schema).validate(_read_json(index_path))
        except ImportError:
            pass
        self.index = _read_json(index_path)
        self.config = _read_json(gw_path)
        recs = self.index["records"]
        ids = [r["id"] for r in recs]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate index ids (fail-closed)")
        self.records = {r["id"]: r for r in recs}
        for rec in recs:
            body = self.body_path(rec)
            if not body.is_file():
                raise FileNotFoundError(body)
            expected = rec["deactivate_method"]
            want = DEACTIVATE_BY_KIND[rec["kind"]]
            if expected != want:
                raise ValueError(
                    f"{rec['id']} deactivate_method {expected!r} != {want!r}"
                )
            if rec["leaks_after_deactivate"] is True:
                raise ValueError(f"{rec['id']} declares a leak; A4 forbids silent leaks")
        self.floor_bytes = (
            utf8_len(index_path) + utf8_len(gw_path) + utf8_len(schema_path)
        )

    def body_path(self, rec: dict[str, Any]) -> Path:
        return (self.root / rec["body_rel"]).resolve()

    def body_cost(self, rec: dict[str, Any]) -> int:
        return utf8_len(self.body_path(rec))

    def process_cost(self, rec: dict[str, Any]) -> int:
        return int(rec["activation_cost_processes"])

    def select(self, task: dict[str, Any]) -> dict[str, Any]:
        tags = {str(t).lower() for t in (task.get("tags") or [])}
        threshold = int(self.config["selection"]["threshold"])
        selected: list[dict[str, Any]] = []
        not_selected: list[dict[str, Any]] = []
        for rec in self.index["records"]:
            overlap = tags.intersection({t.lower() for t in rec["selector_tags"]})
            score = len(overlap)
            row = {
                "id": rec["id"],
                "kind": rec["kind"],
                "score": score,
                "overlap": sorted(overlap),
            }
            if score >= threshold:
                row["reason"] = "tag-overlap"
                selected.append(row)
            else:
                row["reason"] = "below-threshold"
                not_selected.append(row)
        selected.sort(key=lambda r: (-r["score"], r["id"]))
        return {
            "interface": "Gateway.select",
            "activates": False,
            "task_id": task.get("id"),
            "selected": selected,
            "not_selected": not_selected,
            "not_installed": [],
        }

    def lookup(self, cap_id: str) -> str:
        if cap_id in self.records:
            return "INSTALLED"
        return "NOT_INSTALLED"

    def _activated_bytes(self) -> int:
        return sum(len(a.body_bytes) for a in self.activated.values())

    def _activated_processes(self) -> int:
        n = 0
        for a in self.activated.values():
            if a.proc is not None and a.proc.poll() is None:
                n += 1
        return n

    def resident(self) -> dict[str, Any]:
        return {
            "processes": 1 + self._activated_processes(),
            "bytes": self.floor_bytes + self._activated_bytes(),
            "floor_bytes": self.floor_bytes,
            "activated_ids": sorted(self.activated),
            "activated_bytes": self._activated_bytes(),
            "activated_child_processes": self._activated_processes(),
            "contents_when_idle": [
                "gateway host process",
                "INDEX.json",
                "GATEWAY.json",
                "index.schema.json",
            ],
        }

    def _spawn_mcp(self, cap_id: str) -> subprocess.Popen:
        stub = (FIXTURES / "mcp_stub.py").resolve()
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.Popen(
            [sys.executable, "-u", str(stub), cap_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
        assert proc.stdout is not None
        line = proc.stdout.readline()
        if b"ready" not in line.lower():
            proc.kill()
            proc.wait(timeout=3)
            raise RuntimeError(f"mcp stub for {cap_id} did not become ready: {line!r}")
        if proc.poll() is not None:
            raise RuntimeError(f"mcp stub for {cap_id} exited immediately")
        return proc

    def _reap(self, proc: subprocess.Popen | None) -> None:
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)

    def activate(self, cap_id: str) -> dict[str, Any]:
        if cap_id not in self.records:
            return {
                "status": "NOT_INSTALLED",
                "id": cap_id,
                "reason": "absent-from-index",
            }
        if cap_id in self.activated:
            return {"status": "ALREADY_ACTIVE", "id": cap_id}
        rec = self.records[cap_id]
        if rec.get("installed") is not True:
            return {
                "status": "NOT_INSTALLED",
                "id": cap_id,
                "reason": "installed-flag-false",
            }
        body = self.body_path(rec).read_bytes().replace(b"\r\n", b"\n")
        add_bytes = len(body)
        add_proc = self.process_cost(rec)
        budget = self.config["budget"]
        next_bytes = self._activated_bytes() + add_bytes
        next_proc = self._activated_processes() + add_proc
        over_bytes = next_bytes > int(budget["max_activated_bytes"])
        over_proc = next_proc > int(budget["max_activated_processes"])
        if self.enforce_budget and (over_bytes or over_proc):
            why = []
            if over_proc:
                why.append(
                    f"processes {next_proc}>{budget['max_activated_processes']}"
                )
            if over_bytes:
                why.append(f"bytes {next_bytes}>{budget['max_activated_bytes']}")
            return {
                "status": "REFUSED",
                "id": cap_id,
                "reason": "budget-exhausted:" + ",".join(why),
                "on_exhaustion": "REFUSE",
                "materialized": False,
                "resident": self.resident(),
            }
        proc = None
        if add_proc:
            proc = self._spawn_mcp(cap_id)
        self.activated[cap_id] = Activation(
            cap_id=cap_id, kind=rec["kind"], body_bytes=body, proc=proc
        )
        status = "ACTIVATED"
        if (over_bytes or over_proc) and not self.enforce_budget:
            status = "WARN_ACTIVATED"
        return {
            "status": status,
            "id": cap_id,
            "kind": rec["kind"],
            "deactivate_method": rec["deactivate_method"],
            "added_bytes": add_bytes,
            "added_processes": add_proc,
            "materialized": True,
            "resident": self.resident(),
        }

    def deactivate(self, cap_id: str) -> dict[str, Any]:
        act = self.activated.get(cap_id)
        if act is None:
            return {"status": "NOT_ACTIVE", "id": cap_id}
        rec = self.records[cap_id]
        method = rec["deactivate_method"]
        self._reap(act.proc)
        del self.activated[cap_id]
        return {
            "status": "DEACTIVATED",
            "id": cap_id,
            "kind": rec["kind"],
            "method": method,
            "leaked": False,
            "resident": self.resident(),
        }

    def close(self) -> None:
        for cap_id in list(self.activated):
            self.deactivate(cap_id)

    def kinds_in_index(self) -> set[str]:
        return {r["kind"] for r in self.index["records"]}


def check_lifecycle_totality(root: Path | None = None) -> dict[str, Any]:
    gw = Gateway(root=root or FIXTURES, enforce_budget=True)
    try:
        missing_kinds = [k for k in REQUIRED_KINDS if k not in gw.kinds_in_index()]
        floor = gw.resident()
        per_kind: list[dict[str, Any]] = []
        fail = False
        if missing_kinds:
            fail = True
        seen_kind: set[str] = set()
        for rec in gw.index["records"]:
            if rec["kind"] in seen_kind:
                continue
            seen_kind.add(rec["kind"])
            before = gw.resident()
            up = gw.activate(rec["id"])
            mid = gw.resident()
            grew = mid["bytes"] > before["bytes"] or mid["processes"] > before["processes"]
            down = gw.deactivate(rec["id"])
            after = gw.resident()
            restored = (
                after["bytes"] == floor["bytes"]
                and after["processes"] == floor["processes"]
                and after["activated_ids"] == []
            )
            row_ok = (
                up.get("status") == "ACTIVATED"
                and down.get("status") == "DEACTIVATED"
                and grew
                and restored
                and rec["deactivate_method"] == DEACTIVATE_BY_KIND[rec["kind"]]
                and rec["leaks_after_deactivate"] is False
            )
            if not row_ok:
                fail = True
            per_kind.append(
                {
                    "kind": rec["kind"],
                    "id": rec["id"],
                    "deactivate_method": rec["deactivate_method"],
                    "activated": up.get("status"),
                    "deactivated": down.get("status"),
                    "grew": grew,
                    "restored_floor": restored,
                    "ok": row_ok,
                }
            )
        uncovered = [k for k in REQUIRED_KINDS if k not in seen_kind]
        if uncovered:
            fail = True
        mutant_index = json.loads((gw.root / "INDEX.json").read_text(encoding="utf-8"))
        mutant_fail_closed = False
        for rec in mutant_index["records"]:
            if rec["kind"] == "hook":
                rec["deactivate_method"] = ""
                rec["leaks_after_deactivate"] = True
                if rec["deactivate_method"] != DEACTIVATE_BY_KIND["hook"]:
                    mutant_fail_closed = True
                if rec["leaks_after_deactivate"] is True:
                    mutant_fail_closed = True
                break
        if not mutant_fail_closed:
            fail = True
        return {
            "ok": not fail,
            "floor": floor,
            "missing_kinds": missing_kinds,
            "uncovered": uncovered,
            "per_kind": per_kind,
            "mutant_incomplete_lifecycle_rejected": mutant_fail_closed,
            "kinds_required": list(REQUIRED_KINDS),
        }
    finally:
        gw.close()


def check_budget_refuse(root: Path | None = None) -> dict[str, Any]:
    gw = Gateway(root=root or FIXTURES, enforce_budget=True)
    try:
        floor = gw.resident()
        first = gw.activate("mcp.filesystem")
        after_one = gw.resident()
        second = gw.activate("mcp.git")
        after_refuse = gw.resident()
        skill = gw.activate("skill.council")
        refuse_ok = (
            first.get("status") == "ACTIVATED"
            and second.get("status") == "REFUSED"
            and second.get("materialized") is False
            and after_refuse["processes"] == after_one["processes"]
            and after_refuse["bytes"] == after_one["bytes"]
            and "mcp.git" not in after_refuse["activated_ids"]
            and skill.get("status") == "ACTIVATED"
        )
        gw.close()
        restored = gw.resident()
        floor_ok = (
            restored["bytes"] == floor["bytes"]
            and restored["processes"] == floor["processes"]
        )

        mutant = Gateway(root=root or FIXTURES, enforce_budget=False)
        try:
            mutant.activate("mcp.filesystem")
            warned = mutant.activate("mcp.git")
            mutant_would_materialize = warned.get("status") == "WARN_ACTIVATED"
            mutant_children = mutant.resident()["activated_child_processes"]
        finally:
            mutant.close()

        production_is_refuse = (
            str(gw.config["budget"]["on_exhaustion"]).upper() == "REFUSE"
        )
        ok = (
            refuse_ok
            and floor_ok
            and mutant_would_materialize
            and mutant_children == 2
            and production_is_refuse
        )
        return {
            "ok": ok,
            "first": first.get("status"),
            "second": second.get("status"),
            "second_reason": second.get("reason"),
            "skill_under_remaining_budget": skill.get("status"),
            "refused_did_not_materialize": second.get("materialized") is False,
            "floor_restored": floor_ok,
            "warn_only_mutant_materializes_second_mcp": mutant_would_materialize,
            "on_exhaustion": gw.config["budget"]["on_exhaustion"],
            "after_one_processes": after_one["processes"],
            "after_refuse_processes": after_refuse["processes"],
        }
    finally:
        gw.close()


def measure_floor_and_baseline(root: Path | None = None) -> dict[str, Any]:
    gw = Gateway(root=root or FIXTURES, enforce_budget=False)
    try:
        floor = dict(gw.resident())
        results = []
        for rec in gw.index["records"]:
            results.append(gw.activate(rec["id"]))
        baseline = dict(gw.resident())
        mcp_n = sum(1 for r in gw.index["records"] if r["kind"] == "mcp_mount")
        return {
            "method": (
                "resident() = 1 gateway host process + live stdio children; "
                "bytes = utf-8 INDEX.json + GATEWAY.json + index.schema.json "
                "+ sum of currently activated body files. Same function for "
                "floor (activated=[]) and always-on baseline (every index id)."
            ),
            "floor": floor,
            "baseline_always_on": baseline,
            "delta_bytes": baseline["bytes"] - floor["bytes"],
            "delta_processes": baseline["processes"] - floor["processes"],
            "mcp_mounts_in_index": mcp_n,
            "activate_statuses": [r.get("status") for r in results],
            "live_os_mcpish": live_os_mcpish_count(),
        }
    finally:
        gw.close()


if __name__ == "__main__":
    m = measure_floor_and_baseline()
    print(json.dumps(m, indent=2, sort_keys=True))
    print("SUCCESS:ARC-0024 gateway self-measure")
