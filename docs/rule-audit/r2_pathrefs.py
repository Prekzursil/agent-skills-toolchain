"""Broken-pointer sweep over EVERY rule in ALL THREE rule trees, three-way classified.

Why this exists
---------------
The VERIFY lane ran a path-reference slice over the 8 always-on live rules and found no tenth
contradiction. The adversarial round then disclosed the weakness that makes that silence weaker
than it reads: ``_verify_pathrefs.py:44-46`` falls back to ``REPO.rglob(basename)``, so a
reference whose PATH is wrong but whose FILENAME exists somewhere else resolves as satisfied --
and its known-bad control used a filename absent everywhere, so the fallback was never exercised.
A control that cannot reach the failure mode is not a control for that failure mode.

Round 2 fixes both halves:

  * three-way verdict instead of found/missing --
        EXACT         the cited path resolves as written
        BASENAME-ONLY the path does NOT resolve, but that filename exists elsewhere
                      => the pointer is WRONG, which is precisely what the fallback hid
        MISSING       the filename exists nowhere
  * the control set now includes a synthetic BASENAME-ONLY case, so the sweep is proven able to
    reach the hidden state before any of its silence is believed,
  * scope widens from 8 files to all rules in EVERY tree, and markdown link targets are checked as
    well as backticked paths -- a link is a pointer too.

Round 3 fixes the round-2 defect an adversarial lane proved executable. ``TREES`` held only
``live`` and ``repo``; ``agent-self/config/rules`` -- 78 files, 30.7% of the 254-file corpus the
artifact's own DoD defines, and the tree ``agent-self/bootstrap.ps1:45`` force-copies over
``~/.claude`` -- was never swept, while the artifact answered "is there a tenth contradiction on
the path axis?" with "MEASURED: no". Widening the sweep found one. That earlier answer is REFUTED,
not deleted: see ``RULE-AUDIT-R2.md`` §4 and ``RULE-AUDIT.md`` §3.10.

Three buckets, because collapsing them is how a real defect gets green-washed:

    unwaived      an unadjudicated broken pointer -- the thing this sweep exists to catch
    WAIVERS       READ at source and found benign (use-vs-mention, or a quoted example whose
                  relative path is correct from the directory it is quoted FROM)
    KNOWN_DEFECTS READ at source and found REAL, but the file is outside this lane's write scope.
                  Loudly reported, never folded into a pass, and -- like a waiver -- an entry that
                  stops matching FAILS the sweep, so fixing the source forces the entry out.

Exit codes: ``0`` nothing outstanding · ``1`` an unknown broken pointer, or a stale WAIVER /
KNOWN_DEFECTS entry (something NEW or DRIFTED -- act on it) · ``2`` no new findings, but a tracked
real defect is still live. 2 is still a FAILED marker; it only distinguishes "known and tracked"
from "new", so this sweep keeps working as a regression gate while the tracked defect waits on an
owner with write access to that tree.

Read-only. Emits a terminal SUCCESS:/FAILED: marker and exits non-zero on a broken control or a
zero-file walk (a sweep that scanned nothing must never report "no broken pointers").
"""

from __future__ import annotations

import re
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parents[2]
TREES: dict[str, Path] = {
    "live": HOME / ".claude" / "rules",
    "repo": REPO / "rules",
    # Round 3: the tree round 2 silently excluded. bootstrap.ps1:45 force-copies it over
    # ~/.claude, so a broken pointer here ships to a fresh machine.
    "agent-self": REPO / "agent-self" / "config" / "rules",
}

EXTENSIONS = "py|ps1|sh|md|json|yml|yaml|toml|mjs|js|jsonl"
BACKTICK_RE = re.compile(rf"`([A-Za-z0-9_./-]+\.(?:{EXTENSIONS}))`")
# [text](target) -- ignore URLs, anchors and mailto.
LINK_RE = re.compile(r"\[[^\]]*\]\((?!https?:|#|mailto:)([^)\s#]+)\)")

# A basename this common is not evidence of anything; citing it is not a pointer claim.
GENERIC = {"settings.json", "package.json", "CLAUDE.md", "AGENTS.md", "README.md"}

# Adjudicated positional claims: each was READ at its source and found benign. A waiver carries
# its reason, and a waiver that stops matching FAILS the sweep -- a stale exemption quietly
# widens a gate, which is the same defect class as an unexercised control.
WAIVERS: dict[tuple[str, str, str], str] = {
    (
        "live",
        "README.md",
        "../common/coding-style.md",
    ): "illustrative example of an override note as it would appear in rules/golang/; the link "
    "is correct from THAT directory. The probe resolves relative to the containing file, which "
    "it cannot do for a quoted example written from another file's perspective.",
    (
        "repo",
        "common/cross-vendor-dispatch.md",
        "lib/job-control.mjs",
    ): "use-vs-mention: the same sentence states the companion is NOT present in this repo. "
    "The rule names the file to describe a historical mechanism, it does not depend on it.",
    (
        "agent-self",
        "README.md",
        "../common/coding-style.md",
    ): "the SAME illustrative override note as the live:README.md waiver above -- read both, the "
    "sentence is identical and is quoted from the rules/golang/ perspective, where ../common/ "
    "is correct. Probe limitation (it resolves relative to the containing file), not a defect.",
}

# Adjudicated REAL broken pointers whose source file is outside this lane's write scope. Distinct
# from WAIVERS on purpose: a waiver says "not a defect", this says "a defect, tracked, and this
# sweep is not allowed to go green while it is live". Each entry names its tracking anchor, and a
# stale entry fails the sweep so a fix cannot leave a lie behind.
KNOWN_DEFECTS: dict[tuple[str, str, str], str] = {
    (
        "agent-self",
        "README.md",
        "common/windows-shell.md",
    ): "REAL and live. agent-self/config/rules/README.md:74 links [`common/windows-shell.md`]"
    "(common/windows-shell.md) while describing it as the cross-tool rule; that tree ships 10 "
    "common/ files and windows-shell.md is not one of them (ls, find and git ls-files all agree). "
    "Tracked as RULE-AUDIT.md 3.10 with its correction; agent-self/** is propose-only for this "
    "lane, so the fix is proposed, not applied.",
}

_basename_index: dict[str, int] | None = None
_home_cache: dict[str, bool] = {}

# ~/.claude holds the plugin cache (where the VERIFY lane found codex-rescue.md) but also
# multi-GB of session transcripts. Walk only the directories that can hold a cited artifact.
HOME_SEARCH_DIRS = (
    "plugins",
    "skills",
    "hooks",
    "agents",
    "commands",
    "rules",
    "scripts",
)


def basename_index() -> dict[str, int]:
    """One walk of the repo, reused: filename -> how many files carry it."""
    global _basename_index
    if _basename_index is None:
        index: dict[str, int] = {}
        for path in REPO.rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                index[path.name] = index.get(path.name, 0) + 1
        _basename_index = index
    return _basename_index


def in_claude_home(name: str) -> bool:
    """Bounded lookup for a basename under ~/.claude.

    Without this the sweep re-reports codex-rescue.md as MISSING -- a finding the VERIFY lane
    already refuted by locating it in the plugin cache. A detector that re-raises a known-refuted
    finding is a detector failure, not a finding.
    """
    if name not in _home_cache:
        found = False
        for sub in HOME_SEARCH_DIRS:
            root = HOME / ".claude" / sub
            if root.is_dir() and next(root.rglob(name), None) is not None:
                found = True
                break
        _home_cache[name] = found
    return _home_cache[name]


def normalise_token(token: str) -> str:
    """Strip a leading ``./`` -- and ONLY that.

    NOT ``lstrip("./")``: that strips a character SET, so ``.agents/skills/...`` became
    ``agents/skills/...`` and a real dotted-directory path was misreported BASENAME-ONLY. This
    probe shipped that bug; the regression control below is what caught it.
    """
    token = token.strip()
    return token[2:] if token.startswith("./") else token


def classify(token: str, tree_root: Path, containing_dir: Path) -> str:
    """EXACT / BASENAME-ONLY / MISSING for one cited path."""
    token = normalise_token(token)
    if not token:
        return "EXACT"
    bases = (REPO, HOME / ".claude", HOME, tree_root, containing_dir)
    for base in bases:
        try:
            if (base / token).exists():
                return "EXACT"
        except OSError:  # pragma: no cover - defensive on Windows path limits
            continue
    name = token.split("/")[-1]
    if basename_index().get(name) or in_claude_home(name):
        return "BASENAME-ONLY"
    return "MISSING"


def references(text: str) -> list[tuple[int, str, str]]:
    """``(line_number, kind, token)`` for every pointer-shaped reference."""
    out: list[tuple[int, str, str]] = []
    fenced = False
    for lineno, line in enumerate(text.split("\n"), start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue  # a shell example is illustrative, not a pointer claim
        for token in BACKTICK_RE.findall(line):
            out.append((lineno, "backtick", token))
        for token in LINK_RE.findall(line):
            out.append((lineno, "link", token))
    return out


def controls() -> bool:
    """Three-way both-states proof, including the state the previous probe could not reach."""
    tree = (
        REPO / "rules"
    )  # the controls are about the resolver, not about the scanned trees
    here = Path(__file__).resolve().parent
    cases = [
        ("scripts/sync-rules.ps1", "EXACT", "a path that resolves as written"),
        # THE CASE THE OLD PROBE COULD NOT SEE: wrong directory, real filename.
        ("no_such_dir/sync-rules.ps1", "BASENAME-ONLY", "wrong path, filename exists"),
        ("scripts/__definitely_not_here__.ps1", "MISSING", "filename exists nowhere"),
        # REGRESSION control for a bug this probe shipped and I caught: lstrip("./") strips a
        # character SET, so a leading dot-directory was eaten and this real file read as a
        # wrong pointer. Without this case the fix is unproven.
        (
            ".agents/skills/claim-verify-gate/scripts/claim_gate.py",
            "EXACT",
            "dotted-directory path must not be mangled",
        ),
        ("./scripts/sync-rules.ps1", "EXACT", "a leading ./ is still stripped"),
    ]
    ok = True
    for token, expected, why in cases:
        got = classify(token, tree, here)
        flag = "PASS" if got == expected else "FAIL"
        if got != expected:
            ok = False
        print(f"  {flag}  control {expected:<13} -> {got:<13} ({why})")
    return ok


def main() -> int:
    print("detector controls (all three verdicts must be reachable):")
    if not controls():
        print(
            "FAILED:r2_pathrefs controls cannot distinguish the three verdicts -- sweep inert"
        )
        return 1
    print("")

    scanned = 0
    findings: list[tuple[str, str, int, str, str]] = []
    for tree_name, root in TREES.items():
        if not root.is_dir():
            print(f"FAILED:r2_pathrefs tree {tree_name} missing at {root}")
            return 1
        files = sorted(root.rglob("*.md"))
        if not files:
            print(
                f"FAILED:r2_pathrefs tree {tree_name} walked to zero files -- fail closed"
            )
            return 1
        for path in files:
            scanned += 1
            text = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
            rel = path.relative_to(root).as_posix()
            for lineno, kind, token in references(text):
                if token.split("/")[-1] in GENERIC and "/" not in token:
                    continue
                verdict = classify(token, root, path.parent)
                if verdict != "EXACT":
                    findings.append((tree_name, rel, lineno, token, verdict))

    # USE-VS-MENTION, applied as a FIELD and not a judgement about prose: a bare filename with
    # no directory component ("read the project's `.coverage-thresholds.json`") names a file
    # CLASS and asserts no location, so it cannot be a broken pointer. Only a token carrying a
    # directory component is a positional claim that can be wrong. Counting the document instead
    # of the field is what mislabels this class every time.
    path_claims = [f for f in findings if "/" in normalise_token(f[3])]
    name_mentions = [f for f in findings if "/" not in normalise_token(f[3])]

    print(f"rule files scanned: {scanned} across {len(TREES)} trees")
    print(f"non-EXACT references: {len(findings)}")
    print(
        f"  bare-filename MENTIONS (no location asserted, not findings): {len(name_mentions)}"
    )
    print(f"  POSITIONAL path claims that do not resolve: {len(path_claims)}")

    unwaived: list[tuple[str, str, int, str, str]] = []
    fired: set[tuple[str, str, str]] = set()
    defects_fired: set[tuple[str, str, str]] = set()
    for tree_name, rel, lineno, token, verdict in path_claims:
        key = (tree_name, rel, normalise_token(token))
        if key in WAIVERS:
            fired.add(key)
            print(
                f"  WAIVED  {tree_name}:{rel}:{lineno}  ->  {token}\n            {WAIVERS[key]}"
            )
        elif key in KNOWN_DEFECTS:
            defects_fired.add(key)
            print(
                f"  TRACKED DEFECT  {verdict}  {tree_name}:{rel}:{lineno}  ->  {token}"
                f"\n            {KNOWN_DEFECTS[key]}"
            )
        else:
            unwaived.append((tree_name, rel, lineno, token, verdict))
            print(f"  {verdict:<13} {tree_name}:{rel}:{lineno}  ->  {token}")

    # An entry that no longer matches anything is a stale exemption silently widening the gate --
    # true of a waiver, and equally true of a tracked defect somebody has since fixed.
    stale = [k for k in WAIVERS if k not in fired]
    stale += [k for k in KNOWN_DEFECTS if k not in defects_fired]
    for key in stale:
        print(f"  STALE ENTRY (no longer matches, remove it): {key}")

    print("")
    if unwaived or stale:
        print(
            f"FAILED:r2_pathrefs unwaived_path_claims={len(unwaived)} stale_entries={len(stale)}"
        )
        return 1
    if defects_fired:
        print(
            f"FAILED:r2_pathrefs scanned={scanned} unwaived_path_claims=0 "
            f"waived={len(fired)} known_defects={len(defects_fired)} still live and tracked "
            f"(no NEW finding; rc=2 distinguishes this from rc=1)"
        )
        return 2
    print(
        f"SUCCESS:r2_pathrefs scanned={scanned} unwaived_path_claims=0 "
        f"waived={len(fired)} name_mentions={len(name_mentions)} "
        f"(basename_only={sum(1 for f in findings if f[4] == 'BASENAME-ONLY')} "
        f"missing={sum(1 for f in findings if f[4] == 'MISSING')})"
    )
    return 0


def self_test() -> int:
    """Both-states proof at the GATE level, not just the classifier level.

    The classifier controls above show the three verdicts are reachable. They do NOT show that
    the gate goes red when something is actually wrong -- a sweep that always exits 0 is the
    silent-pass shape, and one that always exits non-zero is just as inert. These six states drive
    main() itself and pin every exit code the contract promises.
    """
    import contextlib
    import io
    import tempfile

    global TREES, WAIVERS, KNOWN_DEFECTS
    real_trees, real_waivers, real_defects = TREES, WAIVERS, KNOWN_DEFECTS
    failures: list[str] = []

    def state(
        name: str,
        tree_body: str,
        waivers: dict,
        expect_rc: int,
        expect_in: str,
        defects: dict | None = None,
    ) -> None:
        global TREES, WAIVERS, KNOWN_DEFECTS
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "rules"
            (root / "common").mkdir(parents=True)
            (root / "common" / "probe.md").write_text(tree_body, encoding="utf-8")
            TREES = {"synthetic": root}
            WAIVERS = waivers
            KNOWN_DEFECTS = defects or {}
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = main()
            text = out.getvalue()
        ok = rc == expect_rc and expect_in in text
        print(f"  {'PASS' if ok else 'FAIL'}  {name} -- rc={rc} (expected {expect_rc})")
        if not ok:
            failures.append(name)

    clean = (
        "A rule citing `scripts/sync-rules.ps1` and the bare name `pyproject.toml`.\n"
    )
    broken = (
        "A rule citing `no_such_dir/definitely_absent_xyz.py` as if it were there.\n"
    )
    tracked = {
        ("synthetic", "common/probe.md", "no_such_dir/definitely_absent_xyz.py"): (
            "adjudicated real, source outside write scope"
        )
    }

    print("gate-level controls (main() must go red for a real defect):")
    state("clean tree -> exit 0", clean, {}, 0, "unwaived_path_claims=0")
    state("broken positional claim -> exit 1", broken, {}, 1, "unwaived_path_claims=1")
    state(
        "stale waiver -> exit 1",
        clean,
        {("synthetic", "common/probe.md", "gone/never.py"): "no longer matches"},
        1,
        "STALE ENTRY",
    )
    # The rc=2 bucket only earns its keep if BOTH halves are proven: a tracked defect must not
    # read as clean (it exits 2, not 0), and it must not silence a NEW one (that is still rc=1).
    state(
        "tracked defect, nothing new -> exit 2",
        broken,
        {},
        2,
        "known_defects=1",
        defects=tracked,
    )
    state(
        "tracked defect + a NEW broken claim -> exit 1",
        broken
        + "and also `other_dir/second_absent_xyz.py` which nobody adjudicated.\n",
        {},
        1,
        "unwaived_path_claims=1",
        defects=tracked,
    )
    state(
        "stale tracked defect -> exit 1",
        clean,
        {},
        1,
        "STALE ENTRY",
        defects={("synthetic", "common/probe.md", "gone/never.py"): "already fixed"},
    )

    TREES, WAIVERS, KNOWN_DEFECTS = real_trees, real_waivers, real_defects
    print("")
    if failures:
        print(f"FAILED:r2_pathrefs-self-test {failures}")
        return 1
    print("SUCCESS:r2_pathrefs-self-test all 6 gate-level states passed")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(self_test() if "--self-test" in sys.argv else main())
