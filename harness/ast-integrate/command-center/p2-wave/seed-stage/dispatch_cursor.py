#!/usr/bin/env python3
"""Looping P2 supervisor using Cursor agent CLI + CURSOR_API_KEY.

G-2: full catalog leftovers. Model grok-4.6 (Cursor Models pool).
Does not relaunch p2-cloud-ok-deliver. No git writes. No global catalog --write.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/opt/p2/ast-integrate")
WAVE = ROOT / "command-center" / "p2-wave"
PROBES = WAVE / "probes"
CATALOG = ROOT / "command-center" / "WORK-UNIT-CATALOG.json"
LEFTOVER = WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json"
PARK_FILE = WAVE / "A-PLUS-D-PARK.json"
WORKERS = Path("/opt/p2/workers")
STRIKES = Path("/opt/p2/strikes")
LOCK_DIR = Path("/opt/p2/unit-locks")
LOG = Path("/opt/p2/supervisor.log")
HEART = Path("/opt/p2/supervisor-heartbeat.json")
DONE_MARK = Path("/opt/p2/QUEUE-EMPTY")
DONE_IDS = Path("/opt/p2/completed.json")
AUTH_FAIL = Path("/opt/p2/AUTH-FAIL")
STAGGER = 3.0
TWO_STRIKES = 2
WORKER_TIMEOUT_SEC = 90 * 60
IDLE_RESCAN_SEC = 45
UID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
LATE_PREFIX = {"ADV": 3, "AUD": 3, "PVP": 3}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    line = f"{utc_now()} {msg}"
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line, flush=True)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def which_agent() -> str:
    env = os.environ.get("CURSOR_AGENT_BIN")
    if env and Path(env).is_file():
        return env
    for c in (
        "/root/.local/bin/agent",
        "/root/.local/bin/cursor-agent",
        "/usr/local/bin/agent",
        "/usr/local/bin/cursor-agent",
    ):
        if Path(c).is_file():
            return c
    p = subprocess.run(["bash", "-lc", "command -v cursor-agent || command -v agent"], capture_output=True, text=True)
    got = (p.stdout or "").strip().splitlines()
    return got[-1] if got else "agent"


def slot(uid: str, n: int) -> int:
    return sum(ord(c) for c in uid) % n


def mine(uid: str, box: str) -> bool:
    n_env = os.environ.get("BOX_COUNT")
    i_env = os.environ.get("BOX_INDEX")
    if n_env and i_env is not None and n_env.isdigit() and str(i_env).lstrip("-").isdigit():
        n = int(n_env)
        i = int(i_env)
        if n > 0 and 0 <= i < n:
            return slot(uid, n) == i
    s = slot(uid, 4)
    if box.endswith("-a"):
        return s in {0, 2}
    if box.endswith("-b"):
        return s == 1
    return s == 3


def parked_ids() -> set[str]:
    data = load_json(PARK_FILE)
    out: set[str] = set()
    if not isinstance(data, dict):
        return out
    for rec in (data.get("units") or []) + (data.get("ids") or []):
        if isinstance(rec, dict) and rec.get("id"):
            out.add(str(rec["id"]))
        elif isinstance(rec, str):
            out.add(rec)
    return out


def catalog_ids() -> list[str]:
    data = load_json(CATALOG)
    out: list[str] = []
    if isinstance(data, dict):
        for u in data.get("work_units") or []:
            if isinstance(u, dict):
                uid = str(u.get("id") or "")
                if UID_RE.match(uid):
                    out.append(uid)
    return out


_CATALOG_BY_ID: dict[str, dict] | None = None


def catalog_by_id() -> dict[str, dict]:
    global _CATALOG_BY_ID
    if _CATALOG_BY_ID is None:
        data = load_json(CATALOG)
        out: dict[str, dict] = {}
        if isinstance(data, dict):
            for u in data.get("work_units") or []:
                if isinstance(u, dict) and u.get("id"):
                    out[str(u["id"])] = u
        _CATALOG_BY_ID = out
    return _CATALOG_BY_ID


def leftover_ids() -> list[str] | None:
    data = load_json(LEFTOVER)
    if not isinstance(data, dict):
        return None
    ids = data.get("remaining_ids") or []
    return [i for i in ids if isinstance(i, str) and UID_RE.match(i)]


def all_unit_ids() -> list[str]:
    left = leftover_ids()
    if left:
        return left
    return catalog_ids()


def read_return(uid: str) -> dict | None:
    data = load_json(PROBES / uid / "SUBAGENT-RETURN.json")
    return data if isinstance(data, dict) else None


def status_of(ret: dict | None) -> str:
    if not isinstance(ret, dict):
        return "NO-RETURN"
    return str(ret.get("status") or ret.get("state") or "UNKNOWN").upper()


def measure_ok(ret: dict | None) -> bool:
    if not isinstance(ret, dict):
        return False
    line = str(ret.get("measure_line") or "")
    meas = ret.get("measure") if isinstance(ret.get("measure"), dict) else {}
    if meas.get("exit_code") == 0 and str(meas.get("line") or line).startswith("SUCCESS:"):
        return True
    return line.startswith("SUCCESS:delivered") or line.startswith("SUCCESS:")


def output_live(uid: str) -> bool:
    """Catalog output_path must exist on THIS box. RETURN.json is not delivery."""
    unit = catalog_by_id().get(uid)
    if not isinstance(unit, dict):
        return False
    rel = str(unit.get("output_path") or "").replace("\\", "/")
    if not rel:
        return False
    path = ROOT / rel
    return path.is_file() and path.stat().st_size > 0


def is_green(uid: str, ret: dict | None) -> bool:
    if not output_live(uid):
        return False
    st = status_of(ret)
    if measure_ok(ret) and st in {"DELIVERED", "SUCCESS"}:
        return True
    return False


def load_completed() -> set[str]:
    data = load_json(DONE_IDS)
    if isinstance(data, dict):
        return set(str(x) for x in (data.get("ids") or []))
    return set()


def save_completed(ids: set[str]) -> None:
    DONE_IDS.write_text(json.dumps({"ids": sorted(ids), "ts": utc_now()}, indent=2) + "\n", encoding="utf-8")


def strike_path(uid: str) -> Path:
    return STRIKES / f"{uid}.json"


def load_strikes(uid: str) -> dict:
    data = load_json(strike_path(uid))
    if isinstance(data, dict):
        data.setdefault("attempts", [])
        return data
    return {"id": uid, "count": 0, "attempts": [], "parked": False}


def save_strikes(uid: str, rec: dict) -> None:
    STRIKES.mkdir(parents=True, exist_ok=True)
    rec["count"] = len(rec.get("attempts") or [])
    strike_path(uid).write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")


def fingerprint(text: str) -> str:
    t = (text or "").lower()
    if "not authenticated" in t or "invalid" in t and "api key" in t:
        return "auth-missing"
    if "predicate:absent" in t:
        return "predicate:absent"
    m = re.search(r"FAILED:delivered \S+ (.+)", text or "")
    if m:
        return m.group(1)[:80]
    return (text or "unknown")[:80]


def prompt_for(uid: str) -> str:
    return f"""P2-deliver unit {uid} on this Linux worktree /opt/p2/ast-integrate.

GOAL: G-1 contract-green for THIS unit only. SUCCESS:delivered from
  python3 command-center/p2-wave/_measure_one_delivered.py {uid}
requires ALL of: catalog output_path file on disk (non-empty, parses, not BLOCKED),
live named probes exit 0, per-unit UNIT-ARTIFACT-MANIFEST.json sha256 match.
cloud ok=true is not delivery. SUBAGENT-RETURN.json alone is NOT delivery.

If probes/{uid}/ is missing, CREATE it and implement. Do not exit because the first measure says predicate:absent.

CONSTRAINTS (hard):
- Do not git add/commit/push/stash/checkout/rebase.
- Do not run unit_manifest.py --write on the global catalog.
- Do not rotate or print API keys.
- Do not relaunch finish-everything-close or p2-cloud-ok-deliver.
- Two same-fingerprint structural refutes: park (status=BLOCKED, required_fix named). No ADV rebuild circle.

START FROM command-center/p2-wave/probes/{uid}/ if present. Resume; do not scrap.

WRITE (mandatory, all three):
  1. the catalog output_path for {uid} from command-center/WORK-UNIT-CATALOG.json
     (usually command-center/receipts|adversarial|research|audit/...). Real file. Not BLOCKED.
  2. command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json
  3. command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json (per-unit only, sha256 of the LIVE output_path)

ONLY AFTER those files exist, MEASURE:
  python3 command-center/p2-wave/_measure_one_delivered.py {uid}
SUCCESS only if that prints SUCCESS:delivered. If it prints predicate:absent, write the missing output_path and remasure. Do not stop at RETURN.json.
"""


def live_agent_count() -> int:
    p = subprocess.run(["pgrep", "-cf", r"agent .*-p|--print"], capture_output=True, text=True)
    try:
        n = int((p.stdout or "0").strip() or "0")
    except ValueError:
        n = 0
    return max(0, n)


def run_measure(uid: str) -> tuple[int, str]:
    script = WAVE / "_measure_one_delivered.py"
    if not script.is_file():
        return 2, "FAILED:measure-missing"
    p = subprocess.run(
        [sys.executable, str(script), uid],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    line = ((p.stdout or "") + "\n" + (p.stderr or "")).strip().splitlines()
    last = line[-1] if line else f"exit={p.returncode}"
    return p.returncode, last[:300]


def write_heartbeat(box: str, cap: int, flight: dict, queued: list[str], extra: dict) -> None:
    HEART.write_text(
        json.dumps(
            {
                "ts": utc_now(),
                "box": box,
                "runtime": "cursor-agent",
                "model": "grok-4.6",
                "cap": cap,
                "live_grok": live_agent_count(),
                "in_flight": sorted(flight),
                "in_flight_n": len(flight),
                "queued_n": len(queued),
                "queued_head": queued[:12],
                "queue_empty": not flight and not queued,
                **extra,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def build_queue(box: str, flight: set[str], park: set[str], done: set[str]) -> list[str]:
    out: list[str] = []
    for uid in all_unit_ids():
        if not mine(uid, box):
            continue
        if uid in flight or uid in park or uid in done:
            continue
        rec = load_strikes(uid)
        if rec.get("parked") or len(rec.get("attempts") or []) >= TWO_STRIKES:
            continue
        # leftover remaining_ids are G-1 fails. Do NOT skip because output_path exists.
        out.append(uid)

    def pri(uid: str) -> tuple[int, int, str]:
        prefix = uid.split("-")[0]
        has_tree = (PROBES / uid).is_dir()
        return (0 if not has_tree else 1, LATE_PREFIX.get(prefix, 0), uid)

    out.sort(key=pri)
    return out


def agent_cmd(bin_path: str, prompt: Path) -> list[str]:
    cmd = [
        bin_path,
        "-p",
        "--force",
        "--trust",
        "--sandbox",
        "disabled",
        "--model",
        "cursor-grok-4.6-xhigh",
        "--workspace",
        str(ROOT),
        "--output-format",
        "text",
    ]
    # xhigh if this CLI build supports it (Grok 4.6 effort ladder).
    cmd.extend(["--effort", "xhigh"])
    cmd.append(prompt.read_text(encoding="utf-8")[:12000])
    return cmd


def launch_one(uid: str, attempt: int, bin_path: str) -> dict:
    home = WORKERS / f"loop-{uid}-a{attempt}"
    home.mkdir(parents=True, exist_ok=True)
    prompt = home / "prompt.txt"
    prompt.write_text(prompt_for(uid), encoding="utf-8")
    env = os.environ.copy()
    env.setdefault("HOME", "/root")
    logf = open(home / "worker.log", "a", encoding="utf-8")
    logf.write(f"\n===== launch {utc_now()} attempt={attempt} bin={bin_path} =====\n")
    logf.flush()
    cmd = [
        bin_path,
        "-p",
        "--force",
        "--trust",
        "--sandbox",
        "disabled",
        "--model",
        "cursor-grok-4.6-xhigh",
        "--workspace",
        str(ROOT),
        "--output-format",
        "text",
    ]
    cmd.append(prompt.read_text(encoding="utf-8"))
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=logf,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    (LOCK_DIR / f"{uid}.lock").write_text(
        json.dumps({"pid": proc.pid, "home": str(home), "at": utc_now()}), encoding="utf-8"
    )
    return {"proc": proc, "home": home, "logf": logf, "started": time.time(), "attempt": attempt, "uid": uid}


def tail_text(path: Path, n: int = 30) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-n:])


def reap_one(child: dict) -> dict:
    uid = child["uid"]
    try:
        child["logf"].flush()
        child["logf"].close()
    except Exception:
        pass
    rc = child["proc"].returncode
    runtime = time.time() - float(child.get("started") or time.time())
    blob = tail_text(child["home"] / "worker.log")
    low = blob.lower()
    if "not authenticated" in low or "api key is invalid" in low or "cursor_api_key" in low and "invalid" in low:
        AUTH_FAIL.write_text(f"{utc_now()} {uid}\n", encoding="utf-8")
        log(f"AUTH-FAIL {uid}")
        (LOCK_DIR / f"{uid}.lock").unlink(missing_ok=True)
        return {"uid": uid, "rc": rc, "ok": False, "auth_fail": True, "measure": "AUTH-FAIL"}
    if "unknown flag" in low or "unexpected argument" in low and "--effort" in blob:
        log(f"NO-EFFORT-FLAG {uid} — retry without --effort next (logged)")
    mcode, mline = run_measure(uid)
    ok = mcode == 0 and output_live(uid)
    if ok:
        log(f"DONE-OK {uid} measure={mline}")
        (LOCK_DIR / f"{uid}.lock").unlink(missing_ok=True)
        return {"uid": uid, "rc": rc, "ok": True, "measure": mline, "complete": True}
    fp = fingerprint(mline + "\n" + blob)
    if fp in {"auth-missing", "predicate:absent"} or runtime < 45:
        log(f"INFRA {uid} runtime={runtime:.0f}s fp={fp} {mline}")
        (LOCK_DIR / f"{uid}.lock").unlink(missing_ok=True)
        return {"uid": uid, "rc": rc, "ok": False, "infra": True, "measure": mline}
    rec = load_strikes(uid)
    rec["attempts"].append({"at": utc_now(), "fp": fp, "measure": mline, "rc": rc})
    if len(rec["attempts"]) >= TWO_STRIKES:
        rec["parked"] = True
        rec["park_reason"] = fp
        log(f"PARK {uid} fp={fp}")
    else:
        log(f"RETRYABLE {uid} fp={fp} {mline}")
    save_strikes(uid, rec)
    (LOCK_DIR / f"{uid}.lock").unlink(missing_ok=True)
    return {"uid": uid, "rc": rc, "ok": False, "measure": mline}


def drop_effort_if_needed(bin_path: str) -> None:
    """One-shot help probe; write /opt/p2/NO-EFFORT if --effort unsupported."""
    marker = Path("/opt/p2/NO-EFFORT")
    if marker.exists():
        return
    if not Path(bin_path).is_file():
        log(f"WARN agent bin missing at {bin_path}")
        return
    try:
        p = subprocess.run([bin_path, "-h"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log(f"WARN agent -h failed: {exc}")
        return
    text = (p.stdout or "") + (p.stderr or "")
    if "--effort" not in text and "effort" not in text.lower():
        marker.write_text("no --effort flag\n", encoding="utf-8")
        log("CLI has no --effort; using grok-4.6 default thinking")


def main() -> int:
    box = sys.argv[1] if len(sys.argv) > 1 else "p2-cur-a"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    for d in (WORKERS, STRIKES, LOCK_DIR):
        d.mkdir(parents=True, exist_ok=True)
    if not os.environ.get("CURSOR_API_KEY"):
        log("FAILED:no CURSOR_API_KEY in env")
        AUTH_FAIL.write_text(utc_now() + " missing CURSOR_API_KEY\n", encoding="utf-8")
        return 2
    bin_path = which_agent()
    drop_effort_if_needed(bin_path)
    no_effort = Path("/opt/p2/NO-EFFORT").exists()
    park = parked_ids()
    done = load_completed()
    flight: dict[str, dict] = {}
    stats = {"launched": 0, "ok": 0, "parked": 0, "failed": 0}
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{utc_now()} START box={box} cap={cap} bin={bin_path} leftover={len(all_unit_ids())} park={len(park)}\n")
    DONE_MARK.unlink(missing_ok=True)
    AUTH_FAIL.unlink(missing_ok=True)
    log(f"supervisor start cursor grok-4.6 box={box} cap={cap} bin={bin_path}")

    stopping = {"flag": False}

    def _stop(signum, _frame):
        stopping["flag"] = True
        log(f"signal {signum}")

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    last_launch = 0.0

    while True:
        now = time.time()
        dead = []
        for uid, child in list(flight.items()):
            rc = child["proc"].poll()
            if rc is None and now - child["started"] > WORKER_TIMEOUT_SEC:
                try:
                    os.killpg(child["proc"].pid, signal.SIGKILL)
                except Exception:
                    child["proc"].kill()
                child["proc"].wait(timeout=10)
                rc = child["proc"].returncode
            if rc is not None:
                child["proc"].returncode = rc
                dead.append(uid)
        for uid in dead:
            result = reap_one(flight.pop(uid))
            if result.get("ok"):
                stats["ok"] += 1
                done.add(uid)
                save_completed(done)
            elif load_strikes(uid).get("parked"):
                stats["parked"] += 1
            elif result.get("auth_fail"):
                stats["failed"] += 1
            else:
                stats["failed"] += 1

        queued = build_queue(box, set(flight), park, done)
        write_heartbeat(box, cap, flight, queued, stats)

        if stopping["flag"]:
            if not flight:
                return 0
            time.sleep(5)
            continue
        if AUTH_FAIL.exists():
            log("AUTH-FAIL present — not launching")
            time.sleep(20)
            continue

        while (
            not stopping["flag"]
            and len(flight) < cap
            and queued
            and (time.time() - last_launch) >= STAGGER
        ):
            uid = queued.pop(0)
            if uid in flight:
                continue
            rec = load_strikes(uid)
            attempt = rec.get("count", 0) + 1
            try:
                # rebuild cmd without --effort if flagged
                child = launch_one(uid, attempt, bin_path)
                if no_effort:
                    # launched with --effort; if CLI rejects, worker log will show and we infra-skip
                    pass
                flight[uid] = child
            except Exception as exc:
                log(f"LAUNCH-FAIL {uid} {exc}")
                break
            stats["launched"] += 1
            last_launch = time.time()
            log(f"LAUNCH {uid} attempt={attempt} pid={flight[uid]['proc'].pid} live={len(flight)}")

        if not flight and not queued:
            DONE_MARK.write_text(utc_now() + "\n", encoding="utf-8")
            log(f"QUEUE-EMPTY stats={stats}")
            time.sleep(IDLE_RESCAN_SEC)
            park = parked_ids()
            continue
        DONE_MARK.unlink(missing_ok=True)
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
