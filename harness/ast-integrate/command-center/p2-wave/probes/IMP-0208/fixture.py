"""Certified-workflow fixture used by IMP-0208 probes.

The tree is a VALID certified workflow (IMP-0203-shaped record) plus the
:10842 junk classes sitting next to it, so packing is measured against a
hostile source rather than a pre-cleaned staging directory.
"""
from __future__ import annotations

import json
from pathlib import Path

# AWS documentation example — detector fodder, never a live secret.
_AWS_DOC_EXAMPLE_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def _write(path: Path, body: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(body, bytes):
        path.write_bytes(body)
    else:
        path.write_text(body, encoding="utf-8")


def workflow_doc() -> dict:
    return {
        "id": "wf.catalog-class.publication-demo",
        "namespace": "ast.workflow",
        "name": "publication-demo",
        "version": "1.4.2",
        "licence": {"spdx": "MIT"},
        "permissions": {
            "tools": ["Read", "Grep"],
            "network": False,
            "source_policy": "repo-local",
        },
        "certification": {
            "status": "VALID",
            "corpus_version": "corpus-2026.08",
            "spec_version": "wf/1.4.2",
            "tier": "B",
            "confirmer": "IMP-0203-fixture",
            "evidence_anchor": "benchmarks.json",
        },
    }


def build_certified_tree(root: Path, *, plant_source_junk: bool = True) -> Path:
    """Materialise a certified workflow tree under root. Returns root."""
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "workflow.json", json.dumps(workflow_doc(), indent=2) + "\n")
    _write(root / "LICENSE", "MIT License\nCopyright (c) 2026 fixture\n")
    _write(root / "README.md", "# publication-demo\nCertified workflow fixture for IMP-0208.\n")
    _write(
        root / "provenance.json",
        json.dumps(
            {
                "generator": "imp-0208-fixture",
                "certified_by": "IMP-0203-fixture",
                "git_commit": "0" * 40,
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        root / "sbom.json",
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "components": [
                    {
                        "type": "application",
                        "name": "wf.catalog-class.publication-demo",
                        "version": "1.4.2",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        root / "benchmarks.json",
        json.dumps(
            {
                "suite": "held-out-catalog-class",
                "beats_baseline": True,
                "delta": 0.12,
                "n": 40,
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        root / "lineage.json",
        json.dumps(
            {
                "parents": ["wf.catalog-class.v1"],
                "derived_from": "IMP-0203",
                "channel": "certified",
            },
            indent=2,
        )
        + "\n",
    )
    _write(root / "permissions.json", json.dumps({"tools": ["Read", "Grep"], "network": False}) + "\n")
    _write(root / "skills/skill.pack/SKILL.md", "# pack skill\nFixture skill body.\n")
    _write(root / "docs/overview.md", "# overview\nPayload contents.\n")
    _write(
        root / "workflows/wf.catalog-class.json",
        json.dumps({"id": "wf.catalog-class.publication-demo", "steps": ["discover"]}, indent=2)
        + "\n",
    )

    if plant_source_junk:
        _write(root / ".git/config", "[core]\nrepositoryformatversion = 0\n")
        _write(root / ".git/HEAD", "ref: refs/heads/main\n")
        _write(root / "__pycache__/mod.cpython-312.pyc", b"\x00PYC")
        _write(root / ".cache/data.bin", b"\x00CACHE")
        _write(root / "transcripts/session.transcript", "agent transcript must not ship\n")
        _write(
            root / ".env",
            f"AWS_SECRET_ACCESS_KEY={_AWS_DOC_EXAMPLE_SECRET}\n",
        )
        _write(root / "secrets.json", json.dumps({"token": "fixture-not-for-packing"}) + "\n")
        _write(root / "notes.log", "log file must not ship\n")
    return root


def planted_junk_members() -> dict[str, bytes]:
    """Members a buggy packer would stuff into the archive. Used by probe 2."""
    return {
        ".git/config": b"[core]\nrepositoryformatversion = 0\n",
        "__pycache__/x.pyc": b"\x00PYC",
        "transcripts/pwned.transcript": b"planted transcript\n",
        ".env": f"AWS_SECRET_ACCESS_KEY={_AWS_DOC_EXAMPLE_SECRET}\n".encode("ascii"),
    }
