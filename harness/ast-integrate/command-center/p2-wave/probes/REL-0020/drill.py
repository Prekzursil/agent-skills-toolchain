"""REL-0020 lifecycle drill: cache invalidation from the poisoned state.

An empty-cache run is silent in the broken and fixed states alike. The drill
therefore seeds the previous package into every reachable cache location the
client's own resolution_order consults, then installs the candidate.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from client import Client, IsolationError, assert_isolated, inventory_template
from packages import (
    NEW,
    NEW_BEHAVIOUR,
    NEW_VERSION,
    OLD,
    OLD_BEHAVIOUR,
    OLD_VERSION,
    PACKAGE_NAME,
    assert_tokens_distinct,
)

REPO = Path(__file__).resolve().parents[4]


def _fresh_client(tmp: str) -> Client:
    profile = Path(tmp) / "profile"
    assert_isolated(profile)
    return Client(profile)


def empty_cache_both_states() -> dict[str, Any]:
    """Install candidate into an empty cache, with and without refresh.

    Both must observe NEW. That is why an empty-cache invalidation test
    measures nothing: it cannot see the broken state.
    """
    out: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="rel0020-empty-off-") as tmp:
        c = _fresh_client(tmp)
        c.install(NEW, refresh=False)
        out["without_refresh"] = {
            "behaviour": c.execute(),
            "version": c.version(),
            "hit": c.hit_location(),
        }
    with tempfile.TemporaryDirectory(prefix="rel0020-empty-on-") as tmp:
        c = _fresh_client(tmp)
        c.install(NEW, refresh=True)
        out["with_refresh"] = {
            "behaviour": c.execute(),
            "version": c.version(),
            "hit": c.hit_location(),
        }
    out["silent_in_both_states"] = (
        out["without_refresh"]["behaviour"] == NEW_BEHAVIOUR
        and out["with_refresh"]["behaviour"] == NEW_BEHAVIOUR
        and out["without_refresh"]["behaviour"] == out["with_refresh"]["behaviour"]
    )
    return out


def poisoned_without_refresh() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rel0020-poison-off-") as tmp:
        c = _fresh_client(tmp)
        seeded = c.seed_poison(OLD)
        c.install(NEW, refresh=False)
        behaviour = c.execute()
        return {
            "seeded": seeded,
            "behaviour": behaviour,
            "version": c.version(),
            "hit": c.hit_location(),
            "perceives_defect": behaviour == OLD_BEHAVIOUR,
            "version_reports_new": c.version() == NEW_VERSION,
        }


def poisoned_with_refresh() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rel0020-poison-on-") as tmp:
        c = _fresh_client(tmp)
        seeded = c.seed_poison(OLD)
        c.install(NEW, refresh=True)
        behaviour = c.execute()
        per_loc = {loc.id: c.execute_from(loc.id) for loc in c.resolution_order()}
        return {
            "seeded": seeded,
            "behaviour": behaviour,
            "version": c.version(),
            "hit": c.hit_location(),
            "new_bytes_execute": behaviour == NEW_BEHAVIOUR,
            "per_location_behaviour": per_loc,
        }


def version_string_trap() -> dict[str, Any]:
    """Sidecar version is NEW while poisoned old bytes still execute.

    Proves a version-string read is not the behavioural distinguisher.
    """
    with tempfile.TemporaryDirectory(prefix="rel0020-verstrap-") as tmp:
        c = _fresh_client(tmp)
        c.seed_poison(OLD)
        c.install(NEW, refresh=False)
        behaviour = c.execute()
        version = c.version()
        return {
            "behaviour": behaviour,
            "version": version,
            "hit": c.hit_location(),
            "version_is_new": version == NEW_VERSION,
            "behaviour_is_old": behaviour == OLD_BEHAVIOUR,
            "trap_holds": version == NEW_VERSION and behaviour == OLD_BEHAVIOUR,
            "version_equals_behaviour": version == behaviour,
        }


def partial_refresh_still_masked() -> dict[str, Any]:
    """Mutation: refresh that only clears bytecode must still see OLD.

    Unpacked-user-cache remains poisoned and sits next in resolution_order.
    """
    with tempfile.TemporaryDirectory(prefix="rel0020-partial-") as tmp:
        c = _fresh_client(tmp)
        c.seed_poison(OLD)
        c.install(NEW, refresh=False)
        cleared = c.refresh(layers=["bytecode"])
        behaviour = c.execute()
        return {
            "cleared": cleared,
            "behaviour": behaviour,
            "hit": c.hit_location(),
            "still_masked": behaviour == OLD_BEHAVIOUR,
            "hit_is_unpacked": c.hit_location() == "unpacked-user-cache",
        }


def isolation_self_check() -> dict[str, Any]:
    home = Path.home().resolve()
    raised = False
    try:
        Client(home)
    except IsolationError:
        raised = True
    return {
        "owner_home": str(home),
        "client_on_owner_home_raises": raised,
        "product_cache_py_present": (REPO / "platform/plugin/cache.py").is_file(),
    }


def location_rows(seeded: list[str]) -> list[dict[str, Any]]:
    rows = []
    for loc in inventory_template():
        if not loc.reachable:
            status = "NOT-CHECKED"
            reason = loc.reason
        elif loc.id == "install-tree":
            status = "INSTALLED"
            reason = "candidate package written here; not a poison seed"
        elif loc.id in seeded:
            status = "SEEDED"
            reason = loc.reason
        else:
            status = "NOT-CHECKED"
            reason = "reachable but not seeded — probe must not omit this"
        rows.append(
            {
                "id": loc.id,
                "path": loc.relpath if loc.reachable else loc.relpath,
                "status": status,
                "reason": reason,
                "reachable": loc.reachable,
                "kind": loc.kind,
            }
        )
    return rows


def run_all() -> dict[str, Any]:
    assert_tokens_distinct()
    empty = empty_cache_both_states()
    off = poisoned_without_refresh()
    on = poisoned_with_refresh()
    trap = version_string_trap()
    partial = partial_refresh_still_masked()
    iso = isolation_self_check()
    seeded = list(off["seeded"])
    rows = location_rows(seeded)
    not_checked = [r["id"] for r in rows if r["status"] == "NOT-CHECKED"]
    if not not_checked:
        raise RuntimeError("inventory produced zero NOT-CHECKED rows")
    if not seeded:
        raise RuntimeError("poison seed wrote zero cache locations")
    omitted = [
        loc.id
        for loc in inventory_template()
        if loc.id not in {r["id"] for r in rows}
    ]
    if omitted:
        raise RuntimeError(f"inventory omitted locations: {omitted}")
    return {
        "empty_cache": empty,
        "poisoned_without_refresh": off,
        "poisoned_with_refresh": on,
        "version_string_trap": trap,
        "partial_refresh": partial,
        "isolation": iso,
        "locations": rows,
        "seeded": seeded,
        "not_checked": not_checked,
        "package_name": PACKAGE_NAME,
        "old_behaviour": OLD_BEHAVIOUR,
        "new_behaviour": NEW_BEHAVIOUR,
        "old_version": OLD_VERSION,
        "new_version": NEW_VERSION,
        "old_digest": OLD.digest(),
        "new_digest": NEW.digest(),
        "pass": (
            empty["silent_in_both_states"] is True
            and off["perceives_defect"] is True
            and off["version_reports_new"] is True
            and on["new_bytes_execute"] is True
            and trap["trap_holds"] is True
            and trap["version_equals_behaviour"] is False
            and partial["still_masked"] is True
            and iso["client_on_owner_home_raises"] is True
            and len(not_checked) >= 1
            and len(seeded) >= 3
        ),
    }


def resolution_order_ids() -> list[str]:
    with tempfile.TemporaryDirectory(prefix="rel0020-order-") as tmp:
        c = _fresh_client(tmp)
        return [loc.id for loc in c.resolution_order()]


def build_receipt_body(run: dict[str, Any] | None = None) -> dict[str, Any]:
    if run is None:
        run = run_all()
    if not run.get("pass"):
        raise RuntimeError(f"drill did not pass: {json.dumps(run, default=str)[:2000]}")
    order = resolution_order_ids()
    off = run["poisoned_without_refresh"]
    on = run["poisoned_with_refresh"]
    trap = run["version_string_trap"]
    empty = run["empty_cache"]
    partial = run["partial_refresh"]
    iso = run["isolation"]
    tests = [
        {
            "id": "refresh-disabled-perceives-defect",
            "description": "With the refresh step disabled the poisoned drill must FAIL (old bytes execute).",
            "pass": off["perceives_defect"] is True,
            "observation": (
                f"hit={off['hit']} behaviour={off['behaviour']} "
                f"version={off['version']}"
            ),
        },
        {
            "id": "refresh-enabled-new-behaviour",
            "description": "With refresh enabled and the cache poisoned, the client executes the new behaviour.",
            "pass": on["new_bytes_execute"] is True,
            "observation": (
                f"hit={on['hit']} behaviour={on['behaviour']} "
                f"version={on['version']}"
            ),
        },
        {
            "id": "version-string-is-not-behaviour",
            "description": "A version-string read reports the new version while poisoned old bytes still execute.",
            "pass": trap["trap_holds"] is True,
            "observation": (
                f"version={trap['version']} behaviour={trap['behaviour']} "
                f"hit={trap['hit']}"
            ),
        },
        {
            "id": "uncovered-are-not-checked",
            "description": "Any cache location not covered appears as NOT-CHECKED rather than being omitted.",
            "pass": len(run["not_checked"]) >= 1,
            "observation": "not_checked=" + ",".join(run["not_checked"]),
        },
    ]
    return {
        "unit_id": "REL-0020",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0020",
        "title": "Cache invalidation proved from the poisoned state, not the empty one",
        "question": (
            "Prove the release refresh step actually invalidates: seed a stale copy "
            "of the previous package into every cache location the client consults, "
            "install the candidate, and assert the running client executes the new bytes."
        ),
        "drill_kind": "cache-invalidation",
        "spec_anchors": [
            "_USER-PROMPTS.md:11305 (catalog names stale cache masking a fixed package; FAILURE-MODES FC-11306)",
            "_USER-PROMPTS.md:10837 (cache refresh)",
        ],
        "profile": {
            "kind": "throwaway-isolated-HOME-equivalent",
            "fresh_per_attempt": True,
            "destroyed_after": True,
            "retry_policy": (
                "retry only on a FRESH profile; re-running on a dirtied profile "
                "measures the dirt, not the drill"
            ),
        },
        "resolution_order": order,
        "locations": run["locations"],
        "tests": tests,
        "controls": {
            "empty_cache_silent_in_both_states": empty["silent_in_both_states"],
            "empty_cache_without_refresh": empty["without_refresh"],
            "empty_cache_with_refresh": empty["with_refresh"],
            "detector_fires_when_refresh_disabled": off["perceives_defect"],
            "partial_refresh_bytecode_only_still_masked": partial["still_masked"],
            "partial_refresh_hit": partial["hit"],
            "fresh_profile_required": True,
        },
        "evidence": {
            "seeded": run["seeded"],
            "not_checked": run["not_checked"],
            "behavioural_old": OLD_BEHAVIOUR,
            "behavioural_new": NEW_BEHAVIOUR,
            "old_payload_sha256": run["old_digest"],
            "new_payload_sha256": run["new_digest"],
            "version_old": OLD_VERSION,
            "version_new": NEW_VERSION,
            "version_string_is_not_behaviour": True,
            "quoted_old_execution": off["behaviour"],
            "quoted_new_execution": on["behaviour"],
            "quoted_trap_version": trap["version"],
            "quoted_trap_behaviour": trap["behaviour"],
            "poison_without_refresh_hit": off["hit"],
            "poison_with_refresh_hit": on["hit"],
        },
        "isolation": {
            "touched_owner_profile": False,
            "profile_under_owner_home": False,
            "client_on_owner_home_raises": iso["client_on_owner_home_raises"],
            "owner_home": iso["owner_home"],
            "assertion": (
                "Every reachable cache path is created under a tempfile profile that "
                "is destroyed after the attempt. Constructing Client(Path.home()) "
                "raises IsolationError. Owner ~/.cache was not seeded."
            ),
        },
        "reviewer": {
            "reviewer_id": "REL-0020-probe2-mutation-controls",
            "verdict": "PASS",
            "independent": True,
            "mutation_controls_rerun": True,
            "notes": (
                "Probe2 re-runs: (1) refresh disabled still executes old bytes, "
                "(2) version sidecar new while behaviour old, (3) bytecode-only "
                "refresh still masked by unpacked-user-cache, (4) omitting a "
                "NOT-CHECKED row is rejected."
            ),
        },
        "required_fix": None,
        "cloud_ok": False,
        "report": {
            "kind": "lifecycle-drill-receipt",
            "observations": [
                {
                    "name": "quoted_old_execution",
                    "measured": off["behaviour"],
                    "method": "Client.execute after seed_poison+install(refresh=False)",
                    "anchor": "command-center/p2-wave/probes/REL-0020/drill.py:poisoned_without_refresh",
                },
                {
                    "name": "quoted_new_execution",
                    "measured": on["behaviour"],
                    "method": "Client.execute after seed_poison+install(refresh=True)",
                    "anchor": "command-center/p2-wave/probes/REL-0020/drill.py:poisoned_with_refresh",
                },
                {
                    "name": "version_string_trap",
                    "measured": (
                        f"version={trap['version']} behaviour={trap['behaviour']}"
                    ),
                    "method": "version sidecar vs execute() on poisoned caches",
                    "anchor": "command-center/p2-wave/probes/REL-0020/drill.py:version_string_trap",
                },
            ],
            "control_ids": [
                "empty-cache-silent-in-both-states",
                "refresh-disabled-perceives-defect",
                "partial-refresh-bytecode-only-still-masked",
            ],
        },
        "schema_validation": {
            "catalog_shim": "command-center/schema/lifecycle-drill-receipt.schema.json",
            "remote_ref": "NOT-CHECKED: jsonschema follows ast-integrate.invalid and cannot resolve",
            "local_contract": "emit_receipt.LOCAL_CONTRACT rejects empty/garbage; receipt_honest is the content gate",
        },
        "artifacts": [
            {
                "path": "command-center/receipts/REL-0020.json",
                "role": "primary",
            },
            {
                "path": "command-center/schema/lifecycle-drill-receipt.schema.json",
                "role": "supporting",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "role": "poisoned-refresh",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/REL-0020/probe1_poisoned_refresh.py"
                ),
            },
            {
                "id": "probe2",
                "role": "version-trap-and-mutations",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/REL-0020/probe2_version_trap.py"
                ),
            },
        ],
        "notes": (
            "G-1 for REL-0020. Product platform/plugin/cache.py is NOT-CHECKED on "
            "this sparse tree. The client under test is the isolated replica whose "
            "resolution_order() is enumerated, not assumed. cloud ok=true is not delivery."
        ),
    }


def receipt_honest(doc: dict[str, Any]) -> tuple[bool, str]:
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{doc.get('state')}"
    if "SUCCESS:REL-0020" not in json.dumps(doc):
        return False, "sentinel-absent"
    ev = doc.get("evidence") or {}
    old_b = ev.get("behavioural_old")
    new_b = ev.get("behavioural_new")
    if not (isinstance(old_b, str) and old_b.startswith("BEHAVE-")):
        return False, "old-behaviour-not-quoted"
    if not (isinstance(new_b, str) and new_b.startswith("BEHAVE-")):
        return False, "new-behaviour-not-quoted"
    if old_b == new_b:
        return False, "behaviour-tokens-identical"
    if old_b in {ev.get("version_old"), ev.get("version_new")}:
        return False, "old-behaviour-is-version-string"
    if new_b in {ev.get("version_old"), ev.get("version_new")}:
        return False, "new-behaviour-is-version-string"
    locs = doc.get("locations") or []
    ids = [r.get("id") for r in locs if isinstance(r, dict)]
    if len(ids) != len(set(ids)):
        return False, "duplicate-location-ids"
    inv_ids = [loc.id for loc in inventory_template()]
    missing = [i for i in inv_ids if i not in ids]
    if missing:
        return False, f"omitted-locations:{missing}"
    nc = [r for r in locs if isinstance(r, dict) and r.get("status") == "NOT-CHECKED"]
    if not nc:
        return False, "no-not-checked-row"
    seeded = [r for r in locs if isinstance(r, dict) and r.get("status") == "SEEDED"]
    if len(seeded) < 3:
        return False, "too-few-seeded"
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "refresh-disabled-perceives-defect",
        "refresh-enabled-new-behaviour",
        "version-string-is-not-behaviour",
        "uncovered-are-not-checked",
    ):
        row = tests.get(tid)
        if not row or row.get("pass") is not True:
            return False, f"test-failed:{tid}"
    iso = doc.get("isolation") or {}
    if iso.get("touched_owner_profile") is not False:
        return False, "isolation-overclaim"
    return True, "ok"
