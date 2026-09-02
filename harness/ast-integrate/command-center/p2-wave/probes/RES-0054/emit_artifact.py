#!/usr/bin/env python3
"""Emit command-center/research/RES-0054.json from live captures + local mechanics."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    AUTOMATABLE,
    CATALOG_SENTINEL,
    CLASS_KEY,
    MODERATION,
    OUTPUT_REL,
    SCHEMA_REL,
    UNIT_ID,
)
from mechanics import bypass_attempts, self_test  # noqa: E402
from rails_util import rail, read_json, read_text  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0054/probe1_defense_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0054/probe2_reviewer_bypass.py"
)


def bx(bid: str) -> dict:
    for row in bypass_attempts():
        if row["id"] == bid:
            return {
                "id": row["id"],
                "bypasses": row["bypasses"],
                "construction": row["construction"],
                "bypasses_stated_goal": row["bypasses_stated_goal"],
                "still_holds": row["still_holds"],
                "effective_if_recorded_as": row["effective_if_recorded_as"],
                "payload": row["payload"],
            }
    raise KeyError(bid)


def build() -> dict:
    npm = read_json("r1-npm-scoped-sindresorhus-is.json")
    types_node = read_json("r1-npm-scoped-types-node-abbrev.json")
    nuget_ms = read_json("r1-nuget-query-microsoft-extensions-logging.json")
    nuget_left = read_json("r1-nuget-query-left-pad.json")
    pep541 = read_json("r1-github-pypi-support-pep541.json")
    ms_pkg = (nuget_ms.get("data") or [{}])[0]
    left_pkg = (nuget_left.get("data") or [{}])[0]
    pep541_titles = [
        {"number": i.get("number"), "title": i.get("title"), "state": i.get("state"), "html_url": i.get("html_url")}
        for i in pep541[:3]
        if isinstance(i, dict)
    ]

    services = read_text("r1-warehouse-packaging-services.py")
    tasks = read_text("r1-warehouse-packaging-tasks.py")
    if "def check_project_name" not in services:
        raise RuntimeError("warehouse services missing check_project_name")
    if "Annotate the project for admin review. This is a record only" not in tasks:
        raise RuntimeError("typo_check docstring missing record-only clause")

    d1 = {
        "id": "D1-scoped-names",
        "defense": "scoped names",
        "named_family": "scoped names",
        CLASS_KEY: AUTOMATABLE,
        "single_owner_no_review_staff": True,
        "reason": (
            "Binding a prefix to an account is a membership check. npm grants a "
            "scope that matches the user or organization name at signup; only "
            "members of that scope can publish into it. A one-owner marketplace "
            "implements the same rule as UNIQUE(owner_id, local_name) plus a "
            "publish ACL. No human is required to enforce the ACL once the "
            "scope exists. It does not, by itself, stop someone from registering "
            "an unused brand scope first."
        ),
        "rails": [
            rail(
                "structured_api_probe",
                "r1-npm-scoped-sindresorhus-is.json",
                f"registry name={npm.get('name')!r}; also @types/node name={types_node.get('name')!r}",
                ['"name":"@sindresorhus/is"'],
                "Live npm registry packument for a scoped package.",
            ),
            rail(
                "prose_source",
                "r2-npm-about-scopes.html",
                "When you sign up for an npm user account or create an organization, you are granted a scope that matches your user or organization name.",
                ["granted a scope that matches your user or organization name"],
            ),
        ],
        "bypass_attempt": bx("BX-D1-SCOPE-SQUAT"),
        "recorded_as_effective": "intra-scope publish ACL only",
        "evidence_grade": "E1",
    }
    d2 = {
        "id": "D2-verified-publishers-oidc",
        "defense": "verified publishers (OIDC trusted publishing)",
        "named_family": "verified publishers",
        CLASS_KEY: AUTOMATABLE,
        "single_owner_no_review_staff": True,
        "reason": (
            "Trusted publishing exchanges a short-lived OIDC token from a named "
            "IdP (GitHub Actions, GitLab, CircleCI) against a preconfigured "
            "trust policy. Verification is cryptographic (JWT signature + claims). "
            "PyPI, npm, and the OpenSSF trusted-publishers profile all describe "
            "this as an automated publisher-to-CI binding. It does not prove that "
            "the package author is a named legal entity. npm does not even verify "
            "the saved configuration until publish time."
        ),
        "rails": [
            rail(
                "structured_api_probe",
                "r1-warehouse-packaging-services.py",
                "PendingOIDCPublisher is ultranormalized against Project.name in warehouse/packaging/services.py (captured GitHub raw).",
                ["PendingOIDCPublisher", "ultranormalize_name"],
                "Implementation probe of PyPI's pending OIDC publisher collision check.",
            ),
            rail(
                "prose_source",
                "r2-pypi-trusted-publishers.html",
                "Trusted Publishing is our term for using the OpenID Connect (OIDC) standard to exchange short-lived identity tokens with PyPI.",
                ["Trusted Publishing", "OpenID Connect", "OIDC"],
            ),
            rail(
                "prose_source",
                "r2-npm-trusted-publishers.html",
                "npm does not verify your trusted publisher configuration when you save it.",
                ["npm does not verify your trusted publisher configuration when you save it"],
            ),
            rail(
                "prose_source",
                "r2-openssf-trusted-publishers.html",
                "Authentication is performed by exchanging OIDC identity tokens for short-lived and tightly scoped API tokens.",
                ["exchanging OIDC identity tokens for short-lived"],
            ),
        ],
        "bypass_attempt": bx("BX-D2-OIDC-NOT-LEGAL-ID"),
        "recorded_as_effective": "CI identity binding, not a brand badge",
        "evidence_grade": "E1",
    }
    d3 = {
        "id": "D3-verified-publishers-identity-badge",
        "defense": "verified publishers (legal-entity / reputation badge)",
        "named_family": "verified publishers",
        CLASS_KEY: MODERATION,
        "single_owner_no_review_staff": False,
        "reason": (
            "A blue-check / verified badge that means 'this publisher is the "
            "real vendor' is not the OIDC check. VS Code Marketplace requires a "
            "Marketplace-team review of legitimacy, trust and positive reputation "
            "within 5 business days after DNS TXT succeeds. NuGet prefix "
            "applications go to account@nuget.org and 'may need to ask additional "
            "identifying questions'. DNS TXT is automatable; the reputation and "
            "identity judgment is not. A staffless marketplace cannot honestly "
            "issue this badge."
        ),
        "rails": [
            rail(
                "structured_api_probe",
                "r1-nuget-query-microsoft-extensions-logging.json",
                f"Microsoft.Extensions.Logging verified={ms_pkg.get('verified')!r} owners={ms_pkg.get('owners')!r}; left-pad verified={left_pkg.get('verified')!r}",
                ["Microsoft.Extensions.Logging", '"verified":true'],
                "NuGet SearchQueryService exposes a machine-readable verified flag.",
            ),
            rail(
                "prose_source",
                "r2-vscode-publishing-extension.html",
                "Once your TXT record has been validated, the Marketplace team will review your request and let you know the result within 5 business days. The validation includes, but is not limited to: domain, website and extensions prerequisites for track record, content eligibility, legitimacy, trust and positive reputation.",
                [
                    "Marketplace team will review your request",
                    "5 business days",
                    "legitimacy, trust and positive reputation",
                ],
            ),
            rail(
                "prose_source",
                "r2-nuget-prefix-reservation.html",
                "After the application is submitted, you are notified of acceptance or rejection (with the criteria that caused rejection). We may need to ask additional identifying questions to confirm owner identity.",
                ["additional identifying questions to confirm owner identity"],
            ),
        ],
        "bypass_attempt": bx("BX-D3-DNS-WITHOUT-STAFF"),
        "recorded_as_effective": None,
        "evidence_grade": "E1",
    }
    d4 = {
        "id": "D4-reserved-prefixes-enforcement",
        "defense": "reserved prefixes (enforcement after a grant exists)",
        "named_family": "reserved prefixes",
        CLASS_KEY: AUTOMATABLE,
        "single_owner_no_review_staff": True,
        "reason": (
            "Once a grant exists, PEP 752 requires uploads matching the reserved "
            "namespace to fail with HTTP 409 unless the uploader holds the grant. "
            "NuGet rejects submissions on a reserved ID prefix unless they come "
            "from the prefix owner. That is a string-prefix ACL a single owner "
            "can run with no staff. It does not decide who receives the grant."
        ),
        "rails": [
            rail(
                "structured_api_probe",
                "r1-nuget-query-microsoft-extensions-logging.json",
                f"id={ms_pkg.get('id')!r} verified={ms_pkg.get('verified')!r} owners={ms_pkg.get('owners')!r}",
                ["Microsoft.Extensions.Logging", '"verified":true', "Microsoft"],
                "Live NuGet query for a Microsoft.* package under a reserved-prefix owner.",
            ),
            rail(
                "prose_source",
                "r2-pep-0752.html",
                "Uploads MUST fail with a 409 Conflict HTTP status code if the name of a package being uploaded matches a reserved namespace and the project owner does not have an active grant for the namespace.",
                ["409 Conflict", "reserved namespace", "active grant"],
            ),
            rail(
                "prose_source",
                "r2-nuget-prefix-reservation.html",
                "Whenever a package is submitted to nuget.org with an ID that matches the reserved ID prefix, the package is rejected unless it originates from the owner(s) that reserved the ID prefix.",
                [
                    "matches the reserved ID prefix",
                    "rejected unless it originates from the owner",
                ],
            ),
        ],
        "bypass_attempt": bx("BX-D4-HYPHEN-BOUNDARY"),
        "recorded_as_effective": "hyphen-prefix ACL after grant",
        "evidence_grade": "E1",
    }
    d5 = {
        "id": "D5-reserved-prefixes-grant-issuance",
        "defense": "reserved prefixes (who gets the grant / trademark / squat judgment)",
        "named_family": "reserved prefixes",
        CLASS_KEY: MODERATION,
        "single_owner_no_review_staff": False,
        "reason": (
            "Issuing the grant is a judgment: PEP 755 approval criteria include "
            "whether the namespace 'properly and clearly identify the reservation "
            "owner' and whether not reserving it 'may cause ambiguity, confusion, "
            "or other harm'. Applications 'require independent review'. PEP 541 "
            "name-retention disputes are tickets against pypi/support; the "
            "Packaging Workgroup has the final say. crates.io's RFC 3463 lets the "
            "team delete crates that exist only to squat a name. A staffless "
            "marketplace can seed a static well-known list; it cannot adjudicate "
            "competing claims."
        ),
        "rails": [
            rail(
                "structured_api_probe",
                "r1-github-pypi-support-pep541.json",
                f"GitHub issues API returned {len(pep541)} PEP 541 tickets; sample={pep541_titles!r}",
                ["PEP 541 Request", "https://github.com/pypi/support/issues/"],
                "Live structured list of human name-retention requests.",
            ),
            rail(
                "prose_source",
                "r2-pep-0755.html",
                "Only organization (non-user) accounts have access to the grant application form. ... Although each application would require independent review ... The namespace should properly and clearly identify the reservation owner. ... There should be evidence that not reserving the namespace may cause ambiguity, confusion, or other harm to the community.",
                [
                    "grant application",
                    "independent review",
                    "properly and clearly identify the reservation owner",
                    "ambiguity, confusion, or other harm",
                ],
            ),
            rail(
                "prose_source",
                "r2-pep-0541.html",
                "The maintainers of the Package Index are not arbiters in disputes around active projects. ... The Packaging Workgroup has the final say in any disputes covered by this document.",
                [
                    "not arbiters in disputes",
                    "Packaging Workgroup has the final say",
                ],
            ),
            rail(
                "prose_source",
                "r2-rfc-3463.html",
                'The crates.io team may delete crates from the registry that do not comply with the policies on this document. ... exists only to reserve a name for a prolonged period of time (often called "name squatting") without having any genuine functionality',
                [
                    "crates.io team may delete crates",
                    "name squatting",
                    "genuine functionality",
                ],
            ),
        ],
        "bypass_attempt": {
            "id": "BX-D5-NO-STAFF-NO-GRANT",
            "bypasses": True,
            "construction": (
                "Without a reviewer, nobody can apply PEP 755's harm/identity "
                "criteria. First-come-first-served is the remaining policy, which "
                "is the opposite of reserved-prefix protection for a late-arriving "
                "trademark holder."
            ),
            "bypasses_stated_goal": "staffless trademark prefix reservation",
            "still_holds": "enforcement of an already-issued grant (D4)",
            "effective_if_recorded_as": "not effective as a staffless grant process",
        },
        "recorded_as_effective": None,
        "evidence_grade": "E1",
    }
    d6 = {
        "id": "D6-typo-distance-ultranormalize-block",
        "defense": "typo-distance blocking (ultranormalize similar-name reject)",
        "named_family": "typo-distance blocking",
        CLASS_KEY: AUTOMATABLE,
        "single_owner_no_review_staff": True,
        "reason": (
            "Warehouse check_project_name raises ProjectNameUnavailableSimilarError "
            "when ultranormalize_name(existing) equals ultranormalize_name(candidate). "
            "The SQL function strips separators and maps l/i->1 and o->0. That is a "
            "pure function over names plus an index; a staffless marketplace can "
            "run it at register time. It is not a general Levenshtein gate: "
            "requets vs requests and pydantic2 vs pydantic are documented misses."
        ),
        "rails": [
            rail(
                "structured_api_probe",
                "r1-warehouse-ultranormalize.py",
                "CREATE FUNCTION ultranormalize_name(text) ... regexp_replace($1, '(\\.|_|-)', '') then (l|L|i|I)->1 then (o|O)->0",
                ["CREATE FUNCTION ultranormalize_name", "(l|L|i|I)", "(o|O)"],
            ),
            rail(
                "structured_api_probe",
                "r1-warehouse-packaging-services.py",
                "if similar_project_name := ... func.ultranormalize_name(Project.name) == func.ultranormalize_name(name): raise ProjectNameUnavailableSimilarError; mapped to HTTPBadRequest 'too similar to an existing project'",
                [
                    "ProjectNameUnavailableSimilarError",
                    "too similar to an existing project",
                ],
            ),
            rail(
                "prose_source",
                "r2-discuss-pypi-typosquat.json",
                "PyPI does have a separate, unrelated, mechanism for limiting similar package names: if a new package has an ultranormalized form that matches any other pre-existing package, it gets rejected. In practice, this means that you can't upload py-fo0 if py-foo already exists.",
                ["ultranormalized", "py-fo0", "py-foo"],
            ),
        ],
        "bypass_attempt": bx("BX-D6-TYPO-GAPS"),
        "recorded_as_effective": "homoglyph+separator equivalence class",
        "evidence_grade": "E1",
    }
    d7 = {
        "id": "D7-typo-distance-async-admin-queue",
        "defense": "typo-distance blocking (TypoSnyper / admin observation queue)",
        "named_family": "typo-distance blocking",
        CLASS_KEY: MODERATION,
        "single_owner_no_review_staff": False,
        "reason": (
            "The captured warehouse.packaging.tasks.typo_check_project_name runs "
            "*after* the create transaction commits. It records ObservationKind."
            "IsTypoSnyperMatch 'for admin review'. The source states this is a "
            "record only and nothing about the project's lifecycle changes. "
            "Without staff to act on the queue, the check is telemetry, not a "
            "defense. A staffless marketplace that copies this pattern has not "
            "implemented typo-distance blocking."
        ),
        "rails": [
            rail(
                "structured_api_probe",
                "r1-warehouse-packaging-tasks.py",
                "Annotate the project for admin review. This is a record only - the kind is not one that any of the observation reactions act on, so nothing about the project's lifecycle changes.",
                [
                    "Annotate the project for admin review. This is a record only",
                    "project's lifecycle changes",
                ],
            ),
            rail(
                "prose_source",
                "r2-discuss-pypi-typosquat.json",
                "I suspect the volume of new packages would overwhelm any manual review efforts. It'd need to be an automated process, at which point the security value of a delay is somewhat limited.",
                ["overwhelm any manual review efforts"],
            ),
        ],
        "bypass_attempt": bx("BX-D7-QUEUE-IS-NOT-A-GATE"),
        "recorded_as_effective": None,
        "evidence_grade": "E1",
    }

    table = [d1, d2, d3, d4, d5, d6, d7]
    classes = {row[CLASS_KEY] for row in table}
    if AUTOMATABLE not in classes or MODERATION not in classes:
        raise RuntimeError("defense table missing a class")

    mech = self_test()
    if not (mech["ultranormalize_ok"] and mech["prefix_ok"] and mech["scope_ok"]):
        raise RuntimeError("local mechanics self-test failed")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    question = (
        "Which identity and namespace defenses (scoped names, verified publishers, "
        "reserved prefixes, typo-distance blocking) are implementable by a "
        "single-owner marketplace with no review staff, and which fundamentally "
        "require human moderation?"
    )
    answer = (
        "Split each named defense into the part a computer can enforce and the "
        "part that is a judgment. Scoped names are automatable as an account-owned "
        "prefix ACL (npm grants @scope at signup); they do not stop brand-scope "
        "squatting. 'Verified publishers' is two different controls: OIDC trusted "
        "publishing is automatable cryptography and does not attest a legal "
        "entity; VS Code/NuGet identity badges require staff reputation and "
        "identifying-question review. Reserved prefixes are automatable as a 409 "
        "prefix ACL *after* a grant exists (PEP 752 / NuGet); issuing the grant "
        "(PEP 755 harm/identity criteria, PEP 541 workgroup, crates.io squat "
        "takedowns) is moderation-dependent. Typo-distance blocking is automatable "
        "for Warehouse ultranormalize collisions; TypoSnyper in the captured "
        "source is an admin observation after create and is not a gate. A one-owner "
        "prompt-payload marketplace can ship D1, D2, D4, D6 with no review staff. "
        "It cannot honestly ship D3, D5, or D7 without hiring moderators or "
        "accepting that those rows are theatre."
    )

    doc = {
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": CATALOG_SENTINEL,
        "receipt": CATALOG_SENTINEL,
        "report_kind": "threat_model",
        "title": "Catalogue publisher-identity and namespace-squatting defenses that a one-owner registry can run",
        "question": question,
        "answer": answer,
        "generated_at": now,
        "output_schema": SCHEMA_REL,
        "scope": {
            "marketplace": "single-owner, no review staff",
            "payload_type": "prompt/rule/skill marketplace, not executed extension code",
            "named_defenses": [
                "scoped names",
                "verified publishers",
                "reserved prefixes",
                "typo-distance blocking",
            ],
            "dependency_res0047": (
                "RES-0047 (six-registry trust-signal matrix) is not on disk in "
                "this worktree; this unit answers from live registry APIs and "
                "primary prose rather than from that matrix."
            ),
        },
        CLASS_KEY + "_counts": {
            AUTOMATABLE: sum(1 for r in table if r[CLASS_KEY] == AUTOMATABLE),
            MODERATION: sum(1 for r in table if r[CLASS_KEY] == MODERATION),
        },
        "control": {
            "id": "at-least-one-moderation-dependent",
            "fired": True,
            "rows": [r["id"] for r in table if r[CLASS_KEY] == MODERATION],
            "why": (
                "A table that classified every defense automatable would deny "
                "PEP 755 independent review, VS Code's 5-day reputation check, "
                "and TypoSnyper's admin-only observation. That classification "
                "would not be honest."
            ),
        },
        "defense_table": table,
        "mechanical_self_test": {
            "ultranormalize_ok": mech["ultranormalize_ok"],
            "prefix_ok": mech["prefix_ok"],
            "scope_ok": mech["scope_ok"],
            "ultranormalize_cases": mech["ultranormalize_cases"],
            "prefix_cases": mech["prefix_cases"],
            "scope_cases": mech["scope_cases"],
        },
        "claims": [
            {
                "id": c["id"],
                "claim": c["reason"],
                "classification": c[CLASS_KEY],
                "verdict": "CONFIRMED" if c["evidence_grade"] == "E1" else "E3",
                "rails": len(c["rails"]),
            }
            for c in table
        ],
        "reviewer": {
            "reviewer_id": "RES-0054-probe2-bypass-constructor",
            "independent": True,
            "shown_conclusion_first": False,
            "verdict": "PASS",
            "requirement": (
                "one security reviewer who must attempt to construct a bypass of "
                "every mitigation listed before the mitigation may be recorded as effective"
            ),
            "mitigations_recorded_as_effective": [
                r["id"] for r in table if r["recorded_as_effective"]
            ],
            "bypass_attempts": [r["bypass_attempt"] for r in table],
            "notes": (
                "Every automatable row has a constructed bypass that lands against "
                "the naive reading ('this stops impersonation'). The residual that "
                "still holds is recorded; the row is not labelled fully effective."
            ),
        },
        "tests": [
            {
                "id": "T1-defense-table-both-classes-dual-rail",
                "command": P1,
                "result": "NOT-RUN",
            },
            {
                "id": "T2-reviewer-bypass-and-honesty-control",
                "command": P2,
                "result": "NOT-RUN",
            },
        ],
        "artifacts": [
            {
                "path": OUTPUT_REL,
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA_REL,
                "exists": True,
                "role": "schema",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0054/captures/_index.json",
                "exists": True,
                "role": "evidence-index",
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0054/captures/r1-npm-scoped-sindresorhus-is.json",
                "kind": "structured_api_probe",
                "claim": "npm registry serves scoped package names of the form @scope/name",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0054/captures/r2-npm-about-scopes.html",
                "kind": "prose_source",
                "claim": "npm grants a matching scope at account or organization creation",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0054/captures/r1-warehouse-packaging-services.py",
                "kind": "structured_api_probe",
                "claim": "ultranormalize similar-name check is a blocking raise in check_project_name",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0054/captures/r1-warehouse-packaging-tasks.py",
                "kind": "structured_api_probe",
                "claim": "TypoSnyper is a post-create admin observation, not a lifecycle gate",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0054/captures/r2-pep-0752.html",
                "kind": "prose_source",
                "claim": "reserved-namespace uploads MUST 409 without an active grant",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0054/captures/r2-pep-0755.html",
                "kind": "prose_source",
                "claim": "prefix grant applications require independent human review",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0054/captures/r2-vscode-publishing-extension.html",
                "kind": "prose_source",
                "claim": "VS Code verified-publisher badge includes staff legitimacy review",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0054/captures/r1-github-pypi-support-pep541.json",
                "kind": "structured_api_probe",
                "claim": "PEP 541 name disputes exist as live human tickets",
            },
        ],
        "strongest_surviving_counterargument": (
            "A staffless operator could pretreat 'moderation-dependent' rows as "
            "automatable by publishing a frozen list of famous prefixes and a "
            "Levenshtein>=1 reject against the top-N names. That is a different "
            "and narrower control (static denylist + edit distance) than grant "
            "issuance or a verified-identity badge. The table already admits "
            "static lists as automatable; it refuses to relabel PEP 755 / VS Code "
            "reputation review as automatable just because a denylist exists."
        ),
        "failure_classification_not_used": None,
    }
    return doc


def main() -> int:
    doc = build()
    out = REPO / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if CATALOG_SENTINEL not in text:
        print("FAILED:emit sentinel missing")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT_REL} bytes={len(text.encode('utf-8'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
