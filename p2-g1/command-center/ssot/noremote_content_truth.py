"""Is the 5,518-blob gap real unique content, or line endings?

`noremote_and_alias.py` measured that two no-remote checkouts under Temp/adv0010 each hold
5,518 tracked blobs whose SHA is absent from the canonical store. Reporting that as "unique
content at risk" would be this lane's recurring overclaim: blob-SHA identity is not content
identity. Round 1 already burned a control on exactly this -- its content signal read
`positive=False negative=False` because the working tree is CRLF and git stores LF, so the
signal could never fire.

So: for every absent blob, fetch the bytes, recompute the git blob hash BOTH raw and after
CRLF->LF normalisation, and ask canonical whether it holds the normalised form. A blob that
is absent raw but present normalised is the SAME CONTENT stored with different line endings,
and carries no data-loss risk at all.

Three buckets, and the middle one is the whole point:
    absent-raw AND absent-normalised  -> genuinely unique bytes
    absent-raw BUT present-normalised -> line endings only, redundant
    path also absent from canonical   -> reported separately, since a new PATH is a
                                         different claim from new BYTES

CONTROLS, both states:
  hasher      re-hashing a blob canonical is known to hold must reproduce that exact SHA,
              and a deliberately mangled copy of the same bytes must NOT. A hasher that
              cannot tell those apart makes every number below meaningless.
  reader      a known-present SHA reads present and a fabricated SHA reads absent, through
              the same batched reader used for the verdict.

Read-only: cat-file only. Nothing written outside this directory, nothing deleted.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "noremote-content-truth.json"

CANONICAL = "C:/Users/Prekzursil/source/agent-skills-toolchain"
TARGETS = [
    "C:/Users/Prekzursil/Local Settings/Application Data/Application Data/Application Data/Temp/adv0010/repo",
    "C:/Users/Prekzursil/Local Settings/Application Data/Application Data/Application Data/Temp/adv0010/repo2",
]
FAB_SHA = "0" * 39 + "1"


def blob_sha(data: bytes) -> str:
    h = hashlib.sha1(usedforsecurity=False)
    h.update(b"blob " + str(len(data)).encode() + b"\0")
    h.update(data)
    return h.hexdigest()


def run(args: list[str], cwd: str, stdin: bytes | None = None) -> tuple[int, bytes]:
    p = subprocess.run(args, cwd=cwd, input=stdin, capture_output=True)
    return p.returncode, p.stdout


def batch_present(store: str, shas: list[str]) -> dict[str, bool]:
    if not shas:
        return {}
    rc, out = run(
        ["git", "cat-file", "--batch-check", "--buffer"],
        store,
        stdin=("\n".join(shas) + "\n").encode(),
    )
    res: dict[str, bool] = {}
    for line, sha in zip(out.decode("utf-8", "replace").splitlines(), shas):
        res[sha] = "missing" not in line
    for s in shas:
        res.setdefault(s, False)
    return res


def batch_read(store: str, shas: list[str]) -> dict[str, bytes]:
    """One spawn. Parses the `<sha> <type> <size>\\n<payload>\\n` stream."""
    if not shas:
        return {}
    rc, out = run(
        ["git", "cat-file", "--batch", "--buffer"],
        store,
        stdin=("\n".join(shas) + "\n").encode(),
    )
    res: dict[str, bytes] = {}
    i = 0
    n = len(out)
    while i < n:
        j = out.find(b"\n", i)
        if j < 0:
            break
        header = out[i:j].decode("utf-8", "replace").split()
        i = j + 1
        if len(header) < 3:
            continue
        sha, size = header[0], int(header[2])
        res[sha] = out[i : i + size]
        i += size + 1
    return res


def main() -> int:
    # ------------------------------------------------------------------ CONTROLS
    rc, tree = run(["git", "ls-tree", "-r", "HEAD"], CANONICAL)
    known_sha, known_path = "", ""
    for ln in tree.decode("utf-8", "replace").splitlines():
        parts = ln.split(maxsplit=3)
        if len(parts) >= 4 and parts[1] == "blob":
            known_sha, known_path = parts[2], parts[3]
            break
    payload = batch_read(CANONICAL, [known_sha]).get(known_sha, b"")
    rehash = blob_sha(payload)
    mangled = blob_sha(payload + b"\n# SSOT-CONTROL-MANGLE\n")
    hasher_ok = rehash == known_sha and mangled != known_sha
    print(f"CONTROL hasher: rehash matches source blob : {rehash == known_sha}")
    print(f"CONTROL hasher: mangled copy differs       : {mangled != known_sha}")
    print(f"  ({known_path}, {len(payload)} B)  discriminates: {hasher_ok}")

    probe = batch_present(CANONICAL, [known_sha, FAB_SHA])
    reader_ok = probe.get(known_sha) is True and probe.get(FAB_SHA) is False
    print(
        f"CONTROL reader: known={probe.get(known_sha)} fabricated={probe.get(FAB_SHA)}"
        f"  discriminates: {reader_ok}"
    )
    if not (hasher_ok and reader_ok):
        print("FAILED:noremote-content-truth controls did not discriminate")
        return 3

    # canonical's full path set, so "new PATH" can be separated from "new BYTES".
    canon_paths = set()
    for ref in ("HEAD", "origin/main"):
        rc, t = run(["git", "ls-tree", "-r", "--name-only", ref], CANONICAL)
        if rc == 0:
            canon_paths |= set(t.decode("utf-8", "replace").splitlines())
    print(
        f"\ncanonical distinct tracked paths (HEAD + origin/main): {len(canon_paths)}"
    )

    results = []
    for target in TARGETS:
        if not Path(target).exists():
            continue
        rc, t = run(["git", "ls-tree", "-r", "HEAD"], target)
        blobs: dict[str, str] = {}
        for ln in t.decode("utf-8", "replace").splitlines():
            parts = ln.split(maxsplit=3)
            if len(parts) >= 4 and parts[1] == "blob":
                blobs[parts[2]] = parts[3].strip()

        present_raw = batch_present(CANONICAL, sorted(blobs))
        absent = sorted(s for s, ok in present_raw.items() if not ok)
        print(f"\n{target}")
        print(f"  tracked blobs {len(blobs)}   absent by raw SHA {len(absent)}")

        payloads = batch_read(target, absent)
        norm_sha: dict[str, str] = {}
        crlf_count = 0
        for s in absent:
            data = payloads.get(s, b"")
            if b"\r\n" in data:
                crlf_count += 1
            norm_sha[s] = blob_sha(data.replace(b"\r\n", b"\n"))
        present_norm = batch_present(CANONICAL, sorted(set(norm_sha.values())))

        eol_only, truly_unique = [], []
        for s in absent:
            (eol_only if present_norm.get(norm_sha[s]) else truly_unique).append(s)

        new_paths = [blobs[s] for s in truly_unique if blobs[s] not in canon_paths]
        known_path_new_bytes = [
            blobs[s] for s in truly_unique if blobs[s] in canon_paths
        ]

        print(f"  bytes read back                   : {len(payloads)}")
        print(f"  blobs containing CRLF             : {crlf_count}")
        print(
            f"  absent raw BUT present LF-normalised : {len(eol_only)}  <- line endings only"
        )
        print(f"  genuinely absent both ways           : {len(truly_unique)}")
        print(f"      of those, path unknown to canonical : {len(new_paths)}")
        print(
            f"      of those, path known (content differs): {len(known_path_new_bytes)}"
        )
        for ex in sorted(new_paths)[:10]:
            print(f"        NEW PATH  {ex}")
        for ex in sorted(known_path_new_bytes)[:5]:
            print(f"        DIFFERS   {ex}")

        results.append(
            {
                "path": target,
                "tracked_blobs": len(blobs),
                "absent_raw": len(absent),
                "blobs_with_crlf": crlf_count,
                "eol_only_redundant": len(eol_only),
                "truly_unique": len(truly_unique),
                "unique_new_paths": sorted(new_paths)[:50],
                "unique_new_paths_count": len(new_paths),
                "unique_known_paths_count": len(known_path_new_bytes),
                "unique_known_paths": sorted(known_path_new_bytes)[:50],
            }
        )

    report = {
        "controls": {
            "hasher_reproduces_source": rehash == known_sha,
            "hasher_rejects_mangled": mangled != known_sha,
            "reader_known_present": probe.get(known_sha),
            "reader_fabricated_absent": probe.get(FAB_SHA),
            "discriminates": hasher_ok and reader_ok,
        },
        "canonical_tracked_paths": len(canon_paths),
        "targets": results,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwrote {OUT}")
    total_unique = sum(r["truly_unique"] for r in results)
    print(
        f"SUCCESS:noremote-content-truth targets={len(results)} "
        f"eol_only={sum(r['eol_only_redundant'] for r in results)} unique={total_unique}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
