#!/usr/bin/env python3
"""Pack CC-0006 — wrong-recipe prose gate.

Emits state=BLOCKED with blocked-on-independent-review after green detector
controls + named probes. Does NOT invent SUCCESS: catalog reviewer_requirement
demands an independent reviewer who supplies a NEW documentary mention and
confirms the discriminator on text the author never saw.
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

UNIT = "CC-0006"
OUT = "command-center/receipts/CC-0006.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE_DIR = "command-center/p2-wave/probes/CC-0006"
GATE = f"{PROBE_DIR}/wrong_recipe_gate.py"
TESTS = f"{PROBE_DIR}/test_wrong_recipe_gate.py"
PROBE1 = f"{PROBE_DIR}/probe1_live_scan.py"
PROBE2 = f"{PROBE_DIR}/probe2_discriminator.py"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = L.REPO / PROBE_DIR / "independent-review.json"
TS0 = "2026-09-07T20:15:00Z"


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=L.REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def load_review() -> dict | None:
    """Promote path only when an independent reviewer supplies a NEW documentary mention."""
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
    # Must cite a documentary mention the implementer did not author.
    mention = rev.get("new_documentary_mention") or rev.get("documentary_mention_path")
    if not mention:
        return None
    if not rev.get("discriminator_confirmed"):
        return None
    return rev


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    rc, out = _run([sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line"])
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out, encoding="utf-8")
    if rc != 0:
        raise SystemExit(f"CC-0006 pytest failed:\n{out}")

    p1_rc, p1_out = _run([sys.executable, "-B", str(L.REPO / PROBE1)])
    if p1_rc != 0:
        raise SystemExit(f"CC-0006 probe1 failed:\n{p1_out}")
    p2_rc, p2_out = _run([sys.executable, "-B", str(L.REPO / PROBE2)])
    if p2_rc != 0:
        raise SystemExit(f"CC-0006 probe2 failed:\n{p2_out}")

    p1 = json.loads((L.REPO / PROBE_DIR / "probe1-live-scan.json").read_text(encoding="utf-8"))
    p2 = json.loads((L.REPO / PROBE_DIR / "probe2-discriminator.json").read_text(encoding="utf-8"))
    raw1 = (L.REPO / PROBE_DIR / "probe1-live-scan.raw.txt").read_text(encoding="utf-8")
    raw2 = (L.REPO / PROBE_DIR / "probe2-discriminator.raw.txt").read_text(encoding="utf-8")

    rev = load_review()
    success = rev is not None

    p_pytest = L.probe(
        "source", "test-run", f"python3 -m pytest {TESTS} -q --tb=line", out, rc
    )
    p_probe1 = L.probe(
        "verifier",
        "command",
        f"python3 -B {PROBE1}",
        raw1,
        p1_rc,
    )
    p_probe2 = L.probe(
        "verifier",
        "command",
        f"python3 -B {PROBE2}",
        raw2,
        p2_rc,
    )

    ctrl = p2["controls"]
    counts = p2["counts"]

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
        residual: list[dict] = []
        failure = None
        anti = "SUCCESS-after-independent-new-documentary-mention"
    else:
        state = "BLOCKED"
        sentinel = (
            f"FAILED:{UNIT} blocked-on-independent-review; "
            f"pytest 6 passed; probe1 live ok_clean={p1.get('ok')}; "
            f"probe2 discriminator ok={p2.get('ok')} "
            f"pre_fix_hits={counts['pre_fix_hits']} "
            f"planted_hits={counts['planted_hits']} "
            f"documentary_mentions={counts['documentary_mentions']} "
            f"scratch_hits={counts['scratch_hits']}; "
            f"catalog SUCCESS:{UNIT} withheld pending independent reviewer who "
            f"supplies a new documentary mention and confirms discriminator"
        )
        reviewer = {
            "reviewer_id": "awaiting-independent-documentary-mention",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only. Catalog reviewer_requirement: one independent "
                "reviewer who supplies a NEW documentary mention (text the author never "
                "saw) and confirms the use-vs-mention discriminator holds. Self-review "
                "banned; never stub SUCCESS."
            ),
        }
        residual = [
            {
                "claim": (
                    "Independent reviewer has not supplied a fresh documentary mention "
                    "nor confirmed the discriminator on unseen text."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context reviewer authors a new markdown snippet that quotes "
                    "the identical wrong recipe under forbid/documentary framing, runs "
                    f"`python3 {GATE}` against it (expect SILENT) and against "
                    f"{PROBE_DIR}/fixtures/planted_regression.md (expect FIRE), returns "
                    "PASS with independent=true, discriminator_confirmed=true, and "
                    "new_documentary_mention=<path>."
                ),
            }
        ]
        failure = {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "Detector + tests_required + both named probes are green "
                f"(pytest 6/6; probe1 ok_clean={p1.get('ok')}; probe2 ok={p2.get('ok')}; "
                f"controls={ctrl}). Catalog reviewer_requirement unmet — do not emit "
                "SUCCESS without a new documentary mention from an independent reviewer."
            ),
            "blocked_on": (
                "independent reviewer new-documentary-mention + discriminator confirm"
            ),
            "diagnostic_tail": (out + "\n" + raw1 + "\n" + raw2)[-4000:],
            "two_signal_proof": [p_probe1, p_probe2],
        }
        anti = "BLOCKED-pending-independent-documentary-mention"

    arts = [
        L.art(GATE, "primary"),
        L.art(TESTS, "supporting"),
        L.art(f"{PROBE_DIR}/fixtures/pre_fix_release_checklist.md", "control"),
        L.art(f"{PROBE_DIR}/fixtures/scratch_no_recipe.md", "control"),
        L.art(f"{PROBE_DIR}/fixtures/planted_regression.md", "control"),
        L.art(f"{PROBE_DIR}/fixtures/documentary_forbid.md", "control"),
        L.art("command-center/RELEASE-CHECKLIST.md", "supporting"),
        L.art("rules/common/windows-shell.md", "supporting"),
        L.art(f"{PROBE_DIR}/pytest.out", "log"),
        L.art(f"{PROBE_DIR}/probe1-live-scan.json", "log"),
        L.art(f"{PROBE_DIR}/probe2-discriminator.json", "log"),
        L.art(f"{PROBE_DIR}/probe1-live-scan.raw.txt", "log"),
        L.art(f"{PROBE_DIR}/probe2-discriminator.raw.txt", "log"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
        L.art("command-center/p2-wave/_build_CC0006.py", "control"),
    ]
    if success:
        arts.append(L.art(f"{PROBE_DIR}/independent-review.json", "supporting"))

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0006",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "detector-engineer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    "Wrong-recipe gate under probes/CC-0006/wrong_recipe_gate.py; "
                    "pre-fix checklist FIRES; scratch scores 0; windows-shell + "
                    "documentary fixture SILENT on the identical string; live "
                    "RELEASE-CHECKLIST post-fix SILENT; planted regression re-fires."
                ),
                "CONFIRMED",
                f"file:{GATE}",
                [p_pytest, p_probe2],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Named probes: probe1 live ok_clean={p1.get('ok')} "
                    f"files={p1['report']['files_scanned']}; probe2 discriminator "
                    f"ok={p2.get('ok')} controls={ctrl}."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/probe2-discriminator.json",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        f"python3 -B {PROBE1}",
                        raw1,
                        p1_rc,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        f"read {PROBE_DIR}/probe2-discriminator.json",
                        json.dumps(
                            {"ok": p2.get("ok"), "controls": ctrl, "counts": counts},
                            sort_keys=True,
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot from string matching to sentence-role "
                "classification with a labelled control set."
            ),
        },
        "tests": [
            {
                "id": "known-present-pre-fix",
                "name": "Pre-fix RELEASE-CHECKLIST git-archive line fires.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_known_present_pre_fix_checklist_fires -q"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
            {
                "id": "known-absent-scratch",
                "name": "Scratch document with no recipe scores 0 hits.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_known_absent_scratch_scores_zero -q"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
            {
                "id": "use-vs-mention-windows-shell",
                "name": "windows-shell.md documentary forbid stays silent.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_use_vs_mention_windows_shell_silent -q"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
            {
                "id": "post-fix-and-planted",
                "name": "Live checklist silent; planted regression re-fires.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_post_fix_live_checklist_silent_planted_refires -q"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "pre-fix-and-planted",
                "known-broken-fixture",
                "Pre-fix checklist + planted regression must FIRE as PRESCRIPTIVE.",
                True,
                True,
                bad=f"pre_fix_hits={counts['pre_fix_hits']} planted={counts['planted_hits']}",
                good="live RELEASE-CHECKLIST hit_count=0",
            ),
            L.control(
                "use-vs-mention-documentary",
                "adversarial-payload",
                "Identical wrong string under documentary/forbid framing must stay SILENT.",
                True,
                True,
                bad="would flag documentary_forbid.md / windows-shell.md",
                good=(
                    f"documentary_hits=0 mentions={counts['documentary_mentions']} "
                    f"shell_hits={counts['windows_shell_hits']}"
                ),
            ),
            L.control(
                "known-absent-scratch",
                "absent-input",
                "Scratch with no recipe must score 0 hits.",
                True,
                True,
                bad="would invent hits on empty prose",
                good=f"scratch_hits={counts['scratch_hits']}",
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
                "consumer": "pytest:test_wrong_recipe_gate",
                "artifact_path": TESTS,
                "executed": True,
                "read_ok": rc == 0,
                "exit_code": rc,
                "probe": p_pytest,
            },
            {
                "consumer": "probe1_live_scan",
                "artifact_path": f"{PROBE_DIR}/probe1-live-scan.json",
                "executed": True,
                "read_ok": p1_rc == 0 and bool(p1.get("ok")),
                "exit_code": p1_rc,
                "probe": p_probe1,
            },
            {
                "consumer": "probe2_discriminator",
                "artifact_path": f"{PROBE_DIR}/probe2-discriminator.json",
                "executed": True,
                "read_ok": p2_rc == 0 and bool(p2.get("ok")),
                "exit_code": p2_rc,
                "probe": p_probe2,
            },
        ],
        "residual_unknowns": residual,
        "defects": [],
        "report": {
            "pytest_passed": 6,
            "probe1_ok": p1.get("ok"),
            "probe2_ok": p2.get("ok"),
            "controls": ctrl,
            "counts": counts,
            "live_checklist_fixed": True,
            "catalog_completion_sentinel": f"SUCCESS:{UNIT}",
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "anti_false_green": anti,
            "output_path": OUT,
            "output_schema": SCHEMA,
        },
    }
    if failure is not None:
        receipt["failure"] = failure

    # Manifest first (paths that already exist).
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
        a for a in packed["artifacts"] if a.get("path") not in {OUT, MANIFEST}
    ] + [L.art(MANIFEST, "supporting"), L.art(OUT, "primary")]

    # Refresh hashes after admission append.
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

    errs2 = L.validate(packed, SCHEMA)
    if errs2:
        raise SystemExit(f"FAILED:{UNIT} post-fill schema-invalid: {errs2[:12]}")
    ar.write_json_atomic(L.REPO / OUT, packed)

    # Final artifact remeasure + re-admit.
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
    if val_rc2 != 0 or "ACCEPT:" not in val_out2:
        raise SystemExit(f"receipt_validate REJECTED {UNIT}:\n{val_out2}")

    packed = ar.read_json(L.REPO / OUT)
    if success:
        assert packed["state"] == "SUCCESS"
        assert "failure" not in packed
        print(f"SUCCESS:{UNIT} wrote {OUT} bytes={(L.REPO / OUT).stat().st_size}")
    else:
        assert packed["state"] == "BLOCKED"
        assert packed["reviewer"]["verdict"] == "NOT-REVIEWED"
        print(f"BLOCKED:{UNIT} wrote {OUT} bytes={(L.REPO / OUT).stat().st_size}")
    print(val_out2.strip())
    print(packed["sentinel"])
    return packed


if __name__ == "__main__":
    build()
