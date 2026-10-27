#!/usr/bin/env python3
"""Live probe re-runner, wave-4 shard-21 r2. Runs each named probe from repo root, records rc + tail."""
from __future__ import annotations
import json, os, subprocess, sys, time
from pathlib import Path

REPO = Path.home() / "p2-g1"
os.chdir(REPO)
BATTERY = json.loads((Path(__file__).resolve().parent / "battery-1.json").read_bytes().decode("utf-8"))
OUTL = Path(__file__).resolve().parent / "probe-results.jsonl"


def run_one(uid: str, cmd: str) -> dict:
    # translate "ENV=1 python3 -B path" -> [sys.executable, "-B", path] with env var set
    toks = cmd.split()
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    while toks and "=" in toks[0] and not toks[0].startswith("-"):
        k, v = toks[0].split("=", 1)
        env[k] = v
        toks = toks[1:]
    if toks and (toks[0] in ("python", "python3", "py")):
        toks[0] = sys.executable
    t0 = time.time()
    try:
        p = subprocess.run(toks, cwd=str(REPO), env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
        rc, out, err, how = p.returncode, p.stdout, p.stderr, "ran"
    except subprocess.TimeoutExpired:
        rc, out, err, how = -999, "", "TIMEOUT after 900s", "timeout"
    except Exception as e:
        rc, out, err, how = -998, "", type(e).__name__ + ": " + str(e)[:300], "spawn-error"
    dur = round(time.time() - t0, 2)
    return {"unit": uid, "cmd_tail": " ".join(toks[-2:]), "rc": rc, "dur_s": dur, "how": how,
            "stdout_tail": out[-400:], "stderr_tail": err[-400:]}


def main() -> int:
    rows = []
    for uid, row in BATTERY.items():
        for c in row.get("probe_commands", []):
            r = run_one(uid, c)
            rows.append(r)
            print(json.dumps(r), flush=True)
    OUTL.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    bad = [r for r in rows if r["rc"] != 0]
    print(f"SUCCESS:probes {len(rows)-len(bad)}/{len(rows)} exit0" if not bad
          else f"FAILED:probes {len(bad)}/{len(rows)} nonzero: " + ", ".join(r['unit']+':'+str(r['rc']) for r in bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
