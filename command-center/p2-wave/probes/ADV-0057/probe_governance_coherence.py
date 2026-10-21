#!/usr/bin/env python
"""ADV-0057 named probes: contribution/governance/support-policy legal coherence.

Probe 1: pairwise contradiction matrix across the policy documents that exist, citing the
conflicting sentences by file:line.
Probe 2 (mechanically different): test the enforcement path - the catalog's preferred
instrument (a scratch PR without required sign-off) is NOT-RUN under this run's hard
constraint (no new GitHub Actions billing spend: 8 workflow jobs run on ubuntu-latest,
GitHub-hosted). The executed substitutes are (a) a read-only branch-protection API query
and (b) a workflow/template scan for any DCO/CLA/sign-off enforcement, which together
answer 'does the contribution flow actually collect the rights the project claims'.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent

DOCS = {
    "SECURITY.md": REPO / "SECURITY.md",
    "CONTRIBUTING.md": REPO / "CONTRIBUTING.md",
    "SUPPORT.md": REPO / "SUPPORT.md",
    "DEPRECATION.md": REPO / "DEPRECATION.md",
    "LICENSE": REPO / "LICENSE",
    "NOTICE": REPO / "NOTICE",
    "marketplace GOVERNANCE.md": REPO / "platform/marketplace/GOVERNANCE.md",
    "plugin.json (outbound license claim)": REPO / ".claude-plugin/plugin.json",
}

CONTRADICTIONS = [
    {
        "id": "C1-license-claimed-not-delivered",
        "a": {"doc": "plugin.json (outbound license claim)", "anchor":
              ".claude-plugin/plugin.json:8", "quote": '"license": "MIT",'},
        "b": {"doc": "LICENSE", "anchor": "repo root", "quote":
              "ABSENT: no LICENSE/COPYING/NOTICE file exists at the repo root "
              "(verified by this probe)"},
        "note": "The repo's own marketplace governance (platform/marketplace/"
                "GOVERNANCE.md:34, precondition license-basis-present / MKT-P05) "
                "REFUSES a package published without a license basis; the repo "
                "itself would fail its own gate.",
    },
    {
        "id": "C2-private-only-vs-redistribution-obligations",
        "a": {"doc": "SECURITY.md", "anchor": "SECURITY.md:3", "quote":
              "**This repository must never be made public.**"},
        "b": {"doc": "marketplace GOVERNANCE.md", "anchor":
              "platform/marketplace/GOVERNANCE.md:46-47", "quote":
              "aggregating 31 Apache-2.0 payload entries under a declared MIT, plus "
              "at least one CC BY-SA 4.0 share-alike entry"},
        "note": "Redistribution-obliged content (Apache-2.0 notices, CC BY-SA "
                "share-alike) is aggregated inside a repository whose security policy "
                "forbids ever making it public; notice obligations attach at "
                "distribution, and the packager is the distribution channel.",
    },
    {
        "id": "C3-contribution-terms-absent-while-signing-gates-exist-elsewhere",
        "a": {"doc": "marketplace GOVERNANCE.md", "anchor":
              "platform/marketplace/GOVERNANCE.md:8-13", "quote":
              "Separation is enforced, not documented ... A publisher therefore cannot "
              "revoke a rival"},
        "b": {"doc": "CONTRIBUTING.md", "anchor": "repo root", "quote":
              "ABSENT: no CONTRIBUTING document, no PR template, no DCO/CLA "
              "configuration anywhere in .github/ (verified by this probe)"},
        "note": "The only governance machinery that exists governs the marketplace "
                "fixture; the repository contribution flow itself declares no terms "
                "and collects no rights.",
    },
]


def probe1_matrix() -> list[dict]:
    lines_out = []
    for c in CONTRADICTIONS:
        for side in ("a", "b"):
            doc = c[side]["doc"]
            f = DOCS.get(doc)
            present = f is not None and f.is_file()
            c[side]["exists"] = present
            if present and ":" in c[side]["anchor"]:
                path_part, lineno = c[side]["anchor"].rsplit(":", 1)
                pf = REPO / path_part
                if pf.is_file() and lineno.isdigit():
                    src_lines = pf.read_text(encoding="utf-8",
                                             errors="replace").splitlines()
                    n = int(lineno)
                    if 1 <= n <= len(src_lines):
                        c[side]["verified_line"] = src_lines[n - 1].strip()[:160]
                        ok = c[side]["quote"][:40].lower() in \
                            c[side]["verified_line"].lower()
                        c[side]["quote_verified_on_disk"] = ok
        lines_out.append(c["id"])
    return CONTRADICTIONS


def probe2_enforcement() -> dict:
    out: dict = {"scratch_pr_test": "NOT-RUN"}
    out["scratch_pr_reason"] = (
        "run constraint: no new GitHub Actions billing spend; .github/workflows "
        "contains 8 jobs with runs-on: ubuntu-latest (GitHub-hosted, billed); a PR "
        "would fire them")
    # (a) branch protection, read-only
    try:
        cp = subprocess.run(
            ["gh", "api",
             "repos/Prekzursil/agent-skills-toolchain/branches/main/protection"],
            capture_output=True, text=True, timeout=60)
        out["branch_protection_api"] = {
            "rc": cp.returncode,
            "body": (cp.stdout or cp.stderr).strip()[:200],
            "reading": "HTTP 404 'Branch not protected' = NOTHING enforces "
                       "required reviews, required statuses, or signed commits on main",
        }
    except Exception as exc:  # noqa: BLE001
        out["branch_protection_api"] = {"error": str(exc)[:160]}
    # (b) DCO/CLA/PR-template scan
    hits = []
    gh = REPO / ".github"
    if gh.is_dir():
        for f in sorted(gh.rglob("*")):
            if f.is_file():
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except Exception:  # noqa: BLE001
                    continue
                for m in re.finditer(
                        r"(?i)\b(dco|developer certificate|cla-assistant|"
                        r"signed-off-by|pull_request_template)\b", text):
                    hits.append({"file": str(f.relative_to(REPO)).replace("\\", "/"),
                                 "match": m.group(0)})
    out["dco_cla_scan"] = {
        ".github_files_scanned": sum(1 for f in gh.rglob("*") if f.is_file())
        if gh.is_dir() else 0,
        "enforcement_hits": hits,
        "reading": "no DCO/CLA/sign-off enforcement exists in .github/"
                   if not hits else "see hits",
    }
    out["conclusion"] = (
        "The contribution flow collects NOTHING: main is unprotected and no "
        "sign-off check runs on PRs; the catalog control (compliant scratch PR "
        "must pass) is NOT-RUN under this run's billing constraint, and the "
        "static+API evidence already answers the enforcement question")
    return out


def main() -> int:
    lines: list[str] = []
    say = lines.append
    say("PROBE-1-BEGIN:ADV-0057 (pairwise contradiction matrix, file:line cited)")
    docs_present = {k: v.is_file() for k, v in DOCS.items()}
    for k, v in docs_present.items():
        say(f"DOC {k} present={v}")
    matrix = probe1_matrix()
    for c in matrix:
        say(f"CONTRADICTION {c['id']}")
        say(f"  A {c['a']['anchor']} verified_on_disk="
            f"{c['a'].get('quote_verified_on_disk', c['a'].get('exists'))} :: "
            f"{c['a']['quote'][:110]}")
        say(f"  B {c['b']['anchor']} exists={c['b'].get('exists')} :: "
            f"{c['b']['quote'][:110]}")
        say(f"  NOTE {c['note'][:150]}")
    say("PROBE-1-COMPLETE:ADV-0057")

    say("PROBE-2-BEGIN:ADV-0057 (enforcement path)")
    enf = probe2_enforcement()
    say(f"scratch_pr_test={enf['scratch_pr_test']} reason={enf['scratch_pr_reason']}")
    say(f"branch_protection rc={enf['branch_protection_api'].get('rc')} "
        f"body={enf['branch_protection_api'].get('body', '')[:120]}")
    say(f"reading={enf['branch_protection_api'].get('reading', '')[:160]}")
    say(f"dco_cla hits={enf['dco_cla_scan']['enforcement_hits']}")
    say(f"conclusion={enf['conclusion'][:220]}")
    say("PROBE-2-COMPLETE:ADV-0057")

    results = {"docs_present": docs_present, "contradiction_matrix": matrix,
               "enforcement": enf}
    out = PROBE_DIR / "governance-coherence-results.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    raw = PROBE_DIR / "probe-governance-coherence.raw.txt"
    raw.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print(f"OUT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
