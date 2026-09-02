#!/usr/bin/env python3
"""Capped resource-exhaustion harness for ADV-0034.

Every vector runs under an explicit rlimit. Touching the host's own RAM,
disk, or process table is a harness failure, not a finding.
"""
from __future__ import annotations

import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CHILD = HERE / "_child.py"
WORK = HERE / "work"
UNIT = "ADV-0034"

JSON_AS_BYTES = 96 * 1024 * 1024
EXTRACT_AS_BYTES = 256 * 1024 * 1024
EXTRACT_FSIZE_BYTES = 8 * 1024 * 1024
BOMB_UNCOMPRESSED = 24 * 1024 * 1024
CPU_SECONDS = 20
HUGE_N = 10_000_000
CONTROL_N = 1_000
FANOUT_N = 500
FANOUT_CAP = 10
CHAIN_DEPTH = 80


def _status_map(pid: int) -> dict[str, str]:
    path = Path(f"/proc/{pid}/status")
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                out[key.strip()] = val.strip()
    except FileNotFoundError:
        return {}
    return out


def _kb(status: dict[str, str], key: str) -> int:
    raw = status.get(key, "0")
    return int(raw.split()[0])


def sample_proc(pid: int) -> dict[str, int] | None:
    st = _status_map(pid)
    if not st:
        return None
    fd_n = 0
    try:
        fd_n = len(list(Path(f"/proc/{pid}/fd").iterdir()))
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        fd_n = 0
    return {
        "pid": pid,
        "vm_size_kb": _kb(st, "VmSize"),
        "vm_rss_kb": _kb(st, "VmRSS"),
        "vm_peak_kb": _kb(st, "VmPeak"),
        "vm_data_kb": _kb(st, "VmData"),
        "threads": int(st.get("Threads", "0").split()[0]),
        "fd_count": fd_n,
    }


def _preexec(limits: dict[str, int]):
    def _apply() -> None:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if "cpu" in limits:
            cpu = int(limits["cpu"])
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        if "as" in limits:
            cap = int(limits["as"])
            resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
        if "fsize" in limits:
            cap = int(limits["fsize"])
            resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))

    return _apply


def run_child(
    job: str,
    payload: str,
    extra: str,
    limits: dict[str, int],
    *,
    timeout: float = 25.0,
    sample: bool = False,
) -> dict[str, Any]:
    cmd = [sys.executable, "-B", str(CHILD), job, payload, extra]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO / "tools"), str(REPO / "command-center" / "schema")]
    )
    t0 = time.monotonic()
    samples: list[dict[str, int]] = []
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=_preexec(limits),
    )
    try:
        if sample:
            while proc.poll() is None:
                row = sample_proc(proc.pid)
                if row is not None:
                    samples.append(row)
                if time.monotonic() - t0 > timeout:
                    proc.kill()
                    break
                time.sleep(0.01)
            stdout, stderr = proc.communicate(timeout=5)
        else:
            stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        rc = 124
        sig = None
    else:
        rc = proc.returncode
        sig = None
        if rc is not None and rc < 0:
            sig = -rc
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    peak = None
    if samples:
        peak = {
            "vm_size_kb": max(s["vm_size_kb"] for s in samples),
            "vm_rss_kb": max(s["vm_rss_kb"] for s in samples),
            "vm_peak_kb": max(s["vm_peak_kb"] for s in samples),
            "vm_data_kb": max(s["vm_data_kb"] for s in samples),
            "threads": max(s["threads"] for s in samples),
            "fd_count": max(s["fd_count"] for s in samples),
            "sample_count": len(samples),
        }
    parsed = None
    text = (stdout or "").strip()
    if text:
        try:
            parsed = json.loads(text.splitlines()[-1])
        except json.JSONDecodeError:
            parsed = None
    err = (stderr or "").strip()
    cap_trip = False
    if sig in {signal.SIGKILL, signal.SIGXFSZ, signal.SIGXCPU}:
        cap_trip = True
    if rc == 124:
        cap_trip = True
    if any(
        marker in err
        for marker in ("MemoryError", "File too large", "OSError", "ENOMEM")
    ):
        cap_trip = True
    if rc not in (0, None) and parsed is None and sig is not None:
        cap_trip = True
    app_bound = bool(parsed and parsed.get("app_bound"))
    completed_ok = rc == 0 and parsed is not None and parsed.get("ok") is True
    return {
        "job": job,
        "returncode": rc,
        "signal": sig,
        "signal_name": signal.Signals(sig).name if sig else None,
        "elapsed_ms": elapsed_ms,
        "stdout_tail": text[-2000:],
        "stderr_tail": err[-2000:],
        "parsed": parsed,
        "peak": peak,
        "cap_trip": cap_trip and not app_bound,
        "host_limit": False,
        "limits": limits,
        "completed_ok": completed_ok,
        "app_bound": app_bound,
    }


def ensure_fixtures() -> dict[str, str]:
    WORK.mkdir(parents=True, exist_ok=True)
    huge = WORK / "huge-array.json"
    small = WORK / "control-array.json"
    if not huge.is_file() or huge.stat().st_size < 1_000_000:
        huge.write_text("[" + ",".join(["0"] * HUGE_N) + "]", encoding="utf-8")
    if not small.is_file():
        small.write_text("[" + ",".join(["0"] * CONTROL_N) + "]", encoding="utf-8")

    import io
    import tarfile

    bomb = WORK / "gzip-bomb.tar.gz"
    if not bomb.is_file():
        with tarfile.open(bomb, "w:gz") as tf:
            info = tarfile.TarInfo("zeros.bin")
            info.size = BOMB_UNCOMPRESSED
            tf.addfile(info, io.BytesIO(b"\x00" * BOMB_UNCOMPRESSED))
    control_tar = WORK / "control.tar.gz"
    if not control_tar.is_file():
        blob = b"ok\n"
        with tarfile.open(control_tar, "w:gz") as tf:
            info = tarfile.TarInfo("ok.txt")
            info.size = len(blob)
            tf.addfile(info, io.BytesIO(blob))

    deep = WORK / "deep-subworkflows.json"
    if not deep.is_file():
        subs: dict[str, Any] = {}
        for i in range(1, CHAIN_DEPTH + 1):
            nxt = f"c{i + 1}"
            if i < CHAIN_DEPTH:
                stages = [{"id": f"s{i}", "type": "subworkflow", "subworkflow": nxt}]
            else:
                stages = [{"id": f"t{i}", "type": "task", "tools": ["t"]}]
            subs[f"c{i}"] = {
                "id": f"c{i}",
                "tools": ["t"],
                "stop_rule": {"max_stages": 3},
                "stages": stages,
            }
        deep.write_text(
            json.dumps(
                {
                    "id": "root",
                    "tools": ["t"],
                    "stop_rule": {"max_stages": 3},
                    "stages": [{"id": "s0", "type": "subworkflow", "subworkflow": "c1"}],
                    "subworkflows": subs,
                }
            ),
            encoding="utf-8",
        )

    cycle = WORK / "cyclic-subworkflows.json"
    if not cycle.is_file():
        cycle.write_text(
            json.dumps(
                {
                    "id": "root",
                    "tools": ["t"],
                    "stop_rule": {"max_stages": 3},
                    "stages": [{"id": "s", "type": "subworkflow", "subworkflow": "a"}],
                    "subworkflows": {
                        "a": {
                            "id": "a",
                            "tools": ["t"],
                            "stop_rule": {"max_stages": 3},
                            "stages": [
                                {"id": "s", "type": "subworkflow", "subworkflow": "b"}
                            ],
                        },
                        "b": {
                            "id": "b",
                            "tools": ["t"],
                            "stop_rule": {"max_stages": 3},
                            "stages": [
                                {"id": "s", "type": "subworkflow", "subworkflow": "a"}
                            ],
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

    control_wf = WORK / "control-workflow.json"
    if not control_wf.is_file():
        control_wf.write_text(
            json.dumps(
                {
                    "id": "root",
                    "tools": ["t"],
                    "stop_rule": {"max_stages": 3},
                    "stages": [{"id": "t0", "type": "task", "tools": ["t"]}],
                }
            ),
            encoding="utf-8",
        )

    return {
        "huge_json": str(huge),
        "small_json": str(small),
        "bomb": str(bomb),
        "control_tar": str(control_tar),
        "deep_wf": str(deep),
        "cycle_wf": str(cycle),
        "control_wf": str(control_wf),
        "extract_attack": str(WORK / "extract-attack"),
        "extract_control": str(WORK / "extract-control"),
    }


def classify_vector(row: dict[str, Any], *, expect: str) -> str:
    if row.get("host_limit"):
        return "HARNESS-FAIL-HOST-LIMIT"
    if expect == "app-bound":
        return "APP-BOUND" if row.get("app_bound") else "UNEXPECTED"
    if expect == "cap-trip":
        return (
            "CAP-TRIP-BEFORE-APP-BOUND"
            if row.get("cap_trip") and not row.get("app_bound")
            else "UNEXPECTED"
        )
    if expect == "complete":
        return "COMPLETE-INSIDE-CAP" if row.get("completed_ok") else "UNEXPECTED"
    return "UNEXPECTED"


def _slim(row: dict[str, Any], vector: str, class_: str, id_: str) -> dict[str, Any]:
    return {
        "id": id_,
        "vector": vector,
        "class": class_,
        "returncode": row.get("returncode"),
        "signal_name": row.get("signal_name"),
        "cap_trip": row.get("cap_trip"),
        "app_bound": row.get("app_bound"),
        "completed_ok": row.get("completed_ok"),
        "elapsed_ms": row.get("elapsed_ms"),
        "parsed": row.get("parsed"),
        "stderr_tail": (row.get("stderr_tail") or "")[-500:],
    }


def measure_probe1() -> dict[str, Any]:
    fx = ensure_fixtures()
    shutil.rmtree(fx["extract_attack"], ignore_errors=True)
    shutil.rmtree(fx["extract_control"], ignore_errors=True)

    control_json = run_child(
        "json_load",
        fx["small_json"],
        "",
        {"as": JSON_AS_BYTES, "cpu": CPU_SECONDS},
    )
    attack_json = run_child(
        "json_load",
        fx["huge_json"],
        "",
        {"as": JSON_AS_BYTES, "cpu": CPU_SECONDS},
    )
    control_tar = run_child(
        "extract",
        fx["control_tar"],
        fx["extract_control"],
        {"as": EXTRACT_AS_BYTES, "fsize": EXTRACT_FSIZE_BYTES, "cpu": CPU_SECONDS},
    )
    attack_tar = run_child(
        "extract",
        fx["bomb"],
        fx["extract_attack"],
        {"as": EXTRACT_AS_BYTES, "fsize": EXTRACT_FSIZE_BYTES, "cpu": CPU_SECONDS},
    )
    control_wf = run_child(
        "validate_wf",
        fx["control_wf"],
        "",
        {"as": EXTRACT_AS_BYTES, "cpu": CPU_SECONDS},
    )
    deep_wf = run_child(
        "validate_wf",
        fx["deep_wf"],
        "",
        {"as": EXTRACT_AS_BYTES, "cpu": CPU_SECONDS},
    )
    cycle_wf = run_child(
        "validate_wf",
        fx["cycle_wf"],
        "",
        {"as": EXTRACT_AS_BYTES, "cpu": CPU_SECONDS},
    )
    fanout_capped = run_child(
        "fanout_capped",
        str(FANOUT_N),
        str(FANOUT_CAP),
        {"as": EXTRACT_AS_BYTES, "cpu": CPU_SECONDS},
    )
    fanout_naive = run_child(
        "fanout_naive",
        str(FANOUT_N),
        str(FANOUT_CAP),
        {"as": EXTRACT_AS_BYTES, "cpu": CPU_SECONDS},
    )

    extracted_size = 0
    attack_dir = Path(fx["extract_attack"])
    if attack_dir.is_dir():
        for p in attack_dir.rglob("*"):
            if p.is_file():
                extracted_size += p.stat().st_size

    naive_parsed = fanout_naive.get("parsed") or {}
    capped_parsed = fanout_capped.get("parsed") or {}

    vectors = [
        _slim(control_json, "normal-size JSON array", classify_vector(control_json, expect="complete"), "V-control-json"),
        _slim(attack_json, "10^7-element JSON array via json.loads", classify_vector(attack_json, expect="cap-trip"), "V-json-1e7"),
        _slim(control_tar, "normal-size tar.gz via plugin._safe_extract", classify_vector(control_tar, expect="complete"), "V-control-tar"),
        _slim(attack_tar, "24 MiB zeros gzip tar via plugin._safe_extract", classify_vector(attack_tar, expect="cap-trip"), "V-gzip-bomb"),
        _slim(control_wf, "normal workflow validate_document", classify_vector(control_wf, expect="complete"), "V-control-wf"),
        _slim(deep_wf, "80 unique nested subworkflows", classify_vector(deep_wf, expect="app-bound"), "V-deep-subworkflow"),
        _slim(cycle_wf, "cyclic subworkflow A->B->A", classify_vector(cycle_wf, expect="app-bound"), "V-cyclic-subworkflow"),
        _slim(fanout_capped, "schedule_arrivals production cap", classify_vector(fanout_capped, expect="complete"), "V-fanout-production"),
        _slim(
            fanout_naive,
            "naive_burst known-broken twin (negative control)",
            "NEGATIVE-UNBOUNDED-TWIN" if naive_parsed.get("exceeds_cap") else "UNEXPECTED",
            "V-fanout-naive-negative",
        ),
    ]

    host_limit = False
    classes_ok = all(v["class"] not in {"UNEXPECTED", "HARNESS-FAIL-HOST-LIMIT"} for v in vectors)
    control_ok = (
        control_json.get("completed_ok")
        and control_tar.get("completed_ok")
        and control_wf.get("completed_ok")
        and fanout_capped.get("completed_ok")
    )
    json_unbounded = attack_json.get("cap_trip") and not attack_json.get("app_bound")
    tar_unbounded = attack_tar.get("cap_trip") and not attack_tar.get("app_bound")
    wf_bounded = bool(deep_wf.get("app_bound") and cycle_wf.get("app_bound"))
    fanout_bounded = bool(
        fanout_capped.get("completed_ok")
        and not capped_parsed.get("exceeds_cap")
        and naive_parsed.get("exceeds_cap")
    )
    passed = (
        (not host_limit)
        and classes_ok
        and control_ok
        and json_unbounded
        and tar_unbounded
        and wf_bounded
        and fanout_bounded
        and extracted_size <= EXTRACT_FSIZE_BYTES
    )
    return {
        "probe": "probe1-capped-ingest",
        "unit_id": UNIT,
        "pass": passed,
        "host_limit_reached": host_limit,
        "control_ok": bool(control_ok),
        "huge_n": HUGE_N,
        "json_as_bytes": JSON_AS_BYTES,
        "extract_fsize_bytes": EXTRACT_FSIZE_BYTES,
        "bomb_uncompressed": BOMB_UNCOMPRESSED,
        "extracted_attack_bytes": extracted_size,
        "json_unbounded_at_program": json_unbounded,
        "tar_unbounded_at_program": tar_unbounded,
        "subworkflow_app_bound": wf_bounded,
        "fanout_production_capped": fanout_bounded,
        "vectors": vectors,
    }


def _pack(name: str, row: dict[str, Any]) -> dict[str, Any]:
    peak = row.get("peak") or {}
    rss = int(peak.get("vm_rss_kb") or 0)
    vsz = int(peak.get("vm_size_kb") or 0)
    return {
        "id": name,
        "returncode": row.get("returncode"),
        "signal_name": row.get("signal_name"),
        "cap_trip": row.get("cap_trip"),
        "completed_ok": row.get("completed_ok"),
        "app_bound": row.get("app_bound"),
        "elapsed_ms": row.get("elapsed_ms"),
        "peak": peak,
        "commit_proxy_vm_size_kb": vsz,
        "working_set_vm_rss_kb": rss,
        "threads": peak.get("threads"),
        "fd_count": peak.get("fd_count"),
        "parsed": row.get("parsed"),
    }


def measure_probe2() -> dict[str, Any]:
    fx = ensure_fixtures()
    extract_dir = fx["extract_attack"] + "-p2"
    shutil.rmtree(extract_dir, ignore_errors=True)

    control = run_child(
        "json_load",
        fx["small_json"],
        "",
        {"as": JSON_AS_BYTES, "cpu": CPU_SECONDS},
        sample=True,
    )
    attack = run_child(
        "json_load",
        fx["huge_json"],
        "",
        {"as": JSON_AS_BYTES, "cpu": CPU_SECONDS},
        sample=True,
    )
    extract = run_child(
        "extract",
        fx["bomb"],
        extract_dir,
        {"as": EXTRACT_AS_BYTES, "fsize": EXTRACT_FSIZE_BYTES, "cpu": CPU_SECONDS},
        sample=True,
    )
    naive = run_child(
        "fanout_naive",
        str(FANOUT_N),
        str(FANOUT_CAP),
        {"as": EXTRACT_AS_BYTES, "cpu": CPU_SECONDS},
        sample=True,
    )
    capped = run_child(
        "fanout_capped",
        str(FANOUT_N),
        str(FANOUT_CAP),
        {"as": EXTRACT_AS_BYTES, "cpu": CPU_SECONDS},
        sample=True,
    )

    control_p = _pack("control-json", control)
    attack_p = _pack("json-1e7", attack)
    extract_p = _pack("gzip-bomb", extract)
    naive_p = _pack("fanout-naive", naive)
    capped_p = _pack("fanout-capped", capped)

    naive_threads = int(naive_p.get("threads") or 0)
    capped_threads = int(capped_p.get("threads") or 0)
    passed = (
        bool(control.get("completed_ok"))
        and bool(attack.get("cap_trip"))
        and bool(extract.get("cap_trip"))
        and naive.get("parsed") is not None
        and capped.get("parsed") is not None
        and naive_threads <= 8
        and capped_threads <= 8
    )
    return {
        "probe": "probe2-external-commit",
        "unit_id": UNIT,
        "pass": passed,
        "observer": (
            "parent samples /proc/<pid>/status VmSize (commit proxy), VmRSS "
            "(working set), Threads, and /proc/<pid>/fd while the child runs "
            "under the same rlimits as probe 1"
        ),
        "why_not_rss_only": (
            "The catalog names COMMIT exhaustion, not classic working-set OOM. "
            "Probe 2 therefore records VmSize from outside the process. For "
            "the arrival-scheduler vector, OS process counts stay flat: "
            "naive_burst does not fork. Sliding-window arrival count (probe 1) "
            "is the instrument that sees that twin."
        ),
        "control": control_p,
        "json_1e7": attack_p,
        "gzip_bomb": extract_p,
        "fanout_naive": naive_p,
        "fanout_capped": capped_p,
        "scheduler_thread_counts_flat": naive_threads <= 2 and capped_threads <= 2,
        "host_limit_reached": False,
    }


def dumps(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=1, sort_keys=True)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "probe1"
    doc = measure_probe1() if which == "probe1" else measure_probe2()
    print(dumps(doc))
    raise SystemExit(0 if doc.get("pass") else 1)
