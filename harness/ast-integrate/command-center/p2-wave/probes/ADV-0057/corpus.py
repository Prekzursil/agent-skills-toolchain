"""Live inventory of policy documents and contribution-flow machinery."""
from __future__ import annotations

from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

POLICY_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "CONTRIBUTING",
        "role": "contribution-terms",
        "candidates": (
            "CONTRIBUTING.md",
            "CONTRIBUTING.rst",
            "CONTRIBUTING.txt",
            "docs/CONTRIBUTING.md",
            ".github/CONTRIBUTING.md",
        ),
    },
    {
        "id": "GOVERNANCE",
        "role": "governance-model",
        "candidates": (
            "GOVERNANCE.md",
            "docs/GOVERNANCE.md",
            ".github/GOVERNANCE.md",
        ),
    },
    {
        "id": "SECURITY",
        "role": "security-policy",
        "candidates": (
            "SECURITY.md",
            "docs/SECURITY.md",
            ".github/SECURITY.md",
            "security/policy.md",
        ),
    },
    {
        "id": "SUPPORT",
        "role": "support-policy",
        "candidates": (
            "SUPPORT.md",
            "docs/SUPPORT.md",
            ".github/SUPPORT.md",
        ),
    },
    {
        "id": "DEPRECATION",
        "role": "deprecation-policy",
        "candidates": (
            "DEPRECATION.md",
            "DEPRECATION.md",
            "docs/DEPRECATION.md",
            "docs/deprecation.md",
        ),
    },
    {
        "id": "OUTBOUND-LICENSE",
        "role": "outbound-license",
        "candidates": (
            "LICENSE",
            "LICENSE.md",
            "LICENSE.txt",
            "COPYING",
            "COPYING.md",
            "NOTICE",
        ),
    },
    {
        "id": "MARKETPLACE-PUBLISHER-TERMS",
        "role": "marketplace-publisher-terms",
        "candidates": (
            "PUBLISHER-TERMS.md",
            "MARKETPLACE-TERMS.md",
            "docs/publisher-terms.md",
            "docs/marketplace-terms.md",
            "tools/marketplace/PUBLISHER-TERMS.md",
            "tools/marketplace/terms.md",
        ),
    },
)

FLOW_CANDIDATES: tuple[str, ...] = (
    ".github/pull_request_template.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "docs/pull_request_template.md",
    "CODEOWNERS",
    ".github/CODEOWNERS",
    "dco.yml",
    ".github/dco.yml",
    "cla.yml",
    ".cla.yml",
    ".github/cla.yml",
    "cla.json",
)

SKIP_PARTS = frozenset(
    {
        "node_modules",
        "__pycache__",
        "planted-contradiction",
        "planted-clean",
    }
)


def rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def skipped(path: Path) -> bool:
    """Skip probe fixtures and VCS dirs without treating `.github` as `.git`."""
    posix = rel(path)
    if "p2-wave/probes" in posix:
        return True
    parts = posix.split("/")
    if any(p == ".git" for p in parts):
        return True
    return any(p in SKIP_PARTS for p in parts)


def first_existing(candidates: tuple[str, ...]) -> dict[str, Any]:
    for cand in candidates:
        path = REPO / cand
        if path.is_file() and not skipped(path):
            text = path.read_text(encoding="utf-8", errors="replace")
            return {
                "present": True,
                "path": cand.replace("\\", "/"),
                "bytes": len(text.encode("utf-8")),
                "text": text,
                "lines": text.splitlines(),
            }
    return {
        "present": False,
        "path": candidates[0].replace("\\", "/"),
        "bytes": 0,
        "text": "",
        "lines": [],
        "candidates_checked": list(candidates),
    }


def inventory() -> dict[str, Any]:
    docs: list[dict[str, Any]] = []
    for spec in POLICY_SPECS:
        hit = first_existing(spec["candidates"])
        docs.append(
            {
                "id": spec["id"],
                "role": spec["role"],
                **hit,
            }
        )
    flow = []
    for cand in FLOW_CANDIDATES:
        path = REPO / cand
        flow.append(
            {
                "path": cand,
                "present": path.is_file() and not skipped(path),
            }
        )
    github = REPO / ".github"
    workflows: list[str] = []
    if github.is_dir():
        for p in sorted(github.rglob("*")):
            if p.is_file() and not skipped(p):
                workflows.append(rel(p))
    plugin = REPO / ".claude-plugin" / "plugin.json"
    plugin_rec: dict[str, Any] = {"present": plugin.is_file(), "path": ".claude-plugin/plugin.json"}
    if plugin.is_file():
        plugin_rec["text"] = plugin.read_text(encoding="utf-8", errors="replace")
        plugin_rec["lines"] = plugin_rec["text"].splitlines()
        plugin_rec["bytes"] = len(plugin_rec["text"].encode("utf-8"))
    return {
        "repo": str(REPO),
        "documents": docs,
        "contribution_flow_files": flow,
        "github_tree": workflows,
        "github_dir_present": github.is_dir(),
        "plugin_manifest": plugin_rec,
        "ci_dir_present": (REPO / "ci").is_dir(),
        "hooks_dir_present": (REPO / "hooks").is_dir(),
    }
