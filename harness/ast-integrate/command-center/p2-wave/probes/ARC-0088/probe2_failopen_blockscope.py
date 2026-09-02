#!/usr/bin/env python3
"""Probe 2: fail-open and block-scope (independent of probe 1).

Raise inside a hook => session continues with process exit 0.
A non-dangerous condition cannot produce exit 2.
A genuine irreversible-danger claim on PreToolUse still can (both-states).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import dispatch as D  # noqa: E402
import harness as H  # noqa: E402

OUT = HERE / "probe2-failopen-blockscope.raw.json"
CONTRACT = REPO / "command-center/phase4/contracts/ARC-0088.json"


def load_contract() -> dict | None:
    if not CONTRACT.is_file() or CONTRACT.stat().st_size <= 0:
        return None
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def check_contract(doc: dict) -> list[str]:
    errs: list[str] = []
    if "SUCCESS:ARC-0088" not in json.dumps(doc):
        errs.append("sentinel")
    exits = doc.get("exit_code_semantics") or {}
    if exits.get("exit_2_reserved_for") != "irreversible_danger_only":
        errs.append("exit-2-not-reserved")
    inj = doc.get("inject_do_not_block") or {}
    if inj.get("cannot_produce_exit_2") is not True:
        errs.append("inject-can-block")
    fo = doc.get("fail_open") or {}
    if fo.get("session_continues") is not True or fo.get("process_exit") != 0:
        errs.append("fail-open-not-declared")
    timeout = doc.get("timeout") or {}
    if timeout.get("process_exit") != 0:
        errs.append("timeout-not-fail-open")
    if int(timeout.get("default_ms") or 0) != D.TIMEOUT_MS_DEFAULT:
        errs.append("timeout-default-diverges")
    if list((doc.get("exit_code_semantics") or {}).get("irreversible_danger_classes") or []) != list(
        D.IRREVERSIBLE_DANGER_CLASSES
    ):
        # optional field; only check if present
        extra = (doc.get("exit_code_semantics") or {}).get("irreversible_danger_classes")
        if extra is not None and set(extra) != set(D.IRREVERSIBLE_DANGER_CLASSES):
            errs.append("danger-classes-diverge")
    return errs


def fire_script(body: str, event: str, *, timeout_ms: int = 5000) -> dict:
    with tempfile.TemporaryDirectory(prefix="arc0088-p2-") as tmp:
        root = Path(tmp)
        script = H.write_script(root / "hooks" / "hook.py", body)
        spec = H.spec_for("hook.case", event, script, timeout_ms=timeout_ms)
        manifest = H.write_manifest(root / "manifest.json", [spec])
        extra = {}
        if event in D.EVENT_EXTRA_FIELDS:
            extra = D.default_stdin(event, str(root))
        else:
            extra = D.default_stdin("PreToolUse", str(root))
        payload = extra
        payload["hook_event_name"] = event
        return D.fire_event(manifest, payload, root / "run", "hook.case")


def main() -> int:
    raised = fire_script(H.RAISE_HOOK, "PreToolUse")
    nonzero = fire_script(H.NONZERO_HOOK, "UserPromptSubmit")
    style = fire_script(H.STYLE_BLOCK_HOOK, "PreToolUse")
    danger = fire_script(H.DANGER_BLOCK_HOOK, "PreToolUse")
    timeout = fire_script(H.SLOW_HOOK, "Notification", timeout_ms=200)

    errs: list[str] = []
    if raised["process_exit"] != 0 or raised["session_continue"] is not True:
        errs.append("raise-did-not-fail-open")
    if raised["blocked"] is True:
        errs.append("raise-blocked")
    if not (raised.get("fail_open_reason") or "").startswith("hook-nonzero-exit"):
        # Python uncaught exception typically exits 1
        if raised["raw_exit"] not in {1, None} and raised["process_exit"] != 0:
            errs.append(f"raise-raw={raised['raw_exit']}")
    if nonzero["process_exit"] != 0 or nonzero["session_continue"] is not True:
        errs.append("nonzero-did-not-fail-open")
    if nonzero["blocked"] is True:
        errs.append("nonzero-blocked")

    if style["process_exit"] == 2 or style["blocked"] is True:
        errs.append("style-warning-produced-exit-2")
    if style["session_continue"] is not True:
        errs.append("style-warning-stopped-session")
    if not style.get("block_refused_reason"):
        errs.append("style-warning-not-refused")

    if danger["process_exit"] != 2 or danger["blocked"] is not True:
        errs.append("irreversible-danger-did-not-block")
    if danger["session_continue"] is not False:
        errs.append("irreversible-danger-session-continued")

    if timeout["timeout"] is not True:
        errs.append("slow-hook-not-timed-out")
    if timeout["process_exit"] != 0 or timeout["session_continue"] is not True:
        errs.append("timeout-did-not-fail-open")

    doc = load_contract()
    contract_checked = False
    if doc is not None:
        contract_checked = True
        errs.extend(check_contract(doc))

    payload = {
        "probe": "probe2-failopen-blockscope",
        "unit_id": "ARC-0088",
        "raise_exit": raised["process_exit"],
        "raise_continue": raised["session_continue"],
        "style_exit": style["process_exit"],
        "style_blocked": style["blocked"],
        "danger_exit": danger["process_exit"],
        "danger_blocked": danger["blocked"],
        "timeout_fail_open": timeout["process_exit"] == 0 and timeout["timeout"] is True,
        "contract_checked": contract_checked,
        "errors": errs,
        "pass": not errs,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"raise_exit={raised['process_exit']} raise_continue={raised['session_continue']} "
        f"style_exit={style['process_exit']} style_blocked={style['blocked']} "
        f"danger_exit={danger['process_exit']} danger_blocked={danger['blocked']} "
        f"timeout={timeout['timeout']} timeout_exit={timeout['process_exit']} "
        f"contract_checked={contract_checked}"
    )
    if errs:
        print("FAILED:ARC-0088-probe2 " + "; ".join(errs[:8]))
        return 1
    print("SUCCESS:ARC-0088-probe2 fail-open and block-scope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
