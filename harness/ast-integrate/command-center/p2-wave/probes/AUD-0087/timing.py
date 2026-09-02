"""AUD-0087 startup-latency measurement primitives.

Cold install on this estate is a fresh ``python3 -m venv --without-pip`` prefix
plus a current-source copy of ``tools/plugin`` into that prefix's site-packages.
``pip`` / ``ensurepip`` are absent, so a wheel rebuild is recorded as
NOT-CHECKED rather than invented.

Contention detectors (mechanically different from “any other process exists”):
  * 1-minute load average versus nproc
  * /proc/loadavg runnable count versus nproc
A known other-job mutant fixture must be discarded; a zero-job fixture must
be accepted. Sibling Cursor agents are recorded as diagnostics and are not a
discard reason — process-presence discarded every sample on a parallel
p2-wave host even when load/nproc was far below 1.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN_SRC = REPO / "tools" / "plugin"
FIXTURE_TREE = HERE / "fixtures" / "tiny-tree"
ZERO_JOB = HERE / "fixtures" / "host-zero-job.json"
OTHER_JOB = HERE / "fixtures" / "host-other-job.json"
NEEDED = 9
MAX_ATTEMPTS = 18

IMPORT_PROBE = """\
import json
import time

t0 = time.perf_counter()
import plugin
t_plugin = time.perf_counter()
import plugin.backup
import plugin.census
import plugin.forbidden_scan
import plugin.interpreters
import plugin.launcher
import plugin.projection
import plugin.secret_gate
t1 = time.perf_counter()
print(
    json.dumps(
        {
            "plugin_ms": (t_plugin - t0) * 1000.0,
            "payload_ms": (t1 - t0) * 1000.0,
        }
    )
)
"""

SKIP_DIR_NAMES = {"__pycache__", "tests", ".git"}


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def median(xs: list[float]) -> float:
    if not xs:
        raise ValueError("median of empty")
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


def spread(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"min": 0.0, "max": 0.0, "range": 0.0}
    lo, hi = min(xs), max(xs)
    return {"min": float(lo), "max": float(hi), "range": float(hi - lo)}


def pip_available() -> dict[str, Any]:
    rc, out = _run([sys.executable, "-m", "pip", "--version"])
    ensure = _run([sys.executable, "-c", "import ensurepip"])
    return {
        "pip_module": rc == 0,
        "pip_version": out.strip() if rc == 0 else "",
        "ensurepip": ensure[0] == 0,
        "install_method": "venv-without-pip-plus-current-source-copy",
    }


def plugin_py_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_current_source(src: Path, dest: Path) -> list[dict[str, Any]]:
    dest.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for path in plugin_py_files(src):
        rel = path.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        src_sha = sha256_file(path)
        dst_sha = sha256_file(target)
        rows.append(
            {
                "rel": rel.as_posix(),
                "src_sha256": src_sha,
                "dst_sha256": dst_sha,
                "match": src_sha == dst_sha,
            }
        )
    schema_src = src / "schema"
    if schema_src.is_dir():
        schema_dest = dest / "schema"
        schema_dest.mkdir(parents=True, exist_ok=True)
        for path in sorted(schema_src.glob("*.json")):
            shutil.copy2(path, schema_dest / path.name)
    return rows


def site_packages(venv: Path) -> Path:
    lib = venv / "lib"
    found = sorted(lib.glob("python*/site-packages"))
    if not found:
        raise FileNotFoundError(f"no site-packages under {venv}")
    return found[0]


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=60,
            env=child_env(),
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def live_snapshot(exclude_pids: set[int] | None = None) -> dict[str, Any]:
    exclude_pids = set(exclude_pids or ())
    exclude_pids.add(os.getpid())
    exclude_pids.add(os.getppid())
    raw = Path("/proc/loadavg").read_text(encoding="utf-8").split()
    load1, load5, load15 = float(raw[0]), float(raw[1]), float(raw[2])
    runnable_s, _slash, total_s = raw[3].partition("/")
    nproc = os.cpu_count() or 1
    sibling = 0
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        pid = int(proc.name)
        if pid in exclude_pids:
            continue
        try:
            cmd = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode(
                "utf-8", "replace"
            )
        except OSError:
            continue
        if "cursor-agent" in cmd or "/root/.local/bin/agent " in cmd:
            sibling += 1
    return {
        "load1": load1,
        "load5": load5,
        "load15": load15,
        "nproc": int(nproc),
        "procs_running": int(runnable_s),
        "procs_total": int(total_s or "0"),
        "sibling_agent_count": sibling,
        "detectors": ["load1_vs_nproc", "procs_running_vs_nproc"],
        "retired_detector": "any-other-process-presence",
    }


def contention_reason(snap: dict[str, Any]) -> str | None:
    nproc = max(int(snap.get("nproc") or 1), 1)
    load1 = float(snap.get("load1") or 0.0)
    running = int(snap.get("procs_running") or 0)
    if load1 > nproc:
        return f"load1={load1} exceeds nproc={nproc}"
    if running > nproc + 4:
        return f"procs_running={running} exceeds nproc+4={nproc + 4}"
    return None


def is_contended(snap: dict[str, Any]) -> bool:
    return contention_reason(snap) is not None


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def both_states_contention_control() -> dict[str, Any]:
    bad = load_fixture(OTHER_JOB)
    good = load_fixture(ZERO_JOB)
    bad_reason = contention_reason(bad)
    good_reason = contention_reason(good)
    fired = bad_reason is not None
    silent = good_reason is None
    return {
        "id": "AUD0087-C1",
        "kind": "load-and-runqueue-contention",
        "description": (
            "A known other-job mutant (oversubscribed load1 and runnable "
            "queue) must be discarded; an otherwise identical zero-job "
            "fixture must be accepted. Load is recorded with every live "
            "sample. Process-presence of sibling agents is diagnostic only."
        ),
        "fired_on_bad_state": fired,
        "silent_on_good_state": silent,
        "pass": fired and silent,
        "bad_state": bad,
        "bad_reason": bad_reason,
        "good_state": good,
        "good_reason": good_reason,
        "detectors": ["load1_vs_nproc", "procs_running_vs_nproc"],
    }


def run_one_sample(label: str = "sample") -> dict[str, Any]:
    snap0 = live_snapshot()
    prefix = Path(tempfile.mkdtemp(prefix="aud0087-"))
    phases: dict[str, float] = {}
    hashes: list[dict[str, Any]] = []
    import_stmt: dict[str, Any] = {}
    cmd_rc = -1
    cmd_out = ""
    try:
        t_all0 = time.perf_counter()

        t0 = time.perf_counter()
        py = sys.executable
        venv = prefix / "venv"
        helper = prefix / "import_probe.py"
        t1 = time.perf_counter()
        phases["resolve_ms"] = (t1 - t0) * 1000.0

        t0 = time.perf_counter()
        rc, out = _run([py, "-m", "venv", "--without-pip", str(venv)])
        if rc != 0:
            raise RuntimeError(f"venv failed rc={rc}: {out[-500:]}")
        sp = site_packages(venv)
        dest = sp / "plugin"
        hashes = copy_current_source(PLUGIN_SRC, dest)
        helper.write_text(IMPORT_PROBE, encoding="utf-8")
        t1 = time.perf_counter()
        phases["install_ms"] = (t1 - t0) * 1000.0

        vpy = venv / "bin" / "python3"
        t0 = time.perf_counter()
        rc, out = _run([str(vpy), str(helper)])
        t1 = time.perf_counter()
        phases["import_process_ms"] = (t1 - t0) * 1000.0
        if rc != 0:
            raise RuntimeError(f"first import failed rc={rc}: {out[-500:]}")
        import_stmt = json.loads(out.splitlines()[0])

        t0 = time.perf_counter()
        rc, out = _run([str(vpy), "-m", "plugin.census", str(FIXTURE_TREE)])
        t1 = time.perf_counter()
        phases["execute_ms"] = (t1 - t0) * 1000.0
        cmd_rc = rc
        cmd_out = out[-400:]
        if rc != 0:
            raise RuntimeError(f"first command failed rc={rc}: {out[-500:]}")

        t_all1 = time.perf_counter()
        phases["total_ms"] = (t_all1 - t_all0) * 1000.0
        snap1 = live_snapshot()
        reason0 = contention_reason(snap0)
        reason1 = contention_reason(snap1)
        reason = reason0 or reason1
        match = all(row["match"] for row in hashes) and bool(hashes)
        return {
            "label": label,
            "accepted": reason is None and match and cmd_rc == 0,
            "discarded": reason is not None,
            "discard_reason": reason,
            "source_match": match,
            "hash_rows": len(hashes),
            "hash_mismatches": [r["rel"] for r in hashes if not r["match"]],
            "cold_install_ms": phases["install_ms"],
            "resolve_ms": phases["resolve_ms"],
            "first_import_process_ms": phases["import_process_ms"],
            "first_import_statement_ms": float(import_stmt.get("payload_ms") or 0.0),
            "first_import_plugin_stmt_ms": float(import_stmt.get("plugin_ms") or 0.0),
            "first_command_process_ms": phases["execute_ms"],
            "phases": phases,
            "load_before": snap0,
            "load_after": snap1,
            "command_exit": cmd_rc,
            "pip": pip_available(),
        }
    finally:
        shutil.rmtree(prefix, ignore_errors=True)


def collect_samples(needed: int = NEEDED, max_attempts: int = MAX_ATTEMPTS) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    discarded: list[dict[str, Any]] = []
    errors: list[str] = []
    for i in range(1, max_attempts + 1):
        try:
            row = run_one_sample(label=f"s{i:02d}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")
            continue
        if row.get("accepted"):
            accepted.append(row)
        else:
            discarded.append(row)
        if len(accepted) >= needed:
            break
    return {
        "needed": needed,
        "attempts": len(accepted) + len(discarded),
        "accepted": accepted,
        "discarded": discarded,
        "errors": errors,
        "enough": len(accepted) >= needed,
    }


def summarize(collection: dict[str, Any]) -> dict[str, Any]:
    acc = collection["accepted"]
    keys = (
        "cold_install_ms",
        "resolve_ms",
        "first_import_process_ms",
        "first_import_statement_ms",
        "first_command_process_ms",
    )
    metrics: dict[str, Any] = {}
    for key in keys:
        xs = [float(r[key]) for r in acc]
        name = key[: -len("_ms")] if key.endswith("_ms") else key
        metrics[f"{name}_median_ms"] = median(xs) if xs else None
        sp = spread(xs)
        metrics[f"{name}_range_ms"] = sp
    return {
        "accepted_samples": len(acc),
        "discarded_samples": len(collection["discarded"]),
        "attempts": collection["attempts"],
        "errors": collection["errors"],
        "enough": collection["enough"],
        "metrics": metrics,
        "pip": pip_available(),
        "install_command": [
            "python3 -m venv --without-pip $PREFIX",
            "cp current-source tools/plugin/*.py $PREFIX/lib/python*/site-packages/plugin/",
            "$PREFIX/bin/python3 import_probe.py",
            "$PREFIX/bin/python3 -m plugin.census <tiny-tree>",
        ],
    }


def phase_attribution_ok(sample: dict[str, Any]) -> tuple[bool, str]:
    phases = sample.get("phases") or {}
    needed = ("resolve_ms", "install_ms", "import_process_ms", "execute_ms", "total_ms")
    missing = [k for k in needed if k not in phases]
    if missing:
        return False, f"missing phases {missing}"
    vals = [float(phases[k]) for k in needed]
    if any(v < 0 for v in vals):
        return False, "negative phase"
    if any(float(phases[k]) <= 0 for k in ("install_ms", "import_process_ms", "execute_ms")):
        return False, "non-positive install/import/execute"
    total = float(phases["total_ms"])
    summed = (
        float(phases["resolve_ms"])
        + float(phases["install_ms"])
        + float(phases["import_process_ms"])
        + float(phases["execute_ms"])
    )
    if total <= 0:
        return False, "total_ms not positive"
    # Parent bookkeeping sits outside the four phases; require coverage, not equality.
    if summed > total * 1.25:
        return False, f"sum {summed} exceeds total {total}"
    if summed < total * 0.50:
        return False, f"sum {summed} far below total {total}"
    return True, "ok"


def headline_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    m = summary["metrics"]
    return {
        "baseline_disposition": "CHECKED" if summary["enough"] else "NOT-CHECKED",
        "accepted_samples": summary["accepted_samples"],
        "discarded_samples": summary["discarded_samples"],
        "cold_install_median_ms": m["cold_install_median_ms"],
        "cold_install_range_ms": m["cold_install_range_ms"],
        "first_import_process_median_ms": m["first_import_process_median_ms"],
        "first_import_process_range_ms": m["first_import_process_range_ms"],
        "first_import_statement_median_ms": m["first_import_statement_median_ms"],
        "first_import_statement_range_ms": m["first_import_statement_range_ms"],
        "first_command_process_median_ms": m["first_command_process_median_ms"],
        "first_command_process_range_ms": m["first_command_process_range_ms"],
        "resolve_median_ms": m["resolve_median_ms"],
        "pip_available": summary["pip"]["pip_module"],
        "ensurepip_available": summary["pip"]["ensurepip"],
        "install_method": summary["pip"]["install_method"],
    }
