#!/usr/bin/env python3
"""Forward-repair of the w3s11 IMP-0223 closure (run3 wrote without rollback).

Scope guard: only proceeds when the receipt carries THIS reviewer's block
(w3s11-independent-reviewer-2026-10-26). Fixes:
  - drops the receipt self-row from artifacts[] (receipts cannot self-hash;
    AUD-0044 convention; c3 checks every row exactly)
  - re-points the recorded downstream consumer at the delivered module and
    proves it with the real program delivery gate (two-pass, deterministic)
Then: schema 0 errors, evaluate_full 12/12 SATISFIED, manifest rows
digest-match, canonical gate SUCCESS:delivered. Rollback on any failure.
"""
import hashlib
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
from receipt_schema_gate import validate_receipt, evaluate_full  # noqa: E402

UID = "IMP-0223"
RECEIPT_REL = "command-center/receipts/IMP-0223.json"
MAN_REL = "command-center/p2-wave/probes/IMP-0223/UNIT-ARTIFACT-MANIFEST.json"
MODULE_REL = "tools/gitcrypt-worktree/gitcrypt_worktree.py"
REVIEWER_ID = "w3s11-independent-reviewer-2026-10-26"


def digest(p):
    raw = Path(p).read_bytes().replace(bytes([13, 10]), bytes([10]))
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(*parts):
    return hashlib.sha256(chr(31).join(parts).encode("utf-8")).hexdigest()[:32]


def run(argv):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    env.pop("AST_INTEGRATE_ROOT", None)
    cp = subprocess.run(argv, cwd=str(REPO), env=env, capture_output=True,
                        text=True, timeout=600, encoding="utf-8", errors="replace")
    return cp.returncode, (cp.stdout or ""), (cp.stderr or "")


receipt_path = REPO / RECEIPT_REL
man_path = REPO / MAN_REL
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
rev = receipt.get("reviewer") or {}
if rev.get("reviewer_id") != REVIEWER_ID or rev.get("verdict") != "PASS" or rev.get("independent") is not True:
    print("FAILED:repair-scope receipt is not this reviewer's closure")
    raise SystemExit(1)
orig_receipt_bytes = receipt_path.read_bytes()
orig_man_bytes = man_path.read_bytes()
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

receipt["artifacts"] = [a for a in (receipt.get("artifacts") or [])
                        if str(a.get("path") or "") != RECEIPT_REL]
CONSUMER_CMD = "python command-center/p2-wave/_measure_one_delivered.py IMP-0223"
receipt["downstream_consumers"] = [{
    "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0223 (program delivery gate)",
    "artifact_path": MODULE_REL,
    "executed": True,
    "read_ok": True,
    "exit_code": 0,
    "probe": {
        "role": "verifier",
        "method": "command",
        "command": CONSUMER_CMD,
        "raw_output": "pending-consumer-run",
        "fingerprint": fp("verifier", "command", CONSUMER_CMD),
        "exit_code": 0,
    },
}]


def write_receipt(doc):
    tmp2 = receipt_path.with_suffix(".json.w3s11-tmp")
    tmp2.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="")
    os.replace(str(tmp2), str(receipt_path))


def rehash_manifest(note_update):
    m = json.loads(man_path.read_text(encoding="utf-8"))
    for a in m.get("artifacts") or []:
        if str(a.get("path") or "") == RECEIPT_REL:
            a["sha256"], _ = digest(receipt_path)
            a["bytes"] = receipt_path.stat().st_size
    if note_update:
        m["derivation"] = str(m.get("derivation") or "").split(" | w3s11 independent closure")[0] \
            + " | w3s11 independent closure " + now + ": receipt stamped SUCCESS (reviewer PASS, independent), receipt row re-hashed"
    tmp3 = man_path.with_suffix(".json.w3s11-tmp")
    tmp3.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="")
    os.replace(str(tmp3), str(man_path))


def gate_marker():
    rc, so, se = run([sys.executable, "command-center/p2-wave/_measure_one_delivered.py", UID])
    mk = ""
    for line in (so + se).splitlines():
        if line.startswith("SUCCESS:") or line.startswith("FAILED:"):
            mk = line
            break
    return rc, mk


def rollback(reason):
    receipt_path.write_bytes(orig_receipt_bytes)
    man_path.write_bytes(orig_man_bytes)
    print("ROLLED BACK: " + reason)
    print("FAILED:repair-rolled-back")
    raise SystemExit(1)


schema_errors = validate_receipt(receipt)
if schema_errors:
    print("FAILED:repair-schema-pre")
    for e in schema_errors[:10]:
        print("  - " + e)
    raise SystemExit(1)
print("schema: 0 errors pre-write")
write_receipt(receipt)
rehash_manifest(True)
rcA, mkA = gate_marker()
print("consumer-pass-A rc=" + str(rcA) + " marker=" + mkA)
if rcA != 0 or not mkA.startswith("SUCCESS:"):
    rollback("gate not green: " + mkA)
receipt["downstream_consumers"][0]["probe"]["raw_output"] = mkA
write_receipt(receipt)
rehash_manifest(False)
rcB, mkB = gate_marker()
print("consumer-pass-B rc=" + str(rcB) + " marker=" + mkB + " deterministic=" + str(mkA == mkB))
if rcB != 0 or mkA != mkB:
    rollback("gate marker nondeterministic or not green on final bytes")
fresh = json.loads(receipt_path.read_text(encoding="utf-8"))
result, extra = evaluate_full(fresh, repo_root=str(REPO))
print("gate-on-final:" + result.marker() + " complete=" + str(result.complete) + " coherence=" + str(len(extra)))
if not result.complete or extra:
    for c in result.conditions:
        if c.outcome != "SATISFIED":
            print("  c" + str(c.n) + "=" + c.outcome + " :: " + c.basis[:150])
    for x in extra:
        print("  coherence: " + str(x)[:150])
    rollback("12-condition gate incomplete on final receipt")
man2 = json.loads(man_path.read_text(encoding="utf-8"))
bad = []
for a in man2.get("artifacts") or []:
    rel = str(a.get("path") or "")
    fq = REPO / rel
    if not fq.is_file():
        bad.append("absent:" + rel)
        continue
    s3, _ = digest(fq)
    if s3 != str(a.get("sha256") or ""):
        bad.append("sha:" + rel)
if bad:
    rollback("manifest rows: " + "; ".join(bad[:4]))
print("manifest-postcheck: all rows digest-match live bytes")
new_sha, _ = digest(receipt_path)
print("SUCCESS:repair IMP-0223 closure complete receipt_sha256=" + new_sha)
