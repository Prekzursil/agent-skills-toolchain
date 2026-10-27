"""BUILD R1 -- would `ruff format` on the 45 cited probe scripts destroy declared evidence?

The repo has a live precedent that says evidence BYTES can outrank the style gate: ruff.toml
excludes `command-center/casualty/probes` because five scripts there are byte-identical to
dead agents' scratch originals and that match IS the recovery evidence. So before
reformatting 45 scripts that committed artifacts cite, ask the falsifiable question:

  does any COMMITTED artifact declare a DIGEST of one of these 45 files?

If yes -> reformatting silently invalidates a published receipt; exclude instead of format.
If no  -> the citations are path references only, and reformatting changes nothing a reader
          can verify against.

Method: for every committed line that names one of the 45, look for a hex run >= 12 chars
(sha256/md5 prefixes as used elsewhere in this repo) on that line or the two lines around it.

CONTROL (both states): the same scan is run against a filename that IS digest-declared
nearby -- `adv0022_probe2.py`, whose locked provenance the casualty lane published -- and
must FIRE. And against a name with no digest, which must stay quiet. Without the positive
side, "no digests found" could just mean the regex never matches anything.
"""

import json
import os
import re
import subprocess
import sys

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
OUT = os.path.join(ROOT, "command-center/slop-report/_b5_digest_lock.out.json")
HEX = re.compile(r"\b[0-9a-f]{12,64}\b")


def grep_ctx(names, ctx=2):
    """name -> list of (path, lineno, window_text) for committed lines naming it."""
    pfile = os.path.join(ROOT, "command-center/slop-report/_b5_pat.txt")
    with open(pfile, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(names) + "\n")
    r = subprocess.run(
        ["git", "-C", ROOT, "grep", "-I", "-F", "-n", f"-C{ctx}", "-f", pfile, "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    os.unlink(pfile)
    pat = re.compile(
        "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    )
    hits: dict[str, list] = {n: [] for n in names}
    # git grep -C emits context lines with '-' and matches with ':'; group by file block.
    block: list[str] = []
    for raw in r.stdout.splitlines() + ["--"]:
        if raw == "--":
            text = "\n".join(block)
            for m in set(x.group(0) for x in pat.finditer(text)):
                digs = sorted(set(HEX.findall(text)))
                if digs:
                    hits[m].append({"digests": digs[:4], "window": text[:400]})
            block = []
        else:
            block.append(raw)
    return hits


def main():
    cited = json.load(
        open(
            os.path.join(ROOT, "command-center/slop-report/_b1_cited_probes.out.json"),
            encoding="utf-8",
        )
    )["cited_names"]
    out = {"n_cited": len(cited)}

    hits = grep_ctx(cited)
    locked = {n: v for n, v in hits.items() if v}
    out["digest_adjacent_count"] = len(locked)
    out["digest_adjacent"] = {n: v[:2] for n, v in sorted(locked.items())}
    out["clean_count"] = len(cited) - len(locked)

    # ---- CONTROL -------------------------------------------------------------------------
    POS = (
        "adv0022_probe2.py"  # provenance-locked, digest published by the casualty lane
    )
    NEG = "_zzz_no_such_file_b5control.py"
    ctl = grep_ctx([POS, NEG])
    checks = {
        "positive_control_fires": len(ctl[POS]) > 0,
        "negative_control_quiet": len(ctl[NEG]) == 0,
    }
    out["control"] = {
        "positive": POS,
        "positive_hits": len(ctl[POS]),
        "positive_sample_digests": ctl[POS][0]["digests"] if ctl[POS] else [],
        "negative": NEG,
        "negative_hits": len(ctl[NEG]),
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }
    out["decision"] = (
        "EXCLUDE-not-format (digests declared)"
        if locked
        else "FORMAT-is-safe (no declared digests)"
    )

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(
        json.dumps(
            {k: v for k, v in out.items() if k != "digest_adjacent"},
            indent=1,
        )
    )
    print("digest_adjacent names:", sorted(locked))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
