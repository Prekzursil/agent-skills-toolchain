#!/usr/bin/env python3
"""RunPod adapter -- Pods over the REST v1 API (+ GraphQL for the balance).

Each function is a thin, honest passthrough to ``rest.runpod.io/v1`` (or the
GraphQL endpoint for cost): it maps the normalized compute params onto RunPod's
request shape and wraps the response in the shared envelope. Nothing here
retries or polls -- a Pod bills per-second while it runs, so lifecycle stays
explicit and caller-driven.
"""

from __future__ import annotations

from typing import Any

import envelope
import handles
from providers import _http
from transfer import SshTarget

_BALANCE_QUERY = "query { myself { clientBalance currentSpendPerHr } }"


def _state(pod: dict) -> str:
    return str(pod.get("desiredStatus") or pod.get("lastStatus") or "unknown")


def _build_body(spec: dict) -> dict:
    """Map normalized provision params onto the RunPod ``POST /pods`` body."""
    body: dict[str, Any] = {
        "imageName": spec.get("image", ""),
        "gpuCount": spec.get("gpu_count", 1),
        "containerDiskInGb": spec.get("disk_gb", 20),
    }
    if spec.get("gpu"):
        body["gpuTypeIds"] = [spec["gpu"]]
    if spec.get("name"):
        body["name"] = spec["name"]
    if spec.get("ports"):
        body["ports"] = spec["ports"]
    if spec.get("region"):
        body["dataCenterIds"] = [spec["region"]]
    if spec.get("template"):
        body["templateId"] = spec["template"]
    if spec.get("env"):
        body["env"] = spec["env"]
    return body


def provision(env: dict, spec: dict, dry_run: bool) -> dict:
    """Create a Pod (``POST /pods``); ``dry_run`` returns the uncalled request."""
    body = _build_body(spec)
    if dry_run:
        return envelope.dry_run(
            "runpod", "provision", {"method": "POST", "path": "/pods", "body": body}
        )
    status, data = _http.runpod_rest(env, "POST", "/pods", body)
    if status in (200, 201) and isinstance(data, dict) and data.get("id"):
        handle = handles.make("runpod", str(data["id"]))
        return envelope.ok(
            "runpod",
            handle=handle.format(),
            kind=handle.kind,
            id=str(data["id"]),
            state=_state(data),
            raw=data,
        )
    return envelope.err("runpod", f"create pod failed (HTTP {status})", raw=data)


def status(env: dict, handle: handles.Handle) -> dict:
    """Fetch one Pod (``GET /pods/{id}``)."""
    st, data = _http.runpod_rest(env, "GET", f"/pods/{handle.ident}")
    if st == 200 and isinstance(data, dict):
        return envelope.ok(
            "runpod",
            handle=handle.format(),
            kind=handle.kind,
            id=handle.ident,
            state=_state(data),
            raw=data,
        )
    return envelope.err("runpod", f"get pod failed (HTTP {st})", raw=data)


def ls(env: dict, opts: dict) -> dict:
    """List Pods (``GET /pods``)."""
    st, data = _http.runpod_rest(env, "GET", "/pods")
    items = data if isinstance(data, list) else (data or {}).get("pods", data)
    if st == 200:
        rows = items if isinstance(items, list) else []
        return envelope.ok("runpod", kind="pod", count=len(rows), items=rows)
    return envelope.err("runpod", f"list pods failed (HTTP {st})", raw=data)


def _terminate(env: dict, handle: handles.Handle, confirm: bool, dry_run: bool) -> dict:
    req = {"method": "DELETE", "path": f"/pods/{handle.ident}"}
    if dry_run:
        return envelope.dry_run("runpod", "terminate", req)
    if not confirm:
        return envelope.needs_confirm("runpod", "terminate", req)
    st, data = _http.runpod_rest(env, "DELETE", f"/pods/{handle.ident}")
    if st in (200, 204):
        return envelope.ok(
            "runpod", handle=handle.format(), state="terminated", raw=data
        )
    return envelope.err(
        "runpod", f"terminate failed (HTTP {st})", handle=handle.format(), raw=data
    )


def teardown(
    env: dict, handle: handles.Handle, terminate: bool, confirm: bool, dry_run: bool
) -> dict:
    """Stop (``POST /pods/{id}/stop``) or terminate (``DELETE /pods/{id}``)."""
    if terminate:
        return _terminate(env, handle, confirm, dry_run)
    req = {"method": "POST", "path": f"/pods/{handle.ident}/stop"}
    if dry_run:
        return envelope.dry_run("runpod", "stop", req)
    st, data = _http.runpod_rest(env, "POST", f"/pods/{handle.ident}/stop")
    if st in (200, 201):
        state = _state(data) if isinstance(data, dict) else "stopped"
        return envelope.ok("runpod", handle=handle.format(), state=state, raw=data)
    return envelope.err(
        "runpod", f"stop failed (HTTP {st})", handle=handle.format(), raw=data
    )


def cost(env: dict, opts: dict) -> dict:
    """Account balance + current spend/hr via GraphQL ``myself``."""
    st, data = _http.runpod_graphql(env, _BALANCE_QUERY)
    payload = data if isinstance(data, dict) else {}
    me = (payload.get("data") or {}).get("myself")
    if st == 200 and isinstance(me, dict):
        return envelope.ok(
            "runpod",
            balance=me.get("clientBalance"),
            currency="USD",
            spend_per_hr=me.get("currentSpendPerHr"),
            note="RunPod bills per-second while pods/endpoints run.",
        )
    return envelope.err("runpod", f"balance query failed (HTTP {st})", raw=data)


def catalog(env: dict, opts: dict) -> dict:
    """List GPU types (``GET /gpuTypes``)."""
    st, data = _http.runpod_rest(env, "GET", "/gpuTypes")
    if st == 200:
        rows = data if isinstance(data, list) else (data or {}).get("gpuTypes", [])
        return envelope.ok(
            "runpod", kind="gpuType", count=len(rows or []), items=rows or []
        )
    return envelope.err("runpod", f"gpu catalog failed (HTTP {st})", raw=data)


def ssh_target(env: dict, handle: handles.Handle) -> tuple[SshTarget | None, str]:
    """Resolve the Pod's public SSH endpoint (publicIp + portMappings['22'])."""
    st, data = _http.runpod_rest(env, "GET", f"/pods/{handle.ident}")
    if st != 200 or not isinstance(data, dict):
        return None, f"could not read pod {handle.ident} (HTTP {st})"
    ip = data.get("publicIp") or ""
    port = (data.get("portMappings") or {}).get("22")
    if not ip or not port:
        return None, (
            "pod has no public SSH mapping yet (need a public IP + port 22); "
            "poll compute_status until it is RUNNING with ports exposed"
        )
    return SshTarget(host=str(ip), port=int(port), user="root"), ""
