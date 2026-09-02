#!/usr/bin/env python3
"""Run the SYN-0008 N-way independent synthesis panel.

Independence is a harness property:
  * each synthesizer gets a private sandbox with only its partition copied in
  * outputs are buffered in memory and published only after all N complete
  * a synthesizer that requests a sibling output is DENIED and the denial logged
  * dispatch is foreground, prompt-by-file, exit 0 + non-empty parsed JSON
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

import dispatch as D  # noqa: E402
import partition as P  # noqa: E402

WORK = HERE / "work"
SANDBOXES = WORK / "sandboxes"
CANDIDATES_DIR = WORK / "candidates"


def _sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def prepare_sandbox(agent: dict[str, str]) -> dict[str, Any]:
    agent_id = agent["id"]
    box = SANDBOXES / agent_id
    if box.exists():
        shutil.rmtree(box)
    ev_dir = box / "evidence"
    ev_dir.mkdir(parents=True)
    copied: list[str] = []
    for cls in P.classes_for(agent_id):
        src = P.evidence_path(cls)
        dest = ev_dir / src.name
        shutil.copy2(src, dest)
        copied.append(str(dest.resolve()))
    sibling_target = CANDIDATES_DIR / "syn8-openai-gpt.json"
    prompt = {
        "agent_id": agent_id,
        "vendor": agent["vendor"],
        "model": agent["model"],
        "lens": agent["lens"],
        "allow_read": copied,
        "request_sibling_output": str(sibling_target.resolve())
        if agent_id == "syn8-anthropic-opus"
        else None,
    }
    prompt_path = box / "prompt.json"
    prompt_path.write_text(
        json.dumps(prompt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    out_path = box / "synthesis.json"
    return {
        "agent": agent,
        "sandbox": box,
        "prompt_path": prompt_path,
        "out_path": out_path,
        "copied": copied,
        "manifest": P.partition_manifest(agent, copied),
        "sibling_target": str(sibling_target.resolve()),
    }


def run_panel() -> dict[str, Any]:
    """Run N synthesizers, leak fixture, then publish. Does not write the catalog artifact."""
    WORK.mkdir(parents=True, exist_ok=True)
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    for stale in CANDIDATES_DIR.glob("*.json"):
        stale.unlink()

    preps = [prepare_sandbox(agent) for agent in P.AGENTS]
    buffered: list[dict[str, Any]] = []
    leak_from_worker: dict[str, Any] | None = None

    for prep in preps:
        rec = D.run_synthesizer(prep["prompt_path"], prep["out_path"], mode="complete")
        payload = rec.get("payload") if rec.get("parsed") else None
        if (
            prep["agent"]["id"] == "syn8-anthropic-opus"
            and isinstance(payload, dict)
        ):
            leak_from_worker = payload.get("sibling_request")
        row = {
            "id": prep["agent"]["id"],
            "vendor": prep["agent"]["vendor"],
            "model": prep["agent"]["model"],
            "lens": prep["agent"]["lens"],
            "partition_manifest": prep["manifest"],
            "wall_clock_start": rec["wall_clock_start"],
            "wall_clock_end": rec["wall_clock_end"],
            "prompt_file": rec["prompt_file"],
            "prompt_sha256": _sha256_file(prep["prompt_path"]),
            "exit_code": rec["exit_code"],
            "output_path": rec["output_path"],
            "output_bytes": rec["output_bytes"],
            "parsed": rec["parsed"],
            "classification": rec["classification"],
            "counts_as_result": rec["counts_as_result"],
            "prompt_transport": rec["prompt_transport"],
            "foreground": rec["foreground"],
            "synthesis": payload
            if isinstance(payload, dict)
            else {"findings": []},
            "diagnostic_tail": rec.get("diagnostic_tail") or "",
        }
        buffered.append(row)

    unpublished = D.dispatcher_read_unpublished(buffered[1] if len(buffered) > 1 else None, published=False)
    leak_fixture = {
        "status": "DENIED",
        "requester": "syn8-anthropic-opus",
        "target": "syn8-openai-gpt",
        "reason": "sibling-output-not-filed",
        "logged": True,
        "worker_denial": leak_from_worker,
        "dispatcher_denial": unpublished,
        "target_path": preps[0]["sibling_target"],
        "target_existed_during_request": Path(preps[0]["sibling_target"]).is_file(),
    }
    worker_status = (
        leak_from_worker.get("status")
        if isinstance(leak_from_worker, dict)
        else None
    )
    if worker_status != "DENIED" or unpublished.get("status") != "DENIED":
        leak_fixture["status"] = "LEAKED"
        leak_fixture["reason"] = "harness-failed-to-deny-sibling-read"

    # Publish only after all N filed AND leak attempt recorded.
    published_paths: list[str] = []
    for row in buffered:
        dest = CANDIDATES_DIR / f"{row['id']}.json"
        dest.write_text(
            json.dumps(row, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        published_paths.append(_rel(dest))
        row["published_path"] = _rel(dest)

    manifests = [r["partition_manifest"] for r in buffered]
    cov = P.coverage(manifests)
    vendors = sorted({r["vendor"] for r in buffered if r.get("counts_as_result")})
    admitted = [r for r in buffered if r.get("counts_as_result")]

    severed = D.run_synthesizer(
        preps[0]["prompt_path"],
        SANDBOXES / "severed-control.json",
        mode="severed",
    )

    inline = D.reject_inline("y" * 40000)

    return {
        "candidates": buffered,
        "admitted": admitted,
        "leak_fixture": leak_fixture,
        "partition_coverage": cov,
        "vendors": vendors,
        "vendor_count": len(vendors),
        "published_paths": published_paths,
        "severed_control": {
            "classification": severed["classification"],
            "counts_as_result": severed["counts_as_result"],
            "parsed": severed["parsed"],
            "exit_code": severed["exit_code"],
        },
        "inline_control": inline,
        "schema_parsed_before_fan_in": all(
            r.get("parsed") and r.get("counts_as_result") for r in buffered
        ),
    }
