"""DELETE-ALL model: 77 deleted paths across 5 trees, recovered only via git.

This Linux worktree has no parent .git and no live tools/lib salvage. The
fixture is a recoverable git object store that models the catalog's DELETE-ALL
(77 files, five trees, salvage home tools/lib). It is labelled as a model, not
as the missing Windows-estate object store.

Git writes stay inside the fixture GIT_DIR via hash-object / mktree /
commit-tree. No git add/commit/push/stash/checkout/rebase on the worktree.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

TREES = (
    "origin.cli",
    "origin.hooks",
    "origin.docs",
    "origin.tests",
    "origin.lib",
)

LOST_SYMBOL = "bld0035LostUniqueSymbol"
LOST_TOKEN = "BLD0035_LOST_UNIQUE_BEHAVIOUR"
PRESERVED_SYMBOL = "checkNetAllowlist"
PRESERVED_TOKEN = "BLD0035_PRESERVED_NET_ALLOWLIST"
COVERAGE_TOKEN = "BLD0035_UNIQUE_ASSERTION_NO_EQUIVALENT"
LOST_TEST_NAME = "lost unique coverage has no retained equivalent"
LOST_PATH = "origin.lib/lost-unique.mjs"
PRESERVED_PATH = "origin.lib/net-allowlist.mjs"
LOST_TEST_PATH = "origin.tests/test_lost_unique_assertion.mjs"

SALVAGE_MODULES = {
    "net-allowlist.mjs": f'''\
export function {PRESERVED_SYMBOL}(host) {{
  return host === "allowed.example";
}}
export const NET_ALLOWLIST_TOKEN = "{PRESERVED_TOKEN}";
''',
    "security.mjs": """\
export function assertNoSecrets(text) {
  return !/AKIA[0-9A-Z]{16}/.test(String(text));
}
""",
    "git-diff.mjs": """\
export function parseGitDiff(raw) {
  return String(raw).split("\\n").filter(Boolean).length;
}
""",
    "handled-ledger.mjs": """\
export function appendHandledLedger(id, bytes) {
  return { id: String(id), bytes: Number(bytes) };
}
""",
    "codex-invocation.mjs": """\
export function invokeCodex(prompt) {
  return { prompt: String(prompt), ok: true };
}
""",
    "workspace.mjs": """\
export function resolveWorkspaceRoot(cwd) {
  return String(cwd || ".");
}
""",
}


def _lf(text: str) -> bytes:
    return text.replace("\r\n", "\n").encode("utf-8")


def deleted_contents() -> dict[str, bytes]:
    files: dict[str, bytes] = {}

    for name, body in SALVAGE_MODULES.items():
        files[f"origin.lib/{name}"] = _lf(body)
    files[LOST_PATH] = _lf(
        f'''\
export function {LOST_SYMBOL}() {{
  return "{LOST_TOKEN}";
}}
'''
    )
    for i in range(8):
        files[f"origin.lib/re-export-{i:02d}.mjs"] = _lf(
            f'export {{ {PRESERVED_SYMBOL} }} from "./net-allowlist.mjs";\n'
        )
    # origin.lib = 6 salvage + 1 lost + 8 re-exports = 15

    for i in range(16):
        files[f"origin.cli/cli-{i:02d}.mjs"] = _lf(
            f'export {{ {PRESERVED_SYMBOL} }} from "../origin.lib/net-allowlist.mjs";\n'
        )

    hook = {
        "event": "PreToolUse",
        "command": "node tools/lib/net-allowlist.mjs",
    }
    for i in range(15):
        files[f"origin.hooks/hook-{i:02d}.json"] = _lf(
            json.dumps(hook, indent=1) + "\n"
        )

    for i in range(15):
        files[f"origin.docs/doc-{i:02d}.md"] = _lf(
            f"# Retired origin.docs/{i:02d}\n\n"
            "Narrative only. No documented commands. Owner DELETE-ALL.\n"
        )

    files[LOST_TEST_PATH] = _lf(
        f'''\
import assert from "node:assert/strict";
test("{LOST_TEST_NAME}", () => {{
  assert.equal("{COVERAGE_TOKEN}", "{COVERAGE_TOKEN}");
}});
'''
    )
    for i in range(15):
        files[f"origin.tests/test_salvage_{i:02d}.mjs"] = _lf(
            f'''\
import assert from "node:assert/strict";
test("retained salvage still has {PRESERVED_TOKEN}", () => {{
  assert.equal("{PRESERVED_TOKEN}", "{PRESERVED_TOKEN}");
}});
'''
        )
    # origin.tests = 1 unique lost + 15 salvage tests = 16
    return files


def retained_contents() -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for name, body in SALVAGE_MODULES.items():
        files[f"tools/lib/{name}"] = _lf(body)
    files["tools/lib/hooks/pre-tool.json"] = _lf(
        json.dumps(
            {
                "event": "PreToolUse",
                "command": "node tools/lib/net-allowlist.mjs",
            },
            indent=1,
        )
        + "\n"
    )
    files["tools/lib/tests/test_salvage.mjs"] = _lf(
        f'''\
import assert from "node:assert/strict";
test("retained salvage still has {PRESERVED_TOKEN}", () => {{
  assert.equal("{PRESERVED_TOKEN}", "{PRESERVED_TOKEN}");
}});
'''
    )
    return files


def _git(git_dir: Path, args: list[str], *, input_bytes: bytes | None = None) -> bytes:
    env = os.environ.copy()
    env["GIT_DIR"] = str(git_dir)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_AUTHOR_NAME"] = "BLD-0035"
    env["GIT_AUTHOR_EMAIL"] = "bld-0035@local"
    env["GIT_AUTHOR_DATE"] = "2026-08-01T00:00:00Z"
    env["GIT_COMMITTER_NAME"] = env["GIT_AUTHOR_NAME"]
    env["GIT_COMMITTER_EMAIL"] = env["GIT_AUTHOR_EMAIL"]
    env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"]
    p = subprocess.run(
        ["git", *args],
        input=input_bytes,
        capture_output=True,
        env=env,
        check=False,
    )
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", "replace")[-800:]
        raise RuntimeError(f"git {args} failed: {err}")
    return p.stdout


def _hash_blob(git_dir: Path, data: bytes) -> str:
    out = _git(git_dir, ["hash-object", "-w", "--stdin"], input_bytes=data)
    return out.decode("ascii").strip()


def _mktree(git_dir: Path, entries: list[tuple[str, str, str]]) -> str:
    # entries: (mode, type, oid, name) but we pass mode/type encoded
    lines = []
    for mode, typ, oid, name in entries:
        lines.append(f"{mode} {typ} {oid}\t{name}")
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    out = _git(git_dir, ["mktree"], input_bytes=payload)
    return out.decode("ascii").strip()


def _build_nested_tree(git_dir: Path, files: dict[str, bytes]) -> tuple[str, dict[str, str]]:
    blobs: dict[str, str] = {}
    nested: dict = {}
    for path, data in files.items():
        oid = _hash_blob(git_dir, data)
        blobs[path] = oid
        parts = path.split("/")
        cursor = nested
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = ("blob", oid)

    def walk(node: dict) -> str:
        entries: list[tuple[str, str, str, str]] = []
        for name in sorted(node):
            val = node[name]
            if isinstance(val, tuple) and val[0] == "blob":
                entries.append(("100644", "blob", val[1], name))
            else:
                tree_oid = walk(val)
                entries.append(("040000", "tree", tree_oid, name))
        return _mktree(git_dir, entries)

    return walk(nested), blobs


def write_retained(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    for rel, data in retained_contents().items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return root


def init_git_dir(git_dir: Path) -> Path:
    if git_dir.exists():
        shutil.rmtree(git_dir)
    git_dir.mkdir(parents=True, exist_ok=True)
    _git(git_dir, ["init", "--bare", "--quiet"])
    return git_dir


def build(scratch: Path | None = None) -> dict:
    base = Path(scratch) if scratch else Path(tempfile.mkdtemp(prefix="bld0035-"))
    git_dir = init_git_dir(base / "recovery.git")
    retained = write_retained(base / "retained")
    files = deleted_contents()
    if len(files) != 77:
        raise RuntimeError(f"expected 77 deleted paths, got {len(files)}")
    trees_present = sorted({p.split("/")[0] for p in files})
    if trees_present != sorted(TREES):
        raise RuntimeError(f"trees {trees_present} != {list(TREES)}")

    tree_oid, blobs = _build_nested_tree(git_dir, files)
    commit_oid = (
        _git(git_dir, ["commit-tree", tree_oid, "-m", "BLD-0035 pre-delete model"])
        .decode("ascii")
        .strip()
    )
    _git(git_dir, ["update-ref", "refs/heads/pre-delete", commit_oid])

    deleted = []
    for path in sorted(files):
        raw = files[path]
        deleted.append(
            {
                "path": path,
                "tree": path.split("/")[0],
                "blob_oid": blobs[path],
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        )
    return {
        "git_dir": git_dir,
        "retained_root": retained,
        "commit_oid": commit_oid,
        "tree_oid": tree_oid,
        "files": files,
        "blobs": blobs,
        "deleted": deleted,
        "scratch": base,
    }


def live_estate(repo: Path | None = None) -> dict:
    root = repo or REPO
    git_present = (root / ".git").exists()
    tools_lib = (root / "tools" / "lib").is_dir()
    aud = root / "command-center" / "audit" / "AUD-0094-retirement-blast-radius.json"
    return {
        "worktree_git": git_present,
        "tools_lib_present": tools_lib,
        "aud_0094_present": aud.is_file(),
        "original_77_recovery": "RECOVERED"
        if git_present
        else "UNPROVEN",
        "reason": (
            "parent worktree has a .git; live recovery would walk that object store"
            if git_present
            else (
                "this Linux worktree has no .git object store, no AUD-0094 receipt, "
                "and no tools/lib salvage tree; the original Windows-estate 77-file "
                "DELETE-ALL is UNPROVEN here"
            )
        ),
    }
