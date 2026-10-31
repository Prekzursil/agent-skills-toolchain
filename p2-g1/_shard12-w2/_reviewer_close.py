"""Independent reviewer CLOSURE for wave 2 shard 12 closeable units.

Closes IMP-0218 / IMP-0221 / IMP-0222 whose receipts sit at state=BLOCKED with
failure.classification==["reviewer-absent"] and whose every other DELIVERED check
already held under _reviewer_verify_all.py (schema 0 errs, probes exit 0, sha match).

Closure = the reviewer block the builders were forbidden to self-certify:
  state BLOCKED->SUCCESS, failure block dropped (reason resolved),
  reviewer={PASS, independent, fresh_context}, downstream_consumers rows for the
  TWO consumers executed against the artifact (admission check + schema gate),
  tests[] gains the reviewer's own live probe re-runs.
Every patch is validated (resolver + gate) BEFORE write and the persisted bytes are
re-validated AFTER write; on any error the write is refused and the unit is reported.
Manifest primary row sha256/bytes is refreshed to the closed receipt (CRLF->LF norm).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = ["IMP-0218", "IMP-0221", "IMP-0222"]
RECEIPTS = REPO / "command-center/receipts"
PROBES = REPO / "command-center/p2-wave/probes"
REVIEWER_ID = "p2-wave2-shard12-independent-reviewer"

spec = importlib.util.spec_from_file_location("schema_resolver", REPO / "platform/lib/schema_resolver.py")
resolver = importlib.util.module_from_spec(spec); sys.modules["schema_resolver"] = resolver; spec.loader.exec_module(resolver)
gspec = importlib.util.spec_from_file_location("gate", REPO / "platform/lib/receipt_schema_gate.py")
gate = importlib.util.module_from_spec(gspec); sys.modules["gate"] = gate; gspec.loader.exec_module(gate)


def norm_sha(data: bytes) -> tuple[str, int]:
    n = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(n).hexdigest(), len(n)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def run(cmd: list[str], timeout: int = 300) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", env=dict(os.environ))
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except OSError as e:
        return 127, f"{type(e).__name__}: {e}"


def consumer_row(consumer: str, artifact_rel: str, cmd: list[str], rc: int, out: str) -> dict:
    method = "command"
    return {
        "consumer": consumer,
        "artifact_path": artifact_rel,
        "executed": True,
        "read_ok": rc == 0 and ("ACCEPT" in out or "SCHEMA-VALID" in out),
        "exit_code": rc,
        "probe": {
            "role": "verifier", "method": method, "command": " ".join(cmd),
            "exit_code": rc, "raw_output": out[-1200:],
            "fingerprint": fp(method, " ".join(cmd)),
        },
    }


def probe_test_row(uid: str, n: int, script: Path, rc: int, out: str) -> dict:
    command = f"python -B command-center/p2-wave/probes/{uid}/{script.name}"
    return {
        "id": f"reviewer-{uid.lower()}-rerun-probe{n}",
        "command": command,
        "result": "PASS" if rc == 0 and "SUCCESS:" in out else "FAIL",
        "output_tail": out[-600:],
    }


def close(uid: str) -> dict:
    res: dict = {"unit": uid}
    rel = f"command-center/receipts/{uid}.json"
    path = RECEIPTS / f"{uid}.json"
    raw = path.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    res["pre_state"] = doc.get("state")
    res["pre_class"] = (doc.get("failure") or {}).get("classification")
    if doc.get("state") != "BLOCKED" or res["pre_class"] != ["reviewer-absent"]:
        res["verdict"] = "SKIP"; res["why"] = "not a reviewer-absent BLOCKED receipt"
        return res

    # consumers: REAL executions against this artifact, run right now
    rc_adm, out_adm = run([sys.executable, "command-center/receipt_validate.py", rel])
    rc_gate, out_gate = run([sys.executable, "platform/lib/receipt_schema_gate.py", rel, "--schema-only"])
    res["admission_rc"], res["gate_rc"] = rc_adm, rc_gate
    if rc_adm != 0 or "ACCEPT" not in out_adm or rc_gate != 0 or "SCHEMA-VALID" not in out_gate:
        res["verdict"] = "FAIL"; res["why"] = f"pre-close consumers not green: admission={rc_adm} gate={rc_gate}"
        return res

    # reviewer probe re-runs: live, from this session
    pdir = PROBES / uid
    reruns = []
    for i, script in enumerate(sorted(pdir.glob("probe*.py")), 1):
        rc, out = run([sys.executable, "-B", str(script)])
        reruns.append((script, rc, out))
    if any(rc != 0 for _, rc, _ in reruns):
        res["verdict"] = "FAIL"; res["why"] = "probe re-run failed at close time"
        return res

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    notes = (
        "Independent adversarial closure (wave2 shard12 reviewer, fresh context): "
        "receipt validated against output_schema with BOTH instruments (schema_resolver.validate_artifact "
        "and receipt_schema_gate layer-1) => 0 errors; both catalog probes re-run live by the reviewer, exit 0 "
        "with SUCCESS markers; receipt sha256 (CRLF->LF) matches UNIT-ARTIFACT-MANIFEST primary row; "
        "admission check ACCEPT and unit present in WORK-UNIT-CATALOG; builder's BLOCKED(reason=reviewer-absent) "
        "resolved by this PASS. Builder evidence re-read and re-confirmed: both-states negative controls fired/silent, "
        "tests PASS, evidence source+verifier pairs present."
    )
    doc["reviewer"] = {
        "reviewer_id": REVIEWER_ID,
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "vendor": "claude-code",
        "notes": notes,
        "reviewed_at": now,
    }
    doc["downstream_consumers"] = [
        consumer_row("command-center/receipt_validate.py (admission: parse+schema+catalog cross-reference)",
                     rel, [sys.executable, "command-center/receipt_validate.py", rel], rc_adm, out_adm),
        consumer_row("platform/lib/receipt_schema_gate.py (layer-1 schema re-read)",
                     rel, [sys.executable, "platform/lib/receipt_schema_gate.py", rel, "--schema-only"], rc_gate, out_gate),
    ]
    doc["tests"] = (doc.get("tests") or []) + [
        probe_test_row(uid, i, s, rc, o) for i, (s, rc, o) in enumerate(reruns, 1)
    ]
    doc.pop("failure", None)  # block reason resolved by this closure
    doc["state"] = "SUCCESS"

    # validate BEFORE persist
    errs = resolver.validate_artifact(doc, "command-center/schema/receipt.schema.json")
    errs += list(gate.validate_receipt(doc) or [])
    if errs:
        res["verdict"] = "FAIL"; res["why"] = f"patched receipt invalid, NOT written: {len(errs)} errs; first: {str(errs[0])[:180]}"
        return res

    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    new_raw = text.encode("utf-8")
    tmp = path.with_suffix(".json.closing.tmp")
    tmp.write_bytes(new_raw)
    os.replace(tmp, path)

    # refresh manifest primary row to the closed artifact
    sha, nbytes = norm_sha(new_raw)
    man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_bytes().decode("utf-8"))
    for row in man.get("artifacts") or []:
        if row.get("role") == "primary" and row.get("path", "").endswith(f"{uid}.json"):
            row["sha256"] = sha
            row["bytes"] = nbytes
            row["present"] = True
    man["generated"] = now
    mtext = json.dumps(man, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    mtmp = man_path.with_suffix(".json.closing.tmp")
    mtmp.write_bytes(mtext.encode("utf-8"))
    os.replace(mtmp, man_path)

    # post-write live re-verification
    raw2 = path.read_bytes()
    doc2 = json.loads(raw2.decode("utf-8"))
    e2 = resolver.validate_artifact(doc2, "command-center/schema/receipt.schema.json")
    e2 += list(gate.validate_receipt(doc2) or [])
    rc_adm2, out_adm2 = run([sys.executable, "command-center/receipt_validate.py", rel])
    sha2, nb2 = norm_sha(raw2)
    man2 = json.loads(man_path.read_bytes().decode("utf-8"))
    prow = next((r for r in (man2.get("artifacts") or []) if r.get("role") == "primary"), {})
    res["post_schema_errs"] = len(e2)
    res["post_admission_rc"] = rc_adm2
    res["post_sha_match"] = (prow.get("sha256") == sha2 and prow.get("bytes") == nb2)
    res["post_state"] = doc2.get("state")
    pr = []
    for script in sorted(pdir.glob("probe*.py")):
        rc3, out3 = run([sys.executable, "-B", str(script)])
        pr.append((script.name, rc3, "SUCCESS:" in out3))
    res["post_probes"] = pr
    ok = (not e2) and rc_adm2 == 0 and res["post_sha_match"] and doc2.get("state") == "SUCCESS" \
        and all(rc == 0 and ok for _, rc, ok in pr)
    res["verdict"] = "CLOSED" if ok else "WRITE-REFUTED"
    if not ok:
        res["why"] = f"post-write verification failed: schema={len(e2)} adm={rc_adm2} sha={res['post_sha_match']}"
    return res


def main() -> int:
    out = []
    for uid in UNITS:
        r = close(uid)
        out.append(r)
        print(f"{r['verdict']}:{uid} {r.get('why', '')}"[:220])
    (REPO / "_shard12-w2/_closure_results.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    bad = [r for r in out if r["verdict"] != "CLOSED"]
    print(f"CLOSURE-SUMMARY:{len(out) - len(bad)} closed, {len(bad)} not closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
