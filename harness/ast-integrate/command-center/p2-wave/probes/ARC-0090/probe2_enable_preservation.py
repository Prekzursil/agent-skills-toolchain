#!/usr/bin/env python3
"""Probe 2: curated enable/disable map is restored byte-identically.

Both-states:
  GOOD  migrate(snapshot) restores canonical JSON bytes of the enable map
  BAD   Policy(preserve_enable_on_migrate=False) wipes the map
"""
from __future__ import annotations

import json
import sys
import tempfile
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from cases import PRESERVATION_MAP  # noqa: E402
from model import (  # noqa: E402
    Adapter,
    ContractError,
    Policy,
    SCOPE_FILE,
    SCOPES,
    STDIO_PROCESS_CAP,
    STUB,
    canonical_enable_bytes,
    empty_enable,
    namespaced,
    validate_declaration,
)

ART = REPO / "command-center/phase4/contracts/ARC-0090.json"
SENTINEL = "SUCCESS:ARC-0090"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0090-probe2 {msg}")
    return 1


def file_enable(config_dir: Path) -> dict[str, dict[str, bool]]:
    out: dict[str, dict[str, bool]] = {s: {} for s in SCOPES}
    for scope in SCOPES:
        path = config_dir / SCOPE_FILE[scope]
        doc = json.loads(path.read_text(encoding="utf-8"))
        enabled = doc.get("enabled") or {}
        out[scope] = {str(k): bool(v) for k, v in enabled.items()}
    return out


def apply_map(adapter: Adapter, enable: dict[str, dict[str, bool]]) -> None:
    for scope, mapping in enable.items():
        for server_id, enabled in mapping.items():
            adapter.set_enabled(server_id, enabled, scope=scope)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "ARC-0090":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    stored = doc.get("preservation") or {}
    if not stored.get("byte_identical_restore"):
        return fail("artifact preservation.byte_identical_restore is not true")

    nfail = 0
    original_bytes = canonical_enable_bytes(PRESERVATION_MAP)
    with tempfile.TemporaryDirectory(prefix="arc0090-p2-") as tmp:
        config_dir = Path(tmp) / "good"
        with Adapter(config_dir=config_dir, mark=f"p2g{uuid.uuid4().hex[:8]}") as good:
            apply_map(good, PRESERVATION_MAP)
            snap = good.snapshot_enable()
            before = canonical_enable_bytes(snap)
            if before != original_bytes:
                print("FAILED:ARC-0090-probe2 snapshot bytes != canonical map")
                nfail += 1
            file_before = canonical_enable_bytes(file_enable(config_dir))
            if file_before != original_bytes:
                print("FAILED:ARC-0090-probe2 on-disk files != canonical map")
                nfail += 1
            good.set_enabled("alpha", True, scope="project")
            good.set_enabled("wiped", True, scope="local")
            mutated = canonical_enable_bytes(good.snapshot_enable())
            if mutated == original_bytes:
                print("FAILED:ARC-0090-probe2 mutation did not change the map")
                nfail += 1
            good.migrate(snap)
            after = canonical_enable_bytes(good.snapshot_enable())
            files_after = canonical_enable_bytes(file_enable(config_dir))
            pos = after == original_bytes == files_after
            print(
                f"preserve restore_bytes={len(after)} match={pos} "
                f"mutated_differed={mutated != original_bytes}"
            )
            if not pos:
                print("FAILED:ARC-0090-probe2 migrate did not restore byte-identically")
                nfail += 1

        mutant_dir = Path(tmp) / "mutant"
        with Adapter(
            config_dir=mutant_dir,
            mark=f"p2m{uuid.uuid4().hex[:8]}",
            policy=Policy(preserve_enable_on_migrate=False),
        ) as mutant:
            apply_map(mutant, PRESERVATION_MAP)
            msnap = mutant.snapshot_enable()
            mutant.migrate(msnap)
            destroyed = canonical_enable_bytes(mutant.snapshot_enable())
            empty = canonical_enable_bytes(empty_enable())
            fired = destroyed == empty and destroyed != original_bytes
            print(
                f"mutant-destroy empty={destroyed == empty} "
                f"differs_from_curated={destroyed != original_bytes} fired_on_bad={fired}"
            )
            if not fired:
                print("FAILED:ARC-0090-probe2 mutant did not destroy the enable map")
                nfail += 1

    try:
        validate_declaration("stdio", {})
        print("FAILED:ARC-0090-probe2 empty stdio declaration accepted")
        nfail += 1
    except ContractError:
        print("empty stdio declaration rejected")
    try:
        validate_declaration("http", {"command": ["x"]})
        print("FAILED:ARC-0090-probe2 http+command accepted")
        nfail += 1
    except ContractError:
        print("http+command declaration rejected")
    validate_declaration("stdio", {"command": ["python3", str(STUB)]})
    validate_declaration("http", {"url": "http://127.0.0.1:9/mcp"})

    a = namespaced("alpha", "echo")
    b = namespaced("beta", "echo")
    if a == b or a != "alpha__echo":
        print(f"FAILED:ARC-0090-probe2 namespacing {a!r} {b!r}")
        nfail += 1
    else:
        print(f"namespaced alpha__echo vs beta__echo distinct={a != b}")

    if STDIO_PROCESS_CAP != 8:
        print(f"FAILED:ARC-0090-probe2 cap constant {STDIO_PROCESS_CAP} != 8")
        nfail += 1
    tiny = Policy(stdio_cap=1)
    with tempfile.TemporaryDirectory(prefix="arc0090-p2cap-") as tmp:
        with Adapter(
            config_dir=Path(tmp),
            mark=f"p2c{uuid.uuid4().hex[:8]}",
            policy=tiny,
        ) as adapter:
            adapter.set_enabled("s0", True, scope="project")
            adapter.set_enabled("s1", True, scope="project")
            decl = {"command": ["python3", str(STUB)]}
            first = adapter.mount("s0", transport="stdio", declaration=decl)
            if not first.get("mounted"):
                print("FAILED:ARC-0090-probe2 cap=1 refused the first stdio child")
                nfail += 1
            refused = False
            try:
                adapter.mount("s1", transport="stdio", declaration=decl)
            except ContractError as exc:
                refused = "cap" in str(exc).lower()
            print(f"stdio-cap first_ok={first.get('mounted')} refused_second={refused}")
            if not refused:
                print("FAILED:ARC-0090-probe2 stdio cap did not refuse the extra child")
                nfail += 1

    try:
        import jsonschema
    except ImportError:
        print("WARN: jsonschema missing; skipping artifact schema round-trip")
    else:
        validator = jsonschema.Draft202012Validator(doc)
        garbage = {"blob": "x" * 200, "passing_tests": 999}
        if not list(validator.iter_errors(garbage)):
            print("FAILED:ARC-0090-probe2 schema accepted garbage")
            nfail += 1
        else:
            print("schema rejects garbage")
        good = {
            "server_id": "alpha",
            "transport": "stdio",
            "declaration": {"command": ["python3", "stub.py"]},
            "lifecycle_owner": "adapter",
            "stdio_process_cap": 8,
            "exposed_tools": ["alpha__echo"],
            "enable": PRESERVATION_MAP,
        }
        errs = list(validator.iter_errors(good))
        if errs:
            print(f"FAILED:ARC-0090-probe2 schema rejected valid instance: {errs[0].message}")
            nfail += 1
        else:
            print("schema accepts valid stdio instance")

    if nfail:
        print(f"FAILED:ARC-0090-probe2 failures={nfail}")
        return 1
    print("SUCCESS:ARC-0090-probe2 enable-map byte-identical restore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
