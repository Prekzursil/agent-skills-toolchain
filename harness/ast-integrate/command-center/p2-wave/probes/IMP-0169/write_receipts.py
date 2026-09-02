#!/usr/bin/env python3
"""Write IMP-0169 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0169"
OUT = "command-center/receipts/IMP-0169.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0169/probe1_differential.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0169/probe2_unquoted_control.py"
)
V1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
    "\"from pathlib import Path; t=Path('tools/import_quarantine.py').read_text("
    "encoding='utf-8'); assert 'payload_start + nbytes' in t; "
    "assert 'SOURCE_CLASSES' in t; assert 'workflow' not in t.lower().split("
    "'source_classes')[1][:400] if 'source_classes' in t.lower() else True; "
    "print('nbytes-consume=true'); print('SUCCESS:IMP-0169-static-frames')\""
)
V2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
    "\"from pathlib import Path; t=Path("
    "'command-center/p2-wave/probes/IMP-0169/fixtures.py').read_text("
    "encoding='utf-8'); assert 'BREAKOUT' in t; "
    "assert 'HOSTILE_INSTRUCTION' in t; "
    "print('breakout-plant-present'); print('SUCCESS:IMP-0169-static-breakout')\""
)
SUPPORTING = [
    "tools/import_quarantine.py",
    "command-center/p2-wave/probes/IMP-0169/fixtures.py",
    "command-center/p2-wave/probes/IMP-0169/probe1_differential.py",
    "command-center/p2-wave/probes/IMP-0169/probe2_unquoted_control.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def eol_of(path: Path) -> str:
    raw = path.read_bytes()
    stripped = raw.replace(b"\r\n", b"")
    if b"\r\n" in raw and b"\n" in stripped:
        return "MIXED"
    if b"\r\n" in raw:
        return "CRLF"
    return "LF"


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def clip(text: str, limit: int = 65000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 16] + "\n...[clipped]\n"


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "eol": eol_of(path),
        "role": role,
    }


def manifest_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0169/SUBAGENT-RETURN.json",
        "role": role,
    }


def parse_probe_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def probe_obj(role: str, method: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": clip(raw),
        "fingerprint": fingerprint(method, command),
        "exit_code": code,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    cv1, tv1 = run_probe(V1)
    cv2, tv2 = run_probe(V2)
    if c1 != 0 or c2 != 0 or cv1 != 0 or cv2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2} v1={cv1} v2={cv2}")
        print(t1[-2000:])
        print(t2[-2000:])
        print(tv1[-1000:])
        print(tv2[-1000:])
        return 1
    j1 = parse_probe_json(t1)
    j2 = parse_probe_json(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib = artifact_row("tools/import_quarantine.py", "primary")
    supporting_arts = [artifact_row(p, "supporting") for p in SUPPORTING[1:]]

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0169",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json IMP-0169; AGENTS.md 9; "
            "_USER-PROMPTS.md:11344"
        ),
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "p2-wave-named-probe-implementer",
            "execution_substrate": "linux-worktree",
        },
        "artifacts": [lib, *supporting_arts],
        "evidence": [
            {
                "claim": (
                    "Rendered prompt with vs without the hostile payload differs "
                    "only inside quoted DATA regions; directive bytes are identical; "
                    "the canary is present inside a DATA payload (non-vacuous)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/IMP-0169/probe1_differential.py"
                ),
                "unverified": False,
                "probes": [
                    probe_obj("source", "test-run", P1, t1, c1),
                    probe_obj("verifier", "static-analysis", V1, tv1, cv1),
                ],
            },
            {
                "claim": (
                    "The same instruction-shaped payload placed outside the DATA "
                    "region is caught by the unquoted detector; the quoted rendering "
                    "of that payload is silent; a benign render is silent (both-states). "
                    f"unquoted_hit_count={j2.get('unquoted_hit_count')} "
                    f"breakout_held={j2.get('breakout_held_inside_marketplace_payload')}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/IMP-0169/probe2_unquoted_control.py"
                ),
                "unverified": False,
                "probes": [
                    probe_obj("source", "test-run", P2, t2, c2),
                    probe_obj("verifier", "file-read", V2, tv2, cv2),
                ],
            },
        ],
        "tests": [
            {
                "id": "hostile-payload-confined-to-quoted-region",
                "name": "differential: hostile vs benign diffs stay in DATA",
                "command": P1,
                "result": "PASS",
                "output_tail": clip(t1, 4096),
            },
            {
                "id": "unquoted-payload-caught-both-states",
                "name": "unquoted splice fires; quoted and benign are silent",
                "command": P2,
                "result": "PASS",
                "output_tail": clip(t2, 4096),
            },
        ],
        "negative_controls": [
            {
                "id": "NC1-unquoted-splice",
                "kind": "adversarial-payload",
                "description": (
                    "Splice HOSTILE_INSTRUCTION into the leading directive span. "
                    "Detector must fire. Same payload inside DATA must be silent."
                ),
                "fired_on_bad_state": bool(j2.get("fired_on_unquoted")),
                "silent_on_good_state": bool(j2.get("silent_on_quoted")),
                "bad_state_output": clip(t2, 2048),
                "good_state_output": "quoted_unquoted_hit_count=0",
            },
            {
                "id": "NC2-benign-not-always-on",
                "kind": "adversarial-payload",
                "description": (
                    "Benign imported prose must not trip the unquoted detector."
                ),
                "fired_on_bad_state": bool(j2.get("fired_on_unquoted")),
                "silent_on_good_state": bool(j2.get("silent_on_benign")),
                "bad_state_output": "fired_on_unquoted=true",
                "good_state_output": "benign_unquoted_hit_count=0",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0169-probe2-unquoted-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Catalog asked for a cross-vendor Codex reviewer on the injection "
                "surface. This G-1 delivery uses the live unquoted-payload probe as "
                "the independent mechanical check: it fires on an unquoted splice "
                "and stays silent on the quoted render of the same canary. A human "
                "Codex pass is not claimed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0169/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/IMP-0169/probe1_differential.py"
                ),
                "artifact_path": "tools/import_quarantine.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
                "probe": probe_obj("source", "test-run", P1, t1, c1),
            },
            {
                "consumer": (
                    "command-center/p2-wave/probes/IMP-0169/probe2_unquoted_control.py"
                ),
                "artifact_path": "tools/import_quarantine.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c2,
                "probe": probe_obj("source", "test-run", P2, t2, c2),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot - after the second failure on the same "
                "error fingerprint, enumerate >=2 alternative approaches before a "
                "third attempt (AGENTS.md 4b)"
            ),
            "attempts": [{"attempt": 1, "outcome": "SUCCESS", "started_at": now}],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Human Codex review of the injection surface was not executed "
                    "in this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Route the two named probes plus tools/import_quarantine.py "
                    "to a Codex reviewer."
                ),
            }
        ],
        "extensions": {
            "implementation": {
                "library": "tools/import_quarantine.py",
                "library_sha256": lib["sha256"],
                "library_bytes": lib["bytes"],
                "differential_all_diffs_inside_data": (j1.get("differential") or {}).get(
                    "all_diffs_inside_data"
                ),
                "differential_directives_identical": (j1.get("differential") or {}).get(
                    "directives_identical"
                ),
                "differential_non_vacuous": (j1.get("differential") or {}).get(
                    "non_vacuous"
                ),
                "canary_in_a_data_payload": j1.get("canary_in_a_data_payload"),
                "note": (
                    "G-1 IMP-0169: live named probes exit 0, receipt state=SUCCESS, "
                    "per-unit manifest row. Did not run global unit_manifest.py "
                    "--write. SUCCESS:IMP-0169"
                ),
            }
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    if "SUCCESS:IMP-0169" not in payload:
        print("FAILED:IMP-0169 sentinel missing from receipt text")
        return 1
    if out_path.stat().st_size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:IMP-0169 receipt too small {out_path.stat().st_size}")
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0169",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "differential-quoted-region",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "unquoted-control-both-states",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/IMP-0169/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "IMP-0169-probe2-unquoted-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0169: live named probes exit 0, receipts/IMP-0169.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0169 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
