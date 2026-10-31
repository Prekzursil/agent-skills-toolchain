#!/usr/bin/env python3
"""OVH leftover fleet monitor — 18-box SSH aggregator with remaining/rate/ETA.

Writes:
  ../ovh-monitor/latest.json
  ../ovh-monitor/latest.md
  ../ovh-monitor/history.jsonl
  ../ovh-monitor/watch.log

Does not mutate git, does not start/stop supervisors, does not print secrets.
"""
from __future__ import annotations

import argparse
import base64
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from subprocess import run

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
OUT = WAVE / "ovh-monitor"
LEFTOVER = WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json"
HOURLY_USD = 16.92
FLEET_CAP = 1080
SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]
FLEET = [
    ("p2-ovh-gra11-a", "176.31.201.117", 80, 0),
    ("p2-ovh-gra11-c", "176.31.201.215", 40, 1),
    ("p2-ovh-waw1-b", "51.75.63.116", 80, 2),
    ("p2-ovh-waw1-c", "54.38.138.226", 40, 3),
    ("p2-ovh-de1-a", "51.75.93.252", 80, 4),
    ("p2-ovh-de1-c", "162.19.209.251", 40, 5),
    ("p2-ovh-gra9-b", "37.59.27.161", 80, 6),
    ("p2-ovh-gra9-c", "141.94.186.60", 40, 7),
    ("p2-ovh-rbx-a", "164.132.87.22", 80, 8),
    ("p2-ovh-rbx-c", "152.228.192.99", 40, 9),
    ("p2-ovh-par-a", "57.130.47.223", 80, 10),
    ("p2-ovh-par-c", "57.130.46.182", 40, 11),
    ("p2-ovh-uk1-a", "54.37.3.247", 80, 12),
    ("p2-ovh-uk1-c", "54.37.7.164", 40, 13),
    ("p2-ovh-gra7-a", "51.91.140.54", 80, 14),
    ("p2-ovh-gra7-c", "51.210.248.225", 40, 15),
    ("p2-ovh-sbg5-a", "57.128.35.67", 80, 16),
    ("p2-ovh-sbg5-c", "57.128.111.33", 40, 17),
]
REMOTE = r"""
import json, subprocess
from pathlib import Path
hb = {}
p = Path('/opt/p2/supervisor-heartbeat.json')
if p.exists():
    try:
        hb = json.loads(p.read_text())
    except Exception as e:
        hb = {'_err': str(e)}
done = []
cp = Path('/opt/p2/completed.json')
if cp.exists():
    try:
        done = [str(x) for x in (json.loads(cp.read_text()).get('ids') or [])]
    except Exception:
        done = []
svc = subprocess.run(['systemctl','is-active','p2-supervisor'], capture_output=True, text=True).stdout.strip()
ok = infra = park = launch = retry = failed_meas = success_meas = r429 = authlog = 0
last = ''
failed_ex = []
lp = Path('/opt/p2/supervisor.log')
if lp.exists():
    try:
        lines = lp.read_text(errors='replace').splitlines()
        last = lines[-1] if lines else ''
        for line in lines:
            if ' DONE-OK' in line:
                ok += 1
                if 'measure=FAILED' in line or 'FAILED:delivered' in line:
                    failed_meas += 1
                    if len(failed_ex) < 5:
                        failed_ex.append(line[-180:])
                elif 'SUCCESS:delivered' in line:
                    success_meas += 1
            if ' INFRA ' in line:
                infra += 1
            if ' PARK ' in line:
                park += 1
            if ' LAUNCH ' in line:
                launch += 1
            if ' RETRYABLE ' in line:
                retry += 1
            if 'AUTH-FAIL' in line:
                authlog += 1
            low = line.lower()
            if '429' in line or 'rate limit' in low or 'resource_exhausted' in low:
                r429 += 1
    except Exception:
        pass
probes = Path('/opt/p2/ast-integrate/command-center/p2-wave/probes')
samples = []
missing_ret = missing_man = checked = 0
for uid in done[-8:]:
    checked += 1
    d = probes / uid
    retp = d / 'SUBAGENT-RETURN.json'
    manp = d / 'UNIT-ARTIFACT-MANIFEST.json'
    rec = {'id': uid, 'return': retp.exists(), 'manifest': manp.exists()}
    if not retp.exists():
        missing_ret += 1
    if not manp.exists():
        missing_man += 1
    if retp.exists():
        try:
            r = json.loads(retp.read_text())
            rec['status'] = str(r.get('status') or r.get('state') or '')[:24]
            rec['registered'] = r.get('registered')
            rec['mline'] = str(r.get('measure_line') or '')[:80]
        except Exception:
            rec['status'] = 'BAD-JSON'
    rec['nfiles'] = len(list(d.iterdir())) if d.exists() else 0
    samples.append(rec)
print(json.dumps({
    'hb': hb, 'done_ids': done, 'svc': svc,
    'auth_fail': Path('/opt/p2/AUTH-FAIL').exists(),
    'queue_empty': Path('/opt/p2/QUEUE-EMPTY').exists(),
    'log_ok': ok, 'log_infra': infra, 'log_park': park,
    'log_launch': launch, 'log_retry': retry, 'log_last': last[-300:],
    'success_meas': success_meas, 'failed_meas': failed_meas,
    'r429': r429, 'authlog': authlog, 'failed_ex': failed_ex,
    'samples': samples, 'missing_ret': missing_ret, 'missing_man': missing_man,
    'sample_n': checked,
}, separators=(',', ':')))
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_leftover() -> tuple[int, set[str], dict[str, int]]:
    data = json.loads(LEFTOVER.read_text(encoding="utf-8"))
    ids = [i for i in (data.get("remaining_ids") or []) if isinstance(i, str)]
    return int(data.get("remaining_if_log_success_skipped") or len(ids)), set(ids), dict(data.get("remaining_by_prefix") or {})


def probe(name: str, ip: str, cap: int, idx: int) -> dict:
    t0 = time.time()
    payload = base64.b64encode(REMOTE.strip().encode("utf-8")).decode("ascii")
    remote_cmd = f"echo {payload} | base64 -d | python3"
    try:
        p = run(
            SSH + [f"root@{ip}", remote_cmd],
            capture_output=True,
            text=True,
            timeout=35,
        )
    except Exception as exc:
        return {
            "name": name,
            "ip": ip,
            "cap": cap,
            "idx": idx,
            "ok": False,
            "error": str(exc),
            "rtt_s": round(time.time() - t0, 2),
        }
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if p.returncode != 0 or not out:
        return {
            "name": name,
            "ip": ip,
            "cap": cap,
            "idx": idx,
            "ok": False,
            "error": (err or out or f"rc={p.returncode}")[-400:],
            "rtt_s": round(time.time() - t0, 2),
        }
    try:
        payload = json.loads(out.splitlines()[-1])
    except json.JSONDecodeError:
        return {
            "name": name,
            "ip": ip,
            "cap": cap,
            "idx": idx,
            "ok": False,
            "error": f"bad-json {out[-200:]}",
            "rtt_s": round(time.time() - t0, 2),
        }
    hb = payload.get("hb") if isinstance(payload.get("hb"), dict) else {}
    done_ids = [x for x in (payload.get("done_ids") or []) if isinstance(x, str)]
    in_flight = hb.get("in_flight") if isinstance(hb.get("in_flight"), list) else []
    return {
        "name": name,
        "ip": ip,
        "cap": cap,
        "idx": idx,
        "ok": True,
        "rtt_s": round(time.time() - t0, 2),
        "svc": payload.get("svc"),
        "auth_fail": bool(payload.get("auth_fail")),
        "queue_empty": bool(payload.get("queue_empty")),
        "hb_ts": hb.get("ts"),
        "box": hb.get("box") or name,
        "in_flight_n": int(hb.get("in_flight_n") or len(in_flight) or 0),
        "live_grok": int(hb.get("live_grok") or 0),
        "queued_n": int(hb.get("queued_n") or 0),
        "queued_head": hb.get("queued_head") or [],
        "launched": int(hb.get("launched") or 0),
        "ok_n": int(hb.get("ok") or 0),
        "parked_n": int(hb.get("parked") or 0),
        "failed_n": int(hb.get("failed") or 0),
        "done_n": len(done_ids),
        "done_ids": done_ids,
        "in_flight": [str(x) for x in in_flight],
        "log_ok": int(payload.get("log_ok") or 0),
        "log_infra": int(payload.get("log_infra") or 0),
        "log_park": int(payload.get("log_park") or 0),
        "log_launch": int(payload.get("log_launch") or 0),
        "log_retry": int(payload.get("log_retry") or 0),
        "log_last": payload.get("log_last") or "",
        "success_meas": int(payload.get("success_meas") or 0),
        "failed_meas": int(payload.get("failed_meas") or 0),
        "r429": int(payload.get("r429") or 0),
        "authlog": int(payload.get("authlog") or 0),
        "failed_ex": payload.get("failed_ex") or [],
        "samples": payload.get("samples") or [],
        "missing_ret": int(payload.get("missing_ret") or 0),
        "missing_man": int(payload.get("missing_man") or 0),
        "sample_n": int(payload.get("sample_n") or 0),
    }


def bar(frac: float, width: int = 28) -> str:
    frac = max(0.0, min(1.0, frac))
    filled = int(round(frac * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def fmt_dur(seconds: float | None) -> str:
    if seconds is None:
        return "n/a (need measured completions)"
    if seconds < 0:
        return "n/a"
    m = int(seconds // 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def age_s(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())
    except ValueError:
        return None


def load_history() -> list[dict]:
    path = OUT / "history.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-80:]


def rate_from_history(history: list[dict], unique_done: int) -> dict:
    now = time.time()
    windows = [
        ("5m", 5 * 60),
        ("15m", 15 * 60),
        ("1h", 60 * 60),
        ("all", None),
    ]
    out: dict[str, float | None] = {}
    for label, span in windows:
        if not history:
            out[label] = None
            continue
        if span is None:
            first = history[0]
        else:
            first = None
            for row in history:
                ts = row.get("epoch")
                if isinstance(ts, (int, float)) and now - ts <= span:
                    first = row
                    break
            if first is None:
                first = history[0]
        prev = int(first.get("unique_done") or 0)
        epoch = first.get("epoch")
        if not isinstance(epoch, (int, float)) or now - epoch < 30:
            out[label] = None
            continue
        delta = unique_done - prev
        hours = (now - epoch) / 3600.0
        if span is not None and (now - epoch) < span * 0.6:
            out[label] = None
            continue
        out[label] = round(delta / hours, 2) if hours > 0 else None
    return out


def snapshot() -> dict:
    leftover_n, leftover_ids, leftover_prefix = load_leftover()
    boxes: list[dict] = []
    with ThreadPoolExecutor(max_workers=18) as pool:
        futs = {pool.submit(probe, *row): row[0] for row in FLEET}
        for fut in as_completed(futs):
            boxes.append(fut.result())
    boxes.sort(key=lambda b: int(b.get("idx") or 99))

    unique_done: set[str] = set()
    unique_flight: set[str] = set()
    reachable = 0
    active = 0
    auth_fail = []
    stale = []
    down = []
    in_flight_sum = 0
    cap_sum = 0
    queued_sum = 0
    launched_sum = 0
    ok_sum = 0
    park_sum = 0
    fail_sum = 0
    infra_sum = 0
    log_ok_sum = 0
    success_meas_sum = 0
    failed_meas_sum = 0
    r429_sum = 0
    missing_ret_sum = 0
    missing_man_sum = 0
    sample_n_sum = 0
    failed_examples: list[str] = []
    sample_fail_status: list[str] = []

    slim_boxes = []
    for b in boxes:
        cap_sum += int(b.get("cap") or 0)
        if not b.get("ok"):
            down.append(b["name"])
            slim_boxes.append(
                {
                    "name": b["name"],
                    "ip": b["ip"],
                    "cap": b["cap"],
                    "idx": b["idx"],
                    "reachable": False,
                    "error": b.get("error"),
                }
            )
            continue
        reachable += 1
        if b.get("svc") == "active":
            active += 1
        if b.get("auth_fail"):
            auth_fail.append(b["name"])
        hb_age = age_s(b.get("hb_ts"))
        if hb_age is not None and hb_age > 90:
            stale.append(b["name"])
        unique_done.update(b.get("done_ids") or [])
        unique_flight.update(b.get("in_flight") or [])
        in_flight_sum += int(b.get("in_flight_n") or 0)
        queued_sum += int(b.get("queued_n") or 0)
        launched_sum += int(b.get("launched") or 0)
        ok_sum += int(b.get("ok_n") or 0)
        park_sum += int(b.get("parked_n") or 0)
        fail_sum += int(b.get("failed_n") or 0)
        infra_sum += int(b.get("log_infra") or 0)
        log_ok_sum += int(b.get("log_ok") or 0)
        success_meas_sum += int(b.get("success_meas") or 0)
        failed_meas_sum += int(b.get("failed_meas") or 0)
        r429_sum += int(b.get("r429") or 0)
        missing_ret_sum += int(b.get("missing_ret") or 0)
        missing_man_sum += int(b.get("missing_man") or 0)
        sample_n_sum += int(b.get("sample_n") or 0)
        for ex in b.get("failed_ex") or []:
            if len(failed_examples) < 12:
                failed_examples.append(f"{b['name']} {ex}")
        for rec in b.get("samples") or []:
            st = str(rec.get("status") or "")
            if rec.get("return") and st and st not in {"DELIVERED", "SUCCESS"}:
                sample_fail_status.append(f"{b['name']}:{rec.get('id')}={st}")
        fill = (int(b.get("in_flight_n") or 0) / max(1, int(b.get("cap") or 1))) * 100
        slim_boxes.append(
            {
                "name": b["name"],
                "ip": b["ip"],
                "cap": b["cap"],
                "idx": b["idx"],
                "reachable": True,
                "svc": b.get("svc"),
                "auth_fail": b.get("auth_fail"),
                "queue_empty": b.get("queue_empty"),
                "hb_ts": b.get("hb_ts"),
                "hb_age_s": round(hb_age, 1) if hb_age is not None else None,
                "in_flight_n": b.get("in_flight_n"),
                "live_grok": b.get("live_grok"),
                "queued_n": b.get("queued_n"),
                "fill_pct": round(fill, 1),
                "done_n": b.get("done_n"),
                "launched": b.get("launched"),
                "ok_n": b.get("ok_n"),
                "parked_n": b.get("parked_n"),
                "failed_n": b.get("failed_n"),
                "log_infra": b.get("log_infra"),
                "log_ok": b.get("log_ok"),
                "success_meas": b.get("success_meas"),
                "failed_meas": b.get("failed_meas"),
                "r429": b.get("r429"),
                "missing_ret": b.get("missing_ret"),
                "missing_man": b.get("missing_man"),
                "samples": b.get("samples"),
                "queued_head": b.get("queued_head"),
                "log_last": b.get("log_last"),
                "rtt_s": b.get("rtt_s"),
            }
        )

    leftover_done = unique_done & leftover_ids
    remaining_ids = leftover_ids - leftover_done - unique_flight
    remaining_n = leftover_n - len(leftover_done)
    if remaining_n < 0:
        remaining_n = max(0, leftover_n - len(unique_done))

    by_prefix_done: dict[str, int] = {}
    for uid in leftover_done:
        pref = uid.split("-", 1)[0]
        by_prefix_done[pref] = by_prefix_done.get(pref, 0) + 1
    by_prefix_left = {}
    for pref, n in leftover_prefix.items():
        by_prefix_left[pref] = max(0, int(n) - by_prefix_done.get(pref, 0))

    history = load_history()
    rates = rate_from_history(history, len(leftover_done))
    measured_rate = None
    rate_src = None
    for key in ("5m", "15m", "1h", "all"):
        val = rates.get(key)
        if isinstance(val, (int, float)) and val > 0:
            measured_rate = val
            rate_src = key
            break

    eta_s = None
    eta_cons_s = None
    if measured_rate and remaining_n > 0:
        eta_s = remaining_n / measured_rate * 3600.0
        eta_cons_s = remaining_n / max(measured_rate * 0.4, 1.0) * 3600.0
    cost_left = None
    cost_cons = None
    if eta_s is not None:
        cost_left = round((eta_s / 3600.0) * HOURLY_USD, 2)
    if eta_cons_s is not None:
        cost_cons = round((eta_cons_s / 3600.0) * HOURLY_USD, 2)

    fill_pct = (in_flight_sum / FLEET_CAP) * 100 if FLEET_CAP else 0
    done_pct = (len(leftover_done) / leftover_n) * 100 if leftover_n else 0

    health = "OK"
    reasons: list[str] = []
    if down:
        health = "FAIL"
        reasons.append("ssh-down " + ",".join(down))
    if auth_fail:
        health = "FAIL"
        reasons.append("AUTH-FAIL " + ",".join(auth_fail))
    if failed_meas_sum:
        if health == "OK":
            health = "WARN"
        reasons.append(f"false-DONE-OK {failed_meas_sum} (measure=FAILED still counted done)")
    if missing_ret_sum or missing_man_sum:
        if health == "OK":
            health = "WARN"
        reasons.append(f"sample missing return={missing_ret_sum} manifest={missing_man_sum} of {sample_n_sum}")
    if sample_fail_status:
        if health == "OK":
            health = "WARN"
        reasons.append("non-DELIVERED sample " + ",".join(sample_fail_status[:6]))
    if r429_sum:
        if health == "OK":
            health = "WARN"
        reasons.append(f"429/rate-limit hits {r429_sum}")
    if in_flight_sum == 0 and remaining_n > 0 and active < 10:
        health = "FAIL"
        reasons.append("STALL live=0")

    snap = {
        "ts": utc_now(),
        "epoch": time.time(),
        "leftover_start": leftover_n,
        "unique_done": len(leftover_done),
        "unique_done_all": len(unique_done),
        "unique_in_flight": len(unique_flight),
        "in_flight_sum": in_flight_sum,
        "queued_sum": queued_sum,
        "remaining": remaining_n,
        "remaining_not_started": len(remaining_ids),
        "done_pct": round(done_pct, 2),
        "fill_pct": round(fill_pct, 1),
        "fleet_cap": FLEET_CAP,
        "reachable": reachable,
        "active_svc": active,
        "down": down,
        "stale_hb": stale,
        "auth_fail": auth_fail,
        "launched_sum": launched_sum,
        "ok_sum": ok_sum,
        "park_sum": park_sum,
        "fail_sum": fail_sum,
        "infra_sum": infra_sum,
        "log_ok_sum": log_ok_sum,
        "success_meas_sum": success_meas_sum,
        "failed_meas_sum": failed_meas_sum,
        "r429_sum": r429_sum,
        "missing_ret_sum": missing_ret_sum,
        "missing_man_sum": missing_man_sum,
        "sample_n_sum": sample_n_sum,
        "failed_examples": failed_examples,
        "sample_fail_status": sample_fail_status,
        "health": health,
        "health_reasons": reasons,
        "rate_per_h": rates,
        "rate_used": measured_rate,
        "rate_window": rate_src,
        "eta_s": eta_s,
        "eta": fmt_dur(eta_s),
        "eta_conservative": fmt_dur(eta_cons_s),
        "hourly_usd": HOURLY_USD,
        "eta_cost_usd": cost_left,
        "eta_cost_cons_usd": cost_cons,
        "by_prefix_left": by_prefix_left,
        "by_prefix_done": by_prefix_done,
        "boxes": slim_boxes,
    }
    return snap


def render_md(snap: dict) -> str:
    lines = []
    lines.append(f"# OVH leftover fleet — {snap['ts']}")
    lines.append("")
    lines.append(
        f"{bar(snap['done_pct'] / 100.0)}  **{snap['done_pct']:.1f}%**  "
        f"{snap['unique_done']}/{snap['leftover_start']} unique DONE  "
        f"**{snap['remaining']} remaining**"
    )
    lines.append(
        f"{bar(snap['fill_pct'] / 100.0)}  live fill **{snap['in_flight_sum']}/{snap['fleet_cap']}** "
        f"({snap['fill_pct']:.0f}%)  unique in-flight {snap['unique_in_flight']}  queued {snap['queued_sum']}"
    )
    lines.append("")
    rate = snap.get("rate_used")
    rate_s = f"{rate:.1f}/h ({snap.get('rate_window')})" if rate else "not yet measured"
    lines.append(f"- **HEALTH: {snap.get('health')}**" + (
        " — " + "; ".join(snap.get("health_reasons") or []) if snap.get("health_reasons") else " — no auth/down/false-done/missing-artifact alerts"
    ))
    lines.append(f"- **ETA burst:** {snap.get('eta')}  · **ETA conservative (rate×0.4):** {snap.get('eta_conservative')}  · rate {rate_s}")
    lines.append(
        "  Burst is the measured window (easy CNF/CNL drain first). Conservative assumes the remaining IMP/TST/AUD mix is slower."
    )
    if snap.get("eta_cost_usd") is not None:
        lines.append(
            f"- **Meter:** burst ~${snap['eta_cost_usd']} / conservative ~${snap.get('eta_cost_cons_usd')} @ ${snap['hourly_usd']}/h"
        )
    lines.append(
        f"- boxes reachable {snap['reachable']}/18  systemd-active {snap['active_svc']}/18"
    )
    lines.append(
        f"- quality  SUCCESS:delivered logs={snap.get('success_meas_sum')}  "
        f"false-DONE-OK (measure=FAILED)={snap.get('failed_meas_sum')}  "
        f"INFRA={snap.get('infra_sum')}  PARK={snap.get('park_sum')}  "
        f"429={snap.get('r429_sum')}  sample missing return/manifest="
        f"{snap.get('missing_ret_sum')}/{snap.get('missing_man_sum')} of {snap.get('sample_n_sum')}"
    )
    if snap["down"]:
        lines.append(f"- **DOWN:** {', '.join(snap['down'])}")
    if snap["auth_fail"]:
        lines.append(f"- **AUTH-FAIL:** {', '.join(snap['auth_fail'])}")
    if snap["stale_hb"]:
        lines.append(f"- **stale heartbeat (>90s):** {', '.join(snap['stale_hb'])}")
    lines.append(
        f"- supervisor counters  launched={snap['launched_sum']} ok={snap['ok_sum']} "
        f"park={snap['park_sum']} fail={snap['fail_sum']} infra-log={snap['infra_sum']}"
    )
    rp = snap.get("rate_per_h") or {}
    lines.append(
        f"- rates/h  5m={rp.get('5m')}  15m={rp.get('15m')}  1h={rp.get('1h')}  all={rp.get('all')}"
    )
    lines.append("")
    lines.append("## Per box")
    lines.append("")
    lines.append("| box | idx | svc | live/cap | fill | queued | done | SUCCESS/false | infra | 429 | miss ret/man | hb age | last |")
    lines.append("|---|---:|---|---:|---:|---:|---:|---|---:|---:|---|---:|---|")
    for b in snap["boxes"]:
        if not b.get("reachable"):
            err = str(b.get("error") or "ssh-fail").replace("|", "/")[:60]
            lines.append(f"| {b['name']} | {b['idx']} | DOWN | — | — | — | — | — | — | — | — | — | `{err}` |")
            continue
        last = str(b.get("log_last") or "").replace("|", "/")[-80:]
        lines.append(
            f"| {b['name']} | {b['idx']} | {b.get('svc')} | "
            f"{b.get('in_flight_n')}/{b.get('cap')} | {b.get('fill_pct')}% | "
            f"{b.get('queued_n')} | {b.get('done_n')} | "
            f"{b.get('success_meas')}/{b.get('failed_meas')} | "
            f"{b.get('log_infra')} | {b.get('r429')} | "
            f"{b.get('missing_ret')}/{b.get('missing_man')} | "
            f"{b.get('hb_age_s')}s | `{last}` |"
        )
    left = snap.get("by_prefix_left") or {}
    if left:
        lines.append("")
        lines.append("## Remaining by prefix")
        lines.append("")
        bits = [f"{k} {v}" for k, v in sorted(left.items()) if v]
        lines.append(", ".join(bits) if bits else "(none)")
    if snap.get("failed_examples"):
        lines.append("")
        lines.append("## False DONE-OK (measure=FAILED but dispatcher counted done)")
        lines.append("")
        for ex in snap["failed_examples"]:
            lines.append(f"- `{ex}`")
        lines.append("")
        lines.append(
            "Cause: `dispatch_cursor.py` uses `mcode==0 or is_green(return)`. "
            "A DELIVERED+registered return can skip a failing live measure. "
            "Independent re-measure of IMP-0061 on gra9-b: `FAILED:delivered probe-exit:1` (`node` missing)."
        )
    lines.append("")
    lines.append(
        "Done here is unique `completed.json` IDs ∩ leftover 1726. "
        "INFRA skips are not done. Park stays open. "
        "SUCCESS:delivered log lines are the honest G-1-shaped count; false-DONE-OK is subtracted in HEALTH not in the progress bar. "
        "Not a G-1 import claim — harvest/verify still required."
    )
    lines.append("")
    return "\n".join(lines)


def write_snap(snap: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    slim = dict(snap)
    # keep ids out of latest.json to stay small; they are recoverable from boxes if needed
    (OUT / "latest.json").write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    (OUT / "latest.md").write_text(render_md(snap), encoding="utf-8")
    hist = {
        "ts": snap["ts"],
        "epoch": snap["epoch"],
        "unique_done": snap["unique_done"],
        "remaining": snap["remaining"],
        "in_flight_sum": snap["in_flight_sum"],
        "reachable": snap["reachable"],
        "active_svc": snap["active_svc"],
        "rate_used": snap.get("rate_used"),
        "eta": snap.get("eta"),
        "eta_conservative": snap.get("eta_conservative"),
        "health": snap.get("health"),
        "failed_meas_sum": snap.get("failed_meas_sum"),
        "success_meas_sum": snap.get("success_meas_sum"),
        "down": snap.get("down"),
        "auth_fail": snap.get("auth_fail"),
    }
    with (OUT / "history.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(hist, separators=(",", ":")) + "\n")


def event_line(snap: dict, prev: dict | None) -> str:
    parts = [
        f"TICK {snap['ts']}",
        f"done={snap['unique_done']}/{snap['leftover_start']}",
        f"remain={snap['remaining']}",
        f"live={snap['in_flight_sum']}/{snap['fleet_cap']}",
        f"fill={snap['fill_pct']:.0f}%",
        f"eta={snap.get('eta')}",
        f"eta_cons={snap.get('eta_conservative')}",
        f"health={snap.get('health')}",
        f"false_done={snap.get('failed_meas_sum')}",
        f"rate={snap.get('rate_used')}/h" if snap.get("rate_used") else "rate=pending",
        f"up={snap['reachable']}/18",
        f"active={snap['active_svc']}/18",
    ]
    if snap["down"]:
        parts.append("DOWN=" + ",".join(snap["down"]))
    if snap["auth_fail"]:
        parts.append("AUTH-FAIL=" + ",".join(snap["auth_fail"]))
    if snap["stale_hb"]:
        parts.append("STALE=" + ",".join(snap["stale_hb"]))
    if prev:
        ddone = snap["unique_done"] - int(prev.get("unique_done") or 0)
        dlive = snap["in_flight_sum"] - int(prev.get("in_flight_sum") or 0)
        parts.append(f"ddone={ddone:+d}")
        parts.append(f"dlive={dlive:+d}")
    return " ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--watch", type=int, default=0, help="poll interval seconds")
    ap.add_argument("--events-only", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="write files; stdout only ALERT/DONE")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    logp = OUT / "watch.log"

    def one(prev=None):
        snap = snapshot()
        write_snap(snap)
        line = event_line(snap, prev)
        with logp.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        if not args.quiet:
            print(line, flush=True)
            if not args.events_only:
                print(render_md(snap), flush=True)
        if snap["auth_fail"]:
            print("ALERT AUTH-FAIL " + ",".join(snap["auth_fail"]), flush=True)
        if snap["down"]:
            print("ALERT DOWN " + ",".join(snap["down"]), flush=True)
        prev = prev or {}
        if snap.get("failed_meas_sum") and int(snap["failed_meas_sum"]) > int(prev.get("failed_meas_sum") or -1):
            print("ALERT FALSE-DONE n=" + str(snap["failed_meas_sum"]), flush=True)
        if (snap.get("missing_ret_sum") or snap.get("missing_man_sum")) and (
            int(snap.get("missing_ret_sum") or 0) > int(prev.get("missing_ret_sum") or -1)
            or int(snap.get("missing_man_sum") or 0) > int(prev.get("missing_man_sum") or -1)
        ):
            print(
                "ALERT MISSING-ARTIFACT return="
                + str(snap.get("missing_ret_sum"))
                + " manifest="
                + str(snap.get("missing_man_sum")),
                flush=True,
            )
        if snap.get("r429_sum") and int(snap["r429_sum"]) > int(prev.get("r429_sum") or -1):
            print("ALERT 429 n=" + str(snap["r429_sum"]), flush=True)
        if snap["remaining"] <= 0 and snap["in_flight_sum"] == 0 and snap["reachable"] >= 16:
            print("DONE leftover-drain unique_done=" + str(snap["unique_done"]), flush=True)
        elif (
            snap["in_flight_sum"] == 0
            and snap["remaining"] > 0
            and snap["active_svc"] < 10
        ):
            print("ALERT STALL live=0 remaining=" + str(snap["remaining"]), flush=True)
        return snap

    snap = one()
    if args.once or args.watch <= 0:
        return 0
    prev = snap
    last_tick_print = time.time()
    while True:
        time.sleep(max(30, args.watch))
        prev = one(prev)
        last_tick_print = time.time()
        _ = last_tick_print
        if prev["remaining"] <= 0 and prev["in_flight_sum"] == 0:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
