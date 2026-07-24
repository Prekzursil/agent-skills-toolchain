# Databricks notebook source
import os, json
dbutils.widgets.text("batch_json", "/dbfs/tmp/codex-batch/batch.json")
dbutils.widgets.text("result_dir", "/dbfs/tmp/codex-batch/results")
dbutils.widgets.text("scope", "codex-harness-prekzursil")
dbutils.widgets.text("stagger_s", "3.0")
# The subject bundle is now a WIDGET, defaulting to the historical path so every existing caller
# behaves exactly as before. It was previously hardcoded, which is how an entire campaign (604
# units) silently judged from option cards against a STALE bundle from a different program — the
# runner cannot tell a wrong subject from a right one, so the caller must be able to name it.
dbutils.widgets.text("bundle_tgz", "/dbfs/tmp/codex-batch/harness-bundle.tar.gz")
os.environ["BATCH_JSON"] = dbutils.widgets.get("batch_json")
os.environ["RESULT_DIR"] = dbutils.widgets.get("result_dir")
os.environ["BATCH_STAGGER_S"] = dbutils.widgets.get("stagger_s")
os.environ["BUNDLE_TGZ"] = dbutils.widgets.get("bundle_tgz")
_AUTH = dbutils.secrets.get(scope=dbutils.widgets.get("scope"), key="auth_json")

from __future__ import annotations

import concurrent.futures as cf
import json
import os
import subprocess
import time

# Injected by the caller via notebook widgets / params.
BATCH_JSON = os.environ.get("BATCH_JSON", "/dbfs/tmp/codex-batch/batch.json")
BUNDLE_TGZ = os.environ.get("BUNDLE_TGZ", "/dbfs/tmp/codex-batch/harness-bundle.tar.gz")
RESULT_DIR = os.environ.get("RESULT_DIR", "/dbfs/tmp/codex-batch/results")
WORK = "/local_disk0/codexwork"
NODE_V = "v22.11.0"
CONCURRENCY = int(os.environ.get("BATCH_CONCURRENCY", "0"))  # 0 = auto from RAM


def sh(cmd, timeout=900, cwd=None):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True,
                           timeout=timeout, cwd=cwd)
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "", f"TIMEOUT after {timeout}s"
    except Exception as e:  # never let a setup failure look like a unit failure
        return 125, "", f"EXC {e}"


def setup():
    """Install node + codex and restore auth. Returns (ok, info)."""
    info = {}
    os.makedirs(WORK, exist_ok=True)

    rc, out, err = sh("uname -m")
    arch = (out or "").strip()
    tarch = {"x86_64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(arch)
    info["arch"] = arch
    if not tarch:
        return False, {**info, "error": f"unsupported arch {arch!r}"}

    rc, out, err = sh(
        f"set -e; curl -fsSL https://nodejs.org/dist/{NODE_V}/node-{NODE_V}-linux-{tarch}.tar.xz "
        f"-o /tmp/n.tar.xz; mkdir -p /opt/n; tar -xf /tmp/n.tar.xz -C /opt/n --strip-components=1; "
        f"/opt/n/bin/node --version", timeout=420)
    info["node"] = (out or err).strip()[-40:]
    if rc != 0:
        return False, {**info, "error": "node install failed", "stderr": err[-300:]}

    rc, out, err = sh("export PATH=/opt/n/bin:$PATH; npm install -g @openai/codex 2>&1 | tail -2",
                      timeout=900)
    rc2, out2, _ = sh("export PATH=/opt/n/bin:$PATH; codex --version")
    info["codex"] = (out2 or "").strip()
    if rc2 != 0:
        return False, {**info, "error": "codex install failed", "npm_tail": out[-300:]}
    return True, info


def restore_auth(auth_json_text):
    d = os.path.expanduser("~/.codex")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "auth.json")
    with open(p, "w") as fh:
        fh.write(auth_json_text)
    os.chmod(p, 0o600)
    return os.path.getsize(p)


def unpack_bundle():
    """Unpack the harness bundle so units can READ the subject. 2.99 MB / 617 files."""
    if not os.path.exists(BUNDLE_TGZ):
        return {"bundle": "ABSENT -- units that read the harness will fail honestly",
                "tgz": BUNDLE_TGZ}
    dest = os.path.join(WORK, "bundle")
    os.makedirs(dest, exist_ok=True)
    rc, out, err = sh(f"tar -xzf {BUNDLE_TGZ} -C {dest}", timeout=180)
    n = sum(len(f) for _, _, f in os.walk(dest))
    # Report WHICH archive was unpacked and its size, not just the extract dir. A wrong subject
    # is otherwise invisible: the runner unpacks whatever it is given and every unit then judges
    # confidently against the wrong tree.
    return {"bundle": dest, "files": n, "rc": rc, "tgz": BUNDLE_TGZ,
            "tgz_bytes": os.path.getsize(BUNDLE_TGZ),
            "top_level": sorted(os.listdir(dest))[:10]}


def run_unit(u, start_delay=0.0):
    """Execute ONE unit. Returns a terminal-state record. Never raises.

    start_delay staggers the launch. MEASURED 2026-07-19, batch-01: at concurrency 180 every one
    of 120 failures was `429 Too Many Requests -- exceeded retry limit`, and every one died at
    37-41s, i.e. they all fired at t=0, hit the same rate window, burned codex's internal retries
    together, and gave up together. The 60 survivors were pristine. A thundering herd, not a
    capacity problem: the node still had 228.9 GB free and the units themselves were fine.

    Spreading starts converts a simultaneous burst into a rolling one, so the rate limiter sees a
    sustainable arrival rate instead of a spike.
    """
    uid = u["id"]
    wd = os.path.join(WORK, uid)
    if start_delay:
        time.sleep(start_delay)
    t0 = time.time()
    try:
        os.makedirs(wd, exist_ok=True)
        pf = os.path.join(wd, "prompt.txt")
        with open(pf, "w", encoding="utf-8") as fh:
            fh.write(u["prompt"])

        art = os.path.join(RESULT_DIR, uid + ".md")
        os.makedirs(RESULT_DIR, exist_ok=True)

        # Rewrite the artifact path: the unit prompt names a Windows path that does not exist here.
        # Without this every unit writes into the void and the AND-gate correctly fails all of them.
        with open(pf, "a", encoding="utf-8") as fh:
            fh.write(f"\n\n# REMOTE OVERRIDE -- you are running on a Linux job node, NOT the Windows box.\n"
                     f"# Write your artifact to EXACTLY this path instead of any Windows path above:\n"
                     f"#   {art}\n"
                     f"# The harness subject tree is unpacked read-only at: {os.path.join(WORK,'bundle')}\n"
                     f"# Windows-only paths (C:\\...) do NOT exist here. If your unit REQUIRES them,\n"
                     f"# say so plainly in the artifact and stop -- do not fabricate their contents.\n")

        cmd = ("export PATH=/opt/n/bin:$PATH; "
               f"cd {wd} && codex exec --cd {wd} --skip-git-repo-check --ignore-user-config "
               "--dangerously-bypass-approvals-and-sandbox "
               '-c "tools.web_search=true" -c "mcp_servers={}" '
               # REASONING EFFORT MUST BE PASSED EXPLICITLY.
               # --ignore-user-config discards $CODEX_HOME/config.toml (its own --help says
               # so), and that file is where model_reasoning_effort = "ultra" is pinned. So
               # every unit dispatched before 2026-07-20 silently ran at the CLI DEFAULT,
               # not at the owner's pinned tier -- a quality gap across ~120 units that no
               # flag-reading would reveal, because the flag we passed was correct and the
               # setting we relied on was simply gone.
               # Verified on codex-cli 0.144.6: "ultra" is ACCEPTED (rc=0), while a bogus
               # value is rejected with the API's own enum
               # ('none','minimal','low','medium','high','xhigh','max') -- so the CLI
               # translates "ultra" rather than passing it through. UNVERIFIED which API
               # tier it maps to; 'max' is the API ceiling, so if ultra maps below it the
               # true maximum would be 'max'. Settle by instrumenting the outbound request.
               '-c model_reasoning_effort="ultra" '
               f"-o {wd}/last.json --model gpt-5.6-sol - < {pf}")
        rc, out, err = sh(cmd, timeout=int(u.get("timeout_s", 2400)))

        # AND-gate, identical to the local runner: exit code alone is not evidence.
        ok = False
        size = 0
        if os.path.exists(art):
            size = os.path.getsize(art)
            if size >= 1024:
                with open(art, "r", encoding="utf-8", errors="replace") as fh:
                    ok = "UNIT-COMPLETE" in fh.read()[-600:]

        if rc == 0 and ok:
            state = f"SUCCESS:{uid}"
        elif rc != 0 and not os.path.exists(art):
            state = f"FAILED:{uid} codex-exit-{rc}"
        elif rc == 0 and not os.path.exists(art):
            state = f"FAILED:{uid} severed-stream"
        else:
            state = f"FAILED:{uid} no-sentinel-or-too-small"

        return {"id": uid, "state": state, "sec": round(time.time() - t0, 1),
                "bytes": size, "rc": rc, "tail": (err or out)[-400:] if not ok else ""}
    except Exception as e:
        return {"id": uid, "state": f"FAILED:{uid} runner-exception",
                "sec": round(time.time() - t0, 1), "bytes": 0, "rc": -1, "tail": str(e)[:400]}


def main():
    t0 = time.time()
    result = {"host": {}, "setup": {}, "units": []}

    free_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_AVPHYS_PAGES") / 1e9
    total_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
    cpus = os.cpu_count() or 4
    result["host"] = {"total_gb": round(total_gb, 1), "free_gb": round(free_gb, 1), "cpus": cpus}

    ok, info = setup()
    result["setup"] = info
    if not ok:
        result["fatal"] = "setup failed"
        return result

    result["setup"]["bundle"] = unpack_bundle()

    with open(BATCH_JSON, "r", encoding="utf-8") as fh:
        batch = json.load(fh)
    units = batch["units"]
    result["setup"]["auth_bytes"] = restore_auth(_AUTH)
    result["batch_size"] = len(units)

    # Concurrency from MEASURED per-unit cost (~236 MB), floored so a small node still works, and
    # capped at the unit count -- more workers than units is pure waste, a lesson from the local run
    # where the ramp had to be clamped to units_remaining.
    conc = CONCURRENCY or max(4, min(len(units), int((free_gb - 2) / 0.30), cpus * 8))
    result["concurrency"] = conc

    # Stagger the launches. STAGGER_S seconds between starts spreads a batch of 60 over ~3 minutes
    # of arrival time instead of firing all 60 into the same rate window. Overridable so the
    # ceiling can be probed empirically rather than guessed.
    stagger = float(os.environ.get("BATCH_STAGGER_S", "3.0"))
    result["stagger_s"] = stagger
    result["arrival_window_s"] = round(stagger * max(0, len(units) - 1), 1)

    futures = []
    with cf.ThreadPoolExecutor(max_workers=conc) as ex:
        for i, u in enumerate(units):
            futures.append(ex.submit(run_unit, u, i * stagger))
        for f in cf.as_completed(futures):
            try:
                result["units"].append(f.result())
            except Exception as e:  # a worker must never take the batch down with it
                result["units"].append({"id": "?", "state": "FAILED:? executor-exception",
                                        "sec": 0, "bytes": 0, "rc": -1, "tail": str(e)[:300]})

    # Rate-limit visibility: a 429 cluster is the signal that the stagger is still too tight, and
    # it must be readable from the summary without pulling every artifact.
    r429 = sum(1 for r in result["units"] if "429" in (r.get("tail") or ""))
    result["rate_limited"] = r429

    result["elapsed_s"] = round(time.time() - t0, 1)
    result["success"] = sum(1 for r in result["units"] if r["state"].startswith("SUCCESS"))
    result["failed"] = len(result["units"]) - result["success"]

    os.makedirs(RESULT_DIR, exist_ok=True)
    with open(os.path.join(RESULT_DIR, "_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    return result


_r = main()
_slim = {k: v for k, v in _r.items() if k != "units"}
_slim["units_n"] = len(_r.get("units", []))
_slim["failures"] = [{"id": x["id"], "state": x["state"], "sec": x["sec"]} for x in _r.get("units", []) if x["state"].startswith("FAILED")][:80]
dbutils.notebook.exit(json.dumps(_slim))
