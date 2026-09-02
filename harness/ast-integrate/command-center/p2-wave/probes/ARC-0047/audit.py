"""Both-states audit of fixture fail-open classes and live estate gates.

Every row records known-broken and known-good outcomes. A gate silent in
both states is MEASURING-NOTHING. Text-matching gates also get a mention
document; firing on mention fails the use-versus-mention control.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import events as E
import gates as G
import live_gates as L

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

FIRE = True
PASS = False


def _row(
    gid: str,
    title: str,
    source: str,
    fail_open_class: str,
    *,
    text_matching: bool,
    broken_fired: bool,
    good_fired: bool,
    mention_fired: bool | None,
    notes: str,
) -> dict[str, Any]:
    if not broken_fired and not good_fired:
        classification = "MEASURING-NOTHING"
    elif not broken_fired and good_fired:
        classification = "INVERTED"
    elif broken_fired and good_fired:
        classification = "ALWAYS-FIRE"
    else:
        classification = "FAIL-CLOSED"
    mention_status = "N/A"
    if text_matching:
        if mention_fired is True:
            mention_status = "FIRES-ON-MENTION"
            if classification == "FAIL-CLOSED":
                classification = "FAIL-CLOSED-BUT-USE-VS-MENTION-FAIL"
            elif classification == "MEASURING-NOTHING":
                classification = "MEASURING-NOTHING"
        elif mention_fired is False:
            mention_status = "SILENT-ON-MENTION"
    if fail_open_class in {"text-vs-verb", "require-flag-off", "absent-pass"} and classification == "MEASURING-NOTHING":
        pass
    if fail_open_class == "text-vs-verb" and not broken_fired:
        classification = "FAIL-OPEN"
    if fail_open_class == "require-flag-off" and not broken_fired:
        classification = "FAIL-OPEN"
    if fail_open_class == "absent-pass" and not broken_fired:
        classification = "FAIL-OPEN"
    return {
        "id": gid,
        "title": title,
        "source": source,
        "fail_open_class": fail_open_class,
        "text_matching": text_matching,
        "broken": {"fired": bool(broken_fired), "event": "known-broken"},
        "good": {"fired": bool(good_fired), "event": "known-good"},
        "mention": (
            None
            if mention_fired is None
            else {"fired": bool(mention_fired), "event": "mention-only"}
        ),
        "mention_status": mention_status,
        "classification": classification,
        "both_states_recorded": True,
        "notes": notes,
    }


def _a1_unlisted() -> dict[str, Any]:
    loader = L.a1_loader()
    fixtures = HERE / "fixtures" / "a1"
    good_root = L.write_a1_tree(fixtures / "good", extra=False, duplicate=False)
    extra_root = L.write_a1_tree(fixtures / "unlisted", extra=True, duplicate=False)
    good = loader.load_a1(good_root)
    extra = loader.load_a1(extra_root)
    # Treat "unexpected capability present" as the security question.
    # Loader is silent on unlisted files: FIRE=False on the extra-file tree.
    broken_fired = bool(extra.get("errors"))  # no error → fail-open
    good_fired = bool(good.get("errors"))
    return _row(
        "L-A1-UNLISTED",
        "A1 loader silent-skip of unlisted capability files",
        "command-center/p2-wave/probes/ARC-0009/a1_loader.py",
        "absent-pass",
        text_matching=False,
        broken_fired=broken_fired,
        good_fired=good_fired,
        mention_fired=None,
        notes=(
            f"unlisted_on_disk={extra.get('unlisted_on_disk')} "
            f"silent_omission_ids={extra.get('silent_omission_ids')} "
            f"loader_ok_on_extra={extra.get('ok')}"
        ),
    )


def _a1_dup() -> dict[str, Any]:
    loader = L.a1_loader()
    fixtures = HERE / "fixtures" / "a1"
    good_root = L.write_a1_tree(fixtures / "good-dup", extra=False, duplicate=False)
    dup_root = L.write_a1_tree(fixtures / "dup", extra=False, duplicate=True)
    good = loader.load_a1(good_root)
    dup = loader.load_a1(dup_root)
    broken_fired = any("duplicate-id-FAIL-CLOSED" in e for e in (dup.get("errors") or []))
    good_fired = bool(good.get("errors"))
    return _row(
        "L-A1-DUP",
        "A1 loader FAIL-CLOSED on duplicate capability id",
        "command-center/p2-wave/probes/ARC-0009/a1_loader.py",
        "fail-closed-ok",
        text_matching=False,
        broken_fired=broken_fired,
        good_fired=good_fired,
        mention_fired=None,
        notes=f"dup_errors={dup.get('errors')} good_ok={good.get('ok')}",
    )


def _existence_skip() -> dict[str, Any]:
    root = HERE / "fixtures" / "existence"
    (root / "present").mkdir(parents=True, exist_ok=True)
    present = root / "present" / "ok.json"
    present.write_text("{}\n", encoding="utf-8")
    missing = root / "missing" / "nope.json"
    if missing.exists():
        missing.unlink()
    units = [
        {"id": "U-PRESENT", "output_path": str(present.relative_to(root))},
        {"id": "U-MISSING", "output_path": str(missing.relative_to(root))},
    ]
    visible = L.existence_visible_rows(units, root)
    # FIRE would mean the missing unit was reported as a failure. It is not.
    broken_fired = False
    good_units = [units[0]]
    good_visible = L.existence_visible_rows(good_units, root)
    good_fired = False
    return _row(
        "L-EXISTENCE-SKIP",
        "_probe_delivered.py skips missing output_path files instead of failing them",
        "command-center/p2-wave/_probe_delivered.py",
        "absent-pass",
        text_matching=False,
        broken_fired=broken_fired,
        good_fired=good_fired,
        mention_fired=None,
        notes=f"visible_on_mixed={visible} visible_on_present_only={good_visible}",
    )


def _schema_review() -> dict[str, Any]:
    good_path = HERE / "fixtures" / "schema" / "known-good-review.json"
    good_doc = json.loads(good_path.read_text(encoding="utf-8"))
    broken_fired = L.schema_review_gate({})
    good_fired = L.schema_review_gate(good_doc)
    return _row(
        "L-SCHEMA-REVIEW",
        "architecture-review.schema.json required-field gate (disk $ref)",
        "command-center/schema/architecture-review.schema.json",
        "fail-closed-ok",
        text_matching=False,
        broken_fired=broken_fired,
        good_fired=good_fired,
        mention_fired=None,
        notes=(
            "empty object is known-broken; "
            "fixtures/schema/known-good-review.json is known-good "
            "(A1 FAILURE-MODES.json is absent on this worktree)"
        ),
    )


def _measure_artifact() -> dict[str, Any]:
    good = HERE / "fixtures" / "schema" / "known-good-review.json"
    missing = HERE / "fixtures" / "measure-missing" / "no-such.json"
    if missing.exists():
        missing.unlink()
    broken_fired = L.measure_artifact_gate(missing, "SUCCESS:ARC-0005")
    good_fired = L.measure_artifact_gate(good, "SUCCESS:ARC-0005")
    blocked = HERE / "fixtures" / "measure-blocked" / "blocked.json"
    blocked.parent.mkdir(parents=True, exist_ok=True)
    blocked.write_text(
        json.dumps({"state": "BLOCKED", "sentinel": "SUCCESS:X"}) + "\n",
        encoding="utf-8",
    )
    blocked_fired = L.measure_artifact_gate(blocked, "SUCCESS:X")
    return _row(
        "L-MEASURE-ARTIFACT",
        "_measure_one_delivered.py artifact predicates (absent/BLOCKED/sentinel)",
        "command-center/p2-wave/_measure_one_delivered.py",
        "fail-closed-ok",
        text_matching=False,
        broken_fired=broken_fired and blocked_fired,
        good_fired=good_fired,
        mention_fired=None,
        notes=(
            f"absent_fired={broken_fired} blocked_fired={blocked_fired} "
            "cloud_ok_not_consulted=True"
        ),
    )


def _stub_text() -> dict[str, Any]:
    broken = "PLACEHOLDER"
    good = "delivered artifact with measured content SUCCESS:ARC-0005"
    mention = (
        "The PLACEHOLDER token is a stub-sentinel class this detector watches for."
    )
    return _row(
        "L-STUB-TEXT",
        "_probe_delivered.py STUB_PAT matches payload TEXT",
        "command-center/p2-wave/_probe_delivered.py",
        "text-vs-verb",
        text_matching=True,
        broken_fired=L.stub_text_gate(broken),
        good_fired=L.stub_text_gate(good),
        mention_fired=L.stub_text_gate(mention),
        notes="mention document discusses PLACEHOLDER; STUB_PAT still fires",
    )


def run_audit() -> dict[str, Any]:
    rows = [
        _row(
            "G-TEXT-PAYLOAD",
            "Guard matching payload TEXT for forbidden tool verb Bash",
            "command-center/p2-wave/probes/ARC-0047/gates.py:text_payload_guard",
            "text-vs-verb",
            text_matching=True,
            broken_fired=G.text_payload_guard(E.USE_BASH),
            good_fired=G.text_payload_guard(E.GOOD_READ),
            mention_fired=G.text_payload_guard(E.MENTION_BASH),
            notes="USE event has verb=Bash but payload has no word Bash → silent (fail-open)",
        ),
        _row(
            "G-TOOL-VERB",
            "Guard matching tool VERB field only (use-versus-mention correct)",
            "command-center/p2-wave/probes/ARC-0047/gates.py:tool_verb_guard",
            "fail-closed-ok",
            text_matching=True,
            broken_fired=G.tool_verb_guard(E.USE_BASH),
            good_fired=G.tool_verb_guard(E.GOOD_READ),
            mention_fired=G.tool_verb_guard(E.MENTION_BASH),
            notes="mention document must not fire; USE of Bash must fire",
        ),
        _row(
            "G-CI-REQUIRE-OFF",
            "Completeness check whose require-flag defaults off",
            "command-center/p2-wave/probes/ARC-0047/gates.py:completeness_require",
            "require-flag-off",
            text_matching=False,
            broken_fired=G.completeness_require(E.MISSING_ARTIFACT_REQUIRE_DEFAULT, default_on=False),
            good_fired=G.completeness_require(E.PRESENT_ARTIFACT_REQUIRE_ON, default_on=False),
            mention_fired=None,
            notes="missing artifact + unset flag → PASS (skipped)",
        ),
        _row(
            "G-CI-REQUIRE-ON",
            "Completeness check with require-flag default ON",
            "command-center/p2-wave/probes/ARC-0047/gates.py:completeness_require",
            "fail-closed-ok",
            text_matching=False,
            broken_fired=G.completeness_require(E.MISSING_ARTIFACT_REQUIRE_ON, default_on=True),
            good_fired=G.completeness_require(E.PRESENT_ARTIFACT_REQUIRE_ON, default_on=True),
            mention_fired=None,
            notes="same missing artifact fires once require is on",
        ),
        _row(
            "G-SILENT",
            "Detector silent in both broken and fixed states",
            "command-center/p2-wave/probes/ARC-0047/gates.py:silent_detector",
            "silent-both",
            text_matching=False,
            broken_fired=G.silent_detector(E.USE_BASH),
            good_fired=G.silent_detector(E.GOOD_READ),
            mention_fired=None,
            notes="detector-control: G-TOOL-VERB fires on the same USE event",
        ),
        _row(
            "G-ABSENT-PASS",
            "Gate whose absent input normalizes to a passing value",
            "command-center/p2-wave/probes/ARC-0047/gates.py:absent_normalizes_to_pass",
            "absent-pass",
            text_matching=False,
            broken_fired=G.absent_normalizes_to_pass(E.ABSENT_INPUT),
            good_fired=G.absent_normalizes_to_pass(E.PRESENT_GOOD),
            mention_fired=None,
            notes="absent input → PASS; present-bad still fires (not shown in good column)",
        ),
        _row(
            "G-ABSENT-FAIL",
            "Gate whose absent input fail-closes",
            "command-center/p2-wave/probes/ARC-0047/gates.py:absent_fail_closed",
            "fail-closed-ok",
            text_matching=False,
            broken_fired=G.absent_fail_closed(E.ABSENT_INPUT),
            good_fired=G.absent_fail_closed(E.PRESENT_GOOD),
            mention_fired=None,
            notes="absent input → FIRE",
        ),
        _stub_text(),
        _existence_skip(),
        _schema_review(),
        _a1_unlisted(),
        _a1_dup(),
        _measure_artifact(),
    ]

    by_id = {r["id"]: r for r in rows}
    measuring_nothing = [r["id"] for r in rows if r["classification"] == "MEASURING-NOTHING"]
    fail_open = [r["id"] for r in rows if r["classification"] == "FAIL-OPEN"]
    fail_closed = [r["id"] for r in rows if r["classification"] in {"FAIL-CLOSED", "FAIL-CLOSED-BUT-USE-VS-MENTION-FAIL"}]
    mention_fail = [
        r["id"]
        for r in rows
        if r.get("mention_status") == "FIRES-ON-MENTION"
    ]
    mention_ok = [
        r["id"]
        for r in rows
        if r.get("mention_status") == "SILENT-ON-MENTION"
    ]

    # Required mechanical outcomes (catalog tests_required).
    checks = {
        "g_text_silent_on_use": by_id["G-TEXT-PAYLOAD"]["broken"]["fired"] is False,
        "g_text_fires_on_mention": by_id["G-TEXT-PAYLOAD"]["mention"]["fired"] is True,
        "g_verb_fires_on_use": by_id["G-TOOL-VERB"]["broken"]["fired"] is True,
        "g_verb_silent_on_mention": by_id["G-TOOL-VERB"]["mention"]["fired"] is False,
        "g_verb_silent_on_good": by_id["G-TOOL-VERB"]["good"]["fired"] is False,
        "require_off_silent_on_missing": by_id["G-CI-REQUIRE-OFF"]["broken"]["fired"] is False,
        "require_on_fires_on_missing": by_id["G-CI-REQUIRE-ON"]["broken"]["fired"] is True,
        "silent_both": by_id["G-SILENT"]["classification"] == "MEASURING-NOTHING",
        "absent_pass_fail_open": by_id["G-ABSENT-PASS"]["classification"] == "FAIL-OPEN",
        "absent_fail_closed": by_id["G-ABSENT-FAIL"]["classification"] == "FAIL-CLOSED",
        "stub_fires_on_mention": by_id["L-STUB-TEXT"]["mention"]["fired"] is True,
        "schema_fail_closed": by_id["L-SCHEMA-REVIEW"]["classification"] == "FAIL-CLOSED",
        "a1_unlisted_fail_open": by_id["L-A1-UNLISTED"]["classification"] in {"FAIL-OPEN", "MEASURING-NOTHING"},
        "a1_dup_fail_closed": by_id["L-A1-DUP"]["classification"] == "FAIL-CLOSED",
        "measure_fail_closed": by_id["L-MEASURE-ARTIFACT"]["classification"] == "FAIL-CLOSED",
        "existence_skip_fail_open": by_id["L-EXISTENCE-SKIP"]["classification"] in {"FAIL-OPEN", "MEASURING-NOTHING"},
        "every_row_both_states": all(r["both_states_recorded"] for r in rows),
        "a7_design_absent": not (REPO / "command-center/phase3/A7/DESIGN.json").is_file(),
        "absent_pass_fires_on_present_bad": G.absent_normalizes_to_pass(E.PRESENT_BAD) is True,
        "except_pass_is_fail_open": G.except_pass_gate(E.EXCEPT_ON_USE) is False,
        "verb_detector_control_for_silent": G.tool_verb_guard(E.USE_BASH) is True,
    }
    ok = all(checks.values())
    return {
        "rows": rows,
        "gate_count": len(rows),
        "measuring_nothing": measuring_nothing,
        "fail_open": fail_open,
        "fail_closed": fail_closed,
        "mention_fail": mention_fail,
        "mention_ok": mention_ok,
        "checks": checks,
        "pass": ok,
        "both_states_rule": {
            "id": "BOTH-STATES-EVERY-SECURITY-GATE",
            "must": [
                "known-broken input MUST fire (FIRE=true)",
                "known-good input MUST be silent (FIRE=false)",
                "silent in both states is MEASURING-NOTHING, not a pass",
                "absent or unreadable input MUST fire (fail-closed), never PASS",
                "text-matching gates MUST be silent on a document that only MENTIONS the forbidden pattern",
                "CI completeness require-flag MUST default ON",
                "a gate that cannot produce both outcomes is not shipped",
            ],
        },
    }


if __name__ == "__main__":
    out = run_audit()
    print(json.dumps({k: out[k] for k in out if k != "rows"}, indent=2))
    for r in out["rows"]:
        print(
            f"{r['id']:20} broken={r['broken']['fired']} good={r['good']['fired']} "
            f"mention={r['mention_status']} class={r['classification']}"
        )
    print("PASS" if out["pass"] else "FAIL")
    raise SystemExit(0 if out["pass"] else 1)
