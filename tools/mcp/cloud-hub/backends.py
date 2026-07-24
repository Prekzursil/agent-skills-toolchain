#!/usr/bin/env python3
"""Backend registry for the cloud-hub MCP multiplexer.

Each entry describes ONE fronted cloud-infrastructure MCP server: its short id,
the collision prefix used *only* when a tool name clashes across backends, the
exact stdio launch argv, the per-backend tool-cache filename, any environment
overrides layered on top of the inherited ``os.environ``, and its multi-account
policy (see ``accounts.py``).

Windows launch note: the hub's ``_spawn`` runs argv directly (no shell), so the
``npx``/``uvx`` launchers -- which are ``.cmd`` shims -- MUST go through
``cmd /c``. The two locally-built wrappers (Modal, Lightning) and the rclone
launcher are real Python entry points, so they run under the hub's own
interpreter directly.

Keeping this as plain data (a frozen dataclass list) makes the planner in
``registry.py`` and the account layer trivially unit-testable without touching
the filesystem or spawning a single child process.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Mapping

from accounts import AccountPolicy, CliProfileSpec

HERE = os.path.dirname(os.path.abspath(__file__))

# The interpreter the hub runs under fronts the two built wrappers + the rclone
# launcher, so they inherit exactly the environment (and packages: mcp/fastmcp,
# modal, lightning_sdk) available to the hub process.
PYTHON = sys.executable
RCLONE_LAUNCH = os.path.join(HERE, "rclone_launch.py")
MODAL_SERVER = os.path.join(HERE, "modal-mcp", "server.py")
LIGHTNING_SERVER = os.path.join(HERE, "lightning-mcp", "server.py")
# Locally-built FastMCP wrapper: normalized compute_* verbs that dispatch
# directly to the RunPod / OVH / Lightning provider APIs (hub stays passthrough).
COMPUTE_SERVER = os.path.join(HERE, "compute-mcp", "server.py")
DATABRICKS_SERVER = os.path.join(HERE, "databricks-mcp", "server.py")
# Locally-built FastMCP wrapper over Phylo's reverse-engineered Biomni Lab REST
# API (api.phylo.bio/v2). Bearer token per account (BIOMNI_TOKEN); stdlib-only.
BIOMNI_SERVER = os.path.join(HERE, "biomni-mcp", "server.py")
# Vendored TS MCP (hlebtkachenko/ovhcloud-mcp): built to dist/ via
# `npm ci && npm run build` in ovh-mcp/. node is a real .exe but resolved
# through `cmd /c` so PATH lookup matches the npx/uvx launchers on Windows.
OVH_SERVER = os.path.join(HERE, "ovh-mcp", "dist", "index.js")

# rclone-mcp is a client of a local rclone RC daemon.
RCLONE_RC_ADDR = "localhost:5572"


@dataclass(frozen=True)
class BackendSpec:
    """Immutable description of one fronted MCP backend."""

    id: str
    label: str
    prefix: str
    cmd: tuple[str, ...]
    cache: str
    env: Mapping[str, str] = field(default_factory=dict)
    can_enumerate_offline: bool = True
    note: str = ""
    account: AccountPolicy | None = None

    def child_env(self) -> dict[str, str]:
        """Full child environment: inherit os.environ, then layer overrides.

        The hub layers the ACTIVE account's env on top of this at spawn time
        (see ``hub.RuntimeBackend``), so per-account credentials win over both
        the inherited environment and these static overrides.
        """
        merged = dict(os.environ)
        merged.update(self.env)
        return merged


# ---- Azure / gcloud CLI profile specs (cli-mode account switching) ---------
# Both CLIs are their own source of truth for "accounts": Azure subscriptions
# and gcloud named configurations. list emits one name per line; current emits
# the active name; activate/create/delete substitute {name}.
_AZURE_CLI = CliProfileSpec(
    list_cmd=("az", "account", "list", "--query", "[].name", "-o", "tsv"),
    current_cmd=("az", "account", "show", "--query", "name", "-o", "tsv"),
    activate_cmd=("az", "account", "set", "--subscription", "{name}"),
    add_cmd=None,
    remove_cmd=None,
    add_hint="run `az login` to add a subscription/tenant",
    remove_hint="run `az logout` to remove an account",
)
_GCLOUD_CLI = CliProfileSpec(
    list_cmd=("gcloud", "config", "configurations", "list", "--format=value(name)"),
    current_cmd=(
        "gcloud",
        "config",
        "configurations",
        "list",
        "--filter=is_active:true",
        "--format=value(name)",
    ),
    activate_cmd=("gcloud", "config", "configurations", "activate", "{name}"),
    add_cmd=("gcloud", "config", "configurations", "create", "{name}"),
    remove_cmd=("gcloud", "config", "configurations", "delete", "{name}", "--quiet"),
)


def default_backends() -> list[BackendSpec]:
    """The cloud backends fronted by the hub (order = merge order)."""
    return [
        BackendSpec(
            id="runpod",
            label="RunPod (@runpod/mcp-server)",
            prefix="rp",
            cmd=("cmd", "/c", "npx", "-y", "@runpod/mcp-server@latest"),
            cache="runpod.json",
            can_enumerate_offline=False,
            note="needs RUNPOD_API_KEY; manages pods/endpoints/templates/volumes",
            account=AccountPolicy(
                platform="runpod",
                mode="env",
                seed_env=("RUNPOD_API_KEY",),
                label="RunPod",
            ),
        ),
        BackendSpec(
            id="azure",
            label="Azure (@azure/mcp)",
            prefix="az",
            cmd=("cmd", "/c", "npx", "-y", "@azure/mcp@latest", "server", "start"),
            cache="azure.json",
            can_enumerate_offline=False,
            note="inherits `az login`; account = Azure subscription (cli-profile)",
            account=AccountPolicy(
                platform="azure", mode="cli", cli=_AZURE_CLI, label="Azure"
            ),
        ),
        BackendSpec(
            id="gcloud",
            label="Google Cloud (@google-cloud/gcloud-mcp)",
            prefix="gc",
            cmd=("cmd", "/c", "npx", "-y", "@google-cloud/gcloud-mcp"),
            cache="gcloud.json",
            can_enumerate_offline=False,
            note="inherits gcloud ADC + GOOGLE_CLOUD_PROJECT; account = gcloud "
            "configuration (cli-profile)",
            account=AccountPolicy(
                platform="gcloud", mode="cli", cli=_GCLOUD_CLI, label="Google Cloud"
            ),
        ),
        BackendSpec(
            id="kaggle",
            label="Kaggle (kaggle-mcp-server)",
            prefix="kg",
            cmd=("cmd", "/c", "uvx", "kaggle-mcp-server"),
            cache="kaggle.json",
            can_enumerate_offline=False,
            note="needs KAGGLE_USERNAME+KAGGLE_KEY or ~/.kaggle/kaggle.json; "
            "kernels + datasets + competitions",
            account=AccountPolicy(
                platform="kaggle",
                mode="env",
                seed_env=("KAGGLE_USERNAME", "KAGGLE_KEY"),
                label="Kaggle",
            ),
        ),
        BackendSpec(
            id="rclone",
            label="rclone (rclone-mcp over rcd)",
            prefix="rc",
            # A launcher that starts `rclone rcd` on :5572 if it is down, then
            # execs the rclone-mcp client (which talks to that daemon).
            cmd=(PYTHON, RCLONE_LAUNCH),
            cache="rclone.json",
            env={"RCLONE_URL": f"http://{RCLONE_RC_ADDR}"},
            can_enumerate_offline=False,
            note="needs a running `rclone rcd` (auto-started by the launcher); "
            "copy/sync/move/about across 70+ remotes",
            # No seed_env: RCLONE_URL comes from spec.env; extra accounts (other
            # rcd endpoints / remotes) are added explicitly and override it.
            account=AccountPolicy(platform="rclone", mode="env", label="rclone"),
        ),
        BackendSpec(
            id="modal",
            label="Modal (built wrapper)",
            prefix="md",
            cmd=(PYTHON, MODAL_SERVER),
            cache="modal.json",
            can_enumerate_offline=True,
            note="thin FastMCP wrapper over the `modal` CLI/SDK; needs "
            "MODAL_TOKEN_ID + MODAL_TOKEN_SECRET (or ~/.modal.toml)",
            account=AccountPolicy(
                platform="modal",
                mode="env",
                seed_env=("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"),
                label="Modal",
            ),
        ),
        BackendSpec(
            id="lightning",
            label="Lightning AI (built wrapper)",
            prefix="lg",
            cmd=(PYTHON, LIGHTNING_SERVER),
            cache="lightning.json",
            can_enumerate_offline=True,
            note="thin FastMCP wrapper over `lightning_sdk`; needs "
            "LIGHTNING_USER_ID + LIGHTNING_API_KEY",
            account=AccountPolicy(
                platform="lightning",
                mode="env",
                seed_env=("LIGHTNING_USER_ID", "LIGHTNING_API_KEY"),
                label="Lightning AI",
            ),
        ),
        BackendSpec(
            id="ovh",
            label="OVHcloud (hlebtkachenko/ovhcloud-mcp)",
            prefix="ov",
            cmd=("cmd", "/c", "node", OVH_SERVER),
            cache="ovh.json",
            can_enumerate_offline=True,
            note="vendored TS MCP (node dist/index.js; `npm install && npm run "
            "build` in ovh-mcp/ once). 27 tools: VPS, DNS, billing, SSH, API "
            "explorer (ovh_api_raw reaches Public Cloud instances too). "
            "Region + creds are PER ACCOUNT: each ov account bundles "
            "OVH_ENDPOINT (ovh-eu|ovh-ca|ovh-us) + OVH_APPLICATION_KEY/"
            "SECRET/CONSUMER_KEY (or OAuth2 OVH_CLIENT_ID/SECRET), so "
            "`ov_account_switch ca|eu|us` flips region AND credentials.",
            account=AccountPolicy(
                platform="ovh",
                mode="env",
                seed_env=(
                    "OVH_APPLICATION_KEY",
                    "OVH_APPLICATION_SECRET",
                    "OVH_CONSUMER_KEY",
                ),
                label="OVHcloud",
            ),
        ),
        BackendSpec(
            id="compute",
            label="Compute (unified)",
            prefix="cp",
            cmd=(PYTHON, COMPUTE_SERVER),
            cache="compute.json",
            can_enumerate_offline=True,
            note="normalized compute_* verbs over RunPod/OVH/Lightning; "
            "dispatches to provider APIs",
            account=None,
        ),
        BackendSpec(
            id="databricks",
            label="Databricks",
            prefix="db",
            cmd=(PYTHON, DATABRICKS_SERVER),
            cache="databricks.json",
            can_enumerate_offline=True,
            note="databricks-sdk wrapper; DATABRICKS_HOST + (CLIENT_ID/_SECRET "
            "or TOKEN)",
            account=AccountPolicy(
                platform="databricks",
                mode="env",
                seed_env=("DATABRICKS_HOST", "DATABRICKS_TOKEN"),
                label="Databricks",
            ),
        ),
        BackendSpec(
            id="biomni",
            label="Biomni Lab (Phylo api.phylo.bio/v2)",
            prefix="bm",
            cmd=(PYTHON, BIOMNI_SERVER),
            cache="biomni.json",
            can_enumerate_offline=True,
            note="thin FastMCP wrapper over Phylo's reverse-engineered Biomni Lab "
            "REST API; drives the HOSTED biomni.phylo.bio far past its official "
            "10-tool connector -- effort (model_profile standard|fast|premium), "
            "skill + @-resource attach, live HPC/GPU/process introspection, usage/"
            "billing, and a raw escape hatch. Each biomni account is a BIOMNI_TOKEN "
            "bundle (Bearer from a signed-in session; no API-key product yet), so "
            "bm_account_switch|cycle rotates between the user's Biomni accounts "
            "(email-labelled) -- pair with bm_billing_balance to rotate before one "
            "runs dry.",
            account=AccountPolicy(
                platform="biomni",
                mode="env",
                seed_env=("BIOMNI_TOKEN",),
                label="Biomni Lab",
            ),
        ),
        BackendSpec(
            id="aws",
            label="AWS (mcp-proxy-for-aws -> managed AWS MCP Server)",
            prefix="aws",
            cmd=(
                "cmd",
                "/c",
                "uvx",
                "mcp-proxy-for-aws@1.6.4",
                "https://aws-mcp.eu-central-1.api.aws/mcp",
            ),
            cache="aws.json",
            can_enumerate_offline=False,
            note="thin local stdio SigV4 proxy to the managed AWS MCP Server (the "
            "GA successor to the deprecated aws-api-mcp-server): call_aws + "
            "run_script + live AWS docs/skills + CloudTrail agent attribution. "
            "Profile and region are PER ACCOUNT via AWS_PROFILE + AWS_REGION env "
            "(no --profile/--region args -- the proxy falls back to AWS_PROFILE and "
            "signs with AWS_REGION), so aws_account_switch flips the Bolt IAM "
            "Identity Center profile; creds resolve from the local SSO cache "
            "(`aws sso login`) and refresh per request with NO respawn. Pin "
            ">=1.6.0 (Windows credential_process stdio-hang fix #293). Fallback if "
            "the managed endpoint is org-blocked: awslabs.aws-api-mcp-server "
            "(local boto3, deprecated).",
            account=AccountPolicy(
                platform="aws",
                mode="env",
                seed_env=("AWS_PROFILE", "AWS_REGION"),
                label="AWS",
            ),
        ),
    ]
