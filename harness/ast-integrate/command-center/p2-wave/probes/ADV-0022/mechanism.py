"""ADV-0022 live capability-escape measurement plus ARC-0081 contrast."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from common import ARC_MODEL, ATTEMPTS, REPO  # noqa: E402
from host import run_entry  # noqa: E402
from sandbox import Sandbox  # noqa: E402

_ARC = str((REPO / "command-center" / "p2-wave" / "probes" / "ARC-0081").resolve())
if _ARC not in sys.path:
    sys.path.insert(0, _ARC)

from model import evaluate_request, pset, req, stmt  # noqa: E402


def _tokens_to_pset(subject: str, tokens: list[str], *, loopback_hostport: str) -> dict[str, Any]:
    rows = []
    for token in tokens:
        if token == "Read":
            rows.append(stmt("grant", "tool", "Read"))
        elif token == "Bash":
            rows.append(stmt("grant", "tool", "Bash"))
            rows.append(stmt("grant", "subprocess", "python3"))
            rows.append(stmt("grant", "egress", loopback_hostport))
        elif token == "Write":
            rows.append(stmt("grant", "tool", "Write"))
            rows.append(stmt("grant", "path", "/sandbox/outside/escape.txt", "write"))
        elif token == "Glob":
            rows.append(stmt("grant", "tool", "Glob"))
    if not rows:
        rows.append(stmt("grant", "tool", "Read"))
    return pset(subject, *rows)


REQUESTS = {
    "spawn": req("subprocess", "python3"),
    "network": None,  # filled with concrete host:port
    "write-outside-root": req("path", "/sandbox/outside/escape.txt", "write"),
    "invoke-wider-sibling": req("tool", "Bash"),
}


def census(box: Sandbox, kind: str) -> dict[str, bool]:
    hits = list(box.hits.paths) if box.hits is not None else []
    if kind == "narrow":
        spawn = box.paths["narrow_spawn"].is_file()
        outside = box.paths["outside_file"].is_file()
        sibling = box.paths["sibling_beacon"].is_file()
        network = any(p.startswith("/adv0022-loopback") for p in hits)
    else:
        spawn = box.paths["control_spawn"].is_file()
        outside = box.paths["outside_file"].is_file()
        sibling = box.paths["sibling_beacon"].is_file()
        network = any(p.startswith("/adv0022-loopback") for p in hits)
    return {
        "spawn": spawn,
        "network": network,
        "write-outside-root": outside,
        "invoke-wider-sibling": sibling,
    }


def _reset_side_effects(box: Sandbox) -> None:
    for key in ("narrow_spawn", "control_spawn", "outside_file", "sibling_beacon"):
        path = box.paths[key]
        if path.is_file():
            path.unlink()
    if box.hits is not None:
        box.hits.paths.clear()


def model_verdicts(tokens: list[str], loopback_hostport: str) -> dict[str, Any]:
    declared = _tokens_to_pset("component", tokens, loopback_hostport=loopback_hostport)
    requests = dict(REQUESTS)
    requests["network"] = req("egress", loopback_hostport)
    out: dict[str, Any] = {}
    for aid in ATTEMPTS:
        decision = evaluate_request(declared, requests[aid])
        out[aid] = {
            "outcome": decision["outcome"],
            "reason": decision["reason"],
            "would_allow_side_effect": decision["outcome"] == "GRANT",
        }
    return {"declared_tokens": tokens, "decisions": out}


def _run_one(box: Sandbox, component: Path, report: Path, kind: str) -> dict[str, Any]:
    _reset_side_effects(box)
    env = box.component_env(component, report)
    host = run_entry(component, env)
    observed = census(box, kind)
    self_report = []
    if report.is_file():
        try:
            raw = json.loads(report.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                self_report = raw
        except (OSError, json.JSONDecodeError):
            self_report = []
    attempts = []
    for aid in ATTEMPTS:
        succeeded = bool(observed[aid])
        attempts.append(
            {
                "id": aid,
                "attempted": True,
                "side_effect_observed": succeeded,
                "succeeded": succeeded,
            }
        )
    return {
        "kind": kind,
        "host": host,
        "observed": observed,
        "self_report": self_report,
        "attempts": attempts,
        "any_escape": any(observed[a] for a in ATTEMPTS),
        "all_four": all(observed[a] for a in ATTEMPTS),
    }


def measure() -> dict[str, Any]:
    with Sandbox() as box:
        host, port = box.server.server_address[:2]
        loopback_hostport = f"{host}:{port}"
        narrow = _run_one(
            box, box.paths["narrow"], box.paths["narrow_report"], "narrow"
        )
        control = _run_one(
            box, box.paths["control"], box.paths["control_report"], "control"
        )
        model_narrow = model_verdicts(
            list(narrow["host"]["manifest"]["tool_permissions"]),
            loopback_hostport,
        )
        model_wide = model_verdicts(
            list(control["host"]["manifest"]["tool_permissions"]),
            loopback_hostport,
        )
        interceptor_red = all(
            model_narrow["decisions"][a]["outcome"] == "DENY" for a in ATTEMPTS
        )
        interceptor_silent_on_control = all(
            model_wide["decisions"][a]["outcome"] == "GRANT" for a in ATTEMPTS
        )
        return {
            "sandbox_root_ephemeral": True,
            "loopback_only": True,
            "third_party_contacted": False,
            "live_credential_used": False,
            "narrow": narrow,
            "control": control,
            "model_narrow": model_narrow,
            "model_wide": model_wide,
            "choke_point_spec": ARC_MODEL,
            "choke_point_wired_into_host": False,
            "interceptor_denies_narrow": interceptor_red,
            "interceptor_allows_wide": interceptor_silent_on_control,
            "control_unimpeded": bool(control["all_four"] and control["host"]["exit_code"] == 0),
            "narrow_escaped": bool(narrow["any_escape"]),
        }
