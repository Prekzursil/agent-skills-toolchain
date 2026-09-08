#!/usr/bin/env python3
"""IMP-0017 negative control: plant CRLF shell blob; packer must refuse."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import pack as pack_mod  # noqa: E402

PROBE = Path(__file__).resolve().parent
WORK = PROBE / "work" / "negative"
RAW = PROBE / "negative-control.raw.txt"
MEAS = PROBE / "negative-control-measurement.json"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    repo = WORK / "crlf-payload"
    if repo.exists():
        shutil.rmtree(repo)
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "imp0017-neg@test.invalid")
    _git(repo, "config", "user.name", "IMP-0017-neg")
    _git(repo, "config", "core.autocrlf", "false")
    (repo / "bin").mkdir()
    crlf = b"#!/usr/bin/env bash\r\necho planted-crlf\r\n"
    digest = (
        subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=repo,
            input=crlf,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    subprocess.run(
        [
            "git",
            "update-index",
            "--add",
            "--cacheinfo",
            f"100755,{digest},bin/planted.sh",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "LICENSE").write_bytes(b"MIT\n")
    (repo / ".gitattributes").write_text(
        "*.sh eol=lf\n*.ps1 eol=lf\n*.py eol=lf\n*.md eol=lf\n", encoding="utf-8"
    )
    allow = {
        "artifact": "payload-allowlist",
        "policy": "deny-by-default",
        "rules": [
            {"glob": "bin/*.sh", "reason": "shell"},
            {"glob": "LICENSE", "reason": "license"},
        ],
        "budget": {"max_bytes": 100_000, "max_files": 20},
        "forbidden_classes": {"vcs": [".git", ".git/*"]},
    }
    (repo / "payload-allowlist.json").write_text(
        json.dumps(allow, indent=2) + "\n", encoding="utf-8"
    )
    _git(repo, "add", "LICENSE", ".gitattributes", "payload-allowlist.json")
    _git(repo, "commit", "-m", "plant-crlf-shell")

    blob = pack_mod.git_cat_file(repo, "HEAD", "bin/planted.sh")
    blob_has_cr = b"\x0d" in blob
    cr_count = blob.count(b"\x0d")
    out = WORK / "should-fail.zip"
    refused = False
    err_text = ""
    try:
        pack_mod.pack(
            repo=repo,
            rev="HEAD",
            allowlist=repo / "payload-allowlist.json",
            out=out,
        )
    except pack_mod.PackError as exc:
        refused = True
        err_text = str(exc)

    fired = (
        refused
        and blob_has_cr
        and ("CR" in err_text or "cr=" in err_text.lower())
        and not out.is_file()
    )
    lines = [
        "NEGATIVE CONTROL: CRLF SHELL BLOB MUST BE REFUSED BY PACKER",
        "NEG-BEGIN:IMP-0017",
        f"blob_has_cr={blob_has_cr}",
        f"blob_cr_count={cr_count}",
        f"packer_refused={refused}",
        f"error={err_text}",
        f"archive_exists={out.is_file()}",
        f"negative_control_fired={fired}",
        "NEG-COMPLETE:IMP-0017",
        "SUCCESS:IMP-0017-negative" if fired else "FAILED:IMP-0017-negative",
    ]
    meas = {
        "blob_has_cr": blob_has_cr,
        "blob_cr_count": cr_count,
        "packer_refused": refused,
        "error": err_text,
        "archive_exists": out.is_file(),
        "negative_control_fired": fired,
    }
    MEAS.write_text(json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raw = "\n".join(lines) + "\n"
    RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if fired else 1


if __name__ == "__main__":
    raise SystemExit(main())
