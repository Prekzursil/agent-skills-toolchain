#!/usr/bin/env python3
"""TST-0104 probe 2: emptying the allowlist puts agent-mail in the kill set.

Honest select_kill_set spares agent-mail. The same candidates under a
source mutation `PROTECTED_NAMES = frozenset()` select agent-mail for
KILL (naive no-session classifier). The mutation is not applied — a
wrong termination of the coordination channel is the failure class.
AST confirms the allowlist is consulted on the select path.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
SRC = LIB / "memory_guard" / "guard.py"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LIB))

from memory_guard.guard import (  # noqa: E402
    KILL,
    PROTECTED_NAMES,
    REASON_NO_SESSION,
    REASON_PROTECTED,
    SPARE,
    sample_pressure,
    select_kill_set,
)
from scenario import close_fixture, plant  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0104.json"
SENTINEL = "SUCCESS:TST-0104"
ALLOWLIST_LINE = 'PROTECTED_NAMES = frozenset({"agent-mail"})'
MUTANT_LINE = "PROTECTED_NAMES = frozenset()"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0104-probe2 {msg}")
    return 1


def check_receipt() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{doc.get('state')}"
    if SENTINEL not in text:
        return "sentinel-absent"
    return None


def ast_allowlist_is_load_bearing(tree: ast.AST) -> tuple[bool, str]:
    names_ok = False
    select_uses_constant = False
    reason_checks_on_list = False
    reason_has_no_session = False
    on_list_lineno = None
    no_session_lineno = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "PROTECTED_NAMES":
                    dump = ast.dump(node.value)
                    if "agent-mail" in dump or "agent-mail" in ast.dump(node):
                        names_ok = True
                    # Constant string inside the frozenset call.
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Constant) and sub.value == "agent-mail":
                            names_ok = True
        if isinstance(node, ast.FunctionDef) and node.name == "select_kill_set":
            used = {
                n.id
                for n in ast.walk(node)
                if isinstance(n, ast.Name)
            }
            if "PROTECTED_NAMES" in used:
                select_uses_constant = True
        if isinstance(node, ast.FunctionDef) and node.name == "_reason_for":
            for sub in ast.walk(node):
                if isinstance(sub, ast.If):
                    test = sub.test
                    if isinstance(test, ast.Name) and test.id == "on_list":
                        reason_checks_on_list = True
                        on_list_lineno = sub.lineno
                    if isinstance(test, ast.Compare):
                        dump = ast.dump(test)
                        if "session_id" in dump and "None" in dump:
                            reason_has_no_session = True
                            no_session_lineno = sub.lineno
    if not names_ok:
        return False, "PROTECTED_NAMES does not name agent-mail"
    if not select_uses_constant:
        return False, "select_kill_set does not consult PROTECTED_NAMES"
    if not reason_checks_on_list:
        return False, "_reason_for does not branch on on_list"
    if not reason_has_no_session:
        return False, "_reason_for has no no-session branch"
    if on_list_lineno is None or no_session_lineno is None:
        return False, "missing line numbers for allowlist vs no-session"
    if on_list_lineno >= no_session_lineno:
        return False, "allowlist check is not before the no-session KILL"
    return True, (
        f"allowlist-before-naive-orphan on_list@{on_list_lineno} "
        f"no_session@{no_session_lineno}"
    )


def main() -> int:
    err = check_receipt()
    if err:
        return fail(err)
    src = SRC.read_text(encoding="utf-8")
    ok, why = ast_allowlist_is_load_bearing(ast.parse(src))
    if not ok:
        return fail(why)
    if "agent-mail" not in PROTECTED_NAMES:
        return fail(f"runtime PROTECTED_NAMES={PROTECTED_NAMES}")
    if ALLOWLIST_LINE not in src:
        return fail("allowlist assignment not found for mutation")
    mutated = src.replace(ALLOWLIST_LINE, MUTANT_LINE, 1)
    if mutated == src:
        return fail("mutation did not change source; fingerprints would match")

    fix = plant()
    try:
        planted_rss = sum(c.rss_bytes for c in fix.candidates)
        pressure = sample_pressure(planted_rss_bytes=planted_rss)
        honest = select_kill_set(fix.candidates, pressure)
        mail_honest = honest.decision_for(int(fix.mail.pid))
        if mail_honest is None:
            return fail("honest log missing agent-mail")
        if mail_honest.action != SPARE or mail_honest.reason != REASON_PROTECTED:
            return fail(f"honest did not spare agent-mail: {mail_honest.to_dict()}")
        if int(fix.mail.pid) in honest.kill_set:
            return fail("honest kill set contains agent-mail")

        ns: dict[str, object] = {}
        exec(compile(mutated, "guard_mutant.py", "exec"), ns)
        mutant_select = ns["select_kill_set"]
        mutant_names = ns["PROTECTED_NAMES"]
        if mutant_names:
            return fail(f"mutant PROTECTED_NAMES not empty: {mutant_names}")
        mutant = mutant_select(fix.candidates, pressure)
        mail_mutant = mutant.decision_for(int(fix.mail.pid))
        if mail_mutant is None:
            return fail("mutant log missing agent-mail")
        if mail_mutant.action != KILL:
            return fail(
                f"empty allowlist did not KILL agent-mail: {mail_mutant.to_dict()}"
            )
        if mail_mutant.reason != REASON_NO_SESSION:
            return fail(f"mutant reason not naive-orphan: {mail_mutant.to_dict()}")
        if int(fix.mail.pid) not in mutant.kill_set:
            return fail("mutant kill set missing agent-mail")
        from memory_guard.guard import pid_exists as live_pid

        if not live_pid(int(fix.mail.pid)):
            return fail("agent-mail died during mutation probe; kills leaked")
        from scenario import wait_health

        status, body = wait_health(fix.health_url)
        if status != 200 or body.get("service") != "agent-mail":
            return fail(f"health died during mutation probe {status} {body}")

        payload = {
            "pass": True,
            "probe": "probe2-allowlist-mutation",
            "unit_id": "TST-0104",
            "ast_ok": True,
            "ast_why": why,
            "honest_mail_action": mail_honest.action,
            "honest_mail_reason": mail_honest.reason,
            "mutant_mail_action": mail_mutant.action,
            "mutant_mail_reason": mail_mutant.reason,
            "honest_kill_set_has_mail": False,
            "mutant_kill_set_has_mail": True,
            "mutant_applied": False,
            "health_status": status,
            "source_bytes": len(src.encode("utf-8")),
            "mutant_bytes": len(mutated.encode("utf-8")),
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            "honest_mail=SPARE mutant_mail=KILL mutant_applied=False "
            f"ast_ok=True {why}"
        )
        print(
            "SUCCESS:TST-0104-probe2 empty allowlist selects agent-mail; "
            "honest path spares it"
        )
        return 0
    finally:
        close_fixture(fix)


if __name__ == "__main__":
    raise SystemExit(main())
