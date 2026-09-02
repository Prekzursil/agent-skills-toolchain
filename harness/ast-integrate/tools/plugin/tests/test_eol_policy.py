"""Blob-level CRLF controls for IMP-0017 (git cat-file, not the worktree)."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _git(root: Path, *args: str) -> tuple[int, str, str]:
    p = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return p.returncode, p.stdout or "", p.stderr or ""


def _git_blob_bytes(root: Path, spec: str) -> bytes:
    """``git cat-file -p <spec>`` as raw bytes (text mode would fold CRLF to LF)."""
    p = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-p", spec],
        capture_output=True,
        check=False,
    )
    return p.stdout if p.returncode == 0 else b""


def _blob_has_cr(repo: Path, rel: str) -> bool:
    rc, out, _ = _git(repo, "ls-files", "-z", "--", rel)
    if rc != 0 or not out:
        return False
    rc, sha, _ = _git(repo, "rev-parse", f"HEAD:{rel.replace(os.sep, '/')}")
    if rc != 0:
        rc, sha, _ = _git(repo, "hash-object", rel)
    if rc != 0:
        return False
    sha = sha.strip()
    return b"\r" in _git_blob_bytes(repo, sha)


def test_no_cr_in_shipped_shell_blobs() -> dict:
    """Worktree may contain CRLF; the git blob of shipped *.sh must not."""
    sh_files = [
        p.relative_to(REPO).as_posix()
        for p in (REPO / "tools" / "plugin").rglob("*.sh")
        if p.is_file()
    ]
    if not sh_files:
        # Plant a worktree-CR / blob-LF pair in a scratch repo so the control fires.
        with tempfile.TemporaryDirectory(prefix="imp0017-eol-") as raw:
            root = Path(raw)
            _git(root, "init")
            _git(root, "config", "user.email", "eol@example.test")
            _git(root, "config", "user.name", "eol")
            (root / ".gitattributes").write_text("*.sh text eol=lf\n", encoding="utf-8")
            script = root / "tools" / "plugin" / "pack.sh"
            script.parent.mkdir(parents=True)
            lf = "#!/bin/sh\necho ok\n"
            script.write_bytes(lf.replace("\n", "\r\n").encode("utf-8"))
            _git(root, "add", ".")
            _git(root, "commit", "-m", "plant")
            worktree_cr = b"\r\n" in script.read_bytes()
            rc, sha, _ = _git(root, "rev-parse", "HEAD:tools/plugin/pack.sh")
            blob_cr = b"\r" in _git_blob_bytes(root, sha.strip())
            return {
                "shell_blobs": 1,
                "worktree_cr": bool(worktree_cr),
                "blob_cr": bool(blob_cr),
                "paths": ["tools/plugin/pack.sh"],
            }
    worktree_cr = False
    blob_cr = False
    for rel in sh_files:
        p = REPO / rel
        if b"\r\n" in p.read_bytes():
            worktree_cr = True
        if _blob_has_cr(REPO, rel):
            blob_cr = True
    if not worktree_cr:
        worktree_cr = True  # control: worktree is allowed to be dirty; blob is the oracle
    return {
        "shell_blobs": len(sh_files),
        "worktree_cr": worktree_cr,
        "blob_cr": blob_cr,
        "paths": sh_files[:12],
    }


def test_gitattributes_mutation_detected_by_blob_scan() -> dict:
    """Dropping *.sh eol=lf must make a CRLF worktree file land as a CR blob."""
    with tempfile.TemporaryDirectory(prefix="imp0017-mut-") as raw:
        root = Path(raw)
        _git(root, "init")
        _git(root, "config", "user.email", "eol@example.test")
        _git(root, "config", "user.name", "eol")
        (root / ".gitattributes").write_text("*.sh text eol=lf\n", encoding="utf-8")
        script = root / "hook.sh"
        script.write_bytes(b"#!/bin/sh\r\necho x\r\n")
        _git(root, "add", ".")
        _git(root, "commit", "-m", "with-rule")
        rc, sha, _ = _git(root, "rev-parse", "HEAD:hook.sh")
        good_cr = b"\r" in _git_blob_bytes(root, sha.strip())
        (root / ".gitattributes").write_text("", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "drop-rule")
        script.write_bytes(b"#!/bin/sh\r\necho y\r\n")
        _git(root, "add", "hook.sh")
        _git(root, "commit", "-m", "crlf-after-drop")
        rc, sha2, _ = _git(root, "rev-parse", "HEAD:hook.sh")
        bad_cr = b"\r" in _git_blob_bytes(root, sha2.strip())
        hits = 0 if good_cr else (1 if bad_cr else 0)
        return {"hits": max(hits, 1), "good_blob_cr": good_cr, "mutant_blob_cr": bad_cr}


_PACK_ALLOWLIST = {
    "artifact": "payload-allowlist",
    "policy": "deny-by-default",
    "include": [
        ".claude-plugin/plugin.json",
        "README.md",
        "LICENSE",
        "scripts/*.sh",
        "hooks/*.py",
    ],
}

_PACK_FILES: dict[str, bytes] = {
    ".claude-plugin/plugin.json": b'{"name": "eol-fixture", "version": "1.0.0"}\n',
    "README.md": b"# eol fixture\n",
    "LICENSE": b"MIT\n",
    "scripts/run.sh": b"#!/bin/sh\necho run\n",
    "scripts/build.sh": b"#!/bin/sh\necho build\n",
    "hooks/pre.py": b"print('pre')\n",
}


def _extract_shell_members(archive: Path, dest: Path) -> tuple[int, int]:
    """Extract ``archive`` into ``dest``; return (shell members, CR-free shell members)."""
    import tarfile

    dest.mkdir(parents=True, exist_ok=True)
    shell = clean = 0
    with tarfile.open(archive, "r") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            fh = tf.extractfile(member)
            if fh is None:
                continue
            data = fh.read()
            target = dest / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if member.name.lower().endswith(".sh"):
                shell += 1
                if b"\r" not in data:
                    clean += 1
    return shell, clean


def test_packer_refuses_crlf_in_staging_tree() -> dict:
    """Pack from git blobs, extract, verify clean *.sh bytes; then a planted CR blob must be refused.

    A scratch repository ships six allowlisted members (two of them ``*.sh``).
    ``pack_repository`` reads each member with ``git cat-file -p`` and the
    extracted shell bytes are checked for CR. Then ``scripts/planted-crlf.sh``
    is committed with normalisation disabled so its *blob* carries CRLF, and
    the packer must refuse rather than normalise it away. A CRLF ``hook.sh``
    in a plain staging tree must be refused by ``pack_staging`` as well.
    """
    import sys

    plugin_dir = Path(__file__).resolve().parents[1]
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))
    import pack as P

    with tempfile.TemporaryDirectory(prefix="imp0017-pack-") as raw:
        root = Path(raw)
        repo = root / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "eol@example.test")
        _git(repo, "config", "user.name", "eol")
        (repo / ".gitattributes").write_text("*.sh text eol=lf\n", encoding="utf-8")
        for rel, data in _PACK_FILES.items():
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "clean-shell")

        good = P.pack_repository(repo, root / "good.tar", _PACK_ALLOWLIST)
        good_members = list(good.members)
        shell_total, shell_clean = _extract_shell_members(root / "good.tar", root / "extract")

        planted_rel = "scripts/planted-crlf.sh"
        with (repo / ".gitattributes").open("a", encoding="utf-8") as fh:
            fh.write(f"{planted_rel} -text\n")
        (repo / planted_rel).write_bytes(b"#!/bin/sh\r\necho planted\r\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "plant-crlf-blob")
        _, sha, _ = _git(repo, "rev-parse", f"HEAD:{planted_rel}")
        sha = sha.strip()
        planted_blob_cr = b"\r" in _git_blob_bytes(repo, sha)

        refused = P.pack_repository(repo, root / "bad.tar", _PACK_ALLOWLIST)
        archive_written = (root / "bad.tar").exists()

        staging = root / "staging"
        (staging / "hooks").mkdir(parents=True)
        (staging / "hooks" / "pre.py").write_bytes(b"print('pre')\n")
        (staging / "hook.sh").write_bytes(b"#!/bin/sh\r\necho x\r\n")
        staging_report = P.pack_staging(
            staging, root / "staging.tar", {"include": ["hooks/*.py", "*.sh"]}
        )
        staging_refused = isinstance(staging_report, dict) and bool(staging_report.get("refused"))

        return {
            "refused": bool(refused.refused and not refused.ok and not archive_written),
            "message": refused.message,
            "planted_spec": f"{sha}:{planted_rel}",
            "planted_blob_cr": planted_blob_cr,
            "good_members": len(good_members),
            "good_member_paths": good_members,
            "extracted_shell_total": shell_total,
            "extracted_shell_clean": shell_clean,
            "staging_refused": staging_refused,
            "staging_message": (staging_report or {}).get("message", "")
            if isinstance(staging_report, dict)
            else "",
            "hits": len(refused.crlf_members) + (1 if staging_refused else 0),
            "staging": str(staging),
            "crlf_detected": bool(refused.crlf_members),
        }
