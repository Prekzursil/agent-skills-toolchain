#!/usr/bin/env python3
"""Live source table for RES-0059 (API rail + prose rail per family)."""
from __future__ import annotations

UA = (
    "RES-0059-governance-research/1.0 "
    "(ast-integrate; research-claim-record; not-a-browser)"
)

# Each family supplies one structured API GET and one prose GET.
# Captures are stored under captures/<id>.meta.json + captures/<id>.body
SOURCES = [
    {
        "id": "pep541_api",
        "family": "pep541",
        "rail": "api",
        "url": "https://api.github.com/repos/python/peps/contents/peps/pep-0541.rst",
        "accept": "application/vnd.github+json",
        "decode_github_contents": True,
    },
    {
        "id": "pep541_html",
        "family": "pep541",
        "rail": "prose",
        "url": "https://peps.python.org/pep-0541/",
        "accept": "text/html",
    },
    {
        "id": "npm_disputes_api",
        "family": "npm_disputes",
        "rail": "api",
        "url": (
            "https://api.github.com/repos/npm/documentation/contents/"
            "content/policies/disputes.mdx"
        ),
        "accept": "application/vnd.github+json",
        "decode_github_contents": True,
    },
    {
        "id": "npm_disputes_html",
        "family": "npm_disputes",
        "rail": "prose",
        "url": "https://docs.npmjs.com/policies/disputes",
        "accept": "text/html",
    },
    {
        "id": "npm_conduct_html",
        "family": "npm_conduct",
        "rail": "prose",
        "url": "https://docs.npmjs.com/policies/conduct",
        "accept": "text/html",
    },
    {
        "id": "rfc3463_api",
        "family": "crates_rfc3463",
        "rail": "api",
        "url": (
            "https://api.github.com/repos/rust-lang/rfcs/contents/"
            "text/3463-crates-io-policy-update.md"
        ),
        "fallback_urls": [
            "https://api.github.com/repos/rust-lang/rfcs/contents/text/3463-crates-io-policy-update.md",
            "https://api.github.com/repos/rust-lang/rfcs/contents/text/3463-crates-io-policy-update.md",
        ],
        "accept": "application/vnd.github+json",
        "decode_github_contents": True,
    },
    {
        "id": "rfc3463_raw",
        "family": "crates_rfc3463",
        "rail": "prose",
        "url": (
            "https://raw.githubusercontent.com/rust-lang/rfcs/master/"
            "text/3463-crates-io-policy-update.md"
        ),
        "fallback_urls": [
            "https://raw.githubusercontent.com/rust-lang/rfcs/master/text/3463-crates-io-policy-update.md",
            "https://raw.githubusercontent.com/rust-lang/rfcs/master/text/3463-crates-io-policy-update.md",
        ],
        "accept": "text/plain",
    },
    {
        "id": "crates_policies_html",
        "family": "crates_policies",
        "rail": "prose",
        "url": "https://crates.io/policies",
        "accept": "text/html",
    },
    {
        "id": "hf_moderation_api",
        "family": "hf_moderation",
        "rail": "api",
        "url": (
            "https://api.github.com/repos/huggingface/hub-docs/contents/"
            "docs/hub/moderation.md"
        ),
        "fallback_urls": [
            "https://api.github.com/repos/huggingface/hub-docs/contents/docs/hub/en/moderation.md",
            "https://api.github.com/repos/huggingface/hub-docs/contents/docs/hub/security.md",
        ],
        "accept": "application/vnd.github+json",
        "decode_github_contents": True,
    },
    {
        "id": "hf_moderation_html",
        "family": "hf_moderation",
        "rail": "prose",
        "url": "https://huggingface.co/docs/hub/en/moderation",
        "accept": "text/html",
    },
    {
        "id": "hf_content_html",
        "family": "hf_content",
        "rail": "prose",
        "url": "https://huggingface.co/content-policy",
        "accept": "text/html",
    },
    {
        "id": "hf_tos_html",
        "family": "hf_tos",
        "rail": "prose",
        "url": "https://huggingface.co/terms-of-service",
        "accept": "text/html",
    },
    {
        "id": "pypi_tos_html",
        "family": "pypi_tos",
        "rail": "prose",
        "url": "https://policies.python.org/pypi.org/Terms-of-Use/",
        "accept": "text/html",
    },
]

# Needles are tried in order; first hit in the *searchable* body is recorded.
NEEDLES = {
    "fcfs": [
        "first-come, first-served",
        "first come, first served",
        "First come, first served",
        "first-come-first-served",
        "available on a first-come, first-served basis",
    ],
    "pep541_not_arbiter": [
        "not arbiters in disputes around *active* projects",
        "not arbiters in disputes around active projects",
        "The Package Index maintainers are not arbiters",
        "not arbiters in disputes",
    ],
    "pep541_reach": [
        "no circumstances will a name be reassigned against",
        "Under no circumstances will a name be reassigned against the wishes of a reachable owner",
        "reachable owner",
        "existing owner is reachable",
    ],
    "pep541_channel": [
        "pypi-support",
        "pypa/pypi-support",
        "open a new issue",
        "How to request a name transfer",
    ],
    "npm_no_squat_on_demand": [
        "does not resolve squatting claims on demand",
        "npm does not resolve squatting claims on demand",
        "do not transfer package, organization, or username ownership simply because",
        "We do not transfer package, organization, or username ownership simply because another user wants the name",
        "npm does not mediate naming disputes",
        "We do not transfer package",
    ],
    "npm_trademark": [
        "trademark",
        "GitHub Trademark Policy",
        "name dispute process",
    ],
    "npm_admin_delete": [
        "at the discretion of npm",
        "will be deleted, at the discretion of npm",
        "administrators reserve the right",
        "Service administrators reserve the right",
        "The Service administrators reserve the right to make judgment calls",
        "deleted, at the discretion",
    ],
    "crates_team": [
        "crates.io team",
        "the crates.io team",
    ],
    "crates_no_reverse": [
        "no basis to reverse",
        "there is no basis to reverse these moderation actions",
        "content and account deletion is permanent",
        "In all cases, content and account deletion is permanent and there is no basis to reverse these moderation actions taken by the crates.io team",
        "no basis to reverse these moderation actions taken by the crates.io team",
    ],
    "crates_help": [
        "help@crates.io",
        "contact help@crates.io",
    ],
    "hf_report": [
        "Report the repository",
        "report a repository",
        "Reporting a repository",
    ],
    "hf_contest": [
        "safety@huggingface.co",
        "contest a moderation decision",
        "legal@huggingface.co",
        "How you can contest a moderation decision",
    ],
    "hf_dmca": [
        "dmca@huggingface.co",
        "DMCA takedown",
        "Takedown notice",
    ],
    "hf_discretion": [
        "sole discretion",
        "at our sole discretion",
        "We may remove your Content at any time",
    ],
    "hf_dsa": [
        "out-of-court dispute settlement",
        "Digital Services Act",
        "certified out-of-court",
    ],
}

OMIT_ID = "OMIT-INDEPENDENT-RECUSAL-PANEL"

SENTINEL = (
    "SUCCESS:RES-0059 in the receipt AND a minimal clause set with "
    "per-clause citations and at least one explicitly omitted clause"
)
