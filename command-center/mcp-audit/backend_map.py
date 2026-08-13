#!/usr/bin/env python3
"""Which cloud-hub tool belongs to which BACKEND -- the classifier, separated from the census.

WHY THIS FILE EXISTS.  ``cloud-hub`` is not a server, it is a proxy over ~12 independent
backends, and it says so itself when a dead one is called::

    [cloud-hub] backend 'rclone (rclone-mcp over rcd)' is unavailable: initialize failed:
    deadline exceeded. Its other tools stay listed; fix the credentials/login for that
    backend and restart the session.

"Its other tools stay listed" is the whole problem: the advertised surface does not shrink
when a backend dies, so every per-server signal the audit had -- config, host, mount, even a
real ``initialize+tools/list`` handshake -- stays green over a backend that cannot answer.
Attributing tools to backends is what makes the fourth signal expressible per backend.

WHY IT IS SPLIT OUT.  ``_g3_backend_liveness.py`` owned this classifier AND a dated liveness
census in one file, so the census's exclusion from CI took the classifier's controls out with
it.  The controls are the part that must not rot: they run over a COMMITTED artifact, so they
are deterministic and cheap, while the census's verdict is a dated claim that must not be
re-asserted per PR.  Assertions here (CI-wired), census there (excluded) -- the same split
``_r2_ruff_census.py`` already sets.

CONTROLS (``--self-test``), each required to distinguish the two hypotheses:

  C1  COMPLETENESS.  Every one of cloud-hub's committed tool names classifies.  An
      unclassified tail is not cosmetic -- it silently UNDER-reports whichever backend it
      belongs to.  Measured: the plural RunPod verbs (``list-pods``, ``list-tags``,
      ``list-templates``, ``list-endpoints``, ``list-endpoint-workers``, ``get-job-status``,
      ``purge-endpoint-queue``) do not match the ``-pod``/``-tag``/``-template`` suffix
      hints, and this control is what surfaced them rather than letting RunPod's share read
      7 tools short.
  C2  NEGATIVE FIXTURE.  A name belonging to no backend must be REFUSED.  A classifier that
      accepts everything would pass C1 trivially -- C1 alone cannot tell "classified
      correctly" from "classified always", which is the inert-control shape.
  C3  PARTITION.  The buckets must be disjoint and sum to the total.  Two backends claiming
      one tool would double-count dead surface.

Read-only, pure, committed inputs only.  Spawns nothing.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Iterable

HERE = pathlib.Path(__file__).resolve().parent
MATRIX = "capability-matrix-r2.json"
PROXY_SERVER = "cloud-hub"

# Backend -> ordered prefix/suffix/exact matchers.  Longest match wins, so a specific
# matcher can override a general one without ordering games.
BACKENDS: dict[str, tuple[str, ...]] = {
    "rclone": ("config_", "core_", "operations_", "sync_", "rc_"),
    "runpod": ("rp_account_", "-pod", "-endpoint", "-template", "-tag", "-job"),
    "modal": ("modal_", "md_account_"),
    "databricks": ("dbx_", "db_account_"),
    "biomni": ("bm_",),
    "aws": ("aws_", "aws___"),
    "azure": ("azmcp_", "az_account_"),
    "gcloud": ("run_gcloud_command", "gc_account_"),
    "lightning": ("lightning_", "lg_account_"),
    "ovh": ("ovh_", "ov_account_"),
    "kaggle": (
        "competition",
        "dataset",
        "kernel",
        "model",
        "discussion",
        "kg_account_",
        "benchmark_leaderboard",
        "file_upload",
    ),
    "compute-unified": ("compute_",),
}

# RunPod's REST-style names are hyphenated verbs.  These carry none of the suffix hints
# above and must be enumerated; C1 is what proves the enumeration is complete.
RUNPOD_EXACT = frozenset(
    {
        "list-gpu-types",
        "get-gpu-type",
        "list-cpu-types",
        "get-cpu-type",
        "list-data-centers",
        "get-data-center",
        "list-network-volumes",
        "get-network-volume",
        "create-network-volume",
        "delete-network-volume",
        "update-network-volume",
        "list-container-registry-auths",
        "get-container-registry-auth",
        "create-container-registry-auth",
        "delete-container-registry-auth",
        "get-billing",
        "attach-tag",
        "detach-tag",
        "endpoint-health",
        "list-pods",
        "list-tags",
        "list-templates",
        "list-endpoints",
        "list-endpoint-workers",
        "get-job-status",
        "purge-endpoint-queue",
    }
)

NEGATIVE_FIXTURES = (
    "zzz_not_a_cloud_hub_tool",
    "browser_click",  # a real tool name, but playwright's, not cloud-hub's
    "",
)


def classify(tool: str) -> str | None:
    """Backend owning ``tool``, or None when no matcher claims it (never a guess)."""
    if not tool:
        return None
    if tool in RUNPOD_EXACT:
        return "runpod"
    best: tuple[int, str] | None = None
    for backend, matchers in BACKENDS.items():
        for m in matchers:
            hit = (
                tool.startswith(m)
                or (m.startswith("-") and tool.endswith(m))
                or tool == m
            )
            if hit and (best is None or len(m) > best[0]):
                best = (len(m), backend)
    return best[1] if best else None


def bucket(tools: Iterable[str]) -> tuple[dict[str, list[str]], list[str]]:
    """(backend -> tool names, unclassified names).  Unclassified is RETURNED, never dropped."""
    buckets: dict[str, list[str]] = {}
    unclassified: list[str] = []
    for t in tools:
        b = classify(t)
        if b is None:
            unclassified.append(t)
        else:
            buckets.setdefault(b, []).append(t)
    return buckets, unclassified


def proxy_tool_names(base: pathlib.Path | None = None) -> list[str]:
    """cloud-hub's committed ``tools/list`` surface.  Fails closed if it is not there."""
    path = (base or HERE) / MATRIX
    matrix = json.loads(path.read_text(encoding="utf-8"))
    row = next((r for r in matrix["rows"] if r["name"] == PROXY_SERVER), None)
    if row is None:
        raise SystemExit(f"FAILED:backend-map no {PROXY_SERVER} row in {MATRIX}")
    names = row.get("tool_names") or []
    if not names:
        raise SystemExit(f"FAILED:backend-map {PROXY_SERVER} has an empty tool surface")
    return list(names)


# ----------------------------------------------------------------------- self-test
def self_test(base: pathlib.Path | None = None) -> int:
    print("== backend_map self-test (C1 completeness, C2 negative, C3 partition) ==")
    names = proxy_tool_names(base)
    buckets, unclassified = bucket(names)
    bad: list[str] = []

    # ---- C2 FIRST.  A classifier that accepts everything passes C1 for the wrong
    # reason, so the refusal case has to be established before completeness means anything.
    for fixture in NEGATIVE_FIXTURES:
        got = classify(fixture)
        if got is not None:
            bad.append(f"C2 classifier accepted {fixture!r} as {got!r}")
    print(
        f"  {'ok ' if not bad else 'BAD'} C2 refuses {len(NEGATIVE_FIXTURES)} non-backend names"
    )

    # ---- C1 completeness over the committed surface.
    if unclassified:
        bad.append(f"C1 {len(unclassified)} unclassified: {sorted(unclassified)[:12]}")
    print(
        f"  {'ok ' if not unclassified else 'BAD'} C1 classified {len(names) - len(unclassified)}/{len(names)}"
    )

    # ---- C3 partition: disjoint, and the parts sum to the whole.
    seen: dict[str, str] = {}
    for backend, tools in buckets.items():
        for t in tools:
            if t in seen:
                bad.append(f"C3 {t!r} claimed by both {seen[t]!r} and {backend!r}")
            seen[t] = backend
    total = sum(len(v) for v in buckets.values()) + len(unclassified)
    if total != len(names):
        bad.append(f"C3 bucket sum {total} != surface {len(names)}")
    print(
        f"  {'ok ' if not bad else 'BAD'} C3 {len(buckets)} disjoint buckets summing to {total}"
    )

    # ---- a control that cannot go red is not a control: prove C1 FIRES on a broken input.
    _, tail = bucket([*names, "zzz_unownable_tool_name"])
    if len(tail) != 1:
        bad.append(
            f"C1 did not fire on a deliberately unownable name (tail={len(tail)})"
        )
    print(
        f"  {'ok ' if len(tail) == 1 else 'BAD'} C1 fires when an unownable name is injected"
    )

    if bad:
        for b in bad:
            print(f"  FAIL {b}")
        print(f"FAILED:backend-map {len(bad)} control(s) red")
        return 1
    print(
        f"SUCCESS:backend-map {len(names)}/{len(names)} cloud-hub tools classified into "
        f"{len(buckets)} disjoint backends, negative fixtures refused, C1 proven to fire"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(
        self_test(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    )
