#!/usr/bin/env python3
"""Per-verb dispatch: parse handle -> resolve creds -> adapter -> envelope.

This is the one place that knows how each of the ten ``compute_*`` verbs maps
onto a provider adapter. RunPod/OVH ``exec``/``logs``/``pull``/``push`` go over
ssh/scp (resolving the box's SSH endpoint via the adapter's ``ssh_target``);
Lightning routes to its SDK-backed ``exec_``/``push``/``pull``. Everything comes
back through the shared :mod:`envelope`, so a bad handle or an unknown provider
is an ``ok=False`` result, never an exception.
"""

from __future__ import annotations

import functools

import accounts_bridge
import envelope
import handles
import transfer
from providers import PROVIDERS, lightning

_ACCOUNTS: accounts_bridge.ComputeAccounts | None = None


def _resolve_env(provider: str, account: str = "") -> dict:
    """Resolve a provider's credentials (cached account store). Test seam."""
    global _ACCOUNTS
    if _ACCOUNTS is None:
        _ACCOUNTS = accounts_bridge.build()
    return _ACCOUNTS.resolve_env(provider, account)


def _enveloped(fn):
    """Turn an unknown explicit ``account`` into the shared ``ok=False`` envelope.

    Keeps this module's stated contract -- "a bad handle or an unknown provider
    is an ok=False result, never an exception" -- true for a bad ACCOUNT too.
    ``_resolve_env`` now raises instead of quietly handing back the ambient
    credentials, so the refusal has to be shaped here, before any provider call.
    """

    @functools.wraps(fn)
    def _wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except accounts_bridge.UnknownAccountError as exc:
            return envelope.err("compute", str(exc))

    return _wrapped


def _parse(handle_str: str):
    """Parse a handle -> (Handle, None) or (None, error_envelope)."""
    try:
        return handles.parse(handle_str), None
    except handles.HandleError as exc:
        return None, {"ok": False, "provider": "compute", "error": str(exc)}


def _ports(ports: str) -> list[str]:
    return [p.strip() for p in ports.split(",") if p.strip()] if ports else []


@_enveloped
def provision(
    provider: str,
    gpu: str = "",
    image: str = "",
    region: str = "",
    name: str = "",
    gpu_count: int = 1,
    disk_gb: int = 20,
    ports: str = "",
    template: str = "",
    project: str = "",
    teamspace: str = "",
    ssh_key: str = "",
    account: str = "",
    dry_run: bool = False,
) -> dict:
    """Provision a box on ``provider`` (billable unless ``dry_run``)."""
    mod = PROVIDERS.get(provider)
    if mod is None:
        return envelope.err("compute", f"unknown provider {provider!r}")
    spec = {
        "gpu": gpu,
        "image": image,
        "region": region,
        "name": name,
        "gpu_count": gpu_count,
        "disk_gb": disk_gb,
        "ports": _ports(ports),
        "template": template,
        "project": project,
        "teamspace": teamspace,
        "ssh_key": ssh_key,
    }
    return mod.provision(_resolve_env(provider, account), spec, dry_run)


@_enveloped
def status(handle: str, account: str = "") -> dict:
    """Fetch the current state of a provisioned box."""
    h, err = _parse(handle)
    if err:
        return err
    return PROVIDERS[h.provider].status(_resolve_env(h.provider, account), h)


@_enveloped
def ls(
    provider: str, project: str = "", teamspace: str = "", account: str = ""
) -> dict:
    """List boxes on a provider."""
    mod = PROVIDERS.get(provider)
    if mod is None:
        return envelope.err("compute", f"unknown provider {provider!r}")
    opts = {"project": project, "teamspace": teamspace}
    return mod.ls(_resolve_env(provider, account), opts)


@_enveloped
def cost(provider: str, project: str = "", account: str = "") -> dict:
    """Report account balance / spend for a provider."""
    mod = PROVIDERS.get(provider)
    if mod is None:
        return envelope.err("compute", f"unknown provider {provider!r}")
    return mod.cost(_resolve_env(provider, account), {"project": project})


@_enveloped
def catalog(
    provider: str, region: str = "", project: str = "", account: str = ""
) -> dict:
    """List the GPU/flavor/machine catalog for a provider."""
    mod = PROVIDERS.get(provider)
    if mod is None:
        return envelope.err("compute", f"unknown provider {provider!r}")
    opts = {"region": region, "project": project}
    return mod.catalog(_resolve_env(provider, account), opts)


@_enveloped
def teardown(
    handle: str,
    terminate: bool = False,
    confirm: bool = False,
    dry_run: bool = False,
    account: str = "",
) -> dict:
    """Stop or (with ``terminate=True`` + ``confirm=True``) delete a box."""
    h, err = _parse(handle)
    if err:
        return err
    env = _resolve_env(h.provider, account)
    return PROVIDERS[h.provider].teardown(env, h, terminate, confirm, dry_run)


@_enveloped
def exec_(handle: str, command: str, account: str = "") -> dict:
    """Run a command on a box (SSH for RunPod/OVH, SDK for Lightning)."""
    h, err = _parse(handle)
    if err:
        return err
    env = _resolve_env(h.provider, account)
    if h.provider == "lightning":
        return lightning.exec_(env, h, command)
    target, note = PROVIDERS[h.provider].ssh_target(env, h)
    if target is None:
        return envelope.err(h.provider, note, handle=h.format())
    return _wrap_exec(h.provider, h.format(), transfer.ssh_run(target, command))


@_enveloped
def logs(handle: str, lines: int = 200, account: str = "") -> dict:
    """Best-effort log tail (no provider offers a compute log-stream API)."""
    h, err = _parse(handle)
    if err:
        return err
    env = _resolve_env(h.provider, account)
    note = "best-effort SSH tail; no provider API log stream for compute boxes."
    if h.provider == "lightning":
        return envelope.ok(
            "lightning",
            handle=h.format(),
            note="no API log stream; use compute_exec to tail a log inside the Studio.",
        )
    target, tnote = PROVIDERS[h.provider].ssh_target(env, h)
    if target is None:
        return envelope.err(h.provider, tnote, handle=h.format())
    cmd = (
        f"tail -n {int(lines)} /var/log/syslog 2>/dev/null || "
        f"journalctl -n {int(lines)} --no-pager 2>/dev/null || "
        f"dmesg | tail -n {int(lines)}"
    )
    res = _wrap_exec(h.provider, h.format(), transfer.ssh_run(target, cmd))
    res["note"] = note
    return res


@_enveloped
def pull(
    handle: str, remote_path: str, local_path: str, via: str = "", account: str = ""
) -> dict:
    """Download a file from a box (scp, or rclone RC for an rclone remote)."""
    return _copy("pull", handle, local_path, remote_path, via, account)


@_enveloped
def push(
    handle: str, local_path: str, remote_path: str, via: str = "", account: str = ""
) -> dict:
    """Upload a file to a box (scp/upload_file, or rclone RC for a remote)."""
    return _copy("push", handle, local_path, remote_path, via, account)


def _copy(
    direction: str,
    handle: str,
    local_path: str,
    remote_path: str,
    via: str,
    account: str,
) -> dict:
    h, err = _parse(handle)
    if err:
        return err
    env = _resolve_env(h.provider, account)
    mech = transfer.select_via(local_path, remote_path, via)
    if mech == "rclone":
        src, dst = (
            (remote_path, local_path)
            if direction == "pull"
            else (local_path, remote_path)
        )
        return _wrap_transfer(h.provider, h.format(), transfer.rclone_copy(src, dst))
    if h.provider == "lightning":
        if direction == "push":
            return lightning.push(env, h, local_path, remote_path)
        return lightning.pull(env, h, remote_path, local_path)
    target, note = PROVIDERS[h.provider].ssh_target(env, h)
    if target is None:
        return envelope.err(h.provider, note, handle=h.format())
    res = transfer.scp_copy(direction, target, local_path, remote_path)
    return _wrap_transfer(h.provider, h.format(), res)


def _wrap_exec(provider: str, handle_str: str, res: dict) -> dict:
    """Normalize an ssh_run result into an exec envelope (stdout/stderr/exit)."""
    if "exit_code" not in res:
        return envelope.err(provider, res.get("error", "ssh failed"), handle=handle_str)
    fields = {
        "stdout": res.get("stdout", ""),
        "stderr": res.get("stderr", ""),
        "exit_code": res["exit_code"],
    }
    if res.get("ok"):
        return envelope.ok(provider, handle=handle_str, **fields)
    return envelope.err(
        provider, f"command exited {res['exit_code']}", handle=handle_str, **fields
    )


def _wrap_transfer(provider: str, handle_str: str, res: dict) -> dict:
    """Normalize a scp/rclone result into a transfer envelope."""
    extra = {k: v for k, v in res.items() if k not in ("ok", "error")}
    if res.get("ok"):
        return envelope.ok(provider, handle=handle_str, **extra)
    return envelope.err(
        provider, res.get("error", "transfer failed"), handle=handle_str, **extra
    )
