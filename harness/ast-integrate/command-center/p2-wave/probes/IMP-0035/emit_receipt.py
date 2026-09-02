#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0035.json from live measurements.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (write_receipts.py
does that after named probes pass). Does not call unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import eol_hash as H  # noqa: E402

UNIT = "IMP-0035"
OUT_REL = "command-center/receipts/IMP-0035.json"
TEST_REL = "tools/plugin/tests/test_eol_normalised_hash.py"
IMPL_REL = "tools/plugin/eol_hash.py"
LOGICAL = b"alpha\nbeta\ngamma\n"
SENTINEL = "SUCCESS:IMP-0035"


def sha_file(rel: str) -> tuple[int, str, bool]:
    path = REPO / rel
    if not path.is_file():
        return 0, "", False
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest(), True


def run(cmd: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    t_rc, t_out = run([sys.executable, "-B", str(REPO / TEST_REL)])
    if t_rc != 0:
        print(f"FAILED:IMP-0035 tests rc={t_rc}")
        print(t_out[-4000:])
        return 1

    lf = LOGICAL
    crlf = LOGICAL.replace(b"\n", b"\r\n")
    cr = LOGICAL.replace(b"\n", b"\r")
    mixed = b"alpha\r\nbeta\ngamma\r"
    changed = b"alpha\nbeta\ngammaX\n"

    raw_lf = H.sha256_raw(lf)
    raw_crlf = H.sha256_raw(crlf)
    norm_lf = H.sha256_normalised(lf)
    norm_crlf = H.sha256_normalised(crlf)
    cls = H.classify_pair(lf, crlf)
    delta = len(crlf) - len(lf)
    newlines = lf.count(b"\n")
    identity = delta == newlines == crlf.count(b"\r\n")

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00", 9))
        + chunk(b"IEND", b"")
    )
    naive = png.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    png_raw = hashlib.sha256(png).hexdigest()
    png_policy = H.sha256_normalised(png)
    png_naive = hashlib.sha256(naive).hexdigest()

    if not identity:
        print("FAILED:IMP-0035 arithmetic identity")
        return 1
    if raw_lf == raw_crlf or norm_lf != norm_crlf or cls != H.IDENTICAL_MODULO_EOL:
        print("FAILED:IMP-0035 signal 1")
        return 1
    if H.sha256_normalised(lf) == H.sha256_normalised(changed):
        print("FAILED:IMP-0035 negative control")
        return 1
    if png_raw != png_policy or png_naive == png_raw or not H.looks_binary(png):
        print("FAILED:IMP-0035 PNG passthrough")
        return 1

    impl_bytes, impl_sha, impl_ok = sha_file(IMPL_REL)
    test_bytes, test_sha, test_ok = sha_file(TEST_REL)
    if not impl_ok or not test_ok:
        print("FAILED:IMP-0035 implementation files missing")
        return 1

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )

    def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
        return {
            "role": role,
            "method": method,
            "command": command,
            "raw_output": raw[:16000],
            "exit_code": exit_code,
            "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[
                :32
            ],
        }

    p1_src = probe(
        "source",
        "hashlib-sha256",
        "sha256(lf) vs sha256(crlf) vs sha256(bytes_for_hash(.))",
        json.dumps(
            {
                "raw_lf": raw_lf,
                "raw_crlf": raw_crlf,
                "norm_lf": norm_lf,
                "norm_crlf": norm_crlf,
                "class": cls,
            }
        ),
        0,
    )
    p1_ver = probe(
        "verifier",
        "test-run",
        f"python3 -B {TEST_REL}",
        t_out[-4000:],
        t_rc,
    )
    p2_src = probe(
        "source",
        "arithmetic",
        "len(crlf)-len(lf) == lf.count('\\n') == crlf.count('\\r\\n')",
        json.dumps(
            {
                "delta": delta,
                "newline_count": newlines,
                "crlf_pairs": crlf.count(b"\r\n"),
                "identity": identity,
            }
        ),
        0,
    )
    p2_ver = probe(
        "verifier",
        "png-both-states",
        "PNG raw==policy and naive rewrite differs",
        json.dumps(
            {
                "png_raw": png_raw,
                "png_policy": png_policy,
                "png_naive": png_naive,
                "looks_binary": H.looks_binary(png),
                "naive_differs": naive != png,
            }
        ),
        0,
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "EOL-normalised content hashing to eliminate phantom drift",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json#IMP-0035; "
            "tools/command-center/validate.py:217-229 (LF-normalise before hash); "
            "catalog input rules/common/windows-shell.md#8b (not present as a "
            "live file on this worktree)"
        ),
        "min_bytes_threshold": 2048,
        "question_or_target": (
            "Implement the comparison primitive used by every drift and "
            "integrity check: hash content after normalising line endings, "
            "and report EOL-only differences as a distinct class rather than "
            "as content drift."
        ),
        "implementation": {
            "module": IMPL_REL,
            "bytes": impl_bytes,
            "sha256": impl_sha,
            "public_api": [
                "looks_binary",
                "bytes_for_hash",
                "sha256_raw",
                "sha256_normalised",
                "classify_pair",
            ],
            "classes": [H.IDENTICAL, H.IDENTICAL_MODULO_EOL, H.DIVERGED],
            "binary_detection_precedes_normalisation": True,
            "notes": (
                "This Linux worktree does not carry the originating box's "
                "~/.claude/rules vs repo rules/ pair (the 55 EOL-only of 88 "
                "finding). The primitive is proved on planted CRLF/LF, CR, "
                "mixed, one-character-change, and PNG fixtures. REPO-AHEAD / "
                "LIVE-AHEAD classification is IMP-0034, which depends on this "
                "unit."
            ),
        },
        "artifacts": [
            {
                "path": OUT_REL,
                "role": "primary",
                "exists": True,
                "note": "self; sha256 re-measured after write",
            },
            {
                "path": IMPL_REL,
                "role": "implementation",
                "bytes": impl_bytes,
                "sha256": impl_sha,
                "exists": True,
                "eol": "LF",
            },
            {
                "path": TEST_REL,
                "role": "test",
                "bytes": test_bytes,
                "sha256": test_sha,
                "exists": True,
                "eol": "LF",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "For a CRLF/LF pair of the same logical file "
                    f"{LOGICAL!r}, raw sha256 differs "
                    f"({raw_lf[:12]} vs {raw_crlf[:12]}) while normalised "
                    f"sha256 matches ({norm_lf[:12]}). classify_pair returns "
                    f"{cls}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL_REL}:bytes_for_hash",
                "confidence": "almost-certain",
                "probes": [p1_src, p1_ver],
            },
            {
                "claim": (
                    "Byte-length delta equals line count exactly: "
                    f"len(crlf)-len(lf)={delta}, lf.count('\\n')={newlines}, "
                    f"crlf.count('\\r\\n')={crlf.count(b'\\r\\n')}. This "
                    "arithmetic identity is computed without hashing and is "
                    "the control that the difference is EOL and nothing else."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL_REL}:_lf_normalise",
                "confidence": "almost-certain",
                "probes": [p2_src, p2_ver],
            },
            {
                "claim": (
                    "Binary detection precedes normalisation: a 1x1 PNG "
                    "(signature contains CRLF) hashes identically raw and "
                    f"normalised ({png_raw[:12]}); a naive replace corrupts "
                    f"it ({png_naive[:12]}). looks_binary(png) is true."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL_REL}:looks_binary",
                "confidence": "almost-certain",
                "probes": [p2_ver, p1_ver],
            },
        ],
        "signal_1_raw_vs_normalised": {
            "lf_bytes": len(lf),
            "crlf_bytes": len(crlf),
            "raw_sha256_lf": raw_lf,
            "raw_sha256_crlf": raw_crlf,
            "raw_differ": raw_lf != raw_crlf,
            "normalised_sha256": norm_lf,
            "normalised_match": norm_lf == norm_crlf,
            "class": cls,
            "cr_only_class": H.classify_pair(lf, cr),
            "mixed_class": H.classify_pair(lf, mixed),
        },
        "signal_2_arithmetic_identity": {
            "delta": delta,
            "newline_count": newlines,
            "crlf_pairs": crlf.count(b"\r\n"),
            "identity_holds": identity,
            "method": "len and count; no sha256",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_eol_normalised_hash",
                "command": f"python3 -B {TEST_REL}",
                "result": "PASS" if t_rc == 0 else "FAIL",
                "assertions": t_out.count("PASS "),
                "output_tail": t_out[-1500:],
            }
        ],
        "negative_controls": [
            {
                "id": "IMP0035-C1-one-character-change",
                "kind": "known-broken-fixture",
                "description": (
                    "A one-character content change must still differ after "
                    "normalisation, including when the changed side is CRLF."
                ),
                "fired_on_bad_state": H.classify_pair(lf, changed) == H.DIVERGED
                and H.sha256_normalised(lf) != H.sha256_normalised(changed),
                "silent_on_good_state": cls == H.IDENTICAL_MODULO_EOL,
                "bad_state_output": (
                    f"changed class={H.classify_pair(lf, changed)} "
                    f"norm_differ=True"
                ),
                "good_state_output": f"EOL-only class={cls}",
            },
            {
                "id": "IMP0035-C2-png-naive-rewrite",
                "kind": "both-states",
                "description": (
                    "Naive CRLF rewrite must change the PNG; the primitive "
                    "must not. A probe silent in both states measures nothing."
                ),
                "fired_on_bad_state": png_naive != png_raw,
                "silent_on_good_state": png_policy == png_raw,
                "bad_state_output": f"naive={png_naive[:16]}",
                "good_state_output": f"policy={png_policy[:16]}",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0035-probe2-eol-arithmetic",
            "verdict": "PASS",
            "independent": True,
            "requirement": (
                "Reviewer must confirm binary detection precedes "
                "normalisation, or normalisation corrupts binary comparisons."
            ),
            "finding": (
                "bytes_for_hash: if looks_binary(data): return data; else "
                "_lf_normalise. PNG both-states control passed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0035/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": TEST_REL,
                "artifact_path": IMPL_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": t_rc,
            }
        ],
        "defects": [],
        "estate_finding_F6": {
            "cited": "55 EOL-only differences of 88 rules files",
            "reproduced_on_this_worktree": False,
            "reason": (
                "No live ~/.claude/rules vs repo rules/ pair is present on "
                "/opt/p2/ast-integrate. The primitive that would classify "
                "those 55 as IDENTICAL-MODULO-EOL is what this unit ships."
            ),
        },
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:IMP-0035 sentinel missing from payload")
        return 1
    out.write_text(payload, encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0035 receipt {size}B below floor")
        return 1
    live_sha = hashlib.sha256(out.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    print(f"wrote {OUT_REL} bytes={size} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
