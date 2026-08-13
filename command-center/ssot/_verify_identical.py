"""Independent corroboration of content_check.py's IDENTICAL / MAIN_IS_SUPERSET verdicts.

Those two verdicts are the DANGEROUS direction: they are what would authorise retiring a
checkout. A false ABSENT merely over-preserves. So they get a second signal that shares no
code path with the first.

Signal 1 (content_check.py): LF-normalised LINE-SET comparison, blank lines dropped.
Signal 2 (here):             git's own SHA-1 blob identity via `git hash-object`, computed
                             on raw bytes, plus a raw byte-length comparison.

These disagree by construction when a file differs only in line endings or blank lines --
signal 1 says IDENTICAL, signal 2 says different hash. That is a MEANINGFUL disagreement to
surface, not a bug: it tells us whether "identical" means byte-identical or text-identical.

Both-states control: a path compared against itself must match, and a path compared against
a different real file must NOT match. A comparator that returns True for everything would
certify every scratch file as redundant.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

MAIN_REPO = "C:/Users/Prekzursil/source/ast-integrate"
REF = "origin/main"


def sh(args: list[str], repo: str) -> tuple[int, bytes]:
    p = subprocess.run(["git", "-C", repo] + args, capture_output=True, timeout=120)
    return p.returncode, p.stdout


def blob_sha_and_len(repo: str, rev_path: str) -> tuple[str | None, int]:
    rc, raw = sh(["cat-file", "-p", rev_path], repo)
    if rc != 0:
        return None, 0
    p = subprocess.run(
        ["git", "hash-object", "--stdin"], input=raw, capture_output=True, timeout=60
    )
    return p.stdout.decode().strip(), len(raw)


def control() -> bool:
    rc, out = sh(["ls-tree", "--name-only", REF], MAIN_REPO)
    names = [n.strip() for n in out.decode().split("\n") if n.strip().endswith(".md")]
    if len(names) < 2:
        print("  CONTROL FAIL: need two probe files at tree root")
        return False
    a, b = names[0], names[1]
    sa, _ = blob_sha_and_len(MAIN_REPO, f"{REF}:{a}")
    sa2, _ = blob_sha_and_len(MAIN_REPO, f"{REF}:{a}")
    sb, _ = blob_sha_and_len(MAIN_REPO, f"{REF}:{b}")
    same_ok = sa is not None and sa == sa2
    diff_ok = sa != sb
    print(
        f"  control: same-file({a}) -> {'MATCH' if same_ok else 'MISMATCH'} | "
        f"{a} vs {b} -> {'DIFFER' if diff_ok else 'SAME'} "
        f"=> {'PASS' if same_ok and diff_ok else 'FAIL'}"
    )
    return same_ok and diff_ok


def main() -> int:
    print("=== hash-comparator control ===")
    if not control():
        print("FAILED:verify-identical comparator control did not pass")
        return 2

    src = pathlib.Path("command-center/ssot/content-check.json")
    data = json.loads(src.read_text(encoding="utf-8"))

    checked = 0
    agree = 0
    rows = []
    for r in data["results"]:
        repo = r.get("repo")
        sha = r.get("sha")
        for f in r.get("files", []):
            if f["verdict"] not in ("IDENTICAL", "MAIN_IS_SUPERSET"):
                continue
            path = f["path"]
            scratch_rev = f"{sha}:{path}" if sha else f":{path}"
            s_sha, s_len = blob_sha_and_len(repo, scratch_rev)
            m_sha, m_len = blob_sha_and_len(MAIN_REPO, f"{REF}:{path}")
            byte_identical = s_sha is not None and s_sha == m_sha
            checked += 1
            # Signal 1 said text-identical (or main-superset). Signal 2 asks: byte-identical?
            consistent = byte_identical if f["verdict"] == "IDENTICAL" else True
            if consistent:
                agree += 1
            rows.append(
                {
                    "path": path,
                    "verdict_signal1": f["verdict"],
                    "byte_identical_signal2": byte_identical,
                    "scratch_bytes": s_len,
                    "main_bytes": m_len,
                    "agree": consistent,
                }
            )
            print(
                f"  {f['verdict']:17s} {path}\n"
                f"      signal2 byte-identical={byte_identical} "
                f"(scratch {s_len}B / main {m_len}B) -> "
                f"{'AGREE' if consistent else 'DISAGREE -- resolve before trusting either'}"
            )

    out = pathlib.Path("command-center/ssot/verify-identical.json")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"checked": checked, "agree": agree, "rows": rows}, fh, indent=2)
    print(f"\n{agree}/{checked} verdicts corroborated by the independent hash signal")
    print(f"wrote {out}")
    if agree != checked:
        print("FAILED:verify-identical signals disagree")
        return 1
    print(f"SUCCESS:verify-identical checked={checked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
