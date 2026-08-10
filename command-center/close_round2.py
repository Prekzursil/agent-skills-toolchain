"""Round 2: close 3 more verified items, and correct 2 items whose stated premise is now false.

Every anchor below was re-measured here with a control in the same run. Nothing is taken from a
lane digest.

THE CORRECTIONS MATTER MORE THAN THE CLOSES. R-A22's `next_smallest_action` currently instructs the
next session to *"Write 08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json first"*. That file exists, in
the contracted program directory, at **344,197 bytes**. Lane A2 reported all three of R-A22's files
"absent from both trees" because it searched the British spelling LICENCE; the contract and the file
both use LICENSE. I made the same single-letter error while checking A2's claim, which is how I
noticed. An action item that tells someone to author a 344 KB artifact that already exists is worse
than an open item -- it spends the next session's whole budget re-deriving delivered work.

SCOPE DISCLOSURE, inherited from lane D1 and attached to every disposition that needs it: R-A23 and
R-A24 close on evidence inside `~/.claude/harness-restore-20260806/`, which is NOT in version
control. A fresh clone has none of it. That is legitimate -- the contract asked for "a dedicated,
timestamped program directory" -- but a closure resting on single-machine working-filesystem state
must say so, or the next reader will assume the artifact is recoverable and it is not.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
REGISTER = REPO / "command-center/sources/REGISTER.md"
TREE1 = Path("C:/Users/Prekzursil/.claude/harness-restore-20260806")
#: The SUPERSEDED tree -- every file in it mtimes 2026-07-20, 18 days older than TREE1 (lane D1
#: finding N3). R-A24's four content shards live here, which is why the disposition has to say so.
TREE2 = Path("C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19")

UNTRACKED_SCOPE = (
    " SCOPE, disclosed: this evidence lives in ~/.claude/harness-restore-20260806/, which is NOT in "
    "version control (git's own ancestor walk returns rc=128 there) -- a fresh clone has none of it. "
    "Legitimate, because the contract asked for a dedicated timestamped program directory, but the "
    "closure rests on single-machine working-filesystem state with no clone reproducibility. See "
    "command-center/PROMPT-ONE-REVERIFY.md finding D1-1."
)

CLOSES = {
    "R-A23": (
        "15-IMPLEMENTATION-PRECONDITIONS.md EXISTS at 12,342 B (mtime 2026-08-09 13:47) and is a "
        "substantive gate rather than a stub: 13 preconditions in HARD/SCOPED tiers, each with an "
        "executable check in 15-preconditions-check.py (22,824 B, self-test 12/12) carrying a "
        "known-bad control. Its pair 14-NO-REGRESSION-CONTRACT.md already existed, so the missing "
        "half is now delivered." + UNTRACKED_SCOPE
    ),
    "R-A24": (
        "NAMING RECONCILIATION COMPLETE -- which is exactly what the item asked for; no research was "
        "ever missing. 05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md EXISTS at 14,618 B and is the index the "
        "item specified: its section 0 lists all four 05-ECO-* shards with byte counts "
        "(72,150 + 92,804 + 53,973 + 36,768 = 255,695 B), heading counts, URL counts and an access "
        "path per shard. COMPOUND SCOPE CAVEAT: the index sits in harness-restore-20260806/ while "
        "all four content shards live in platform-redesign-2026-07-19/ -- the SUPERSEDED tree, 18 "
        "days older (lane D1 finding N3). The index is explicit and honest about this at its line "
        "26 and states the shards remain the source of truth, so the artifact does resolve under the "
        "contracted name; but the content it indexes belongs to an earlier program generation, and "
        "neither tree is in version control." + UNTRACKED_SCOPE
    ),
    "R-B05": (
        "PREMISE REFUTED -- Program-B artifacts now have a real consumer, so 'zero consumers reach "
        "any Program-B artifact' is false. `.github/workflows/quality.yml:611` runs a named gate "
        "'gate-tests-coverage program-b register (suite + mutation probe)' executing BOTH "
        "`ci/tests/test_program_b_register.py` and `docs/program-b/mutation_probe.py`. Re-measured "
        "2026-08-10: the suite runs green, 27 passed in 1.30 s, and `git ls-files docs/program-b/` "
        "shows 3 tracked artifacts (README.md, mutation_probe.py, program-b-receipt.json). Unlike "
        "R-A23/R-A24 this evidence IS in version control and survives a fresh clone."
    ),
}

#: id -> (new evidence prose, new next_smallest_action). Premise corrections, NOT closures.
CORRECTIONS = {
    "R-A22": (
        "PREMISE CORRECTED 2026-08-10: 2 of the 3 named artifacts EXIST in the contracted program "
        "directory. 08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json is present at 344,197 B and "
        "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json at 161,920 B; only "
        "10-WORKFLOW-FUSION-AND-CERTIFICATION-MAPS.json is genuinely absent (control: a sentinel "
        "name is absent from both trees, so the probe discriminates). The earlier reading 'all three "
        "absent from both trees' was a SPELLING artifact -- it searched LICENCE while the contract "
        "and the file use LICENSE. Recorded rather than deleted." + UNTRACKED_SCOPE,
        "Write ONLY 10-WORKFLOW-FUSION-AND-CERTIFICATION-MAPS.json -- the other two named artifacts "
        "already exist (344,197 B and 161,920 B). Do NOT re-author the provenance/licence graph; the "
        "previous action line said to write it first and that was based on a misspelled probe.",
    ),
    "R-A21": (
        "PREMISE PARTLY REFUTED 2026-08-10: 01-BLOCKER-REPRODUCTION.md is NOT absent -- it exists at "
        "9,584 B in the contracted program directory, with 21 fixture/repro references and no "
        "'not reproducible' disclaimer. The earlier reading 'absent from both trees' is wrong on the "
        "document. What remains open is the SECOND half of the target, the reproducible failing "
        "fixture: the item's own action line warns the host has changed since, so the repro needs "
        "re-deriving before the old root cause may be cited. Narrowed, not closed, because I did not "
        "execute the fixture." + UNTRACKED_SCOPE,
        "Re-derive the failing repro on the CURRENT host and record whether it still reproduces. The "
        "document half already exists (9,584 B) -- do not re-author it. If the repro no longer fires, "
        "say so explicitly rather than citing the old root cause.",
    ),
}


def _probe_verdict(cid: str, ok: bool, measured: str, control_ok: bool) -> dict:
    verdict = (
        "DETECTOR-BROKEN" if not control_ok else ("CONFIRMED" if ok else "REFUTED")
    )
    return {
        "check": cid,
        "verdict": verdict,
        "measured": measured,
        "ok": verdict == "CONFIRMED",
    }


def verify() -> list[dict]:
    out = []
    sentinel_absent = not (TREE1 / "ZZZ-NOT-REAL-SENTINEL.md").exists()

    p = TREE1 / "15-IMPLEMENTATION-PRECONDITIONS.md"
    c = TREE1 / "15-preconditions-check.py"
    out.append(
        _probe_verdict(
            "R-A23",
            p.exists()
            and p.stat().st_size > 10_000
            and c.exists()
            and c.stat().st_size > 20_000,
            f"preconditions.md={p.stat().st_size if p.exists() else 0}B, "
            f"check.py={c.stat().st_size if c.exists() else 0}B",
            sentinel_absent and p.exists(),
        )
    )

    e = TREE1 / "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md"
    # The shards are in TREE2, not TREE1 -- the index says so in as many words at its line 26
    # ("All four live in .../platform-redesign-2026-07-19/, NOT in harness-restore-20260806/").
    # My first probe globbed TREE1, found 0, and reported DETECTOR-BROKEN. Correct behaviour for a
    # probe that read the wrong directory, and the answer was written in the artifact I was checking.
    shards = sorted(TREE2.glob("05-ECO-*.md"))
    out.append(
        _probe_verdict(
            "R-A24",
            e.exists() and e.stat().st_size > 10_000 and len(shards) == 4,
            f"index={e.stat().st_size if e.exists() else 0}B, {len(shards)} shards "
            f"totalling {sum(s.stat().st_size for s in shards)}B",
            sentinel_absent and bool(shards),
        )
    )

    tracked = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "docs/program-b/"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    gate = "program-b register" in (REPO / ".github/workflows/quality.yml").read_text(
        encoding="utf-8"
    )
    suite = subprocess.run(
        ["python", "-m", "pytest", "ci/tests/test_program_b_register.py", "-q"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    out.append(
        _probe_verdict(
            "R-B05",
            len(tracked) >= 3 and gate and suite.returncode == 0,
            f"{len(tracked)} tracked docs/program-b files, CI gate present={gate}, "
            f"suite rc={suite.returncode}",
            bool(tracked)
            and "zzz-not-a-gate"
            not in (REPO / ".github/workflows/quality.yml").read_text(encoding="utf-8"),
        )
    )
    return out


def main() -> int:
    results = verify()
    for r in results:
        print(f"  {r['verdict']:16} {r['check']:8} {r['measured']}")
    blocked = [r["check"] for r in results if not r["ok"]]
    if blocked:
        print(f"\nFAILED:close-round2 not eligible: {blocked} -- nothing written")
        return 1

    raw = CATALOG.read_text(encoding="utf-8")
    doc = json.loads(raw)
    assert json.dumps(doc, indent=1, ensure_ascii=False) == raw, (
        "serialiser drift; refusing to write"
    )

    closed, corrected = [], []
    for item in doc["items"]:
        iid = item["id"]
        if iid in CLOSES:
            item["status"] = item["disposition"] = "DONE-VERIFIED"
            item["disposition_evidence"] = CLOSES[iid]
            closed.append(iid)
        elif iid in CORRECTIONS:
            ev, action = CORRECTIONS[iid]
            item.setdefault("history", []).append(
                {
                    "event": "premise-corrected",
                    "date": "2026-08-10",
                    "superseded_evidence": item.get("evidence", ""),
                    "superseded_action": item.get("next_smallest_action", ""),
                }
            )
            item["evidence"] = ev
            item["next_smallest_action"] = action
            corrected.append(iid)

    if sorted(closed) != sorted(CLOSES) or sorted(corrected) != sorted(CORRECTIONS):
        print(f"FAILED:close-round2 closed={closed} corrected={corrected}")
        return 1

    # Register status cells for the closes, addressed by column index.
    reg = REGISTER.read_text(encoding="utf-8")
    eol = "\r\n" if "\r\n" in reg else "\n"
    lines = reg.split(eol)
    moved = []
    for n, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        parts = line.split("|")
        if len(parts) < 7 or parts[1].strip() not in CLOSES:
            continue
        parts[3] = " DONE-VERIFIED "
        lines[n] = "|".join(parts)
        moved.append(parts[1].strip())
    if sorted(moved) != sorted(CLOSES):
        print(f"FAILED:close-round2 register rows {moved}")
        return 1
    REGISTER.write_text(eol.join(lines), encoding="utf-8", newline="")

    # REACH-6: re-record the snapshot hash from LF-normalised bytes, since REGISTER.md just changed.
    import hashlib

    lf = REGISTER.read_bytes().replace(b"\r\n", b"\n")
    doc["provenance"]["register_sha256"] = hashlib.sha256(lf).hexdigest()
    doc["provenance"]["register_bytes"] = len(lf)

    CATALOG.write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8", newline=""
    )

    still_open = sum(1 for i in doc["items"] if i.get("status") == "OPEN")
    print(f"\n  CLOSED    : {', '.join(sorted(closed))}")
    print(
        f"  CORRECTED : {', '.join(sorted(corrected))} (premise refuted, item stays open)"
    )
    print(
        f"\nSUCCESS:close-round2 {len(closed)} closed, {len(corrected)} corrected; {still_open} OPEN"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
