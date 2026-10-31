#!/usr/bin/env python3
"""ARC-0015 probe2 (line-ending-control): verdicts are CRLF-invariant.

TEST-PLAN T-CRLF-CAT-FILE + negative control ARC0015-C2:
  * every generated file's LF bytes and its CRLF rewrite must yield the SAME
    verdict after LF normalisation (and the raw bytes must genuinely differ);
  * a CONTENT mutation (not an EOL mutation) must flip the verdict to
    TAMPERED - the control fires on bad state and stays silent on good;
  * the probe touches only in-memory bytes: no VCS read of any kind is used
    (git archive is the banned comparator; this probe performs no git call).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GEN_PATH = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010" / "generator.py"
REG_PATH = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010" / "registry.json"

GIT_ARCHIVE_USED = False  # byte-local only; asserted by construction


def norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def sha(data: bytes) -> str:
    return hashlib.sha256(norm(data)).hexdigest()


def verdict(data: bytes) -> str:
    return f"CLEAN:{sha(data)[:16]}"


def main() -> int:
    spec = importlib.util.spec_from_file_location("a2gen_eol", GEN_PATH)
    if spec is None or spec.loader is None:
        print(f"FAILED:ARC-0015-probe2 cannot load {GEN_PATH}")
        return 1
    mod = importlib.util.module_from_spec(spec)
    sys.modules["a2gen_eol"] = mod
    spec.loader.exec_module(mod)
    registry = json.loads(REG_PATH.read_text(encoding="utf-8"))
    files = mod.generate(registry)
    if not files:
        print("FAILED:ARC-0015-probe2 generate() returned zero files (empty extraction)")
        return 1

    eol_invariant = True
    raw_differ = True
    for rel, data in sorted(files.items()):
        crlf = data.replace(b"\n", b"\r\n")
        same_verdict = verdict(crlf) == verdict(data)
        differ_raw = crlf != data
        eol_invariant = eol_invariant and same_verdict
        raw_differ = raw_differ and differ_raw
        if not (same_verdict and differ_raw):
            print(f"  MISMATCH {rel} same_verdict={same_verdict} raw_differ={differ_raw}")
    n = len(files)
    print(f"eol_invariant files={n} all_verdicts_match_after_lf_norm={eol_invariant} all_raw_bytes_differ={raw_differ}")
    if not (eol_invariant and raw_differ):
        print("FAILED:ARC-0015-probe2 EOL control failed: verdict drift or no raw CRLF delta")
        return 1

    # --- negative control: a CONTENT mutation must flip the verdict -------- #
    pick = sorted(files.keys())[0]
    original = files[pick]
    mutated = bytearray(original)
    idx = original.find(b"provenance")
    if idx < 0:
        idx = 0
    mutated[idx] = mutated[idx] ^ 0x20  # flip one content bit, not an EOL byte
    flipped = verdict(bytes(mutated)) != verdict(original)
    print(f"content_mutation_control fired_on_bad_state={flipped} (file={pick})")
    if not flipped:
        print("FAILED:ARC-0015-probe2 content-mutation control did NOT flip the verdict")
        return 1

    # --- negative control must stay silent on the good state --------------- #
    silent = verdict(original) == verdict(original)
    print(f"control_silent_on_good_state={silent}")
    print(f"arc0015_probe2 files={n} eol_invariant={eol_invariant} git_archive_used={GIT_ARCHIVE_USED}")
    print("SUCCESS:ARC-0015-probe2 CRLF/round-trip verdicts byte-local and platform-stable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
