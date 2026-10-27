"""Executable supply-chain scenario: planted edit, whitespace, missing pin.

Runs against a scratch copy of ARC-0010. Does not mutate the live generator.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import gate
import scratch
import templates as T
from fingerprint import digest_bytes, fingerprint
from ownership import REQUIRED_AUTHORIZERS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GEN_DIR = REPO / "command-center/p2-wave/probes/ARC-0010"
PIN_PATH = REPO / T.PIN_REL


def live_generate() -> tuple[object, dict[str, bytes]]:
    mod = scratch.load_generator(GEN_DIR / "generator.py", "a2_gen_live_arc0013")
    files = scratch.generate_from(mod)
    return mod, files


def build_pin(files: dict[str, bytes]) -> dict:
    fp = fingerprint(files)
    pin = {
        "schema_version": 1,
        "kind": "a2-output-fingerprint-pin",
        "algorithm": "sha256",
        "generator_path": T.GENERATOR_REL,
        "registry_path": T.REGISTRY_REL,
        "schema_path": T.SCHEMA_REL,
        "authorized_by": list(REQUIRED_AUTHORIZERS),
        "review_scope": [T.GENERATOR_REL, T.SCHEMA_REL, T.PIN_REL],
        "file_count": fp["file_count"],
        "files": fp["files"],
        "tree_sha256": fp["tree_sha256"],
    }
    PIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    PIN_PATH.write_text(
        json.dumps(pin, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return pin


def _cleanup(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)


def run_planted(pin: dict) -> dict:
    tmp = scratch.copy_generator_tree(GEN_DIR)
    try:
        gen_py = tmp / "generator.py"
        before = scratch.source_sha256(gen_py)
        scratch.plant_semantic(gen_py)
        after = scratch.source_sha256(gen_py)
        mod = scratch.load_generator(gen_py, "a2_gen_planted_arc0013")
        files = scratch.generate_from(mod)
        verdict = gate.check(files, pin, mod.parse_provenance)
        n = len(files)
        n_changed = len(verdict["files_changed"])
        return {
            "caught": verdict["tripped"] is True
            and verdict["reason"] == "output-fingerprint-mismatch"
            and n_changed == n
            and n >= 1
            and before != after,
            "tripped": verdict["tripped"],
            "reason": verdict["reason"],
            "files_changed": n_changed,
            "file_count": n,
            "source_hash_changed": before != after,
            "scratch": str(tmp),
        }
    finally:
        _cleanup(tmp)


def run_whitespace(pin: dict) -> dict:
    tmp = scratch.copy_generator_tree(GEN_DIR)
    try:
        gen_py = tmp / "generator.py"
        before = scratch.source_sha256(gen_py)
        scratch.plant_whitespace(gen_py)
        after = scratch.source_sha256(gen_py)
        mod = scratch.load_generator(gen_py, "a2_gen_ws_arc0013")
        files = scratch.generate_from(mod)
        verdict = gate.check(files, pin, mod.parse_provenance)
        source_would_trip = before != after
        return {
            "silent": verdict["tripped"] is False and verdict["reason"] == "match",
            "tripped": verdict["tripped"],
            "reason": verdict["reason"],
            "files_changed": len(verdict["files_changed"]),
            "source_hash_changed": source_would_trip,
            "source_hash_gate_would_trip": source_would_trip,
            "scratch": str(tmp),
        }
    finally:
        _cleanup(tmp)


def run_missing_pin(files: dict[str, bytes], parse_provenance) -> dict:
    verdict = gate.check(files, None, parse_provenance)
    return {
        "fail_closed": verdict["tripped"] is True
        and verdict["fail_closed"] is True
        and verdict["reason"] == "pin-absent",
        "tripped": verdict["tripped"],
        "reason": verdict["reason"],
    }


def run_clean(files: dict[str, bytes], pin: dict, parse_provenance) -> dict:
    verdict = gate.check(files, pin, parse_provenance)
    return {
        "silent": verdict["tripped"] is False,
        "tripped": verdict["tripped"],
        "reason": verdict["reason"],
        "file_count": verdict["file_count"],
        "tree_sha256": verdict["tree_sha256"],
    }


def provenance_ok(files: dict[str, bytes], parse_provenance) -> dict:
    rows = []
    ok = True
    for rel, raw in sorted(files.items()):
        prov = parse_provenance(raw)
        has = (
            isinstance(prov, dict)
            and str(prov.get("registry_id") or "").strip()
            and str(prov.get("generator_version") or "").strip()
        )
        if not has:
            ok = False
        rows.append(
            {
                "path": rel,
                "registry_id": (prov or {}).get("registry_id"),
                "generator_version": (prov or {}).get("generator_version"),
                "ok": bool(has),
            }
        )
    return {"ok": ok, "files": rows, "count": len(rows)}


def run() -> dict:
    for rel in T.named_paths():
        if not (REPO / rel).is_file():
            raise SystemExit(f"FAILED:ARC-0013 named template missing {rel}")
    mod, files = live_generate()
    pin = build_pin(files)
    clean = run_clean(files, pin, mod.parse_provenance)
    planted = run_planted(pin)
    white = run_whitespace(pin)
    absent = run_missing_pin(files, mod.parse_provenance)
    prov = provenance_ok(files, mod.parse_provenance)
    live_src = digest_bytes((GEN_DIR / "generator.py").read_bytes())
    executed = (
        clean["silent"]
        and planted["caught"]
        and white["silent"]
        and white["source_hash_gate_would_trip"]
        and absent["fail_closed"]
        and prov["ok"]
        and int(clean["file_count"]) == 10
    )
    return {
        "executed": executed,
        "clean": clean,
        "planted_edit": planted,
        "whitespace": white,
        "pin_absent": absent,
        "provenance": {"ok": prov["ok"], "count": prov["count"]},
        "provenance_files": prov["files"],
        "pin_path": T.PIN_REL,
        "pin_tree_sha256": pin["tree_sha256"],
        "live_generator_sha256": live_src,
        "named_template_files": T.NAMED_TEMPLATE_FILES,
        "file_count": int(clean["file_count"]),
    }
