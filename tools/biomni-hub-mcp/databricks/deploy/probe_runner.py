"""Phase-1 plumbing proof runner for biomni-hub Databricks adapter.

Runs as a Databricks Jobs ``spark_python_task`` on an ephemeral single-node
cluster. Proves, with REAL evidence, that:
  1. our submitted code executes on the bolt-datascience workspace's compute;
  2. pip on that compute can reach PyPI and install ``biomni`` (reduced);
  3. ``import biomni`` succeeds and reports a version.

It writes a JSON result to a DBFS path the caller downloads afterwards, and
also echoes everything to driver stdout (captured in the run logs).

NOT a biomni agent task -- no data lake download, no A1().go(). Just plumbing.
"""
import sys
import json
import time
import platform
import subprocess

RESULT_PATH = "/dbfs/tmp/biomni-hub/probe_result.json"

result = {
    "marker": "BIOMNI_HUB_PHASE1_PROOF",
    "ts_start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "python_version": sys.version,
    "python_executable": sys.executable,
    "machine": platform.machine(),
    "platform": platform.platform(),
    "processor": platform.processor(),
}


def _run(cmd, timeout):
    t0 = time.time()
    try:
        p = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=timeout,
        )
        return p.returncode, p.stdout, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return 124, (e.output or "") + "\n<TIMEOUT>", time.time() - t0


# --- Step 1: prove PyPI reachability + that biomni exists for this platform ---
rc_v, out_v, dt_v = _run(
    [sys.executable, "-m", "pip", "index", "versions", "biomni"], 120
)
result["pip_index_rc"] = rc_v
result["pip_index_tail"] = out_v[-1500:]
result["pip_index_secs"] = round(dt_v, 1)

# --- Step 2: install reduced biomni ---
rc_i, out_i, dt_i = _run(
    [sys.executable, "-m", "pip", "install", "--quiet",
     "--disable-pip-version-check", "biomni"], 1500
)
result["pip_install_rc"] = rc_i
result["pip_install_tail"] = out_i[-3000:]
result["pip_install_secs"] = round(dt_i, 1)

# --- Step 3: import biomni + report version ---
import importlib
importlib.invalidate_caches()
try:
    import biomni  # noqa: E402
    result["biomni_import"] = "OK"
    result["biomni_version"] = getattr(biomni, "__version__", "unknown")
    result["biomni_file"] = getattr(biomni, "__file__", "?")
    try:
        import biomni.agent  # noqa: E402
        result["biomni_agent_import"] = "OK"
        result["biomni_agent_has_A1"] = hasattr(biomni.agent, "A1")
    except Exception as e:  # noqa: BLE001
        result["biomni_agent_import"] = f"FAILED: {type(e).__name__}: {e}"
except Exception as e:  # noqa: BLE001
    result["biomni_import"] = f"FAILED: {type(e).__name__}: {e}"
    result["biomni_version"] = None

result["ts_end"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
result["overall"] = (
    "SUCCESS"
    if result.get("biomni_import") == "OK" and rc_i == 0
    else "PARTIAL/FAILED"
)

blob = json.dumps(result, indent=2)
print("=== BIOMNI_HUB_PHASE1_PROOF BEGIN ===")
print(blob)
print("=== BIOMNI_HUB_PHASE1_PROOF END ===")

try:
    import os
    os.makedirs("/dbfs/tmp/biomni-hub", exist_ok=True)
    with open(RESULT_PATH, "w") as fh:
        fh.write(blob)
    print(f"wrote result to {RESULT_PATH}")
except Exception as e:  # noqa: BLE001
    print(f"WARN could not write DBFS result: {e}")
