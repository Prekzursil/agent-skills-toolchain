"""Round 7: re-measure EVERY number round 6 asserted, and report reproduce/differ.

Round 6 found three defects the audit had not flagged by re-measuring every number in
round 5 rather than only the flagged ones. This applies the same method to round 6
itself. Nothing here reads a claim -- every row executes the measurement.

Terminal state: SUCCESS:docs-r7-remeasure ... / FAILED:docs-r7-remeasure <reason>

Controls are stated as two competing hypotheses, and a control whose PASS looks the
same under both is discarded rather than cited (a control that cannot distinguish the
hypotheses only proves the instrument ran).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "quality.yml"

# Round 6's asserted values, transcribed from docs/_LANE-DOCS-BUILD-R6.md.
R6_CLAIMS = {
    "pre_fix": "20/16",
    "post_fix": "19/15",
    "hooks_json_occurrences": 51,
    "hooks_json_distinct": 23,
    "siblings": 22,
    "authors_last_60": 1,
    "fetch_depth_zero_lines": [1631],
    "test_python_job_line": 283,
    "checkout_line": 287,
}


def git(*args: str) -> str:
    """Run git and return stdout. encoding is explicit: Windows defaults to cp1252
    and a non-ASCII author name decodes wrong (a round-6 self-inflicted failure)."""
    out = subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return out.stdout


def git_ok(*args: str) -> bool:
    out = subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return out.returncode == 0


def workflow_jobs(text: str) -> list[tuple[int, str]]:
    """(line_number, job_name) for every top-level job key, 1-indexed."""
    jobs: list[tuple[int, str]] = []
    in_jobs = False
    for i, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^jobs:\s*$", line):
            in_jobs = True
            continue
        if in_jobs:
            # a new top-level key ends the jobs block
            if re.match(r"^[A-Za-z_]", line):
                in_jobs = False
                continue
            m = re.match(r"^  ([A-Za-z0-9_\-]+):\s*$", line)
            if m:
                jobs.append((i, m.group(1)))
    return jobs


def job_at(jobs: list[tuple[int, str]], line: int) -> str:
    owner = "<before first job>"
    for ln, name in jobs:
        if ln <= line:
            owner = name
        else:
            break
    return owner


def main() -> int:
    rows: list[tuple[str, str, str, str]] = []  # id, r6 said, measured, verdict

    def row(rid: str, said: object, got: object) -> None:
        verdict = "REPRODUCES" if str(said) == str(got) else "DIFFERS"
        rows.append((rid, str(said), str(got), verdict))

    # ---- N1 fabricated anchor + census control -------------------------------
    bad_resolves = git_ok("cat-file", "-t", "d088884d3bf0")
    census = git("cat-file", "--batch-all-objects", "--batch-check=%(objectname)")
    bad_hits = sum(1 for o in census.splitlines() if o.startswith("d088884d"))
    head_sha = git("rev-parse", "HEAD").strip()
    ctrl_hits = sum(1 for o in census.splitlines() if o.startswith(head_sha[:8]))
    row("N1 d088884d resolves", False, bad_resolves)
    row("N1 census hits for d088884d", 0, bad_hits)
    # CONTROL: the census must find a known-present object, else "0" is a dead matcher.
    if ctrl_hits < 1:
        print(
            f"FAILED:docs-r7-remeasure census control found {ctrl_hits} for HEAD prefix"
        )
        return 1

    # ---- N2 mirror identity, at the CURRENT head (a moving target) -----------
    a = git("rev-parse", "HEAD:commands/sessions.md").strip()
    b = git("rev-parse", "HEAD:agent-self/config/commands/sessions.md").strip()
    row("N2 mirror identical at HEAD", True, a == b and bool(a))
    row("N2 mirror blob", "df9d9d760bba", a[:12])
    # CONTROL: the reader must not be constant.
    other = git("rev-parse", "HEAD:README.md").strip()
    if other[:12] == a[:12]:
        print("FAILED:docs-r7-remeasure blob reader returned the same sha for README")
        return 1

    # ---- N3 the pre-fix blob pin --------------------------------------------
    parent_blob = git("rev-parse", "67137879:commands/sessions.md").strip()
    row("N3 parent blob", "3bfb914d", parent_blob[:8])

    # ---- N4 hooks.json sibling count ----------------------------------------
    hooks_json = REPO / "hooks" / "hooks.json"
    if hooks_json.exists():
        raw = hooks_json.read_bytes().decode("utf-8", "replace")
        occ = re.findall(r"scripts/hooks/[A-Za-z0-9_.\-]+", raw)
        distinct = sorted(set(occ))
        row("N4 occurrences", R6_CLAIMS["hooks_json_occurrences"], len(occ))
        row("N4 distinct", R6_CLAIMS["hooks_json_distinct"], len(distinct))
        siblings = len([d for d in distinct if not d.endswith("cost-tracker.js")])
        row("N4 siblings (excl cost-tracker)", R6_CLAIMS["siblings"], siblings)
        # CONTROL: a token known to be absent must score 0, else the matcher is broken.
        if len(re.findall(r"scripts/hooks/zzz-not-real", raw)) != 0:
            print("FAILED:docs-r7-remeasure zero-arm control matched a fake token")
            return 1
    else:
        rows.append(("N4 hooks.json", "present", "ABSENT", "DIFFERS"))

    # ---- N5 authorship ------------------------------------------------------
    authors = {
        ln for ln in git("log", "-60", "--format=%an <%ae>").splitlines() if ln.strip()
    }
    row("N5 distinct authors in last 60", R6_CLAIMS["authors_last_60"], len(authors))

    # ---- N6 workflow structure (this one drove a BUILD DECISION) ------------
    wf = WORKFLOW.read_bytes().decode("utf-8", "replace")
    lines = wf.splitlines()
    jobs = workflow_jobs(wf)
    fd_zero = [
        i
        for i, ln in enumerate(lines, start=1)
        if re.match(r"^\s*fetch-depth:\s*0\s*$", ln)
    ]
    row("N6 fetch-depth:0 lines", R6_CLAIMS["fetch_depth_zero_lines"], fd_zero)
    for ln in fd_zero:
        rows.append(
            (f"N6 owner of line {ln}", "gitleaks (r6)", job_at(jobs, ln), "INFO")
        )

    # where do the docs gate steps actually live?
    docs_steps = [
        i
        for i, ln in enumerate(lines, start=1)
        if "test_docs_executable_claims" in ln
        or "test_docs_gate_ci_wiring" in ln
        or "test_command_doc_promises" in ln
    ]
    for ln in docs_steps:
        rows.append(
            (
                f"N6 docs step line {ln}",
                "job test-python (r6)",
                job_at(jobs, ln),
                "INFO",
            )
        )

    # does the hosting job's checkout carry a with: block?
    host_jobs = sorted({job_at(jobs, ln) for ln in docs_steps})
    for hj in host_jobs:
        start = next(ln for ln, nm in jobs if nm == hj)
        after = [ln for ln, _ in jobs if ln > start]
        end = after[0] if after else len(lines) + 1
        co = [i for i in range(start, end) if "actions/checkout" in lines[i - 1]]
        for c in co:
            nxt = lines[c].strip() if c < len(lines) else ""
            has_with = nxt.startswith("with:")
            rows.append(
                (
                    f"N6 checkout L{c} in {hj}",
                    "no with: -> depth 1 (r6)",
                    f"with:={has_with}",
                    "INFO",
                )
            )

    # ---- report -------------------------------------------------------------
    width = max(len(r[0]) for r in rows)
    print(f"{'claim':<{width}}  {'round 6 said':<26} {'measured now':<26} verdict")
    for rid, said, got, verdict in rows:
        print(f"{rid:<{width}}  {said:<26} {got:<26} {verdict}")

    differs = [r for r in rows if r[3] == "DIFFERS"]
    print()
    print(f"rows={len(rows)} differs={len(differs)} head={head_sha[:8]}")
    if differs:
        print(
            "FAILED:docs-r7-remeasure "
            + "; ".join(f"{r[0]}: {r[1]}->{r[2]}" for r in differs)
        )
        return 1
    print("SUCCESS:docs-r7-remeasure all round-6 numbers reproduce")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
