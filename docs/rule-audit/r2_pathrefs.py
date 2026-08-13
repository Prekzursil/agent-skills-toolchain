"""R2: broken-pointer sweep over EVERY rule in the live and repo trees, three-way classified.

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
  * scope widens from 8 files to all rules in BOTH trees (live is what agents read at turn 0;
    repo is what the CI gates read), and markdown link targets are checked as well as backticked
    paths -- a link is a pointer too.

Read-only. Emits a terminal SUCCESS:/FAILED: marker and exits non-zero on a broken control or a
zero-file walk (a sweep that scanned nothing must never report "no broken pointers").
"""

from __future__ import annotations

import re
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parents[2]
TREES: dict[str, Path] = {"live": HOME / ".claude" / "rules", "repo": REPO / "rules"}

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
    for tree_name, rel, lineno, token, verdict in path_claims:
        key = (tree_name, rel, normalise_token(token))
        if key in WAIVERS:
            fired.add(key)
            print(
                f"  WAIVED  {tree_name}:{rel}:{lineno}  ->  {token}\n            {WAIVERS[key]}"
            )
        else:
            unwaived.append((tree_name, rel, lineno, token, verdict))
            print(f"  {verdict:<13} {tree_name}:{rel}:{lineno}  ->  {token}")

    # A waiver that no longer matches anything is a stale exemption silently widening the gate.
    stale = [k for k in WAIVERS if k not in fired]
    for key in stale:
        print(f"  STALE WAIVER (no longer matches): {key}")

    print("")
    if unwaived or stale:
        print(
            f"FAILED:r2_pathrefs unwaived_path_claims={len(unwaived)} stale_waivers={len(stale)}"
        )
        return 1
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
    silent-pass shape. These three states drive main() itself.
    """
    import contextlib
    import io
    import tempfile

    global TREES, WAIVERS
    real_trees, real_waivers = TREES, WAIVERS
    failures: list[str] = []

    def state(
        name: str, tree_body: str, waivers: dict, expect_rc: int, expect_in: str
    ) -> None:
        global TREES, WAIVERS
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "rules"
            (root / "common").mkdir(parents=True)
            (root / "common" / "probe.md").write_text(tree_body, encoding="utf-8")
            TREES = {"synthetic": root}
            WAIVERS = waivers
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

    print("gate-level controls (main() must go red for a real defect):")
    state("clean tree -> exit 0", clean, {}, 0, "unwaived_path_claims=0")
    state("broken positional claim -> exit 1", broken, {}, 1, "unwaived_path_claims=1")
    state(
        "stale waiver -> exit 1",
        clean,
        {("synthetic", "common/probe.md", "gone/never.py"): "no longer matches"},
        1,
        "STALE WAIVER",
    )

    TREES, WAIVERS = real_trees, real_waivers
    print("")
    if failures:
        print(f"FAILED:r2_pathrefs-self-test {failures}")
        return 1
    print("SUCCESS:r2_pathrefs-self-test all 3 gate-level controls passed")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(self_test() if "--self-test" in sys.argv else main())
