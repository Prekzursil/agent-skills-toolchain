"""Local replicas of registry identity/namespace mechanics plus bypass cases.

Ultranormalize matches warehouse migration d18d443f89f0 (captured).
Prefix matching follows PEP 752 hyphenated-child semantics.
These functions are the executable half of the reviewer bypasses.
"""
from __future__ import annotations

import re


def ultranormalize_name(name: str) -> str:
    """Replica of warehouse SQL ultranormalize_name (d18d443f89f0)."""
    s = re.sub(r"[._-]", "", name, flags=re.IGNORECASE)
    s = re.sub(r"[lLiI]", "1", s)
    s = re.sub(r"[oO]", "0", s)
    return s.lower()


def pep503_canonicalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_npm_scope(name: str) -> dict:
    if name.startswith("@") and "/" in name[1:]:
        scope, local = name[1:].split("/", 1)
        return {
            "name": name,
            "scoped": True,
            "scope": scope,
            "local": local,
            "well_formed": bool(scope) and bool(local),
        }
    return {
        "name": name,
        "scoped": False,
        "scope": None,
        "local": name,
        "well_formed": bool(name) and not name.startswith("@"),
    }


def matches_reserved_prefix(name: str, prefix: str) -> bool:
    """PEP 752-style: child names are prefix + hyphen + rest; parent equals prefix stem."""
    p = prefix.lower()
    if not p.endswith("-"):
        p = p + "-"
    n = name.lower()
    return n == p[:-1] or n.startswith(p)


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins, delete, sub = cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def similar_name_blocked(existing: str, candidate: str) -> bool:
    return ultranormalize_name(existing) == ultranormalize_name(candidate)


def ultranormalize_cases() -> list[dict]:
    """Positive and negative controls for the blocking similar-name gate."""
    rows = [
        ("py-foo", "pyfo0", True, "separator-strip plus o->0"),
        ("pip", "p1p", True, "i->1 homoglyph"),
        ("example", "examp1e", True, "l->1 / 1 collision"),
        ("example", "exampie", True, "i->1 / l->1 collision"),
        ("requests", "requets", False, "single deletion is not an ultranormalize hit"),
        ("numpy", "nunpy", False, "n/m substitution is not l/i/o"),
        ("pydantic", "pydantic2", False, "trailing digit documented miss (warehouse#17774)"),
        ("google-cloud", "googlecloud", True, "hyphen stripped; not the same as prefix match"),
    ]
    out = []
    for existing, candidate, want, why in rows:
        got = similar_name_blocked(existing, candidate)
        out.append(
            {
                "existing": existing,
                "candidate": candidate,
                "ultranormalize_existing": ultranormalize_name(existing),
                "ultranormalize_candidate": ultranormalize_name(candidate),
                "blocked": got,
                "expected_blocked": want,
                "ok": got is want,
                "why": why,
            }
        )
    return out


def prefix_cases() -> list[dict]:
    prefix = "google-cloud-"
    rows = [
        ("google-cloud-compute", True, "hyphenated child"),
        ("google-cloud", True, "parent stem"),
        ("googlecloud-compute", False, "missing hyphen boundary"),
        ("google-cloudcompute", False, "child not split on reserved hyphen"),
        ("not-google-cloud-foo", False, "prefix is not a substring grant"),
        ("google-cloud-compute-extra", True, "deeper child still matches"),
    ]
    out = []
    for name, want, why in rows:
        got = matches_reserved_prefix(name, prefix)
        out.append(
            {
                "name": name,
                "prefix": prefix,
                "matches": got,
                "expected": want,
                "ok": got is want,
                "why": why,
            }
        )
    return out


def scope_cases() -> list[dict]:
    rows = [
        ("@sindresorhus/is", True, "sindresorhus", "is"),
        ("@types/node", True, "types", "node"),
        ("@acme-corp/sdk", True, "acme-corp", "sdk"),
        ("lodash", False, None, "lodash"),
        ("@incomplete", False, None, "@incomplete"),
    ]
    out = []
    for name, scoped, scope, local in rows:
        got = parse_npm_scope(name)
        ok = (
            got["scoped"] is scoped
            and got["scope"] == scope
            and got["local"] == local
        )
        out.append({**got, "expected_scoped": scoped, "ok": ok})
    return out


def bypass_attempts() -> list[dict]:
    """Reviewer constructions against every automatable mitigation."""
    squat = parse_npm_scope("@acme-corp/sdk")
    oidc_lookalike = {
        "package": "acme-official-sdk",
        "trusted_publisher": {
            "idp": "github-actions",
            "repository": "attacker-org/acme-official-sdk",
            "workflow": "release.yml",
        },
        "proves_legal_entity": False,
        "npm_verifies_config_at_save": False,
    }
    prefix_skip = {
        "reserved": "google-cloud-",
        "blocked_name": "google-cloud-compute",
        "bypass_name": "googlecloud-compute",
        "blocked": matches_reserved_prefix("google-cloud-compute", "google-cloud-"),
        "bypass_blocked": matches_reserved_prefix("googlecloud-compute", "google-cloud-"),
    }
    typo_miss = {
        "popular": "requests",
        "levenshtein_1": "requets",
        "distance": levenshtein("requests", "requets"),
        "ultranormalize_blocks": similar_name_blocked("requests", "requets"),
        "trailing_digit": {
            "popular": "pydantic",
            "candidate": "pydantic2",
            "ultranormalize_blocks": similar_name_blocked("pydantic", "pydantic2"),
        },
    }
    dns_only_badge = {
        "domain": "acme-official.example",
        "txt_record_proves": "control of that domain",
        "txt_record_does_not_prove": "legal identity of Acme Corp",
        "staff_review_required_for_reputation": True,
    }
    return [
        {
            "id": "BX-D1-SCOPE-SQUAT",
            "target": "D1-scoped-names",
            "mitigation": "scoped names as account-owned namespaces",
            "construction": (
                "Register the unused scope @acme-corp and publish @acme-corp/sdk. "
                "Scope ACL only checks membership of that scope; it does not ask "
                "whether the registrant is Acme Corp."
            ),
            "payload": squat,
            "bypasses_stated_goal": "impersonation of an unclaimed brand namespace",
            "bypasses": True,
            "still_holds": "an outsider still cannot publish inside an already-owned scope",
            "effective_if_recorded_as": "intra-scope publish ACL, not trademark protection",
        },
        {
            "id": "BX-D2-OIDC-NOT-LEGAL-ID",
            "target": "D2-verified-publishers-oidc",
            "mitigation": "OIDC trusted publishing",
            "construction": (
                "Bind a trusted publisher to an attacker-controlled CI repo whose "
                "package name resembles a vendor. OIDC authenticates the IdP identity "
                "in the preconfigured trust policy; it does not attest a legal entity. "
                "npm's own docs state the trusted-publisher config is not verified at save."
            ),
            "payload": oidc_lookalike,
            "bypasses_stated_goal": "verified publisher means this is the real vendor",
            "bypasses": True,
            "still_holds": "publish still requires a matching OIDC token for that policy",
            "effective_if_recorded_as": "CI-to-package cryptographic binding, not a brand badge",
        },
        {
            "id": "BX-D3-DNS-WITHOUT-STAFF",
            "target": "D3-verified-publishers-identity-badge",
            "mitigation": "domain TXT plus reputation badge",
            "construction": (
                "Prove TXT on a lookalike domain. The automatable step only proves "
                "DNS control. VS Code's remaining checks are legitimacy/reputation "
                "review by the Marketplace team within 5 business days."
            ),
            "payload": dns_only_badge,
            "bypasses_stated_goal": "staffless verified-publisher badge",
            "bypasses": True,
            "still_holds": "none, if the badge is issued from DNS alone",
            "effective_if_recorded_as": "not effective as a staffless identity defense",
        },
        {
            "id": "BX-D4-HYPHEN-BOUNDARY",
            "target": "D4-reserved-prefixes-enforcement",
            "mitigation": "hyphenated prefix reservation (PEP 752 / NuGet)",
            "construction": (
                "Publish googlecloud-compute against a grant on google-cloud-. "
                "The reserved-namespace matcher keys off the hyphenated prefix, "
                "not ultranormalize equivalence."
            ),
            "payload": prefix_skip,
            "bypasses_stated_goal": "all names that look like google-cloud-*",
            "bypasses": True,
            "still_holds": "hyphenated children of the reserved prefix are rejected",
            "effective_if_recorded_as": "hyphen-prefix ACL after a grant exists",
        },
        {
            "id": "BX-D6-TYPO-GAPS",
            "target": "D6-typo-distance-ultranormalize-block",
            "mitigation": "ultranormalize similar-name reject",
            "construction": (
                "Use requets (Levenshtein 1 vs requests) or pydantic2 (trailing digit). "
                "Neither collides under ultranormalize, so check_project_name's "
                "similar-name raise does not fire."
            ),
            "payload": typo_miss,
            "bypasses_stated_goal": "block all typo-distance impersonation of popular names",
            "bypasses": True,
            "still_holds": "homoglyph/separator collisions such as pip/p1p still reject",
            "effective_if_recorded_as": "homoglyph+separator equivalence class only",
        },
        {
            "id": "BX-D7-QUEUE-IS-NOT-A-GATE",
            "target": "D7-typo-distance-async-admin-queue",
            "mitigation": "TypoSnyper post-create admin observation",
            "construction": (
                "Create the project. warehouse.packaging.tasks.typo_check_project_name "
                "runs after commit and records an observation only; captured source "
                "says nothing about the project's lifecycle changes."
            ),
            "payload": {
                "lifecycle_changes": False,
                "admin_review_required_for_action": True,
            },
            "bypasses_stated_goal": "staffless publish-time typo blocking",
            "bypasses": True,
            "still_holds": "none as a gate; it is a review ticket generator",
            "effective_if_recorded_as": "not effective without review staff",
        },
    ]


def self_test() -> dict:
    u_cases = ultranormalize_cases()
    p_cases = prefix_cases()
    s_cases = scope_cases()
    bx = bypass_attempts()
    return {
        "ultranormalize_cases": u_cases,
        "prefix_cases": p_cases,
        "scope_cases": s_cases,
        "bypass_attempts": bx,
        "ultranormalize_ok": all(r["ok"] for r in u_cases),
        "prefix_ok": all(r["ok"] for r in p_cases),
        "scope_ok": all(r["ok"] for r in s_cases),
        "bypass_count": len(bx),
        "automatable_bypasses_that_land": [
            b["id"] for b in bx if b["bypasses"]
        ],
    }
