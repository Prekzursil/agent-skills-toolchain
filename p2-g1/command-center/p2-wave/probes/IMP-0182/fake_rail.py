"""IMP-0182 fake rail: executes a workflow plan in-process. No network, no
subprocess spawns - the plan hash is a sha256 over the canonical plan JSON."""
from __future__ import annotations

import hashlib
import json


class FakeRail:
    def __init__(self):
        self.network_count = 0
        self.spawn_count = 0
        self.runs = []

    def plan(self, workflow: dict) -> dict:
        return {
            "id": workflow["id"],
            "stages": [[s["name"], sorted(s.get("inputs") or []), sorted(s.get("outputs") or [])]
                       for s in workflow["stages"]],
            "edges": [list(e) for e in workflow.get("edges") or []],
        }

    def run(self, workflow: dict) -> dict:
        plan = self.plan(workflow)
        digest = hashlib.sha256(
            json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        rec = {"workflow_id": workflow["id"], "plan_sha256": digest}
        self.runs.append(rec)
        return rec

    def run_many(self, workflows: list) -> list:
        return [self.run(w) for w in workflows]
