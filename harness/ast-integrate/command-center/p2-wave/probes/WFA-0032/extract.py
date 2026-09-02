"""Materialize 284-candidate corpus and dual-route provenance extract."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from corpus import (
    ANCHOR_LINE,
    N_EXPECTED,
    PLANT_FS_ONLY,
    PLANT_GIT_ONLY,
    WRONG_LINE,
    candidates,
)
from deref import (
    combine_routes,
    deref_filesystem,
    deref_git_blob,
    git_blob_sha1,
    line_at,
    sha256_bytes,
    write_loose_blob,
)

REPO = HERE.parents[3]
CORPUS_DIR = HERE / "fixtures" / "corpus"
GIT_DIR = HERE / "fixtures" / "objects.git"
REL_CORPUS = "command-center/p2-wave/probes/WFA-0032/fixtures/corpus"
REL_GIT = "command-center/p2-wave/probes/WFA-0032/fixtures/objects.git"


def _init_git_dir() -> None:
    GIT_DIR.mkdir(parents=True, exist_ok=True)
    (GIT_DIR / "objects").mkdir(parents=True, exist_ok=True)
    (GIT_DIR / "config").write_text(
        "[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = true\n",
        encoding="utf-8",
        newline="\n",
    )
    (GIT_DIR / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8", newline="\n")


def materialize() -> list[dict[str, Any]]:
    _init_git_dir()
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for spec in candidates():
        rel = f"{REL_CORPUS}/{spec['id']}.txt"
        path = REPO / rel
        body = spec["body"]
        data = body.encode("utf-8")
        blob_sha = git_blob_sha1(data)
        if spec["plant"] != "git-only":
            path.write_text(body, encoding="utf-8", newline="\n")
        elif path.exists():
            path.unlink()
        if spec["plant"] != "fs-only":
            write_loose_blob(GIT_DIR, data)
        rows.append(
            {
                **spec,
                "relpath": rel,
                "git_blob_sha1": None if spec["plant"] == "fs-only" else blob_sha,
            }
        )
    return rows


def extract_one(row: dict[str, Any]) -> dict[str, Any]:
    path = REPO / row["relpath"]
    line_no = int(row["anchor_line"])
    fs = deref_filesystem(path, line_no)
    git = deref_git_blob(GIT_DIR, row.get("git_blob_sha1") or "", line_no)
    combined = combine_routes(fs, git)
    return {
        "candidate_id": row["id"],
        "family": row["family"],
        "origin": row["origin"],
        "plant": row["plant"],
        "anchor": {
            "form": "path+line + git-blob-sha1",
            "path": row["relpath"],
            "line": line_no,
            "git_blob_sha1": row.get("git_blob_sha1"),
            "git_dir": REL_GIT,
        },
        **combined,
    }


def wrong_line_control(rows: list[dict[str, Any]]) -> dict[str, Any]:
    target = next(r for r in rows if r.get("plant") is None)
    path = REPO / target["relpath"]
    text = path.read_text(encoding="utf-8")
    good = line_at(text, ANCHOR_LINE)
    bad = line_at(text, WRONG_LINE)
    good_h = sha256_bytes(good.encode("utf-8"))
    bad_h = sha256_bytes(bad.encode("utf-8"))
    caught = good_h != bad_h
    if not caught:
        raise RuntimeError("wrong-line plant is not distinguishable by hash")
    return {
        "candidate_id": target["id"],
        "correct_line": ANCHOR_LINE,
        "wrong_line": WRONG_LINE,
        "correct_line_sha256": good_h,
        "wrong_line_sha256": bad_h,
        "caught": True,
        "rule": (
            "A deliberately wrong line number must not match the stored "
            "anchor-line content hash."
        ),
    }


def run_extract() -> dict[str, Any]:
    specs = materialize()
    records = [extract_one(s) for s in specs]
    if len(records) != N_EXPECTED:
        raise RuntimeError(f"extract produced {len(records)} != {N_EXPECTED}")
    unresolved = [r for r in records if r["status"] != "RESOLVED"]
    plants = {r["candidate_id"]: r for r in records if r["plant"]}
    fs_only = plants.get(PLANT_FS_ONLY)
    git_only = plants.get(PLANT_GIT_ONLY)
    if fs_only is None or git_only is None:
        raise RuntimeError("detector plants missing from extract")
    if fs_only["status"] != "UNRESOLVED" or "git-blob" not in (fs_only.get("failing_route") or ""):
        raise RuntimeError(f"fs-only plant not UNRESOLVED via git-blob: {fs_only}")
    if git_only["status"] != "UNRESOLVED" or "filesystem" not in (
        git_only.get("failing_route") or ""
    ):
        raise RuntimeError(f"git-only plant not UNRESOLVED via filesystem: {git_only}")
    silent = [
        r
        for r in unresolved
        if not r.get("failing_route")
    ]
    if silent:
        raise RuntimeError(f"UNRESOLVED without failing_route: {silent[:3]}")
    fam = {}
    for r in records:
        fam[r["family"]] = fam.get(r["family"], 0) + 1
    control = wrong_line_control(specs)
    payload = {
        "n": len(records),
        "n_resolved": sum(1 for r in records if r["status"] == "RESOLVED"),
        "n_unresolved": len(unresolved),
        "family_counts": fam,
        "records": records,
        "wrong_line_control": control,
        "corpus_dir": REL_CORPUS,
        "git_dir": REL_GIT,
    }
    blob = repr(sorted((r["candidate_id"], r["status"], r.get("content_sha256")) for r in records)).encode()
    payload["extract_fingerprint"] = hashlib.sha256(blob).hexdigest()
    return payload
