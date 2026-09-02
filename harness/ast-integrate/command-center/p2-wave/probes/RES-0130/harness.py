#!/usr/bin/env python3
"""Live lockfile install matrix for RES-0130.

This worktree has no npm/pnpm/poetry/cargo/nix binaries. The harness is a
Python installer that:
  * pins the same version field each ecosystem records
  * verifies the same digest family each resolver function checks
  * emits error strings quoted from frozen upstream source (or a labeled
    reconstructed missing-artifact code when the snapshot has no 404 text)
  * never installs a version other than the lockfile pin (anti-downgrade)

Nix NAR encoding is not reimplemented: flake.lock narHash is modeled as
SRI-sha256 of fixture bytes, applying the equal/not-equal rule in
libfetchers (NAR hash mismatch).
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from typing import Any

PKG = "widget"
PIN_VER = "1.0.0"
DECOY_VER = "2.0.0"
PIN_BYTES = b"RES-0130-PINNED-WIDGET-1.0.0\n" + (b"P" * 64)
DECOY_BYTES = b"RES-0130-DECOY-WIDGET-2.0.0\n" + (b"D" * 64)
POISON_BYTES = b"RES-0130-POISON-SAME-VERSION\n" + (b"X" * 64)

ECOSYSTEMS = (
    "npm-package-lock",
    "pnpm-lock",
    "poetry-lock",
    "cargo-lock",
    "nix-flake-lock",
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sri(algo: str, data: bytes) -> str:
    digest = base64.b64encode(getattr(hashlib, algo)(data).digest()).decode("ascii")
    return f"{algo}-{digest}"


def pin_digest(ecosystem: str, data: bytes) -> str:
    if ecosystem in {"npm-package-lock", "pnpm-lock"}:
        return sri("sha512", data)
    if ecosystem == "nix-flake-lock":
        return sri("sha256", data)
    return sha256_hex(data)


def integrity_error(ecosystem: str, wanted: str, got: str, n: int, url: str) -> tuple[str, str]:
    """Return (message, code) quoted from frozen resolver source."""
    if ecosystem == "npm-package-lock":
        # ssri-index.js checkData: Integrity checksum failed when using ${algorithm}...
        msg = (
            f"Integrity checksum failed when using sha512: Wanted {wanted}, "
            f"but got {got}. ({n} bytes)"
        )
        return msg, "EINTEGRITY"
    if ecosystem == "pnpm-lock":
        # TarballIntegrityError in pnpm worker/src/index.ts (commit aa6149d)
        msg = (
            f'Got unexpected checksum for "{url}". Wanted "{wanted}". Got "{got}".'
        )
        return msg, "ERR_PNPM_TARBALL_INTEGRITY"
    if ecosystem == "poetry-lock":
        # Executor._validate_archive_hash
        msg = (
            f"Hash for {PKG} ({PIN_VER}) from archive {PKG}-{PIN_VER}.tar.gz "
            f"not found in known hashes (was: sha256:{got})"
        )
        return msg, "HASH_MISMATCH"
    if ecosystem == "cargo-lock":
        # finish_download in cargo-download.rs
        msg = f"failed to verify the checksum of `{PKG} v{PIN_VER}`"
        return msg, "CHECKSUM"
    msg = (
        f"NAR hash mismatch in input '{PKG}', expected '{wanted}' but got '{got}'"
    )
    return msg, "NAR_HASH_MISMATCH"


def missing_error(ecosystem: str, offline: bool) -> tuple[str, str]:
    """Missing-artifact errors.

    Integrity strings above are copied from source. These missing-tarball
    codes are reconstructed from docs (npm unpublish removes the registry
    object; pnpm --offline uses the store only) because arborist/pip 404
    formatters were not in the frozen snapshots.
    """
    if offline:
        if ecosystem == "pnpm-lock":
            return (
                "pnpm i --offline: package not in store; installation will fail",
                "ERR_PNPM_NO_OFFLINE",
            )
        if ecosystem == "npm-package-lock":
            return (
                "ENOTCACHED: cache mode only-if-cached but no cached tarball",
                "ENOTCACHED",
            )
        if ecosystem == "nix-flake-lock":
            return (
                "cannot compute store path for unlocked input; empty store and no substituter",
                "UNFETCHABLE",
            )
        if ecosystem == "cargo-lock":
            return (
                "failed to download from registry (--offline, crate not in cache)",
                "OFFLINE",
            )
        return (
            "Package not found in poetry cache (--offline)",
            "OFFLINE",
        )
    if ecosystem == "npm-package-lock":
        return (
            f"npm ERR! code E404; 404 Not Found - GET registry://{PKG}/-/{PKG}-{PIN_VER}.tgz",
            "E404",
        )
    if ecosystem == "pnpm-lock":
        return (
            f"ERR_PNPM_FETCH_404 GET registry://{PKG}/-/{PKG}-{PIN_VER}.tgz",
            "ERR_PNPM_FETCH_404",
        )
    if ecosystem == "nix-flake-lock":
        return (
            f"error: unable to download input '{PKG}': HTTP 404",
            "FETCH_404",
        )
    if ecosystem == "cargo-lock":
        return (
            f"failed to download `{PKG} v{PIN_VER}` (deleted from registry, not merely yanked)",
            "GONE",
        )
    return (
        f"PackageNotFound: {PKG}=={PIN_VER} unpublished from index",
        "NOT_FOUND",
    )


@dataclass
class World:
    """Registry / cache / mirror state. Decoy version is always present."""

    registry: dict[tuple[str, str], bytes | None] = field(default_factory=dict)
    yanked: set[tuple[str, str]] = field(default_factory=set)
    cache: dict[tuple[str, str], bytes] = field(default_factory=dict)
    mirror: dict[tuple[str, str], bytes] = field(default_factory=dict)
    allow_registry: bool = True


def install(ecosystem: str, world: World, *, verify: bool = True) -> dict[str, Any]:
    """Install the lockfile pin. Never selects DECOY_VER."""
    key = (PKG, PIN_VER)
    decoy_key = (PKG, DECOY_VER)
    wanted = pin_digest(ecosystem, PIN_BYTES)
    url = f"registry://{PKG}/-/{PKG}-{PIN_VER}.tgz"

    source = None
    blob: bytes | None = None
    warning = None

    if key in world.cache:
        blob = world.cache[key]
        source = "cache"
    elif world.allow_registry and key in world.registry:
        reg = world.registry[key]
        if reg is None:
            blob = None
        else:
            blob = reg
            source = "registry"
            if key in world.yanked:
                if ecosystem == "poetry-lock":
                    warning = (
                        f"The file chosen for install of {PKG} {PIN_VER} "
                        f"({url}) is yanked."
                    )
                elif ecosystem == "cargo-lock":
                    warning = (
                        "yanked release used because it already exists in the "
                        "Cargo.lock file"
                    )
    if blob is None and key in world.mirror:
        blob = world.mirror[key]
        source = "mirror"

    if blob is None:
        msg, code = missing_error(ecosystem, offline=not world.allow_registry)
        return {
            "ok": False,
            "installed_version": None,
            "installed_digest": None,
            "installed_source": None,
            "error": msg,
            "error_code": code,
            "warning": warning,
            "decoy_installed": False,
            "decoy_present_on_registry": decoy_key in world.registry,
        }

    got = pin_digest(ecosystem, blob)
    if verify and got != wanted:
        msg, code = integrity_error(ecosystem, wanted, got, len(blob), url)
        return {
            "ok": False,
            "installed_version": None,
            "installed_digest": None,
            "installed_source": source,
            "error": msg,
            "error_code": code,
            "warning": warning,
            "decoy_installed": False,
            "decoy_present_on_registry": decoy_key in world.registry,
        }

    return {
        "ok": True,
        "installed_version": PIN_VER,
        "installed_digest": got,
        "installed_source": source,
        "error": None,
        "error_code": None,
        "warning": warning,
        "decoy_installed": False,
        "decoy_present_on_registry": decoy_key in world.registry,
        "bytes": len(blob),
    }


def _base_world() -> World:
    w = World()
    w.registry[(PKG, DECOY_VER)] = DECOY_BYTES
    return w


def scenario_worlds() -> dict[str, World]:
    reachable = _base_world()
    reachable.registry[(PKG, PIN_VER)] = PIN_BYTES

    offline_empty = _base_world()
    offline_empty.allow_registry = False

    unpublished = _base_world()
    unpublished.registry[(PKG, PIN_VER)] = None

    yank = _base_world()
    yank.registry[(PKG, PIN_VER)] = PIN_BYTES
    yank.yanked.add((PKG, PIN_VER))

    mirror_match = _base_world()
    mirror_match.registry[(PKG, PIN_VER)] = None
    mirror_match.mirror[(PKG, PIN_VER)] = PIN_BYTES

    mirror_poison = _base_world()
    mirror_poison.registry[(PKG, PIN_VER)] = None
    mirror_poison.mirror[(PKG, PIN_VER)] = POISON_BYTES

    cache_hit = _base_world()
    cache_hit.registry[(PKG, PIN_VER)] = None
    cache_hit.allow_registry = False
    cache_hit.cache[(PKG, PIN_VER)] = PIN_BYTES

    return {
        "reachable": reachable,
        "offline_empty": offline_empty,
        "unpublished_no_mirror": unpublished,
        "yanked_upstream_still_present": yank,
        "stale_mirror_match": mirror_match,
        "stale_mirror_mismatch": mirror_poison,
        "offline_cache_hit": cache_hit,
    }


def run_matrix() -> dict[str, Any]:
    worlds = scenario_worlds()
    wanted = {eco: pin_digest(eco, PIN_BYTES) for eco in ECOSYSTEMS}
    rows: list[dict[str, Any]] = []
    for eco in ECOSYSTEMS:
        for name, world in worlds.items():
            result = install(eco, world)
            rows.append({"ecosystem": eco, "scenario": name, **result})
    # Detector control: mismatch with verify=False would install poison.
    mutant = install(
        "npm-package-lock",
        worlds["stale_mirror_mismatch"],
        verify=False,
    )
    return {
        "package": PKG,
        "pin_version": PIN_VER,
        "decoy_version": DECOY_VER,
        "wanted_digest": wanted,
        "rows": rows,
        "mutant_mismatch_without_verify": {
            "ok": mutant["ok"],
            "installed_digest": mutant["installed_digest"],
            "would_install_poison": mutant["ok"]
            and mutant["installed_digest"] != wanted["npm-package-lock"],
        },
    }


def summarize(matrix: dict[str, Any]) -> dict[str, Any]:
    def pick(eco: str, scenario: str) -> dict[str, Any]:
        for row in matrix["rows"]:
            if row["ecosystem"] == eco and row["scenario"] == scenario:
                return row
        raise KeyError(f"{eco}/{scenario}")

    both_states = []
    research = []
    for eco in ECOSYSTEMS:
        green = pick(eco, "reachable")
        red = pick(eco, "offline_empty")
        match = pick(eco, "stale_mirror_match")
        poison = pick(eco, "stale_mirror_mismatch")
        unpublished = pick(eco, "unpublished_no_mirror")
        yanked = pick(eco, "yanked_upstream_still_present")
        cache = pick(eco, "offline_cache_hit")
        both_ok = (
            green["ok"] is True
            and green["installed_version"] == PIN_VER
            and green["decoy_installed"] is False
            and red["ok"] is False
            and red["installed_version"] is None
            and red["decoy_installed"] is False
            and bool(red["error"])
        )
        both_states.append(
            {
                "ecosystem": eco,
                "reachable_ok": green["ok"],
                "offline_empty_ok": red["ok"],
                "offline_error": red["error"],
                "offline_error_code": red["error_code"],
                "pass": both_ok,
            }
        )
        research.append(
            {
                "ecosystem": eco,
                "stale_mirror_match_ok": match["ok"],
                "stale_mirror_match_source": match["installed_source"],
                "stale_mirror_mismatch_ok": poison["ok"],
                "stale_mirror_mismatch_error": poison["error"],
                "stale_mirror_mismatch_code": poison["error_code"],
                "unpublished_no_mirror_ok": unpublished["ok"],
                "unpublished_error": unpublished["error"],
                "yanked_without_mirror_ok": yanked["ok"],
                "yanked_warning": yanked["warning"],
                "offline_cache_hit_ok": cache["ok"],
            }
        )
    mutant = matrix["mutant_mismatch_without_verify"]
    return {
        "both_states_all_pass": all(x["pass"] for x in both_states),
        "both_states": both_states,
        "research": research,
        "mirror_match_all_five": all(x["stale_mirror_match_ok"] for x in research),
        "mirror_mismatch_all_fail": all(
            x["stale_mirror_mismatch_ok"] is False for x in research
        ),
        "detector_control": {
            "verify_on_mismatch_fails": all(
                x["stale_mirror_mismatch_ok"] is False for x in research
            ),
            "verify_off_would_install_poison": mutant["would_install_poison"] is True,
            "silent_in_both_states": False,
        },
    }


def assert_live_invariants(matrix: dict[str, Any], summary: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if not summary["both_states_all_pass"]:
        errs.append("both-states control failed")
    if not summary["mirror_match_all_five"]:
        errs.append("stale matching mirror did not install all five")
    if not summary["mirror_mismatch_all_fail"]:
        errs.append("poison mirror did not fail closed")
    det = summary["detector_control"]
    if not det["verify_on_mismatch_fails"] or not det["verify_off_would_install_poison"]:
        errs.append("detector control silent in both states")
    for row in matrix["rows"]:
        if row["decoy_installed"]:
            errs.append(f"decoy installed {row['ecosystem']}/{row['scenario']}")
        if row["ok"] and row["installed_version"] != PIN_VER:
            errs.append(f"non-pin version {row['ecosystem']}/{row['scenario']}")
        if row["ok"] and row["installed_digest"] != matrix["wanted_digest"][row["ecosystem"]]:
            errs.append(f"digest drift {row['ecosystem']}/{row['scenario']}")
    # Cargo/poetry yank without mirror must succeed (upstream still has bytes).
    for eco in ("cargo-lock", "poetry-lock"):
        yanked = next(
            r
            for r in matrix["rows"]
            if r["ecosystem"] == eco
            and r["scenario"] == "yanked_upstream_still_present"
        )
        if not yanked["ok"]:
            errs.append(f"{eco} yank-without-mirror should succeed")
    # npm/pnpm unpublished with no mirror must fail.
    for eco in ("npm-package-lock", "pnpm-lock"):
        unp = next(
            r
            for r in matrix["rows"]
            if r["ecosystem"] == eco and r["scenario"] == "unpublished_no_mirror"
        )
        if unp["ok"]:
            errs.append(f"{eco} unpublished-no-mirror should fail")
    return errs
