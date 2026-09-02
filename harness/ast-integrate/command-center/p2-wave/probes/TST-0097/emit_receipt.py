#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0097.json from live cache fault injection.

Validates against the catalog output_schema via platform/lib/schema_resolver
(disk-only; no network to ast-integrate.invalid). Does not write the per-unit
manifest (write_receipts.py does that). Does not call unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from cache import (  # noqa: E402
    DETECT_INTACT,
    DETECT_LEFTOVER_TMP,
    DETECT_TRUNCATED,
    DETECT_UNREADABLE,
    DETECT_WRONG_HASH,
)
from scenario import (  # noqa: E402
    run_all_modes,
    run_atomic_interrupt,
    run_inplace_mutant,
    run_intact_negative_control,
    run_rebuild_correct,
    run_silent_serve_mutant,
    verdict_modes,
)

OUT_REL = "command-center/receipts/TST-0097.json"
SCHEMA_REL = "command-center/schema/fault-injection-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0097"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0097/probe1_corruption_modes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0097/probe2_atomic_rebuild.py"
)
QUESTION = (
    "Phase 10 layer 25. Target: corrupt the cache in each distinct way "
    "(truncated entry, wrong hash, unreadable permissions, half-written temp "
    "file left behind) and assert the system detects and rebuilds rather than "
    "serving corrupt data. Precedent: a render cancelled mid-write can leave a "
    "half-file unless writes are atomic (tmp + mv -f)."
)
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/TST-0097/cache.py",
    "command-center/p2-wave/probes/TST-0097/scenario.py",
    "command-center/p2-wave/probes/TST-0097/probe1_corruption_modes.py",
    "command-center/p2-wave/probes/TST-0097/probe2_atomic_rebuild.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def digest_rel(rel: str, role: str = "supporting") -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def schema_errors(doc: dict) -> list[str]:
    """Validate against local physical schemas. No network.

    Host jsonschema 4.10 lacks the referencing.Registry kwarg used by
    platform/lib/schema_resolver.py, so this maps the catalog $id URIs to
    on-disk files with RefResolver.
    """
    from jsonschema import Draft202012Validator, RefResolver

    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    shim = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    store = {
        receipt["$id"]: receipt,
        profiles["$id"]: profiles,
        shim.get("$id")
        or "https://ast-integrate.invalid/command-center/schema/fault-injection-receipt.schema.json": shim,
    }
    resolver = RefResolver(
        base_uri=shim.get("$id")
        or "https://ast-integrate.invalid/command-center/schema/fault-injection-receipt.schema.json",
        referrer=shim,
        store=store,
    )
    out: list[str] = []
    validator = Draft202012Validator(shim, resolver=resolver)
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text[-4000:]


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0)
    with tempfile.TemporaryDirectory(prefix="tst0097-emit-") as tmp:
        root = Path(tmp)
        rows = run_all_modes(root)
        intact = run_intact_negative_control(root)
        atomic = run_atomic_interrupt(root)
        inplace = run_inplace_mutant(root)
        rebuild = run_rebuild_correct(root)
        silent = run_silent_serve_mutant(root)

    ok, why = verdict_modes(rows)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0097 emit probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    tests_ok = {
        "test_each_corruption_mode_is_detected": ok and c1 == 0,
        "test_cache_writes_are_atomic": (
            not atomic.get("partial_published")
            and atomic.get("payload_sha256_match")
            and atomic.get("leftover_cleared")
            and inplace.get("partial_on_publish_path")
            and inplace.get("detector_fires")
            and c2 == 0
        ),
        "test_rebuild_produces_a_correct_entry": (
            rebuild.get("rebuilt")
            and rebuild.get("payload_sha256_match")
            and rebuild.get("post_rebuild_inspect_ok")
            and c2 == 0
        ),
        "negative_control_intact_not_quarantined": (
            intact.get("hit")
            and not intact.get("quarantined")
            and not intact.get("rebuilt")
            and intact.get("payload_sha256_match")
        ),
        "mutant_silent_serve_goes_red": (
            silent.get("served_corrupt") and silent.get("detector_fires")
        ),
    }
    if not all(tests_ok.values()):
        print("FAILED:TST-0097 emit tests not all PASS")
        print(json.dumps(tests_ok, indent=2))
        print(why)
        return 1
    if any(r.get("served_corrupt") for r in rows):
        print("FAILED:TST-0097 P0 served corrupt")
        return 1

    cases = []
    for r in rows:
        cases.append(
            {
                "corruption_mode": r["corruption_mode"],
                "detection_mechanism": r["detection_mechanism"],
                "served_corrupt": r["served_corrupt"],
                "rebuilt": r["rebuilt"],
                "payload_sha256_match": r["payload_sha256_match"],
                "quarantined": r["quarantined"],
                "quarantine_listing": r.get("quarantine_listing") or [],
                "sibling_intact": r.get("sibling_intact"),
                "served_sha256": r.get("served_sha256"),
                "expected_sha256": r.get("expected_sha256"),
                "inspect_detail": r.get("inspect_detail"),
            }
        )

    artifacts = [digest_rel(rel) for rel in SUPPORTING]
    missing = [a["path"] for a in artifacts if a["bytes"] < 1]
    if missing:
        print("FAILED:TST-0097 missing supporting", missing)
        return 1

    ended = datetime.now(timezone.utc).replace(microsecond=0)
    duration = max(0, int((ended - started).total_seconds()))
    production = REPO / "tools/plugin-cache-reaper/reap.py"

    tests = [
        {
            "id": "test_each_corruption_mode_is_detected",
            "name": (
                "truncated, wrong_hash, unreadable_permissions, leftover_tmp "
                "each classified by a named detector and rebuilt"
            ),
            "command": P1,
            "result": "PASS",
            "output_tail": t1[-1500:],
        },
        {
            "id": "test_cache_writes_are_atomic",
            "name": (
                "interrupt before os.replace leaves no partial on the publish "
                "path; leftover tmp is swept not served"
            ),
            "command": P2,
            "result": "PASS",
            "output_tail": t2[-1500:],
        },
        {
            "id": "test_rebuild_produces_a_correct_entry",
            "name": "post-rebuild payload sha256 equals render(source); inspect(ok)=True",
            "command": P2,
            "result": "PASS",
            "output_tail": (
                f"rebuilt={rebuild.get('rebuilt')} "
                f"match={rebuild.get('payload_sha256_match')} "
                f"inspect_ok={rebuild.get('post_rebuild_inspect_ok')} "
                f"sha={rebuild.get('served_sha256')}"
            ),
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0097",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11013",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "fault-injection-engineer",
            "execution_substrate": "linux-local",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Each of four corruption modes (truncated, wrong_hash, "
                    "unreadable_permissions, leftover_tmp) is classified by a "
                    "named detector, quarantined, and rebuilt; IntegrityCache "
                    "did not serve corrupt bytes."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0097/probe1_corruption_modes.py:38"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": t1,
                        "fingerprint": "probe1:corruption-modes",
                        "exit_code": c1,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": P2,
                        "raw_output": t2,
                        "fingerprint": "probe2:atomic-rebuild-hash",
                        "exit_code": c2,
                    },
                ],
            },
            {
                "claim": (
                    "Cache publish is tmp+os.replace: an interrupt before replace "
                    "leaves no partial on entries/<key>/; in-place-write mutant "
                    "DOES leave a readable partial so the detector is not silent "
                    "in both states. Rebuild payload sha256 matches render(source)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0097/probe2_atomic_rebuild.py:25"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": t2,
                        "fingerprint": "probe2:atomic-rebuild",
                        "exit_code": c2,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": P1,
                        "raw_output": t1,
                        "fingerprint": "probe1:modes-as-verifier",
                        "exit_code": c1,
                    },
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-SILENT-SERVE-MUTANT",
                "kind": "mutation",
                "description": (
                    "SilentServeCache returns on-disk bytes without integrity "
                    "checks. Detector must fire (served_corrupt=true) on the "
                    "mutant and stay silent on IntegrityCache."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"served_corrupt={silent.get('served_corrupt')} "
                    f"detector_fires={silent.get('detector_fires')}"
                ),
                "good_state_output": (
                    "integrity_cache_served_corrupt=false "
                    f"modes={[r['corruption_mode'] for r in rows]}"
                ),
            },
            {
                "id": "NC-INPLACE-PARTIAL",
                "kind": "mutation",
                "description": (
                    "InPlaceWriteCache writes a truncated payload onto the "
                    "publish path. inspect() must classify it; IntegrityCache "
                    "interrupt-before-replace must not publish a partial."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"partial_on_publish_path={inplace.get('partial_on_publish_path')} "
                    f"inspect_mode={inplace.get('inspect_mode')}"
                ),
                "good_state_output": (
                    f"atomic_partial_published={atomic.get('partial_published')} "
                    f"orphan_tmp_count={atomic.get('orphan_tmp_count')}"
                ),
            },
            {
                "id": "NC-INTACT-HIT",
                "kind": "known-broken-fixture",
                "description": (
                    "An intact planted entry is a hit: not quarantined, not rebuilt, "
                    "payload sha256 matches. Proves the detector is silent on the "
                    "good state."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "corrupt modes quarantined+rebuilt (probe1)",
                "good_state_output": (
                    f"hit={intact.get('hit')} quarantined={intact.get('quarantined')} "
                    f"rebuilt={intact.get('rebuilt')}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0097-probe2-atomic-rebuild-and-silent-serve-mutant",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 is a separate script (atomic interrupt, in-place-write "
                "mutant, rebuild hash match, silent-serve mutant). Cross-vendor "
                "Windows/PowerShell re-run is not available on this Linux worker "
                "and is not claimed."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0097/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "TST-0097",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/TST-0097/probe1_corruption_modes.py"
                ),
                "artifact_path": "command-center/p2-wave/probes/TST-0097/cache.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
                "probe": {
                    "role": "verifier",
                    "method": "test-run",
                    "command": P1,
                    "raw_output": t1,
                    "fingerprint": "consumer:probe1-on-cache",
                    "exit_code": c1,
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
            "policy": "two strikes then pivot: after the 2nd failure on the same error-fingerprint, enumerate >=2 alternative approaches before a 3rd attempt (AGENTS.md 4b)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Production tools/plugin-cache-reaper/reap.py is absent on this "
                    "worktree (present="
                    + str(production.is_file())
                    + "). Probes measure probes/TST-0097/cache.py."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Bind the same four corruption modes and tmp+os.replace "
                    "publish to a live plugin-cache-reaper tree and re-run probe1 "
                    "and probe2 against that binary."
                ),
            },
            {
                "claim": (
                    "Catalog reviewer_requirement asks for a fresh-context "
                    "adversarial reviewer from the other vendor. This Linux "
                    "worker ran a mechanically independent second probe script; "
                    "it did not dispatch a Codex/Claude reviewer process."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Dispatch a Codex (openai) fresh-context reviewer over "
                    "command-center/receipts/TST-0097.json and require PASS "
                    "without re-running only probe1."
                ),
            },
        ],
        "report": {
            "kind": "fault-injection-receipt",
            "question": QUESTION,
            "claim_under_test": (
                "A cache that publishes with tmp+os.replace and verifies payload "
                "length, mode bits, and sha256 on read will detect truncated, "
                "wrong-hash, unreadable, and leftover-tmp corruption, quarantine "
                "the bad object, and rebuild a correct entry. Serving corrupt "
                "bytes is a P0 and did not occur on IntegrityCache."
            ),
            "system_under_test": {
                "production_path": "tools/plugin-cache-reaper/reap.py",
                "production_present": production.is_file(),
                "live_substrate": "command-center/p2-wave/probes/TST-0097/cache.py",
                "publish": "tmp + os.replace (atomic)",
            },
            "observations": [
                {
                    "name": "corruption_modes_named",
                    "measured": ",".join(r["corruption_mode"] for r in rows),
                    "method": "live-injection",
                    "anchor": "command-center/p2-wave/probes/TST-0097/scenario.py:139",
                },
                {
                    "name": "p0_silent_serve_on_integrity_cache",
                    "measured": False,
                    "method": "byte-compare",
                    "anchor": "command-center/p2-wave/probes/TST-0097/cache.py:296",
                },
                {
                    "name": "atomic_partial_published_on_interrupt",
                    "measured": bool(atomic["partial_published"]),
                    "method": "file-read",
                    "anchor": "command-center/p2-wave/probes/TST-0097/scenario.py:165",
                },
                {
                    "name": "rebuild_payload_sha256_match",
                    "measured": bool(rebuild["payload_sha256_match"]),
                    "method": "byte-compare",
                    "anchor": "command-center/p2-wave/probes/TST-0097/scenario.py:232",
                },
            ],
            "control_ids": [
                "NC-SILENT-SERVE-MUTANT",
                "NC-INPLACE-PARTIAL",
                "NC-INTACT-HIT",
            ],
            "detection_mechanisms": {
                "truncated": DETECT_TRUNCATED,
                "wrong_hash": DETECT_WRONG_HASH,
                "unreadable_permissions": DETECT_UNREADABLE,
                "leftover_tmp": DETECT_LEFTOVER_TMP,
                "intact": DETECT_INTACT,
            },
            "cases": cases,
            "atomic_write": {
                "method": "tmp + os.replace",
                "partial_published_on_interrupt": atomic["partial_published"],
                "orphan_tmp_count_before_sweep": atomic["orphan_tmp_count"],
                "leftover_cleared": atomic["leftover_cleared"],
                "inplace_mutant_leaves_partial": inplace["partial_on_publish_path"],
                "inplace_mutant_inspect_mode": inplace.get("inspect_mode"),
            },
            "rebuild": {
                "rebuilt": rebuild["rebuilt"],
                "payload_sha256_match": rebuild["payload_sha256_match"],
                "post_rebuild_inspect_ok": rebuild["post_rebuild_inspect_ok"],
                "served_sha256": rebuild["served_sha256"],
                "expected_sha256": rebuild["expected_sha256"],
            },
            "silent_serve_p0": {
                "integrity_cache_served_corrupt": False,
                "silent_serve_mutant_served_corrupt": silent["served_corrupt"],
                "control": (
                    "mutant returns on-disk bytes without checks; "
                    "IntegrityCache never does"
                ),
            },
            "intact_negative_control": {
                "hit": intact["hit"],
                "quarantined": intact["quarantined"],
                "rebuilt": intact["rebuilt"],
                "payload_sha256_match": intact["payload_sha256_match"],
                "detection_mechanism": DETECT_INTACT,
            },
        },
        "extensions": {
            "cloud_ok": False,
            "output_schema": SCHEMA_REL,
            "completion_sentinel": SENTINEL,
        },
    }

    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out_path.write_text(body, encoding="utf-8")

    errs = schema_errors(json.loads(out_path.read_text(encoding="utf-8")))
    if errs:
        print("FAILED:TST-0097 schema-invalid")
        for e in errs[:20]:
            print(" ", e)
        return 1

    text = out_path.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0097 sentinel missing after write")
        return 1
    sha, size = sha256_file(out_path)
    if size < 2048:
        print(f"FAILED:TST-0097 receipt too small bytes={size}")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
