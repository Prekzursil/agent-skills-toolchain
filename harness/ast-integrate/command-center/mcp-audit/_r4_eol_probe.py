#!/usr/bin/env python3
"""Measure the line endings of the blobs this lane shipped, with a control that fires.

WHY THIS EXISTS.  Round 3 shipped, as a statement of fact::

    "the `.md`/`.json` blobs carry CRLF (`ROUND3-DEFECT-CLOSURE.md` 278,
     `disposition.json` 840)"

An independent verifier measured both blobs at **0 CRLF** and both numbers as exact LINE
counts.  Round 3 also talked itself out of the correct reading using a control that could
not distinguish its two hypotheses: it compared a LINE count against a LINE count and
concluded "the detector fires and agrees".

So this probe is built the other way round.  It refuses to report a single number until it
has proven, end to end and through the same code path, that a genuinely-CRLF blob read by
`git show` comes back WITH its CRLF.  Without that proof a reading of 0 is meaningless --
it could equally mean "git show normalises", and that ambiguity is exactly what produced
the false sentence.

  PART A  detector controls, both states, including a REAL throwaway-repo blob
  PART B  every shipped CRLF claim, measured at the revision that shipped it
  PART C  a mechanically independent second instrument (`git ls-files --eol`)

Run::  python _r4_eol_probe.py   ->  exit 0 only if the controls behave.  A control that
misbehaves is a broken instrument, so the run goes red instead of printing numbers.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]

# (rev, path, the number the shipped doc printed beside it)
ROUND3_CLAIMS = [
    ("0d3c9e93", "docs/mcp-audit/ROUND3-DEFECT-CLOSURE.md", 278),
    ("673cd180", "command-center/mcp-audit/disposition.json", 840),
]
# Round 2's table, measured at 2caafe53 -- the commit that SHIPPED that table.
ROUND2_CLAIMS = [
    ("2caafe53", "docs/mcp-audit/ROUND2-DEFECT-CLOSURE.md", 248),
    ("2caafe53", "command-center/mcp-audit/ruff-census.json", 28),
    ("2caafe53", "docs/mcp-audit/MCP-FLEET-AUDIT.md", 355),
    ("2caafe53", "README.md", 328),
    ("2caafe53", "AGENTS.md", 112),
]


def git_bytes(args: list[str], cwd: pathlib.Path) -> bytes:
    """Run git and return raw stdout.  Never text=True: that would eat the \\r."""
    out = subprocess.run(args, cwd=cwd, capture_output=True, check=True)
    return out.stdout


def counts(buf: bytes) -> tuple[int, int]:
    """(CRLF pairs, LF total).  LF total is the line count for an LF-terminated file."""
    return buf.count(b"\r\n"), buf.count(b"\n")


def blob(rev: str, path: str, cwd: pathlib.Path | None = None) -> bytes:
    return git_bytes(["git", "show", f"{rev}:{path}"], cwd or REPO)


def part_a() -> bool:
    """Both states, twice: a synthetic buffer, then a REAL blob through `git show`."""
    print("== PART A: does this detector fire on CRLF at all? ==")
    ok = True

    crlf_buf = b"a\r\nb\r\nc\r\n"
    lf_buf = b"a\nb\nc\n"
    a1 = counts(crlf_buf) == (3, 3)
    a2 = counts(lf_buf) == (0, 3)
    print(f"  A1 synthetic CRLF buffer  -> {counts(crlf_buf)}  want (3, 3)  ok={a1}")
    print(f"  A2 synthetic LF buffer    -> {counts(lf_buf)}  want (0, 3)  ok={a2}")
    ok = ok and a1 and a2

    # A3/A4 are the control round 3 never ran.  A synthetic buffer proves the COUNTER
    # works; it says nothing about whether `git show` hands CRLF back.  Build a real repo,
    # commit a real CRLF blob, read it back through the identical call.
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="r4eol_"))
    try:
        run = ["git", "-c", "core.autocrlf=false", "-c", "user.email=t@t", "-c"]
        run += ["user.name=t"]
        subprocess.run(["git", "init", "-q", str(tmp)], check=True, capture_output=True)
        (tmp / ".gitattributes").write_bytes(b"* -text\n")
        (tmp / "crlf.md").write_bytes(crlf_buf)
        (tmp / "lf.md").write_bytes(lf_buf)
        subprocess.run(
            [*run, "add", ".gitattributes", "crlf.md", "lf.md"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [*run, "commit", "-q", "-m", "control"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        got_crlf = counts(blob("HEAD", "crlf.md", tmp))
        got_lf = counts(blob("HEAD", "lf.md", tmp))
        a3 = got_crlf == (3, 3)
        a4 = got_lf == (0, 3)
        print(f"  A3 REAL CRLF blob via git show -> {got_crlf}  want (3, 3)  ok={a3}")
        print(f"  A4 REAL LF   blob via git show -> {got_lf}  want (0, 3)  ok={a4}")
        ok = ok and a3 and a4
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(
        "  => git show PRESERVES CRLF when the blob has it, so a reading of 0 on a real\n"
        "     blob means the blob is LF -- not that the instrument is blind."
        if ok
        else "  => CONTROL MISBEHAVED: no reading below may be cited."
    )
    return ok


def part_b() -> list[dict]:
    print("\n== PART B: every shipped CRLF claim, at the revision that shipped it ==")
    print(
        f"  {'rev':9} {'path':44} {'said':>5} {'CRLF':>5} "
        f"{'lines':>6} {'wt CRLF':>8}  hypothesis"
    )
    rows = []
    for rev, path, claimed in ROUND3_CLAIMS + ROUND2_CLAIMS:
        b = blob(rev, path)
        crlf, lf = counts(b)
        wt = REPO / path
        wt_crlf = counts(wt.read_bytes())[0] if wt.exists() else None
        h1 = claimed == crlf
        h2 = claimed == lf
        verdict = "H1 CRLF-count" if h1 else ("H2 LINE-count" if h2 else "neither")
        rows.append(
            {
                "rev": rev,
                "path": path,
                "claimed": claimed,
                "blob_crlf": crlf,
                "blob_lines": lf,
                "worktree_crlf": wt_crlf,
                "hypothesis": verdict,
            }
        )
        short = path if len(path) <= 44 else "..." + path[-41:]
        print(
            f"  {rev:9} {short:44} {claimed:5} {crlf:5} "
            f"{lf:6} {str(wt_crlf):>8}  {verdict}"
        )
    n_h1 = sum(1 for r in rows if r["hypothesis"] == "H1 CRLF-count")
    n_h2 = sum(1 for r in rows if r["hypothesis"] == "H2 LINE-count")
    print(f"  H1 'the numbers are CRLF counts' matches {n_h1}/{len(rows)}")
    print(f"  H2 'the numbers are LINE counts'  matches {n_h2}/{len(rows)}")
    return rows


LANE_DIRS = ("docs/mcp-audit/", "command-center/mcp-audit/")


def part_c() -> tuple[int, int, int]:
    """Second instrument: git's own attribute view, not my byte counting.

    The repo-wide number is a MOVING TARGET -- sibling lanes commit while this runs.  Two
    runs of this probe 4 minutes apart read i/crlf 0 then 1, which is a self-contradiction
    until settled, so it was settled: HEAD moved 0475e4a4 -> 379351df and a sibling
    committed a deliberately-CRLF control fixture.  Not a parser bug, a real index change.
    The load-bearing number is therefore the LANE-SCOPED one, which does not move.
    """
    print("\n== PART C: independent instrument -- git ls-files --eol over the index ==")
    out = git_bytes(["git", "ls-files", "--eol"], REPO).decode("utf-8", "replace")
    n_crlf = n_mixed = n_total = 0
    lane_crlf = lane_total = 0
    crlf_paths: list[str] = []
    for line in out.splitlines():
        if not line.startswith("i/"):
            continue
        n_total += 1
        parts = line.split("\t", 1)
        tag = parts[0].split()[0]
        path = parts[1].strip() if len(parts) > 1 else ""
        in_lane = path.startswith(LANE_DIRS)
        lane_total += in_lane
        if tag == "i/crlf":
            n_crlf += 1
            lane_crlf += in_lane
            crlf_paths.append(path)
        elif tag == "i/mixed":
            n_mixed += 1
    print(f"  indexed paths: {n_total}   i/crlf: {n_crlf}   i/mixed: {n_mixed}")
    print(f"  THIS LANE's indexed paths: {lane_total}   of them i/crlf: {lane_crlf}")
    for p in crlf_paths:
        print(f"    i/crlf -> {p}")
    # A real, third-party-authored CRLF blob in THIS repo is a stronger positive control
    # than my throwaway one.  Optional: a sibling owns it and may retire it.
    for p in crlf_paths:
        got = counts(blob("HEAD", p))
        print(f"  A5 in-repo REAL CRLF blob {p} -> {got}  crlf>0 ok={got[0] > 0}")
        break
    else:
        print(
            "  A5 skipped: no i/crlf blob in the index right now (A3 still carries it)"
        )
    # Control: the detector must be able to SEE a crlf attribute somewhere, or a zero is
    # just a broken parser.  *.ps1 is pinned eol=crlf in .gitattributes, so its WORKTREE
    # column must read w/crlf even though its blob is LF.
    ps1 = [ln for ln in out.splitlines() if ln.rstrip().endswith(".ps1")]
    w_crlf = sum(1 for ln in ps1 if " w/crlf" in ln)
    print(
        f"  control: {w_crlf}/{len(ps1)} *.ps1 read w/crlf in the WORKTREE column "
        f"-> the parser can see crlf when it is there"
    )
    return n_crlf, n_mixed, w_crlf


def main() -> int:
    if not part_a():
        print("FAILED:r4-eol control misbehaved, no verdict")
        return 1
    rows = part_b()
    n_crlf, n_mixed, w_crlf = part_c()
    if w_crlf == 0:
        print("FAILED:r4-eol part-C control never saw a crlf attribute")
        return 1
    bad = [r for r in rows if r["hypothesis"] == "H1 CRLF-count"]
    print(
        f"\n  RESULT: {len(bad)}/{len(rows)} shipped numbers are CRLF counts; "
        f"{n_crlf} blobs in the whole index are i/crlf ({n_mixed} mixed)."
    )
    print("SUCCESS:r4-eol controls fired, claims measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
