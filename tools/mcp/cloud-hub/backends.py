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
    current_cmd=("gcloud", "config", "configurations", "list",
                 "--filter=is_active:true", "--format=value(name)"),
    activate_cmd=("gcloud", "config", "configurations", "activate", "{name}"),
    add_cmd=("gcloud", "config", "configurations", "create", "{name}"),
    remove_cmd=("gcloud", "config", "configurations", "delete", "{name}",
                "--quiet"),
)


def default_backends() -> list[BackendSpec]:
    """The seven cloud backends fronted by the hub (order = merge order)."""
    return [
        BackendSpec(
            id="runpod",
            label="RunPod (@runpod/mcp-server)",
            prefix="rp",
            cmd=("cmd", "/c", "npx", "-y", "@runpod/mcp-server@latest"),
            cache="runpod.json",
            can_enumerate_offline=False,
            note="needs RUNPOD_API_KEY; manages pods/endpoints/templates/volumes",
            account=AccountPolicy(platform="runpod", mode="env",
                                  seed_env=("RUNPOD_API_KEY",), label="RunPod"),
        ),
        BackendSpec(
            id="azure",
            label="Azure (@azure/mcp)",
            prefix="az",
            cmd=("cmd", "/c", "npx", "-y", "@azure/mcp@latest", "server", "start"),
            cache="azure.json",
            can_enumerate_offline=False,
            note="inherits `az login`; account = Azure subscription (cli-profile)",
            account=AccountPolicy(platform="azure", mode="cli", cli=_AZURE_CLI,
                                  label="Azure"),
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
            account=AccountPolicy(platform="gcloud", mode="cli", cli=_GCLOUD_CLI,
                                  label="Google Cloud"),
        ),
        BackendSpec(
            id="kaggle",
            label="Kaggle (kaggle-mcp-server)",
            prefix="kg",
            cmd=("cmd", "/c", "uvx", "kaggle-mcp-server"),
            cache="kaggle.json",
            can_enumerate_offline=False,
            note="needs KAGGLE_API_TOKEN or ~/.kaggle/kaggle.json; kernels + "
                 "datasets + competitions",
            account=AccountPolicy(platform="kaggle", mode="env",
                                  seed_env=("KAGGLE_API_TOKEN",), label="Kaggle"),
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
            account=AccountPolicy(platform="modal", mode="env",
                                  seed_env=("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"),
                                  label="Modal"),
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
            account=AccountPolicy(platform="lightning", mode="env",
                                  seed_env=("LIGHTNING_USER_ID", "LIGHTNING_API_KEY"),
                                  label="Lightning AI"),
        ),
    ]
