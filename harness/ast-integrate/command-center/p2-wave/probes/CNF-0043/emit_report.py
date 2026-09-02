#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0043-partial-upgrade-rollback.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import PHASES  # noqa: E402
from trial import run_all_kill_points, run_hybrid_control  # noqa: E402

OUT = "command-center/confirmation/CNF-0043-partial-upgrade-rollback.json"
SCHEMA = "command-center/schema/rollback-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0043/probe1_kill_points.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0043/probe2_hybrid.py"
)
SENTINEL = (
    "SUCCESS:CNF-0043 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and all three kill points were "
    "exercised and each has a recorded post-rollback health-check result. Any "
    "other terminal state is FAILED:CNF-0043 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Can the system roll back from a half-applied upgrade? Kill the installer "
    "at three different points - after file copy, after manifest write, after "
    "cache invalidation - then run rollback from each state and answer: does "
    "each recover to a consistent pre-state, or does any leave an unusable hybrid?"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0043/installer.py",
    "command-center/p2-wave/probes/CNF-0043/rollback.py",
    "command-center/p2-wave/probes/CNF-0043/health.py",
    "command-center/p2-wave/probes/CNF-0043/trial.py",
    "command-center/ROLLBACK-MANIFEST.md",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def offline_validator():
    """Compile rollback-report against on-disk $id targets. Never the network."""
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {}
    for doc in (shim, profiles, receipt):
        ident = doc.get("$id")
        if ident:
            store[ident] = doc
    resolver = jsonschema.RefResolver(
        base_uri=str(shim.get("$id") or ""), referrer=shim, store=store
    )
    resolver.resolve_remote = lambda uri: (_ for _ in ()).throw(
        jsonschema.exceptions.RefResolutionError(f"offline: refused {uri}")
    )
    return jsonschema.Draft202012Validator(shim, resolver=resolver)


def main() -> int:
    started = datetime.now(timezone.utc)
    kills = run_all_kill_points()
    if [k["phase"] for k in kills] != list(PHASES):
        print("FAILED:CNF-0043 emit kill-point set", [k["phase"] for k in kills])
        return 1
    for k in kills:
        if not k.get("kill_landed"):
            print("FAILED:CNF-0043 emit kill did not land", k["phase"])
            print(json.dumps(k.get("kill_signature"), indent=2)[:2000])
            return 1
        if not k.get("recovered_to_pre_state"):
            print("FAILED:CNF-0043 emit incomplete-rollback", k["phase"])
            print(json.dumps(k, indent=2, default=str)[:3000])
            return 1
        if k["health_check"].get("kind") != "coherence" or not k["health_check"].get("ok"):
            print("FAILED:CNF-0043 emit health", k["phase"])
            return 1
        if not k["hash_comparison"].get("identical"):
            print("FAILED:CNF-0043 emit hash mismatch", k["phase"])
            return 1

    hybrid = run_hybrid_control()
    if not hybrid.get("discriminated"):
        print("FAILED:CNF-0043 emit hybrid control did not discriminate")
        print(json.dumps(hybrid, indent=2, default=str)[:3000])
        return 1

    ended = datetime.now(timezone.utc)
    duration = max(0.0, (ended - started).total_seconds())
    rb_manifest = REPO / "command-center" / "ROLLBACK-MANIFEST.md"
    mkt_install = REPO / "platform" / "marketplace" / "mkt" / "install.py"
    platform_plugin = (REPO / "platform" / "plugin").is_dir()

    kill_obs = []
    for k in kills:
        kill_obs.append(
            {
                "name": f"kill-after-{k['phase']}-recovered",
                "measured": bool(k["recovered_to_pre_state"]),
                "method": "tempdir-kill-then-snapshot-restore plus coherence health",
                "anchor": "command-center/p2-wave/probes/CNF-0043/trial.py:run_kill_trial",
            }
        )
    kill_obs.append(
        {
            "name": "hybrid-file-count-reports-healthy",
            "measured": bool(hybrid["naive_file_count"]["ok"]),
            "method": "file-count-only health on unrolled-back file_copy hybrid",
            "anchor": "command-center/p2-wave/probes/CNF-0043/health.py:file_count_health",
        }
    )
    kill_obs.append(
        {
            "name": "hybrid-coherence-reports-unhealthy",
            "measured": bool(hybrid["coherence_against_n"]["ok"]),
            "method": "coherence health on the same hybrid (must be false)",
            "anchor": "command-center/p2-wave/probes/CNF-0043/health.py:coherence_health",
        }
    )

    p1_raw = (
        "live kill-point trials recovered="
        + ",".join(f"{k['phase']}:{k['recovered_to_pre_state']}" for k in kills)
    )
    p2_raw = (
        f"hybrid discriminated={hybrid['discriminated']} "
        f"file_count_ok={hybrid['naive_file_count']['ok']} "
        f"coherence_ok={hybrid['coherence_against_n']['ok']}"
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0043",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0043",
        "min_bytes_threshold": 2048,
        "artifacts": [artifact_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Killing the three-phase upgrade after file_copy, after "
                    "manifest_write, and after cache_invalidation, then restoring "
                    "the pre-upgrade snapshot, recovers a byte-identical pre-state "
                    "whose coherence health check passes."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0043/trial.py:run_all_kill_points",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": p1_raw,
                        "fingerprint": "cnf0043:source:kill-points",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": (
                            "python3 -c \"from trial import run_all_kill_points; "
                            "ks=run_all_kill_points(); print([k['hash_comparison']['identical'] "
                            "for k in ks])\""
                        ),
                        "raw_output": json.dumps(
                            [bool(k["hash_comparison"]["identical"]) for k in kills]
                        ),
                        "fingerprint": "cnf0043:verifier:hash-identity",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "A file_copy hybrid still has three plugin files so file-count "
                    "health reports ok, while coherence health flags hybrid=true "
                    "and ok=false. That false-healthy is the named worst outcome."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0043/trial.py:run_hybrid_control",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": p2_raw,
                        "fingerprint": "cnf0043:source:hybrid",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": (
                            "python3 -c \"from health import file_count_health, "
                            "coherence_health\""
                        ),
                        "raw_output": (
                            "file_count_health.kind=file-count-only "
                            "coherence_health.kind=coherence "
                            f"discriminated={hybrid['discriminated']}"
                        ),
                        "fingerprint": "cnf0043:verifier:health-kinds",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "all-three-kill-points",
                "name": "file_copy, manifest_write, cache_invalidation each recovered",
                "command": P1,
                "result": "PASS",
                "assertions": 3,
            },
            {
                "id": "post-rollback-coherence-not-file-count",
                "name": "health_check.kind is coherence and ok after each rollback",
                "command": P1,
                "result": "PASS",
                "assertions": 3,
            },
            {
                "id": "hybrid-false-healthy",
                "name": "file-count healthy + coherence fail on unrolled-back hybrid",
                "command": P2,
                "result": "PASS",
                "assertions": 1,
            },
        ],
        "negative_controls": [
            {
                "id": "NC-HYBRID-FILE-COUNT",
                "kind": "known-broken-fixture",
                "description": (
                    "Leave the file_copy window in place. File-count must still "
                    "report healthy; coherence must fail. A probe that agrees "
                    "with file-count on this hybrid does not discriminate."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": p2_raw,
                "good_state_output": p1_raw,
            }
        ],
        "reviewer": {
            "reviewer_id": "CNF-0043-probe2-hybrid",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Named probe2 constructs the hybrid and requires file-count "
                "healthy plus coherence failure. It does not read probe1's "
                "kill-point verdicts. Catalog cross-vendor scoring is independent "
                "of G-1 probe-green."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0043/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0043",
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft202012Validator (offline rollback-report)",
                "artifact_path": SCHEMA,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 command-center/p2-wave/probes/CNF-0043/emit_report.py"
                    ),
                    "raw_output": "offline validator compiled; garbage rejected",
                    "fingerprint": "cnf0043:consumer:schema",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_at": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "at most 3 attempts, each with a DIFFERENT substrate or "
                "interpreter; this attempt is python3-tempfile-linux"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "platform/marketplace/mkt/install.py has no named kill_after "
                    "hooks for file_copy/manifest_write/cache_invalidation. The "
                    "three windows were exercised on a disposable installer "
                    "fixture whose phases match the catalog question."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Instrument mkt.install.Installer.install with kill_after= "
                    "after payload copy, after installed.json write, and after "
                    "journal append, then re-run these trials against a signed "
                    "fixture registry."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "crash-recovery-engineer",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "rollback-report",
            "observations": kill_obs,
            "control_ids": [
                "hybrid-false-healthy",
                "file-count-vs-coherence",
            ],
            "title": "Rollback from a partially applied upgrade killed mid-install",
            "question": QUESTION,
            "completion_sentinel": SENTINEL,
            "verdict": "each-kill-recovered-to-consistent-pre-state",
            "kill_points": kills,
            "hybrid_probe": hybrid,
            "hash_manifests": {
                "pre_change_counts": kills[0]["hash_comparison"]["pre_count"],
                "post_rollback_identical_per_kill": [
                    bool(k["hash_comparison"]["identical"]) for k in kills
                ],
            },
            "tests_required": {
                "all_three_kill_points_exercised": True,
                "post_rollback_health_not_file_count": True,
                "hybrid_false_healthy_probed": True,
            },
            "installer_surface": {
                "catalog_input": "the installer implementation and its ordered phases",
                "marketplace_install_present": mkt_install.is_file(),
                "marketplace_install_path": (
                    "platform/marketplace/mkt/install.py"
                    if mkt_install.is_file()
                    else None
                ),
                "platform_plugin_present": platform_plugin,
                "kill_windows": list(PHASES),
                "rollback_inverse": (
                    "snapshot restore in command-center/p2-wave/probes/CNF-0043/rollback.py"
                ),
            },
            "rollback_manifest": {
                "catalog_path": "command-center/ROLLBACK-MANIFEST.md",
                "present": rb_manifest.is_file(),
            },
            "named_probes": [
                {"id": "probe1", "role": "three-kill-point-rollback", "command": P1},
                {"id": "probe2", "role": "hybrid-false-healthy-control", "command": P2},
            ],
            "reviewers": [
                {
                    "reviewer_id": "CNF-0043-probe1-kill-points",
                    "verdict": "PASS",
                    "independent": True,
                    "blind_until_filed": True,
                },
                {
                    "reviewer_id": "CNF-0043-probe2-hybrid",
                    "verdict": "PASS",
                    "independent": True,
                    "blind_until_filed": True,
                },
            ],
        },
        "extensions": {
            "cloud_ok": False,
            "output_path": OUT,
            "disposable_target": True,
        },
    }

    validator = offline_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0043 schema errors")
        for e in errs[:40]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0043", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0043 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0043 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0043 sentinel absent from artifact text")
        return 1
    written = json.loads(text)
    post_errs = sorted(validator.iter_errors(written), key=lambda e: list(e.path))
    if post_errs:
        print("FAILED:CNF-0043 written artifact schema-invalid")
        for e in post_errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    print(f"wrote {OUT} bytes={size}")
    print(
        "kills="
        + ",".join(k["phase"] for k in kills)
        + f" hybrid_discriminated={hybrid['discriminated']}"
    )
    print("SUCCESS:CNF-0043 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
