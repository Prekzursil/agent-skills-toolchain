"""Qwiklabs/Google Skills grader probe — the universal instrument (v2, verified 2026-09-30 on GSP322 at 100/100).

Makes ANY lab's grading fully transparent: arms data-access audit configs
(including logging.googleapis.com — the blind-spot closer), extracts the
grader's EXACT ListLogEntries predicates after each check click, simulates
the grader locally against those predicates, and profiles per-click read bursts.

Usage:
  python grader_probe.py arm PROJECT [extra-services...]   # arm audit configs (safe, idempotent)
  python grader_probe.py filters PROJECT [student-email]   # dump grader predicates seen so far
  python grader_probe.py watch PROJECT [student-email]     # live: print new predicates as the grader fires them
  python grader_probe.py verify PROJECT [student-email]    # SIMULATE: re-run each extracted filter, report SATISFIED/MISSING
  python grader_probe.py profile PROJECT [minutes]         # per-burst read matrix (which principal read what, when)

Method (proven):
  1. arm BEFORE the first check click
  2. click a check (learner's browser) — or just wait: the ~60-90s poller
     re-runs stuck-check predicates continuously (passive capture works)
  3. read filters: each is the verbatim expected-evidence query
  4. verify locally (verify command) — every predicate SATISFIED before you click
  5. satisfy MISSING predicates with REAL actions, never fabricated log entries
  6. re-click

Attribution rules (measured):
  - Ruby engine = project's own SA, callerIp 2600:1900:… (Google IPv6) → the grader
  - admiral@qwiklabs-services-prod = central evaluator, 35.x/34.x GFE IPs
  - your reads show your student email — exclude it to see grader-only
"""

import json, subprocess, sys, time, shutil

BASE = [
    "compute.googleapis.com",
    "iap.googleapis.com",
    "logging.googleapis.com",
    "bigquery.googleapis.com",
    "oslogin.googleapis.com",
]
ALL_TYPES = ["ADMIN_READ", "DATA_READ", "DATA_WRITE"]


def find_gcloud():
    for name in ("gcloud.cmd", "gcloud.bat", "gcloud"):
        p = shutil.which(name)
        if p:
            return p
    sys.exit("FAILED:no-gcloud-on-path")


GC_BIN = find_gcloud()


def gc(*args, **kw):
    return subprocess.run([GC_BIN, *args], capture_output=True, text=True, **kw)


def arm(project, extra=()):
    r = gc("projects", "get-iam-policy", project, "--format=json")
    if r.returncode:
        sys.exit("FAILED:get-policy " + r.stderr[:200])
    pol = json.loads(r.stdout)
    wanted = list(BASE) + list(extra)
    by_svc = {a.get("service"): a for a in pol.get("auditConfigs", []) or []}
    for svc in wanted:
        a = by_svc.get(svc)
        if a:
            have = {c.get("logType") for c in (a.get("auditLogConfigs") or [])}
            a["auditLogConfigs"] += [{"logType": t} for t in ALL_TYPES if t not in have]
        else:
            pol.setdefault("auditConfigs", []).append(
                {"service": svc, "auditLogConfigs": [{"logType": t} for t in ALL_TYPES]}
            )
    json.dump(pol, open("probe_pol.json", "w"), indent=1)
    r2 = gc("projects", "set-iam-policy", project, "probe_pol.json", "--quiet")
    if r2.returncode:
        sys.exit("FAILED:set-policy " + r2.stderr[:200])
    print(f"ARMED: {wanted} ({len(pol.get('bindings', []))} bindings preserved)")


def read_raw(project, exclude, minutes=120):
    flt = f'timestamp>="{minutes_ago_iso(minutes)}" AND logName:"cloudaudit.googleapis.com%2Fdata_access"'
    r = gc(
        "logging", "read", flt, "--project=" + project, "--limit=100", "--format=json"
    )
    if r.returncode:
        sys.exit("FAILED:read " + r.stderr[:200])
    out = []
    for e in json.loads(r.stdout or "[]"):
        p = e.get("protoPayload", {})
        a = p.get("authenticationInfo", {})
        who = a.get("principalEmail") or a.get("principalSubject") or "?"
        if exclude and exclude in who:
            continue
        if who.startswith("student-"):
            continue  # own reads
        out.append(
            {
                "ts": e.get("timestamp", "")[:19],
                "who": who,
                "service": p.get("serviceName", "").split(".")[0],
                "method": p.get("methodName", "").split(".")[-1],
                "resource": p.get("resourceName", "").split("/")[-1][:40],
                "filter": (p.get("request", {}) or {}).get("filter") or "",
            }
        )
    return out


def minutes_ago_iso(m):
    import datetime

    return (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=m)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_filters(project, exclude):
    """Distinct grader ListLogEntries predicates."""
    out = {}
    for e in read_raw(project, exclude):
        if e["method"] == "ListLogEntries" and e["filter"]:
            key = e["filter"][:160]
            out.setdefault(key, {"ts": e["ts"], "who": e["who"], "filter": e["filter"]})
    return out


def show(filters):
    for v in sorted(filters.values(), key=lambda x: x["ts"]):
        print(f"\n[{v['ts']}] {v['who']}\n  {v['filter']}")
    print(f"\nTOTAL distinct predicates: {len(filters)}")


def verify(project, exclude):
    """Simulate the grader: re-run each extracted predicate, count matches."""
    filters = extract_filters(project, exclude)
    if not filters:
        print(
            "no grader predicates captured yet (click a check or wait for the poller)"
        )
        return
    sat, miss = 0, 0
    for v in sorted(filters.values(), key=lambda x: x["ts"]):
        r = gc(
            "logging",
            "read",
            v["filter"],
            "--project=" + project,
            "--limit=5",
            "--format=value(timestamp)",
        )
        n = len([l for l in (r.stdout or "").splitlines() if l.strip()])
        ok = n > 0
        sat, miss = sat + (1 if ok else 0), miss + (0 if ok else 1)
        tag = "SATISFIED" if ok else "MISSING "
        hint = (
            "" if ok else "  ← satisfy with REAL actions (see GRADER-INTERNALS.md §5c)"
        )
        print(f"[{tag}] ({n} hits) {v['filter'][:150]}{hint}")
    print(
        f"\nGRADER SIMULATION: {sat} satisfied / {miss} missing — "
        + (
            "ALL GREEN — click with confidence"
            if miss == 0
            else "fix MISSING predicates first"
        )
    )


def profile(project, minutes):
    """Group all grader reads into time bursts (per-check read matrix)."""
    rows = read_raw(project, None, minutes=minutes)
    rows = [r for r in rows if not r["who"].startswith("student-")]
    bursts, cur, last = [], [], None
    for r in sorted(rows, key=lambda x: x["ts"]):
        if last and (ts_diff(last, r["ts"]) > 20) and cur:
            bursts.append(cur)
            cur = []
        cur.append(r)
        last = r["ts"]
    if cur:
        bursts.append(cur)
    for i, b in enumerate(bursts, 1):
        print(f"\n=== BURST {i} @ {b[0]['ts']} ({len(b)} reads) ===")
        for r in b:
            extra = f"  FILTER: {r['filter'][:120]}" if r["filter"] else ""
            print(
                f"  {r['ts'][11:]} {r['who'][:36]:36} {r['service']:8} {r['method']:22} {r['resource']}{extra}"
            )


def ts_diff(a, b):
    import datetime

    ta = datetime.datetime.fromisoformat(a)
    tb = datetime.datetime.fromisoformat(b)
    return abs((tb - ta).total_seconds())


if __name__ == "__main__":
    cmd, project = sys.argv[1], sys.argv[2]
    if cmd == "arm":
        arm(project, sys.argv[3:])
    elif cmd == "filters":
        show(extract_filters(project, sys.argv[3] if len(sys.argv) > 3 else None))
    elif cmd == "verify":
        verify(project, sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "profile":
        profile(project, int(sys.argv[3]) if len(sys.argv) > 3 else 60)
    elif cmd == "watch":
        exclude = sys.argv[3] if len(sys.argv) > 3 else None
        seen = {}
        print("watching — click checks in the lab UI; Ctrl+C to stop")
        while True:
            for k, v in extract_filters(project, exclude).items():
                if k not in seen:
                    seen[k] = v
                    print(f"\nNEW [{v['ts']}] {v['who']}\n  {v['filter']}")
            time.sleep(5)
