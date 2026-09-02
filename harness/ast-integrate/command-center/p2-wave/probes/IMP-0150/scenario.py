"""Plant git fixtures for IMP-0150 named probes.

Git runs only inside TemporaryDirectory trees. This worktree is never
add/commit/checkout'd.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

KNOWN_PRESENT = "workflows/rtv-pdr.js"
SENTINEL = "workflows/__IMP0150_SENTINEL_NOWHERE__.js"
REF_ONLY = "workflows/ref-only-remote.js"
REF_ONLY_REF = "origin/imp0150-ref-only"
LINKED_PATH = "workflows/linked-worktree.js"
LIVE_ARC_CONTROL = (
    "command-center/p2-wave/probes/ARC-0004/fixtures/estate/t0-baseline/"
    "capabilities/workflows/wf.catalog-class.discovery-only.wf.json"
)

RTV_PDR_JS = """\
// Saved Workflow: rtv-pdr (IMP-0150 planted known-present).
// Dialect: injected agent / parallel / phase globals.
export default async function rtvPdr(ctx) {
  await phase("discover", async () => {
    await parallel([
      agent("scout", { task: "enumerate local workflow artifacts" }),
      agent("hasher", { task: "hash each candidate" }),
    ]);
  });
  await phase("report", async () => {
    await agent("scribe", { task: "emit candidate rows with access methods" });
  });
}
"""

REF_ONLY_JS = """\
// REF-ONLY remote workflow. A bare path here is unreadable.
export default async function refOnlyRemote() {
  await phase("secret", async () => {
    await agent("ghost", { task: "IMP-0150-REF-ONLY-MARKER" });
  });
}
"""

LINKED_JS = """\
export default async function linkedWorktree() {
  await agent("linked", { task: "IMP-0150-LINKED-WORKTREE" });
}
"""

README = "IMP-0150 fixture repository\n"


def git_show_access(ref: str, rel: str) -> str:
    return f"git show {ref}:{rel}"


def _git_init(root: Path, env: dict[str, str]) -> None:
    try:
        git(root, env, "init", "-b", "main")
    except RuntimeError:
        git(root, env, "init")
        git(root, env, "symbolic-ref", "HEAD", "refs/heads/main")


def _git_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_AUTHOR_NAME"] = "IMP-0150"
    env["GIT_AUTHOR_EMAIL"] = "imp-0150@local.test"
    env["GIT_COMMITTER_NAME"] = "IMP-0150"
    env["GIT_COMMITTER_EMAIL"] = "imp-0150@local.test"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(cwd: Path, env: dict[str, str], *args: str) -> str:
    if args and args[0] == "archive":
        raise RuntimeError("git archive is forbidden in IMP-0150 fixtures")
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {(proc.stderr or proc.stdout or '').strip()}"
        )
    return proc.stdout


def git_out_bytes(cwd: Path, env: dict[str, str], *args: str) -> bytes:
    if args and args[0] == "archive":
        raise RuntimeError("git archive is forbidden in IMP-0150 fixtures")
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {err}")
    return proc.stdout


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def plant_empty(root: Path, home: Path) -> dict:
    """Git repo with no workflow-shaped files (known-present must be silent)."""
    root.mkdir(parents=True, exist_ok=True)
    env = _git_env(home)
    _git_init(root, env)
    _write(root / "README.md", README)
    git(root, env, "add", "README.md")
    git(root, env, "-c", "commit.gpgsign=false", "commit", "-m", "empty fixture")
    return {"root": root, "env": env}


def plant_repo(root: Path, home: Path, linked: Path) -> dict:
    """Primary tree + remote-only ref + linked worktree."""
    from discovery.local_repo import sha256_bytes

    root.mkdir(parents=True, exist_ok=True)
    env = _git_env(home)
    _git_init(root, env)
    _write(root / "README.md", README)
    _write(root / KNOWN_PRESENT, RTV_PDR_JS)
    git(root, env, "add", "README.md", KNOWN_PRESENT)
    git(root, env, "-c", "commit.gpgsign=false", "commit", "-m", "known-present rtv-pdr")

    git(root, env, "checkout", "-b", "imp0150-ref-only")
    _write(root / REF_ONLY, REF_ONLY_JS)
    git(root, env, "add", REF_ONLY)
    git(root, env, "-c", "commit.gpgsign=false", "commit", "-m", "ref-only remote workflow")
    sha = git(root, env, "rev-parse", "HEAD").strip()
    git(root, env, "update-ref", f"refs/remotes/{REF_ONLY_REF}", sha)
    git(root, env, "checkout", "main")
    git(root, env, "branch", "-D", "imp0150-ref-only")

    git(root, env, "branch", "imp0150-linked")
    git(root, env, "worktree", "add", str(linked), "imp0150-linked")
    _write(linked / LINKED_PATH, LINKED_JS)
    git(linked, env, "add", LINKED_PATH)
    git(
        linked,
        env,
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-m",
        "linked worktree workflow",
    )

    present_bytes = (root / KNOWN_PRESENT).read_bytes()
    ref_raw = git_out_bytes(root, env, "show", f"{REF_ONLY_REF}:{REF_ONLY}")
    linked_bytes = (linked / LINKED_PATH).read_bytes()
    return {
        "root": root,
        "linked": linked,
        "env": env,
        "known_present": KNOWN_PRESENT,
        "known_present_hash": sha256_bytes(present_bytes),
        "sentinel": SENTINEL,
        "ref_only_path": REF_ONLY,
        "ref_only_ref": REF_ONLY_REF,
        "ref_only_access": git_show_access(REF_ONLY_REF, REF_ONLY),
        "ref_only_hash": sha256_bytes(ref_raw),
        "linked_path": LINKED_PATH,
        "linked_hash": sha256_bytes(linked_bytes),
        "linked_exists_on_primary": (root / LINKED_PATH).is_file(),
        "ref_only_exists_on_primary": (root / REF_ONLY).is_file(),
    }
