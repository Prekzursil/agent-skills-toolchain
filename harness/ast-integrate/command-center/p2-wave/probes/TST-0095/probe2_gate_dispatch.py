#!/usr/bin/env python3
"""Probe 2: gate + dispatch, mechanically independent of the extractor control.

Reads planted fixtures from disk (not probe 1's return value). Requires the
gate to fail on a single planted two-definition id, pass a clean corpus, and
refuse dispatch of two work units that share an id. Also refuses a receipt
that claims the 31-way is live on this worktree when the original markdown
artifacts are absent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import collision as C  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0095.json"
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0095/probe2_gate_dispatch.py"
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0095-probe2 {msg}")
    return 1


def main() -> int:
    S.ensure_fixtures()
    gate_live = S.test_gate_fails_on_any_id_with_two_definitions()
    disp_live = S.test_dispatch_refuses_to_run_two_units_with_the_same_id()
    if not gate_live["ok"]:
        print(json.dumps(gate_live, sort_keys=True, default=str)[:4000])
        return fail("gate did not fail on two-definition ids / pass clean corpus")
    if not disp_live["ok"]:
        print(json.dumps(disp_live, sort_keys=True, default=str)[:4000])
        return fail("dispatch did not refuse duplicate work-unit ids")

    planted_bp = C.extract_paths(
        [
            S.PLANTED_DIR / "blueprint-meaning-a.json",
            S.PLANTED_DIR / "blueprint-meaning-b.json",
        ],
        repo=REPO,
    )
    planted_gate = C.gate(planted_bp)
    if planted_gate["ok"] or "BP-TWOMEAN" not in planted_gate["colliding_ids"]:
        return fail("planted BP-TWOMEAN did not fail the gate by name")

    clean_gate = C.gate(S.extract_dir(S.CLEAN_DIR))
    if not clean_gate["ok"]:
        return fail("clean corpus failed the gate")

    units = [r for r in S.extract_dir(S.PLANTED_DIR) if r["kind"] == "work_unit"]
    disp = C.dispatch(units)
    if disp["ok"] or disp["refused_ids"] != ["TST-DUP-0001"]:
        return fail(f"dispatch refused_ids={disp.get('refused_ids')}")
    if any(u["id"] == "TST-DUP-0001" for u in disp["ran"]):
        return fail("dispatch ran a duplicate-id unit")
    ran_ids = {u["id"] for u in disp["ran"]}
    if ran_ids != {"TST-UNIQ-0001", "TST-UNIQ-0002"}:
        return fail(f"dispatch ran unexpected unique set {ran_ids}")

    orig_opt = (REPO / "07-OPTION-UNIVERSE.md").is_file()
    orig_mech = (REPO / "13-ARCHITECTURE-CANDIDATES.md").is_file()
    live_present = orig_opt and orig_mech

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        text = json.dumps(doc)
        if "SUCCESS:TST-0095" not in text:
            return fail("artifact sentinel-absent")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared:{st}")
        if doc.get("live_31way_on_this_worktree") is True and not live_present:
            return fail("receipt overclaims live 31-way; original markdown absent")
        tests = doc.get("tests") or []
        names = {t.get("name") or t.get("id") for t in tests if isinstance(t, dict)}
        required = {
            "test_extractor_reproduces_the_known_collision_set",
            "test_gate_fails_on_any_id_with_two_definitions",
            "test_dispatch_refuses_to_run_two_units_with_the_same_id",
        }
        if not required.issubset(names):
            return fail(f"artifact tests missing {required - names}")
        for row in tests:
            if row.get("name") in required and row.get("result") != "PASS":
                return fail(f"artifact test not PASS: {row.get('name')}")
        src = doc.get("source_probe") or {}
        ver = doc.get("verifier_probe") or {}
        if not src or not ver:
            return fail("empty source_probe or verifier_probe")
        if src.get("command") == ver.get("command"):
            return fail("source and verifier commands identical")
        if ver.get("command") != P2 and P2 not in str(ver.get("command") or ""):
            # verifier may be stored as relative command; accept suffix match
            if not str(ver.get("command") or "").endswith("probe2_gate_dispatch.py"):
                return fail("verifier_probe is not probe2")
        rec_gate = (doc.get("gate") or {}).get("planted_two_definition_fails")
        if rec_gate is not True:
            return fail("artifact gate.planted_two_definition_fails is not true")
        rec_disp = (doc.get("dispatch") or {}).get("duplicate_id_refused")
        if rec_disp is not True:
            return fail("artifact dispatch.duplicate_id_refused is not true")

    out = {
        "probe": "probe2-gate-dispatch",
        "unit_id": "TST-0095",
        "planted_gate_fails": True,
        "planted_id": "BP-TWOMEAN",
        "clean_gate_ok": True,
        "duplicate_dispatch_refused": True,
        "unique_units_ran": sorted(ran_ids),
        "live_31way_markdown_present": live_present,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"gate planted BP-TWOMEAN colliding={planted_gate['colliding_ids']} "
        f"dispatch refused={disp['refused_ids']} ran={sorted(ran_ids)}"
    )
    print("SUCCESS:TST-0095-probe2 gate fails two-definition ids; dispatch refuses duplicates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
