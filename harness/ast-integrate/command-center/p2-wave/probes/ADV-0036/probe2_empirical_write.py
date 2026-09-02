#!/usr/bin/env python3
"""Probe 2: empirical non-elevated write, mechanically different from icacls text.

Uses the DACL engine's access_check (canonical deny/allow order, parent
replace) plus a POSIX analog run as uid 65534. Does not modify product ACLs.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from layout import deployed_nodes, product_stat_snapshot  # noqa: E402
from lib_acl import (  # noqa: E402
    NON_ELEVATED_SIDS,
    can_replace_via_parent,
    can_write_data,
    consumer_sshd_admin_keys,
    naive_broad_writable,
    render_icacls,
    self_test,
)

OUT = HERE / "probe2-empirical-write.raw.json"
UID = "ADV-0036"
NOBODY = 65534


def empirical_row(node) -> dict:
    token = NON_ELEVATED_SIDS
    inplace = can_write_data(node.sd, token)
    replace = can_replace_via_parent(node.sd, token)
    consumer = consumer_sshd_admin_keys(node.sd)
    text = render_icacls(node.sd)
    naive = naive_broad_writable(text)
    return {
        "id": node.node_id,
        "role": node.role,
        "control": node.control,
        "win_path": node.sd.path,
        "source_rel": node.source_rel,
        "non_elevated_inplace_write": inplace,
        "non_elevated_replace_via_parent": replace,
        "non_elevated_effective_write": bool(inplace or replace),
        "naive_textual_broad": naive,
        "textual_vs_empirical_diverge": bool(naive) != bool(inplace),
        "sshd_consumer": consumer,
        "note": node.note,
    }


def _try_write_as_nobody(path: str) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os,sys\n"
                "p=sys.argv[1]\n"
                "try:\n"
                " fd=os.open(p, os.O_WRONLY|os.O_APPEND)\n"
                " os.write(fd, b'x')\n"
                " os.close(fd)\n"
                " print('OK')\n"
                "except OSError as e:\n"
                " print('ERR', e.errno)\n"
                " sys.exit(1)\n"
            ),
            path,
        ],
        user=NOBODY,
        group=NOBODY,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def posix_analog() -> dict:
    """Known-protected must reject; known user-owned must accept.

    Runs as uid 65534 so root bypass of mode bits is not credited.
    Fixture files only; product paths are not chmod'd.
    """
    td = tempfile.mkdtemp(prefix="adv0036-posix-")
    prot = os.path.join(td, "protected")
    user = os.path.join(td, "userowned")
    try:
        with open(prot, "w", encoding="utf-8") as fh:
            fh.write("protected\n")
        with open(user, "w", encoding="utf-8") as fh:
            fh.write("user\n")
        os.chmod(td, 0o755)  # mkdtemp is 0700; nobody must be able to traverse
        os.chmod(prot, 0o444)
        os.chown(user, NOBODY, NOBODY)
        os.chmod(user, 0o644)
        p = _try_write_as_nobody(prot)
        u = _try_write_as_nobody(user)
        return {
            "temp_dir": td,
            "protected_mode": oct(os.stat(prot).st_mode & 0o777),
            "user_mode": oct(os.stat(user).st_mode & 0o777),
            "protected_write": p,
            "user_write": u,
            "protected_rejected": not p["ok"],
            "user_accepted": u["ok"],
            "ok": (not p["ok"]) and u["ok"],
            "ran_as_uid": NOBODY,
        }
    finally:
        shutil.rmtree(td, ignore_errors=True)


def snapshots_equal(a: dict, b: dict) -> bool:
    return a == b


def main() -> int:
    engine = self_test()
    before = product_stat_snapshot()
    rows = [empirical_row(n) for n in deployed_nodes()]
    posix = posix_analog()
    after = product_stat_snapshot()
    unchanged = snapshots_equal(before, after)

    protected = next(r for r in rows if r["control"] == "protected")
    user_owned = next(r for r in rows if r["control"] == "user-owned")
    trap = next(r for r in rows if r["control"] == "inherited-deny-trap")
    everyone = next(r for r in rows if r["control"] == "planted-everyone-write")
    override = next(
        r for r in rows if r["control"] == "explicit-allow-over-inherited-deny"
    )
    replace = next(r for r in rows if r["control"] == "replace-via-parent")
    pf = [r for r in rows if r["id"].endswith("programfiles")]

    protected_ok = (
        not protected["non_elevated_inplace_write"]
        and not protected["non_elevated_replace_via_parent"]
        and not protected["sshd_consumer"]["reject"]
    )
    user_ok = user_owned["non_elevated_inplace_write"]
    trap_ok = (
        trap["naive_textual_broad"]
        and not trap["non_elevated_inplace_write"]
        and trap["textual_vs_empirical_diverge"]
    )
    everyone_ok = (
        everyone["non_elevated_inplace_write"]
        and everyone["sshd_consumer"]["reject"]
    )
    override_ok = override["non_elevated_inplace_write"]
    replace_ok = (
        not replace["non_elevated_inplace_write"]
        and replace["non_elevated_replace_via_parent"]
    )
    pf_ok = all(not r["non_elevated_effective_write"] for r in pf)

    ok = (
        engine["ok"]
        and protected_ok
        and user_ok
        and trap_ok
        and everyone_ok
        and override_ok
        and replace_ok
        and pf_ok
        and posix["ok"]
        and unchanged
    )
    report = {
        "probe": "probe2-empirical-write",
        "unit_id": UID,
        "pass": ok,
        "computed_not_asserted": True,
        "engine_self_test": engine,
        "instrument": "dacl-access-check-plus-posix-nobody-write",
        "acl_modified": False,
        "product_acl_unchanged": unchanged,
        "product_snapshot_before": before,
        "product_snapshot_after": after,
        "posix_analog": {
            k: posix[k]
            for k in (
                "protected_mode",
                "user_mode",
                "protected_write",
                "user_write",
                "protected_rejected",
                "user_accepted",
                "ok",
                "ran_as_uid",
            )
        },
        "controls": {
            "protected_rejects": protected_ok,
            "user_owned_accepts": user_ok,
            "inherited_deny_diverges": trap_ok,
            "everyone_write_and_sshd_reject": everyone_ok,
            "explicit_allow_over_inherited_deny": override_ok,
            "replace_via_parent": replace_ok,
            "program_files_not_effectively_writable": pf_ok,
            "posix_analog": posix["ok"],
            "no_product_acl_mutation": unchanged,
        },
        "rows": rows,
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "probe", "unit_id", "pass", "acl_modified", "product_acl_unchanged",
        "controls",
    )}, sort_keys=True))
    print(
        f"protected_ok={protected_ok} user_ok={user_ok} trap_ok={trap_ok} "
        f"posix={posix['ok']} unchanged={unchanged} replace_ok={replace_ok}"
    )
    if ok:
        print(
            "SUCCESS:ADV-0036-probe2 empirical non-elevated write; "
            "controls held; no ACL modified"
        )
        return 0
    print("FAILED:ADV-0036-probe2 empirical controls did not hold")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
