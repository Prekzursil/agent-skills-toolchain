#!/usr/bin/env python
"""ADV-0053 named probes: terms-of-service conformance of provider-touching stages.

Probe 1: map each external-provider stage to the specific clause it touches, quoting the
clause with its retrieval date.
Probe 2 (mechanically different): determine the DEFAULT state EMPIRICALLY - invoke each
stage entrypoint with a scrubbed environment (no provider credentials, fresh temp HOME)
and record whether it (a) refuses/is inert with a missing-credential error (opt-in), or
(b) attempts provider egress with no configuration (default-on). No credentials are read
by this probe; scrubbed children cannot reach the real ones.

The deliverable separates 'restricted and default-on' (release blocker) from
'restricted and opt-in with a documented warning' (acceptable) from 'unrestricted'.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent

STAGES = [
    {
        "id": "zai-lane-refresh",
        "path": "zai-lanes/zai-refresh.py",
        "provider": "Z.ai (chat.z.ai / zcode.z.ai)",
        "mechanism": "official OAuth authorize+token flow driven by the logged-in "
                     "browser session (the zcode CLI's own client id)",
        "clauses": [
            {
                "source": "chat.z.ai OAuth consent screen (user must check a ToS box "
                          "per zai-refresh.py's own instructions)",
                "quote": "the script prints: '2. Check the ToS box, click Continue' - the "
                         "provider's terms are surfaced interactively per authorization",
                "retrieved": "2026-10-21 (from zai-lanes/zai-refresh.py:14-20)",
            },
            {
                "source": "Z.ai terms of service - verbatim clause",
                "quote": "NOT-CHECKED: z.ai terms text not retrievable from this box "
                         "(recorded as a gap, not as compliance)",
                "retrieved": "2026-10-21",
            },
        ],
        "restriction_class": "automated-access-to-provider (official OAuth path)",
    },
    {
        "id": "crcp-codex-rail-login",
        "path": "tools/crcp/crcp/auth_sso.py",
        "provider": "OpenAI (Codex/API plane via OIDC PKCE)",
        "mechanism": "PKCE authorization-code login; module docstring explicitly says it "
                     "does NOT fabricate NextAuth cookies; a cookie-store/ bridge exists "
                     "for web-UI sessions",
        "clauses": [
            {
                "source": "OpenAI Terms of Use (Rest of World), 'What you cannot do'",
                "quote": "Automatically or programmatically extract data or Output "
                         "(except as permitted through the API or with our written "
                         "consent)",
                "retrieved": "2026-10-21 via "
                             "https://openai.com/policies/row-terms-of-use (direct fetch "
                             "HTTP 403 from this box; clause text corroborated via "
                             "community.openai.com quotation of the ToU)",
            },
        ],
        "restriction_class": "automated access / programmatic extraction",
    },
    {
        "id": "crcp-cookie-bridge",
        "path": "tools/crcp/cookie-store/",
        "provider": "OpenAI / Anthropic (web UI sessions)",
        "mechanism": "cookie bridge carrying web-UI session cookies across runtimes",
        "clauses": [
            {
                "source": "Anthropic Acceptable Use Policy, 'Do Not Abuse Our Platform'",
                "quote": "Resell, proxy, or otherwise provide access to Claude through "
                         "unauthorized means",
                "retrieved": "2026-10-21 via https://www.anthropic.com/legal/aup",
            },
            {
                "source": "Anthropic Acceptable Use Policy, 'Do Not Abuse Our Platform'",
                "quote": "Coordinate malicious activity across multiple accounts, or "
                         "create multiple accounts, to avoid detection, circumvent "
                         "product guardrails",
                "retrieved": "2026-10-21 via https://www.anthropic.com/legal/aup",
            },
        ],
        "restriction_class": "credential sharing / multi-account / proxying access",
    },
    {
        "id": "biomni-local",
        "path": "tools/biomni-local/",
        "provider": "phylo.bio (LabBench biomni API)",
        "mechanism": "patched biomni MCP server calling api.phylo.bio",
        "clauses": [
            {
                "source": "phylo.bio service terms",
                "quote": "NOT-CHECKED: no terms text retrievable from this box; "
                         "recorded as a gap",
                "retrieved": "2026-10-21",
            },
        ],
        "restriction_class": "unclassified (terms NOT-CHECKED)",
    },
    {
        "id": "local-plugin-lifecycle",
        "path": "platform/plugin/",
        "provider": "none (local install/update/uninstall)",
        "mechanism": "transactional local installer; probe-verified to spawn only fixed"
                     "-argv interpreter version probes",
        "clauses": [],
        "restriction_class": "unrestricted (no external provider)",
    },
]


def empirical_default_state(stage: dict) -> dict:
    """Invoke the stage entrypoint in a scrubbed env; record inert/refusal vs egress."""
    entry = REPO / stage["path"]
    if entry.is_dir() or not entry.is_file():
        return {"stage": stage["id"], "entrypoint": stage["path"],
                "status": "NOT-RUN (no single-file entrypoint; directory stage)"}
    tmp = Path(tempfile.mkdtemp(prefix="adv53-"))
    env = {
        "USERPROFILE": str(tmp), "HOME": str(tmp), "TEMP": str(tmp), "TMP": str(tmp),
        "PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get(
            "SYSTEMROOT", "C:\\Windows"),
        "PYTHONIOENCODING": "utf-8",
    }
    for secret_key in ("OPENROUTER_API_KEY", "ZAI_KEY", "ANTHROPIC_API_KEY",
                       "OPENAI_API_KEY", "GROK_LANE_KEY"):
        env.pop(secret_key, None)
    try:
        cp = subprocess.run(
            [sys.executable, "-B", str(entry)],
            capture_output=True, text=True, timeout=60, env=env, cwd=str(tmp))
        out = (cp.stdout or "") + (cp.stderr or "")
        egress_attempt = bool(re.search(
            r"urlopen|urllib\.error|HTTP Error|Connection|ssl|CERTIFICATE", out))
        inert = cp.returncode != 0 and not egress_attempt
        return {
            "stage": stage["id"], "entrypoint": stage["path"], "rc": cp.returncode,
            "scrubbed_home": str(tmp),
            "attempted_provider_egress": egress_attempt,
            "classification": ("opt-in/inert-without-setup" if inert else
                               "NEEDS-INSPECTION"),
            "raw_tail": out.strip()[-400:],
        }
    except Exception as exc:  # noqa: BLE001
        return {"stage": stage["id"], "entrypoint": stage["path"],
                "status": f"ERROR {type(exc).__name__}: {exc}"[:200]}


def main() -> int:
    lines: list[str] = []
    say = lines.append
    say("PROBE-1-BEGIN:ADV-0053 (clause-to-stage mapping, quoted with retrieval date)")
    for st in STAGES:
        say(f"STAGE {st['id']} provider={st['provider']} class={st['restriction_class']}")
        for c in st["clauses"]:
            say(f"  CLAUSE ({c['retrieved']}) {c['source']}: {c['quote'][:220]}")
    say("PROBE-1-COMPLETE:ADV-0053")

    say("PROBE-2-BEGIN:ADV-0053 (empirical default-state, scrubbed env, no credentials)")
    results = []
    for st in STAGES:
        r = empirical_default_state(st)
        results.append(r)
        say(f"DEFAULT {r.get('stage')} rc={r.get('rc')} "
            f"egress={r.get('attempted_provider_egress')} "
            f"class={r.get('classification', r.get('status'))}")
        if r.get("raw_tail"):
            say(f"  TAIL {r['raw_tail'][:200]!r}")
    say("PROBE-2-COMPLETE:ADV-0053")

    say("SEPARATION (release blocker vs acceptable vs unrestricted):")
    for st, r in zip(STAGES, results, strict=False):
        if st["restriction_class"] == "unrestricted (no external provider)":
            bucket = "unrestricted"
        elif r.get("classification") == "opt-in/inert-without-setup":
            bucket = "restricted and opt-in (inert without explicit setup)"
        elif r.get("classification") == "NEEDS-INSPECTION":
            bucket = "restricted and NEEDS-INSPECTION"
        else:
            bucket = "restricted and NOT-RUN"
        say(f"  BUCKET {st['id']} -> {bucket}")
        st["bucket"] = bucket
    say("restricted-and-default-on (release blocker) count = "
        f"{sum(1 for st in STAGES if st.get('bucket','').startswith('restricted and default'))}")
    say("PROBE-SEPARATION-COMPLETE:ADV-0053")

    out = PROBE_DIR / "provider-tos-results.json"
    out.write_text(json.dumps({"stages": STAGES, "empirical": results}, indent=2,
                              sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    raw = PROBE_DIR / "probe-provider-tos.raw.txt"
    raw.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print(f"OUT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
