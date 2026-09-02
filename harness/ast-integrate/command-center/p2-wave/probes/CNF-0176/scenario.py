#!/usr/bin/env python3
"""Load source repos, fuse with lineage, run CNF-0176 confirmation checks."""
from __future__ import annotations

import json
from pathlib import Path

from engine import (
    LOST_CAPABILITY,
    LOST_PROVENANCE,
    MORE_STAGES_REFUSAL,
    attach_execution,
    capability_losses,
    decompose,
    digest_bytes,
    drop_capability,
    execute,
    fuse_union,
    fusion_accept_gate,
    pad_noop_stages,
    recompose,
    strip_license,
    structural_fingerprint,
)

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
SOURCES = FIX / "sources"
CASES_PATH = FIX / "cases.json"
CERT_PATH = FIX / "certified-fusion" / "certification.json"
FUSION_ID = "wf.certified.union-alpha-beta"
BLIND_EXCLUDE = (
    "command-center/p2-wave/probes/CNF-0176/fixtures/certified-fusion/certification.json"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_source(name: str) -> dict:
    root = SOURCES / name
    wf = load_json(root / "workflow.json")
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    credit_text = (root / "CREDIT").read_text(encoding="utf-8")
    wf["_repo"] = {
        "path": str(root.relative_to(HERE.parents[3])).replace("\\", "/"),
        "license_file_present": True,
        "credit_file_present": True,
        "license_sha256": digest_bytes(license_text.encode("utf-8")),
        "credit_sha256": digest_bytes(credit_text.encode("utf-8")),
        "license_mentions_spdx_or_name": wf["license"] in license_text
        or wf.get("spdx", "") in license_text,
        "credit_mentions_string": wf["credit"] in credit_text,
    }
    return wf


def load_sources() -> list[dict]:
    return [load_source("wf-alpha"), load_source("wf-beta")]


def cases() -> dict:
    return load_json(CASES_PATH)


def blinding_payload(sources: list[dict], fusion: dict) -> bytes:
    """Bytes the confirmer is allowed to see: sources + fusion, not certification."""
    body = {
        "excluded": [BLIND_EXCLUDE],
        "sources": [
            {
                "id": s["id"],
                "license": s["license"],
                "credit": s["credit"],
                "capabilities": s["capabilities"],
                "stages": s["stages"],
                "version": s["version"],
                "repo": s["_repo"],
            }
            for s in sources
        ],
        "fusion": fusion,
        "cases": cases(),
    }
    return (json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def run_confirmation() -> dict:
    sources = load_sources()
    smoke = cases()
    fusion = fuse_union(sources, FUSION_ID)
    gate = fusion["certification_gate"]
    if not gate.get("accepted"):
        return {"pass": False, "reason": "certified-fusion-refused", "gate": gate}

    decomp = decompose(fusion)
    cases_by_id = {
        "wf-alpha": dict(smoke["wf-alpha"]),
        "wf-beta": dict(smoke["wf-beta"]),
    }
    attach_execution(decomp, cases_by_id)

    orig_exec = {
        s["id"]: execute(s, dict(smoke[s["id"]]))
        for s in sources
    }
    recovered_match = []
    for report in decomp["reports"]:
        sid = report["source_id"]
        orig = orig_exec[sid]
        recovered_match.append(
            {
                "source_id": sid,
                "original_executed": bool(orig.get("executed")),
                "recovered_executed": bool(report.get("executed")),
                "original_tokens": list(orig.get("tokens") or []),
                "recovered_tokens": list(report.get("tokens") or []),
                "tokens_equal": list(orig.get("tokens") or []) == list(report.get("tokens") or []),
                "original_terminal": bool(orig.get("terminal")),
                "recovered_terminal": bool(report.get("terminal")),
            }
        )

    recomposed = recompose(decomp["components"], FUSION_ID)
    fp_fusion = structural_fingerprint(fusion)
    fp_round = structural_fingerprint(recomposed)
    roundtrip_ok = fp_fusion == fp_round

    losses = capability_losses(fusion, sources)
    lossy = drop_capability(fusion, "rank")
    planted_losses = capability_losses(lossy, sources)
    planted_loss_fired = any(
        "rank" in (row.get("lost_capabilities") or []) for row in planted_losses
    )

    vanity = fusion_accept_gate(
        {
            "capabilities": list(sources[0]["capabilities"]),
            "stages": list(sources[0]["stages"])
            + list(pad_noop_stages(sources[0])["stages"]),
        },
        [sources[0]],
    )

    broken = strip_license(fusion, "wf-alpha")
    broken_decomp = decompose(broken)
    license_detector = any(
        (not r.get("license_present")) and r.get("source_id") == "wf-alpha"
        for r in broken_decomp["reports"]
    )
    license_defect = any(
        d.get("defect") == LOST_PROVENANCE and d.get("source_id") == "wf-alpha"
        for d in broken_decomp["defects"]
    )

    parse_only = {
        "id": "wf-parse-only",
        "license": "MIT",
        "credit": "none",
        "capabilities": ["documented"],
        "stages": [{"id": "doc", "kind": "documented", "capabilities": ["documented"]}],
    }
    parse_run = execute(parse_only, {"text": "x"})

    fusion_run = execute(fusion, dict(smoke["fusion"]))

    per_component = []
    for report, match in zip(decomp["reports"], recovered_match):
        per_component.append(
            {
                "source_id": report["source_id"],
                "executed": bool(report.get("executed")),
                "license_present": bool(report.get("license_present")),
                "credit_present": bool(report.get("credit_present")),
                "license": report.get("license"),
                "credit": report.get("credit"),
                "terminal_state": report.get("terminal_state"),
                "tokens_equal": match["tokens_equal"],
                "tokens": list(report.get("tokens") or []),
            }
        )

    all_executed = all(p["executed"] and p["tokens_equal"] for p in per_component)
    all_licensed = all(p["license_present"] and p["credit_present"] for p in per_component)
    no_loss = losses == []
    cert_on_disk = CERT_PATH.is_file()
    cert_doc = load_json(CERT_PATH) if cert_on_disk else {}
    lazy = str(cert_doc.get("instruction_to_lazy_confirmer") or "")

    ok = (
        gate.get("accepted") is True
        and roundtrip_ok
        and all_executed
        and all_licensed
        and no_loss
        and planted_loss_fired
        and vanity.get("accepted") is False
        and vanity.get("reason") == MORE_STAGES_REFUSAL
        and license_detector
        and license_defect
        and parse_run.get("executed") is False
        and fusion_run.get("executed") is True
        and cert_on_disk
        and len(per_component) == 2
    )
    payload = blinding_payload(sources, fusion)
    lazy_leaked = bool(lazy) and lazy.encode("utf-8") in payload
    ok = ok and not lazy_leaked
    return {
        "pass": ok,
        "fusion_id": FUSION_ID,
        "fusion": fusion,
        "fusion_fingerprint": fp_fusion,
        "recompose_fingerprint": fp_round,
        "roundtrip_ok": roundtrip_ok,
        "gate": gate,
        "vanity_gate": vanity,
        "capability_losses": losses,
        "planted_lossy": {
            "dropped": "rank",
            "losses": planted_losses,
            "detector_fired": planted_loss_fired,
            "defect": LOST_CAPABILITY,
        },
        "license_strip_control": {
            "source_id": "wf-alpha",
            "detector_fired": license_detector and license_defect,
            "defects": broken_decomp["defects"],
            "reports": [
                {
                    "source_id": r["source_id"],
                    "license_present": r["license_present"],
                    "credit_present": r["credit_present"],
                }
                for r in broken_decomp["reports"]
            ],
            "defect": LOST_PROVENANCE,
        },
        "parse_only_control": {
            "executed": bool(parse_run.get("executed")),
            "state": parse_run.get("state"),
            "reason": parse_run.get("reason"),
            "terminal": bool(parse_run.get("terminal")),
        },
        "fusion_execute": {
            "executed": bool(fusion_run.get("executed")),
            "terminal": bool(fusion_run.get("terminal")),
            "tokens": list(fusion_run.get("tokens") or []),
            "stages_run": list(fusion_run.get("stages_run") or []),
        },
        "per_component": per_component,
        "recovered_match": recovered_match,
        "original_execute": {
            sid: {
                "executed": bool(r.get("executed")),
                "terminal": bool(r.get("terminal")),
                "tokens": list(r.get("tokens") or []),
                "stages_run": list(r.get("stages_run") or []),
            }
            for sid, r in orig_exec.items()
        },
        "sources": [
            {
                "id": s["id"],
                "license": s["license"],
                "credit": s["credit"],
                "capabilities": s["capabilities"],
                "repo": s["_repo"],
            }
            for s in sources
        ],
        "blinding": {
            "sha256": digest_bytes(payload),
            "bytes": len(payload.replace(b"\r\n", b"\n")),
            "excluded": [BLIND_EXCLUDE],
            "certification_on_disk": cert_on_disk,
            "lazy_instruction_leaked": lazy_leaked,
        },
    }
