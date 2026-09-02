"""Live experiments for WFA-0085. Each call executes; nothing is stubbed."""
from __future__ import annotations

import hashlib
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

from corpus import (  # noqa: E402
    ADJUDICATION,
    BETA_UPDATE_BODY,
    EPSILON_UPDATE_BODY,
    EXPECTED_STABLE_IDS,
    KILL_AFTER,
    N_SOURCES,
    N_UNIQUE,
    MIGRATION_MAP,
    materialize,
    rewrite_source,
)
from naive import append_all  # noqa: E402
from registry import index_records, set_adjudication, stable_ids  # noqa: E402
from store import dumps, load_json, registry_path  # noqa: E402
from sweep import load_migration, persist, run_sweep  # noqa: E402

SWEEP_PY = HERE / "sweep.py"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def file_digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def records_view(store: dict[str, Any]) -> list[dict[str, Any]]:
    recs = []
    for rec in store.get("records") or []:
        recs.append(
            {
                "aliases": rec.get("aliases"),
                "body": rec.get("body"),
                "content_hash": rec.get("content_hash"),
                "family": rec.get("family"),
                "mechanism": rec.get("mechanism"),
                "stable_id": rec.get("stable_id"),
                "title": rec.get("title"),
                "adjudication": rec.get("adjudication"),
            }
        )
    recs.sort(key=lambda r: str(r.get("stable_id") or ""))
    return recs


def setup(root: Path) -> tuple[Path, Path, dict[str, str]]:
    corpus, map_path = materialize(root)
    amap = load_migration(map_path)
    if amap != MIGRATION_MAP:
        raise RuntimeError("migration map round-trip mismatch")
    return corpus, map_path, amap


def run_idempotence(root: Path) -> dict[str, Any]:
    corpus, _map_path, amap = setup(root)
    work = root / "work-idem"
    first = run_sweep(corpus, work, amap, resume=True)
    path = registry_path(work)
    sha1, n1 = file_digest(path)
    ids1 = stable_ids(first)
    second = run_sweep(corpus, work, amap, resume=True)
    sha2, n2 = file_digest(path)
    ids2 = stable_ids(second)
    new_ids = sorted(set(ids2) - set(ids1))
    return {
        "byte_identical": sha1 == sha2 and n1 == n2,
        "new_records": len(new_ids),
        "new_ids": new_ids,
        "n_records": len(ids1),
        "n_sources": N_SOURCES,
        "expected_ids": EXPECTED_STABLE_IDS,
        "ids": ids1,
        "sha256_first": sha1,
        "sha256_second": sha2,
        "bytes_first": n1,
        "bytes_second": n2,
        "ids_match_expected": ids1 == EXPECTED_STABLE_IDS,
    }


def run_content_update(root: Path) -> dict[str, Any]:
    corpus, _map_path, amap = setup(root)
    work = root / "work-update"
    run_sweep(corpus, work, amap, resume=True)
    before = load_json(registry_path(work))
    n_before = len(before["records"])
    rewrite_source(corpus, "05-epsilon.json", body=EPSILON_UPDATE_BODY)
    after_store = run_sweep(corpus, work, amap, resume=True)
    rec = index_records(after_store)["WF-EPSILON"]
    updates = [e for e in rec.get("evidence") or [] if e.get("kind") == "update"]
    delta_fields: list[str] = []
    if updates:
        delta_fields = sorted((updates[-1].get("delta") or {}).keys())
    return {
        "n_records_before": n_before,
        "n_records_after": len(after_store["records"]),
        "duplicated": len(after_store["records"]) != n_before,
        "updated_id": "WF-EPSILON",
        "body": rec.get("body"),
        "expected_body": EPSILON_UPDATE_BODY,
        "evidence_kind": updates[-1]["kind"] if updates else None,
        "delta_fields": delta_fields,
        "update_applied": rec.get("body") == EPSILON_UPDATE_BODY and bool(updates),
    }


def run_adjudication(root: Path) -> dict[str, Any]:
    corpus, _map_path, amap = setup(root)
    work = root / "work-adj"
    store = run_sweep(corpus, work, amap, resume=True)
    set_adjudication(store, "WF-BETA", ADJUDICATION)
    persist(work, store)
    rewrite_source(corpus, "02-beta.json", body=BETA_UPDATE_BODY)
    after = run_sweep(corpus, work, amap, resume=True)
    rec = index_records(after)["WF-BETA"]
    adj = rec.get("adjudication") or {}
    return {
        "id": "WF-BETA",
        "preserved": adj == ADJUDICATION,
        "disposition": adj.get("disposition"),
        "content_updated": rec.get("body") == BETA_UPDATE_BODY,
        "n_records": len(after["records"]),
        "duplicated": len(after["records"]) != N_UNIQUE,
    }


def run_naive(root: Path) -> dict[str, Any]:
    corpus, _map_path, amap = setup(root)
    result = append_all(corpus, amap)
    result["merge_unique"] = N_UNIQUE
    result["append_exceeds_merge"] = result["n_records"] > N_UNIQUE
    return result


def _popen_sweep(
    corpus: Path, work: Path, map_path: Path, *, hold_checkpoint: int | None = None
) -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    if hold_checkpoint is not None:
        env["WFA0085_HOLD_CHECKPOINT"] = str(hold_checkpoint)
    else:
        env.pop("WFA0085_HOLD_CHECKPOINT", None)
    return subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-B",
            str(SWEEP_PY),
            "--corpus",
            str(corpus),
            "--work",
            str(work),
            "--map",
            str(map_path),
        ],
        cwd=str(HERE.parents[3]),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )


def run_uninterrupted(corpus: Path, work: Path, map_path: Path) -> dict[str, Any]:
    proc = _popen_sweep(corpus, work, map_path)
    out, _ = proc.communicate(timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"uninterrupted sweep rc={proc.returncode}\n{out}")
    store = load_json(registry_path(work))
    return {"store": store, "stdout": out, "returncode": proc.returncode}


def run_killed(corpus: Path, work: Path, map_path: Path, after: int) -> dict[str, Any]:
    proc = _popen_sweep(corpus, work, map_path, hold_checkpoint=after)
    lines: list[str] = []
    killed = False
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))
            if line.startswith(f"CHECKPOINT n={after} "):
                proc.send_signal(signal.SIGKILL)
                killed = True
                break
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        raise
    return {
        "killed": killed,
        "returncode": proc.returncode,
        "stdout": "\n".join(lines),
        "n_target": after,
    }


def run_kill_resume(root: Path) -> dict[str, Any]:
    corpus, map_path, _amap = setup(root)
    clean = root / "work-clean"
    interrupted = root / "work-kill"
    u = run_uninterrupted(corpus, clean, map_path)
    k = run_killed(corpus, interrupted, map_path, KILL_AFTER)
    if not k["killed"]:
        raise RuntimeError(f"did not SIGKILL at n={KILL_AFTER}: {k['stdout']}")
    if k["returncode"] not in (-signal.SIGKILL, -9):
        raise RuntimeError(f"expected SIGKILL returncode, got {k['returncode']}")
    mid_path = registry_path(interrupted)
    if not mid_path.is_file():
        raise RuntimeError("no durable registry after kill")
    mid = load_json(mid_path)
    n_mid = len(mid.get("records") or [])
    n_ck = len((mid.get("checkpoint") or {}).get("completed_sources") or [])
    resumed = run_uninterrupted(corpus, interrupted, map_path)
    view_u = records_view(u["store"])
    view_r = records_view(resumed["store"])
    ids_u = stable_ids(u["store"])
    ids_r = stable_ids(resumed["store"])
    return {
        "kill_executed": True,
        "kill_signal": "SIGKILL",
        "killed_after": KILL_AFTER,
        "child_returncode": k["returncode"],
        "records_at_kill": n_mid,
        "sources_at_kill": n_ck,
        "n_records_uninterrupted": len(ids_u),
        "n_records_resume": len(ids_r),
        "ids_uninterrupted": ids_u,
        "ids_resume": ids_r,
        "ids_equal": ids_u == ids_r,
        "per_cell_equal": view_u == view_r,
        "record_set_equal": view_u == view_r and ids_u == ids_r,
        "view_sha256_uninterrupted": sha256_bytes(dumps({"records": view_u}).encode("utf-8")),
        "view_sha256_resume": sha256_bytes(dumps({"records": view_r}).encode("utf-8")),
        "no_lost_record": set(ids_u) <= set(ids_r) and set(ids_r) <= set(ids_u),
        "no_duplicate": len(ids_r) == len(set(ids_r)),
    }


def run_all(root: Path) -> dict[str, Any]:
    return {
        "idempotence": run_idempotence(root / "idem"),
        "content_update": run_content_update(root / "upd"),
        "adjudication": run_adjudication(root / "adj"),
        "kill_resume": run_kill_resume(root / "kr"),
        "naive_append": run_naive(root / "naive"),
    }
