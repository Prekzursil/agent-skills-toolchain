#!/usr/bin/env python3
"""AUD-0005 probe1 -- git tag dereference census (live, fail-closed).

Rebuilds the fixture control repo in a temp dir and re-proves the
discriminating instrument: `git rev-list -n 1 <tag>` (caret form forbidden)
resolves real annotated tags to their commit SHA (LIVE) and fails on a
string-registry-only "tag" that has no git object (DEAD). Then re-verifies the
artifact's tag_rows against its recorded verdicts and tallies, and re-proves
the planted orphan control's independence (probe1 LIVE / probe2 DEAD).
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/audit/AUD-0005-tag-release-parity.json"
UNIT = "AUD-0005"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe1 artifact unreadable: {type(exc).__name__}")
        return 1

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{': ' + detail if detail else ''}")

    # structural predicate
    check(isinstance(doc, dict), "artifact not a JSON object")
    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(
        str(doc.get("state", "")).upper() not in NOT_DELIVERING,
        "self-declared non-delivery",
        str(doc.get("state")),
    )
    check(OUT.stat().st_size > 0, "artifact empty")
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent")

    # rebuild the fixture control repo: two real tags + a registry-only orphan
    with tempfile.TemporaryDirectory(prefix="aud0005probe1-") as td:
        fx = Path(td)
        ok, out = run(["git", "init", "-q", "repo"], fx)
        check(ok == 0, "git init failed", out[:120])
        repo = fx / "repo"
        run(["git", "config", "user.email", "probe@example.invalid"], repo)
        run(["git", "config", "user.name", "AUD-0005 probe1"], repo)
        (repo / "VERSION").write_text("1.0.0\n", encoding="utf-8", newline="\n")
        run(["git", "add", "VERSION"], repo)
        run(["git", "commit", "-q", "-m", "v1.0.0"], repo)
        run(["git", "tag", "-a", "v1.0.0", "-m", "release 1.0.0"], repo)
        (repo / "VERSION").write_text("1.1.0\n", encoding="utf-8", newline="\n")
        run(["git", "add", "VERSION"], repo)
        run(["git", "commit", "-q", "-m", "v1.1.0"], repo)
        run(["git", "tag", "-a", "v1.1.0", "-m", "release 1.1.0"], repo)
        # string-registry-only orphan: the name exists ONLY in a registry file
        (repo / "REGISTRY.txt").write_text(
            "v0.0.0-aud0005-orphan\n", encoding="utf-8", newline="\n"
        )
        run(["git", "add", "REGISTRY.txt"], repo)
        run(["git", "commit", "-q", "-m", "registry mentions an untagged version"], repo)

        def deref(tag: str) -> tuple[int, str]:
            rc, out = run(["git", "rev-list", "-n", "1", tag], repo)
            return rc, out

        rc0, sha0 = deref("v1.0.0")
        rc1, _sha1 = deref("v1.1.0")
        rc_orph, _ = deref("v0.0.0-aud0005-orphan")
        check(rc0 == 0 and SHA_RE.match(sha0) is not None, "fixture tag v1.0.0 did not deref", sha0[:80])
        check(rc1 == 0, "fixture tag v1.1.0 did not deref")
        check(rc_orph != 0, "registry-only orphan tag dereferenced (instrument cannot fire)")

    # artifact census re-verification
    rows = doc.get("tag_rows") or []
    items = doc.get("items") or []
    tallies = doc.get("tallies") or {}
    check(len(rows) == int(tallies.get("modules_scanned", -1)), "tag_rows != tallies.modules_scanned",
          f"{len(rows)} vs {tallies.get('modules_scanned')}")
    check(len(items) == len(rows), "items and tag_rows disagree in length")
    p1_dead = [r for r in rows if r.get("probe1_verdict") == "DEAD"]
    check(len(p1_dead) == int(tallies.get("probe1_dead", -1)), "probe1_dead recount mismatch",
          f"{len(p1_dead)} vs {tallies.get('probe1_dead')}")
    for r in rows:
        if r.get("probe1_verdict") == "LIVE":
            # probe1's arm is git-side dereference only: a LIVE row must carry
            # the resolved commit SHA. Release-asset checks are probe2's arm.
            check(bool(SHA_RE.match(str(r.get("commit", "")))),
                  "LIVE row without a well-formed 40-hex resolved commit", str(r.get("tag")))
    # planted orphan control: independent across probes
    pc = doc.get("planted_control") or {}
    check(pc.get("independent") is True, "planted_control.independent not true")
    check(pc.get("probe1_verdict") == "LIVE" and pc.get("probe2_verdict") == "DEAD",
          "planted control verdict pair drift",
          f"{pc.get('probe1_verdict')}/{pc.get('probe2_verdict')}")
    check(int(tallies.get("disagree", -1)) == 3, "tallies.disagree != 3", str(tallies.get("disagree")))
    check(doc.get("answer") and "Planted control" in str(doc.get("answer")), "answer corpus missing")
    # scope honesty: caret form forbidden
    scope = doc.get("scope") or {}
    check("caret" in str(scope.get("git_instrument", "")).lower(),
          "scope does not record the caret-form prohibition")

    # drift notes (recorded, not gating)
    if not (REPO / ".git").is_dir():
        notes.append(
            "drift note: artifact records worktree_is_git=true (built in the prior builder's "
            "tree); the current worktree is not a git repository, so the discriminating census "
            "is the freshly rebuilt fixture control-repo above, which re-proves the instrument"
        )

    report = {
        "probe": "probe1-git-tag-deref",
        "unit_id": UNIT,
        "fixture": "temp control repo (2 annotated tags + registry-only orphan)",
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe1 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe1 tag-deref instrument re-proven (2 tags LIVE, orphan DEAD); "
          f"{len(rows)} artifact rows consistent with tallies; planted control independent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
