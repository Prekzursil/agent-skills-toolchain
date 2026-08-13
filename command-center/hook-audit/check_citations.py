r"""check_citations.py -- resolve every published number in docs/hook-audit/*.md against
the committed evidence file it cites, and fail if the file does not actually contain it.

WHY THIS EXISTS. An independent verifier found that round 1 published two timing tables
and a three-arm A/B table whose cited evidence files did not contain the cited numbers:

  * `H4-TIMING-live.json` was never committed at all, so the per-check table cited a file
    that does not exist in git.
  * `B6-FLEET.json` was cited for a timing table, but a later `--inertness`-only run of the
    producing probe had overwritten it with `{"inertness": ...}` -- the timing key was gone.
  * `B3-AB-BUDGET.json` holds 2 arms; the document printed 3.

None of that is a lie about the code -- it is a document drifting away from its evidence
with nothing watching. This gate watches. It does NOT read prose and it does NOT trust a
claim: for each citation it OPENS the named file, walks the named JSON path, and compares
the resolved value to the number printed in the document.

CITATION SYNTAX -- an HTML comment next to the claim, so it renders invisibly:

    <!-- cite: id=C4-worst file=B6-FLEET.json path=timing.worst_pct value=17.8 tol=0.05 -->

  id     free-form, unique, used in the failure message
  file   relative to command-center/hook-audit/
  path   dotted path; a bare integer segment indexes a list
  value  the number (or string) the document prints
  tol    OPTIONAL relative tolerance for floats (default 0 = exact)
  exists OPTIONAL `exists=true` asserts the path resolves, without pinning a value
         (for a number that legitimately moves between runs)

DETECTOR CONTROLS (this gate is itself a detector, so it needs both states proven):
  * fail-closed on ZERO citations found. A gate that silently passes an unannotated
    document measures nothing -- that is the exact failure it exists to prevent.
  * `--self-test` mutates each citation's expected value and asserts the checker goes RED
    for every one. A citation the checker cannot fail is not being checked.
  * the tracked-in-git check is separate from the on-disk check, because an UNCOMMITTED
    evidence file reads as present on the author's box and is absent to everyone else --
    which is precisely how `H4-TIMING-live.json` shipped as a citation to nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
DOCS = REPO / "docs" / "hook-audit"
EVID = REPO / "command-center" / "hook-audit"

CITE = re.compile(r"<!--\s*cite:\s*(?P<body>[^>]*?)\s*-->")


FENCE = re.compile(r"^\s*(```|~~~)")


def _strip_fenced(text: str) -> str:
    """Blank out fenced code blocks, preserving line numbers.

    Without this a document cannot show its own citation syntax in an example without the
    parser trying to resolve the example -- which it did, reporting `id=? citation has no
    file=` for a line of prose. Blanking rather than deleting keeps `_line` honest.
    """
    out, inside = [], False
    for line in text.splitlines():
        if FENCE.match(line):
            inside = not inside
            out.append("")
            continue
        out.append("" if inside else line)
    return "\n".join(out)


def parse_cites(text: str, src: str) -> list[dict]:
    out = []
    for m in CITE.finditer(_strip_fenced(text)):
        kv: dict[str, str] = {}
        for tok in m.group("body").split():
            if "=" not in tok:
                continue
            k, v = tok.split("=", 1)
            kv[k.strip()] = v.strip()
        kv["_src"] = src
        kv["_line"] = text[: m.start()].count("\n") + 1
        out.append(kv)
    return out


def walk(obj, path: str):
    """Resolve a dotted path. A bare integer segment indexes a list."""
    cur = obj
    for seg in path.split("."):
        if isinstance(cur, list):
            if not re.fullmatch(r"-?\d+", seg):
                raise KeyError(f"list needs an integer index, got {seg!r}")
            cur = cur[int(seg)]
        elif isinstance(cur, dict):
            if seg not in cur:
                raise KeyError(seg)
            cur = cur[seg]
        else:
            raise KeyError(f"cannot descend into {type(cur).__name__} at {seg!r}")
    return cur


def tracked(rel: Path) -> bool:
    p = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(rel).replace("\\", "/")],
        cwd=str(REPO),
        capture_output=True,
    )
    return p.returncode == 0


def check_one(c: dict, *, mutate: bool = False) -> tuple[bool, str]:
    cid = c.get("id", "?")
    where = f"{c['_src']}:{c['_line']} id={cid}"
    fname = c.get("file")
    if not fname:
        return False, f"{where} -- citation has no file="
    fp = EVID / fname
    rel = fp.relative_to(REPO)
    if not fp.is_file():
        return False, f"{where} -- evidence file MISSING on disk: {rel}"
    if not tracked(rel):
        return (
            False,
            f"{where} -- evidence file is UNTRACKED (invisible in a clone): {rel}",
        )
    try:
        blob = json.loads(fp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return False, f"{where} -- evidence file unreadable: {e}"
    path = c.get("path")
    if not path:
        return False, f"{where} -- citation has no path="
    try:
        got = walk(blob, path)
    except (KeyError, IndexError, TypeError) as e:
        return False, f"{where} -- path {path!r} does not resolve in {fname}: {e}"

    if c.get("exists", "").lower() == "true" and "value" not in c:
        return True, f"{where} -- path resolves ({path} -> {got!r})"

    want_raw = c.get("value")
    if want_raw is None:
        return False, f"{where} -- citation has neither value= nor exists=true"
    try:
        want = float(want_raw)
        if mutate:
            want = want + max(1.0, abs(want)) * 10.0 + 7.0
        gotf = float(got)
        tol = float(c.get("tol", "0") or 0)
        ok = abs(gotf - want) <= max(abs(want), 1e-9) * tol if tol else gotf == want
        return ok, (
            f"{where} -- {path}: doc says {want_raw}, evidence has {got}"
            if not ok
            else f"{where} -- OK {path}={got}"
        )
    except (TypeError, ValueError):
        want_s = str(want_raw) + ("__MUTATED" if mutate else "")
        ok = str(got) == want_s
        return ok, (
            f"{where} -- {path}: doc says {want_s!r}, evidence has {str(got)!r}"
            if not ok
            else f"{where} -- OK {path}={got!r}"
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="prove the gate can FAIL: mutate every expected value and require a red",
    )
    a = ap.parse_args()

    cites: list[dict] = []
    for md in sorted(DOCS.glob("*.md")):
        cites.extend(parse_cites(md.read_text(encoding="utf-8"), md.name))

    if not cites:
        print(
            "FAILED:cite-check ZERO citations found -- an unannotated document is not"
        )
        print("       evidence-checked, and a silent pass here is the defect this gate")
        print("       exists to prevent. Annotate the numbers or delete this gate.")
        return 1

    if a.self_test:
        survived = []
        for c in cites:
            if c.get("exists", "").lower() == "true" and "value" not in c:
                continue
            ok, msg = check_one(c, mutate=True)
            if ok:
                survived.append(msg)
        print(f"== SELF-TEST mutated {len(cites)} citations")
        if survived:
            for s in survived:
                print(f"   SURVIVED (gate cannot fail this one): {s}")
            print(
                f"FAILED:cite-check-selftest {len(survived)} citation(s) unfalsifiable"
            )
            return 1
        print("   every citation went RED when mutated -- the gate can fail")
        print("SUCCESS:cite-check-selftest")
        return 0

    bad = []
    for c in cites:
        ok, msg = check_one(c)
        print(("   " if ok else "!! ") + msg)
        if not ok:
            bad.append(msg)
    print(f"\n== {len(cites)} citations checked, {len(bad)} unbacked")
    if bad:
        print(
            f"FAILED:cite-check {len(bad)} published number(s) not backed by evidence"
        )
        return 1
    print("SUCCESS:cite-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
