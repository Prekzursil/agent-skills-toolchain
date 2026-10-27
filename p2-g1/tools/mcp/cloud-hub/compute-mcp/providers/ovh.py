#!/usr/bin/env python3
"""OVHcloud adapter -- Public Cloud instances over the signed OVH API.

OVH has no purpose-built GPU-instance MCP tool, so this drives the raw
``/cloud/project/{serviceName}/instance`` surface via the signed
``providers._http.ovh_request``. The Public Cloud project (``serviceName``) is
resolved from an explicit ``project`` arg, then ``OVH_CLOUD_PROJECT_ID``, then a
single-project auto-discovery -- ambiguity is surfaced, never guessed.

Honesty note: OVH has no "stop without billing" for a Public Cloud instance
(you either keep paying or terminate/shelve), so ``compute_teardown`` without
``terminate=True`` returns a clear note rather than pretending it stopped.
"""

from __future__ import annotations

from typing import Any

import envelope
import handles
from providers import _http
from transfer import SshTarget


def resolve_service(env: dict, project: str) -> tuple[str, str]:
    """Resolve the Public Cloud serviceName -> (serviceName, error_note)."""
    if project:
        return project, ""
    if env.get("OVH_CLOUD_PROJECT_ID"):
        return env["OVH_CLOUD_PROJECT_ID"], ""
    st, data = _http.ovh_request(env, "GET", "/cloud/project")
    ids = data if isinstance(data, list) else []
    if st == 200 and len(ids) == 1:
        return str(ids[0]), ""
    if st == 200 and len(ids) > 1:
        return "", f"multiple OVH projects {ids}; pass project=<serviceName>"
    return (
        "",
        f"could not resolve an OVH project (HTTP {st}); pass project=<serviceName>",
    )


def _parts(handle: handles.Handle) -> tuple[str, str]:
    p = handle.parts
    return (p[0], p[1]) if len(p) >= 2 else ("", "")


def _build_body(spec: dict) -> dict:
    body: dict[str, Any] = {
        "flavorId": spec.get("gpu", ""),
        "imageId": spec.get("image", ""),
        "region": spec.get("region", ""),
        "name": spec.get("name", "compute-instance"),
        "monthlyBilling": False,
    }
    if spec.get("ssh_key"):
        body["sshKeyId"] = spec["ssh_key"]
    return body


def provision(env: dict, spec: dict, dry_run: bool) -> dict:
    """Create a Public Cloud instance (``POST /cloud/project/{sn}/instance``)."""
    sn, note = resolve_service(env, spec.get("project", ""))
    if not sn:
        return envelope.err("ovh", note)
    body = _build_body(spec)
    path = f"/cloud/project/{sn}/instance"
    if dry_run:
        return envelope.dry_run(
            "ovh", "provision", {"method": "POST", "path": path, "body": body}
        )
    st, data = _http.ovh_request(env, "POST", path, body)
    if st in (200, 201) and isinstance(data, dict) and data.get("id"):
        handle = handles.make("ovh", f"{sn}/{data['id']}", "instance")
        return envelope.ok(
            "ovh",
            handle=handle.format(),
            kind=handle.kind,
            id=str(data["id"]),
            state=str(data.get("status") or "BUILDING"),
            raw=data,
        )
    return envelope.err("ovh", f"create instance failed (HTTP {st})", raw=data)


def status(env: dict, handle: handles.Handle) -> dict:
    """Fetch one instance (``GET /cloud/project/{sn}/instance/{id}``)."""
    sn, iid = _parts(handle)
    if not sn or not iid:
        return envelope.err("ovh", "handle must be ovh/instance/<serviceName>/<id>")
    st, data = _http.ovh_request(env, "GET", f"/cloud/project/{sn}/instance/{iid}")
    if st == 200 and isinstance(data, dict):
        return envelope.ok(
            "ovh",
            handle=handle.format(),
            kind=handle.kind,
            id=iid,
            state=str(data.get("status") or "unknown"),
            raw=data,
        )
    return envelope.err("ovh", f"get instance failed (HTTP {st})", raw=data)


def ls(env: dict, opts: dict) -> dict:
    """List instances (``GET /cloud/project/{sn}/instance``)."""
    sn, note = resolve_service(env, opts.get("project", ""))
    if not sn:
        return envelope.err("ovh", note)
    st, data = _http.ovh_request(env, "GET", f"/cloud/project/{sn}/instance")
    if st == 200:
        rows = data if isinstance(data, list) else []
        return envelope.ok("ovh", kind="instance", count=len(rows), items=rows)
    return envelope.err("ovh", f"list instances failed (HTTP {st})", raw=data)


def teardown(
    env: dict, handle: handles.Handle, terminate: bool, confirm: bool, dry_run: bool
) -> dict:
    """Terminate an instance (``DELETE ...``); stop is a no-op honest note."""
    sn, iid = _parts(handle)
    if not sn or not iid:
        return envelope.err("ovh", "handle must be ovh/instance/<serviceName>/<id>")
    if not terminate:
        return envelope.ok(
            "ovh",
            handle=handle.format(),
            state="running",
            stopped=False,
            note="OVH has no stop-without-billing for a Public Cloud instance; "
            "terminate=true (DELETE) to stop billing, or shelve it via the API.",
        )
    path = f"/cloud/project/{sn}/instance/{iid}"
    req = {"method": "DELETE", "path": path}
    if dry_run:
        return envelope.dry_run("ovh", "terminate", req)
    if not confirm:
        return envelope.needs_confirm("ovh", "terminate", req)
    st, data = _http.ovh_request(env, "DELETE", path)
    if st in (200, 204):
        return envelope.ok("ovh", handle=handle.format(), state="terminated", raw=data)
    return envelope.err(
        "ovh", f"terminate failed (HTTP {st})", handle=handle.format(), raw=data
    )


def cost(env: dict, opts: dict) -> dict:
    """Account credit balance + the project's current usage."""
    st_bal, balance = _http.ovh_request(env, "GET", "/me/credit/balance")
    sn, _note = resolve_service(env, opts.get("project", ""))
    usage: Any = None
    if sn:
        _st, usage = _http.ovh_request(env, "GET", f"/cloud/project/{sn}/usage/current")
    return envelope.ok(
        "ovh",
        currency="EUR",
        balance=balance if st_bal == 200 else None,
        usage_current=usage,
        note="OVH GPU instances bill hourly; balances are credit-voucher names "
        "(GET /me/credit/balance/{name} for detail).",
    )


def catalog(env: dict, opts: dict) -> dict:
    """List flavors (optionally filtered by region) + the project's regions."""
    sn, note = resolve_service(env, opts.get("project", ""))
    if not sn:
        return envelope.err("ovh", note)
    query = {"region": opts["region"]} if opts.get("region") else None
    st, flavors = _http.ovh_request(
        env, "GET", f"/cloud/project/{sn}/flavor", query=query
    )
    _st, regions = _http.ovh_request(env, "GET", f"/cloud/project/{sn}/region")
    if st == 200:
        rows = flavors if isinstance(flavors, list) else []
        return envelope.ok(
            "ovh",
            kind="flavor",
            count=len(rows),
            items=rows,
            regions=regions if isinstance(regions, list) else [],
        )
    return envelope.err("ovh", f"flavor catalog failed (HTTP {st})", raw=flavors)


def _public_ipv4(instance: dict) -> str:
    for addr in instance.get("ipAddresses") or []:
        if isinstance(addr, dict) and addr.get("version") == 4:
            if addr.get("type") in ("public", None):
                return str(addr.get("ip") or "")
    return ""


def ssh_target(env: dict, handle: handles.Handle) -> tuple[SshTarget | None, str]:
    """Resolve the instance's public IPv4 + image login user for ssh/scp."""
    sn, iid = _parts(handle)
    if not sn or not iid:
        return None, "handle must be ovh/instance/<serviceName>/<id>"
    st, data = _http.ovh_request(env, "GET", f"/cloud/project/{sn}/instance/{iid}")
    if st != 200 or not isinstance(data, dict):
        return None, f"could not read instance {iid} (HTTP {st})"
    ip = _public_ipv4(data)
    if not ip:
        return None, "instance has no public IPv4 yet; poll compute_status"
    user = (data.get("image") or {}).get("user") or "ubuntu"
    return SshTarget(host=ip, port=22, user=str(user)), ""
