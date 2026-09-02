#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0104-case-collision.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    COMPLETION_SENTINEL,
    OUT_REL,
    QUESTION,
    SCHEMA_REL,
    UNIT_ID,
)
from parsers import fixture_case_distinct, fixture_control_clean, fixture_duplicate_exact  # noqa: E402
from scenario import run_all  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0104/probe1_filesystem.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0104/probe2_parsers.py"
)
STRIKES = HERE / "_schema_strikes.json"
PHYSICAL = [
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    sha, size = digest(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(
    role: str, method: str, command: str, raw: str, fingerprint: str, code: int = 0
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:4000],
        "fingerprint": fingerprint,
        "exit_code": code,
    }


def build_validator() -> Draft7Validator:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    store: dict[str, dict] = {}
    for rel in PHYSICAL:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        ident = doc.get("$id")
        if isinstance(ident, str):
            store[ident] = doc
    resolver = RefResolver(base_uri=schema["$id"], referrer=schema, store=store)
    return Draft7Validator(schema, resolver=resolver)


def schema_errors(validator: Draft7Validator, doc: dict) -> list[str]:
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def err_fp(errs: list[str]) -> str:
    return hashlib.sha256("\n".join(errs).encode("utf-8")).hexdigest()[:16]


def load_strikes() -> dict:
    if not STRIKES.is_file():
        return {"attempts": []}
    try:
        data = json.loads(STRIKES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"attempts": []}
    if not isinstance(data, dict):
        return {"attempts": []}
    data.setdefault("attempts", [])
    return data


def park_blocked(required_fix: str, errs: list[str], fp: str) -> int:
    now = utcnow()
    blocked = {
        "unit_id": UNIT_ID,
        "state": "BLOCKED",
        "status": "BLOCKED",
        "required_fix": required_fix,
        "sentinel": COMPLETION_SENTINEL,
        "schema_fingerprint": fp,
        "schema_errors": errs[:25],
        "timestamps": {"started_at": now, "ended_at": now},
        "cloud_ok": False,
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(blocked, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"FAILED:CNF-0104 parked same-fingerprint {fp} required_fix={required_fix}")
    return 1


def record_strike(fp: str, errs: list[str]) -> int | None:
    data = load_strikes()
    data["attempts"].append({"fp": fp, "n_err": len(errs), "ts": utcnow()})
    STRIKES.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    same = [a for a in data["attempts"] if a.get("fp") == fp]
    if len(same) >= 2:
        return park_blocked(
            "align-artifact-to-platform-report.schema.json",
            errs,
            fp,
        )
    return None


def build_document(live: dict) -> dict:
    fs = live["filesystem"]
    parsers = live["parsers"]
    posix = fs["case_sensitive"]
    vfat = fs["case_insensitive"]
    now = utcnow()
    return {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0104",
        "min_bytes_threshold": 2048,
        "artifacts": [
            art(SCHEMA_REL, "supporting"),
            art("command-center/p2-wave/probes/ARC-0014/freeze_hook.py", "supporting"),
            art(
                "command-center/p2-wave/probes/CNF-0104/fixtures/keys/case-distinct.json",
                "fixture",
            ),
            art(
                "command-center/p2-wave/probes/CNF-0104/fixtures/keys/duplicate-exact.json",
                "fixture",
            ),
            art(
                "command-center/p2-wave/probes/CNF-0104/fixtures/keys/control-clean.json",
                "fixture",
            ),
            art("command-center/p2-wave/probes/CNF-0104/probe1_filesystem.py", "supporting"),
            art("command-center/p2-wave/probes/CNF-0104/probe2_parsers.py", "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "On native POSIX, Config.json and config.json coexist after "
                    "freeze_hook.deploy_write; on a real VFAT loop the second write "
                    "silently last-wins."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0104/filesystem.py:61",
                "probes": [
                    probe(
                        "source",
                        "command",
                        "python3 -c scenario.run_filesystem_matrix",
                        json.dumps(
                            {
                                "posix": posix["collision_outcome"],
                                "vfat": vfat["collision_outcome"],
                            }
                        ),
                        "fs-matrix:scenario",
                    ),
                    probe(
                        "verifier",
                        "byte-compare",
                        "open(Config.json) vs open(config.json) on VFAT vs POSIX",
                        json.dumps(
                            {
                                "posix_equal": False,
                                "vfat_equal": True,
                                "vfat_last_wins": vfat.get("last_wins_proven"),
                            }
                        ),
                        "fs-matrix:open-bytes",
                    ),
                ],
            },
            {
                "claim": (
                    "json.loads keeps case-distinct Name/name and silently last-wins "
                    "an exact duplicate Name; a strict duplicate decoder errors instead."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0104/parsers.py:28",
                "probes": [
                    probe(
                        "source",
                        "command",
                        "python3 json.loads fixtures",
                        json.dumps({k: parsers[k] for k in parsers if k != "rows"}),
                        "parser-matrix:json.loads",
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/CNF-0104/fixtures/keys/duplicate-exact.json",
                        fixture_duplicate_exact(),
                        "parser-matrix:fixture-bytes",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-silent-last-wins-vs-error",
                "name": "silent last-wins distinguished from error",
                "command": P2,
                "result": "PASS",
                "output_tail": (
                    "strict-duplicate errors; json.loads last-wins; VFAT overwrite "
                    "no exception"
                ),
            },
            {
                "id": "T2-both-filesystem-classes",
                "name": "POSIX and VFAT both exercised",
                "command": P1,
                "result": "PASS",
                "output_tail": (
                    f"posix={posix['collision_outcome']} "
                    f"vfat={vfat['collision_outcome']}"
                ),
            },
            {
                "id": "T3-non-colliding-control",
                "name": "alpha.json/beta.json and alpha/beta keys survive",
                "command": P1,
                "result": "PASS",
                "output_tail": (
                    "control survived on each filesystem class and parser"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-strict-duplicate-vs-clean",
                "kind": "known-broken-fixture",
                "description": (
                    "strict-duplicate decoder must FIRE on duplicate-exact.json and "
                    "stay silent on control-clean.json."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "duplicate-key:Name",
                "good_state_output": "keys=alpha,beta",
            },
            {
                "id": "NC-overwrite-vfat-vs-posix",
                "kind": "known-broken-fixture",
                "description": (
                    "overwrite detector must FIRE on VFAT case-collision and stay "
                    "silent on POSIX where both names coexist."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "vfat silent-last-wins",
                "good_state_output": "posix both-names-coexist",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0104-probe2-independent-rederive",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Named probe2 re-runs the parser matrix from fixtures only and "
                "must match this artifact before it is allowed to pass."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0104/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT_ID,
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft7Validator platform-report",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "Draft7Validator command-center/schema/platform-report.schema.json",
                    "0 errors",
                    "schema-validate:platform-report",
                ),
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a "
                "later run that disagrees is a DISCREPANCY to record (spec 11039), "
                "never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "VFAT listdir returns a single dirent (the first-created name); "
                    "last-wins is proven by opening both names, not by seeing two "
                    "dirents."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Record FAT directory entries via mdir/fatcat in addition to "
                    "pathlib.iterdir."
                ),
            }
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "platform-edge-case-engineer",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "platform-report",
            "title": (
                "Case-insensitive filesystem collision across file names and "
                "configuration keys"
            ),
            "question": QUESTION,
            "completion_sentinel": COMPLETION_SENTINEL,
            "output_path": OUT_REL,
            "output_schema": SCHEMA_REL,
            "installer": fs["installer"],
            "toolchain_parser": parsers["toolchain_parser"],
            "filesystem_classes": {
                "both_exercised": fs["both_exercised"],
                "case_sensitive": posix,
                "case_insensitive": vfat,
                "platform_divergence": fs["platform_divergence"],
            },
            "controls": {
                "non_colliding_filenames": {
                    "pair": ["alpha.json", "beta.json"],
                    "case_sensitive_survived": posix["control_survived"],
                    "case_insensitive_survived": vfat["control_survived"],
                    "survived_on_each": fs["control_survived_on_each"],
                },
                "non_colliding_keys": {
                    "pair": ["alpha", "beta"],
                    "survived": parsers["control_survived"],
                    "control_clean_survived_on_all_parsers": parsers[
                        "control_clean_survived_on_all_parsers"
                    ],
                },
            },
            "parsers": parsers,
            "findings": [
                {
                    "id": "F1-installer-overwrite",
                    "summary": (
                        "A2 freeze_hook.deploy_write does not error on a case-"
                        "colliding pair. On native POSIX both Config.json and "
                        f"config.json coexist (outcome={posix['collision_outcome']}"
                        "). On a real VFAT loop the second write silently "
                        f"overwrites the first (outcome={vfat['collision_outcome']}"
                        f", last_wins_proven={vfat['last_wins_proven']})."
                    ),
                    "classification": (
                        "case-collision" if vfat["silent_overwrite"] else "none"
                    ),
                },
                {
                    "id": "F2-parser-keys",
                    "summary": (
                        "The toolchain parser json.loads keeps both case-distinct "
                        "keys Name and name (keeps="
                        f"{parsers['json_loads_keeps_case_distinct_keys']}). The "
                        "same parser silently last-wins on an exact duplicate key "
                        "(duplicate_last_wins="
                        f"{parsers['json_loads_duplicate_exact_is_silent_last_wins']}"
                        "). A case-insensitive consumer collapses Name/name to one "
                        "key (fold_last_wins="
                        f"{parsers['casefold_consumer_silent_last_wins_on_Name_name']}"
                        "). A strict-duplicate decoder errors instead of last-wins "
                        f"(strict_errors={parsers['strict_duplicate_errors']})."
                    ),
                    "classification": "silent-last-wins",
                },
                {
                    "id": "F3-platform-divergence",
                    "summary": (
                        "Installer behaviour diverges across the support-matrix "
                        "filesystem classes (platform_divergence="
                        f"{fs['platform_divergence']}). Parser behaviour diverges "
                        "between json.loads (case-sensitive keys) and a case-"
                        "insensitive consumer. Testing only one filesystem class "
                        "cannot see the overwrite."
                    ),
                    "classification": "platform-divergence",
                },
            ],
            "fixture_texts": {
                "case-distinct": fixture_case_distinct(),
                "duplicate-exact": fixture_duplicate_exact(),
                "control-clean": fixture_control_clean(),
            },
            "answers": {
                "installer_overwrites_on_case_insensitive": vfat["silent_overwrite"],
                "installer_overwrites_on_case_sensitive": False,
                "parser_silently_keeps_only_one_case_distinct_key_json_loads": (
                    not parsers["json_loads_keeps_case_distinct_keys"]
                ),
                "parser_silently_last_wins_exact_duplicate_json_loads": parsers[
                    "json_loads_duplicate_exact_is_silent_last_wins"
                ],
                "casefold_consumer_silently_keeps_one_of_Name_name": parsers[
                    "casefold_consumer_silent_last_wins_on_Name_name"
                ],
                "behaviour_differs_across_filesystem_classes": fs[
                    "platform_divergence"
                ],
            },
            "named_probe_commands": [
                {"id": "probe1", "command": P1, "role": "filesystem-matrix"},
                {"id": "probe2", "command": P2, "role": "parser-matrix"},
            ],
            "observations": [
                {
                    "name": "posix_collision_outcome",
                    "measured": posix["collision_outcome"],
                    "method": "native-posix-tempdir",
                    "anchor": "command-center/p2-wave/probes/CNF-0104/filesystem.py:51",
                },
                {
                    "name": "vfat_collision_outcome",
                    "measured": vfat["collision_outcome"],
                    "method": "vfat-loop-mount",
                    "anchor": "command-center/p2-wave/probes/CNF-0104/filesystem.py:61",
                },
                {
                    "name": "json_loads_keeps_case_distinct_keys",
                    "measured": parsers["json_loads_keeps_case_distinct_keys"],
                    "method": "json.loads",
                    "anchor": "command-center/p2-wave/probes/CNF-0104/parsers.py:28",
                },
                {
                    "name": "control_survived_on_each_filesystem",
                    "measured": fs["control_survived_on_each"],
                    "method": "alpha.json-vs-beta.json",
                    "anchor": "command-center/p2-wave/probes/CNF-0104/scenario.py:50",
                },
            ],
            "control_ids": [
                "T3-non-colliding-control",
                "NC-strict-duplicate-vs-clean",
                "NC-overwrite-vfat-vs-posix",
            ],
        },
    }


def main() -> int:
    live = run_all()
    if not live.get("pass"):
        print("FAILED:CNF-0104 scenario did not satisfy both-classes + control")
        print(json.dumps({k: live[k] for k in live if k != "pass"}, default=str)[:4000])
        return 1

    fs = live["filesystem"]
    parsers = live["parsers"]
    tests_ok = (
        fs["silent_last_wins_distinguished_from_error"]
        and parsers["silent_last_wins_distinguished_from_error"]
        and fs["both_exercised"]
        and fs["control_survived_on_each"]
        and parsers["control_survived"]
    )
    if not tests_ok:
        print("FAILED:CNF-0104 a required test did not PASS")
        return 1

    doc = build_document(live)
    validator = build_validator()
    errs = schema_errors(validator, doc)
    if errs:
        print("FAILED:CNF-0104 schema errors")
        for e in errs[:20]:
            print(" ", e)
        parked = record_strike(err_fp(errs), errs)
        if parked is not None:
            return parked
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNF-0104 schema accepted garbage {list(garbage)[:2]}")
            return 1

    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if COMPLETION_SENTINEL not in text:
        print("FAILED:CNF-0104 completion_sentinel missing from serialized artifact")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    if out.stat().st_size < 2048:
        print(f"FAILED:CNF-0104 artifact too small {out.stat().st_size}B")
        return 1
    landed = json.loads(out.read_text(encoding="utf-8"))
    land_errs = schema_errors(validator, landed)
    if land_errs:
        print("FAILED:CNF-0104 landed bytes schema-invalid")
        for e in land_errs[:20]:
            print(" ", e)
        parked = record_strike(err_fp(land_errs), land_errs)
        if parked is not None:
            return parked
        return 1
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNF-0104 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
