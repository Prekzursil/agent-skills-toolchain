"""BUILD R1 -- is any digest declared NEAR a probe's name actually the digest OF that file?

_b5 found 5 of the 45 cited probes have a hex run within +/-2 lines of their name in a
committed artifact. Adjacency is NOT identity: the digest could be of the probe's OUTPUT, of
a commit, or of an unrelated payload. Counting the document instead of the FIELD is the
use-vs-mention error, so decide it by exact arithmetic instead of reading prose.

For each of the 5, compute sha256 and md5 over the file's real bytes and over its LF-only
form, and test every declared digest as a PREFIX of any of them.

  match     -> the file is byte-locked by a published receipt; do NOT reformat it.
  no match  -> the adjacency is coincidental; reformatting invalidates nothing verifiable.

CONTROL (both states): the same matcher is run on the known-locked casualty probe
`adv0022_probe2.py` against the digests the casualty lane published for it -- it MUST match.
A matcher that finds nothing everywhere is indistinguishable from a broken matcher, so the
positive side is what makes a null result meaningful. A deliberately corrupted copy of the
same file must NOT match.
"""

import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
OUT = os.path.join(ROOT, "command-center/slop-report/_b6_digest_match.out.json")
HEX = re.compile(r"\b[0-9a-f]{12,64}\b")


def digests_of(data: bytes):
    lf = data.replace(b"\r\n", b"\n")
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "md5": hashlib.md5(data, usedforsecurity=False).hexdigest(),
        "sha256_lf": hashlib.sha256(lf).hexdigest(),
        "md5_lf": hashlib.md5(lf, usedforsecurity=False).hexdigest(),
    }


def declared_near(name, ctx=2):
    r = subprocess.run(
        ["git", "-C", ROOT, "grep", "-I", "-F", "-n", f"-C{ctx}", "-e", name, "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return sorted(set(HEX.findall(r.stdout)))


def test(name, path):
    data = open(path, "rb").read()
    d = digests_of(data)
    declared = declared_near(name)
    matches = []
    for dec in declared:
        for kind, full in d.items():
            if full.startswith(dec) or dec.startswith(full):
                matches.append({"declared": dec, "kind": kind})
    return {
        "file": name,
        "bytes": len(data),
        "own_digests": {k: v[:16] for k, v in d.items()},
        "n_declared_nearby": len(declared),
        "declared_sample": declared[:6],
        "matches": matches,
        "locked": bool(matches),
    }


def main():
    suspects = [
        "_d1_reverify_artifacts.py",
        "_imp2_build.py",
        "_m1_deny_cost.py",
        "_m1_drift_probe.py",
        "_p14_manifest_verify.py",
    ]
    out = {"suspects": {}}
    for n in suspects:
        out["suspects"][n] = test(n, os.path.join(ROOT, "command-center", n))
    out["locked_count"] = sum(1 for v in out["suspects"].values() if v["locked"])

    # ---- CONTROL --------------------------------------------------------------------------
    pos_name = "adv0022_probe2.py"
    pos_path = os.path.join(ROOT, "command-center/casualty/probes", pos_name)
    pos = test(pos_name, pos_path)
    corrupt = digests_of(open(pos_path, "rb").read() + b"\n# corrupted\n")
    declared_pos = declared_near(pos_name)
    corrupt_match = any(
        full.startswith(dec) or dec.startswith(full)
        for dec in declared_pos
        for full in corrupt.values()
    )
    checks = {
        "positive_locked_file_matches": pos["locked"],
        "corrupted_copy_does_not_match": not corrupt_match,
    }
    out["control"] = {
        "positive": pos,
        "corrupted_copy_matched": corrupt_match,
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }
    out["decision"] = (
        "EXCLUDE-not-format"
        if out["locked_count"]
        else "FORMAT-is-safe for all 45 (no digest identifies a probe file)"
    )

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1)[:3500])
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
