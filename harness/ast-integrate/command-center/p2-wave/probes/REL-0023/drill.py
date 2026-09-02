#!/usr/bin/env python3
"""Withdrawal drill: deprecate then revoke, plus PR-ONLY revert exposure window."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from client import CanaryClient, IsolationError
from clock import CLOCK_API, CLOCK_SOURCE, NamedClock, delay_seconds
from pr_only import DirectIndexWriteRefused, PublicIndex, PullRequest, RegistryReflector
from registry import PKG, PrivateRegistry

PAYLOAD = {
    "1.0.0": "BEHAVIOUR-STABLE-100\n",
    "1.1.0": "BEHAVIOUR-BAD-110-WITHDRAW-ME\n",
    "1.2.0": "BEHAVIOUR-SUCCESSOR-120\n",
}
INJECTED_PROPAGATION_S = 0.05


def owner_home() -> Path:
    return Path(os.environ.get("HOME") or str(Path.home())).resolve()


def fresh_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="rel0023-canary-"))
    home = owner_home()
    if root == home or home in root.parents:
        raise IsolationError(f"temp root landed in owner HOME: {root}")
    return root


def seed_registry(path: Path, versions: dict[str, str] | None = None) -> PrivateRegistry:
    reg = PrivateRegistry(path)
    for ver, payload in (versions or PAYLOAD).items():
        reg.publish(PKG, ver, payload)
    return reg


def client_on(root: Path, reg: PrivateRegistry, name: str) -> CanaryClient:
    return CanaryClient(root / name, reg, owner_home())


def three_registry_states(root: Path) -> dict[str, Any]:
    """Record next-resolve behaviour for current, deprecated, and revoked."""
    clock = NamedClock()
    observations = []

    # --- current ---
    reg_a = seed_registry(root / "state-current" / "registry.json")
    pinned_a = client_on(root / "state-current", reg_a, "pinned-110")
    pinned_a.move_to("1.1.0")
    obs_a = pinned_a.next_resolve()
    observations.append(
        {
            "registry_state": "current",
            "installed": "1.1.0",
            "observed_action": obs_a["action"],
            "warning": obs_a.get("warning"),
            "detail": obs_a,
        }
    )

    # --- deprecated ---
    reg_b = seed_registry(root / "state-deprecated" / "registry.json")
    reg_b.deprecate(
        PKG,
        "1.1.0",
        "bad canary build; successor is 1.2.0",
        "1.2.0",
        clock.now_ns(),
    )
    pinned_b = client_on(root / "state-deprecated", reg_b, "pinned-110")
    dep_install = pinned_b.move_to("1.1.0")
    obs_b = pinned_b.next_resolve()
    fresh_b = client_on(root / "state-deprecated", reg_b, "fresh")
    fresh_b_res = fresh_b.fresh_install()
    observations.append(
        {
            "registry_state": "deprecated",
            "installed": "1.1.0",
            "observed_action": obs_b["action"],
            "warning": obs_b.get("warning"),
            "deprecated_version_install": dep_install,
            "fresh_install": fresh_b_res,
            "detail": obs_b,
        }
    )

    # --- revoked ---
    reg_c = seed_registry(root / "state-revoked" / "registry.json")
    reg_c.revoke(PKG, "1.1.0", "withdrawn by private-registry half", clock.now_ns())
    pinned_c = client_on(root / "state-revoked", reg_c, "pinned-110")
    # Install 1.1.0 by writing while it is still current, then revoke, to
    # model "installed before withdrawal". Seed a second registry for that.
    reg_pre = seed_registry(root / "state-revoked" / "pre.json")
    pre_client = client_on(root / "state-revoked", reg_pre, "pre-install")
    pre_client.move_to("1.1.0")
    # Point the same profile at the revoked registry by swapping the client.registry
    # after copying the installed tree.
    already = client_on(root / "state-revoked", reg_c, "already-on-110")
    (already.profile / "installed.json").write_text(
        (pre_client.profile / "installed.json").read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )
    (already.profile / "payload.txt").write_text(
        (pre_client.profile / "payload.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )
    obs_c = already.next_resolve()
    offered = client_on(root / "state-revoked", reg_c, "on-100")
    offered.move_to("1.0.0")
    refuse = offered.move_to("1.1.0")
    fresh_c = client_on(root / "state-revoked", reg_c, "fresh")
    fresh_c_res = fresh_c.fresh_install()
    successor_missing = None
    try:
        reg_c.deprecate(
            PKG,
            "1.0.0",
            "would-be-bad",
            "9.9.9",
            clock.now_ns(),
        )
        successor_missing = "NOT-RAISED"
    except Exception as exc:
        successor_missing = type(exc).__name__
    observations.append(
        {
            "registry_state": "revoked",
            "installed": "1.1.0",
            "observed_action": obs_c["action"],
            "warning": obs_c.get("warning"),
            "offered_revoked": refuse,
            "fresh_install": fresh_c_res,
            "detail": obs_c,
        }
    )
    return {
        "observations": observations,
        "refuse_move": refuse,
        "fresh_revoked": fresh_c_res,
        "successor_missing": successor_missing,
    }


def exposure_window(root: Path) -> dict[str, Any]:
    """Public revert PR + private reflect; measure CLOCK_MONOTONIC delay."""
    clock = NamedClock()
    work = root / "exposure"
    work.mkdir(parents=True, exist_ok=True)
    # 1.1.0 is the latest published version being withdrawn. A successor is
    # not yet published, so a fresh resolve during the window still lands on it.
    reg = seed_registry(
        work / "registry.json",
        {"1.0.0": PAYLOAD["1.0.0"], "1.1.0": PAYLOAD["1.1.0"]},
    )
    public = PublicIndex(work / "public-index.json")
    public.seed_from_registry(reg)

    direct_refused = False
    direct_error = ""
    try:
        public.direct_write({"no": "direct-writes"})
    except DirectIndexWriteRefused as exc:
        direct_refused = True
        direct_error = str(exc)

    pr = PullRequest("REL-0023-revert-1.1.0", PKG, "1.1.0", "revert-withdraw")
    merge_ns = pr.merge(public, clock)

    # During the window the private registry has not yet revoked 1.1.0.
    exposed = client_on(work, reg, "during-window")
    during = exposed.fresh_install()

    clock.sleep_s(INJECTED_PROPAGATION_S)
    reflector = RegistryReflector(reg)
    reflect_ns = reflector.reflect_revoke(
        "1.1.0",
        "private registry reflecting merged revert PR REL-0023-revert-1.1.0",
        clock,
    )
    closed = client_on(work, reg, "after-reflect")
    after = closed.fresh_install()

    delay_ns = reflect_ns - merge_ns
    delay_s = delay_seconds(merge_ns, reflect_ns)

    on_100 = client_on(work, reg, "on-100-after")
    on_100.move_to("1.0.0")
    refuse = on_100.move_to("1.1.0")

    private_half = {
        "name": "private-file-backed-registry",
        "action": "deprecate then revoke 1.1.0 in the canary registry",
        "protects_next_resolve": True,
        "uninstalls_already_installed": False,
    }
    public_half = {
        "name": "pr-only-revert-pull-request",
        "action": "merge revert PR against the public index; reflector copies into private registry",
        "protects_next_resolve": False,
        "protects_after_reflect_only": True,
        "uninstalls_already_installed": False,
    }
    return {
        "clock_source": CLOCK_SOURCE,
        "clock_api": CLOCK_API,
        "merge_ns": merge_ns,
        "reflect_ns": reflect_ns,
        "delay_ns": delay_ns,
        "delay_seconds": delay_s,
        "injected_propagation_s": INJECTED_PROPAGATION_S,
        "during_window_fresh": during,
        "after_reflect_fresh": after,
        "refuse_move_after": refuse,
        "direct_index_write_refused": direct_refused,
        "direct_index_write_error": direct_error,
        "revert_pr": pr.id,
        "private_half": private_half,
        "public_half": public_half,
        "protects_already_installed": (
            "Neither half uninstalls a client that installed 1.1.0 before "
            "withdrawal: next resolve on that pin is KEEP_RUNNING_UNAWARE. "
            "The private-registry revoke is the half that protects somebody "
            "at next resolve who is not already on 1.1.0 (REFUSE_MOVE) and "
            "blocks fresh installs. The revert PR is the public record; it "
            "does not protect anyone until the private registry reflects it. "
            f"That reflection delay is the exposure window: {delay_s:.6f}s "
            f"measured on {CLOCK_SOURCE}."
        ),
    }


def run_drill() -> dict[str, Any]:
    root = fresh_root()
    states = three_registry_states(root)
    window = exposure_window(root)
    iso = client_on(root, seed_registry(root / "iso-reg.json"), "iso").isolation_record()
    return {
        "root": str(root),
        "package": PKG,
        "isolation": iso,
        "registry_states": states["observations"],
        "refuse_move": states["refuse_move"],
        "fresh_revoked": states["fresh_revoked"],
        "successor_missing": states["successor_missing"],
        "exposure_window": window,
    }
