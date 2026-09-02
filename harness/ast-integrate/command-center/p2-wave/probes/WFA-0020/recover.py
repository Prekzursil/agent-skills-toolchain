"""Recover executed stage sequences from neutralized transcript events."""
from __future__ import annotations

from typing import Any


def _content_blocks(event: dict[str, Any]) -> list[Any]:
    msg = event.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, list):
            return content
        if isinstance(content, dict):
            return [content]
    content = event.get("content")
    if isinstance(content, list):
        return content
    return []


def stage_tokens(event: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for key in ("stage", "workflow_stage", "stage_id"):
        raw = event.get(key)
        if isinstance(raw, str) and raw.strip():
            tokens.append(raw.strip())
    if event.get("type") == "tool_use" and isinstance(event.get("name"), str):
        tokens.append(str(event["name"]))
    for block in _content_blocks(event):
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use" and isinstance(block.get("name"), str):
            tokens.append(str(block["name"]))
        raw = block.get("stage")
        if isinstance(raw, str) and raw.strip():
            tokens.append(raw.strip())
    return tokens


def recover_stages(events: list[dict[str, Any]]) -> list[str]:
    stages: list[str] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        for token in stage_tokens(ev):
            stages.append(token)
    return stages


def match_registry(
    stages: list[str],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    for cand in candidates:
        cand_stages = cand.get("stages")
        if not isinstance(cand_stages, list):
            continue
        as_str = [str(s) for s in cand_stages]
        if as_str == stages:
            return {
                "matched": True,
                "candidate_id": cand.get("id"),
                "candidate_name": cand.get("name"),
                "family": cand.get("family"),
            }
    return {
        "matched": False,
        "candidate_id": None,
        "candidate_name": None,
        "family": None,
        "reason": "no-h-family-stage-sequence-match",
    }


match_h_family = match_registry
