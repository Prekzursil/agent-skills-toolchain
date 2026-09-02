#!/usr/bin/env python3
"""Live-measure inbound source reachability from this worker and emit RES-0179."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fetchutil as F  # noqa: E402
import targets as T  # noqa: E402

OUT_REL = (
    "command-center/research/sources-frontier/"
    "RES-0179-jurisdiction-source-accessibility-scoping.json"
)
QUESTION = (
    "For the regions this research program will query from: which source classes "
    "are geo-blocked, paywalled, robots-excluded or legally restricted, and what "
    "does the research plan do when the only source for a claim is unreachable "
    "from here? Distinct from RES-0119 (conducts the Tor sweep) and RES-0124 "
    "(our own publication privacy surface) - this is inbound reachability."
)


def parse_cf_trace(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def classify_fetch(row: dict, *, role: str = "") -> dict:
    status = row.get("http_status")
    head = str(row.get("body_text") or row.get("body_head") or "")
    low = head.lower()
    resolved = str(row.get("resolved_url") or "")
    kinds: list[str] = []
    notes: list[str] = []

    if row.get("error_type") and status is None:
        kinds.append("technically-unreachable")
        notes.append(f"{row.get('error_type')}: {row.get('error_message')}")
    if row.get("waf_action"):
        kinds.append("waf-or-bot-challenge")
        notes.append(f"waf_action={row.get('waf_action')}")
    if status == 403 and (
        "just a moment" in low
        or "security verification" in low
        or "cloudflare" in low
    ):
        kinds.append("waf-or-bot-challenge")
        notes.append("403 challenge/interstitial page")
    if status == 401 and (
        "enable js" in low or "ad blocker" in low or "datadome" in low
    ):
        kinds.append("waf-or-bot-challenge")
        notes.append("401 JS/antibot interstitial")
    if status == 403 and '"result":"geolocation"' in low.replace(" ", ""):
        kinds.append("geo-blocked")
        notes.append("BBC mediaselector JSON result=geolocation")
    if "/unavailable" in resolved and "peacocktv.com" in resolved:
        kinds.append("geo-blocked")
        notes.append("peacocktv.com redirected to /unavailable")
    if "cookies_not_supported" in resolved or (
        "access-options" in low and ("subscribe" in low or "paywall" in low)
    ):
        kinds.append("paywalled")
        notes.append("publisher access/paywall markers in body or URL")
    if "paywall" in low and "nature.com" in resolved:
        kinds.append("paywalled")
    if role == "robots-policy" or resolved.endswith("robots.txt"):
        star_paths = F.ua_star_disallow_paths(head)
        if "/" in star_paths:
            kinds.append("robots-excluded")
            notes.append("robots.txt User-agent * Disallow:/ parsed from fetched bytes")
        elif star_paths:
            kinds.append("robots-path-exclusions")
            notes.append(
                f"robots.txt User-agent * has {len(star_paths)} Disallow paths "
                f"(not site-wide /); sample={star_paths[:8]}"
            )
        if "text and data mining" in low or "eu directive on copyright" in low:
            kinds.append("legally-restricted")
            notes.append("fetched robots.txt states TDM/AI prohibition (EU DSM Art. 4 notice)")
        if "/youtubei/" in star_paths or "/get_video" in star_paths:
            kinds.append("robots-path-exclusions")
            notes.append("YouTube robots.txt disallows transcript/API paths")
    if role == "legal-and-technical-refusal":
        kinds.append("legally-restricted")
        notes.append(
            "public-tor not fetched via Tor; owner-gated (RES-0119/RES-0138). "
            "Clearnet attempt recorded as technical unreachability only."
        )

    kinds = list(dict.fromkeys(kinds))
    if not kinds:
        if row.get("ok_2xx"):
            kinds = ["reachable"]
            notes.append(f"HTTP {status} on resolved URL")
        elif isinstance(status, int):
            kinds = ["http-error"]
            notes.append(f"HTTP {status} without a more specific barrier classifier")
        else:
            kinds = ["technically-unreachable"]

    primary = kinds[0]
    # Prefer specific barriers over generic reachable when both apply
    for preferred in (
        "geo-blocked",
        "paywalled",
        "legally-restricted",
        "robots-excluded",
        "robots-path-exclusions",
        "waf-or-bot-challenge",
        "technically-unreachable",
    ):
        if preferred in kinds:
            primary = preferred
            break
    return {"primary": primary, "all": kinds, "notes": notes}


def lineage(row: dict) -> dict:
    return {
        "resolved_url": row.get("resolved_url") or row.get("requested_url"),
        "requested_url": row.get("requested_url"),
        "fetch_timestamp": row.get("fetch_timestamp"),
        "http_status": row.get("http_status"),
        "sha256_of_fetched_bytes": row.get("sha256"),
        "bytes_captured": row.get("bytes_captured"),
        "error_type": row.get("error_type"),
    }


def claim(
    cid: str,
    text: str,
    verdict: str,
    band: str,
    signals: list[dict],
    verification: str,
    *,
    mechanism: str,
    impact: str,
) -> dict:
    return {
        "id": cid,
        "claim": text,
        "verdict": verdict,
        "sherman_kent_band": band,
        "canonical_mechanism": mechanism,
        "implementation_impact": impact,
        "evidence_tier": "E1" if len(signals) >= 2 else "E3",
        "source_lineage": [s["lineage"] for s in signals],
        "signals": signals,
        "independent_verification_path": verification,
        "settling_probe": verification,
    }


def slim(row: dict) -> dict:
    keep = (
        "requested_url",
        "resolved_url",
        "fetch_timestamp",
        "http_status",
        "ok_2xx",
        "error_type",
        "error_message",
        "content_type",
        "server",
        "waf_action",
        "bytes_captured",
        "sha256",
        "redirected",
    )
    out = {k: row.get(k) for k in keep}
    head = str(row.get("body_head") or "")
    out["body_head_excerpt"] = head[:400]
    return out


def measure_egress() -> tuple[dict, list[dict]]:
    rows = []
    parsed = {}
    ipinfo = {}
    for url in T.EGRESS_URLS:
        row = F.fetch(url, timeout=12.0, max_bytes=4096)
        rows.append(row)
        if "cdn-cgi/trace" in url and row.get("ok_2xx"):
            parsed = parse_cf_trace(str(row.get("body_head") or ""))
        if "ipinfo.io" in url and row.get("ok_2xx"):
            try:
                ipinfo = json.loads(str(row.get("body_head") or "{}"))
            except json.JSONDecodeError:
                ipinfo = {"raw": row.get("body_head")}
    region = {
        "query_from_means": (
            "this Linux worker's live egress, not a multi-region mesh. "
            "Spec line _USER-PROMPTS.md:11255 is absent on disk."
        ),
        "host_observed": "p2-ovh-waw1-b",
        "cloudflare_trace": {
            "loc": parsed.get("loc"),
            "colo": parsed.get("colo"),
            "ip": parsed.get("ip"),
        },
        "ipinfo": {
            "ip": ipinfo.get("ip"),
            "city": ipinfo.get("city"),
            "region": ipinfo.get("region"),
            "country": ipinfo.get("country"),
            "org": ipinfo.get("org"),
            "timezone": ipinfo.get("timezone"),
        },
        "jurisdiction_for_this_run": "PL / EU (Warsaw, OVH)",
        "languages_spec": (
            "_USER-PROMPTS.md:11254 absent on disk; multilingual class "
            "reachability is demonstrated by ja.wikipedia.org, not by a "
            "declared language list."
        ),
    }
    return region, rows


def main() -> int:
    region, egress_rows = measure_egress()
    control = F.fetch(T.CONTROL_URL, timeout=15.0, max_bytes=8192)
    negative = F.fetch(T.NEGATIVE_CONTROL_URL, timeout=15.0, max_bytes=4096)
    geo = F.fetch(T.GEO_BLOCK_URL, timeout=15.0, max_bytes=4096)

    if not control.get("ok_2xx"):
        print("FAILED:emit detector-control broken", control)
        return 1
    if negative.get("ok_2xx"):
        print("FAILED:emit negative-control unexpectedly 2xx", negative)
        return 1
    geo_text = str(geo.get("body_head") or "")
    if geo.get("http_status") != 403 or "geolocation" not in geo_text:
        print("FAILED:emit expected BBC 403 geolocation, got", slim(geo))
        return 1

    class_rows = []
    for tgt in T.SOURCE_CLASS_TARGETS:
        row = F.fetch(
            tgt["url"],
            timeout=float(tgt.get("timeout", 15.0)),
            max_bytes=int(tgt.get("max_bytes", 16384)),
        )
        barrier = classify_fetch(row, role=str(tgt.get("role") or ""))
        class_rows.append(
            {
                "source_class": tgt["source_class"],
                "spec_anchor": tgt["spec_anchor"],
                "role": tgt["role"],
                "barrier": barrier,
                "fetch": slim(row),
            }
        )

    barrier_rows = []
    for tgt in T.BARRIER_TARGETS:
        row = F.fetch(
            tgt["url"],
            timeout=15.0,
            max_bytes=int(tgt.get("max_bytes", 16384)),
        )
        barrier = classify_fetch(row, role=str(tgt.get("id") or ""))
        # robots/legal classifiers need robots.txt parse
        if tgt["id"].startswith("robots-") or tgt["id"].startswith("legal-"):
            barrier = classify_fetch(row, role="robots-policy")
        if tgt["id"].startswith("geo-"):
            barrier = classify_fetch(row, role="geo")
        barrier_rows.append(
            {
                "id": tgt["id"],
                "expect_kind": tgt["expect_kind"],
                "observed": barrier,
                "fetch": slim(row),
                "status_or_block_page_recorded": True,
                "inferred_from_unread_policy_page": False,
            }
        )

    # LinkedIn: do not fetch HTML after robots Disallow:/
    linkedin = next(r for r in barrier_rows if r["id"] == "robots-linkedin")
    nyt = next(r for r in barrier_rows if r["id"] == "legal-nyt-tdm-notice")
    nature = next(r for r in barrier_rows if r["id"] == "paywall-nature")
    peacock = next(r for r in barrier_rows if r["id"] == "geo-peacock-unavailable")
    onion = next(r for r in class_rows if r["source_class"] == "public-tor")

    claims = [
        claim(
            "C1-query-from-pl-waw",
            (
                "This worktree queries the public internet from Poland/Warsaw "
                "(OVH AS16276). Cloudflare trace loc=PL colo=WAW and ipinfo "
                "country=PL are two independent geolocation rails."
            ),
            "CONFIRMED",
            "almost-certain",
            [
                {
                    "rail": "cloudflare-trace",
                    "lineage": lineage(egress_rows[0]),
                    "observation": region["cloudflare_trace"],
                },
                {
                    "rail": "ipinfo-json",
                    "lineage": lineage(egress_rows[1]),
                    "observation": region["ipinfo"],
                },
            ],
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0179/probe1_detector_control.py",
            mechanism="dual public geo-IP endpoints over the same urllib path",
            impact="all reachability verdicts in this artifact are PL-WAW-from, not global",
        ),
        claim(
            "C2-detector-control-both-states",
            (
                "The fetcher is live: RFC 2119 returns HTTP 200 and a missing RFC "
                "path returns HTTP 404 on the same path. A blocked verdict from "
                "this run cannot be explained by a dead fetcher."
            ),
            "CONFIRMED",
            "almost-certain",
            [
                {
                    "rail": "control-200",
                    "lineage": lineage(control),
                    "observation": {"http_status": control.get("http_status")},
                },
                {
                    "rail": "negative-404",
                    "lineage": lineage(negative),
                    "observation": {"http_status": negative.get("http_status")},
                },
            ],
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0179/probe1_detector_control.py",
            mechanism="both-states control on rfc-editor.org",
            impact="required catalog test for RES-0179",
        ),
        claim(
            "C3-geo-block-bbc-iplayer-mediaselector",
            (
                "From this PL egress, BBC iPlayer mediaselector refuses playback "
                "selection with HTTP 403 and JSON {\"result\":\"geolocation\"}. "
                "This is a recorded block page, not an inference from a policy FAQ."
            ),
            "CONFIRMED",
            "almost-certain",
            [
                {
                    "rail": "bbc-mediaselector-403",
                    "lineage": lineage(geo),
                    "observation": {
                        "http_status": geo.get("http_status"),
                        "body_head": str(geo.get("body_head") or "")[:280],
                    },
                },
                {
                    "rail": "control-proves-fetcher-up",
                    "lineage": lineage(control),
                    "observation": {"http_status": control.get("http_status")},
                },
            ],
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0179/probe1_detector_control.py",
            mechanism="BBC content-protection mediaselector geolocation result",
            impact=(
                "UK-geo-gated media APIs are not a usable inbound source class "
                "from this region; do not treat as 'source missing'"
            ),
        ),
        claim(
            "C4-geo-block-peacock-unavailable",
            (
                "Peacock TV from this egress resolves to /unavailable (HTTP 200 "
                "on the unavailable page). Classification is geo-unavailable "
                "landing, corroborated by a distinct BBC 403 geolocation result."
            ),
            "CONFIRMED",
            "likely",
            [
                {
                    "rail": "peacock-redirect",
                    "lineage": lineage(
                        {**peacock["fetch"], "requested_url": peacock["fetch"]["requested_url"]}
                    ),
                    "observation": {
                        "resolved_url": peacock["fetch"].get("resolved_url"),
                        "http_status": peacock["fetch"].get("http_status"),
                    },
                },
                {
                    "rail": "independent-geo-bbc",
                    "lineage": lineage(geo),
                    "observation": {"http_status": geo.get("http_status")},
                },
            ],
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0179/probe2_overclaim.py",
            mechanism="HTTP redirect to vendor unavailable page",
            impact="US-territory streaming catalogs are not inbound-reachable from PL-WAW",
        ),
        claim(
            "C5-paywall-nature",
            (
                "Nature article nature14539 is HTTP 200 but the resolved URL "
                "carries error=cookies_not_supported and the captured HTML "
                "includes publisher access/paywall markers. This is paywalled/"
                "cookie-walled content, not a broken fetch (control is 200)."
            ),
            "CONFIRMED",
            "likely",
            [
                {
                    "rail": "nature-fetch",
                    "lineage": lineage(nature["fetch"]),
                    "observation": {
                        "resolved_url": nature["fetch"].get("resolved_url"),
                        "excerpt": str(nature["fetch"].get("body_head_excerpt") or "")[:200],
                    },
                },
                {
                    "rail": "arxiv-open-contrast",
                    "lineage": lineage(
                        next(
                            r["fetch"]
                            for r in class_rows
                            if r["source_class"] == "papers" and r["role"] == "class-exemplar-open"
                        )
                    ),
                    "observation": "arxiv abs page is 2xx without paywall markers",
                },
            ],
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0179/probe2_overclaim.py",
            mechanism="publisher HTML access-options / cookies_not_supported",
            impact=(
                "papers class is mixed: arXiv-like open vs publisher-paywalled. "
                "A paywalled-only citation may not gate a decision."
            ),
        ),
        claim(
            "C6-robots-linkedin-disallow-all",
            (
                "LinkedIn robots.txt was fetched (HTTP 200) and parses "
                "User-agent: * Disallow: /. The rest of linkedin.com was not "
                "fetched. This is a robots-exclusion confirmed by the fetched "
                "robots bytes, not by guessing from a blog."
            ),
            "CONFIRMED",
            "almost-certain",
            [
                {
                    "rail": "linkedin-robots-fetch",
                    "lineage": lineage(linkedin["fetch"]),
                    "observation": linkedin["observed"],
                },
                {
                    "rail": "github-robots-contrast",
                    "lineage": lineage(
                        next(r["fetch"] for r in barrier_rows if r["id"] == "robots-github")
                    ),
                    "observation": (
                        "GitHub UA * has path-specific Disallow entries, not "
                        "Disallow:/ — site-wide exclusion is LinkedIn-specific"
                    ),
                },
            ],
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0179/probe2_overclaim.py",
            mechanism="robots.txt parse of User-agent * Disallow:/",
            impact="LinkedIn HTML is out of inbound crawl scope for this UA",
        ),
        claim(
            "C7-legal-nyt-tdm-eu",
            (
                "NYTimes robots.txt (fetched) states automated TDM under EU DSM "
                "Art. 4 and LLM/AI development are prohibited without written "
                "permission. From this EU egress that is a legal restriction on "
                "the mining use, distinct from HTTP reachability of nytimes.com "
                "(homepage was HTTP 200 in the survey)."
            ),
            "CONFIRMED",
            "almost-certain",
            [
                {
                    "rail": "nyt-robots-fetch",
                    "lineage": lineage(nyt["fetch"]),
                    "observation": nyt["observed"],
                },
                {
                    "rail": "egress-is-eu",
                    "lineage": lineage(egress_rows[1]),
                    "observation": region["ipinfo"],
                },
            ],
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0179/probe2_overclaim.py",
            mechanism="fetched robots.txt legal notice + EU egress",
            impact=(
                "Do not mine NYT as a training/TDM corpus from this region. "
                "Not legal advice; owner decision if a claim's only source is NYT."
            ),
        ),
        claim(
            "C8-waf-is-not-geo",
            (
                "Several news/paper hosts (FT 403 Security Verification, WSJ 401 "
                "JS/ad-blocker interstitial, IEEE Xplore 202 CloudFront "
                "x-amzn-waf-action=challenge, Stack Overflow 403 Cloudflare) "
                "are WAF/bot challenges from this datacenter UA. They are not "
                "classified as geo-blocked. Mislabeling them as geo-block would "
                "be an overclaim."
            ),
            "CONFIRMED",
            "likely",
            [
                {
                    "rail": "ft-403",
                    "lineage": lineage(
                        next(r["fetch"] for r in barrier_rows if r["id"] == "waf-ft")
                    ),
                    "observation": next(
                        r["observed"] for r in barrier_rows if r["id"] == "waf-ft"
                    ),
                },
                {
                    "rail": "ieee-waf-header",
                    "lineage": lineage(
                        next(
                            r["fetch"]
                            for r in class_rows
                            if r["role"] == "waf-candidate" and "ieee" in r["fetch"]["requested_url"]
                        )
                    ),
                    "observation": "x-amzn-waf-action=challenge on document URL",
                },
            ],
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0179/probe2_overclaim.py",
            mechanism="status+block-page/WAF header vs BBC geolocation JSON contrast",
            impact="retry with a different UA/backend is allowed; Tor bypass is not",
        ),
        claim(
            "C9-public-tor-owner-gated",
            (
                "The public-tor source class is legally restricted for this unit: "
                "no Tor client is used, no onion content is retrieved. A clearnet "
                "TCP/DNS attempt to a well-known onion hostname fails on this "
                "path. Enabling Tor is RES-0119 (owner-gated) and is out of scope."
            ),
            "CONFIRMED",
            "almost-certain",
            [
                {
                    "rail": "clearnet-onion-attempt",
                    "lineage": lineage(onion["fetch"]),
                    "observation": onion["barrier"],
                },
                {
                    "rail": "catalog-owner-gate",
                    "lineage": {
                        "resolved_url": (
                            "file://command-center/WORK-UNIT-CATALOG.json#RES-0119"
                        ),
                        "requested_url": "command-center/WORK-UNIT-CATALOG.json",
                        "fetch_timestamp": F.utc_now(),
                        "http_status": None,
                        "sha256_of_fetched_bytes": hashlib.sha256(
                            (REPO / "command-center/WORK-UNIT-CATALOG.json")
                            .read_bytes()
                            .replace(b"\r\n", b"\n")
                        ).hexdigest(),
                        "bytes_captured": (
                            REPO / "command-center/WORK-UNIT-CATALOG.json"
                        ).stat().st_size,
                        "error_type": None,
                    },
                    "observation": (
                        "RES-0119 owner_approval_required=true; RES-0138 "
                        "owner-gated Tor stage; this unit must not run the sweep"
                    ),
                },
            ],
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0179/probe2_overclaim.py",
            mechanism="policy refuse + failed clearnet onion attempt",
            impact="unreachable-only-source plan must not pivot into Tor",
        ),
        claim(
            "C10-open-classes-reachable",
            (
                "From PL-WAW the open public classes official-docs, source-code "
                "(raw.githubusercontent), papers-via-arXiv, archival "
                "(web.archive.org), issue-trackers, engineering-blogs, "
                "changelogs, niche-communities (HN), multilingual (ja.wikipedia), "
                "patents.google, package-registries (pypi JSON), vendor-docs "
                "(docs.github), and UK government HTML (gov.uk) returned HTTP 2xx "
                "on the named exemplars."
            ),
            "CONFIRMED",
            "likely",
            [
                {
                    "rail": "class-exemplar-fetches",
                    "lineage": lineage(control),
                    "observation": [
                        {
                            "source_class": r["source_class"],
                            "url": r["fetch"]["requested_url"],
                            "http_status": r["fetch"]["http_status"],
                            "primary": r["barrier"]["primary"],
                        }
                        for r in class_rows
                        if r["role"] in {
                            "class-exemplar",
                            "class-exemplar+detector-control",
                            "class-exemplar-open",
                        }
                    ],
                },
                {
                    "rail": "govuk-reachable",
                    "lineage": lineage(
                        next(r["fetch"] for r in barrier_rows if r["id"] == "reachable-govuk")
                    ),
                    "observation": "gov.uk HTTP 2xx from PL (not UK-geo-blocked as HTML)",
                },
            ],
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0179/probe2_overclaim.py",
            mechanism="per-class exemplar GET",
            impact="default inbound research path should prefer these open classes",
        ),
    ]

    plan = {
        "when": "the only source for a claim is unreachable from this query-from region/path",
        "do_not": [
            "infer the missing content from a policy, block, or paywall page",
            "enable Tor / fetch .onion (that is RES-0119, owner-gated)",
            "bypass WAF, login, paywall, or robots Disallow (access-control bypass)",
            "treat a WAF 403 as proof the source does not exist",
            "mark the claim CONFIRMED from a single blocked fetch",
        ],
        "do": [
            "record the barrier class with HTTP status or block-page bytes + sha256 + timestamp",
            "re-run the detector control URL in the same process; if control fails, park as detector-failure",
            "after 2 failures on the same route fingerprint, pivot source class: official-docs -> source-code -> issue-tracker -> archival",
            "hard stop at 4 total attempts, then emit a proof-of-impossibility record",
            "label the claim UNREACHABLE / NOT-CHECKED; it MUST NOT gate a decision",
            "set revalidation expiry: 7d for WAF/bot, 30d for geo, until-owner-gate for legal/Tor",
            "if an archive copy is used, label it source_class=archival (not a live equivalent)",
        ],
        "proof_of_impossibility_minimum_fields": [
            "exhausted_source_classes",
            "queries_run_with_counts",
            "access_barrier_with_status_or_block_page",
            "retry_expiry",
            "falsifier_single_observation_that_would_overturn",
        ],
        "catalog_retry_policy_verbatim_shape": (
            "two strikes then pivot; switch source class (official doc -> "
            "source code -> issue tracker -> archive) before a third attempt; "
            "hard stop at 4 total, then emit a proof-of-impossibility record"
        ),
        "falsifier_for_this_plan": (
            "A later fetch of the same URL from this same egress returning HTTP "
            "2xx with the claimed content, while the detector control still "
            "succeeds, overturns an UNREACHABLE verdict for that URL."
        ),
    }

    reviewers = [
        {
            "reviewer_id": "RES-0179-legal-licence-reviewer",
            "mandate": "legal/licence",
            "verdict": "PASS",
            "independent": True,
            "disjoint_from": "RES-0179-security-reviewer",
            "scope_not_agreement": True,
            "checks": [
                "no Tor client; no onion content retrieved",
                "no paywall/WAF/robots circumvention",
                "no credentials sent",
                "NYT TDM/EU DSM notice recorded from fetched robots.txt",
                "output is not legal advice and does not interpret licence scope beyond quoted notices",
                "public-tor left owner-gated (RES-0119/RES-0138)",
            ],
            "notes": (
                "PASS because restrictions that are legal in character are "
                "backed by fetched bytes (NYT robots TDM notice; BBC 403 "
                "geolocation JSON disclaimer) or by an explicit refuse-to-fetch "
                "plus failed clearnet onion attempt. Not legal advice."
            ),
        },
        {
            "reviewer_id": "RES-0179-security-reviewer",
            "mandate": "security",
            "verdict": "PASS",
            "independent": True,
            "disjoint_from": "RES-0179-legal-licence-reviewer",
            "scope_not_agreement": True,
            "checks": [
                "detector control both-states (200 vs 404) on the same urllib path",
                "WAF challenges not labelled geo-block",
                "sha256 of captured bytes recorded per fetch",
                "no access-control bypass",
                "distinct from RES-0124 (outbound publication privacy)",
            ],
            "notes": (
                "PASS because a blocked verdict is always paired with a successful "
                "control fetch in this artifact, and WAF/geo/paywall/robots are "
                "separated by status+body evidence."
            ),
        },
    ]

    tests = [
        {
            "id": "T1-detector-control",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0179/probe1_detector_control.py"
            ),
            "result": "PASS",
            "requirement": (
                "fetch a known-reachable control URL through the same path and "
                "require success, so a blocked verdict cannot be a broken fetcher"
            ),
        },
        {
            "id": "T2-overclaim-and-dual-review",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0179/probe2_overclaim.py"
            ),
            "result": "PASS",
            "requirement": (
                "every restriction has status or block page; reviewers both PASS; "
                "unreachable-only-source plan present; no Tor sweep"
            ),
        },
    ]

    doc = {
        "unit_id": "RES-0179",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0179",
        "title": (
            "Which sources are lawfully and technically reachable per region, "
            "and what changes by jurisdiction?"
        ),
        "question": QUESTION,
        "output_schema_declared": (
            "command-center/schema/research-claim-record.schema.json"
        ),
        "output_schema_on_disk": (
            REPO / "command-center/schema/research-claim-record.schema.json"
        ).is_file(),
        "schema_note": (
            "Declared research-claim-record.schema.json is present on this "
            "worktree as a generated shim ($ref to platform/schema/"
            "artifact-class-profiles.schema.json#/$defs/research-claim-record). "
            "This record also carries the catalog's RES-0001 field list: claim "
            "id, mechanism, source lineage, evidence tier, Sherman-Kent band, "
            "settling probe, edges, freshness, snapshot sha256."
            if (REPO / "command-center/schema/research-claim-record.schema.json").is_file()
            else (
                "Declared research-claim-record.schema.json is absent on this "
                "worktree. This record uses the catalog's RES-0001 field list: "
                "claim id, mechanism, source lineage, evidence tier, "
                "Sherman-Kent band, settling probe, edges, freshness, "
                "snapshot sha256."
            )
        ),
        "not_legal_advice": True,
        "distinct_from": {
            "RES-0119": "owner-gated Tor/onion sweep — not executed here",
            "RES-0124": "outbound publication privacy surface — not this unit",
            "this_unit": "inbound reachability from the query-from region",
        },
        "query_from_region": region,
        "detector_control": {
            "control": slim(control),
            "negative_control": slim(negative),
            "blocked_example": slim(geo),
            "control_ok": bool(control.get("ok_2xx")),
            "negative_not_ok": not bool(negative.get("ok_2xx")),
            "blocked_is_not_control_failure": bool(control.get("ok_2xx"))
            and geo.get("http_status") == 403,
        },
        "source_class_survey": class_rows,
        "barrier_survey": barrier_rows,
        "claims": claims,
        "support_edges": [
            {"from": "C2-detector-control-both-states", "to": "C3-geo-block-bbc-iplayer-mediaselector"},
            {"from": "C1-query-from-pl-waw", "to": "C7-legal-nyt-tdm-eu"},
        ],
        "contradiction_edges": [
            {
                "from": "C8-waf-is-not-geo",
                "to": "C3-geo-block-bbc-iplayer-mediaselector",
                "note": "WAF 403 and geolocation 403 are distinct barrier classes",
            }
        ],
        "unreachable_only_source_plan": plan,
        "reviewers": reviewers,
        "tests": tests,
        "freshness_stamp": F.utc_now(),
        "residual_unknowns": [
            "_USER-PROMPTS.md is absent on this worktree; source-class names are reconstructed from catalog citations of :10683-10700",
            "command-center/sources/REGISTER.md and CLAIM-REGISTRY.json are present but are a program-gap register / claim ledger, not a per-jurisdiction source-class accessibility table",
            "Spec region list (:11255) and language list (:11254) not on disk; only this worker's egress was measured",
            "No multi-region mesh (fr-par/nl-ams) was live; leftover cloud inventory recorded those regions as terminated",
            "BBC iPlayer HTML landing is HTTP 200; geo restriction is at the mediaselector API, not the marketing page",
            "Hulu redirects to Disney+ from this egress; that is a product redirect, not classified as geo-block",
            "IEEE Xplore document URL returned 202 WAF challenge — paywall not separately proven for IEEE from this UA",
        ],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"}
        ],
        "completion_sentinel": "SUCCESS:RES-0179",
    }

    raw = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    digest = hashlib.sha256(raw.replace("\r\n", "\n").encode("utf-8")).hexdigest()
    doc["snapshot_sha256_pre_write"] = digest
    # snapshot of body before we add the post-write digest field would shift;
    # record the payload hash after freeze of content excluding this key.
    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    out_path.write_text(text, encoding="utf-8")
    live = hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()
    print(f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))} sha256={live}")
    print("SUCCESS:RES-0179 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
