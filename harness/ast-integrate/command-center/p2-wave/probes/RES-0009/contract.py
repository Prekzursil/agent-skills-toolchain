"""Validate RES-0009 research record and overclaim mutants."""
from __future__ import annotations

import copy
import json
from typing import Any

from constants import (
    BLOCK_STDERR,
    INJECT_MARKER,
    NOT_DELIVERING,
    SENTINEL,
    SHORT_SENTINEL,
    UNIT_ID,
)

RAIL_KEYS = ("kind", "path", "sha256", "bytes")
PAYLOAD_KEYS = ("event", "raw", "sha256", "hook_event_name")


def text_of(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=True)


def validate_artifact(doc: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["artifact-not-object"]
    if doc.get("unit_id") != UNIT_ID:
        errs.append(f"unit_id:{doc.get('unit_id')}")
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        errs.append(f"self-declared:{state}")
    blob = text_of(doc)
    if SENTINEL not in blob:
        errs.append("catalog-sentinel-absent")
    if SHORT_SENTINEL not in blob:
        errs.append("short-sentinel-absent")
    rails = doc.get("source_rails") or []
    if not isinstance(rails, list) or len(rails) < 2:
        errs.append("need-two-source-rails")
    kinds = {str(row.get("kind") or "") for row in rails if isinstance(row, dict)}
    if "cli-hooks-reference" not in kinds or "sdk-hooks-reference" not in kinds:
        errs.append("rails-kinds-missing")
    for row in rails:
        if not isinstance(row, dict):
            errs.append("rail-not-object")
            continue
        for key in RAIL_KEYS:
            if not row.get(key):
                errs.append(f"rail-missing-{key}")
    cli = doc.get("cli_events") or []
    sdk = doc.get("sdk_events") or []
    if not isinstance(cli, list) or len(cli) < 15:
        errs.append(f"cli-events-too-few:{len(cli) if isinstance(cli, list) else 0}")
    if not isinstance(sdk, list) or len(sdk) < 8:
        errs.append(f"sdk-events-too-few:{len(sdk) if isinstance(sdk, list) else 0}")
    payloads = doc.get("captured_raw_payloads") or []
    if not isinstance(payloads, list):
        errs.append("payloads-not-list")
        payloads = []
    by_event: dict[str, dict[str, Any]] = {}
    for row in payloads:
        if not isinstance(row, dict):
            errs.append("payload-not-object")
            continue
        for key in PAYLOAD_KEYS:
            if not row.get(key):
                errs.append(f"payload-missing-{key}")
        event = str(row.get("event") or "")
        by_event[event] = row
        if row.get("hook_event_name") != event:
            errs.append(f"payload-hook_event_name-mismatch:{event}")
        raw = str(row.get("raw") or "")
        if "hook_event_name" not in raw or event not in raw:
            errs.append(f"payload-raw-missing-event:{event}")
    for event in cli:
        if event not in by_event:
            errs.append(f"missing-raw-payload:{event}")
    controls = doc.get("controls") or {}
    if not isinstance(controls, dict):
        errs.append("controls-missing")
        controls = {}
    block = controls.get("block") or {}
    inject = controls.get("inject") or {}
    timeout = controls.get("timeout") or {}
    if int(block.get("returncode") or 0) != 2:
        errs.append("block-returncode-not-2")
    if BLOCK_STDERR not in str(block.get("stderr") or ""):
        errs.append("block-stderr-marker-absent")
    if block.get("pre_tool_use_blocked") is not True:
        errs.append("block-pretooluse-not-blocked")
    if block.get("session_start_blocked") is True:
        errs.append("block-sessionstart-false-positive")
    inj_stdout = str(inject.get("stdout") or "")
    if INJECT_MARKER not in inj_stdout:
        errs.append("inject-marker-absent")
    if "hookSpecificOutput" not in inj_stdout:
        errs.append("inject-envelope-absent")
    if inject.get("returncode") not in (0, "0"):
        errs.append("inject-returncode-not-0")
    if timeout.get("timed_out") is not True:
        errs.append("timeout-not-observed")
    elapsed = float(timeout.get("elapsed_s") or 99)
    sleep_s = float(timeout.get("sleep_s") or 30)
    if elapsed >= sleep_s:
        errs.append("timeout-waited-full-sleep")
    client = doc.get("client_discovery") or {}
    if client.get("live_session_fired") is True and not client.get("binary"):
        errs.append("overclaim-live-session-without-binary")
    drift = doc.get("naming_drift") or {}
    if not isinstance(drift, dict) or "cli_only" not in drift or "sdk_only" not in drift:
        errs.append("naming-drift-missing")
    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 4:
        errs.append("claims-too-few")
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        if not claim.get("source_lineage"):
            errs.append(f"{claim.get('id')}:missing-source-lineage")
        statement = str(claim.get("statement") or "")
        if str(claim.get("verdict") or "") == "CONFIRMED" and "live Claude Code session" in statement:
            if not client.get("binary"):
                errs.append(f"{claim.get('id')}:confirmed-unfired-client")
    return errs


def mutant_drop_payload(doc: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(doc)
    rows = list(mutant.get("captured_raw_payloads") or [])
    if rows:
        mutant["captured_raw_payloads"] = rows[1:]
    return mutant


def mutant_drop_timeout(doc: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(doc)
    controls = dict(mutant.get("controls") or {})
    controls.pop("timeout", None)
    mutant["controls"] = controls
    return mutant


def mutant_live_client_overclaim(doc: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(doc)
    client = dict(mutant.get("client_discovery") or {})
    client["binary"] = None
    client["live_session_fired"] = True
    mutant["client_discovery"] = client
    return mutant
