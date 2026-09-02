"""Live both-states runner for TST-0129.

Spawns `install.py` and `index_hash.py` as separate processes. Captures
(exit, stderr) as signal (a) and the independent directory sha256 as signal (b).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dns_udp import UdpResolver  # noqa: E402
from http_stub import RegistryHttp  # noqa: E402
from install import HOST_DEFAULT, MARKER_CACHE  # noqa: E402

PY = sys.executable
INSTALL = HERE / "install.py"
HASHER = HERE / "index_hash.py"


def _install_env() -> dict:
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "NO_PROXY": "*",
        "no_proxy": "*",
    }
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(key, None)
    return env


def run_hashed(index_dir: Path) -> dict:
    p = subprocess.run(
        [PY, "-B", str(HASHER), str(index_dir)],
        cwd=str(HERE),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if p.returncode != 0:
        raise RuntimeError(f"index_hash rc={p.returncode} {(p.stderr or p.stdout)[:400]}")
    doc = json.loads((p.stdout or "").strip().splitlines()[-1])
    doc["hasher_pid"] = doc.get("pid")
    doc["parent_pid"] = os.getpid()
    return doc


def run_install(
    index_dir: Path,
    resolver_ip: str,
    resolver_port: int,
    http_port: int,
    dns_fail_mode: str = "abort",
    timeout: float = 0.6,
) -> dict:
    p = subprocess.run(
        [
            PY,
            "-B",
            str(INSTALL),
            "--host",
            HOST_DEFAULT,
            "--resolver",
            resolver_ip,
            "--resolver-port",
            str(resolver_port),
            "--http-port",
            str(http_port),
            "--index-dir",
            str(index_dir),
            "--timeout",
            str(timeout),
            "--dns-fail-mode",
            dns_fail_mode,
        ],
        cwd=str(HERE),
        capture_output=True,
        text=True,
        timeout=30,
        env=_install_env(),
    )
    return {
        "returncode": p.returncode,
        "stdout": p.stdout or "",
        "stderr": p.stderr or "",
        "dns_fail_mode": dns_fail_mode,
    }


def fail_closed_holds(install_run: dict, before: dict, after: dict, resolver: str) -> dict:
    text = install_run["stderr"] + install_run["stdout"]
    host_named = HOST_DEFAULT in text
    resolver_named = resolver in text and "resolver" in text.lower()
    nonzero = int(install_run["returncode"]) != 0
    unchanged = before["sha256"] == after["sha256"] and before["files"] == after["files"]
    independent = before.get("pid") != os.getpid() and after.get("pid") != os.getpid()
    return {
        "nonzero_exit": nonzero,
        "host_named": host_named,
        "resolver_named": resolver_named,
        "index_unchanged": unchanged,
        "hasher_independent": independent,
        "holds": bool(
            nonzero and host_named and resolver_named and unchanged and independent
        ),
    }


def seed_cache(index_dir: Path) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "index.json").write_text(MARKER_CACHE, encoding="utf-8")


def evaluate() -> dict:
    http = RegistryHttp()
    blackhole = UdpResolver("blackhole", HOST_DEFAULT)
    answer = UdpResolver("answer", HOST_DEFAULT, "127.0.0.1")
    try:
        with tempfile.TemporaryDirectory(prefix="tst0129-") as tmp:
            root = Path(tmp)
            cached = root / "cached-index"
            empty = root / "empty-index"
            reachable = root / "reachable-index"
            mutant_dir = root / "mutant-cache"
            partial_dir = root / "mutant-partial"
            seed_cache(cached)
            seed_cache(mutant_dir)
            seed_cache(partial_dir)
            empty.mkdir()

            bh_before = run_hashed(cached)
            bh_install = run_install(
                cached, blackhole.ip, blackhole.port, http.port, "abort"
            )
            bh_after = run_hashed(cached)
            bh_assert = fail_closed_holds(
                bh_install, bh_before, bh_after, blackhole.address
            )

            empty_before = run_hashed(empty)
            empty_install = run_install(
                empty, blackhole.ip, blackhole.port, http.port, "abort"
            )
            empty_after = run_hashed(empty)
            empty_assert = fail_closed_holds(
                empty_install, empty_before, empty_after, blackhole.address
            )
            empty_still_empty = (
                empty_after["file_count"] == 0 and not any(empty.iterdir())
            )

            ok_before = run_hashed(reachable)
            ok_install = run_install(
                reachable, answer.ip, answer.port, http.port, "abort"
            )
            ok_after = run_hashed(reachable)
            ok_assert = fail_closed_holds(
                ok_install, ok_before, ok_after, answer.address
            )
            ok_wrote = (reachable / "index.json").is_file() and (
                '"pkg.demo"' in (reachable / "index.json").read_text(encoding="utf-8")
            )

            mutant_before = run_hashed(mutant_dir)
            mutant = run_install(
                mutant_dir, blackhole.ip, blackhole.port, http.port, "cache-success"
            )
            mutant_after = run_hashed(mutant_dir)
            mutant_assert = fail_closed_holds(
                mutant, mutant_before, mutant_after, blackhole.address
            )

            partial_before = run_hashed(partial_dir)
            partial = run_install(
                partial_dir, blackhole.ip, blackhole.port, http.port, "write-partial"
            )
            partial_after = run_hashed(partial_dir)
            partial_assert = fail_closed_holds(
                partial, partial_before, partial_after, blackhole.address
            )

            return {
                "host": HOST_DEFAULT,
                "http": {"ip": http.ip, "port": http.port},
                "blackhole_resolver": blackhole.address,
                "answer_resolver": answer.address,
                "blackhole": {
                    "install": _trim(bh_install),
                    "before": bh_before,
                    "after": bh_after,
                    "assertion": bh_assert,
                },
                "empty_index": {
                    "install": _trim(empty_install),
                    "before": empty_before,
                    "after": empty_after,
                    "assertion": empty_assert,
                    "still_empty": empty_still_empty,
                },
                "reachable": {
                    "install": _trim(ok_install),
                    "before": ok_before,
                    "after": ok_after,
                    "assertion": ok_assert,
                    "wrote_live_index": ok_wrote,
                    "index_changed": ok_before["sha256"] != ok_after["sha256"],
                },
                "mutant_cache_success": {
                    "install": _trim(mutant),
                    "before": mutant_before,
                    "after": mutant_after,
                    "assertion": mutant_assert,
                    "detector_rejects_mutant": (not mutant_assert["holds"])
                    and mutant["returncode"] == 0,
                },
                "mutant_write_partial": {
                    "install": _trim(partial),
                    "before": partial_before,
                    "after": partial_after,
                    "assertion": partial_assert,
                    "detector_rejects_mutant": (not partial_assert["index_unchanged"]),
                },
            }
    finally:
        answer.close()
        blackhole.close()
        http.close()


def _trim(run: dict) -> dict:
    return {
        "returncode": run["returncode"],
        "stdout": (run.get("stdout") or "")[-1500:],
        "stderr": (run.get("stderr") or "")[-1500:],
        "dns_fail_mode": run.get("dns_fail_mode"),
    }


def verdict(doc: dict) -> tuple[bool, list[str]]:
    fails: list[str] = []
    if not doc["blackhole"]["assertion"]["holds"]:
        fails.append("blackhole assertion did not fire")
    if not doc["empty_index"]["assertion"]["holds"]:
        fails.append("empty-index assertion did not fire")
    if not doc["empty_index"]["still_empty"]:
        fails.append("empty index directory was mutated")
    reach = doc["reachable"]
    if reach["assertion"]["holds"]:
        fails.append("reachable registry incorrectly fired fail-closed assertion")
    if reach["install"]["returncode"] != 0:
        fails.append(f"reachable install rc={reach['install']['returncode']}")
    if not reach["wrote_live_index"] or not reach["index_changed"]:
        fails.append("reachable install did not write a new index")
    if "ERROR: DNS resolution failed" in reach["install"]["stderr"]:
        fails.append("reachable install stderr contains DNS failure")
    if not doc["mutant_cache_success"]["detector_rejects_mutant"]:
        fails.append("cache-success mutant was not rejected by the detector")
    if not doc["mutant_write_partial"]["detector_rejects_mutant"]:
        fails.append("write-partial mutant left the index unchanged (detector blind)")
    return (not fails), fails
