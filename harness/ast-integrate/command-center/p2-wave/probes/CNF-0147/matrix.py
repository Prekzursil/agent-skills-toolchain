"""Four-cell confirmation matrix: egress × cache."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from egress import LocalOrigin, prove_block  # noqa: E402
from suite import GETPIP_PATH, all_tests, cache_file, classify_spec, getpip_url  # noqa: E402

CELLS = (
    ("open-cold", "open", "cold"),
    ("blocked-cold", "blocked", "cold"),
    ("blocked-warm", "blocked", "warm"),
    ("open-warm", "open", "warm"),
)


def _run_child(*, port: int, cache_dir: Path | None, blocked: bool, report: Path) -> dict:
    cmd = [
        sys.executable,
        "-B",
        str(HERE / "run_one.py"),
        "--port",
        str(port),
        "--cache-dir",
        "" if cache_dir is None else str(cache_dir),
        "--json-out",
        str(report),
    ]
    if blocked:
        cmd = ["unshare", "-rn", *cmd]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=90,
        env=env,
    )
    if proc.returncode != 0 or not report.is_file():
        raise RuntimeError(
            f"run_one failed rc={proc.returncode} blocked={blocked} "
            f"stdout={proc.stdout[-500:]!r} stderr={proc.stderr[-500:]!r}"
        )
    return json.loads(report.read_text(encoding="utf-8"))


def seed_warm_cache(cache_dir: Path, port: int) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    url = getpip_url(port)
    with urlopen(url, timeout=2) as resp:
        body = resp.read()
    dest = cache_file(cache_dir, url)
    dest.write_bytes(body)
    return {
        "url": url,
        "bytes": len(body),
        "path": str(dest),
        "sha256_prefix": __import__("hashlib").sha256(body).hexdigest()[:16],
    }


def by_id(results: list[dict]) -> dict[str, dict]:
    return {row["id"]: row for row in results}


def classify_matrix(cells: dict[str, dict]) -> dict:
    specs = {s.id: s for s in all_tests()}
    open_cold = by_id(cells["open-cold"]["results"])
    blocked_cold = by_id(cells["blocked-cold"]["results"])
    blocked_warm = by_id(cells["blocked-warm"]["results"])
    open_warm = by_id(cells["open-warm"]["results"])
    delta = []
    declared = []
    silent = []
    unknown = []
    cache_masked = []
    hermetic_ok = []
    for test_id, spec in specs.items():
        base = open_cold[test_id]
        bc = blocked_cold[test_id]
        bw = blocked_warm[test_id]
        ow = open_warm[test_id]
        green_net = bool(base["ok"])
        red_without = bool(base["ok"]) and not bool(bc["ok"])
        if green_net and bool(bc["ok"]):
            hermetic_ok.append(test_id)
            continue
        if red_without:
            cls = classify_spec(spec)
            row = {
                "test_id": test_id,
                "green_with_network": True,
                "red_without": True,
                "blocked_warm_ok": bool(bw["ok"]),
                "open_warm_ok": bool(ow["ok"]),
                "classification": cls,
                "connection_attempts": bc.get("attempts") or [],
                "declared_network": spec.declared_network,
                "claims_never_download": spec.claims_never_download,
            }
            delta.append(row)
            if cls == "declared-dependency":
                declared.append(test_id)
            elif cls == "silent-download":
                silent.append(test_id)
            else:
                unknown.append(test_id)
            if bool(bw["ok"]) and not bool(bc["ok"]):
                cache_masked.append(test_id)
            continue
        unknown.append(test_id)
    baseline_ids = sorted(k for k, v in open_cold.items() if v["ok"])
    restored_ids = sorted(k for k, v in open_warm.items() if v["ok"])
    return {
        "delta": delta,
        "attribution": {
            "declared_dependency": declared,
            "silent_download": silent,
            "unknown": unknown,
        },
        "hermetic_ok": hermetic_ok,
        "cache_masked": cache_masked,
        "both_states": {
            "baseline_pass_ids": baseline_ids,
            "restored_pass_ids": restored_ids,
            "baseline_restored": baseline_ids == restored_ids,
        },
    }


def run_matrix(work: Path | None = None) -> dict:
    specs = all_tests()
    origin = LocalOrigin()
    port = origin.start()
    tmp_owned = False
    if work is None:
        work = Path(tempfile.mkdtemp(prefix="cnf0147-"))
        tmp_owned = True
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    try:
        block = prove_block(port)
        if not block["pass"]:
            raise RuntimeError(f"egress block control failed: {block}")
        warm = work / "cache-warm"
        if warm.exists():
            shutil.rmtree(warm)
        seed = seed_warm_cache(warm, port)
        cells_raw = {}
        for cell_id, egress, cache in CELLS:
            # Cold cells must not see a store populated by an earlier open run.
            cache_dir = warm if cache == "warm" else None
            report = work / f"{cell_id}.json"
            payload = _run_child(
                port=port,
                cache_dir=cache_dir,
                blocked=(egress == "blocked"),
                report=report,
            )
            cells_raw[cell_id] = {
                "id": cell_id,
                "egress": egress,
                "cache": cache,
                "results": payload["results"],
            }
        classified = classify_matrix(cells_raw)
        return {
            "port": port,
            "block_control": block,
            "cache_seed": seed,
            "n_tests": len(specs),
            "runs": [cells_raw[c[0]] for c in CELLS],
            **classified,
        }
    finally:
        origin.stop()
        if tmp_owned:
            shutil.rmtree(work, ignore_errors=True)
