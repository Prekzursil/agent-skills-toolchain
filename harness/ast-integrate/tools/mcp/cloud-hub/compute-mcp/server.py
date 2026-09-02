#!/usr/bin/env python3
"""Compute MCP -- one normalized ``compute_*`` verb set over RunPod, OVH, and
Lightning AI.

A thin FastMCP server (tool names PRE-NAMESPACED ``compute_*`` so the cloud-hub
collision-prefix never fires) that dispatches DIRECTLY to each provider's API --
the hub stays a passthrough. Ten verbs give a single, provider-agnostic GPU
lifecycle: provision, exec, logs, pull, push, teardown, status, ls, cost,
catalog. A box is addressed by an opaque handle
(``compute://provider/kind/ident``) returned by provision.

GPU cost awareness: provision / exec start billable compute that bills per
second or hour while it runs. Preview with ``dry_run=true``; always
``compute_teardown`` when done (``terminate=true`` + ``confirm=true`` deletes).
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_HUB = os.path.dirname(_HERE)  # tools/mcp/cloud-hub
_SHARED = os.path.join(os.path.dirname(_HUB), "_shared")  # tools/mcp/_shared
for _p in (_HERE, _HUB, _SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import dispatch  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("compute")


def _json(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def compute_provision(
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
) -> str:
    """Provision a GPU/CPU box on a provider (runpod | ovh | lightning).

    Maps one param set onto each provider: gpu becomes RunPod gpuTypeIds / OVH
    flavorId / Lightning machine; image becomes imageName / imageId; region
    becomes dataCenterIds / OVH region; template becomes RunPod templateId;
    ports is a comma-separated list (RunPod, e.g. '8888/http,22/tcp'); project
    is the OVH Public Cloud serviceName; teamspace is the Lightning teamspace;
    ssh_key is the OVH sshKeyId. Returns a compute:// handle for the other verbs.

    COST: starts billable compute (per-second on RunPod/Lightning, hourly on
    OVH). Set dry_run=true to return the exact request WITHOUT creating anything.
    """
    return _json(
        dispatch.provision(
            provider,
            gpu=gpu,
            image=image,
            region=region,
            name=name,
            gpu_count=gpu_count,
            disk_gb=disk_gb,
            ports=ports,
            template=template,
            project=project,
            teamspace=teamspace,
            ssh_key=ssh_key,
            account=account,
            dry_run=dry_run,
        )
    )


@mcp.tool()
def compute_exec(handle: str, command: str, account: str = "") -> str:
    """Run a shell command on a provisioned box; returns stdout/stderr/exit_code.

    RunPod/OVH run it over SSH (needs the box to expose a public IP + SSH);
    Lightning runs it inside the Studio via the SDK. Pass the compute:// handle
    from compute_provision.
    """
    return _json(dispatch.exec_(handle, command, account=account))


@mcp.tool()
def compute_logs(handle: str, lines: int = 200, account: str = "") -> str:
    """Best-effort recent logs for a box (tails syslog/journal over SSH).

    Honest note: none of the three providers exposes a compute log-stream API,
    so this is a best-effort SSH tail (RunPod/OVH) or a pointer to compute_exec
    inside a Lightning Studio.
    """
    return _json(dispatch.logs(handle, lines=lines, account=account))


@mcp.tool()
def compute_pull(
    handle: str, remote_path: str, local_path: str, via: str = "", account: str = ""
) -> str:
    """Download a file from a box to a local path.

    Mechanism is auto-selected: an rclone remote path ('remote:sub/path') uses
    the local rclone RC daemon; otherwise scp over the box's SSH endpoint. Force
    it with via='scp' or via='rclone'. Lightning has no SDK download -- use an
    rclone remote or the Studio UI.
    """
    return _json(
        dispatch.pull(handle, remote_path, local_path, via=via, account=account)
    )


@mcp.tool()
def compute_push(
    handle: str, local_path: str, remote_path: str, via: str = "", account: str = ""
) -> str:
    """Upload a local file to a box.

    Mechanism is auto-selected: an rclone remote path uses the rclone RC daemon;
    otherwise scp (RunPod/OVH) or Studio.upload_file (Lightning). Force it with
    via='scp' or via='rclone'.
    """
    return _json(
        dispatch.push(handle, local_path, remote_path, via=via, account=account)
    )


@mcp.tool()
def compute_teardown(
    handle: str,
    terminate: bool = False,
    confirm: bool = False,
    dry_run: bool = False,
    account: str = "",
) -> str:
    """Stop a box, or delete it with terminate=true (bills stop on delete).

    Default (terminate=false) stops billing where the provider supports it
    (RunPod stop, Lightning stop; OVH has no stop-without-billing and returns a
    note). terminate=true is IRREVERSIBLE and requires confirm=true -- without
    it the call is refused with a 'would' preview. dry_run=true previews the
    request without calling.
    """
    return _json(
        dispatch.teardown(
            handle,
            terminate=terminate,
            confirm=confirm,
            dry_run=dry_run,
            account=account,
        )
    )


@mcp.tool()
def compute_status(handle: str, account: str = "") -> str:
    """Get a box's current state (normalized 'state' + the raw provider object)."""
    return _json(dispatch.status(handle, account=account))


@mcp.tool()
def compute_ls(
    provider: str, project: str = "", teamspace: str = "", account: str = ""
) -> str:
    """List boxes on a provider (runpod | ovh | lightning).

    OVH needs project (the Public Cloud serviceName, or set OVH_CLOUD_PROJECT_ID);
    Lightning needs teamspace to enumerate studios.
    """
    return _json(
        dispatch.ls(provider, project=project, teamspace=teamspace, account=account)
    )


@mcp.tool()
def compute_cost(provider: str, project: str = "", account: str = "") -> str:
    """Report account balance / current spend for a provider.

    RunPod returns clientBalance + currentSpendPerHr (USD); OVH returns credit
    balance + the project's current usage (EUR); Lightning reports cost only on
    its dashboard (honest note, no public balance API).
    """
    return _json(dispatch.cost(provider, project=project, account=account))


@mcp.tool()
def compute_catalog(
    provider: str, region: str = "", project: str = "", account: str = ""
) -> str:
    """List the GPU/flavor/machine catalog for a provider.

    RunPod lists GPU types; OVH lists flavors (filter with region) + the
    project's regions (needs project); Lightning lists Studio machine types.
    """
    return _json(
        dispatch.catalog(provider, region=region, project=project, account=account)
    )


if __name__ == "__main__":
    mcp.run()
