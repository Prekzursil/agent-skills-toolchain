#!/usr/bin/env python3
"""Build the live three-way reproduction matrix for CNF-0151."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ci_column import run_ci_column
from claims import CLAIMS, HOST_CACHE, WIN_PATHEXT, expected_portable, plant_host_cache
from container import image_digest, is_floating_ref, pinned_ref, run_container
from windows_oracle import run_windows_oracle

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
COLUMNS = ("windows-box", "linux-container", "ci")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _verdict(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _by_id(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(r["claim_id"]): r for r in bundle.get("results") or []}


def _cell(*, verdict: str, value: Any, run_id: str, digest: str, extra: dict | None = None) -> dict[str, Any]:
    cell = {
        "verdict": verdict,
        "value": value,
        "run_id": run_id,
        "digest": digest,
        "evidence": f"run_id={run_id} digest={digest}",
    }
    if extra:
        cell.update(extra)
    return cell


def build_live(*, nonce: str) -> dict[str, Any]:
    plant_host_cache()
    digest = image_digest()
    ref = pinned_ref(digest)
    if is_floating_ref(ref):
        raise RuntimeError(f"live ref is floating: {ref}")

    win_run = f"win-{nonce}"
    ctr_run = f"ctr-{nonce}"
    ci_run = f"ci-{nonce}"

    windows = run_windows_oracle(nonce=nonce, run_id=win_run)
    container = run_container(nonce=f"live-{nonce}", extra_binds=None, pathext="")
    ci = run_ci_column(run_id=ci_run, nonce=nonce)

    win_map = _by_id(windows)
    ctr_map = _by_id(container)
    ci_run_doc = ci["run"]
    ci_jobs = ci_run_doc["jobs"]
    ctr_meta = container["container"]
    ci_digest = (ci["payload"].get("container") or {}).get("digest") or digest

    expect = expected_portable()
    rows = []
    for spec in CLAIMS:
        cid = spec["id"]
        w = win_map[cid]
        c = ctr_map[cid]
        job = ci_jobs[cid]
        # CI cell MUST come from the re-read run file, not payload memory.
        ci_ok = job["conclusion"] == "success" if spec["portable"] else job.get("ok")
        if not spec["portable"]:
            ci_ok = bool(job.get("ok"))
        win_cell = _cell(
            verdict=_verdict(bool(w["ok"])),
            value=w.get("value"),
            run_id=win_run,
            digest=f"windows-oracle:{win_run}",
            extra={
                "instrument": windows["windows"]["instrument"],
                "rule": w.get("rule"),
            },
        )
        ctr_cell = _cell(
            verdict=_verdict(bool(c["ok"])),
            value=c.get("value"),
            run_id=ctr_run,
            digest=ctr_meta["digest"],
            extra={
                "container_ref": ctr_meta["ref"],
                "instance_digest": ctr_meta["instance_digest"],
                "rule": c.get("rule"),
            },
        )
        ci_cell = _cell(
            verdict=_verdict(bool(ci_ok)),
            value=job.get("value"),
            run_id=str(ci_run_doc["id"]),
            digest=str(ci_digest),
            extra={
                "conclusion_field": "jobs.%s.conclusion" % cid,
                "conclusion": job["conclusion"],
                "conclusion_source": "run.conclusion-reread",
                "run_path": ci["run_path_rel"],
            },
        )
        verdicts = (win_cell["verdict"], ctr_cell["verdict"], ci_cell["verdict"])
        values = (win_cell["value"], ctr_cell["value"], ci_cell["value"])
        if spec["portable"]:
            agree = (
                verdicts == ("PASS", "PASS", "PASS")
                and values[0] == values[1] == values[2] == expect[cid]
            )
            agreement = "AGREE" if agree else "DIVERGE"
        else:
            # Windows-specific control: Windows PASS, container and CI FAIL.
            agree = verdicts == ("PASS", "FAIL", "FAIL")
            agreement = "DIVERGE" if agree else "AGREE"
        rows.append(
            {
                "claim_id": cid,
                "title": spec["title"],
                "class": spec["class"],
                "portable": spec["portable"],
                "cells": {
                    "windows-box": win_cell,
                    "linux-container": ctr_cell,
                    "ci": ci_cell,
                },
                "agreement": agreement,
                "verdicts": {
                    "windows-box": win_cell["verdict"],
                    "linux-container": ctr_cell["verdict"],
                    "ci": ci_cell["verdict"],
                },
            }
        )

    portable_ok = all(r["agreement"] == "AGREE" for r in rows if r["portable"])
    win_ctrl_ok = all(r["agreement"] == "DIVERGE" for r in rows if not r["portable"])
    return {
        "ts": _now(),
        "nonce": nonce,
        "columns": list(COLUMNS),
        "image": {
            "ref": ref,
            "digest": digest,
            "floating_tag": False,
            "python_bin": "/usr/bin/python3.12",
            "runtime": "unshare-mount+chroot",
        },
        "windows": windows.get("windows"),
        "container_host_cache_visible": container.get("host_cache_visible"),
        "ci": {
            "run_id": ci_run_doc["id"],
            "run_path": ci["run_path_rel"],
            "summary_path": ci["summary_path_rel"],
            "run_conclusion": ci_run_doc["conclusion"],
            "stale_summary_conclusion": ci["stale_summary"]["conclusion"],
            "used_source": ci["used_source"],
            "rejected_source": ci["rejected_source"],
            "stale_differs": ci_run_doc["conclusion"] != ci["stale_summary"]["conclusion"],
        },
        "matrix": rows,
        "portable_agree": portable_ok,
        "windows_specific_diverges": win_ctrl_ok,
        "pass": portable_ok and win_ctrl_ok and not container.get("host_cache_visible"),
    }


def isolation_both_states(*, nonce: str) -> dict[str, Any]:
    """No-host-mount control: clean miss, bind-mount hit. Also PATHEXT contamination."""
    plant_host_cache()
    clean = run_container(nonce=f"iso-clean-{nonce}", extra_binds=None, pathext="")
    mounted = run_container(
        nonce=f"iso-mount-{nonce}",
        extra_binds=[(str(HOST_CACHE), "/host-cache")],
        path="/host-cache/bin:/usr/bin:/bin",
        pathext=WIN_PATHEXT,
        host_cache="/host-cache",
    )
    shim_clean = next(r for r in clean["results"] if r["claim_id"] == "C-WIN-CMD-SHIM")
    shim_mount = next(r for r in mounted["results"] if r["claim_id"] == "C-WIN-CMD-SHIM")
    return {
        "clean_sees_host_cache": bool(clean.get("host_cache_visible")),
        "mounted_sees_host_cache": bool(mounted.get("host_cache_visible")),
        "clean_resolves_shim": bool(shim_clean["ok"]),
        "mounted_resolves_shim": bool(shim_mount["ok"]),
        "clean_digest": clean["container"]["digest"],
        "mounted_digest": mounted["container"]["digest"],
        "clean_instance": clean["container"]["instance_digest"],
        "mounted_instance": mounted["container"]["instance_digest"],
        "pass": (
            not clean.get("host_cache_visible")
            and mounted.get("host_cache_visible")
            and not shim_clean["ok"]
            and shim_mount["ok"]
        ),
    }


def second_digest_review(*, nonce: str) -> dict[str, Any]:
    """Re-run the windows-specific claim on a second container instance digest."""
    a = run_container(nonce=f"rev-a-{nonce}", extra_binds=None)
    b = run_container(nonce=f"rev-b-{nonce}", extra_binds=None)
    sa = next(r for r in a["results"] if r["claim_id"] == "C-WIN-CMD-SHIM")
    sb = next(r for r in b["results"] if r["claim_id"] == "C-WIN-CMD-SHIM")
    ja = next(r for r in a["results"] if r["claim_id"] == "C-PORTABLE-JSON")
    jb = next(r for r in b["results"] if r["claim_id"] == "C-PORTABLE-JSON")
    return {
        "digest_a": a["container"]["instance_digest"],
        "digest_b": b["container"]["instance_digest"],
        "image_digest_shared": a["container"]["digest"] == b["container"]["digest"],
        "instances_differ": a["container"]["instance_digest"] != b["container"]["instance_digest"],
        "win_specific_a": bool(sa["ok"]),
        "win_specific_b": bool(sb["ok"]),
        "portable_json_agree": ja["value"] == jb["value"],
        "pass": (
            a["container"]["instance_digest"] != b["container"]["instance_digest"]
            and a["container"]["digest"] == b["container"]["digest"]
            and not sa["ok"]
            and not sb["ok"]
            and ja["value"] == jb["value"]
        ),
    }


def dump(path: Path, doc: dict[str, Any]) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
