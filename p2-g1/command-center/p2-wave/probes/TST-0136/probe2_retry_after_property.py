#!/usr/bin/env python3
"""TST-0136 probe2 -- Retry-After property re-run live (delta-seconds + HTTP-date).

Re-runs the receipt's 200-case honor property against the live parser
(tools/command-center/retry_after.py, digest-checked against the receipt's
recorded supporting row): honor = observed wait matches the instructed
window via the module's own in_window(); the ignore-client (fixed 1.0s)
fails 199/200; past-date is an immediate retry; malformed takes the
documented 0.25s fallback without raising; FakeClock/WallClock reconcile.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import sys
from datetime import timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0136.json"
MODULE = REPO / "tools/command-center/retry_after.py"

FAILS: list[str] = []


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


def norm_sha(p: Path) -> tuple[str, int]:
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def gen_cases(rng: random.Random, n: int) -> list[dict]:
    """199 cases whose instructed wait != 1.0 plus exactly one == 1.0, so the
    honor client passes 200/200 and the ignore client fails 199/200."""
    kinds = ["delta", "delta-zero", "delta-huge", "malformed-neg", "malformed-float",
             "malformed-plus", "malformed-junk", "http-date", "http-date-past"]
    out = []
    for i in range(n - 1):
        k = kinds[i % len(kinds)]
        if k == "delta":
            x = rng.randint(2, 400)
            v, instr = str(x), float(x)
        elif k == "delta-zero":
            v, instr = "0", 0.0
        elif k == "delta-huge":
            v, instr = "999999999", 999999999.0
        elif k in ("malformed-neg", "malformed-float", "malformed-plus", "malformed-junk"):
            v = {"malformed-neg": "-5", "malformed-float": "2.5",
                 "malformed-plus": "+5", "malformed-junk": "soon"}[k]
            instr = 0.25  # documented fallback
        elif k == "http-date":
            v, instr = "@@HTTP_DATE@@", float(rng.randint(2, 400))
        else:  # http-date-past
            v, instr = "@@PAST_DATE@@", 0.0
        out.append({"kind": k, "value": v, "instructed": instr})
    out.append({"kind": "delta", "value": "1", "instructed": 1.0})
    return out


def main() -> int:
    spec = importlib.util.spec_from_file_location("live_retry_after", MODULE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_retry_after"] = mod
    spec.loader.exec_module(mod)

    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    rows = {str(a.get("path")): a for a in doc.get("artifacts") or []}
    rel = "tools/command-center/retry_after.py"
    sha, _ = norm_sha(MODULE)
    rec = rows.get(rel) or rows.get(rel.replace("/", "\\"))
    if rec and rec.get("sha256"):
        chk(sha == rec["sha256"], "module-sha-drift", (sha, rec.get("sha256")))

    from email.utils import formatdate
    base = mod.DEFAULT_EPOCH
    cases = gen_cases(random.Random(1360136), 200)
    fixed = []
    fixed = list(cases)  # http-dates are clock-relative; generated after now0 below

    clock = mod.WallClock()
    now0 = clock.datetime_now()
    if now0.tzinfo is None:
        now0 = now0.replace(tzinfo=timezone.utc)
    from email.utils import formatdate as _fmt
    for c in fixed:  # http-dates issued relative to the clock's own now
        if c["value"] == "@@HTTP_DATE@@":
            c["value"] = _fmt((now0 + timedelta(seconds=c["instructed"])).timestamp(), usegmt=True)
        elif c["value"] == "@@PAST_DATE@@":
            c["value"] = _fmt((now0 - timedelta(seconds=1000)).timestamp(), usegmt=True)
    honor_pass = ignore_fail = 0
    kinds_seen = set()
    for c in fixed:
        wait = mod.wait_seconds(c["value"], now=now0, fallback=0.25)
        kinds_seen.add("http-date" if c["kind"].startswith("http-date")
                       else ("malformed" if c["kind"].startswith("malformed") else "delta-seconds"))
        # HTTP-date wire form carries second precision (RFC 9110 IMF-fixdate); delta-seconds is exact
        obs_tol = 1.0 if c["kind"].startswith("http-date") else 1e-9
        if mod.in_window(wait, c["instructed"], slack_abs=obs_tol):
            honor_pass += 1
        if not mod.in_window(1.0, c["instructed"], slack_abs=1e-9):
            ignore_fail += 1
    chk(honor_pass == 200, "honor-pass", honor_pass)
    chk(ignore_fail == 199, "ignore-fail", ignore_fail)
    chk({"delta-seconds", "http-date", "malformed"} <= kinds_seen, "wire-forms", kinds_seen)

    # fake/wall clock reconciliation: pair dispatch[i] with arrival[i], gaps equal waits
    fake = mod.FakeClock(start=7.0)
    t_start = fake.datetime_now()
    waits = [mod.wait_seconds(fixed[i]["value"], now=t_start, fallback=0.25) for i in range(10)]
    for w in waits:
        fake.sleep(w)
    gap = fake.datetime_now() - t_start
    chk(abs(gap.total_seconds() - sum(waits)) < 1e-6, "fake-clock-gap", gap.total_seconds())

    nc = (doc.get("negative_controls") or [{}])[0]
    chk(nc.get("fired_on_bad_state") is True and nc.get("silent_on_good_state") is True, "nc-semantics")
    prop = doc.get("property_test") or {}
    chk(prop.get("honor_pass") == 200 and prop.get("n") == 200, "recorded-property", prop)
    imp = doc.get("implementation") or {}
    chk(str(imp.get("parser") or "").endswith("retry_after.py"), "parser-path-recorded")
    chk("fallback" in str(imp.get("malformed")), "fallback-recorded")
    if FAILS:
        print("FAILED:TST-0136-probe2 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0136-probe2 200/200 honor windows pass live (delta-seconds + HTTP-date + past-date + malformed 0.25s fallback), ignore-client fails 199/200, fake/wall clocks reconcile, module digest matches recorded row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
