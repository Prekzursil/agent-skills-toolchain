#!/usr/bin/env python3
"""Provider adapter registry for the compute layer.

``_http`` is imported first so ``providers._http`` is bound before the adapters
(which import ``SshTarget`` from ``transfer``, whose rclone path lazily imports
``providers._http``) load -- keeping the import graph acyclic.
"""

from __future__ import annotations

from . import _http, lightning, ovh, runpod

# provider id -> adapter module. Each exposes provision/status/ls/teardown/
# cost/catalog; runpod+ovh add ssh_target; lightning adds exec_/push/pull.
PROVIDERS = {"runpod": runpod, "ovh": ovh, "lightning": lightning}

__all__ = ["PROVIDERS", "_http", "lightning", "ovh", "runpod"]
