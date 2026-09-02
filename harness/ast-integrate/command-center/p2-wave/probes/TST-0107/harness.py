"""Live checks for TST-0107. Does not write the catalog receipt."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from path_shim import KNOWN_SPAWN, path_shim
from scenario import (
    DEBOUNCE_MS,
    HERE,
    NESTED_SPAWN_BUDGET,
    OUT_REL,
    PAYLOAD,
    REPO,
    SCHEMA_REL,
    SENTINEL,
    UNIT,
)
from surface import (
    FakeClock,
    GATED,
    INPROC,
    OVERBUDGET,
    SLOW,
    StatusSurface,
)


def _fail(name: str, reason: str, **extra: Any) -> dict[str, Any]:
    row = {"id": name, "pass": False, "reason": reason}
    row.update(extra)
    return row


def _ok(name: str, **extra: Any) -> dict[str, Any]:
    row = {"id": name, "pass": True}
    row.update(extra)
    return row


def test_shim_catches_a_known_spawn() -> dict[str, Any]:
    """Detector control: a planted PATH exec must increment the shim log."""
    with path_shim() as shim:
        before = shim.count(KNOWN_SPAWN)
        planted = subprocess.run(
            [KNOWN_SPAWN],
            capture_output=True,
            text=True,
            env=shim.env(),
        )
        after = shim.count(KNOWN_SPAWN)
        jq_before = shim.count("jq")
        jq = subprocess.run(
            ["jq", "-n", "."],
            capture_output=True,
            text=True,
            env=shim.env(),
        )
        jq_after = shim.count("jq")
        if planted.returncode != 0:
            return _fail(
                "test_shim_catches_a_known_spawn",
                "known-spawn helper exited nonzero",
                returncode=planted.returncode,
            )
        if after != before + 1:
            return _fail(
                "test_shim_catches_a_known_spawn",
                "shim did not increment for planted tst0107-probe",
                before=before,
                after=after,
                detector="broken",
            )
        if jq.returncode != 0 or jq_after != jq_before + 1:
            return _fail(
                "test_shim_catches_a_known_spawn",
                "shim did not increment for a live jq spawn",
                jq_rc=jq.returncode,
                jq_before=jq_before,
                jq_after=jq_after,
            )
        return _ok(
            "test_shim_catches_a_known_spawn",
            planted_delta=after - before,
            jq_delta=jq_after - jq_before,
            detector="proven",
            method="PATH-shim",
        )


def test_grep_is_not_the_detector() -> dict[str, Any]:
    """In-proc renderer mentions jq in text but must not spawn it."""
    text = INPROC.read_text(encoding="utf-8")
    if "jq" not in text or KNOWN_SPAWN not in text:
        return _fail(
            "test_grep_is_not_the_detector",
            "fixture lost the grep-trap strings",
        )
    with path_shim() as shim:
        planted = subprocess.run(
            [KNOWN_SPAWN], capture_output=True, env=shim.env()
        )
        if planted.returncode != 0 or shim.count(KNOWN_SPAWN) < 1:
            return _fail(
                "test_grep_is_not_the_detector",
                "refusing to trust a zero: detector control did not fire first",
                detector="unproven",
            )
        jq_before = shim.count("jq")
        known_before = shim.count(KNOWN_SPAWN)
        surface = StatusSurface(shim)
        result = surface.invoke(INPROC, PAYLOAD, force=True)
        if result.status != "ok":
            return _fail(
                "test_grep_is_not_the_detector",
                f"inproc renderer status={result.status}",
                stdout=result.stdout,
            )
        if result.nested_spawns != 0:
            return _fail(
                "test_grep_is_not_the_detector",
                "inproc renderer nested-spawned despite grep-trap-only mentions",
                nested=result.nested_spawns,
                log=shim.entries(),
            )
        if shim.count("jq") != jq_before or shim.count(KNOWN_SPAWN) != known_before:
            return _fail(
                "test_grep_is_not_the_detector",
                "PATH shim recorded a helper the inproc file only mentions",
                entries=shim.entries(),
            )
        return _ok(
            "test_grep_is_not_the_detector",
            text_mentions_jq=True,
            shim_jq_delta=shim.count("jq") - jq_before,
            shim_known_delta=shim.count(KNOWN_SPAWN) - known_before,
            nested_spawns=0,
            stdout=result.stdout,
        )


def test_spawn_count_per_invocation_is_within_budget() -> dict[str, Any]:
    with path_shim() as shim:
        control = subprocess.run(
            [KNOWN_SPAWN], capture_output=True, env=shim.env()
        )
        if control.returncode != 0 or shim.count(KNOWN_SPAWN) < 1:
            return _fail(
                "test_spawn_count_per_invocation_is_within_budget",
                "refusing to trust a zero: detector control did not fire first",
                detector="unproven",
            )
        surface = StatusSurface(shim)
        result = surface.invoke(INPROC, PAYLOAD, force=True)
        if result.status != "ok":
            return _fail(
                "test_spawn_count_per_invocation_is_within_budget",
                f"inproc status={result.status}",
            )
        if result.nested_spawns > NESTED_SPAWN_BUDGET:
            return _fail(
                "test_spawn_count_per_invocation_is_within_budget",
                "inproc exceeded nested-spawn budget",
                nested=result.nested_spawns,
                budget=NESTED_SPAWN_BUDGET,
                log=shim.entries(),
            )
        mutant = surface.invoke(OVERBUDGET, PAYLOAD, force=True)
        if mutant.nested_spawns <= NESTED_SPAWN_BUDGET:
            return _fail(
                "test_spawn_count_per_invocation_is_within_budget",
                "over-budget mutant was silent (gate not load-bearing)",
                nested=mutant.nested_spawns,
                log=shim.entries(),
            )
        return _ok(
            "test_spawn_count_per_invocation_is_within_budget",
            inproc_nested=result.nested_spawns,
            overbudget_nested=mutant.nested_spawns,
            budget=NESTED_SPAWN_BUDGET,
            detector_proven_before_zero=True,
            inproc_stdout=result.stdout,
            overbudget_stdout=mutant.stdout,
        )


def test_idle_session_pays_zero_for_gated_probes() -> dict[str, Any]:
    with path_shim() as shim:
        control = subprocess.run(
            [KNOWN_SPAWN], capture_output=True, env=shim.env()
        )
        if control.returncode != 0 or shim.count(KNOWN_SPAWN) < 1:
            return _fail(
                "test_idle_session_pays_zero_for_gated_probes",
                "refusing to trust a zero: detector control did not fire first",
                detector="unproven",
            )
        surface = StatusSurface(shim)
        idle_gated = surface.session_tick(
            idle=True,
            statusline=INPROC,
            gated_probe=GATED,
            skip_gated_when_idle=True,
        )
        if idle_gated["nested_spawns"] != 0 or idle_gated["gated_probes_run"]:
            return _fail(
                "test_idle_session_pays_zero_for_gated_probes",
                "idle session still paid nested spawns",
                tick=idle_gated,
            )
        idle_ungated = surface.session_tick(
            idle=True,
            statusline=INPROC,
            gated_probe=GATED,
            skip_gated_when_idle=False,
        )
        if idle_ungated["nested_spawns"] < 1:
            return _fail(
                "test_idle_session_pays_zero_for_gated_probes",
                "ungated idle mutant did not spawn (gate not load-bearing)",
                tick=idle_ungated,
            )
        return _ok(
            "test_idle_session_pays_zero_for_gated_probes",
            idle_gated_nested=idle_gated["nested_spawns"],
            idle_ungated_nested=idle_ungated["nested_spawns"],
            gate_load_bearing=True,
        )


def test_debounce_and_cancel() -> dict[str, Any]:
    clock = FakeClock()
    with path_shim() as shim:
        surface = StatusSurface(shim, debounce_ms=DEBOUNCE_MS, clock=clock)
        first = surface.invoke(INPROC, PAYLOAD)
        second = surface.invoke(INPROC, PAYLOAD)
        clock.advance(DEBOUNCE_MS / 1000.0 + 0.001)
        third = surface.invoke(INPROC, PAYLOAD)
        if first.status != "ok":
            return _fail("test_debounce_and_cancel", "first render failed")
        if second.status != "debounced":
            return _fail(
                "test_debounce_and_cancel",
                "second render inside 300 ms was not debounced",
                status=second.status,
            )
        if third.status != "ok":
            return _fail(
                "test_debounce_and_cancel",
                "render after debounce window failed",
                status=third.status,
            )
    with path_shim() as shim:
        killer = StatusSurface(shim, timeout_ms=150)
        slow = killer.invoke(SLOW, PAYLOAD, force=True)
        if not slow.cancelled or slow.status != "cancelled":
            return _fail(
                "test_debounce_and_cancel",
                "slow render was not CANCELLED",
                status=slow.status,
                elapsed_ms=slow.elapsed_ms,
            )
        if "should-not-print" in slow.stdout:
            return _fail(
                "test_debounce_and_cancel",
                "cancelled render still printed completion",
            )
        return _ok(
            "test_debounce_and_cancel",
            first=first.status,
            second=second.status,
            third=third.status,
            slow_status=slow.status,
            slow_elapsed_ms=round(slow.elapsed_ms, 3),
            debounce_ms=DEBOUNCE_MS,
        )


def sample_tool_ms(cmd: list[str], n: int = 5) -> dict[str, Any]:
    times: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, check=False)
        times.append((time.perf_counter() - t0) * 1000.0)
        if proc.returncode != 0:
            return {
                "cmd": cmd,
                "ok": False,
                "returncode": proc.returncode,
                "samples_ms": times,
            }
    return {
        "cmd": cmd,
        "ok": True,
        "n": n,
        "samples_ms": [round(x, 3) for x in times],
        "median_ms": round(sorted(times)[n // 2], 3),
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
    }


def tool_cost_samples() -> dict[str, Any]:
    jq = shutil.which("jq")
    bash = shutil.which("bash")
    out: dict[str, Any] = {}
    if jq:
        out["jq"] = sample_tool_ms([jq, "-n", "."])
    else:
        out["jq"] = {"ok": False, "reason": "jq not on PATH"}
    if bash:
        out["bash"] = sample_tool_ms([bash, "-c", ":"])
    else:
        out["bash"] = {"ok": False, "reason": "bash not on PATH"}
    return out


# Local Draft-07 discriminator. jsonschema 4.10.3 on this box follows $ref on
# the generated catalog shim out to https://ast-integrate.invalid (network)
# and cannot take schema_resolver's registry= kwarg (needs jsonschema>=4.18).
# Never call jsonschema.validate on the shim. Disk-only RefResolver is
# catalog_schema_errors(); this local schema is the always-available rejector.
LOCAL_DISCRIMINATOR = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "artifacts",
        "evidence",
        "manifest_registration",
        "min_bytes_threshold",
        "negative_controls",
        "report",
        "residual_unknowns",
        "retry",
        "reviewer",
        "schema_version",
        "sentinel",
        "spec_anchor",
        "state",
        "tests",
        "timestamps",
        "unit_id",
    ],
    "properties": {
        "min_bytes_threshold": {"type": "integer", "minimum": 1},
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {"kind": {"const": "benchmark-receipt"}},
        },
        "schema_version": {"const": 1},
        "sentinel": {"type": "string", "pattern": "^SUCCESS:TST-0107"},
        "state": {"const": "SUCCESS"},
        "unit_id": {"const": "TST-0107"},
    },
}


def catalog_schema_errors(doc: dict[str, Any]) -> list[str]:
    """Validate against the physical benchmark-receipt profile. Disk only."""
    import jsonschema
    from jsonschema import RefResolver

    profiles_path = REPO / "platform/schema/artifact-class-profiles.schema.json"
    receipt_path = REPO / "platform/schema/receipt.schema.json"
    shim_path = REPO / SCHEMA_REL
    profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    shim = json.loads(shim_path.read_text(encoding="utf-8"))
    store = {
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
        "https://ast-integrate.invalid/command-center/schema/benchmark-receipt.schema.json": shim,
    }
    for blob in (profiles, receipt, shim):
        sid = blob.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = blob
    resolver = RefResolver(
        base_uri=str(shim.get("$id") or shim_path.as_uri()),
        referrer=shim,
        store=store,
    )
    validator = jsonschema.Draft202012Validator(shim, resolver=resolver)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def local_schema_errors(doc: dict[str, Any]) -> list[str]:
    import jsonschema

    jsonschema.Draft7Validator.check_schema(LOCAL_DISCRIMINATOR)
    validator = jsonschema.Draft7Validator(LOCAL_DISCRIMINATOR)
    return [
        f"{list(e.path)}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]


def schema_garbage_rejection() -> dict[str, Any]:
    schema_path = REPO / SCHEMA_REL
    if not schema_path.is_file():
        return _fail("schema_garbage_rejection", "schema file missing")
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        return _fail("schema_garbage_rejection", "jsonschema not installed")
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 2000},
    ]
    local_rejected = sum(1 for doc in garbage if local_schema_errors(doc))
    try:
        catalog_rejected = sum(1 for doc in garbage if catalog_schema_errors(doc))
        catalog_ok = True
    except Exception as exc:
        catalog_rejected = 0
        catalog_ok = False
        catalog_exc = f"{type(exc).__name__}: {exc}"
    else:
        catalog_exc = ""
    if local_rejected != 3:
        return _fail(
            "schema_garbage_rejection",
            "local discriminator accepted garbage",
            rejected=local_rejected,
        )
    if catalog_ok and catalog_rejected != 3:
        return _fail(
            "schema_garbage_rejection",
            "physical catalog schema accepted garbage",
            rejected=catalog_rejected,
        )
    if not catalog_ok:
        return _fail(
            "schema_garbage_rejection",
            "physical catalog schema did not compile (disk resolver)",
            error=catalog_exc[:500],
        )
    return _ok(
        "schema_garbage_rejection",
        rejected=3,
        of=3,
        local_rejected=local_rejected,
        catalog_rejected=catalog_rejected,
        method="Draft7-local+Draft202012-RefResolver-disk",
    )


def receipt_shape_ok() -> dict[str, Any]:
    art = REPO / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return _fail("receipt_shape_ok", "receipt missing")
    text = art.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return _fail("receipt_shape_ok", f"unparseable:{exc}")
    if not isinstance(doc, dict):
        return _fail("receipt_shape_ok", "receipt-not-object")
    if doc.get("unit_id") != UNIT:
        return _fail("receipt_shape_ok", f"unit_id={doc.get('unit_id')}")
    if SENTINEL not in text:
        return _fail("receipt_shape_ok", "sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail("receipt_shape_ok", f"self-declared:{st}")
    local_errs = local_schema_errors(doc)
    if local_errs:
        return _fail(
            "receipt_shape_ok",
            "local-schema",
            errors=local_errs[:8],
        )
    try:
        cat_errs = catalog_schema_errors(doc)
    except Exception as exc:
        return _fail(
            "receipt_shape_ok",
            f"catalog-resolver:{type(exc).__name__}: {exc}",
        )
    if cat_errs:
        return _fail(
            "receipt_shape_ok",
            "catalog-schema",
            errors=cat_errs[:12],
        )
    return _ok(
        "receipt_shape_ok",
        schema="PASS",
        bytes=art.stat().st_size,
        method="Draft7-local+Draft202012-RefResolver-disk",
    )


def detector_bundle() -> dict[str, Any]:
    a = test_shim_catches_a_known_spawn()
    b = test_grep_is_not_the_detector()
    return {
        "pass": bool(a.get("pass") and b.get("pass")),
        "checks": [a, b],
    }


def budget_bundle() -> dict[str, Any]:
    a = test_spawn_count_per_invocation_is_within_budget()
    b = test_idle_session_pays_zero_for_gated_probes()
    c = test_debounce_and_cancel()
    d = schema_garbage_rejection()
    return {
        "pass": all(x.get("pass") for x in (a, b, c, d)),
        "checks": [a, b, c, d],
    }


def all_named_tests() -> list[dict[str, Any]]:
    return [
        test_shim_catches_a_known_spawn(),
        test_spawn_count_per_invocation_is_within_budget(),
        test_idle_session_pays_zero_for_gated_probes(),
        test_grep_is_not_the_detector(),
        test_debounce_and_cancel(),
        schema_garbage_rejection(),
    ]
