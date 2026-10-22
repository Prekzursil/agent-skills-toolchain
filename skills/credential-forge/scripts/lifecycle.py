#!/usr/bin/env python3
"""lifecycle.py -- credential-forge capability (5a): expiry ledger + refresh
watchdog + bounded Scheduled Task registration.

ledger build : decodes exp claims OFFLINE (base64 payload split, no network).
               Every store's exp source is known from references/store-map.md
               (.grok expires_at RFC3339; .gemini expiry_date unix-ms +
               id_token JWT; .claude refreshTokenExpiresAt; .zcode derived
               from JWT values; AWS sso cache expiresAt). Emits
               days_to_expiry with expiring_soon thresholds at 7d/1d.
watchdog     : ONE bounded pass. Invokes PROVIDER-NATIVE refresh only -- the
               owning CLI refreshes its own store at runtime (mtimes verified
               2026-10-22). This discipline NEVER hand-rolls refresh POSTs to
               inferred endpoints (the stores research marked grok/zcode
               refresh endpoints as inference, not observation). Stores this
               box cannot refresh (cursor-agent STALE 09-02, opencode STALE
               04-27) are marked stale + alerted, not poked. Failures
               auto-quarantine in the roster with an alert -- never a 3am
               stack trace.
task install : registers Bounded Scheduled Tasks (ExecutionTimeLimit set,
               MultipleInstances IgnoreNew): the watchdog pass and the nightly
               hygiene audit gate (audit_secret_artifacts.py ... exit 2 =
               findings -> alert).

Examples:
  python lifecycle.py ledger build
  python lifecycle.py ledger show --store gemini
  python lifecycle.py watchdog --dry
  python lifecycle.py task install --dry
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _common as C  # noqa: E402
import harvest  # noqa: E402

LEDGER = C.STATE_DIR / "ledger.json"
ALERTS = C.STATE_DIR / "alerts.json"
WATCHDOG_LAST = C.STATE_DIR / "watchdog-last.txt"
LOCK = C.STATE_DIR / "watchdog.lock"
ROSTER = C.STATE_DIR / "roster.json"
ZTREE = HOME_TREE = pathlib.Path(os.environ.get("USERPROFILE", "")) / ".zcode" / "skills" / "credential-forge"
ATREE = pathlib.Path(os.environ.get("USERPROFILE", "")) / ".agents" / "skills" / "credential-forge"

EXPIRING_SOON_DAYS = 7.0
EXPIRED_DAYS = 0.0

# Provider-native refresh commands. Deliberately EMPTY by default: no store
# on this box has a verified safe NON-interactive refresh command. Add an
# entry ONLY when the owning CLI itself provides one (never a hand-rolled
# token POST against an inferred endpoint).
SAFE_REFRESH_CMDS: dict[str, list[str]] = {}


def load_ledger() -> dict:
    data = C.load_json(LEDGER) or {}
    data.setdefault("entries", [])
    return data


def build_entries(budget_deadline: float | None = None) -> list[dict]:
    entries = []
    for store_id, cfg in C.STORES.items():
        if budget_deadline is not None and time.monotonic() > budget_deadline:
            entries.append({"store": store_id, "account": "<budget-cut>",
                            "kind": "skipped", "expires_at": None,
                            "note": "watchdog budget reached"})
            continue
        info = None
        for p in ([*cfg.get("paths", []), *cfg.get("dbs", [])]):
            f = C.probe(p)
            if f:
                info = f
                break
        if info is None and not cfg.get("glob"):
            entries.append({"store": store_id, "account": "<store>",
                            "kind": "absent", "expires_at": None,
                            "liveness": "absent",
                            "refreshable_by_cli": cfg.get("refreshable_by_cli", False)})
            continue
        try:
            meta, _raw, notes = harvest.collect(store_id)
        except Exception as exc:  # noqa: BLE001
            meta = []
            notes = ["collect failed: %s %s" % (type(exc).__name__, str(exc)[:100])]
        if not meta:
            probe_info = info or {"mtime": None}
            entries.append({"store": store_id, "account": "<store>",
                            "kind": "probe-only", "expires_at": None,
                            "liveness": C.mtime_verdict(info),
                            "mtime": probe_info.get("mtime"),
                            "notes": notes[:3],
                            "refreshable_by_cli": cfg.get("refreshable_by_cli", False)})
            continue
        for m in meta:
            d = C.days_to(m.get("expires_at"))
            entry = {"store": store_id, "account": m.get("account"),
                     "kind": m.get("kind"),
                     "access_len": m.get("access_len", 0),
                     "refresh_len": m.get("refresh_len", 0),
                     "expires_at": m.get("expires_at"),
                     "days_to_expiry": d,
                     "liveness": C.mtime_verdict(info),
                     "mtime": info["mtime"] if info else None,
                     "issuer": m.get("issuer"),
                     "refreshable_by_cli": cfg.get("refreshable_by_cli", False)}
            if d is not None and d <= EXPIRED_DAYS:
                entry["status"] = "expired"
            elif d is not None and d <= EXPIRING_SOON_DAYS:
                entry["status"] = "expiring_soon"
            else:
                entry["status"] = "ok" if d is not None else "unknown-expiry"
            entries.append(entry)
    return entries


def cmd_ledger_build(args) -> int:
    entries = build_entries()
    ledger = {"schema_version": 1, "generated_at": C.now_iso(), "entries": entries}
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.get("status", "?")] = counts.get(e.get("status", "?"), 0) + 1
    print("ledger entries: %d (%s)" % (len(entries), json.dumps(counts, sort_keys=True)))
    if args.dry:
        print("DRY: ledger.json NOT written")
        return 0
    C.atomic_json_write(LEDGER, ledger)
    print("wrote: %s" % LEDGER)
    return 0


def cmd_ledger_show(args) -> int:
    ledger = load_ledger()
    rows = ledger.get("entries", [])
    if args.store:
        rows = [r for r in rows if r.get("store") == args.store]
    print("store            account                    status          days  expires_at")
    for r in sorted(rows, key=lambda x: (x.get("store", ""), x.get("account", ""))):
        print("%-16s %-26s %-14s %5s  %s" % (
            r.get("store", "?"), (r.get("account") or "?")[:26],
            r.get("status", "?"),
            "?" if r.get("days_to_expiry") is None else r.get("days_to_expiry"),
            r.get("expires_at") or "-"))
    if not rows:
        print("(no entries%s)" % (" for store %s" % args.store if args.store else ""))
        return 1
    return 0


# ---------------------------------------------------------------------------
# watchdog

def acquire_lock() -> bool:
    if LOCK.exists():
        try:
            data = json.loads(LOCK.read_text(encoding="utf-8"))
            age = time.time() - float(data.get("ts", 0))
        except (OSError, ValueError):
            age = 1e9
        if age < 30 * 60:
            print("watchdog: another pass holds the lock (age %.0fs) -- single-instance, exiting" % age)
            return False
        print("watchdog: stale lock (%.0fs) -- overriding" % age)
    C.atomic_json_write(LOCK, {"ts": time.time(), "pid": os.getpid()})
    return True


def release_lock() -> None:
    try:
        LOCK.unlink()
    except OSError:
        pass


def cmd_watchdog(args) -> int:
    budget_deadline = time.monotonic() + (args.budget_seconds if args.budget_seconds else 300)
    if not acquire_lock():
        return 0
    try:
        entries = build_entries(budget_deadline)
        if not args.dry:
            C.atomic_json_write(LEDGER, {"schema_version": 1, "generated_at": C.now_iso(),
                                         "entries": entries})
        alerts = []
        for e in entries:
            store, status = e.get("store"), e.get("status")
            # store-map liveness rule: research-flagged STALE stores that this
            # box cannot refresh are marked stale + alerted, not poked.
            research_stale = str(C.STORES.get(store, {}).get("design_status", "")).startswith("STALE")
            if research_stale and not e.get("refreshable_by_cli"):
                e["status"] = "stale-research"
                e["quarantined"] = True
                print("watchdog: %s/%s research-flagged STALE -> stale-quarantine (marked, not poked)"
                      % (store, e.get("account")))
                alerts.append({"store": store, "account": e.get("account"),
                               "status": "stale-research", "action": "stale-quarantine",
                               "expires_at": e.get("expires_at")})
                continue
            if status in ("expired", "expiring_soon"):
                if e.get("refreshable_by_cli"):
                    # provider-native doctrine: the OWNING CLI refreshes its own
                    # store at runtime; we never POST. Owner action is to run
                    # the CLI once (capture.py hand-off lanes exist for this).
                    action = "owner-run-owning-cli"
                    if args.apply_refresh and store in SAFE_REFRESH_CMDS:
                        cmd = SAFE_REFRESH_CMDS[store]
                        print("watchdog: provider-native refresh for %s: %s" % (store, " ".join(cmd)))
                        try:
                            proc = subprocess.run(cmd, timeout=60, capture_output=True)
                            print("watchdog: refresh rc=%d" % proc.returncode)
                        except (OSError, subprocess.TimeoutExpired) as exc:
                            print("watchdog: refresh failed: %s" % type(exc).__name__)
                    else:
                        print("watchdog: %s/%s %s -> %s (no hand-rolled POSTs; SAFE_REFRESH_CMDS=%s)"
                              % (store, e.get("account"), status, action,
                                 "empty" if not SAFE_REFRESH_CMDS else "configured"))
                else:
                    action = "stale-quarantine"
                    e["quarantined"] = True
                    print("watchdog: %s/%s %s -> %s (unrefreshable on this box; marked, not poked)"
                          % (store, e.get("account"), status, action))
                alerts.append({"store": store, "account": e.get("account"),
                               "status": status, "action": action,
                               "expires_at": e.get("expires_at")})
        if not args.dry:
            C.atomic_json_write(ALERTS, {"generated_at": C.now_iso(), "alerts": alerts})
            # quarantine propagation into roster store_entries (names only)
            roster = C.load_json(ROSTER)
            if roster:
                dirty = False
                flagged = {(a["store"], a["account"]) for a in alerts if a["action"] == "stale-quarantine"}
                for se in roster.get("store_entries", []):
                    if (se.get("store"), se.get("account")) in flagged:
                        se["status"] = "quarantined"
                        dirty = True
                if dirty:
                    C.atomic_json_write(ROSTER, roster)
                    print("watchdog: roster store_entries quarantined (names only)")
        # statusline segment hand-off
        dated = [e["days_to_expiry"] for e in entries if e.get("days_to_expiry") is not None]
        segment = "forge:%dkeys exp:%sd" % (len(entries), int(min(dated)) if dated else "?")
        if alerts:
            segment += " alerts:%d" % len(alerts)
        if args.dry:
            print("DRY: %s (ledger.json, watchdog-last.txt, alerts.json NOT written)" % segment)
        else:
            WATCHDOG_LAST.write_text(segment + "\n", encoding="utf-8")
            print("watchdog pass done: %s" % segment)
        print("alerts: %d (details: %s)" % (len(alerts), ALERTS))
        return 0
    finally:
        release_lock()


# ---------------------------------------------------------------------------
# bounded Scheduled Task registration (ExecutionTimeLimit + single-instance)

TASK_WATCHDOG = "CredentialForgeWatchdog"
TASK_HYGIENE = "CredentialForgeHygiene"


def _ps_settings(minutes: int) -> str:
    return ("New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes %d) "
            "-MultipleInstances IgnoreNew -StartWhenAvailable" % minutes)


def task_commands() -> list[tuple[str, str]]:
    py = sys.executable or "python"
    lc = str(pathlib.Path(__file__).resolve())
    actions = [
        (TASK_WATCHDOG,
         "Register-ScheduledTask -TaskName '%s' -Action (New-ScheduledTaskAction -Execute '%s' "
         "-Argument '\"%s\" watchdog') -Trigger (New-ScheduledTaskTrigger -Daily -At 08:00) "
         "-Settings (%s) -Principal (New-ScheduledTaskPrincipal -UserId \"$env:USERNAME\" -LogonType Interactive)"
         % (TASK_WATCHDOG, py, lc, _ps_settings(20))),
        (TASK_HYGIENE,
         "Register-ScheduledTask -TaskName '%s' -Action (New-ScheduledTaskAction -Execute '%s' "
         "-Argument '\"%s\" \"%s\" \"%s\" \"%s\" --rotation-manifest \"%s\" --report \"%s\"') "
         "-Trigger (New-ScheduledTaskTrigger -Daily -At 03:30) -Settings (%s) "
         "-Principal (New-ScheduledTaskPrincipal -UserId \"$env:USERNAME\" -LogonType Interactive)"
         % (TASK_HYGIENE, py, str(C.AUDIT_SCRIPT), str(ATREE), str(ZTREE), str(C.STATE_DIR),
            str(C.STATE_DIR / "rotation-manifest.json"), str(C.STATE_DIR / "last-audit.json"),
            _ps_settings(15))),
    ]
    return actions


def cmd_task(args) -> int:
    if args.task_cmd == "install":
        for name, ps in task_commands():
            print("task %s:" % name)
            print("  powershell -NoProfile -Command %s" % ps)
        if args.dry or not args.apply:
            print("DRY: tasks NOT registered (pass --apply; ExecutionTimeLimit + IgnoreNew are in the settings above)")
            return 0
        rc = 0
        for name, ps in task_commands():
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                  capture_output=True, timeout=120)
            print("  %s register rc=%d %s" % (name, proc.returncode,
                                              proc.stderr.decode("utf-8", "replace").strip()[:120]))
            rc |= proc.returncode
        return rc
    if args.task_cmd == "remove":
        names = (TASK_WATCHDOG, TASK_HYGIENE)
        for name in names:
            print("task %s: Unregister-ScheduledTask -TaskName %s -Confirm:$false" % (name, name))
        if args.dry or not args.apply:
            print("DRY: tasks NOT removed")
            return 0
        rc = 0
        for name in names:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Unregister-ScheduledTask -TaskName '%s' -Confirm:$false" % name],
                capture_output=True, timeout=60)
            print("  %s remove rc=%d" % (name, proc.returncode))
            rc |= proc.returncode
        return rc
    if args.task_cmd == "show":
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-ScheduledTask -TaskName '%s','%s' | Select-Object TaskName,State | Format-Table -HideTableHeaders"
             % (TASK_WATCHDOG, TASK_HYGIENE)],
            capture_output=True, timeout=60)
        print(proc.stdout.decode("utf-8", "replace").strip() or "(no credential-forge tasks registered)")
        return 0
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="lifecycle.py",
        description="expiry ledger (offline JWT/exp decode) + bounded single-instance watchdog + schtask wiring",
    )
    sub = ap.add_subparsers(dest="group", required=True)
    p_ledger = sub.add_parser("ledger", help="expiry ledger operations")
    led_sub = p_ledger.add_subparsers(dest="cmd", required=True)
    p_lb = led_sub.add_parser("build", help="rebuild state/ledger.json from all mapped stores")
    p_lb.add_argument("--dry", action="store_true", help="print summary; write nothing")
    p_ls = led_sub.add_parser("show", help="print the ledger table (names/dates only)")
    p_ls.add_argument("--store", help="filter by store id")
    p_ls.add_argument("--dry", action="store_true", help="no-op for symmetry; show never writes")
    p_wd = sub.add_parser("watchdog", help="one bounded pass: mark/alert/quarantine; provider-native refresh only")
    p_wd.add_argument("--dry", action="store_true", help="run detection but skip watchdog-last.txt write")
    p_wd.add_argument("--apply-refresh", action="store_true",
                      help="allow provider-native refresh commands (SAFE_REFRESH_CMDS; empty by default)")
    p_wd.add_argument("--budget-seconds", type=int, default=300, help="wall-clock budget for the pass (default 300)")
    p_tk = sub.add_parser("task", help="manage the bounded Scheduled Tasks (watchdog + nightly hygiene audit)")
    p_tk.add_argument("task_cmd", choices=["install", "remove", "show"])
    p_tk.add_argument("--dry", action="store_true", help="print the exact PowerShell; change nothing")
    p_tk.add_argument("--apply", action="store_true", help="required for any live task change")
    args = ap.parse_args(argv)
    if args.group == "ledger":
        if args.cmd == "build":
            return cmd_ledger_build(args)
        if args.cmd == "show":
            return cmd_ledger_show(args)
        return 2
    if args.group == "watchdog":
        return cmd_watchdog(args)
    if args.group == "task":
        return cmd_task(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
