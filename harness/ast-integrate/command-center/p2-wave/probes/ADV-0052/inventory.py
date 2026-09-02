"""Published / proposed marketplace listing identity visible on this worktree."""
from __future__ import annotations

from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _read(rel: str) -> str | None:
    path = REPO / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def listing_targets() -> list[dict[str, Any]]:
    """Every name, display name, description and icon this unit enumerates."""
    agentspec = _read("tools/agentspec-js/package.json")
    handoff = _read("tools/marketplace/schema/install-handoff.schema.json")
    aud_manifest = REPO / "command-center/p2-wave/probes/AUD-0021/probe1-manifests.json"
    aud_yaml = REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
    return [
        {
            "id": "T-NAME-agent-skills-toolchain",
            "kind": "package-name",
            "value": "agent-skills-toolchain",
            "display_name": None,
            "on_disk": (REPO / "package.json").is_file(),
            "sources": [
                "command-center/p2-wave/probes/AUD-0021/probe1-manifests.json:package.json name",
                "WORK-UNIT-CATALOG.json IMP-0069: 'agent-skills-toolchain' (the real existing name)",
            ],
            "source_present": aud_manifest.is_file(),
        },
        {
            "id": "T-NAME-agent-skills-toolchain-release",
            "kind": "package-name",
            "value": "@prekzursil/agent-skills-toolchain-release",
            "display_name": None,
            "on_disk": (REPO / "release/package.json").is_file(),
            "sources": [
                "command-center/p2-wave/probes/AUD-0021/probe1-manifests.json:release/package.json"
            ],
            "source_present": aud_manifest.is_file(),
        },
        {
            "id": "T-NAME-agentspec-js",
            "kind": "package-name",
            "value": "@prekzursil/agentspec-js",
            "display_name": None,
            "on_disk": True,
            "sources": ["tools/agentspec-js/package.json"],
            "source_present": agentspec is not None,
        },
        {
            "id": "T-NAME-ast-integrate-platform",
            "kind": "package-name",
            "value": "ast-integrate-platform",
            "display_name": None,
            "on_disk": False,
            "sources": [
                "command-center/p2-wave/probes/AUD-0085/_extract2_out.json dist zip name"
            ],
            "source_present": (
                REPO / "command-center/p2-wave/probes/AUD-0085/_extract2_out.json"
            ).is_file(),
        },
        {
            "id": "T-DESC-agentspec-js",
            "kind": "description",
            "value": "@prekzursil/agentspec-js",
            "text": (
                "JS port of agentspec Phase-7 spec types with set-equality parity vs Python"
            ),
            "on_disk": True,
            "sources": ["tools/agentspec-js/package.json"],
            "source_present": agentspec is not None,
        },
        {
            "id": "T-DESC-marketplace-handoff",
            "kind": "description",
            "value": "marketplace-install-handoff",
            "text": (
                "Single typed interface: marketplace hands a verified blob "
                "to the plugin installer. File placement happens only on the "
                "installer side of this object."
            ),
            "on_disk": True,
            "sources": ["tools/marketplace/schema/install-handoff.schema.json"],
            "source_present": handoff is not None,
        },
        {
            "id": "T-DESC-agent-skills-toolchain-runner",
            "kind": "description",
            "value": "agent-skills-toolchain",
            "text": (
                "Opened by the **codex-runner** (agent-skills-toolchain) — "
                "autonomous, propose-only."
            ),
            "on_disk": aud_yaml.is_file(),
            "sources": [
                "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
            ],
            "source_present": aud_yaml.is_file(),
        },
        {
            "id": "T-ICON-marketplace-listing",
            "kind": "icon",
            "value": None,
            "text": None,
            "on_disk": False,
            "sources": [
                "glob of listing icon paths on this worktree returned no file"
            ],
            "source_present": True,
        },
        {
            "id": "T-POLICY-naming-impersonation",
            "kind": "policy",
            "value": "marketplace-naming-and-impersonation-policy",
            "text": None,
            "on_disk": False,
            "sources": [
                "catalog ADV-0052 input: the marketplace's own naming and impersonation policy",
                "IMP-0069 defines package-name grammar, not impersonation copy",
            ],
            "source_present": False,
        },
    ]


def names_to_search() -> list[str]:
    names = []
    for t in listing_targets():
        if t["kind"] == "package-name" and t.get("value"):
            names.append(str(t["value"]))
    return names
