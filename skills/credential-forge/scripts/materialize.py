#!/usr/bin/env python3
"""materialize.py -- credential-forge capability (3): 1Password vault SSOT +
forge-run env materialization.

forge-run  : resolves op://vault/item/field refs AND plain env names (os env,
             then winreg) into a CHILD process's environment at exec time,
             then execs. Values exist only in the child's env -- never in
             dotfiles, the skill tree, or logs. Prints resolved NAMES and
             lengths only.
vault-sync : pushes new harvests to the 1P vault via the op CLI
             (OP_CONNECT_* stripped inline in the env dict -- the estate
             gotcha: the op-personal bash wrapper is not exec-able from
             Windows python). NEVER force-migrates password-shaped vars:
             they are listed as candidates with a documented-exception path.

HONEST LIMIT (1password-ops/SKILL.md): only the 'Shared with Grok Bot' vault
is CLI-visible; the 9 fleet Login items are NOT. The vault is SSOT-of-record
while HKCU registry remains the materialized cache; roster entries carry
vault_sync: synced|blocked.

Examples:
  python materialize.py forge-run --env GROK_LANE_KEY -- python -c "print(1)"
  python materialize.py forge-run --env API=op://Vault/Item/field --dry -- cmd
  python materialize.py vault-sync
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _common as C  # noqa: E402

ROSTER = C.STATE_DIR / "roster.json"
OP_URI = re.compile(r"^op://[A-Za-z0-9 _.-]+/[A-Za-z0-9 _.-]+/[A-Za-z0-9 _.-]+$")
PASSWORD_SHAPED = re.compile(r"(?i)password|passwd")


def op_read(uri: str) -> str | None:
    """Resolve an op:// URI to its value IN MEMORY via the op CLI with
    OP_CONNECT_* stripped inline (Connect-mode bypass, one Windows Hello
    per unlock window). The value is never printed."""
    op = C.find_op()
    if op is None:
        print("FAIL: op CLI not found (vault lane degraded on this box)")
        return None
    try:
        proc = subprocess.run(
            [str(op), "read", "--no-newline", uri],
            env=C.op_base_env(),
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace").rstrip("\r\n")


def resolve_env_value(name: str) -> tuple[str | None, str]:
    """Plain env name: os env first, then winreg lanes. Value to memory only."""
    value = os.environ.get(name)
    if value is not None:
        return value, "process-env"
    for machine in (False, True):
        value = C.env_get_value(name, machine=machine)
        if value is not None:
            return value, "winreg-" + ("Machine" if machine else "User")
    return None, "missing"


def cmd_forge_run(args) -> int:
    cmd = list(args.command)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print(
            "FAIL: no command after -- (usage: forge-run [--env NAME]... -- <cmd...>)"
        )
        return 2
    child_env = dict(os.environ)
    resolved = 0
    for spec in args.env or []:
        if "=" in spec:
            name, ref = spec.split("=", 1)
        else:
            name, ref = spec, spec
        if OP_URI.match(ref):
            value = op_read(ref)
            source = "op://" if value is not None else "op://(FAILED)"
        else:
            value, source = resolve_env_value(ref)
        if value is None:
            print("FAIL: could not resolve %s (source %s)" % (name, source))
            return 1
        child_env[name] = value
        print("resolved %s <- %s (len=%d)" % (name, source, len(value)))
        resolved += 1
    # strip Connect-mode vars from the child only if it is not op itself
    if args.strip_connect:
        child_env = {
            k: v for k, v in child_env.items() if not k.startswith("OP_CONNECT_")
        }
    if args.dry:
        print("DRY: would exec %d resolved var(s); command not spawned" % resolved)
        return 0
    proc = subprocess.run(cmd, env=child_env)
    print("child exit=%d" % proc.returncode)
    return proc.returncode


def op_item_exists(op: pathlib.Path, title: str) -> bool:
    try:
        proc = subprocess.run(
            [str(op), "item", "get", title],
            env=C.op_base_env(),
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def cmd_vault_sync(args) -> int:
    roster = C.load_json(ROSTER)
    if not roster:
        print("no roster -- run: python roster.py sync first")
        return 1
    keys = roster.get("keys", [])
    migratable, manual_exception = [], []
    for key in keys:
        if PASSWORD_SHAPED.search(key["env_name"]):
            manual_exception.append(key["env_name"])
        elif key.get("vault_sync") != "synced":
            migratable.append(key)
    print("vault-sync candidates (non-password-shaped): %d" % len(migratable))
    for key in migratable[:12]:
        print("  candidate: %s (provider=%s)" % (key["env_name"], key["provider"]))
    print(
        "password-shaped vars held back (documented exception, NEVER force-migrated): %d"
        % len(manual_exception)
    )
    for name in manual_exception[:4]:
        print("  manual-exception: %s" % name)
    print(
        "vault visibility limit: only CLI-enabled vaults are writable; fleet Login items are NOT CLI-visible"
    )
    if args.dry or not args.apply:
        print("DRY: nothing written (pass --apply to create items)")
        return 0
    op = C.find_op()
    if op is None:
        print("FAIL: op CLI not found")
        return 1
    synced = 0
    for key in migratable:
        value, source = resolve_env_value(key["env_name"])
        if value is None:
            print("skip %s (no value via %s)" % (key["env_name"], source))
            continue
        if op_item_exists(op, key["env_name"]):
            print("idempotent: %s already in vault" % key["env_name"])
            key["vault_sync"] = "synced"
            key["vault_ref"] = "op://credential-forge/%s/password" % key["env_name"]
            synced += 1
            continue
        # NOTE (honest limit): op item create takes the field value via argv;
        # the value is process-visible for the call duration on this owner's
        # own box. See references/hygiene.md before changing this.
        try:
            proc = subprocess.run(
                [
                    str(op),
                    "item",
                    "create",
                    "--category=Password",
                    "--title",
                    key["env_name"],
                    "password=%s" % value,
                ],
                env=C.op_base_env(),
                capture_output=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            proc = None
        if proc is not None and proc.returncode == 0:
            key["vault_sync"] = "synced"
            key["vault_ref"] = "op://credential-forge/%s/password" % key["env_name"]
            synced += 1
            print("synced %s (len=%d)" % (key["env_name"], len(value)))
        else:
            print("blocked %s (vault not CLI-visible or op error)" % key["env_name"])
    C.atomic_json_write(ROSTER, roster)
    print("vault-sync done: synced=%d of %d candidates" % (synced, len(migratable)))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="materialize.py",
        description="forge-run (resolve op:// + env refs into a child env, then exec) and vault-sync",
        epilog="Values exist only in the child process environment / vault; never printed or written to disk.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("forge-run", help="resolve refs into child env and exec")
    p_run.add_argument(
        "--env",
        action="append",
        default=[],
        help="NAME or NAME=op://vault/item/field (repeatable)",
    )
    p_run.add_argument(
        "--strip-connect",
        action="store_true",
        help="strip OP_CONNECT_* from the child env",
    )
    p_run.add_argument(
        "--dry",
        action="store_true",
        help="resolve and print names/lengths; do not spawn",
    )
    p_run.add_argument("command", nargs=argparse.REMAINDER, help="command after --")
    p_vs = sub.add_parser("vault-sync", help="push roster env lanes into the 1P vault")
    p_vs.add_argument(
        "--dry",
        action="store_true",
        help="list candidates; write nothing (default behavior)",
    )
    p_vs.add_argument(
        "--apply", action="store_true", help="required for any live vault write"
    )
    args = ap.parse_args(argv)
    if args.cmd == "forge-run":
        return cmd_forge_run(args)
    if args.cmd == "vault-sync":
        return cmd_vault_sync(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
