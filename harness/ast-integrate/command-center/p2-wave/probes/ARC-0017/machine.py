#!/usr/bin/env python3
"""A3 executable spec: package state machine, digest-keyed cache, paper package.

The canonical registry INDEX is the control plane. Local capabilities exist
only as lockfile-pinned installed packages. Versions are immutable. Cache
lookup for activation is content-addressed by digest; a (package_id, version)
label is never sufficient to activate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
A2_REGISTRY = REPO / "command-center/p2-wave/probes/ARC-0010/registry.json"

STATES: tuple[str, ...] = (
    "ABSENT",
    "RESOLVING",
    "FETCHING",
    "VERIFYING",
    "STAGING",
    "INSTALLED",
    "ROLLING_BACK",
    "UNINSTALLING",
    "FAILED",
    "QUARANTINED",
)

EVENTS: tuple[str, ...] = (
    "request_install",
    "resolve_ok",
    "resolve_fail",
    "fetch_ok",
    "fetch_fail",
    "cache_hit",
    "cache_miss",
    "verify_ok",
    "verify_fail",
    "activate",
    "request_update",
    "request_rollback",
    "request_uninstall",
    "complete",
    "abort",
    "retry",
    "publish_public",
    "mutate_in_place",
)

ALWAYS_REJECT: dict[str, str] = {
    "publish_public": (
        "PR_ONLY_FORBIDS: owner release mode is PR-ONLY; a public marketplace "
        "publish is not a legal event. The only write path is a pull request "
        "against INDEX.json. Catalog citation: WORK-UNIT-CATALOG.json "
        "owner_decisions answer PR-ONLY (OQ-3)."
    ),
    "mutate_in_place": (
        "IMMUTABLE_VERSION: a (package_id, version) pair's digest cannot change. "
        "A fix is a new version plus a lockfile pin update. In-place republish "
        "is the root of stale-cache-masks-a-fixed-package."
    ),
}


def _t(
    nxt: str,
    pre: str,
    post: str,
    *,
    explicit_self_loop: bool = False,
) -> dict[str, Any]:
    return {
        "next": nxt,
        "precondition": pre,
        "postcondition": post,
        "explicit_self_loop": explicit_self_loop,
    }


# Sparse defined transitions. Complements are EXPLICIT REJECT, never implicit.
DEFINED: dict[tuple[str, str], dict[str, Any]] = {
    ("ABSENT", "request_install"): _t(
        "RESOLVING",
        "No lockfile pin and no install-root files for this package_id.",
        "Record enters RESOLVING; target pin is taken from INDEX channel pointer.",
    ),
    ("RESOLVING", "resolve_ok"): _t(
        "FETCHING",
        "INDEX contains (package_id, version, digest) for the requested channel.",
        "Target pin is bound; fetch or cache lookup may begin.",
    ),
    ("RESOLVING", "resolve_fail"): _t(
        "FAILED",
        "INDEX has no row, channel pointer is forbidden, or digest is missing.",
        "No bytes are written. Failure reason is recorded.",
    ),
    ("RESOLVING", "abort"): _t(
        "FAILED",
        "Operator aborts before a pin is bound.",
        "Record is FAILED; install-root unchanged.",
    ),
    ("FETCHING", "fetch_ok"): _t(
        "VERIFYING",
        "Blob bytes were obtained from the content store (not from a name-keyed cache).",
        "Bytes are held unverified. Activation is forbidden until verify_ok.",
    ),
    ("FETCHING", "fetch_fail"): _t(
        "FAILED",
        "Blob store miss or I/O error.",
        "No install-root write. Cache is not poisoned with partial bytes.",
    ),
    ("FETCHING", "cache_hit"): _t(
        "VERIFYING",
        "cache[digest] exists AND sha256(bytes)==digest AND lockfile.digest==digest.",
        "Cached bytes are treated as a fetch_ok. Name-only hits are not this event.",
    ),
    ("FETCHING", "cache_miss"): _t(
        "FETCHING",
        "No cache[digest], or cached bytes do not hash to digest (poison evicted).",
        "Remain FETCHING and obtain bytes from the blob store. Explicit self-loop.",
        explicit_self_loop=True,
    ),
    ("FETCHING", "abort"): _t(
        "FAILED",
        "Operator aborts during fetch.",
        "Partial downloads deleted. Install-root unchanged.",
    ),
    ("VERIFYING", "verify_ok"): _t(
        "STAGING",
        "sha256(bytes)==pin.digest. Owner-local signature over digest verifies. "
        "No postinstall rewrite of bytes is permitted.",
        "Bytes copied to staging dir named by digest. Install-root not yet swapped.",
    ),
    ("VERIFYING", "verify_fail"): _t(
        "QUARANTINED",
        "Digest mismatch, signature fail, or payload contains a forbidden postinstall rewrite.",
        "Bytes retained only for audit. Activation is forbidden.",
    ),
    ("VERIFYING", "abort"): _t(
        "FAILED",
        "Operator aborts during verify.",
        "Staging not created. Install-root unchanged.",
    ),
    ("STAGING", "activate"): _t(
        "INSTALLED",
        "Staging digest matches lockfile pin. claimed_paths do not overlap another pin.",
        "Install-root swap is atomic. Lockfile pin is the running identity.",
    ),
    ("STAGING", "abort"): _t(
        "FAILED",
        "Operator aborts after staging, before swap.",
        "Staging dir deleted. Previous INSTALLED pin, if any, remains.",
    ),
    ("STAGING", "request_uninstall"): _t(
        "UNINSTALLING",
        "Cancel a not-yet-activated stage.",
        "Staging deleted; uninstall proceeds to ABSENT if no prior pin.",
    ),
    ("INSTALLED", "request_update"): _t(
        "RESOLVING",
        "Lockfile pin exists. INDEX offers a different (version, digest) on the channel.",
        "Previous pin is stored as lockfile.previous. New target is unresolved.",
    ),
    ("INSTALLED", "request_rollback"): _t(
        "ROLLING_BACK",
        "lockfile.previous is present (version, digest).",
        "Target pin becomes previous. Current pin is retained until activate.",
    ),
    ("INSTALLED", "request_uninstall"): _t(
        "UNINSTALLING",
        "Operator requested removal of claimed_paths only.",
        "Files outside claimed_paths are not touched.",
    ),
    ("ROLLING_BACK", "resolve_ok"): _t(
        "FETCHING",
        "lockfile.previous.digest is known and INDEX still lists that immutable release, or cache has it.",
        "Target pin is the previous digest. Fetch/cache-hit follows the same verify path.",
    ),
    ("ROLLING_BACK", "resolve_fail"): _t(
        "FAILED",
        "No previous pin, or previous digest is unknown to INDEX and cache.",
        "Current INSTALLED pin remains on disk; rollback did not swap.",
    ),
    ("ROLLING_BACK", "cache_hit"): _t(
        "VERIFYING",
        "cache[previous.digest] hits under the digest key.",
        "Previous payload is re-verified before swap. Name-only hit is not this event.",
    ),
    ("ROLLING_BACK", "abort"): _t(
        "INSTALLED",
        "Operator aborts rollback.",
        "Current pin stays INSTALLED. No swap.",
    ),
    ("UNINSTALLING", "complete"): _t(
        "ABSENT",
        "Every claimed_path removed. Files not in claimed_paths still exist.",
        "Lockfile pin deleted. Cache entries MAY remain (content-addressed, not authority).",
    ),
    ("UNINSTALLING", "abort"): _t(
        "INSTALLED",
        "Uninstall cancelled before claimed_paths were fully removed.",
        "Restore remaining claimed files from cache[pin.digest] if needed; pin stays.",
    ),
    ("FAILED", "retry"): _t(
        "ABSENT",
        "Failure recorded. No install-root pin.",
        "Record reset to ABSENT so request_install may be retried.",
    ),
    ("FAILED", "request_uninstall"): _t(
        "UNINSTALLING",
        "Partial files may exist from a crashed swap.",
        "claimed_paths cleaned; then ABSENT.",
    ),
    ("QUARANTINED", "retry"): _t(
        "ABSENT",
        "Quarantined bytes kept for audit, not activated.",
        "Record reset. Quarantine blob is not reused as a cache HIT unless digest still matches a later pin.",
    ),
    ("QUARANTINED", "request_uninstall"): _t(
        "UNINSTALLING",
        "Operator discards quarantined bytes.",
        "Audit copy may remain outside install-root.",
    ),
}


def reject_reason(state: str, event: str) -> str:
    if event in ALWAYS_REJECT:
        return ALWAYS_REJECT[event]
    if (state, event) in DEFINED:
        raise KeyError(f"defined pair asked to reject: {state} {event}")
    if event in {"activate", "complete", "verify_ok", "fetch_ok", "resolve_ok"}:
        return (
            "ILLEGAL_IN_STATE: success event "
            f"{event!r} is not enabled from {state}; refusing rather than "
            "silently staying put (no implicit self-loop)."
        )
    return (
        f"ILLEGAL_IN_STATE: event {event!r} is not enabled from {state}; "
        "explicit REJECT, not an implicit self-loop."
    )


def full_table() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for state in STATES:
        for event in EVENTS:
            key = (state, event)
            if key in DEFINED:
                spec = DEFINED[key]
                rows.append(
                    {
                        "state": state,
                        "event": event,
                        "kind": "DEFINED",
                        "next": spec["next"],
                        "precondition": spec["precondition"],
                        "postcondition": spec["postcondition"],
                        "explicit_self_loop": bool(spec["explicit_self_loop"]),
                        "reject_reason": None,
                    }
                )
            else:
                rows.append(
                    {
                        "state": state,
                        "event": event,
                        "kind": "REJECT",
                        "next": None,
                        "precondition": f"Current state is {state}.",
                        "postcondition": (
                            "State unchanged because the event is refused. "
                            "This is not a transition and not an implicit self-loop."
                        ),
                        "explicit_self_loop": False,
                        "reject_reason": reject_reason(state, event),
                    }
                )
    return rows


def canonical_bytes(obj: Any) -> bytes:
    return (
        json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def table_digest(rows: list[dict[str, Any]] | None = None) -> str:
    rows = rows if rows is not None else full_table()
    return sha256_bytes(canonical_bytes(rows))


def totality_gaps(rows: list[dict[str, Any]] | None = None) -> list[str]:
    rows = rows if rows is not None else full_table()
    present = {(r["state"], r["event"]) for r in rows}
    expected = {(s, e) for s in STATES for e in EVENTS}
    missing = sorted(expected - present)
    extra = sorted(present - expected)
    gaps = [f"missing:{s}+{e}" for s, e in missing] + [
        f"extra:{s}+{e}" for s, e in extra
    ]
    by_pair: dict[tuple[str, str], int] = {}
    for r in rows:
        k = (r["state"], r["event"])
        by_pair[k] = by_pair.get(k, 0) + 1
    gaps.extend(
        f"duplicate:{s}+{e}" for (s, e), n in sorted(by_pair.items()) if n != 1
    )
    for r in rows:
        if r["kind"] == "DEFINED" and r["next"] == r["state"]:
            if not r.get("explicit_self_loop"):
                gaps.append(
                    f"implicit-self-loop:{r['state']}+{r['event']}"
                )
        if r["kind"] == "DEFINED" and r["next"] not in STATES:
            gaps.append(f"unknown-next:{r['state']}+{r['event']}->{r['next']}")
        if r["kind"] not in {"DEFINED", "REJECT"}:
            gaps.append(f"bad-kind:{r['state']}+{r['event']}")
        if r["kind"] == "REJECT" and r.get("next") is not None:
            gaps.append(f"reject-has-next:{r['state']}+{r['event']}")
        if r["kind"] == "REJECT" and r.get("explicit_self_loop"):
            gaps.append(f"reject-marked-self-loop:{r['state']}+{r['event']}")
    return gaps


class ImmutabilityError(ValueError):
    pass


class DigestCache:
    """Content-addressed cache. Activation lookup is by digest only."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.labels: dict[tuple[str, str], str] = {}

    def put(self, digest: str, blob: bytes, package_id: str, version: str) -> None:
        if sha256_bytes(blob) != digest:
            raise ValueError("refusing to store blob whose hash is not the key")
        self.blobs[digest] = blob
        self.labels[(package_id, version)] = digest

    def lookup_digest(self, digest: str) -> str:
        blob = self.blobs.get(digest)
        if blob is None:
            return "MISS"
        if sha256_bytes(blob) != digest:
            del self.blobs[digest]
            return "MISS"
        return "HIT"

    def lookup_name(self, package_id: str, version: str) -> str | None:
        """Advisory only. MUST NOT be used to activate under the design rule."""
        return self.labels.get((package_id, version))


class Index:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], str] = {}

    def publish(self, package_id: str, version: str, digest: str) -> None:
        key = (package_id, version)
        if key in self.rows and self.rows[key] != digest:
            raise ImmutabilityError(
                f"refusing in-place mutation of {package_id}@{version}: "
                f"{self.rows[key]} -> {digest}"
            )
        self.rows[key] = digest

    def get(self, package_id: str, version: str) -> str | None:
        return self.rows.get((package_id, version))


def walk_stale_cache_masks_fix(*, digest_in_key: bool) -> dict[str, Any]:
    """Walk the stale-cache-masks-a-fixed-package class.

    Publisher ships 1.0.0 with a bug (D_bad), then ships a fix. Under the
    design, the fix MUST be 1.0.1 (new version). A stale cache still holding
    D_bad must not satisfy a lockfile pin of D_good.

    digest_in_key=True  → design rule; class is unreachable.
    digest_in_key=False → mutant name-keyed cache; class is reachable.
    """
    payload_bad = b"skill.council v1.0.0 BUG"
    payload_good = b"skill.council v1.0.1 FIX"
    d_bad = sha256_bytes(payload_bad)
    d_good = sha256_bytes(payload_good)
    idx = Index()
    cache = DigestCache()
    pkg = "skill.council"

    idx.publish(pkg, "1.0.0", d_bad)
    cache.put(d_bad, payload_bad, pkg, "1.0.0")
    lockfile = {"package_id": pkg, "version": "1.0.0", "digest": d_bad}

    in_place_rejected = False
    try:
        idx.publish(pkg, "1.0.0", d_good)
    except ImmutabilityError:
        in_place_rejected = True

    idx.publish(pkg, "1.0.1", d_good)
    cache.labels[(pkg, "1.0.1")] = d_bad
    lockfile = {
        "package_id": pkg,
        "version": "1.0.1",
        "digest": d_good,
        "previous": {"version": "1.0.0", "digest": d_bad},
    }

    if digest_in_key:
        hit = cache.lookup_digest(lockfile["digest"])
        if hit == "HIT":
            activated = lockfile["digest"]
            fetched = False
        else:
            cache.put(d_good, payload_good, pkg, "1.0.1")
            if cache.lookup_digest(d_good) != "HIT":
                raise RuntimeError("fresh put did not HIT")
            activated = d_good
            fetched = True
    else:
        name_digest = cache.lookup_name(pkg, lockfile["version"])
        activated = name_digest
        fetched = False

    masked = activated != d_good
    return {
        "digest_in_key": digest_in_key,
        "in_place_rejected": in_place_rejected,
        "d_bad": d_bad,
        "d_good": d_good,
        "lockfile": lockfile,
        "activated_digest": activated,
        "fetched_after_miss": fetched,
        "masked": masked,
        "class_reachable": masked or (not in_place_rejected),
    }


def load_skill_council_entry() -> dict[str, Any]:
    doc = json.loads(A2_REGISTRY.read_text(encoding="utf-8"))
    for entry in doc["entries"]:
        if entry.get("id") == "skill.council":
            return entry
    raise KeyError("skill.council missing from A2 registry")


def paper_package_skill_council() -> dict[str, Any]:
    """Package one real on-tree capability end to end (typed skill.council)."""
    entry = load_skill_council_entry()
    payload = canonical_bytes(entry)
    digest = sha256_bytes(payload)
    claimed = [
        "command-center/p2-wave/probes/ARC-0010/registry.json#entries[id=skill.council]"
    ]
    not_claimed = [
        e["id"]
        for e in json.loads(A2_REGISTRY.read_text(encoding="utf-8"))["entries"]
        if e["id"] != "skill.council"
    ]
    release = {
        "package_id": "skill.council",
        "kind": "skill",
        "version": "1.0.0",
        "digest": digest,
        "channel": "pr",
        "claimed_paths": claimed,
        "immutable": True,
        "deps": [],
    }
    lockfile = {
        "schema_version": 1,
        "pins": [
            {
                "package_id": "skill.council",
                "version": "1.0.0",
                "digest": digest,
                "previous": None,
            }
        ],
    }
    index = {
        "schema_version": 1,
        "architecture_id": "A3",
        "release_mode": "PR-ONLY",
        "channels": [
            {
                "id": "pr",
                "write_path": "pull-request-against-index",
                "deploy_target": "none",
            },
            {
                "id": "beta",
                "write_path": "pull-request-against-index",
                "deploy_target": "index-pointer",
            },
            {
                "id": "stable",
                "write_path": "pull-request-against-index",
                "deploy_target": "index-pointer",
            },
            {
                "id": "canary-rehearsal",
                "write_path": "throwaway-prefix-rehearsal",
                "deploy_target": "throwaway-prefix",
            },
        ],
        "packages": [release],
    }
    walk = [
        ("ABSENT", "request_install", "RESOLVING"),
        ("RESOLVING", "resolve_ok", "FETCHING"),
        ("FETCHING", "cache_miss", "FETCHING"),
        ("FETCHING", "fetch_ok", "VERIFYING"),
        ("VERIFYING", "verify_ok", "STAGING"),
        ("STAGING", "activate", "INSTALLED"),
    ]
    state = "ABSENT"
    for src, event, dst in walk:
        spec = DEFINED[(src, event)]
        if src != state or spec["next"] != dst:
            raise RuntimeError(f"paper walk broken at {src}+{event}")
        state = spec["next"]
    return {
        "source_path": "command-center/p2-wave/probes/ARC-0010/registry.json",
        "source_id": "skill.council",
        "payload_sha256": digest,
        "payload_bytes": len(payload),
        "release": release,
        "lockfile": lockfile,
        "index": index,
        "not_claimed_sibling_ids": not_claimed,
        "install_walk": [
            {"from": a, "event": b, "to": c} for a, b, c in walk
        ],
        "terminal_state": state,
        "boundary_rule": (
            "The package owns only claimed_paths. Sibling registry entries "
            "are not claimed. Uninstall may delete only claimed_paths. "
            + (
                "skills/council/SKILL.md is present on this worktree and is "
                "EXPRESSIBLE as a separate markdown package; it is not claimed "
                "by this paper package, whose payload is the typed A2 registry entry."
                if (REPO / "skills/council/SKILL.md").is_file()
                else "skills/council/SKILL.md is absent on this worktree and is not claimed."
            )
        ),
    }


def apply(state: str, event: str) -> dict[str, Any]:
    row = next(
        r for r in full_table() if r["state"] == state and r["event"] == event
    )
    if row["kind"] == "DEFINED":
        return {"ok": True, "next": row["next"], "row": row}
    return {"ok": False, "next": state, "row": row}
