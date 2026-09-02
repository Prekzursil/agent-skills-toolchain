"""Estate rails, verbatim quotes, running practices, and plain-reading tensions.

Reports what the captured terms SAY. Does not render a compliance verdict.
"""
from __future__ import annotations

import os
from pathlib import Path

from common import REPO, collapse_ws

DISPATCH = REPO / "command-center" / "p2-wave" / "seed-stage" / "dispatch_cursor.py"
FLEET = REPO / "command-center" / "p2-wave" / "seed-stage" / "bringup_cursor_fleet.py"
CNF7 = REPO / "command-center" / "p2-wave" / "probes" / "CNF-0007" / "dispatch.py"
WHOAMI = REPO / "command-center" / "p2-wave" / "probes" / "CNF-0160" / "whoami.py"


def _contains(path: Path, needle: str) -> bool:
    if not path.is_file():
        return False
    return needle in path.read_text(encoding="utf-8", errors="replace")


def practices() -> list[dict]:
    unattended = _contains(DISPATCH, "cursor-agent") and _contains(DISPATCH, '"-p"')
    shared_key_slots = DISPATCH.is_file() and _contains(DISPATCH, "CURSOR_API_KEY") and "% 4" in DISPATCH.read_text(
        encoding="utf-8", errors="replace"
    )
    fleet_same_token = _contains(FLEET, "CURSOR_API_KEY") or _contains(FLEET, "CURSOR_API_TOKEN")
    confirmer_local = CNF7.is_file()
    rotator_hits = []
    for rel in (
        "command-center/p2-wave/seed-stage",
        "tools",
    ):
        root = REPO / rel
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            text = p.read_text(encoding="utf-8", errors="replace").lower()
            if "multi-account" in text or "account_rotat" in text or "rotate_account" in text:
                rotator_hits.append(str(p.relative_to(REPO)).replace("\\", "/"))
    env_presence = {
        name: bool(os.environ.get(name))
        for name in (
            "CURSOR_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "XAI_API_KEY",
            "GROQ_API_KEY",
        )
    }
    return [
        {
            "id": "cursor-unattended-cli",
            "running": unattended,
            "evidence": "command-center/p2-wave/seed-stage/dispatch_cursor.py launches cursor-agent -p",
            "present": DISPATCH.is_file(),
        },
        {
            "id": "cursor-shared-env-key-concurrency",
            "running": bool(shared_key_slots or (unattended and DISPATCH.is_file())),
            "evidence": "one CURSOR_API_KEY in the process environment; slot(uid)%4 worker fan-out",
            "present": DISPATCH.is_file(),
        },
        {
            "id": "cursor-fleet-same-token",
            "running": fleet_same_token,
            "evidence": "command-center/p2-wave/seed-stage/bringup_cursor_fleet.py reads CURSOR_API_KEY/TOKEN for 3 boxes",
            "present": FLEET.is_file(),
        },
        {
            "id": "catalog-cross-vendor-assignment",
            "running": True,
            "evidence": "WORK-UNIT-CATALOG.json assigned_model_vendor_role plus CNF-0007 confirmer/implementer split",
            "present": True,
        },
        {
            "id": "cnf0007-confirmer-subprocess",
            "running": confirmer_local,
            "evidence": "CNF-0007/dispatch.py is a local confirmer subprocess, not a live vendor HTTPS call",
            "present": confirmer_local,
        },
        {
            "id": "multi-account-rotation",
            "running": False,
            "evidence": (
                "no account-rotator implementation found under seed-stage/tools; "
                f"mention_hits={rotator_hits[:8]}"
            ),
            "present": False,
        },
        {
            "id": "env-vendor-key-names",
            "running": any(env_presence.values()),
            "evidence": {
                k: {"present": v, "value_redacted": True} for k, v in env_presence.items()
            },
            "present": True,
        },
        {
            "id": "cnf0160-named-rails",
            "running": WHOAMI.is_file(),
            "evidence": "CNF-0160/whoami.py names anthropic, openai-codex, google-gemini, xai, groq, cursor",
            "present": WHOAMI.is_file(),
        },
    ]


# Quotes must be substrings of captured .txt after collapse_ws.
QUOTES = [
    {
        "id": "cursor-tos-account-confidentiality",
        "capture_id": "cursor-tos",
        "rail": "cursor",
        "topic": "account-sharing",
        "effective_date": "2026-08-13",
        "quote": (
            "You are solely responsible for maintaining the confidentiality of your "
            "account and password, and you accept responsibility for all activities "
            "that occur under your account."
        ),
    },
    {
        "id": "cursor-aup-automated-access",
        "capture_id": "cursor-aup",
        "rail": "cursor",
        "topic": "programmatic-invocation",
        "effective_date": "2026-08-11",
        "quote": (
            "Accessing the Service through automated or non-human means, whether "
            "through a bot, script, or otherwise"
        ),
    },
    {
        "id": "cursor-aup-model-providers",
        "capture_id": "cursor-aup",
        "rail": "cursor",
        "topic": "cross-vendor-orchestration",
        "effective_date": "2026-08-11",
        "quote": (
            "The Service may route your data to AI models provided by us and by "
            "third-party model providers (\"Model Providers\"). When you access a "
            "third-party AI model through the Service, the applicable Model "
            "Provider's acceptable use policy also applies."
        ),
    },
    {
        "id": "cursor-aup-rate-limits",
        "capture_id": "cursor-aup",
        "rail": "cursor",
        "topic": "rate-limit-circumvention",
        "effective_date": "2026-08-11",
        "quote": (
            "including circumventing any rate limits or restrictions or protective "
            "measures and safety mitigations"
        ),
    },
    {
        "id": "cursor-msa-login-not-shared",
        "capture_id": "cursor-msa",
        "rail": "cursor",
        "topic": "account-sharing",
        "effective_date": "2026-08-13",
        "quote": (
            "including without limitation ensuring any Authorized User's login is "
            "not shared by multiple people"
        ),
    },
    {
        "id": "cursor-cli-print-mode",
        "capture_id": "cursor-cli-headless",
        "rail": "cursor",
        "topic": "programmatic-invocation-permitted-path",
        "effective_date": "retrieved-live-no-page-date",
        "quote": (
            "Use print mode (-p, --print) for non-interactive scripting and automation."
        ),
    },
    {
        "id": "cursor-sa-cli-key",
        "capture_id": "cursor-service-accounts",
        "rail": "cursor",
        "topic": "programmatic-invocation-permitted-path",
        "effective_date": "retrieved-live-no-page-date",
        "quote": (
            "Service accounts can authenticate the Cursor CLI by setting the API key "
            "as CURSOR_API_KEY. This is the recommended way to run the CLI in CI/CD "
            "pipelines, cron jobs, and other non-interactive environments where "
            "browser login isn't possible."
        ),
    },
    {
        "id": "anthropic-commercial-api-keys",
        "capture_id": "anthropic-commercial",
        "rail": "anthropic",
        "topic": "programmatic-invocation",
        "effective_date": "2025-06-17",
        "quote": "They govern Customer’s use of Anthropic API keys",
    },
    {
        "id": "anthropic-commercial-not-consumer",
        "capture_id": "anthropic-commercial",
        "rail": "anthropic",
        "topic": "consumer-vs-api",
        "effective_date": "2025-06-17",
        "quote": "Services under these Terms are not for consumer use.",
    },
    {
        "id": "anthropic-commercial-account-activity",
        "capture_id": "anthropic-commercial",
        "rail": "anthropic",
        "topic": "account-responsibility",
        "effective_date": "2025-06-17",
        "quote": "Customer is responsible for all activity under its account.",
    },
    {
        "id": "anthropic-aup-multi-account",
        "capture_id": "anthropic-aup",
        "rail": "anthropic",
        "topic": "multi-account-rotation",
        "effective_date": "2025-09-15",
        "quote": (
            "Coordinate malicious activity across multiple accounts to avoid "
            "detection or circumvent product guardrails"
        ),
    },
    {
        "id": "anthropic-aup-automation-accounts",
        "capture_id": "anthropic-aup",
        "rail": "anthropic",
        "topic": "multi-account-rotation",
        "effective_date": "2025-09-15",
        "quote": "Utilize automation in account creation or to engage in spammy behavior",
    },
    {
        "id": "anthropic-consumer-no-bots",
        "capture_id": "anthropic-consumer",
        "rail": "anthropic",
        "topic": "programmatic-invocation",
        "effective_date": "2025-10-08",
        "quote": (
            "Except when you are accessing our Services via an Anthropic API Key or "
            "where we otherwise explicitly permit it, to access the Services through "
            "automated or non-human means, whether through a bot, script, or otherwise."
        ),
    },
    {
        "id": "openai-services-api-right",
        "capture_id": "openai-services",
        "rail": "openai",
        "topic": "programmatic-invocation",
        "effective_date": "2026-01-01",
        "quote": (
            "This includes the right to use OpenAI’s API to integrate the Services "
            "into Customer Applications"
        ),
    },
    {
        "id": "openai-services-no-share-creds",
        "capture_id": "openai-services",
        "rail": "openai",
        "topic": "account-sharing",
        "effective_date": "2026-01-01",
        "quote": (
            "Customer will not share Account access credentials or individual login "
            "credentials between multiple users."
        ),
    },
    {
        "id": "openai-services-no-circumvent-limits",
        "capture_id": "openai-services",
        "rail": "openai",
        "topic": "rate-limit-circumvention",
        "effective_date": "2026-01-01",
        "quote": (
            "interfere with or disrupt the Services, including circumvent any rate "
            "limits or restrictions"
        ),
    },
    {
        "id": "openai-consumer-no-share",
        "capture_id": "openai-consumer",
        "rail": "openai",
        "topic": "account-sharing",
        "effective_date": "2026-01-01",
        "quote": (
            "You may not share your account credentials or make your account "
            "available to anyone else"
        ),
    },
    {
        "id": "google-no-competing-models",
        "capture_id": "google-gemini-api",
        "rail": "google",
        "topic": "programmatic-invocation",
        "effective_date": "2026-03-23",
        "quote": (
            "You may not use the Services to develop models that compete with the "
            "Services (e.g., Gemini API or Google AI Studio)."
        ),
    },
    {
        "id": "google-no-bypass-safety",
        "capture_id": "google-gemini-api",
        "rail": "google",
        "topic": "rate-limit-circumvention",
        "effective_date": "2026-03-23",
        "quote": "You may not attempt to bypass these protective measures",
    },
    {
        "id": "xai-no-share",
        "capture_id": "xai-consumer",
        "rail": "xai",
        "topic": "account-sharing",
        "effective_date": "2026-06-26",
        "quote": (
            "You may not share your account credentials or make your account "
            "available to anyone else"
        ),
    },
    {
        "id": "xai-enterprise-governs-api",
        "capture_id": "xai-consumer",
        "rail": "xai",
        "topic": "programmatic-invocation",
        "effective_date": "2026-06-26",
        "quote": (
            "Our Enterprise Terms of Service govern the use of our Services for "
            "developers and businesses, including xAI APIs and PromptIDE."
        ),
    },
    {
        "id": "groq-website-defers",
        "capture_id": "groq-website-tos",
        "rail": "groq",
        "topic": "consumer-vs-api",
        "effective_date": "2025-10-15",
        "quote": (
            "These Terms do not apply to you in connection with your use of Groq’s "
            "cloud services, including GroqChat, Groq Playground, and GroqCloud. If "
            "you are interacting with Groq as a customer of our services, the Groq "
            "Services Agreement governs."
        ),
    },
    {
        "id": "groq-not-consumer",
        "capture_id": "groq-services",
        "rail": "groq",
        "topic": "programmatic-invocation",
        "effective_date": "online-acceptance",
        "quote": (
            "Cloud Services and the AI Model Services under this Agreement are not "
            "for consumer use."
        ),
    },
    {
        "id": "groq-api-right",
        "capture_id": "groq-services",
        "rail": "groq",
        "topic": "programmatic-invocation",
        "effective_date": "online-acceptance",
        "quote": (
            "including the right to use Groq’s APIs to integrate the Cloud Services"
        ),
    },
    {
        "id": "groq-account-authorized-only",
        "capture_id": "groq-services",
        "rail": "groq",
        "topic": "account-sharing",
        "effective_date": "online-acceptance",
        "quote": (
            "Customer will only make its Account available to Authorized Account Users."
        ),
    },
]


def quote_in_text(quote: str, text: str) -> bool:
    return collapse_ws(quote) in collapse_ws(text)


def locate_quotes(captures: dict[str, dict]) -> list[dict]:
    rows = []
    for q in QUOTES:
        cap = captures.get(q["capture_id"]) or {}
        text = cap.get("text") or ""
        found = quote_in_text(q["quote"], text)
        rows.append({**q, "found_in_capture": found, "capture_http_status": cap.get("http_status")})
    return rows


def compute_conflicts(practice_rows: list[dict], quote_rows: list[dict]) -> list[dict]:
    by_p = {p["id"]: p for p in practice_rows}
    by_q = {q["id"]: q for q in quote_rows}
    out: list[dict] = []

    def add(cid: str, qid: str, pid: str, note: str) -> None:
        q = by_q[qid]
        p = by_p[pid]
        if not p.get("running"):
            return
        out.append(
            {
                "id": cid,
                "quote_id": qid,
                "practice_id": pid,
                "rail": q["rail"],
                "plain_reading_tension": True,
                "legal_verdict": None,
                "owner_decision": True,
                "note": note,
                "quote": q["quote"],
                "effective_date": q["effective_date"],
            }
        )

    add(
        "C-CURSOR-AUP-AUTOMATION-VS-UNATTENDED-CLI",
        "cursor-aup-automated-access",
        "cursor-unattended-cli",
        "Consumer AUP lists automated/non-human access as a prohibited example; "
        "the estate already runs cursor-agent -p. Cursor CLI docs and service-account "
        "docs describe -p + CURSOR_API_KEY as the supported non-interactive path. "
        "Which contract (consumer AUP vs service-account/MSA) applies is an owner "
        "choice, not an engineering one.",
    )
    add(
        "C-CURSOR-TOS-ACCOUNT-VS-SHARED-ENV-KEY",
        "cursor-tos-account-confidentiality",
        "cursor-shared-env-key-concurrency",
        "Consumer ToS assigns all activity under an account to the registrant and "
        "requires password confidentiality. Fan-out of one env key across concurrent "
        "agent processes is a currently running practice. Whether that key is a "
        "personal login or a service-account credential is an owner classification.",
    )
    add(
        "C-CURSOR-MSA-LOGIN-VS-FLEET-TOKEN",
        "cursor-msa-login-not-shared",
        "cursor-fleet-same-token",
        "MSA requires an Authorized User login not be shared by multiple people. "
        "Fleet bring-up can stamp one CURSOR_API_KEY/TOKEN onto multiple boxes. "
        "People-sharing vs non-human service-account reuse is an owner distinction.",
    )
    add(
        "C-CURSOR-AUP-UPSTREAM-VS-GROK-VIA-CURSOR",
        "cursor-aup-model-providers",
        "cursor-unattended-cli",
        "Cursor AUP says the upstream Model Provider AUP also applies when a "
        "third-party model is selected. This session's dispatcher pins "
        "cursor-grok-4.6-xhigh, so xAI terms may be in the stack even though the "
        "estate's counterparty for the CLI is Cursor. Owner decides whether Grok "
        "via Cursor is treated as Cursor-only or dual-vendor.",
    )
    add(
        "C-ANTHROPIC-AUP-MULTI-ACCOUNT-VS-ROTATION",
        "anthropic-aup-multi-account",
        "multi-account-rotation",
        "Usage Policy forbids coordinating activity across multiple accounts to "
        "circumvent guardrails. A live rotator would be a plain-reading tension. "
        "This detector only fires when that practice is running.",
    )
    add(
        "C-OPENAI-LIMITS-VS-ROTATION",
        "openai-services-no-circumvent-limits",
        "multi-account-rotation",
        "Services Agreement forbids circumventing rate limits. Multi-account "
        "rotation to evade limits would be a plain-reading tension. Fires only "
        "when that practice is running.",
    )
    return out


def owner_vs_engineering() -> list[dict]:
    return [
        {
            "item": "Use consumer Cursor login versus service-account/API key for unattended fleet",
            "class": "owner",
            "why": "Chooses which Cursor instrument (consumer ToS/AUP vs MSA/service accounts) is the contract.",
        },
        {
            "item": "Stand up multiple vendor accounts to evade rate limits",
            "class": "owner",
            "why": "Several AUPs speak to multi-account circumvention; building that rail is not an engineering default.",
        },
        {
            "item": "Queue and retry work on one authenticated Cursor CLI rail",
            "class": "engineering",
            "why": "Official CLI docs describe -p / CURSOR_API_KEY for non-interactive runs once the credential class is chosen.",
        },
        {
            "item": "Send estate content to a confirmer on a different vendor than the implementer",
            "class": "owner",
            "why": "Cross-vendor data flow and upstream Model Provider AUPs are contract/privacy choices; CNF-0007 is only an assignment mechanism.",
        },
        {
            "item": "How to implement a catalog confirmer subprocess",
            "class": "engineering",
            "why": "CNF-0007 dispatch.py is a local parsing harness, not a live vendor API client.",
        },
        {
            "item": "Treat this unit's output as permission to keep or change a rail",
            "class": "owner",
            "why": "Catalog reviewer_requirement and owner_approval_required: research reports what terms say and does not authorize action.",
        },
    ]
