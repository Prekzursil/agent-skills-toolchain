#!/usr/bin/env python3
"""Hermetic fake rail for IMP-0182.

Executes a spliced (or parent) workflow with zero network and zero real process
spawns. A capability not in EMULATABLE is a named refusal — silently faking it
would be worse than refusing.

This is a local stand-in for tools/agentspec/agentspec/evals/fake_rail.py, which
is not present on this worktree. Probe 2 AST-walks this file to prove the rail
does not import subprocess/socket/urllib.
"""
from __future__ import annotations

import hashlib
from typing import Any

from workflow_ir import stage_fingerprint

EMULATABLE = frozenset({"pure-transform", "gate", "score"})


class RailRefusal(Exception):
    def __init__(self, reason: str, detail: dict[str, Any] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail or {}


class FakeRail:
    def __init__(self) -> None:
        self.spawn_count = 0
        self.network_count = 0
        self.plan: list[str] = []

    def run(
        self, workflow: dict[str, Any], initial: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.plan = []
        env: dict[str, Any] = dict(initial or {})
        stages = workflow.get("stages") or []
        if not stages:
            raise RailRefusal("empty-workflow", {"workflow_id": workflow.get("id")})
        for stage in stages:
            cap = str(stage.get("capability") or "pure-transform")
            if cap not in EMULATABLE:
                raise RailRefusal(
                    "unemulatable-capability",
                    {"capability": cap, "stage_id": stage.get("id")},
                )
            env = self._apply(stage, env)
            self.plan.append(stage_fingerprint(stage))
        return {
            "ok": True,
            "workflow_id": workflow.get("id"),
            "plan": list(self.plan),
            "plan_fingerprint": hashlib.sha256(
                ("|".join(self.plan)).encode("utf-8")
            ).hexdigest(),
            "env": env,
            "spawn_count": self.spawn_count,
            "network_count": self.network_count,
            "stage_count": len(stages),
        }

    def _apply(self, stage: dict[str, Any], env: dict[str, Any]) -> dict[str, Any]:
        body = stage.get("body") or {}
        op = str(body.get("op") or "")
        nxt = dict(env)
        if op == "parse":
            src = body.get("from", "raw")
            dst = body.get("to", "doc")
            blob = env.get(src)
            if not isinstance(blob, (bytes, bytearray, str)):
                raise RailRefusal("missing-input", {"port": src, "stage_id": stage.get("id")})
            if isinstance(blob, (bytes, bytearray)):
                nxt[dst] = bytes(blob).decode("utf-8", "replace")
            else:
                nxt[dst] = str(blob)
            return nxt
        if op == "extract":
            src = body.get("from", "doc")
            dst = body.get("to", "score")
            doc = env.get(src)
            if doc is None:
                raise RailRefusal("missing-input", {"port": src, "stage_id": stage.get("id")})
            quality = float(body.get("quality", 0.5))
            digest = hashlib.sha256(str(doc).encode("utf-8")).digest()
            mix = digest[0] / 255.0
            nxt[dst] = round(min(1.0, max(0.0, 0.5 * quality + 0.5 * mix * quality)), 6)
            return nxt
        if op == "decide":
            src = body.get("from", "score")
            dst = body.get("to", "verdict")
            score = env.get(src)
            if not isinstance(score, (int, float)):
                raise RailRefusal("missing-input", {"port": src, "stage_id": stage.get("id")})
            threshold = float(body.get("threshold", 0.5))
            nxt[dst] = bool(float(score) >= threshold)
            return nxt
        if op == "classify_image":
            raise RailRefusal(
                "unemulatable-capability",
                {
                    "capability": "image-pixels",
                    "stage_id": stage.get("id"),
                    "note": "pixels are not honestly emulatable on this rail",
                },
            )
        raise RailRefusal("unknown-op", {"op": op, "stage_id": stage.get("id")})
