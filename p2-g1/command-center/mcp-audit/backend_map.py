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

THE ACCOUNT LAYER IS NOT A BACKEND (added round 2).  Every backend used to own its own
``*_account_*`` family -- ``rp_account_current`` counted as RunPod surface, ``kg_account_*``
as Kaggle surface, and so on.  That is wrong, and it was inflating dead surface: those tools
are cloud-hub's OWN multi-account shim (env-var/CLI profile bookkeeping) and they keep
working while the backend behind them is down.

Measured 2026-08-14, four probes, deliberately chosen so the hypothesis could FAIL -- three
of the four sit over a backend independently measured non-functional in the same session:

    aws_account_current  -> ok:true   while every aws___* tool is non-dispatchable
    rp_account_current   -> ok:true   while the RunPod backend is dead
    kg_account_current   -> ok:true   while the Kaggle backend is dead (child exited)
    az_account_current   -> ok:true   while every azmcp_* tool is non-dispatchable

A shared ``cloud-hub-account-layer`` bucket therefore holds all eleven families.  This moves
the number in the SAFE-LOOKING direction (less surface counted dead), which is exactly why
it needed measurement rather than an argument -- and why C4 exists.

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
  C4  ACCOUNT-LAYER COMPLETENESS.  Every ``*_account_*`` name in the surface must land in
      the account-layer bucket.  C1/C2/C3 cannot see this defect: a half-finished relocation
      leaves the stragglers classified, disjoint, and summing correctly -- just attributed to
      a DEAD backend, which is the precise error this change exists to remove.  C4 is the
      only control that fails when the relocation is incomplete, so it is the one that has
      to be proven to fire.

Read-only, pure, committed inputs only.  Spawns nothing.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Iterable

HERE = pathlib.Path(__file__).resolve().parent
MATRIX = "capability-matrix-r2.json"
PROXY_SERVER = "cloud-hub"

# Backend -> ordered prefix/suffix/exact matchers.  Longest match wins, so a specific
# matcher can override a general one without ordering games.
ACCOUNT_LAYER = "cloud-hub-account-layer"

# The eleven ``*_account_*`` families.  Longest-match-wins is what makes the relocation
# safe: ``rc_account_`` (11) beats rclone's ``rc_`` (3), ``bm_account_`` beats biomni's
# ``bm_``, ``aws_account_`` beats aws's ``aws_`` -- so the general backend matchers below
# can stay exactly as they were and the account names still land here.
ACCOUNT_FAMILIES: tuple[str, ...] = (
    "aws_account_",
    "az_account_",
    "bm_account_",
    "db_account_",
    "gc_account_",
    "kg_account_",
    "lg_account_",
    "md_account_",
    "ov_account_",
    "rc_account_",
    "rp_account_",
)

BACKENDS: dict[str, tuple[str, ...]] = {
    "rclone": ("config_", "core_", "operations_", "sync_", "rc_"),
    "runpod": ("-pod", "-endpoint", "-template", "-tag", "-job"),
    "modal": ("modal_",),
    "databricks": ("dbx_",),
    "biomni": ("bm_",),
    "aws": ("aws_", "aws___"),
    "azure": ("azmcp_",),
    "gcloud": ("run_gcloud_command",),
    "lightning": ("lightning_",),
    "ovh": ("ovh_",),
    "kaggle": (
        "competition",
        "dataset",
        "kernel",
        "model",
        "discussion",
        "benchmark_leaderboard",
        "file_upload",
    ),
    "compute-unified": ("compute_",),
    ACCOUNT_LAYER: ACCOUNT_FAMILIES,
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


Table = dict[str, tuple[str, ...]]

# C4's INDEPENDENT detector.  Deliberately NOT the family table: it constrains the NAME
# SHAPE and the shim's fixed six-verb op set, and never enumerates which prefixes exist.
# If C4 asked ACCOUNT_FAMILIES which names belong to the account layer it would be asking
# the mutant to grade itself -- both sides would shrink together and the control could never
# fire.  That is the inert-control shape this repo has measured.
#
# It started life as the substring ``_account_`` and that was WRONG: on its first run over
# the real surface it claimed three stragglers -- ``azmcp_cosmos_account_list``,
# ``azmcp_storage_account_list`` and ``ovh_account_info`` -- which are backend tools about
# cloud ACCOUNTS, not the hub's account shim.  Classic use-vs-mention: the word appears in
# the name without the name being one.  The shape + verb set separates them, and the control
# catching its own author is the reason it is written down here.
ACCOUNT_OPS = ("add", "current", "cycle", "list", "remove", "switch")
ACCOUNT_NAME_RE = re.compile(rf"^[a-z]{{2,3}}_account_(?:{'|'.join(ACCOUNT_OPS)})$")


def _table(families: tuple[str, ...] | None = None) -> Table:
    """The matcher table, optionally with a REDUCED account-layer family tuple (C4 only)."""
    if families is None:
        return BACKENDS
    return {**BACKENDS, ACCOUNT_LAYER: families}


def classify(tool: str, table: Table | None = None) -> str | None:
    """Backend owning ``tool``, or None when no matcher claims it (never a guess)."""
    if not tool:
        return None
    if tool in RUNPOD_EXACT:
        return "runpod"
    best: tuple[int, str] | None = None
    for backend, matchers in (table or BACKENDS).items():
        for m in matchers:
            hit = (
                tool.startswith(m)
                or (m.startswith("-") and tool.endswith(m))
                or tool == m
            )
            if hit and (best is None or len(m) > best[0]):
                best = (len(m), backend)
    return best[1] if best else None


def bucket(
    tools: Iterable[str], table: Table | None = None
) -> tuple[dict[str, list[str]], list[str]]:
    """(backend -> tool names, unclassified names).  Unclassified is RETURNED, never dropped."""
    buckets: dict[str, list[str]] = {}
    unclassified: list[str] = []
    for t in tools:
        b = classify(t, table)
        if b is None:
            unclassified.append(t)
        else:
            buckets.setdefault(b, []).append(t)
    return buckets, unclassified


def account_stragglers(
    names: Iterable[str], buckets: dict[str, list[str]]
) -> list[str]:
    """Account-layer tools that landed somewhere ELSE -- typically on a dead backend.

    Uses ``ACCOUNT_NAME_RE`` rather than the family table so it stays independent of the
    thing it is checking.
    """
    owned = set(buckets.get(ACCOUNT_LAYER, ()))
    return sorted(n for n in names if ACCOUNT_NAME_RE.match(n) and n not in owned)


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

    # ---- C4a: the independent detector's OWN both-states fixture.  The loose version of
    # this regex shipped three false positives, so it needs a guard of its own or the next
    # loosening lands silently.
    must_match = ("aws_account_current", "rc_account_add", "kg_account_switch")
    must_refuse = (
        "azmcp_cosmos_account_list",  # an Azure resource listing, not the hub shim
        "azmcp_storage_account_list",
        "ovh_account_info",  # real OVH account read; 'info' is not one of the six ops
        "compute_status",
    )
    det = [
        f"C4a regex missed {n!r}" for n in must_match if not ACCOUNT_NAME_RE.match(n)
    ]
    det += [
        f"C4a regex accepted {n!r}" for n in must_refuse if ACCOUNT_NAME_RE.match(n)
    ]
    bad.extend(det)
    print(
        f"  {'ok ' if not det else 'BAD'} C4a detector matches {len(must_match)} shim names, "
        f"refuses {len(must_refuse)} look-alikes"
    )

    # ---- C4 account-layer completeness, over the real surface.
    stragglers = account_stragglers(names, buckets)
    if stragglers:
        bad.append(
            f"C4 {len(stragglers)} account-layer tool(s) attributed elsewhere: "
            f"{stragglers[:8]}"
        )
    n_acct = len(buckets.get(ACCOUNT_LAYER, []))
    if not n_acct:
        bad.append(
            "C4 the account-layer bucket is EMPTY -- the relocation did not happen"
        )
    print(
        f"  {'ok ' if not stragglers and n_acct else 'BAD'} C4 {n_acct} account-layer tools, 0 stragglers"
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

    # ---- and prove C4 fires on the defect it exists for.  The mutation drops ``rc_account_``
    # ONLY.  That family is the isolating case: ``rc_account_*`` still matches rclone's
    # ``rc_``, so it stays classified, the buckets stay disjoint and still sum to 424 --
    # C1, C2 and C3 all remain GREEN while 6 working tools are attributed to a DEAD backend.
    # A mutation that made the names unclassifiable would trip C1 and prove nothing about C4.
    reduced = tuple(f for f in ACCOUNT_FAMILIES if f != "rc_account_")
    mut_buckets, mut_tail = bucket(names, _table(reduced))
    mut_stragglers = account_stragglers(names, mut_buckets)
    mut_sum = sum(len(v) for v in mut_buckets.values()) + len(mut_tail)
    c4_isolated = bool(mut_stragglers) and not mut_tail and mut_sum == len(names)
    if not c4_isolated:
        bad.append(
            f"C4 did not fire in isolation (stragglers={len(mut_stragglers)}, "
            f"unclassified={len(mut_tail)}, sum={mut_sum})"
        )
    print(
        f"  {'ok ' if c4_isolated else 'BAD'} C4 fires on an incomplete relocation "
        f"({len(mut_stragglers)} straggler(s) -> {classify('rc_account_add', _table(reduced))!r}) "
        f"while C1/C3 stay green"
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
