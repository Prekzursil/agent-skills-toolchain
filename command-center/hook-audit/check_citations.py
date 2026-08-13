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

ROUND 3 -- three holes in this gate itself, each measured, each closed here:

  H1 IT READ THE WORKING TREE, NEVER THE SHIPPED BLOB. `fp.read_text()` resolves the file
     on the author's disk. A clone sees the stored blob (`git show :<path>`; `blob_json`
     explains index-not-HEAD). Those diverge exactly when
     the evidence is regenerated after staging -- which is how C3 shipped -- so the gate
     was blind to the one drift direction that actually occurred. Measured 2026-08-13: the
     gate returned SUCCESS (32/32) while `C6-GATE-EVIDENCE-SIDE.json`, a CITED evidence
     file, differed from its own committed blob in four fields. Every citation is now
     resolved TWICE, worktree and staged blob, and a divergence is `EVIDENCE-DRIFT`.
  H2 THE REPO ROOT WAS A HARDCODED ABSOLUTE PATH. `REPO = Path("C:/Users/.../ast-integrate")`
     means a run from any other checkout silently validated ast-integrate's documents
     against ast-integrate's evidence and reported on files the caller does not have --
     the same "read the wrong tree and still say SUCCESS" shape as the round-2 blob gate.
     The root is now derived from this file via `git rev-parse --show-toplevel`, overridable
     with HOOK_AUDIT_REPO, and fails closed if the two expected directories are absent.
  H3 THE ZERO-CITATION FLOOR WAS GLOBAL, NOT PER-DOCUMENT. One annotated document satisfied
     it for the whole directory, so `HOOK-AUDIT.md` (the round-1 deliverable, and the one
     whose tables the verifier faulted) carried 0 citations and passed. The floor is now
     per-document, with an explicit exemption list that must name a reason.

ROUND 4 -- a FOURTH hole, and it is the one that mattered most, because the gate was GREEN
while the flagship deliverable published unbacked numbers:

  H4 THE GATE ONLY CHECKED NUMBERS THAT VOLUNTEERED FOR CHECKING. Every rule above operates
     on a `cite:` marker. A number with NO marker was not "unbacked" to this gate, it was
     invisible -- so the cheapest way to pass was to annotate one paragraph and leave the
     tables bare. Measured 2026-08-13 by an independent verifier: `HOOK-AUDIT.md`'s DoD-1
     deliverable table published 7 numbers that appear in NO committed evidence file and
     diverge 1.7x-10.9x from `H4-TIMING-live.json`, the only committed evidence for that
     measurement -- and `check_citations.py` printed SUCCESS, because the table carried zero
     markers and the per-document floor was satisfied 30 lines higher up.
     The rule added here: a markdown TABLE that publishes a MEASUREMENT (a number carrying
     ms / s / % / x / B) must carry a `cite:` marker INSIDE the table block, or be preceded
     by `<!-- uncited-table: reason=... -->` naming why not. Scoped to tables on purpose --
     measured against this corpus the rule flags 3 of 6 measurement tables, so it is a floor
     the corpus can actually meet, not a flood that trains the reader to ignore it (which is
     itself a finding of this very audit).

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
  * fail-closed on ZERO citations found, per document. A gate that silently passes an
    unannotated document measures nothing -- that is the exact failure it exists to prevent.
  * `--self-test` mutates each citation's expected value and asserts the checker goes RED
    for every one. A citation the checker cannot fail is not being checked.
  * the tracked-in-git check is separate from the on-disk check, because an UNCOMMITTED
    evidence file reads as present on the author's box and is absent to everyone else --
    which is precisely how `H4-TIMING-live.json` shipped as a citation to nothing.
  * `test_citation_gate.py` builds a throwaway git repo where the blob and the worktree
    disagree on a cited path, and requires the PRE-ROUND-3 gate to pass it and this one to
    fail it. Without that pairing "no drift found" would be indistinguishable from "drift
    is not looked for".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

# Documents that legitimately carry no citation. Each needs a REASON: an exemption without
# one is how a per-document floor decays back into the global floor it replaced.
NO_CITE_EXEMPT: dict[str, str] = {}

CITE = re.compile(r"<!--\s*cite:\s*(?P<body>[^>]*?)\s*-->")
FENCE = re.compile(r"^\s*(```|~~~)")

# H4. A measurement is a number carrying a unit. `\d[\d,]*` so a thousands separator does not
# split the token; the unit set is deliberately small -- this gate guards timing/size claims,
# not every integer in a sentence.
MEASURE = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:ms\b|s\b|%|x\b|B\b|bytes\b)")
# A waiver must carry a REASON. An exemption without one is how a floor decays back into the
# global floor it replaced -- the same reasoning as NO_CITE_EXEMPT above.
# `[^>]` means a reason containing `>` (e.g. an arrow `->`) does not parse as a waiver and the
# table is reported unwaived. That is FAIL-CLOSED and deliberate -- such a comment is also
# invalid HTML -- but it is surprising enough to write down: it bit the author of the first
# waiver in this corpus, and the failure mode is a flag you did not expect, never a silent pass.
TABLE_WAIVER = re.compile(r"<!--\s*uncited-table:\s*(?P<body>[^>]*?)\s*-->")
WAIVER_LOOKBACK = 3


def measurement_tables(text: str) -> tuple[list[dict], int]:
    """-> (violations, measurement_table_count) for one document.

    A violation is a pipe-table whose cells publish a measurement and which carries neither
    an inline `cite:` marker nor a reasoned `uncited-table:` waiver in the WAIVER_LOOKBACK
    lines above it. Runs over the fence-stripped text so an EXAMPLE table inside a code fence
    is not audited as a claim, and so line numbers stay honest.
    """
    lines = _strip_fenced(text).splitlines()
    viol: list[dict] = []
    n_measure = 0
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            j += 1
        block = "\n".join(lines[i:j])
        if MEASURE.search(block):
            n_measure += 1
            if not CITE.search(block):
                waiver = None
                for k in range(max(0, i - WAIVER_LOOKBACK), i):
                    m = TABLE_WAIVER.search(lines[k])
                    if m:
                        waiver = m.group("body")
                        break
                reason = ""
                if waiver is not None:
                    for tok in waiver.split("reason=", 1)[1:]:
                        reason = tok.strip()
                if waiver is None:
                    viol.append(
                        {
                            "line": i + 1,
                            "head": lines[i].strip()[:80],
                            "why": "no cite marker inside the table and no waiver",
                        }
                    )
                elif not reason:
                    viol.append(
                        {
                            "line": i + 1,
                            "head": lines[i].strip()[:80],
                            "why": "uncited-table waiver carries no reason=",
                        }
                    )
        i = j
    return viol, n_measure


# Both-states control for the classifier above, run on EVERY invocation. A regex that quietly
# stops matching would otherwise turn this rule into a permanently green no-op -- the exact
# shape of defect it was added to catch.
_SELFCHECK_HOT = "| check | wall |\n|---|---|\n| wire-check | 6,541.6 ms |\n"
_SELFCHECK_COLD = "| half | state |\n|---|---|\n| PreCompact | NOT-WIRED |\n"


def classifier_selfcheck() -> tuple[bool, bool]:
    """-> (fires_on_a_measurement_table, stays_silent_on_a_prose_table)."""
    hot, n_hot = measurement_tables(_SELFCHECK_HOT)
    _cold, n_cold = measurement_tables(_SELFCHECK_COLD)
    return (len(hot) == 1 and n_hot == 1), (n_cold == 0)


def repo_root() -> Path:
    """Resolve the repo THIS FILE lives in -- never a hardcoded absolute path (H2).

    Order: HOOK_AUDIT_REPO env (tests point it at a fixture) -> `git rev-parse
    --show-toplevel` from this file's directory -> two parents up. Fails closed if the
    result does not hold both expected directories, so a wrong root can never present as
    a clean run.
    """
    env = os.environ.get("HOOK_AUDIT_REPO")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve().parent
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(here),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if p.returncode == 0 and p.stdout.strip():
            return Path(p.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return here.parents[1]


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


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, timeout=60
    )


def tracked(repo: Path, rel: Path) -> bool:
    return (
        _git(
            repo, "ls-files", "--error-unmatch", str(rel).replace("\\", "/")
        ).returncode
        == 0
    )


def blob_json(repo: Path, rel: Path) -> tuple[object | None, str]:
    """Parse the file as the INDEX holds it -- the bytes this commit will ship (H1).

    The index, not `HEAD`: the defect being caught is an evidence file regenerated after it
    was staged, and comparing against `HEAD` would make the gate unrunnable before the
    commit that adds new evidence (a newly staged file has no HEAD copy). For a tracked file
    with no staged change the index copy IS the HEAD copy, so the post-commit drift case is
    covered too. `git show :<path>` emits the stored blob; `git archive` would re-apply EOL
    conversion on Windows and hand back CRLF, so it is not used here.
    """
    p = _git(repo, "show", f":{str(rel).replace(chr(92), '/')}")
    if p.returncode != 0:
        return None, (p.stderr or b"").decode("utf-8", "replace").strip()[:160]
    try:
        return json.loads(p.stdout.decode("utf-8", "replace")), ""
    except ValueError as e:
        return None, f"blob is not valid JSON: {e}"


def check_one(repo: Path, c: dict, *, mutate: bool = False) -> tuple[bool, str]:
    cid = c.get("id", "?")
    where = f"{c['_src']}:{c['_line']} id={cid}"
    fname = c.get("file")
    if not fname:
        return False, f"{where} -- citation has no file="
    evid = repo / "command-center" / "hook-audit"
    fp = evid / fname
    rel = fp.relative_to(repo)
    if not fp.is_file():
        return False, f"{where} -- evidence file MISSING on disk: {rel}"
    if not tracked(repo, rel):
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

    # H1: the same citation, resolved against the bytes this commit ships. A worktree-only
    # match is what let a regenerated-after-staging evidence file pass unnoticed.
    if not mutate:
        shipped, err = blob_json(repo, rel)
        if shipped is None:
            return (
                False,
                f"{where} -- cited evidence is not readable from the index ({rel}): {err}",
            )
        try:
            got_blob = walk(shipped, path)
        except (KeyError, IndexError, TypeError) as e:
            return (
                False,
                f"{where} -- EVIDENCE-DRIFT: {path!r} resolves in the worktree copy of "
                f"{fname} but NOT in the staged blob this commit will ship: {e}",
            )
        if str(got_blob) != str(got):
            return (
                False,
                f"{where} -- EVIDENCE-DRIFT: {path} is {got!r} on disk but {got_blob!r} "
                f"in the staged blob -- a clone reads the second one",
            )

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

    repo = repo_root()
    docs = repo / "docs" / "hook-audit"
    evid = repo / "command-center" / "hook-audit"
    if not docs.is_dir() or not evid.is_dir():
        print(
            f"FAILED:cite-check repo root {repo} does not hold docs/hook-audit and "
            "command-center/hook-audit -- refusing to guess, and refusing to validate "
            "some other checkout's files (set HOOK_AUDIT_REPO to override)"
        )
        return 1

    # H4 control, before any verdict: prove the table classifier can still tell the two
    # states apart. A silent classifier would report "0 uncited tables" forever.
    fires, silent = classifier_selfcheck()
    if not (fires and silent):
        print(
            "FAILED:cite-check the measurement-table classifier failed its own both-states "
            f"control (fires_on_measurement={fires}, silent_on_prose={silent}) -- it cannot "
            "be trusted to report zero, so no verdict is issued"
        )
        return 1

    md_files = sorted(docs.glob("*.md"))
    cites: list[dict] = []
    per_doc: dict[str, int] = {}
    table_viol: list[str] = []
    n_measure_tables = 0
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        got = parse_cites(text, md.name)
        per_doc[md.name] = len(got)
        cites.extend(got)
        viol, n_meas = measurement_tables(text)
        n_measure_tables += n_meas
        for v in viol:
            table_viol.append(f"{md.name}:{v['line']} -- {v['why']}: {v['head']}")

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
            ok, msg = check_one(repo, c, mutate=True)
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
        ok, msg = check_one(repo, c)
        print(("   " if ok else "!! ") + msg)
        if not ok:
            bad.append(msg)

    # H3: per-DOCUMENT floor. A single annotated file used to satisfy the whole directory.
    unannotated = []
    for name, n in sorted(per_doc.items()):
        if n == 0 and name not in NO_CITE_EXEMPT:
            unannotated.append(name)
            print(
                f"!! {name} -- ZERO citations: this document publishes numbers no gate "
                "checks. Annotate them, or add it to NO_CITE_EXEMPT with a reason."
            )
    # H4: a measurement table with no marker was invisible to every rule above.
    for v in table_viol:
        print(
            f"!! UNCITED-MEASUREMENT-TABLE {v}\n"
            "     A table that publishes ms/s/%/x/B must carry a cite: marker inside the "
            "table, or an <!-- uncited-table: reason=... --> waiver above it."
        )

    print(
        f"\n== docs scanned: {len(md_files)}  "
        + ", ".join(f"{k}={v}" for k, v in sorted(per_doc.items()))
    )
    print(
        f"== {len(cites)} citations checked, {len(bad)} unbacked, {len(unannotated)} unannotated doc(s)"
    )
    print(
        f"== {n_measure_tables} measurement table(s) scanned, {len(table_viol)} uncited "
        "(classifier both-states control: PASS)"
    )
    if bad or unannotated or table_viol:
        print(
            f"FAILED:cite-check {len(bad)} published number(s) not backed by evidence, "
            f"{len(unannotated)} document(s) with no citation at all, "
            f"{len(table_viol)} uncited measurement table(s)"
        )
        return 1
    print("SUCCESS:cite-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
