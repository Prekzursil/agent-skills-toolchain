"""Run the TST-0050 conformance suite: live harvest plus both-states controls."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from checker import check_payload, leak_needles_in
from contract import (
    PATH_CANARY,
    RULES,
    USER_CANARY,
    credential_canary,
    value_fingerprint,
)
from harvest import canonical_live, harvest_live, harvest_scratch
from paths import HERE, REPO, UNIT
from test_double import emit, emit_ignores_disabled

FIXTURES = HERE / "fixtures"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def decision_ids(doc: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(doc, list):
        for row in doc:
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                ids.add(row["id"])
    return ids


def conforming() -> dict[str, Any]:
    return load_json(FIXTURES / "conforming.json")


def plant_credential() -> dict[str, Any]:
    payload = conforming()
    payload["session_ref"] = credential_canary()
    return payload


def plant_path() -> dict[str, Any]:
    payload = conforming()
    payload["session_ref"] = PATH_CANARY
    return payload


def plant_user() -> dict[str, Any]:
    payload = conforming()
    payload["event_name"] = USER_CANARY
    return payload


def run_cmd(command: str) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    return {
        "command": command,
        "exit_code": proc.returncode,
        "stdout_len": len(proc.stdout or ""),
        "stderr_len": len(proc.stderr or ""),
    }


def finding_rules(result: dict[str, Any]) -> set[str]:
    return {f.get("rule") for f in (result.get("findings") or []) if f.get("rule")}


def control_row(
    *,
    rule_id: str,
    good: dict[str, Any],
    bad: dict[str, Any],
    expect_rule: str,
) -> dict[str, Any]:
    silent = bool(good.get("ok"))
    fired = (not bad.get("ok")) and (expect_rule in finding_rules(bad))
    return {
        "id": rule_id,
        "fired_on_bad": fired,
        "silent_on_good": silent,
        "pass": fired and silent,
        "expect_rule": expect_rule,
        "good_ok": bool(good.get("ok")),
        "bad_ok": bool(bad.get("ok")),
        "bad_rules": sorted(finding_rules(bad)),
    }


def both_states(log_ids: set[str]) -> dict[str, Any]:
    good_payload = conforming()
    good = check_payload(good_payload, decision_log_ids=log_ids)
    extra = check_payload(
        load_json(FIXTURES / "extra_field.json"), decision_log_ids=log_ids
    )
    cred = check_payload(plant_credential(), decision_log_ids=log_ids)
    path = check_payload(plant_path(), decision_log_ids=log_ids)
    user = check_payload(plant_user(), decision_log_ids=log_ids)
    no_optin = check_payload(
        load_json(FIXTURES / "egress_no_optin.json"), decision_log_ids=log_ids
    )
    bad_optin = check_payload(
        load_json(FIXTURES / "egress_bad_optin.json"), decision_log_ids=log_ids
    )
    ok_optin = check_payload(
        load_json(FIXTURES / "egress_ok.json"), decision_log_ids=log_ids
    )

    enabled_off = emit(False, good_payload)
    enabled_on = emit(True, good_payload)
    broken = emit_ignores_disabled(good_payload)
    disabled_ok = enabled_off == []
    disabled_on_emits = len(enabled_on) == 1
    broken_fires = len(broken) != 0

    scratch = harvest_scratch([load_json(FIXTURES / "extra_field.json")])
    scratch_payloads = [row["payload"] for row in scratch["payloads"]]
    scratch_checked = [
        check_payload(p, decision_log_ids=log_ids) for p in scratch_payloads
    ]
    capture_complete = scratch["payload_count"] == 1 and not scratch_checked[0]["ok"]

    rows = [
        control_row(
            rule_id="declared-fields",
            good=good,
            bad=extra,
            expect_rule="declared-fields",
        ),
        control_row(
            rule_id="no-credential",
            good=good,
            bad=cred,
            expect_rule="no-credential",
        ),
        control_row(
            rule_id="no-path",
            good=good,
            bad=path,
            expect_rule="no-path",
        ),
        control_row(
            rule_id="no-user-content",
            good=good,
            bad=user,
            expect_rule="no-user-content",
        ),
        control_row(
            rule_id="egress-requires-opt-in",
            good=ok_optin,
            bad=no_optin,
            expect_rule="egress-requires-opt-in",
        ),
        control_row(
            rule_id="opt-in-in-decision-log",
            good=ok_optin,
            bad=bad_optin,
            expect_rule="opt-in-in-decision-log",
        ),
        {
            "id": "disabled-emits-nothing",
            "fired_on_bad": broken_fires,
            "silent_on_good": disabled_ok,
            "pass": broken_fires and disabled_ok and disabled_on_emits,
            "expect_rule": "disabled-emits-nothing",
            "good_ok": disabled_ok,
            "bad_ok": not broken_fires,
            "enabled_on_count": len(enabled_on),
            "enabled_off_count": len(enabled_off),
            "broken_count": len(broken),
        },
        {
            "id": "scratch-capture-complete",
            "fired_on_bad": capture_complete,
            "silent_on_good": bool(good.get("ok")),
            "pass": capture_complete and bool(good.get("ok")),
            "expect_rule": "declared-fields",
            "scratch_payload_count": scratch["payload_count"],
        },
    ]

    cred_out = json.dumps(cred, sort_keys=True)
    path_out = json.dumps(path, sort_keys=True)
    leaks = leak_needles_in(cred_out) + leak_needles_in(path_out)
    leaks += leak_needles_in(json.dumps(user, sort_keys=True))
    no_print = not leaks
    if not no_print:
        rows.append(
            {
                "id": "never-print-sensitive",
                "fired_on_bad": True,
                "silent_on_good": False,
                "pass": False,
                "leaks": leaks,
            }
        )
    else:
        rows.append(
            {
                "id": "never-print-sensitive",
                "fired_on_bad": True,
                "silent_on_good": True,
                "pass": True,
                "credential_fingerprint": value_fingerprint(credential_canary()),
            }
        )

    covered = {r["id"] for r in rows}
    missing_rules = [r for r in RULES if r not in covered]
    all_pass = all(r.get("pass") for r in rows) and not missing_rules
    return {
        "pass": all_pass,
        "rows": rows,
        "missing_rules": missing_rules,
        "conforming_ok": bool(good.get("ok")),
        "optin_positive_ok": bool(ok_optin.get("ok")),
        "checker_omits_sensitive_values": no_print,
    }


def live_payload_results(
    live: dict[str, Any], log_ids: set[str]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, row in enumerate(live.get("payloads") or []):
        payload = row.get("payload") if isinstance(row, dict) else row
        checked = check_payload(payload, decision_log_ids=log_ids)
        item = {
            "index": i,
            "source": row.get("source") if isinstance(row, dict) else "live",
            "ok": checked["ok"],
            "extra_fields": checked["extra_fields"],
            "credential_shaped_count": checked["credential_shaped_count"],
            "path_shaped_count": checked["path_shaped_count"],
            "user_content_count": checked["user_content_count"],
            "finding_rules": sorted(finding_rules(checked)),
        }
        out.append(item)
    return out


def measure() -> dict[str, Any]:
    log_ids = decision_ids(load_json(FIXTURES / "decision_log.json"))
    live = harvest_live()
    live_checked = live_payload_results(live, log_ids)
    live_violations = [row for row in live_checked if not row.get("ok")]
    controls = both_states(log_ids)

    harvest_cli = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/TST-0050/harvest.py --live"
    )
    suite_cli = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/TST-0050/suite.py --both-states"
    )
    field_cli = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/TST-0050/suite.py --live"
    )
    steps = []
    for sid, source, command in (
        (
            "load-declared-fields",
            "command-center/p2-wave/probes/TST-0050/contract.py",
            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import sys; sys.path.insert(0,'command-center/p2-wave/probes/TST-0050'); from contract import DECLARED_FIELDS; print(len(DECLARED_FIELDS))\"",
        ),
        (
            "harvest-live",
            "command-center/p2-wave/probes/TST-0050/harvest.py",
            harvest_cli,
        ),
        (
            "diff-live-payloads",
            "command-center/p2-wave/probes/TST-0050/suite.py",
            field_cli,
        ),
        (
            "both-states",
            "command-center/p2-wave/probes/TST-0050/suite.py",
            suite_cli,
        ),
    ):
        ran = run_cmd(command)
        classification = "ok" if ran["exit_code"] == 0 else "wrong-recipe"
        steps.append(
            {
                "id": sid,
                "source": source,
                "command": command,
                "exit_code": ran["exit_code"],
                "classification": classification,
                "status": "executed",
            }
        )

    core_ok = all(s.get("classification") == "ok" for s in steps) and bool(
        controls.get("pass")
    )
    return {
        "live": live,
        "live_canonical": canonical_live(live),
        "live_checked": live_checked,
        "live_violations": live_violations,
        "controls": controls,
        "steps": steps,
        "core_ok": core_ok and bool(controls.get("pass")),
        "decision_log_ids": sorted(log_ids),
    }


def public_control_rows(controls: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in controls.get("rows") or []:
        rows.append(
            {
                "id": row.get("id"),
                "fired_on_bad": bool(row.get("fired_on_bad")),
                "silent_on_good": bool(row.get("silent_on_good")),
                "pass": bool(row.get("pass")),
            }
        )
    return rows


def main() -> int:
    log_ids = decision_ids(load_json(FIXTURES / "decision_log.json"))
    if "--both-states" in sys.argv:
        controls = both_states(log_ids)
        printable = public_control_rows(controls)
        print(json.dumps(printable, sort_keys=True))
        print(
            f"pass={controls['pass']} conforming_ok={controls['conforming_ok']} "
            f"no_print={controls['checker_omits_sensitive_values']}"
        )
        if not controls.get("pass"):
            print(f"FAILED:{UNIT} both-states did not discriminate")
            return 1
        print(f"SUCCESS:{UNIT}-suite both-states discriminate")
        return 0
    if "--live" in sys.argv:
        live = canonical_live(harvest_live())
        print(json.dumps(live, sort_keys=True))
        print(f"SUCCESS:{UNIT}-suite live harvest")
        return 0
    measured = measure()
    print(json.dumps({"core_ok": measured["core_ok"]}, sort_keys=True))
    if not measured["core_ok"]:
        print(f"FAILED:{UNIT} suite core_ok is false")
        return 1
    print(f"SUCCESS:{UNIT}-suite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
