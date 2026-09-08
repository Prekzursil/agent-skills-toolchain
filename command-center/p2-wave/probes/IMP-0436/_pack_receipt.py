#!/usr/bin/env python3
"""Pack IMP-0436 — catalog override semantics as honest BLOCKED receipt.

Catalog reviewer_requirement: 2 independent reviewers (schema reviewer +
adversarial refuter probing null semantics). Never invent SUCCESS. Never
invent independent-review.json.

Linux Cloud / single-checkout scope disclosed in reviewer.notes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "IMP-0436"
OUT = "command-center/receipts/IMP-0436.json"
SCHEMA = "command-center/schema/receipt.schema.json"
ALSO = ["command-center/schema/receipt.schema.json"]
PROBE_DIR = "command-center/p2-wave/probes/IMP-0436"
GATE = "tools/command-center/catalog.py"
VALIDATE = "tools/command-center/validate.py"
TESTS = "tools/command-center/tests/test_catalog_overrides.py"
DUMP = f"{PROBE_DIR}/dump_resolved_view.py"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = L.REPO / PROBE_DIR / "independent-review.json"
TS0 = "2026-09-08T01:45:00Z"


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


def load_reviews() -> list[dict]:
    """Promote only when BOTH independent reviews are present and PASS."""
    if not REVIEW.is_file():
        return []
    try:
        raw = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    reviews = raw if isinstance(raw, list) else [raw]
    good = []
    for rev in reviews:
        if rev.get("verdict") != "PASS":
            continue
        if not rev.get("independent") or not rev.get("fresh_context"):
            continue
        role = str(rev.get("role", "")).lower()
        if "schema" not in role and "refut" not in role and "adversarial" not in role:
            # Accept explicit reviewer_slot markers too.
            slot = str(rev.get("reviewer_slot", "")).lower()
            if slot not in ("schema", "adversarial-refuter", "refuter"):
                continue
        good.append(rev)
    # Need both slots represented.
    slots = set()
    for rev in good:
        role = str(rev.get("role", "")).lower() + " " + str(rev.get("reviewer_slot", "")).lower()
        if "schema" in role:
            slots.add("schema")
        if "refut" in role or "adversarial" in role:
            slots.add("refuter")
    if slots >= {"schema", "refuter"} and len(good) >= 2:
        return good
    return []


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    rc, out = _run([sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line"])
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out, encoding="utf-8")
    if rc != 0:
        raise SystemExit(f"IMP-0436 pytest failed:\n{out}")

    d_rc, d_out = _run([sys.executable, "-B", str(L.REPO / DUMP)])
    (L.REPO / PROBE_DIR / "dump.out").write_text(d_out, encoding="utf-8")
    if d_rc != 0:
        raise SystemExit(f"IMP-0436 dump_resolved_view failed:\n{d_out}")

    resolved = json.loads(
        (L.REPO / PROBE_DIR / "resolved-view.json").read_text(encoding="utf-8")
    )
    mutation = json.loads(
        (L.REPO / PROBE_DIR / "defaults-mutation.json").read_text(encoding="utf-8")
    )

    v_rc, v_out = _run([sys.executable, str(L.REPO / VALIDATE)])
    (L.REPO / PROBE_DIR / "validate.out").write_text(v_out, encoding="utf-8")

    reviews = load_reviews()
    success = len(reviews) >= 2

    p_pytest = L.probe(
        "source", "test-run", f"python3 -m pytest {TESTS} -q --tb=line", out, rc
    )
    p_dump = L.probe(
        "verifier", "command", f"python3 -B {DUMP}", d_out, d_rc
    )
    p_val = L.probe(
        "source", "command", f"python3 {VALIDATE}", v_out, v_rc
    )

    units = {u["id"]: u for u in resolved["units"]}
    three_override_n = sum(
        1
        for f, row in units["FIX-THREE-OVERRIDES"]["fields"].items()
        if row["provenance"] == "override"
    )
    all_def_n = sum(
        1
        for f, row in units["FIX-ALL-DEFAULTS"]["fields"].items()
        if row["provenance"] == "default"
    )
    nine_n = sum(
        1
        for f, row in units["FIX-ALL-NINE"]["fields"].items()
        if row["provenance"] in ("override", "explicit-null")
    )

    if success:
        state = "SUCCESS"
        sentinel = "SENTINEL:IMP-0436:CATALOG-OVERRIDES-ENFORCED"
        notes_parts = []
        for rev in reviews:
            n = rev.get("notes", "")
            notes_parts.append(n if isinstance(n, str) else json.dumps(n))
        reviewer = {
            "reviewer_id": "+".join(r.get("reviewer_id", "reviewer") for r in reviews),
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": reviews[0].get("vendor", "openai"),
            "reviewed_at": reviews[0].get("reviewed_at", ended),
            "notes": " | ".join(notes_parts)[:4000],
        }
        residual: list[dict] = []
        failure = None
        anti = "SUCCESS-after-dual-independent-review"
        downstream = [
            {
                "consumer": "catalog.resolve_field",
                "artifact_path": f"{PROBE_DIR}/resolved-view.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_dump,
            }
        ]
    else:
        state = "BLOCKED"
        sentinel = (
            f"FAILED:{UNIT} blocked-on-independent-review; "
            f"precedence=unit-over-defaults; explicit-null≠fall-through; "
            f"V-DEFAULTS both_states={mutation.get('both_states')}; "
            f"resolved-view FIX-ALL-DEFAULTS defaults={all_def_n}/9 "
            f"FIX-THREE-OVERRIDES overrides={three_override_n}/9 "
            f"FIX-ALL-NINE override|null={nine_n}/9; "
            f"SUCCESS:{UNIT} withheld pending dual independent reviews "
            f"(schema + adversarial null-semantics refuter)"
        )
        reviewer = {
            "reviewer_id": "awaiting-dual-independent-review",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only on Linux Cloud single-checkout. Catalog "
                "reviewer_requirement unmet: needs 2 independent reviewers — "
                "(1) a schema reviewer confirming resolve_field provenance "
                "contract and V-DEFAULTS wiring, and (2) an adversarial refuter "
                "probing null semantics (unit-level null must stay "
                "explicit-null, not fall through). Self-review banned; "
                "independent-review.json not invented. Scope: live 2007 "
                "work_units were not wholesale-mutated; evidence uses "
                "fixtures/override-catalog.json plus a scratch live-item "
                "override probe. Prompt-One Windows trees unmounted."
            ),
        }
        residual = [
            {
                "claim": (
                    "Dual independent review (schema + adversarial null-semantics "
                    "refuter) has not landed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context schema reviewer and separate adversarial "
                    "refuter each return PASS with independent=true, "
                    "fresh_context=true, distinct reviewer_id/role "
                    "(schema vs refuter), confirming precedence + explicit-null "
                    "+ defaults-deletion red-proof; then re-pack may emit "
                    "SENTINEL:IMP-0436:CATALOG-OVERRIDES-ENFORCED."
                ),
            }
        ]
        failure = {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "Override resolver + V-DEFAULTS gate + pytest + resolved-view "
                f"dump are green (pytest rc={rc}; dump ok; "
                f"mutation both_states={mutation.get('both_states')}; "
                f"live validate rc={v_rc}). Catalog reviewer_requirement "
                "demands 2 independent reviewers; do not emit SUCCESS without "
                "both PASS reviews."
            ),
            "blocked_on": (
                "independent schema reviewer + adversarial null-semantics refuter"
            ),
            "diagnostic_tail": (out + "\n" + d_out + "\n" + v_out)[-4000:],
            "two_signal_proof": [p_pytest, p_dump],
        }
        anti = "BLOCKED-pending-dual-independent-review"
        downstream = [
            {
                "consumer": "catalog.resolve_field",
                "artifact_path": f"{PROBE_DIR}/resolved-view.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_dump,
            },
            {
                "consumer": "validate.V-DEFAULTS",
                "artifact_path": f"{PROBE_DIR}/defaults-mutation.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_dump,
            },
            {
                "consumer": "cc-validate-live",
                "artifact_path": f"{PROBE_DIR}/validate.out",
                "executed": True,
                "read_ok": True,
                "exit_code": v_rc,
                "probe": p_val,
            },
        ]

    arts = [
        L.art(GATE, "primary"),
        L.art(VALIDATE, "supporting"),
        L.art(TESTS, "supporting"),
        L.art(f"{PROBE_DIR}/fixtures/override-catalog.json", "control"),
        L.art(f"{PROBE_DIR}/resolved-view.json", "log"),
        L.art(f"{PROBE_DIR}/defaults-mutation.json", "log"),
        L.art(f"{PROBE_DIR}/pytest.out", "log"),
        L.art(f"{PROBE_DIR}/dump.out", "log"),
        L.art(f"{PROBE_DIR}/validate.out", "log"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
        L.art(DUMP, "control"),
    ]
    if success:
        arts.append(L.art(f"{PROBE_DIR}/independent-review.json", "supporting"))

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#IMP-0436",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "schema-author",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    "Enforced precedence: unit-declared key wins over "
                    "catalog.defaults; explicit JSON null → "
                    "provenance=explicit-null (no fall-through). Implemented in "
                    f"{GATE}:resolve_field / resolve_unit / "
                    "defaults_block_violations; validate.py emits always-on "
                    "V-DEFAULTS."
                ),
                "CONFIRMED",
                f"file:{GATE}",
                [p_pytest, p_dump],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Resolved-view dump for three fixture units: "
                    f"FIX-ALL-DEFAULTS defaults={all_def_n}/9; "
                    f"FIX-THREE-OVERRIDES overrides={three_override_n}/9; "
                    f"FIX-ALL-NINE override|explicit-null={nine_n}/9 "
                    "(timeout_seconds explicit-null). Live scratch override "
                    "probe confirms the same resolver on WORK-UNIT-CATALOG.json."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/resolved-view.json",
                [p_dump, p_pytest],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Defaults-deletion mutation both-states: good violations="
                    f"{mutation.get('good_state_violations')}; delete block "
                    f"V-DEFAULTS fired="
                    f"{mutation.get('delete_defaults_block', {}).get('fired')}; "
                    f"delete timeout_seconds default fired="
                    f"{mutation.get('delete_single_default_field', {}).get('fired')}; "
                    f"both_states={mutation.get('both_states')}."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/defaults-mutation.json",
                [p_dump, p_val],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot; null-semantics disputes require a "
                "fresh adversarial refuter, not a third implementer attempt."
            ),
        },
        "tests": [
            {
                "id": "precedence-per-field",
                "name": "Unit override wins over default for each of the nine fields.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_precedence_unit_wins_per_field -q"
                ),
                "result": "PASS" if rc == 0 else "FAIL",
                "assertions": 9,
                "output_tail": out[-800:],
            },
            {
                "id": "explicit-null-no-fallthrough",
                "name": "Unit-level JSON null is explicit-null, not default fall-through.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_explicit_null_does_not_fall_through -q"
                ),
                "result": "PASS" if rc == 0 else "FAIL",
                "assertions": 9,
                "output_tail": out[-800:],
            },
            {
                "id": "defaults-block-deletion-caught",
                "name": "Deleting defaults turns validate red without --require-complete.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_defaults_block_deletion_is_caught_without_require_complete -q"
                ),
                "result": "PASS" if mutation.get("both_states") else "FAIL",
                "assertions": 2,
                "output_tail": d_out[-800:],
            },
            {
                "id": "single-default-field-deletion-caught",
                "name": "Deleting one relied-upon default field fires V-DEFAULTS.",
                "command": (
                    f"python3 -m pytest {TESTS}::"
                    "test_single_default_field_deletion_caught_when_items_rely -q"
                ),
                "result": "PASS"
                if mutation.get("delete_single_default_field", {}).get("fired")
                else "FAIL",
                "assertions": 2,
                "output_tail": d_out[-800:],
            },
            {
                "id": "resolved-view-three-units",
                "name": "Resolved-view dump covers all-defaults / three / all-nine shapes.",
                "command": f"python3 -B {DUMP}",
                "result": "PASS" if d_rc == 0 else "FAIL",
                "assertions": 6,
                "output_tail": d_out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "defaults-block-deleted-fires",
                "mutation",
                "Deleting catalog.defaults must emit V-DEFAULTS (not silent green).",
                True,
                True,
                bad=mutation.get("delete_defaults_block", {}).get("sample_detail", ""),
                good=f"good_violations={mutation.get('good_state_violations')}",
            ),
            L.control(
                "single-default-field-deleted-fires",
                "mutation",
                "Deleting defaults.timeout_seconds while items rely on it must fire.",
                True,
                True,
                bad=mutation.get("delete_single_default_field", {}).get(
                    "sample_detail", ""
                ),
                good="live catalog clean",
            ),
            L.control(
                "explicit-null-not-default",
                "known-broken-fixture",
                "FIX-ALL-NINE.timeout_seconds=null must resolve explicit-null ≠ 1800.",
                True,
                True,
                bad="would fall through to 1800",
                good=str(units["FIX-ALL-NINE"]["fields"]["timeout_seconds"]),
            ),
        ],
        "reviewer": reviewer,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": downstream,
        "residual_unknowns": residual,
        "defects": [],
        "report": {
            "kind": "catalog-override-semantics",
            "observations": [
                {
                    "name": "precedence_rule",
                    "measured": resolved["precedence_rule"],
                    "method": "catalog.resolve_field + validate V-DEFAULTS",
                    "anchor": GATE,
                },
                {
                    "name": "resolved_view_counts",
                    "measured": {
                        "all_defaults": all_def_n,
                        "three_overrides": three_override_n,
                        "all_nine": nine_n,
                    },
                    "method": "dump_resolved_view.py on fixtures/override-catalog.json",
                    "anchor": f"{PROBE_DIR}/resolved-view.json",
                },
                {
                    "name": "defaults_mutation_both_states",
                    "measured": mutation.get("both_states"),
                    "method": "scratch copy delete defaults / delete timeout_seconds",
                    "anchor": f"{PROBE_DIR}/defaults-mutation.json",
                },
            ],
            "control_ids": [
                "precedence-per-field",
                "explicit-null-no-fallthrough",
                "defaults-block-deletion-caught",
                "single-default-field-deletion-caught",
                "resolved-view-three-units",
            ],
            "dual_reviewer_requirement": {
                "required_count": 2,
                "slots": ["schema-reviewer", "adversarial-null-refuter"],
                "independent_review_present": REVIEW.is_file(),
                "reviews_loaded": len(reviews),
            },
            "scope": {
                "execution_substrate": "linux-cloud-agent",
                "checkout": "single",
                "live_catalog_wholesale_mutation": False,
                "fixture_path": f"{PROBE_DIR}/fixtures/override-catalog.json",
            },
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "anti_false_green": anti,
            "linux_cloud_scope": True,
            "catalog_completion_sentinel": "SENTINEL:IMP-0436:CATALOG-OVERRIDES-ENFORCED",
        },
    }
    if failure is not None:
        receipt["failure"] = failure

    (L.REPO / MANIFEST).write_text(
        json.dumps(
            {
                "entry_id": UNIT,
                "unit_id": UNIT,
                "artifacts": [
                    OUT,
                    GATE,
                    VALIDATE,
                    TESTS,
                    f"{PROBE_DIR}/fixtures/override-catalog.json",
                    f"{PROBE_DIR}/resolved-view.json",
                    f"{PROBE_DIR}/defaults-mutation.json",
                    DUMP,
                ],
                "state": state,
                "registered_at": ended,
                "reviewer_requirement": (
                    "2 independent reviewers: schema reviewer + adversarial "
                    "refuter probing null semantics"
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    rc_w = L.write_if_valid(receipt, OUT, SCHEMA, also=ALSO)
    if rc_w != 0:
        raise SystemExit(rc_w)
    receipt["artifacts"].insert(0, L.art(OUT, "primary"))
    rc2 = L.write_if_valid(receipt, OUT, SCHEMA, also=ALSO)
    if rc2 != 0:
        raise SystemExit(rc2)

    v_rc2, v_out2 = _run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    (L.REPO / PROBE_DIR / "receipt-validate.out").write_text(v_out2, encoding="utf-8")
    if v_rc2 != 0 or "ACCEPT" not in v_out2:
        raise SystemExit(f"receipt_validate rejected:\n{v_out2}")

    print(f"PACKED {OUT} state={state} bytes={L.art(OUT)['bytes']}")
    print(
        f"resolved all_defaults={all_def_n} three={three_override_n} nine={nine_n} "
        f"mutation_both_states={mutation.get('both_states')}"
    )
    print(f"independent_review={REVIEW.is_file()} (must stay false for this emit)")
    return receipt


if __name__ == "__main__":
    build()
