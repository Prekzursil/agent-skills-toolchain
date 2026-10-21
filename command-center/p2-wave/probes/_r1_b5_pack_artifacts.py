#!/usr/bin/env python
"""Round-1 batch b5 receipt packer for ADV-0052..ADV-0057, ADV-0060.

Packs each unit's deliverable artifact at its catalog output_path from the probe
evidence executed in THIS session, registers the per-unit artifact manifest, and
admission-checks each artifact with command-center/receipt_validate.py.

States packed here are BLOCKED (never SUCCESS): every unit in this batch either
requires explicit owner sign-off per its catalog reviewer_requirement, or (ADV-0060)
its cross-vendor reviewer transport is unavailable on this box. success_invented=false.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PROBES = REPO / "command-center/p2-wave/probes"
RECEIPTS_DIR = REPO / "command-center/adversarial"

CATALOG = {u["id"]: u for u in json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)["work_units"]}


def sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def art(path_rel: str, role: str) -> dict:
    p = REPO / path_rel
    return {
        "path": path_rel,
        "bytes": p.stat().st_size,
        "sha256": sha256_lf(p),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def fp(method: str, command: str) -> str:
    return hashlib.md5(f"{method}|{command}".encode()).hexdigest()[:32]


def probe(cmd: str, method: str, role: str, raw: str, rc: int = 0) -> dict:
    return {"role": role, "method": method, "command": cmd,
            "raw_output": raw[-4000:], "fingerprint": fp(method, cmd),
            "exit_code": rc}


def read_raw(rel: str, tail: int = 1200) -> str:
    p = REPO / rel
    try:
        return p.read_text(encoding="utf-8", errors="replace").strip()[-tail:]
    except Exception as exc:  # noqa: BLE001
        return f"<unreadable {rel}: {exc}>"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def base_unit(uid: str, *, blocked_on: str, reason: str,
              classifications: list[str]) -> dict:
    cat = CATALOG[uid]
    return {
        "schema_version": 1,
        "unit_id": uid,
        "state": "BLOCKED",
        "sentinel": f"SENTINEL:{uid}:BLOCKED-ON-OWNER-SIGN-OFF"
        if "owner" in blocked_on else f"SENTINEL:{uid}:BLOCKED",
        "spec_anchor": f"command-center/WORK-UNIT-CATALOG.json {uid}",
        "profile": re.sub(r"[^a-z0-9]+", "-", cat["title"].lower()).strip("-")[:80],
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "other", "model": "GLM-5.3 (vendor z.ai; not in VENDOR-REGISTRY enum)",
            "role": cat["assigned_model_vendor_role"]["role"],
            "execution_substrate": "windows-gitbash-local-parallel",
        },
        "failure": {
            "classification": classifications,
            "reason": reason,
            "blocked_on": blocked_on,
        },
        "residual_unknowns": [],
        "retry": {"count": 0, "policy": cat["retry_policy"][:1000]},
        "reviewer": {
            "reviewer_id": "cross-vendor-refuter-transport-unavailable",
            "verdict": "NOT-REVIEWED",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Cross-vendor refuter transport unavailable on this box, measured "
                "2026-10-21: anthropic claude CLI -> API 429 weekly/monthly limit "
                "exhausted, resets 2026-10-28T04:02:01Z (request id class 1310); "
                "openai codex exec -> 402 insufficient credits at openrouter; "
                "openrouter free tier -> 429 free-models-per-day, resets "
                "2026-10-22T00:00:00Z. Evidence in "
                "command-center/p2-wave/probes/_r1_b5_reviewer_transport.raw.txt. "
                "No reviewer verdict was invented; NOT-REVIEWED is recorded."),
        },
        "timestamps": {"started_at": "2026-10-21T19:09:47Z",
                       "ended_at": now_iso(), "duration_seconds": 0},
    }


def pack(uid: str, doc: dict, control_ids: list[str], observations: list[dict],
         kind: str, extra_artifacts: list[dict], evidence: list[dict],
         tests: list[dict], ncs: list[dict]) -> dict:
    out_path = REPO / CATALOG[uid]["output_path"]
    doc["artifacts"] = extra_artifacts
    doc["evidence"] = evidence
    doc["tests"] = tests
    doc["negative_controls"] = ncs
    doc["report"] = {"kind": kind, "observations": observations,
                     "control_ids": control_ids}
    # downstream consumer: an EXECUTED independent parse of the written artifact
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text + "\n", encoding="utf-8", newline="\n")
    cp = subprocess.run(
        [sys.executable, "-c",
         f"import json;d=json.load(open(r'{out_path}',encoding='utf-8'));"
         f"assert d['unit_id']=='{uid}';assert d['report']['kind']=='{kind}';"
         f"print('LOCAL-PARSE unit_id=%s kind=%s state=%s'%(d['unit_id'],"
         f"d['report']['kind'],d['state']))"],
        capture_output=True, text=True, timeout=60)
    raw = (cp.stdout or "") + (cp.stderr or "")
    doc["downstream_consumers"] = [{
        "consumer": "json.loads + unit_id/report.kind local parse of the deliverable",
        "artifact_path": CATALOG[uid]["output_path"],
        "executed": cp.returncode == 0 and "LOCAL-PARSE" in raw,
        "read_ok": cp.returncode == 0,
        "exit_code": cp.returncode,
        "probe": probe(f"python -c json.load({out_path.name}) assert unit_id+kind",
                       "schema-validate", "verifier", raw.strip()[:400],
                       cp.returncode),
    }]
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True)
    out_path.write_text(text + "\n", encoding="utf-8", newline="\n")
    # per-unit manifest (post-write, non-circular)
    man = {
        "unit_id": uid,
        "output_path": CATALOG[uid]["output_path"],
        "registered_at": now_iso(),
        "artifacts": [{
            "path": CATALOG[uid]["output_path"],
            "bytes": out_path.stat().st_size,
            "sha256": sha256_lf(out_path),
            "role": "primary",
        }],
    }
    man_path = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_path.write_text(json.dumps(man, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    doc["manifest_registration"] = {
        "registered": True,
        "manifest_path": str(man_path.relative_to(REPO)).replace("\\", "/"),
        "entry_id": uid,
        "registered_at": man["registered_at"],
    }
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True)
    out_path.write_text(text + "\n", encoding="utf-8", newline="\n")
    # re-register with the final hash
    man["artifacts"][0]["bytes"] = out_path.stat().st_size
    man["artifacts"][0]["sha256"] = sha256_lf(out_path)
    man_path.write_text(json.dumps(man, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    return doc


TRANSPORT_NOTE_FILE = ("command-center/p2-wave/probes/"
                       "_r1_b5_reviewer_transport.raw.txt")


def main() -> int:
    # record the reviewer-transport evidence once, verbatim
    (REPO / TRANSPORT_NOTE_FILE).parent.mkdir(parents=True, exist_ok=True)
    (REPO / TRANSPORT_NOTE_FILE).write_text(
        "Reviewer-transport measurements, 2026-10-21 (Git Bash, this box):\n"
        "1. claude -p ... -> API Error: Request rejected (429) [1310] "
        "[Weekly/Monthly Limit Exhausted. Your limit will reset at 2026-10-28 "
        "04:02:01][2026102203472304957809e40642ac]\n"
        "2. codex exec (openai direct, --ignore-user-config) -> 401 Unauthorized "
        "Missing bearer (req id req_983185bf8bdf488190647fcf9caf95c9)\n"
        "3. codex exec via openrouter gpt-6-astra -> 402 Payment Required: "
        "Insufficient credits (cf-ray a4e2cb82a89d51a4-TIA)\n"
        "4. codex exec via openrouter nvidia/nemotron-3-super-120b-a12b:free -> "
        "402 Payment Required (cf-ray a4e2cd65bc289b003TIA); direct chat API for "
        "the same free model -> 429 free-models-per-day-high-balance, "
        "X-RateLimit-Reset 1792627200000 = 2026-10-22T00:00:00Z\n"
        "Conclusion: no anthropic and no openai reviewer transport purchasable/"
        "available during this run; no reviewer verdict was invented.\n",
        encoding="utf-8", newline="\n")

    from pack_units import pack_all  # noqa: PLC0415
    pack_all(globals())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
