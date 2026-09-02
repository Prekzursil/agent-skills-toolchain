"""Force each catalog fallback kind; assert event surface and artifact survival."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "fixtures"))

import census  # noqa: E402
import events as E  # noqa: E402
import product as P  # noqa: E402


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _alive(path: Path, original: str | None = None) -> None:
    if not path.is_file():
        raise AssertionError(f"work artifact vanished: {path}")
    if original is not None and path.read_text(encoding="utf-8") != original:
        raise AssertionError(f"work artifact mutated: {path}")


def force_fixture_kinds() -> dict:
    """Force all five kinds plus the SILENT control. Returns structured results."""
    results = []
    with tempfile.TemporaryDirectory(prefix="bld0026-") as tmp:
        td = Path(tmp)
        work = td / "work.json"
        original = '{"keep": true, "payload": "BLD-0026-artifact"}'
        _write(work, original)

        # 1 default-on-exception: corrupt JSON, function returns {}, file remains
        E.reset()
        _write(work, "{not json")
        out = P.default_on_exception(work)
        _alive(work, "{not json")
        if out != {}:
            raise AssertionError(f"default-on-exception returned {out!r}")
        if not E.USER_EVENTS:
            raise AssertionError("default-on-exception emitted no user event")
        results.append(
            {
                "kind": "default-on-exception",
                "classification": "LOUD",
                "event": E.USER_EVENTS[-1],
                "artifact_survived": True,
            }
        )

        # 2 best-effort-parse
        E.reset()
        messy = 'garbage {"salvaged": true} trailing'
        _write(work, messy)
        out = P.best_effort_parse(work)
        _alive(work, messy)
        if not E.USER_EVENTS:
            raise AssertionError("best-effort-parse emitted no user event")
        if out.get("salvaged") is not True:
            raise AssertionError(f"best-effort-parse did not salvage: {out!r}")
        results.append(
            {
                "kind": "best-effort-parse",
                "classification": "LOUD",
                "event": E.USER_EVENTS[-1],
                "artifact_survived": True,
            }
        )

        # 3 capability-missing-shim
        E.reset()
        _write(work, original)
        out = P.capability_missing_shim("anthropic", work)
        _alive(work, original)
        if not str(out).startswith("shim-local:"):
            raise AssertionError(f"shim returned {out!r}")
        if not E.USER_EVENTS:
            raise AssertionError("capability-missing-shim emitted no user event")
        results.append(
            {
                "kind": "capability-missing-shim",
                "classification": "LOUD",
                "event": E.USER_EVENTS[-1],
                "artifact_survived": True,
            }
        )

        # 4 cached-value-on-error
        E.reset()
        cache = {"last": "PRIOR-GOOD"}
        _write(work, "")
        out = P.cached_value_on_error(work, cache)
        _alive(work, "")
        if out != "PRIOR-GOOD":
            raise AssertionError(f"cache fallback returned {out!r}")
        if not E.USER_EVENTS:
            raise AssertionError("cached-value-on-error emitted no user event")
        results.append(
            {
                "kind": "cached-value-on-error",
                "classification": "LOUD",
                "event": E.USER_EVENTS[-1],
                "artifact_survived": True,
            }
        )

        # 5 vendor-adapter-substitution
        E.reset()
        _write(work, original)
        out = P.vendor_adapter_substitution("anthropic", work)
        _alive(work, original)
        if not str(out).startswith("secondary:local:"):
            raise AssertionError(f"adapter substitution returned {out!r}")
        if not E.USER_EVENTS:
            raise AssertionError("vendor-adapter-substitution emitted no user event")
        results.append(
            {
                "kind": "vendor-adapter-substitution",
                "classification": "LOUD",
                "event": E.USER_EVENTS[-1],
                "artifact_survived": True,
            }
        )

        # CONTROL SILENT: debug log only
        E.reset()
        _write(work, "{bad")
        out = P.silent_debug_only(work)
        _alive(work, "{bad")
        if E.USER_EVENTS:
            raise AssertionError("silent_debug_only leaked a user-visible event")
        if not E.DEBUG_EVENTS:
            raise AssertionError("silent_debug_only produced no debug trace")
        results.append(
            {
                "kind": "default-on-exception",
                "classification": "SILENT",
                "function": "silent_debug_only",
                "event": E.DEBUG_EVENTS[-1],
                "artifact_survived": True,
            }
        )

        # CONTROL no-fallback: must raise, must not be in census
        E.reset()
        raised = False
        try:
            P.no_fallback_strict(work)
        except json.JSONDecodeError:
            raised = True
        _alive(work, "{bad")
        if not raised:
            raise AssertionError("no_fallback_strict did not raise")
        fx = census.as_entries(census.scan_fixtures())
        if not census.no_fallback_in_register(fx):
            raise AssertionError("no_fallback_strict appeared in the register")
        results.append(
            {
                "kind": "none",
                "classification": "NOT-A-FALLBACK",
                "function": "no_fallback_strict",
                "raised": True,
                "in_register": False,
            }
        )
    return {"forced": len([r for r in results if r["classification"] in {"LOUD", "SILENT"}]), "results": results}


def force_live() -> dict:
    """Two-strike injection against live shipped fallbacks that we can import."""
    sys.path.insert(0, str(REPO / "command-center"))
    import ready_units as ru  # noqa: E402

    catalog = ru.CATALOG
    catalog_bytes = catalog.read_bytes() if catalog.is_file() else b""
    unreachable: list[dict] = []
    forced: list[dict] = []

    # Strike 1+2: capability-missing resolver. platform/lib/schema_resolver.py exists
    # on this tree, so force the missing-file branch by pointing REPO off-disk.
    # CATALOG is already bound to the real path; the work artifact must survive.
    saved_repo = ru.REPO
    ru.REPO = Path("/nonexistent-bld0026-force-resolver")
    try:
        for strike in (1, 2):
            E.reset()
            mod = ru._load_resolver()
            still = catalog.is_file() and catalog.read_bytes() == catalog_bytes
            user = list(E.USER_EVENTS)
            if mod is not None:
                unreachable.append(
                    {
                        "id": "live:ready_units.py:_load_resolver",
                        "strike": strike,
                        "reason": "resolver unexpectedly loaded",
                    }
                )
                continue
            if not still:
                raise AssertionError("catalog artifact changed during resolver fallback")
            if not user:
                # After two strikes without a user event, pivot rather than a third try.
                unreachable.append(
                    {
                        "id": "live:ready_units.py:_load_resolver",
                        "strike": strike,
                        "reason": "no user-visible degradation event",
                    }
                )
            else:
                forced.append(
                    {
                        "id": "live:ready_units.py:_load_resolver",
                        "strike": strike,
                        "classification": "LOUD",
                        "event": user[-1],
                        "artifact_survived": True,
                    }
                )
    finally:
        ru.REPO = saved_repo

    # SILENT live control: historical _prefix_predicate swallow.
    class Boom:
        def validate_artifact(self, doc, schema):  # noqa: ANN001
            raise RuntimeError("forced-injection")

    unit = {
        "output_path": "command-center/WORK-UNIT-CATALOG.json",
        "output_schema": "command-center/schema/blindspot-register.schema.json",
    }
    if hasattr(ru, "_prefix_predicate"):
        E.reset()
        got = ru._prefix_predicate(unit, Boom())
        if got is not True:
            raise AssertionError(f"_prefix_predicate expected True (old skip), got {got!r}")
        if E.USER_EVENTS:
            raise AssertionError("_prefix_predicate leaked a user-visible event")
        forced.append(
            {
                "id": "live:ready_units.py:_prefix_predicate",
                "classification": "SILENT",
                "artifact_survived": catalog.is_file(),
                "note": "historical silent skip reproduced; no user-visible event",
            }
        )
    else:
        unreachable.append(
            {
                "id": "live:ready_units.py:_prefix_predicate",
                "reason": "symbol absent",
                "strike": 1,
            }
        )
        unreachable.append(
            {
                "id": "live:ready_units.py:_prefix_predicate",
                "reason": "symbol absent",
                "strike": 2,
            }
        )

    # Pivot rule: two failures of the same branch -> UNREACHABLE-BY-INJECTION, no third try.
    pivoted = []
    counts: dict[str, int] = {}
    for row in unreachable:
        counts[row["id"]] = counts.get(row["id"], 0) + 1
    for fid, n in counts.items():
        if n >= 2:
            pivoted.append(fid)
    payload = {
        "forced": forced,
        "forced": forced,
        "unreachable_strikes": unreachable,
        "unreachable_strikes": unreachable,
        "unreachable_by_injection": pivoted,
        "unreachable_by_injection": pivoted,
        "strikes_then_pivot": 2,
        "strikes_then_pivot": 2,
    }
    return payload


force_fixture_kinds = force_fixture_kinds
force_live = force_live
