#!/usr/bin/env python3
"""Read-only host-gate preflight for the cloud-container-security skill.

Reports which wrapped scanners are present on PATH so the operator knows which
lanes are usable before running anything against OWNER cloud. It NEVER runs a
scanner, touches a cloud account, opens a network socket, or spawns a
subprocess -- it only consults ``shutil.which``. Fail-open: it always exits 0;
a missing tool is reported, never enforced.
"""

from __future__ import annotations

import argparse
import shutil
from collections.abc import Callable, Iterable, Mapping

WhichFn = Callable[[str], str | None]

# tool -> one-line purpose + license (owner-cloud / authorized-estate only).
TOOLS: dict[str, str] = {
    "prowler": "multi-cloud + K8s CSPM (AWS/Azure/GCP/M365/K8s), Apache-2.0",
    "trivy": "image/fs/repo/IaC/K8s/SBOM/secret scan; `trivy mcp` plugin, Apache-2.0",
    "kubescape": "K8s posture vs NSA/CIS/MITRE, Apache-2.0",
    "steampipe": "SQL posture queries over cloud APIs, AGPL-3.0 (wrap)",
    "powerpipe": "compliance benchmarks over Steampipe, AGPL-3.0 (wrap)",
    "cloudfox": "non-destructive attack-path enumeration on owner cloud, MIT",
    "trufflehog": "verified-secret scanning (--only-verified), AGPL-3.0 (wrap)",
    "syft": "SBOM generation (feeds Trivy/grype/cve-mcp), Apache-2.0",
}


def check_tools(
    tools: Iterable[str] | None = None,
    which: WhichFn = shutil.which,
) -> dict[str, str | None]:
    """Return a {tool: path-or-None} map using ``which`` (injectable for tests)."""
    names = list(tools) if tools is not None else list(TOOLS)
    return {name: which(name) for name in names}


def format_report(results: Mapping[str, str | None]) -> str:
    """Render a human-readable presence report; absence is informational only."""
    lines = ["cloud-container-security preflight (read-only host-gate)", ""]
    present = 0
    for name, path in results.items():
        if path:
            present += 1
        mark = "ok" if path else "--"
        location = path if path else "not on PATH"
        lines.append(f"[{mark}] {name:<11} {location}")
        purpose = TOOLS.get(name)
        if purpose:
            lines.append(f"        {purpose}")
    lines.append("")
    lines.append(
        f"{present}/{len(results)} tools present. "
        "Absent tools are host-gated: install per SKILL.md, owner cloud only."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None, which: WhichFn = shutil.which) -> int:
    parser = argparse.ArgumentParser(
        description="Host-gate preflight for cloud-container-security (read-only).",
    )
    parser.add_argument(
        "--tools",
        nargs="*",
        default=None,
        help="Subset of tools to check (default: all).",
    )
    args = parser.parse_args(argv)
    results = check_tools(args.tools, which=which)
    print(format_report(results))
    return 0  # fail-open: never block on a missing tool


if __name__ == "__main__":
    raise SystemExit(main())
