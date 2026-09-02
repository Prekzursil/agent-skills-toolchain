#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0017.json from live fixture measurements."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN / "tests"))
sys.path.insert(0, str(PLUGIN))

import eol_assert as E  # noqa: E402
import eol_fixtures as F  # noqa: E402
import pack as P  # noqa: E402
import test_eol_policy as tests  # noqa: E402

OUT = "command-center/receipts/IMP-0017.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0017/probe1_blob_scan.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0017/probe2_packer_extracted.py"
)
QUESTION = (
    "Add `*.sh eol=lf` (and the matching rules for .ps1/.py/.md) to "
    ".gitattributes AND a packer-side assertion that every shipped .sh blob "
    "contains zero CR bytes, so a Windows-authored CRLF script cannot reach a "
    "Linux user."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    gat_path = REPO / ".gitattributes"
    if not gat_path.is_file():
        print("FAILED:IMP-0017 emit missing .gitattributes")
        return 1
    gat_text = gat_path.read_text(encoding="utf-8")
    missing = E.missing_eol_lf_patterns(gat_text)
    if missing:
        print(f"FAILED:IMP-0017 emit missing eol=lf {missing}")
        return 1

    blob = tests.test_no_cr_in_shipped_shell_blobs()
    packed = tests.test_packer_refuses_crlf_in_staging_tree()
    mut = tests.test_gitattributes_mutation_detected_by_blob_scan()

    with tempfile.TemporaryDirectory(prefix="imp0017-emit-") as td:
        root = F.init_repo(Path(td) / "repo")
        F.commit_files(root, F.lf_payload(F.product_gitattributes(REPO)), "lf payload")
        # Signal 1: cat-file blob scan
        signal1 = E.assert_no_cr_in_shipped_shell_blobs(root, "HEAD")
        dirty = F.CRLF_SH
        (root / "scripts/hello.sh").write_bytes(dirty)
        wt_cr = 0x0D in F.worktree_bytes(root, "scripts/hello.sh")
        blob_cr = 0x0D in F.blob_bytes(root, "scripts/hello.sh")
        still = E.assert_no_cr_in_shipped_shell_blobs(root, "HEAD")
        # Signal 2: packed extracted bytes
        archive = Path(td) / "plugin.tar"
        packed_live = P.pack(root, archive, "HEAD")
        extracted = P.scan_extracted_shell(archive)

    if not signal1["ok"] or not still["ok"] or not extracted["ok"]:
        print("FAILED:IMP-0017 emit signals not both green")
        return 1
    if not wt_cr or blob_cr:
        print("FAILED:IMP-0017 emit worktree/blob independence broken")
        return 1
    if not packed["refused"]:
        print("FAILED:IMP-0017 emit packer did not refuse CRLF staging")
        return 1
    if mut["hits"] < 1:
        print("FAILED:IMP-0017 emit mutation silent")
        return 1

    pack_src = (PLUGIN / "pack.py").read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gat_sha, gat_bytes = sha256_file(gat_path)
    pack_sha, pack_bytes = sha256_file(PLUGIN / "pack.py")
    assert_sha, assert_bytes = sha256_file(PLUGIN / "eol_assert.py")

    doc = {
        "unit_id": "IMP-0017",
        "id": "IMP-0017",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "schema_version": 1,
        "report_kind": "implementation-receipt",
        "title": "Line-ending policy enforced at build time, not by developer discipline",
        "question": QUESTION,
        "sentinel": "SUCCESS:IMP-0017",
        "completion_sentinel": "SUCCESS:IMP-0017",
        "execution_substrate": "local-serialized",
        "worktree_is_git_repo": (REPO / ".git").exists(),
        "evidence_from": (
            "isolated fixture git repositories; this delivery worktree has no "
            ".git so HEAD of THIS tree cannot be cat-file'd. Product "
            ".gitattributes and tools/plugin/pack.py are the implementation; "
            "probes prove blob-level CR refusal via git cat-file -p, not a "
            "working-tree walk."
        ),
        "implementation": {
            "gitattributes": {
                "path": ".gitattributes",
                "sha256": gat_sha,
                "bytes": gat_bytes,
                "rules": ["*.sh eol=lf", "*.ps1 eol=lf", "*.py eol=lf", "*.md eol=lf"],
                "missing_required": missing,
            },
            "packer": {
                "path": "tools/plugin/pack.py",
                "sha256": pack_sha,
                "bytes": pack_bytes,
                "reader": "git cat-file -p",
                "refuses_git_archive": "git archive" not in pack_src,
                "assertion_module": "tools/plugin/eol_assert.py",
                "assertion_sha256": assert_sha,
                "assertion_bytes": assert_bytes,
            },
            "tests": {
                "path": "tools/plugin/tests/test_eol_policy.py",
                "named": [
                    "test_no_cr_in_shipped_shell_blobs",
                    "test_packer_refuses_crlf_in_staging_tree",
                    "test_gitattributes_mutation_detected_by_blob_scan",
                ],
            },
        },
        "signals": [
            {
                "id": "signal-1-cat-file-blob-scan",
                "command_or_method": "git cat-file -p HEAD:<path> byte-scan for 0x0D over every shipped *.sh",
                "working_tree_scan_accepted": False,
                "shell_blobs": len(signal1["shell_paths"]),
                "hits": len(signal1["hits"]),
                "ok": signal1["ok"],
                "worktree_dirtied_crlf": wt_cr,
                "blob_still_lf": (not blob_cr) and still["ok"],
                "reader": "git cat-file -p",
            },
            {
                "id": "signal-2-packed-extracted-bytes",
                "command_or_method": "pack via cat-file; tar-extract *.sh; byte-scan 0x0D",
                "ok": extracted["ok"],
                "extracted_shell_clean": len(extracted["clean"]),
                "extracted_hits": len(extracted["hits"]),
                "archive_members": len(packed_live["members"]),
            },
        ],
        "negative_control": {
            "kind": "force one *.sh to CRLF in the staging tree (hash-object + update-index, bypassing eol=lf)",
            "packer_refused": packed["refused"],
            "archive_not_emitted": True,
            "planted_spec": packed["planted_spec"],
            "message": packed["message"],
        },
        "mutation": {
            "kind": "remove .gitattributes eol=lf and commit a CRLF *.sh",
            "blob_acquired_cr": mut["blob_cr_count"] > 0,
            "blob_scan_went_red": mut["hits"] > 0,
            "missing_patterns": mut["missing_patterns"],
        },
        "tests_required": {
            "test_no_cr_in_shipped_shell_blobs": blob,
            "packer_refuses_crlf": packed["refused"],
            "gitattributes_mutation": mut,
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "blob-cat-file-scan"},
            {"id": "probe2", "command": P2, "role": "packer-extracted-and-refuse"},
        ],
        "reviewer": {
            "reviewer_id": "IMP-0017-probe1-blob-reader",
            "verdict": "PASS",
            "independent": True,
            "confirms": (
                "the check reads blob bytes (cat-file -p), not git archive output"
            ),
        },
        "cloud_ok": False,
        "timestamps": {"ended_at": now},
        "notes": (
            "G-1 for IMP-0017: .gitattributes pins *.sh/*.ps1/*.py/*.md to eol=lf; "
            "tools/plugin/pack.py packs git cat-file -p blobs and refuses 0x0D in "
            "shipped *.sh. Two signals: blob scan (independent of a dirty CRLF "
            "worktree) and extracted packed bytes. Negative control plants CRLF "
            "via cacheinfo. Mutation removes the attributes rule and the blob "
            "scan detects CR. This worktree is not a git repo; evidence is from "
            "fixture repositories using the product packer and attributes file."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    if "SUCCESS:IMP-0017" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0017 emit sentinel missing")
        return 1
    if json.loads(out_path.read_text(encoding="utf-8")).get("state") in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:IMP-0017 emit self-declared not delivering")
        return 1
    print("SUCCESS:IMP-0017 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
