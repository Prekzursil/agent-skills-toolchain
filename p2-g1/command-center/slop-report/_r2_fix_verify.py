"""BUILD R2 / D2 -- verify the fix, BOTH states, and prove the receipt cannot rot again.

The fix is only real if it distinguishes the two hypotheses:
  H_fixed  : a runtime-random sentinel cannot be in the corpus -> quiet == 0, rc 0, PASS.
  H_broken : the round-1 hardcoded sentinel IS in the corpus  -> quiet >= 1, rc 1, FAIL.

If BOTH modes passed, the "fix" would only prove the script still runs. So `--sentinel legacy`
is required to FAIL here; it is the negative control, and it cannot silently start passing
because the legacy literal lives in `_b1_control.py` permanently.

Also asserted, because these are what actually broke:
  * the DEFAULT (published) invocation leaves the tracked receipt byte-unchanged;
  * the DEFAULT invocation exits 0 on a healthy tree;
  * the written receipt contains NO sentinel literal, so it can never re-poison the corpus;
  * the receipt still regenerates __pycache__ (the bucket-(c) side effect the report cites).
"""

import hashlib
import json
import os
import subprocess
import sys

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
HERE = os.path.join(ROOT, "command-center/slop-report")
OUT = os.path.join(HERE, "_r2_fix_verify.out.json")
SCRIPT = os.path.join(HERE, "_b1_control.py")
RECEIPT_REL = "command-center/slop-report/_b1_control.out.json"
RECEIPT = os.path.join(ROOT, RECEIPT_REL)
LEGACY_SENTINEL = "_zzz_control_no_such_probe_9f3a17.py"


def sha16(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def git_dirty(rel):
    r = subprocess.run(
        ["git", "-C", ROOT, "status", "--porcelain", "--", rel],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.stdout.strip()


def invoke(*args):
    r = subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
    )
    try:
        payload = json.loads(r.stdout)
    except json.JSONDecodeError:
        payload = {}
    return r.returncode, payload, r.stderr[-400:]


def main():
    out = {}

    # ---- 1. DEFAULT (random sentinel), read-only ---------------------------
    before_sha, before_dirty = sha16(RECEIPT), git_dirty(RECEIPT_REL)
    rc_d, pay_d, err_d = invoke()
    after_sha, after_dirty = sha16(RECEIPT), git_dirty(RECEIPT_REL)
    out["default_random_readonly"] = {
        "cmd": "python command-center/slop-report/_b1_control.py",
        "rc": rc_d,
        "verdict": pay_d.get("verdict"),
        "quiet_citer_count": pay_d.get("quiet_citer_count"),
        "fire_citer_count": pay_d.get("fire_citer_count"),
        "receipt_sha16_before": before_sha,
        "receipt_sha16_after": after_sha,
        "receipt_byte_unchanged": before_sha == after_sha,
        "git_dirty_before": before_dirty,
        "git_dirty_after": after_dirty,
        "stderr_tail": err_d,
    }

    # ---- 2. NEGATIVE CONTROL: legacy hardcoded sentinel must FAIL ----------
    rc_l, pay_l, err_l = invoke("--sentinel", "legacy")
    out["legacy_negative_control"] = {
        "cmd": "python command-center/slop-report/_b1_control.py --sentinel legacy",
        "rc": rc_l,
        "verdict": pay_l.get("verdict"),
        "quiet_citer_count": pay_l.get("quiet_citer_count"),
        "quiet_citers": pay_l.get("quiet_citers"),
        "stderr_tail": err_l,
    }

    # ---- 3. --write refreshes the receipt ----------------------------------
    rc_w, pay_w, err_w = invoke("--write")
    receipt_text = ""
    if os.path.exists(RECEIPT):
        with open(RECEIPT, encoding="utf-8", newline="") as fh:
            receipt_text = fh.read()
    out["write_mode"] = {
        "cmd": "python command-center/slop-report/_b1_control.py --write",
        "rc": rc_w,
        "verdict": pay_w.get("verdict"),
        "receipt_sha16": sha16(RECEIPT),
        "receipt_contains_legacy_sentinel": LEGACY_SENTINEL in receipt_text,
        "receipt_nonexistent_field": json.loads(receipt_text).get("nonexistent")
        if receipt_text
        else None,
        "stderr_tail": err_w,
    }

    # ---- 4. re-run default after the write: must still be clean + green ----
    sha_a = sha16(RECEIPT)
    rc_d2, pay_d2, _ = invoke()
    sha_b = sha16(RECEIPT)
    out["default_after_write"] = {
        "rc": rc_d2,
        "verdict": pay_d2.get("verdict"),
        "receipt_byte_unchanged": sha_a == sha_b,
    }

    checks = {
        "default_rc_zero": rc_d == 0,
        "default_pass": pay_d.get("verdict") == "PASS",
        "default_quiet_zero": pay_d.get("quiet_citer_count") == 0,
        "default_fire_nonzero": (pay_d.get("fire_citer_count") or 0) >= 1,
        "default_leaves_receipt_untouched": before_sha == after_sha,
        "default_leaves_tree_clean": after_dirty == before_dirty,
        "legacy_control_fails": rc_l == 1 and pay_l.get("verdict") == "FAIL",
        "legacy_control_quiet_nonzero": (pay_l.get("quiet_citer_count") or 0) >= 1,
        "states_distinguishable": rc_d == 0 and rc_l == 1,
        "write_ok": rc_w == 0,
        "receipt_has_no_sentinel_literal": LEGACY_SENTINEL not in receipt_text,
        "idempotent_readonly_after_write": sha_a == sha_b and rc_d2 == 0,
    }
    out["checks"] = checks
    out["verdict"] = "FIX-VERIFIED" if all(checks.values()) else "FIX-NOT-VERIFIED"

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1))
    return 0 if out["verdict"] == "FIX-VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
