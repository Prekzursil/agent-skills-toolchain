"""Build an isolated git fixture that reproduces the git-archive CRLF trap."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CONTROL_REL = "control.txt"
CONTROL_BODY = "".join(f"line-{i:02d} control payload for TST-0252\n" for i in range(1, 21))
CHECKLIST_REL = "RELEASE-CHECKLIST.md"


def scratch_root() -> Path:
    return HERE / "scratch"


def build_fixture(root: Path | None = None) -> dict:
    """Create a repo whose `git archive` export is CRLF and whose blob is LF."""
    import sys

    sys.path.insert(0, str(REPO / "tools"))
    from docsverify.harness import git, measure, three_route_table

    root = Path(root) if root is not None else scratch_root()
    if root.exists():
        shutil.rmtree(root)
    repo = root / "repo"
    repo.mkdir(parents=True)

    (repo / ".gitattributes").write_text("* text eol=crlf\n", encoding="utf-8")
    (repo / CONTROL_REL).write_bytes(CONTROL_BODY.encode("ascii"))
    checklist = (HERE / "fixtures" / "RELEASE-CHECKLIST.md").read_text(encoding="utf-8")
    (repo / CHECKLIST_REL).write_text(checklist, encoding="utf-8", newline="\n")

    git(repo, "init", "-q")
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "config", "user.email", "tst-0252@fixture.invalid")
    git(repo, "config", "user.name", "TST-0252 fixture")
    git(repo, "config", "commit.gpgsign", "false")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "TST-0252 seed: LF blob, archive exports CRLF")
    rev = git(repo, "rev-parse", "HEAD").stdout.decode("ascii").strip()
    routes = dict(three_route_table(repo, CONTROL_REL, rev))
    blob_bytes = git(repo, "cat-file", "-p", f"{rev}:{CONTROL_REL}").stdout
    arch_bytes = subprocess.run(
        f"git -C {repo} archive {rev} {CONTROL_REL} | tar -xO",
        shell=True,
        capture_output=True,
    ).stdout or b""
    if "routes" not in routes:
        routes["routes"] = {
            "git archive | tar -xO": measure(arch_bytes),
            "git cat-file -p": measure(blob_bytes),
        }
    blob = (repo / CONTROL_REL).read_bytes()  # worktree; may still be LF
    return {
        "repo": repo,
        "root": root,
        "rev": rev,
        "control_rel": CONTROL_REL,
        "control_body": CONTROL_BODY,
        "checklist_rel": CHECKLIST_REL,
        "checklist_path": repo / CHECKLIST_REL,
        "seed_doc": HERE / "fixtures" / "RELEASE-CHECKLIST.md",
        "worktree_control": measure(blob),
        "routes": routes,
    }
