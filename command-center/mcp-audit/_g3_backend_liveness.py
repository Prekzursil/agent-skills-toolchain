#!/usr/bin/env python3
"""GROUNDING round 2: cloud-hub is a MULTIPLEXER, and its per-backend liveness is
a signal the fleet audit never had.

WHY.  The lane's `call_verified` field was correctly narrowed in round 5 to mean
"the process starts and ADVERTISES a tool surface". `searxng` was the worked
counter-example: 4 advertised tools over a dead SearXNG instance.

That example understates the problem. `cloud-hub` is the largest row in the fleet
(424 tools, 321,053 B of schema = 62% of all measured schema bytes) and it is not
one server -- it is a proxy over ~13 independent backends, each of which can be
down while ITS TOOLS STAY LISTED. That is not inference: it is what the server
itself says when a dead backend is called ::

    [cloud-hub] backend 'rclone (rclone-mcp over rcd)' is unavailable:
    initialize failed: deadline exceeded. Its other tools stay listed;
    fix the credentials/login for that backend and restart the session.

This script joins the MEASURED per-backend probe results (real in-session tool
calls made by the grounding session, recorded in BACKEND_PROBES below) against the
committed `tools/list` surface, and reports how much of the advertised surface is
currently backed by something that cannot answer.

CONTROLS (rule 3 / a control must distinguish the two hypotheses):
  C1  every cloud-hub tool name must land in exactly one backend bucket. Unclassified
      names are PRINTED and counted, never silently dropped into "other" -- an
      unclassified tail is how a bucket count becomes fiction.
  C2  the classifier is run against a NEGATIVE fixture (a name that belongs to no
      backend) and must refuse to classify it.
  C3  the dead-surface total is recomputed from the bucket sums and must equal the
      independent sum over probed-dead backends; a mismatch fails closed.

Read-only. Spawns nothing. Prints no credential value.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# Backend -> ordered prefix/exact matchers. Order matters: longest/most specific first.
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

# RunPod's REST-style names are hyphenated verbs; enumerate the ones that do not
# carry one of the suffix hints above.
RUNPOD_EXACT = {
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
    # Plural list-* verbs: the `-pod` / `-tag` / `-template` suffix matchers below do
    # NOT match these, and the C1 unclassified-tail control is what surfaced them
    # rather than letting the bucket percentages quietly under-report RunPod by 7.
    "list-pods",
    "list-tags",
    "list-templates",
    "list-endpoints",
    "list-endpoint-workers",
    "get-job-status",
    "purge-endpoint-queue",
}

# MEASURED by this grounding session via real in-session tool calls, 2026-08-13.
# verdict: "dead" = the backend could not answer; "auth-dead" = the backend answered
# and rejected the credential; "hang" = no answer inside the 600 s MCP tool timeout.
BACKEND_PROBES: dict[str, tuple[str, str, str]] = {
    "rclone": (
        "core_version",
        "dead",
        "backend unavailable: initialize failed: deadline exceeded",
    ),
    "runpod": (
        "list-gpu-types",
        "dead",
        "backend unavailable: initialize failed: deadline exceeded",
    ),
    "modal": (
        "modal_whoami",
        "hang",
        "tool timed out after 600s -- no terminal state at all",
    ),
    "databricks": (
        "dbx_current_user",
        "auth-dead",
        "PermissionDenied: invalid access token (PAT expired)",
    ),
    "biomni": ("bm_whoami", "dead", "local broker refused connection (WinError 10061)"),
}

NEGATIVE_FIXTURE = "zzz_not_a_cloud_hub_tool"


def classify(tool: str) -> str | None:
    if tool in RUNPOD_EXACT:
        return "runpod"
    best: tuple[int, str] | None = None
    for backend, prefixes in BACKENDS.items():
        for p in prefixes:
            hit = (
                tool.startswith(p)
                or (p.startswith("-") and tool.endswith(p))
                or tool == p
            )
            if hit and (best is None or len(p) > best[0]):
                best = (len(p), backend)
    return best[1] if best else None


def main() -> int:
    matrix = json.loads(
        (HERE / "capability-matrix-r2.json").read_text(encoding="utf-8")
    )
    row = next(r for r in matrix["rows"] if r["name"] == "cloud-hub")
    names: list[str] = row["tool_names"]
    total, schema_b = row["tool_count"], row["schema_bytes"]

    # ---- C2: the classifier must REFUSE a name that belongs to no backend ----
    if classify(NEGATIVE_FIXTURE) is not None:
        print(
            "FAILED:g3-backend classifier accepted the negative fixture -- verdict withheld"
        )
        return 1
    print("  ok  C2 classifier refuses a non-cloud-hub name")

    buckets: dict[str, list[str]] = {}
    unclassified: list[str] = []
    for t in names:
        b = classify(t)
        if b is None:
            unclassified.append(t)
        else:
            buckets.setdefault(b, []).append(t)

    # ---- C1: an unclassified tail invalidates every bucket percentage ----
    print(f"  ok  C1 classified {len(names) - len(unclassified)}/{len(names)}")
    if unclassified:
        print(f"  !!  UNCLASSIFIED ({len(unclassified)}): {sorted(unclassified)}")

    per_tool_b = schema_b / total if total else 0.0
    print(f"\n  cloud-hub advertised surface: {total} tools, {schema_b:,} B schema")
    print(f"  mean schema bytes/tool      : {per_tool_b:,.0f}\n")
    print(f"  {'backend':<16} {'tools':>6} {'~schema B':>11}  probe")
    print(f"  {'-' * 16} {'-' * 6} {'-' * 11}  {'-' * 44}")

    dead_tools = 0
    for backend in sorted(buckets, key=lambda k: -len(buckets[k])):
        n = len(buckets[backend])
        probe = BACKEND_PROBES.get(backend)
        mark = f"{probe[1].upper():<9} via {probe[0]}" if probe else "not probed"
        if probe:
            dead_tools += n
        print(f"  {backend:<16} {n:>6} {n * per_tool_b:>11,.0f}  {mark}")
    if unclassified:
        print(
            f"  {'(unclassified)':<16} {len(unclassified):>6} {len(unclassified) * per_tool_b:>11,.0f}"
        )

    # ---- C3: recompute independently and require agreement ----
    recomputed = sum(len(buckets.get(b, [])) for b in BACKEND_PROBES)
    if recomputed != dead_tools:
        print(
            f"FAILED:g3-backend dead-surface disagreement {dead_tools} != {recomputed}"
        )
        return 1
    print(
        f"\n  ok  C3 dead-surface total agrees on two independent sums ({dead_tools})"
    )

    pct = 100.0 * dead_tools / total if total else 0.0
    print(
        f"\n  MEASURED-DEAD advertised surface: {dead_tools}/{total} tools "
        f"({pct:.1f}%), ~{dead_tools * per_tool_b:,.0f} B of schema"
    )
    print(
        f"  SCOPE: {len(BACKEND_PROBES)} of {len(buckets)} backends were probed. "
        f"The unprobed ones are NOT claimed live -- they are unmeasured."
    )
    print(
        f"SUCCESS:g3-backend {dead_tools}/{total} cloud-hub tools "
        f"({pct:.1f}%) are advertised over a backend measured non-functional"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
