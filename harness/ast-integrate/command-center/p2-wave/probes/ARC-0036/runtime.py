"""Probe-local A5 runtime surrogate: append-only ledger, claim, worker, harvest.

This is not ARC-0031 DESIGN.json (that file is absent and is not rebuilt).
It is the executable substrate the chaos suite runs against so the shared
12-condition reducer can return COMPLETE or INCOMPLETE on real files.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from predicate import evaluate

UNIT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": True,
    "required": ["unit_id", "state"],
    "properties": {
        "unit_id": {"type": "string", "minLength": 3},
        "state": {"type": "string", "minLength": 2},
        "sentinel": {"type": "string"},
        "payload": {"type": "string"},
    },
}

LEDGER_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": True,
    "required": ["kind", "unit_id"],
    "properties": {
        "kind": {"type": "string", "minLength": 3},
        "unit_id": {"type": "string", "minLength": 3},
    },
}

PAD = "payload-padding-" + ("*" * 160)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


class World:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.ledger = root / "ledger.jsonl"
        self.artifacts = root / "artifacts"
        self.evidence = root / "evidence"
        self.manifest_path = root / "MANIFEST.json"
        self.unit_schema = root / "unit.schema.json"
        self.ledger_schema = root / "ledger.schema.json"
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.evidence.mkdir(parents=True, exist_ok=True)
        self.unit_schema.write_text(
            json.dumps(UNIT_SCHEMA, indent=2) + "\n", encoding="utf-8"
        )
        self.ledger_schema.write_text(
            json.dumps(LEDGER_SCHEMA, indent=2) + "\n", encoding="utf-8"
        )
        if not self.ledger.is_file():
            self.ledger.write_text("", encoding="utf-8")
        if not self.manifest_path.is_file():
            self.manifest_path.write_text(
                json.dumps({"artifacts": []}, indent=2) + "\n", encoding="utf-8"
            )

    def append_ledger(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, sort_keys=True)
        with self.ledger.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def read_ledger_lines(self) -> list[str]:
        if not self.ledger.is_file():
            return []
        return self.ledger.read_text(encoding="utf-8").splitlines()

    def claim_count(self, unit_id: str) -> int:
        n = 0
        for line in self.read_ledger_lines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("kind") == "CLAIM" and rec.get("unit_id") == unit_id:
                n += 1
        return n


def _healthy_body(unit_id: str, sentinel: str) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "payload": PAD,
        "downstream_token": f"read-ok:{unit_id}",
    }


def _support(world: World, unit_id: str) -> dict[str, str]:
    ev_rel = f"evidence/{unit_id}.anchor.txt"
    ev = world.root / ev_rel
    ev.write_text(f"anchor-for-{unit_id}\n", encoding="utf-8")
    return {"evidence": ev_rel}


def _register(world: World, unit_id: str, art_rel: str) -> dict[str, Any]:
    path = world.root / art_rel
    sha = sha256_file(path)
    doc = json.loads(world.manifest_path.read_text(encoding="utf-8"))
    row = {
        "path": art_rel,
        "sha256": sha,
        "present": True,
        "registered": True,
        "unit_id": unit_id,
    }
    arts = [a for a in doc.get("artifacts") or [] if a.get("path") != art_rel]
    arts.append(row)
    doc["artifacts"] = arts
    world.manifest_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return row


def _base_obs(world: World, unit_id: str, art_rel: str, ev_rel: str) -> dict[str, Any]:
    sentinel = f"SUCCESS:{unit_id}"
    return {
        "repo": str(world.root),
        "state": "SUCCESS",
        "exit_code": 0,
        "claim_count": 1,
        "artifacts": [{"path": art_rel}],
        "schema_path": "unit.schema.json",
        "sentinel": sentinel,
        "evidence": [{"path": ev_rel}],
        "tests": [{"id": f"t-{unit_id}", "result": "PASS"}],
        "negative_controls": [
            {"id": f"nc-{unit_id}", "fired_on_bad": True, "silent_on_good": True}
        ],
        "reviewer": {
            "reviewer_id": "arc-0036-fixture-reviewer",
            "independent": True,
            "verdict": "PASS",
        },
        "defects": [],
        "manifest": {
            "registered": False,
            "present": False,
            "path": art_rel,
            "sha256": "",
        },
        "consumer_required_fields": ["unit_id", "downstream_token"],
    }


def run_healthy(world: World, unit_id: str) -> dict[str, Any]:
    """Worker writes a full artifact; monitor harvests and registers."""
    sentinel = f"SUCCESS:{unit_id}"
    art_rel = f"artifacts/{unit_id}.json"
    ev = _support(world, unit_id)
    world.append_ledger({"kind": "CLAIM", "unit_id": unit_id, "dispatcher": "d1"})
    body = _healthy_body(unit_id, sentinel)
    (world.root / art_rel).write_text(
        json.dumps(body, indent=2) + "\n", encoding="utf-8"
    )
    world.append_ledger(
        {"kind": "WORKER-EXIT", "unit_id": unit_id, "state": "SUCCESS"}
    )
    row = _register(world, unit_id, art_rel)
    world.append_ledger(
        {
            "kind": "HARVEST",
            "unit_id": unit_id,
            "artifact": art_rel,
            "sha256": row["sha256"],
        }
    )
    obs = _base_obs(world, unit_id, art_rel, ev["evidence"])
    obs["manifest"] = {
        "registered": True,
        "present": True,
        "path": art_rel,
        "sha256": row["sha256"],
    }
    obs["claim_count"] = world.claim_count(unit_id)
    result = evaluate(obs)
    result["observation"] = {k: v for k, v in obs.items() if k != "repo"}
    result["unit_id"] = unit_id
    return result


def kill_monitor(world: World, unit_id: str) -> dict[str, Any]:
    """Worker finishes; monitor dies before harvest/register. Targets C11."""
    sentinel = f"SUCCESS:{unit_id}"
    art_rel = f"artifacts/{unit_id}.json"
    ev = _support(world, unit_id)
    world.append_ledger({"kind": "CLAIM", "unit_id": unit_id, "dispatcher": "d1"})
    (world.root / art_rel).write_text(
        json.dumps(_healthy_body(unit_id, sentinel), indent=2) + "\n", encoding="utf-8"
    )
    world.append_ledger(
        {"kind": "WORKER-EXIT", "unit_id": unit_id, "state": "SUCCESS"}
    )
    world.append_ledger(
        {"kind": "MONITOR-KILLED", "unit_id": unit_id, "phase": "pre-harvest"}
    )
    obs = _base_obs(world, unit_id, art_rel, ev["evidence"])
    obs["manifest"] = {
        "registered": False,
        "present": False,
        "path": art_rel,
        "sha256": "",
    }
    obs["claim_count"] = world.claim_count(unit_id)
    result = evaluate(obs)
    result["observation"] = {k: v for k, v in obs.items() if k != "repo"}
    result["unit_id"] = unit_id
    return result


def kill_worker(world: World, unit_id: str) -> dict[str, Any]:
    """Worker dies after a 1-byte stub. Targets C3 (mid-unit partial write)."""
    art_rel = f"artifacts/{unit_id}.json"
    ev = _support(world, unit_id)
    world.append_ledger({"kind": "CLAIM", "unit_id": unit_id, "dispatcher": "d1"})
    (world.root / art_rel).write_bytes(b"{")
    world.append_ledger(
        {"kind": "WORKER-KILLED", "unit_id": unit_id, "phase": "mid-write"}
    )
    obs = _base_obs(world, unit_id, art_rel, ev["evidence"])
    obs["state"] = "INCOMPLETE"
    obs["manifest"] = {
        "registered": False,
        "present": False,
        "path": art_rel,
        "sha256": "",
    }
    obs["claim_count"] = world.claim_count(unit_id)
    result = evaluate(obs)
    result["observation"] = {k: v for k, v in obs.items() if k != "repo"}
    result["unit_id"] = unit_id
    return result


def corrupt_ledger(world: World, unit_id: str) -> dict[str, Any]:
    """Overwrite a committed HARVEST line. Resume must parse the ledger. Targets C4."""
    first = run_healthy(world, unit_id)
    torn_rel = f"artifacts/{unit_id}.torn-ledger.json"
    lines = world.read_ledger_lines()
    corrupted = False
    new_lines: list[str] = []
    for line in lines:
        if (not corrupted) and '"HARVEST"' in line and unit_id in line:
            new_lines.append('{"kind":"HARVEST","unit_id":')
            corrupted = True
        else:
            new_lines.append(line)
    if not corrupted:
        raise RuntimeError("no HARVEST line to corrupt")
    world.ledger.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    # Keep the dump >= the C3 size floor so this case isolates C4 (parse),
    # not C3 (too small). The bytes remain invalid JSON.
    torn = '{"kind":"HARVEST","unit_id":' + ("x" * 160)
    (world.root / torn_rel).write_text(torn, encoding="utf-8")
    ev_rel = f"evidence/{unit_id}.anchor.txt"
    obs = _base_obs(world, unit_id, torn_rel, ev_rel)
    obs["schema_path"] = "ledger.schema.json"
    obs["state"] = "INCOMPLETE"
    obs["manifest"] = {
        "registered": False,
        "present": False,
        "path": torn_rel,
        "sha256": "",
    }
    obs["claim_count"] = 1
    result = evaluate(obs)
    result["observation"] = {k: v for k, v in obs.items() if k != "repo"}
    result["unit_id"] = unit_id
    result["pre_corrupt_verdict"] = first["verdict"]
    result["ledger_corrupted"] = True
    return result


def duplicate_dispatch(world: World, unit_id: str) -> dict[str, Any]:
    """Two dispatchers CLAIM the same unit; no exclusive winner. Targets C1."""
    sentinel = f"SUCCESS:{unit_id}"
    art_rel = f"artifacts/{unit_id}.json"
    ev = _support(world, unit_id)
    world.append_ledger({"kind": "CLAIM", "unit_id": unit_id, "dispatcher": "d1"})
    world.append_ledger({"kind": "CLAIM", "unit_id": unit_id, "dispatcher": "d2"})
    (world.root / art_rel).write_text(
        json.dumps(_healthy_body(unit_id, sentinel), indent=2) + "\n", encoding="utf-8"
    )
    row = _register(world, unit_id, art_rel)
    obs = _base_obs(world, unit_id, art_rel, ev["evidence"])
    obs["manifest"] = {
        "registered": True,
        "present": True,
        "path": art_rel,
        "sha256": row["sha256"],
    }
    obs["claim_count"] = world.claim_count(unit_id)
    obs["state"] = "SUCCESS"
    result = evaluate(obs)
    result["observation"] = {k: v for k, v in obs.items() if k != "repo"}
    result["unit_id"] = unit_id
    return result


def unstarted(world: World, unit_id: str) -> dict[str, Any]:
    """Queued but never written. Used by partial-batch unfinished members. Targets C2."""
    art_rel = f"artifacts/{unit_id}.json"
    ev = _support(world, unit_id)
    world.append_ledger({"kind": "CLAIM", "unit_id": unit_id, "dispatcher": "d1"})
    obs = _base_obs(world, unit_id, art_rel, ev["evidence"])
    obs["state"] = "INCOMPLETE"
    obs["manifest"] = {
        "registered": False,
        "present": False,
        "path": art_rel,
        "sha256": "",
    }
    obs["claim_count"] = world.claim_count(unit_id)
    result = evaluate(obs)
    result["observation"] = {k: v for k, v in obs.items() if k != "repo"}
    result["unit_id"] = unit_id
    return result


def naive_claim_means_complete(world: World, unit_id: str) -> bool:
    """Vacuous batch reducer: a CLAIM record is treated as done. Must NOT be used."""
    return world.claim_count(unit_id) >= 1


def inject_condition(world: World, unit_id: str, n: int) -> dict[str, Any]:
    """Drive a single condition to UNSATISFIED from an otherwise-healthy unit."""
    if n == 1:
        return duplicate_dispatch(world, unit_id)
    if n == 2:
        return unstarted(world, unit_id)
    if n == 3:
        return kill_worker(world, unit_id)
    if n == 4:
        return corrupt_ledger(world, unit_id)
    if n == 11:
        return kill_monitor(world, unit_id)

    sentinel = f"SUCCESS:{unit_id}"
    art_rel = f"artifacts/{unit_id}.json"
    ev = _support(world, unit_id)
    body = _healthy_body(unit_id, sentinel)
    if n == 5:
        body.pop("sentinel", None)
    if n == 12:
        body.pop("downstream_token", None)
    (world.root / art_rel).write_text(
        json.dumps(body, indent=2) + "\n", encoding="utf-8"
    )
    row = _register(world, unit_id, art_rel)
    world.append_ledger({"kind": "CLAIM", "unit_id": unit_id, "dispatcher": "d1"})
    obs = _base_obs(world, unit_id, art_rel, ev["evidence"])
    obs["manifest"] = {
        "registered": True,
        "present": True,
        "path": art_rel,
        "sha256": row["sha256"],
    }
    if n == 6:
        obs["evidence"] = [{"path": f"evidence/{unit_id}.MISSING.txt"}]
    if n == 7:
        obs["tests"] = [{"id": f"t-{unit_id}", "result": "FAIL"}]
    if n == 8:
        obs["negative_controls"] = [
            {"id": f"nc-{unit_id}", "fired_on_bad": False, "silent_on_good": True}
        ]
    if n == 9:
        obs["reviewer"] = {
            "reviewer_id": "arc-0036-fixture-reviewer",
            "independent": False,
            "verdict": "PASS",
        }
    if n == 10:
        obs["defects"] = [{"id": "D-P0", "severity": "P0", "status": "OPEN"}]
    result = evaluate(obs)
    result["observation"] = {k: v for k, v in obs.items() if k != "repo"}
    result["unit_id"] = unit_id
    return result


def vacuity(world: World, unit_id: str) -> dict[str, Any]:
    """Complete a unit, then delete its artifact. Predicate must flip to INCOMPLETE."""
    before = run_healthy(world, unit_id)
    art_rel = before["observation"]["artifacts"][0]["path"]
    path = world.root / art_rel
    if not path.is_file():
        raise RuntimeError("vacuity requires an existing artifact")
    path.unlink()
    obs = dict(before["observation"])
    obs["repo"] = str(world.root)
    after = evaluate(obs)
    return {
        "before": before,
        "after": after,
        "deleted": art_rel,
        "flipped": before["verdict"] == "COMPLETE" and after["verdict"] == "INCOMPLETE",
        "c2_after": next(
            r["outcome"] for r in after["conditions"] if r["n"] == 2
        ),
    }


def exit_zero_alone(world: World, unit_id: str) -> dict[str, Any]:
    """exit_code=0 with no artifact and no completion state is not success."""
    art_rel = f"artifacts/{unit_id}.json"
    obs = {
        "repo": str(world.root),
        "state": "",
        "exit_code": 0,
        "claim_count": 1,
        "artifacts": [{"path": art_rel}],
        "schema_path": "unit.schema.json",
        "sentinel": f"SUCCESS:{unit_id}",
        "evidence": [{"path": f"evidence/{unit_id}.anchor.txt"}],
        "tests": [{"id": "t", "result": "PASS"}],
        "negative_controls": [
            {"id": "nc", "fired_on_bad": True, "silent_on_good": True}
        ],
        "reviewer": {
            "reviewer_id": "x",
            "independent": True,
            "verdict": "PASS",
        },
        "defects": [],
        "manifest": {
            "registered": True,
            "present": True,
            "path": art_rel,
            "sha256": "a" * 64,
        },
        "consumer_required_fields": ["unit_id"],
    }
    result = evaluate(obs)
    result["unit_id"] = unit_id
    return result
