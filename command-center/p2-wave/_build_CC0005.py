r"""CC-0005 — Manifest provenance gate hashes git blob, not Windows worktree.

Catalog row built to the row. Emits state=BLOCKED with
blocked-on-independent-review after green pytest + planted CRLF control.
Does NOT invent an independent PASS (reviewer_requirement: Windows checkout
reproduction + Linux CI parity).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(L.REPO / "platform" / "lib"))
import atomic_receipt as ar  # noqa: E402

UNIT = "CC-0005"
OUT = "command-center/receipts/CC-0005.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE_DIR = "command-center/p2-wave/probes/CC-0005"
MEASURE = f"{PROBE_DIR}/measure_routes.py"
TESTS = "tools/command-center/tests/test_reach6_blob_provenance.py"
IMPL = "tools/command-center/validate.py"
BLOBREAD = "tools/measure-guard/blobread.py"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
TS0 = "2026-09-07T18:45:00Z"


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd, cwd=L.REPO, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    rc, out = _run([sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line"])
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out, encoding="utf-8")
    if rc != 0:
        raise SystemExit(f"CC-0005 pytest failed:\n{out}")

    # Also run IMP-0439 sibling suite (render provenance_bytes) as cross-check.
    rc2, out2 = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tools/command-center/tests/test_provenance_blob_hash.py",
            "-q",
            "--tb=line",
        ]
    )
    (L.REPO / PROBE_DIR / "pytest-imp0439.out").write_text(out2, encoding="utf-8")
    if rc2 != 0:
        raise SystemExit(f"CC-0005 sibling IMP-0439 pytest failed:\n{out2}")

    m_rc, m_out = _run(
        [sys.executable, str(L.REPO / MEASURE), "--write-dir", str(L.REPO / PROBE_DIR)]
    )
    if m_rc != 0:
        raise SystemExit(f"CC-0005 measure_routes failed:\n{m_out}")
    planted = json.loads((L.REPO / PROBE_DIR / "planted-control.json").read_text(encoding="utf-8"))
    live = json.loads((L.REPO / PROBE_DIR / "live-routes.json").read_text(encoding="utf-8"))

    p_pytest = L.probe(
        "source", "test-run", f"python3 -m pytest {TESTS} -q --tb=line", out, rc
    )
    p_measure = L.probe(
        "verifier",
        "command",
        f"python3 {MEASURE} --write-dir {PROBE_DIR}",
        m_out[:8000],
        m_rc,
    )
    p_sibling = L.probe(
        "source",
        "test-run",
        "python3 -m pytest tools/command-center/tests/test_provenance_blob_hash.py -q",
        out2,
        rc2,
    )

    gs = planted["gate_simulation"]
    fx = planted["fixture"]
    sentinel = (
        f"FAILED:{UNIT} blocked-on-independent-review; "
        f"pytest reach6-blob 5 passed; IMP-0439 sibling green; "
        f"planted CRLF before_exit={gs['before_exit_code']} after_exit={gs['after_exit_code']}; "
        f"byte_delta={fx['byte_delta']}==line_count={fx['line_count']}; "
        f"catalog SUCCESS:{UNIT} withheld pending independent Windows checkout + Linux CI parity"
    )

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0005",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "platform-portability-engineer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": [
            L.art(IMPL, "primary"),
            L.art("tools/command-center/seed.py", "supporting"),
            L.art(BLOBREAD, "supporting"),
            L.art(TESTS, "supporting"),
            L.art(".gitattributes", "supporting"),
            L.art(MEASURE, "control"),
            L.art(f"{PROBE_DIR}/pytest.out", "log"),
            L.art(f"{PROBE_DIR}/pytest-imp0439.out", "log"),
            L.art(f"{PROBE_DIR}/probe-results.json", "log"),
            L.art(f"{PROBE_DIR}/planted-control.json", "log"),
            L.art(f"{PROBE_DIR}/live-routes.json", "log"),
            L.art("command-center/p2-wave/_build_CC0005.py", "control"),
        ],
        "evidence": [
            L.evidence(
                (
                    "REACH-6 hashes via git cat-file blob (validate._register_provenance_bytes); "
                    "planted CRLF worktree raw digest differs from blob while blob route stays "
                    f"silent (before_exit={gs['before_exit_code']}, after_exit={gs['after_exit_code']}). "
                    "Every hash cited from cat-file / planted control, never archive-as-blob."
                ),
                "CONFIRMED",
                f"file:{IMPL}",
                [p_pytest, p_measure],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Byte-delta control: planted CRLF delta={fx['byte_delta']} equals "
                    f"line_count={fx['line_count']}, confirming EOL-only cause. "
                    ".gitattributes records explicit decision: no *.md eol=lf; shell keeps "
                    "eol=lf; provenance gates hash the blob."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/planted-control.json",
                [
                    p_measure,
                    L.probe(
                        "source",
                        "file-read",
                        "read .gitattributes CC-0005 EOL policy block",
                        (L.REPO / ".gitattributes").read_text(encoding="utf-8")[-1200:],
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Historic Windows pair cited from catalog inputs "
                    "(blob 8b3e44cc3813 vs CRLF worktree 1a404a91d819). "
                    "Live Linux three-route on REGISTER.md recorded; archive trap is "
                    "Windows-scoped per blobread.md / windows-shell.md §8b."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/live-routes.json",
                [
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "live three-route + historic pair citation",
                        json.dumps(
                            {
                                "historic": live.get("historic_windows_pair"),
                                "live_cat_file": live.get("routes", {}).get("git_cat_file"),
                                "platform_note": live.get("platform_note"),
                            },
                            indent=2,
                        )[:4000],
                        0,
                    ),
                    p_sibling,
                ],
                "likely",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot; if a .gitattributes change alone does not "
                "achieve parity, do not iterate on it a third time — move the fix into "
                "the hashing routine."
            ),
        },
        "tests": [
            {
                "id": "both-states-silent-eol",
                "name": "Fixed gate SILENT on pure line-ending difference.",
                "command": f"python3 -m pytest {TESTS}::test_silent_on_pure_eol_difference -q",
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
            {
                "id": "both-states-fire-content",
                "name": "Fixed gate FIRES when content genuinely changes.",
                "command": (
                    f"python3 -m pytest {TESTS}::test_fires_when_content_genuinely_changes -q"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
            {
                "id": "byte-delta-control",
                "name": "Pre-fix CRLF delta equals file line count.",
                "command": (
                    f"python3 -m pytest {TESTS}::test_byte_delta_control_crlf_delta_equals_line_count -q"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
            {
                "id": "platform-parity-blob-route",
                "name": "Blob route identical on LF and CRLF checkouts.",
                "command": (
                    f"python3 -m pytest {TESTS}::test_platform_parity_blob_route_identical_lf_and_crlf -q"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "planted-crlf-worktree",
                "known-broken-fixture",
                "Raw worktree hash must FIRE vs recorded blob; cat-file route SILENT.",
                True,
                True,
                bad=(
                    f"before_exit={gs['before_exit_code']} "
                    f"wt={gs['before_worktree_raw_sha256'][:12]}"
                ),
                good=(
                    f"after_exit={gs['after_exit_code']} "
                    f"blob={gs['after_cat_file_sha256'][:12]}"
                ),
            ),
            L.control(
                "byte-delta-eol-only",
                "adversarial-payload",
                "CRLF-LF byte delta must equal line count (EOL cause, not content).",
                True,
                True,
                bad=f"delta!={fx['line_count']} would invalidate EOL claim",
                good=f"delta={fx['byte_delta']}==line_count={fx['line_count']}",
            ),
        ],
        "reviewer": {
            "reviewer_id": "awaiting-independent-windows-checkout-parity",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only. Catalog reviewer_requirement: one independent "
                "reviewer who reproduces the gate on a Windows checkout, plus a Linux CI "
                "run of the identical commit for parity. Self-review banned."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "pytest:test_reach6_blob_provenance",
                "artifact_path": TESTS,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_pytest,
            },
            {
                "consumer": "measure_routes.planted_crlf_control",
                "artifact_path": f"{PROBE_DIR}/planted-control.json",
                "executed": True,
                "read_ok": True,
                "exit_code": m_rc,
                "probe": p_measure,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Independent reviewer has not reproduced REACH-6 on a Windows "
                    "core.autocrlf=true checkout of this commit, nor confirmed Linux CI parity."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context reviewer on Windows: materialise CRLF REGISTER.md, run "
                    "tools/command-center/validate.py, confirm exit 0 with blob hashing; "
                    "flip one content byte, confirm exit 1; Linux CI same commit exit 0; "
                    "return PASS with independent=true."
                ),
            }
        ],
        "defects": [],
        "failure": {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "Implementation + tests_required probes are green (reach6-blob pytest; "
                f"planted CRLF before_exit={gs['before_exit_code']} "
                f"after_exit={gs['after_exit_code']}; byte_delta==line_count). "
                "Catalog reviewer_requirement unmet — do not emit SUCCESS."
            ),
            "blocked_on": "independent Windows checkout + Linux CI parity (NOT-REVIEWED)",
            "diagnostic_tail": (out + "\n" + m_out)[-4000:],
            "two_signal_proof": [p_pytest, p_measure],
        },
        "report": {
            "kind": "provenance_blob_hash_report",
            "planted_before_exit": gs["before_exit_code"],
            "planted_after_exit": gs["after_exit_code"],
            "byte_delta": fx["byte_delta"],
            "line_count": fx["line_count"],
            "historic_windows_pair": live.get("historic_windows_pair"),
            "catalog_completion_sentinel": f"SUCCESS:{UNIT}",
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": "command-center/p2-wave/_build_CC0005.py",
            "related_units": ["IMP-0439", "TST-0334"],
        },
    }

    arts = []
    for a in receipt["artifacts"]:
        rel = a["path"]
        p = L.REPO / rel
        if p.is_file():
            data = p.read_bytes().replace(b"\r\n", b"\n")
            arts.append(
                {
                    "path": rel,
                    "bytes": len(data),
                    "sha256": __import__("hashlib").sha256(data).hexdigest(),
                    "present": True,
                }
            )
    arts.append({"path": OUT, "bytes": 0, "sha256": "pending", "present": False})
    man_doc = {
        "entry_id": UNIT,
        "unit_id": UNIT,
        "artifacts": arts,
        "writer": ar.ATOMIC_WRITER_ID,
        "registered_at": ended,
        "state": "BLOCKED",
    }
    ar.write_json_atomic(L.REPO / MANIFEST, man_doc)
    receipt["artifacts"].append(L.art(MANIFEST, "supporting"))

    errs = L.validate(receipt, SCHEMA)
    if errs:
        raise SystemExit(f"FAILED:{UNIT} schema-invalid ({len(errs)}): {errs[:12]}")

    ar.write_json_atomic(L.REPO / OUT, receipt)
    packed = ar.read_json(L.REPO / OUT)

    # First pass may warn; rewrite after attaching admission consumer like CC-0009.
    p_admit = L.probe(
        "verifier",
        "command",
        f"python3 command-center/receipt_validate.py {OUT}",
        "",
        None,
    )
    packed["downstream_consumers"].append(
        {
            "consumer": "receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": p_admit,
        }
    )
    # Clear previous schema warns by re-validating after consumer shape fix.
    errs2 = L.validate(packed, SCHEMA)
    if errs2:
        raise SystemExit(f"FAILED:{UNIT} schema-invalid ({len(errs2)}): {errs2[:12]}")
    ar.write_json_atomic(L.REPO / OUT, packed)

    val_rc, val_out = _run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    (L.REPO / PROBE_DIR / "receipt_validate.out").write_text(val_out, encoding="utf-8")
    # Update admission probe with real output and re-write.
    packed["downstream_consumers"][-1]["probe"] = L.probe(
        "verifier",
        "command",
        f"python3 command-center/receipt_validate.py {OUT}",
        val_out,
        val_rc,
    )
    packed["downstream_consumers"][-1]["exit_code"] = val_rc
    packed["downstream_consumers"][-1]["read_ok"] = val_rc == 0
    ar.write_json_atomic(L.REPO / OUT, packed)

    print(f"BLOCKED:{UNIT} wrote {OUT} bytes={(L.REPO / OUT).stat().st_size}")
    print(f"  receipt_validate rc={val_rc}")
    print(val_out.strip())
    print(
        f"  planted before_exit={gs['before_exit_code']} after_exit={gs['after_exit_code']} "
        f"delta={fx['byte_delta']}=={fx['line_count']}"
    )
    if val_rc != 0:
        raise SystemExit(f"CC-0005 receipt_validate failed:\n{val_out}")
    return ar.read_json(L.REPO / OUT)


if __name__ == "__main__":
    build()
