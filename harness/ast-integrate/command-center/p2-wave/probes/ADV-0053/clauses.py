"""Pinned provider-clause excerpts for ADV-0053 Probe 1.

Quotes were retrieved 2026-08-24 from the URLs below. Probes re-run offline
against this pin; they do not re-fetch. Retrieval date travels with each quote.
"""
from __future__ import annotations

RETRIEVED_AT = "2026-08-24"

CLAUSES: dict[str, dict] = {
    "openai-credentials": {
        "provider": "openai",
        "url": "https://openai.com/policies/services-agreement/",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "credential_sharing",
        "quote": (
            "Customer will not share Account access credentials or individual "
            "login credentials between multiple users. Customer may not resell "
            "or lease access to its Account or any End User Account."
        ),
    },
    "openai-api-keys": {
        "provider": "openai",
        "url": "https://openai.com/policies/services-agreement/",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "credential_sharing",
        "quote": (
            "buy, sell, or transfer API keys from, to, or with a third party"
        ),
    },
    "openai-rate-evasion": {
        "provider": "openai",
        "url": "https://openai.com/policies/services-agreement/",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "rate_evasion",
        "quote": (
            "interfere with or disrupt the Services, including circumvent any "
            "rate limits or restrictions or bypass any protective measures or "
            "safety mitigations for the Services"
        ),
    },
    "openai-extract": {
        "provider": "openai",
        "url": "https://openai.com/policies/services-agreement/",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "scraping",
        "quote": (
            "extract data from the Services other than as permitted through "
            "the Services"
        ),
    },
    "anthropic-credentials": {
        "provider": "anthropic",
        "url": "https://www.anthropic.com/legal/consumer-terms",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "credential_sharing",
        "quote": (
            "You may not share your Account login information, Anthropic API "
            "key, or Account credentials with anyone else. You also may not "
            "make your Account available to anyone else."
        ),
    },
    "anthropic-scrape": {
        "provider": "anthropic",
        "url": "https://www.anthropic.com/legal/consumer-terms",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "scraping",
        "quote": (
            "To crawl, scrape, or otherwise harvest data or information from "
            "our Services other than as permitted under these Terms."
        ),
    },
    "anthropic-automated": {
        "provider": "anthropic",
        "url": "https://www.anthropic.com/legal/consumer-terms",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "automated_access",
        "quote": (
            "Except when you are accessing our Services via an Anthropic API "
            "Key or where we otherwise explicitly permit it, to access the "
            "Services through automated or non-human means, whether through "
            "a bot, script, or otherwise."
        ),
    },
    "tavily-scrape-services": {
        "provider": "tavily",
        "url": "https://www.tavily.com/acceptable-use-policy",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "scraping",
        "quote": (
            "to access, use, scrape, extract, harvest, or index the Services "
            "(including any data or content made available through the "
            "Services) by automated means, except as expressly permitted by "
            "the Services or in writing by Tavily"
        ),
    },
    "tavily-load": {
        "provider": "tavily",
        "url": "https://www.tavily.com/acceptable-use-policy",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "rate_evasion",
        "quote": (
            "to interfere with, disrupt, degrade, impair, or attack the "
            "Services, the Tavily platform, or any network or system "
            "connected thereto, including through flooding, denial-of-service "
            "attacks, or the use of bots or automated scripts to generate "
            "excessive or abusive load on the Services"
        ),
    },
    "tavily-key-share": {
        "provider": "tavily",
        "url": "https://www.tavily.com/terms",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "credential_sharing",
        "quote": (
            "the Tavily API, including any Agent Key, is intended solely for "
            "Customer's use, may not be transferred, assigned, shared, or "
            "otherwise made available to any third party"
        ),
    },
    "tavily-multi-account": {
        "provider": "tavily",
        "url": "https://www.tavily.com/terms",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "multiple_accounts",
        "quote": (
            "each Order Form provides the Customer and its Users with access "
            "to a single Account only, and (Y) any additional Accounts may "
            "require the issuance of a separate Order Form"
        ),
    },
    "exa-scrape-services": {
        "provider": "exa",
        "url": "https://exa.ai/assets/Exa_Labs_Terms_of_Service.pdf",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "scraping",
        "quote": (
            "use any robot, spider, crawlers, scraper, or other automatic "
            "device, process, software or queries that intercepts, \"mines,\" "
            "scrapes, extracts, or otherwise accesses the Services to monitor, "
            "extract, copy or collect information or data from or through "
            "the Services"
        ),
    },
    "exa-bots": {
        "provider": "exa",
        "url": "https://exa.ai/assets/Exa_Labs_Terms_of_Service.pdf",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "automated_access",
        "quote": (
            "use automation software (bots), hacks, modifications (mods) or "
            "any other unauthorized third-party software designed to modify "
            "the Services"
        ),
    },
    "exa-account": {
        "provider": "exa",
        "url": "https://exa.ai/assets/Exa_Labs_Terms_of_Service.pdf",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "credential_sharing",
        "quote": (
            "You are solely responsible for any activity on your Account or "
            "your Authorized Users' Accounts"
        ),
    },
    "firecrawl-account": {
        "provider": "firecrawl",
        "url": "https://www.firecrawl.dev/terms-of-service",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "credential_sharing",
        "quote": "Access another's account without permission of us or that person;",
    },
    "firecrawl-unlawful": {
        "provider": "firecrawl",
        "url": "https://www.firecrawl.dev/terms-of-service",
        "retrieved_at": RETRIEVED_AT,
        "restriction": "scraping",
        "quote": (
            "Use the Services for any unlawful activities or in violation of "
            "any laws, regulations, or contractual provisions, or to induce "
            "others to do or engage in the same;"
        ),
    },
}


def clause(cid: str) -> dict:
    row = CLAUSES[cid]
    return {
        "id": cid,
        "provider": row["provider"],
        "url": row["url"],
        "retrieved_at": row["retrieved_at"],
        "restriction": row["restriction"],
        "quote": row["quote"],
    }
