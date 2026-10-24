#!/usr/bin/env python3
"""Pack CC-0009 receipt.

Promotes to SUCCESS only when independent-review.json has verdict=PASS with
independent=true and fresh_context=true and non-anthropic vendor.
Otherwise leaves/re-emits BLOCKED.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(L.REPO / "platform" / "lib"))
import atomic_receipt as ar  # noqa: E402
from artifact_manifest_gate import (  # noqa: E402
    DEFAULT_MANIFEST,
    GATE_ID,
    probe_manifest_consumers,
)

UNIT = "CC-0009"
OUT = "command-center/receipts/CC-0009.json"
SCHEMA = "command-center/schema/receipt.schema.json"
IMPL = "platform/lib/artifact_manifest_gate.py"
TESTS = "platform/lib/test_artifact_manifest_gate.py"
PROBE_DIR = "command-center/p2-wave/probes/CC-0009"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = L.REPO / PROBE_DIR / "independent-review.json"
TS0 = "2026-09-07T18:30:00Z"


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd, cwd=L.REPO, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def load_review() -> dict | None:
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    if str(rev.get("vendor", "")).lower() in ("", "anthropic"):
        # Same-vendor as implementer is insufficient for this promote path.
        return None
    return rev


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    rc, out = _run([sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line"])
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out, encoding="utf-8")
    if rc != 0:
        raise SystemExit(f"CC-0009 pytest failed:\n{out}")

    report = probe_manifest_consumers(L.REPO, manifest_rel=DEFAULT_MANIFEST)
    live = json.dumps(report.to_dict(), indent=2) + "\n"
    (L.REPO / PROBE_DIR / "live-probe.json").write_text(live, encoding="utf-8")
    if not report.ok:
        raise SystemExit(f"CC-0009 live probe red:\n{live[:2000]}")

    citations = [f"{row.path} via {row.consumer}: {row.summary}" for row in report.results]
    cite_text = "\n".join(citations) + "\n"
    (L.REPO / PROBE_DIR / "consumer-citations.txt").write_text(cite_text, encoding="utf-8")

    rev = load_review()
    success = rev is not None

    p_pytest = L.probe("source", "test-run", f"python3 -m pytest {TESTS} -q --tb=line", out, rc)
    p_live = L.probe(
        "verifier",
        "command",
        f"python3 {IMPL} --manifest {DEFAULT_MANIFEST} probe",
        report.sentinel_line() + "\n" + cite_text[:4000],
        0,
    )

    if success:
        state = "SUCCESS"
        sentinel = f"SUCCESS:{UNIT}"
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", "")[:4000],
        }
        residual: list[dict] = [
            {
                "claim": (
                    "Live ARTIFACT-MANIFEST.json digest drift for STATUS.md and "
                    "TEST-REGISTRY.json (verified_on_disk=true with stale sha/bytes). "
                    "Outside CC-0009 readability gate; settle via tools/command-center/render.py."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "python3 tools/command-center/render.py --check "
                    "then re-render ARTIFACT-MANIFEST.json"
                ),
            }
        ]
        failure = None
        anti = "SUCCESS-after-independent-phantom-review-PASS"
    else:
        state = "BLOCKED"
        sentinel = (
            f"FAILED:{UNIT} blocked-on-independent-review; pytest 9 passed; "
            f"live ARTIFACT-MANIFEST {len(report.results)}/{len(report.results)} consumers read_ok; "
            f"GATE_ID={GATE_ID}; catalog SUCCESS:{UNIT} withheld pending independent "
            f"reviewer who adds a phantom manifest entry and confirms rejection"
        )
        reviewer = {
            "reviewer_id": "awaiting-independent-phantom-review",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only. Catalog reviewer_requirement unmet or review FAIL."
            ),
        }
        residual = [
            {
                "claim": (
                    "Independent reviewer has not yet re-planted a phantom ARTIFACT-MANIFEST "
                    "entry and confirmed rejection outside this implementer session."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context reviewer adds phantom path to a scratch copy of "
                    f"{DEFAULT_MANIFEST}, runs probe_manifest_consumers, confirms FAIL, "
                    "returns PASS with independent=true."
                ),
            }
        ]
        failure = {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "Implementation + tests_required probes are green; catalog "
                "reviewer_requirement still unmet or review not PASS."
            ),
            "blocked_on": "independent reviewer phantom-entry confirmation",
            "diagnostic_tail": out[-4000:],
            "two_signal_proof": [p_pytest, p_live],
        }
        anti = "BLOCKED-pending-independent-review"

    arts = [
        L.art(IMPL, "primary"),
        L.art(TESTS, "supporting"),
        L.art(DEFAULT_MANIFEST, "supporting"),
        L.art(f"{PROBE_DIR}/pytest.out", "log"),
        L.art(f"{PROBE_DIR}/live-probe.json", "log"),
        L.art(f"{PROBE_DIR}/consumer-citations.txt", "log"),
        L.art("command-center/p2-wave/_build_CC0009.py", "control"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
    ]
    if success:
        arts.append(L.art(f"{PROBE_DIR}/independent-review.json", "supporting"))

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0009",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    "Register-on-write + consumer probe at platform/lib/artifact_manifest_gate.py; "
                    "9/9 pytest cases cover unregistered/missing/unparseable/both-states."
                ),
                "CONFIRMED",
                f"file:{IMPL}",
                [p_pytest, p_live],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Live {DEFAULT_MANIFEST}: {len(report.results)} entries opened by declared/"
                    "inferred consumers; each citation records first_key or record_count."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/consumer-citations.txt",
                [
                    L.probe(
                        "source",
                        "file-read",
                        f"read {PROBE_DIR}/consumer-citations.txt",
                        cite_text[:4000],
                        0,
                    ),
                    p_live,
                ],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "Two strikes then pivot; do not weaken condition 12 to an existence check.",
        },
        "tests": [
            {
                "id": "unregistered-fails",
                "name": "Artifact written without registration fails condition 11.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_artifact_written_without_registration_fails_predicate -q"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
            {
                "id": "missing-path-fails",
                "name": "Manifest entry whose path does not exist fails.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_manifest_entry_whose_path_does_not_exist_must_fail -q"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
            {
                "id": "unparseable-fails",
                "name": "Exists but does not parse with declared consumer fails.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_exists_but_does_not_parse_with_declared_consumer_must_fail -q"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
            {
                "id": "both-states-live-green",
                "name": "All currently-valid ARTIFACT-MANIFEST entries pass consumer probe.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_both_states_currently_valid_entries_pass -q"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "phantom-manifest-entry",
                "known-broken-fixture",
                "Planted absent path in manifest must fail consumer probe (reviewer shape).",
                True,
                True,
                bad="out/PHANTOM-DOES-NOT-EXIST.json present=true",
                good="probe fails registered-but-absent",
            ),
            L.control(
                "unparseable-consumer",
                "malformed-input",
                "json.loads against non-JSON bytes must fail read_ok.",
                True,
                True,
                bad="not-json.txt registered with consumer=json.loads",
                good="json.loads FAILED in summary",
            ),
        ],
        "reviewer": reviewer,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "artifact_manifest_gate.probe_manifest_consumers",
                "artifact_path": DEFAULT_MANIFEST,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_live,
            }
        ],
        "residual_unknowns": residual,
        "defects": [],
        "report": {
            "gate_id": GATE_ID,
            "pytest_passed": 9,
            "live_entries": len(report.results),
            "live_failing": len(report.failing),
            "catalog_completion_sentinel": f"SUCCESS:{UNIT}",
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": "command-center/p2-wave/probes/CC-0009/_pack_receipt.py",
            "anti_false_green": anti,
        },
    }
    if failure is not None:
        receipt["failure"] = failure

    man_paths = [a["path"] for a in receipt["artifacts"]] + [OUT]
    arts_hashed = []
    for rel in man_paths:
        p = L.REPO / rel
        if p.is_file():
            data = p.read_bytes().replace(b"\r\n", b"\n")
            arts_hashed.append(
                {
                    "path": rel,
                    "bytes": len(data),
                    "sha256": __import__("hashlib").sha256(data).hexdigest(),
                    "present": True,
                }
            )
    man_doc = {
        "entry_id": UNIT,
        "unit_id": UNIT,
        "artifacts": arts_hashed,
        "writer": ar.ATOMIC_WRITER_ID,
        "registered_at": ended,
        "state": state,
    }
    ar.write_json_atomic(L.REPO / MANIFEST, man_doc)
    receipt["artifacts"].append(L.art(MANIFEST, "supporting"))

    errs = L.validate(receipt, SCHEMA)
    if errs:
        raise SystemExit(f"FAILED:{UNIT} schema-invalid ({len(errs)}): {errs[:12]}")

    ar.write_json_atomic(L.REPO / OUT, receipt)
    packed = ar.read_json(L.REPO / OUT)

    val_rc, val_out = _run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    (L.REPO / PROBE_DIR / "receipt-validate.out").write_text(val_out, encoding="utf-8")
    packed["downstream_consumers"].append(
        {
            "consumer": "receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": val_rc == 0 and "ACCEPT:" in val_out,
            "exit_code": val_rc,
            "probe": L.probe(
                "verifier",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                val_out,
                val_rc,
            ),
        }
    )
    packed["artifacts"] = [
        a for a in packed["artifacts"] if a.get("path") != OUT
    ] + [L.art(OUT, "primary"), L.art(MANIFEST, "supporting")]
    errs2 = L.validate(packed, SCHEMA)
    if errs2:
        raise SystemExit(f"FAILED:{UNIT} post-fill schema-invalid: {errs2[:12]}")
    ar.write_json_atomic(L.REPO / OUT, packed)

    packed = ar.read_json(L.REPO / OUT)
    packed["artifacts"] = [
        a for a in packed["artifacts"] if a.get("path") != OUT
    ] + [L.art(OUT, "primary")]
    arts_hashed2 = []
    for a in packed["artifacts"]:
        rel = a["path"]
        p = L.REPO / rel
        if p.is_file():
            data = p.read_bytes().replace(b"\r\n", b"\n")
            arts_hashed2.append(
                {
                    "path": rel,
                    "bytes": len(data),
                    "sha256": __import__("hashlib").sha256(data).hexdigest(),
                    "present": True,
                }
            )
    man_doc["artifacts"] = arts_hashed2
    man_doc["state"] = state
    ar.write_json_atomic(L.REPO / MANIFEST, man_doc)
    packed["artifacts"] = [
        a for a in packed["artifacts"] if a.get("path") != MANIFEST
    ] + [L.art(MANIFEST, "supporting")]
    packed["artifacts"] = [
        L.art(a["path"], a.get("role", "supporting"))
        for a in packed["artifacts"]
        if a.get("path") != OUT
    ] + [L.art(OUT, "primary")]
    ar.write_json_atomic(L.REPO / OUT, packed)
    packed = ar.read_json(L.REPO / OUT)
    packed["artifacts"] = [
        L.art(a["path"], a.get("role", "supporting"))
        for a in packed["artifacts"]
        if a.get("path") != OUT
    ] + [L.art(OUT, "primary")]
    ar.write_json_atomic(L.REPO / OUT, packed)

    val_rc2, val_out2 = _run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    (L.REPO / PROBE_DIR / "receipt-validate.out").write_text(val_out2, encoding="utf-8")
    if val_rc2 != 0:
        raise SystemExit(f"receipt_validate REJECTED {UNIT}:\n{val_out2}")

    packed = ar.read_json(L.REPO / OUT)
    if success:
        assert packed["state"] == "SUCCESS"
        assert "failure" not in packed
        assert packed["reviewer"]["verdict"] == "PASS"
        assert packed["reviewer"]["independent"] is True
        if val_rc2 != 0 or "ACCEPT:" not in val_out2:
            raise SystemExit(f"FAILED:{UNIT} receipt_validate after promote:\n{val_out2}")
        print(f"SUCCESS:{UNIT} wrote {OUT} bytes={(L.REPO / OUT).stat().st_size}")
    else:
        assert packed["state"] == "BLOCKED"
        print(f"BLOCKED:{UNIT} wrote {OUT} bytes={(L.REPO / OUT).stat().st_size}")
    print(f"  gate={GATE_ID} pytest=9 live_ok={report.ok} review={bool(rev)}")
    print(packed["sentinel"])
    return packed


if __name__ == "__main__":
    build()
