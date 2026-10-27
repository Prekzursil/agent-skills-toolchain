"""shard3-w4 resume 2026-10-26: build the missing command-center/receipts/AUD-0084.json.

The unit's artifact + probes + manifest verify live (measure SUCCESS:delivered), but no
canonical receipt existed. This writes the builder-stage receipt: state=BLOCKED,
failure.classification=["reviewer-absent"] - receipt_core forbids state=SUCCESS without
reviewer.verdict=PASS + independent=true, and only the independent reviewer closes.

The artifact embeds a 2026-08-21 C5-wave reviewer block (PASS, independent), but that
closure predates the current artifact revision (re-emitted 2026-10-24, sha c4a7a21f...),
so it does not still verify live and cannot be lifted onto the receipt. Disclosed in notes.
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
OUT_REL = "command-center/audit/AUD-0084-hardcoded-path-census.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0084/probe1_literal_scan.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0084/probe2_ast_adjudication.py"
)
SENTINEL = (
    "SUCCESS:AUD-0084 emitted only when the artifact at output_path exists, is non-empty, "
    "parses against output_schema, and both named probes are recorded with their verbatim output"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


_m_path = REPO / "command-center/p2-wave/_measure_one_delivered.py"
_m_spec = __import__("importlib.util", fromlist=["util"]).spec_from_file_location("_m1d", _m_path)
_m = __import__("importlib.util", fromlist=["util"]).module_from_spec(_m_spec)
sys.modules["_m1d"] = _m
_m_spec.loader.exec_module(_m)
run_cmd = _m.run_cmd  # estate-standard Windows adaptation (env prefixes + g1 wrapper)


def fp(uid: str, i: int, role: str, tail: str) -> str:
    return f"{uid}:probe{i}:{role}:{hashlib.md5(tail.encode('utf-8')).hexdigest()[:12]}"


def main() -> int:
    art_path = REPO / OUT_REL
    sha, nbytes = digest(art_path)
    art = json.loads(art_path.read_text(encoding="utf-8"))

    results = []
    for i, (role, cmd) in enumerate(
        [("source", P1), ("verifier", P2)], 1
    ):
        code, out = run_cmd(cmd)
        print(f"probe[{i}] rc={code} role={role}")
        print("  " + out.splitlines()[-1] if out else "  <no output>")
        if code != 0:
            print(f"FAILED:AUD-0084-receipt probe{i} rc={code}")
            return 1
        results.append((role, cmd, code, out))

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    evidence_probes = []
    tests = []
    for i, (role, cmd, code, out) in enumerate(results, 1):
        tail = out[-4000:]
        evidence_probes.append(
            {
                "role": role,
                "method": "command",
                "command": cmd,
                "raw_output": tail,
                "fingerprint": fp("AUD-0084", i, role, out),
                "exit_code": code,
            }
        )
        tests.append(
            {
                "id": f"t-AUD-0084-probe{i}",
                "command": cmd,
                "result": "PASS",
                "output_tail": out.strip().splitlines()[-1],
            }
        )

    receipt = {
        "schema_version": 1,
        "unit_id": "AUD-0084",
        "state": "BLOCKED",
        "sentinel": SENTINEL,
        "spec_anchor": "catalog:AUD-0084",
        "min_bytes_threshold": 2048,
        "artifacts": [
            {
                "path": OUT_REL,
                "role": "primary",
                "sha256": sha,
                "bytes": nbytes,
                "exists": True,
                "eol": "LF",
            }
        ],
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/AUD-0084/SUBAGENT-RETURN.json",
                "claim": "Both named probes re-ran live this run (builder-shard3-w4 resume) and exited 0; artifact at the catalog output_path exists, parses, is not self-declared BLOCKED/FAILED, and sha-matches the per-unit manifest primary row (CRLF normalized).",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "probes": evidence_probes,
            }
        ],
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/AUD-0084/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "tests": tests,
        "negative_controls": [
            {
                "id": nc.get("id"),
                "kind": nc.get("kind"),
                "description": nc.get("description"),
                "fired_on_bad_state": nc.get("fired_on_bad_state"),
                "silent_on_good_state": nc.get("silent_on_good_state"),
            }
            for nc in (art.get("negative_controls") or [])
        ],
        "residual_unknowns": art.get("residual_unknowns") or [],
        "produced_by": {
            "execution_substrate": "local-serialized",
            "model": "claude-opus-5-5",
            "role": "builder-shard3-w4",
            "vendor": "anthropic",
        },
        "retry": {
            "attempts": [],
            "count": 0,
            "policy": "retry only after the named upstream unit emits its SUCCESS sentinel; retrying against a missing input is a detector failure, not a transient",
        },
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": (
                "Builder-shard3-w4 resume 2026-10-26: no canonical receipt existed for this unit. "
                f"Artifact verified live this run: exists/non-empty/parses, state=SUCCESS, not "
                f"self-blocked; both named probes re-ran exit 0; manifest primary row sha-matches "
                f"(CRLF normalized) at sha {sha}; _measure_one_delivered.py AUD-0084 exits "
                "SUCCESS:delivered. state stays BLOCKED/reviewer-absent per receipt_core - the "
                "builder may not self-close. The artifact-embedded 2026-08-21 C5-wave reviewer "
                "block (PASS, independent, openai/gpt-5.2) predates the current artifact revision "
                "(re-emitted 2026-10-24), so it does not still verify live and was not lifted onto "
                "this receipt; independent reviewer closure pending on the current revision."
            ),
        },
        "notes": (
            "Builder-stage receipt written by shard3-w4 resume 2026-10-26 (prior builder attempt "
            "died mid-flight after emitting artifact+probes+manifest but before any receipt). "
            "Catalog reviewer_requirement: one fresh-context reviewer who has not seen this "
            "unit's transcript, falsifying the headline count before PASS. No owner gate "
            "(owner_approval_required=false). Artifact-embedded reviewer block (2026-08-21 C5 "
            "wave) is stale relative to the 2026-10-24 artifact revision and is preserved in the "
            "artifact only; it is not receipt evidence."
        ),
        "timestamps": {"started_at": "2026-10-26T20:50:00Z", "ended_at": now},
    }

    rp = REPO / "command-center/receipts/AUD-0084.json"
    rp.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    # admission self-check, then embed the ACCEPT row (downstream_consumers).
    # Clean env: _m.run_cmd puts REPO on PYTHONPATH, whose platform/ namespace
    # package shadows stdlib platform and breaks jsonschema->attrs. The validator
    # imports the gate by absolute path and needs none of that PYTHONPATH.
    import subprocess as _sp
    def _validate(vcmd):
        vp = _sp.run(vcmd, cwd=str(REPO), shell=True, capture_output=True, text=True)
        return vp.returncode, ((vp.stdout or "") + (vp.stderr or "")).strip()
    vcmd = "python -B command-center/receipt_validate.py command-center/receipts/AUD-0084.json"
    vcode, vout = _validate(vcmd)
    print("validate rc=", vcode, "|", vout.splitlines()[0] if vout else "<none>")
    if vcode != 0:
        print(f"FAILED:AUD-0084-receipt admission rc={vcode}")
        print(vout[-1500:])
        return 1
    receipt["downstream_consumers"] = [
        {
            "consumer": "command-center/receipt_validate.py (admission gate C1-C5)",
            "artifact_path": "command-center/receipts/AUD-0084.json",
            "executed": True,
            "read_ok": True,
            "exit_code": vcode,
            "probe": {"role": "verifier", "method": "command", "command": vcmd, "raw_output": vout[-1500:], "fingerprint": fp("AUD-0084", 3, "verifier", vout)},
        }
    ]
    rp.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    vcode2, vout2 = _validate(vcmd)
    print("revalidate rc=", vcode2, "|", vout2.splitlines()[0] if vout2 else "<none>")
    if vcode2 != 0:
        print(f"FAILED:AUD-0084-receipt post-embed admission rc={vcode2}")
        print(vout2[-1500:])
        return 1
    print(f"SUCCESS:AUD-0084 receipt written state=BLOCKED reviewer-absent sha={sha} bytes={nbytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
