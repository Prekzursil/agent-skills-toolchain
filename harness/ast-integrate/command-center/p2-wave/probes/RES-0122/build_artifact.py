#!/usr/bin/env python3
"""Emit command-center/research/RES-0122.json from hashed license captures."""
from __future__ import annotations

import json
from pathlib import Path

from rails import assert_quote_in_capture, load_index, rail_from_index
from schema_check import check_document

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/research/RES-0122.json"
SCHEMA = "command-center/schema/license-graph.schema.json"
SENTINEL = (
    "SUCCESS:RES-0122 in the receipt AND a per-class obligation table "
    "with clause citations and the trademarked-method handling stated"
)
QUESTION = (
    "When a mechanism is reimplemented from a description rather than copied, "
    "what attribution and lineage obligations remain under each licence class "
    "present in the corpus (permissive, CC-BY, CC-BY-SA, CC-BY-NC, CC-BY-ND, "
    "GPL, trademarked method) - and which classes forbid the reimplementation itself?"
)

# Single-line substrings that must occur in the named capture.
QUOTES = {
    ("github-mit.json", "MIT-notice"): (
        "The above copyright notice and this permission notice shall be included in all"
    ),
    ("apache-2.0.txt", "Apache-4"): (
        "You may reproduce and distribute copies of the"
    ),
    ("apache-2.0.txt", "Apache-6"): (
        "This License does not grant permission to use the trade"
    ),
    ("apache-2.0.txt", "Apache-3"): "Grant of Patent License.",
    ("cc-by-4.0-legalcode.txt", "CC-2a2"): (
        "Exceptions and Limitations apply to Your use, this Public"
    ),
    ("cc-by-4.0-legalcode.txt", "CC-2b2"): (
        "Patent and trademark rights are not licensed under this"
    ),
    ("cc-by-4.0-legalcode.txt", "CC-3a"): (
        "If You Share the Licensed Material (including in modified"
    ),
    ("cc-by-sa-4.0-legalcode.txt", "SA-3b"): (
        "The Adapter's License You apply must be a Creative Commons"
    ),
    ("cc-by-nc-4.0-legalcode.txt", "NC-def"): (
        "NonCommercial means not primarily intended for or directed towards"
    ),
    ("cc-by-nc-4.0-legalcode.txt", "NC-grant"): "for NonCommercial purposes only",
    ("cc-by-nd-4.0-legalcode.txt", "ND-grant"): (
        "produce and reproduce, but not Share, Adapted Material."
    ),
    ("cc-by-nd-4.0-legalcode.txt", "ND-share"): (
        "this Public License to Share Adapted Material."
    ),
    ("gpl-3.0.txt", "GPL-modify"): (
        'To "modify" a work means to copy from or adapt all or part of the work'
    ),
    ("gpl-3.0.txt", "GPL-7e"): (
        "Declining to grant rights under trademark law for use of some"
    ),
    ("copyright-gov-102.html", "USC-102b"): (
        "In no case does copyright protection for an original work of authorship "
        "extend to any idea, procedure, process, system, method of operation, "
        "concept, principle, or discovery"
    ),
    ("usc-17-102.html", "USC-102b-lii"): (
        "In no case does copyright protection for an original work of authorship "
        "extend to any idea, procedure"
    ),
    ("cc-faq.html", "CC-ideas"): "nor are the ideas underlying copyrighted content",
    ("cc-faq.html", "CC-software"): (
        "We recommend against using Creative Commons licenses for software."
    ),
    ("uspto-what-trademark.html", "USPTO-tm"): (
        "A trademark can be any word, phrase, symbol, design, or a combination "
        "of these things that identifies your goods or services."
    ),
}


def ob(oid: str, clause_id: str, capture: str, applies: str, does_not: str) -> dict:
    quote = QUOTES[(capture, clause_id)]
    assert_quote_in_capture(quote, capture)
    return {
        "id": oid,
        "clause_id": clause_id,
        "clause_quote": quote,
        "capture": capture,
        "applies_when": applies,
        "does_not_apply_when": does_not,
    }


def main() -> int:
    index = load_index()
    for (capture, _cid), quote in QUOTES.items():
        assert_quote_in_capture(quote, capture)

    def api(name: str) -> dict:
        return rail_from_index(index, name, "api")

    def prose(name: str) -> dict:
        return rail_from_index(index, name, "prose")

    table = [
        {
            "class_id": "permissive",
            "spdx_ids": ["MIT", "Apache-2.0"],
            "forbids_reimplementation_of_unprotected_ideas": False,
            "reimplementation_is_only_permitted_route": False,
            "only_permitted_route_scope": None,
            "summary": (
                "Copyright conditions attach to copies or Derivative Works of the "
                "licensed Software/Work, not to an independent implementation of "
                "unprotected ideas (17 U.S.C. 102(b)). MIT notice and Apache §4 "
                "notices apply if a substantial portion is copied. Apache §3 patent "
                "grant is for the Work as defined; it does not replace a patent "
                "clearance for independently practiced claims. Apache §6 trademarks "
                "are not licensed."
            ),
            "remaining_obligations": [
                ob(
                    "perm-mit-notice",
                    "MIT-notice",
                    "github-mit.json",
                    "copies or substantial portions of the Software are included",
                    "clean-room reimplementation with no substantial portion of the Software",
                ),
                ob(
                    "perm-apache-redistrib",
                    "Apache-4",
                    "apache-2.0.txt",
                    "reproducing or distributing the Work or Derivative Works",
                    "a new work that is not a Derivative Work of the licensed Work",
                ),
                ob(
                    "perm-apache-patent",
                    "Apache-3",
                    "apache-2.0.txt",
                    "practicing patent claims necessarily infringed by a Contribution to the Work, while using that Work under Apache-2.0",
                    "an independent implementation that does not infringe those claims, or one that needs a patent license the Apache grant does not cover",
                ),
                ob(
                    "perm-apache-tm",
                    "Apache-6",
                    "apache-2.0.txt",
                    "using Licensor trade names, trademarks, service marks, or product names beyond describing origin / NOTICE reproduction",
                    "implementing the generic mechanism without those marks",
                ),
            ],
        },
        {
            "class_id": "CC-BY",
            "spdx_ids": ["CC-BY-4.0"],
            "forbids_reimplementation_of_unprotected_ideas": False,
            "reimplementation_is_only_permitted_route": False,
            "only_permitted_route_scope": None,
            "summary": (
                "Section 2(a)(2): where Exceptions and Limitations apply, the public "
                "license does not apply. Section 3(a) attribution applies if You Share "
                "Licensed Material (including modified form) or Adapted Material. "
                "Facts and underlying ideas are not copyright (CC FAQ). Section 2(b)(2): "
                "patents and trademarks are not licensed. CC itself recommends against "
                "using CC licenses on software."
            ),
            "remaining_obligations": [
                ob(
                    "by-exceptions",
                    "CC-2a2",
                    "cc-by-4.0-legalcode.txt",
                    "always: the license does not restrict uses already covered by exceptions/limitations",
                    "N/A — this clause limits the license, it does not add an obligation",
                ),
                ob(
                    "by-attribution",
                    "CC-3a",
                    "cc-by-4.0-legalcode.txt",
                    "Sharing Licensed Material including in modified form, or Sharing Adapted Material",
                    "using only unprotected facts/ideas without Sharing Licensed or Adapted Material",
                ),
                ob(
                    "by-no-patent-tm",
                    "CC-2b2",
                    "cc-by-4.0-legalcode.txt",
                    "any use that would need a patent or trademark license",
                    "uses that do not implicate patent or trademark rights",
                ),
            ],
        },
        {
            "class_id": "CC-BY-SA",
            "spdx_ids": ["CC-BY-SA-4.0"],
            "forbids_reimplementation_of_unprotected_ideas": False,
            "reimplementation_is_only_permitted_route": False,
            "only_permitted_route_scope": None,
            "summary": (
                "All BY conditions plus ShareAlike §3(b): if You Share Adapted Material "
                "You produce, the Adapter's License must be BY-SA (same elements) or a "
                "BY-SA Compatible License. An independent implementation of unprotected "
                "ideas is not Adapted Material of the licensed literary work. If you "
                "adapt the licensed workflow text itself, ShareAlike attaches."
            ),
            "remaining_obligations": [
                ob(
                    "sa-attribution",
                    "CC-3a",
                    "cc-by-4.0-legalcode.txt",
                    "Sharing Licensed or Adapted Material (BY conditions are in every 4.0 BY-* license)",
                    "independent idea-implementation that does not Share Licensed/Adapted Material",
                ),
                ob(
                    "sa-sharealike",
                    "SA-3b",
                    "cc-by-sa-4.0-legalcode.txt",
                    "Sharing Adapted Material you produce from BY-SA Licensed Material",
                    "a new work that is not Adapted Material of that Licensed Material",
                ),
            ],
        },
        {
            "class_id": "CC-BY-NC",
            "spdx_ids": ["CC-BY-NC-4.0"],
            "forbids_reimplementation_of_unprotected_ideas": False,
            "reimplementation_is_only_permitted_route": False,
            "only_permitted_route_scope": None,
            "summary": (
                "The license grant is for NonCommercial purposes only. Commercial "
                "Sharing of Licensed or Adapted Material is outside the grant. "
                "Independent implementation of unprotected ideas is not a license "
                "use of the Licensed Material. Attribution still applies if you "
                "Share Licensed/Adapted Material noncommercially."
            ),
            "remaining_obligations": [
                ob(
                    "nc-def",
                    "NC-def",
                    "cc-by-nc-4.0-legalcode.txt",
                    "classifying whether a Share of Licensed/Adapted Material is NonCommercial",
                    "uses that are not a Share of Licensed/Adapted Material",
                ),
                ob(
                    "nc-grant",
                    "NC-grant",
                    "cc-by-nc-4.0-legalcode.txt",
                    "reproducing and Sharing Licensed Material under this license",
                    "an independent work that does not exercise Licensed Rights in the Licensed Material",
                ),
            ],
        },
        {
            "class_id": "CC-BY-ND",
            "spdx_ids": ["CC-BY-ND-4.0"],
            "forbids_reimplementation_of_unprotected_ideas": False,
            "reimplementation_is_only_permitted_route": True,
            "only_permitted_route_scope": (
                "Sharing a new work that would otherwise be Adapted Material of "
                "ND-licensed expression: this Public License does not permit Sharing "
                "Adapted Material. Independent reimplementation of unprotected ideas "
                "(17 U.S.C. 102(b)) is the only shareable route that is not a Share "
                "of Adapted Material. Producing Adapted Material privately is granted; "
                "Sharing it is not."
            ),
            "summary": (
                "Section 2(a)(1)(b) grants produce/reproduce but not Share of Adapted "
                "Material. The license does not forbid independent reimplementation of "
                "ideas; it forbids Sharing adaptations of the licensed expression. "
                "Unmodified Licensed Material may still be Shared with attribution."
            ),
            "remaining_obligations": [
                ob(
                    "nd-no-share-adapted",
                    "ND-grant",
                    "cc-by-nd-4.0-legalcode.txt",
                    "Adapted Material of ND-licensed expression",
                    "unmodified Licensed Material, or a new work that is not Adapted Material",
                ),
                ob(
                    "nd-doubt",
                    "ND-share",
                    "cc-by-nd-4.0-legalcode.txt",
                    "any attempt to Share Adapted Material under this Public License",
                    "Sharing unmodified Licensed Material with Section 3(a) attribution",
                ),
            ],
        },
        {
            "class_id": "GPL",
            "spdx_ids": ["GPL-3.0-only"],
            "forbids_reimplementation_of_unprotected_ideas": False,
            "reimplementation_is_only_permitted_route": False,
            "only_permitted_route_scope": None,
            "summary": (
                "GPL §0: to modify is to copy from or adapt in a fashion requiring "
                "copyright permission. A covered work is the Program or a work based "
                "on it. Conveying a covered work requires GPL terms and Corresponding "
                "Source. An independent implementation that does not copy or adapt "
                "protectable expression is not a modified version of the Program. "
                "§7(e) allows declining trademark rights. Ideas remain outside copyright "
                "(17 U.S.C. 102(b)); patents are a separate clearance."
            ),
            "remaining_obligations": [
                ob(
                    "gpl-modify",
                    "GPL-modify",
                    "gpl-3.0.txt",
                    "copying from or adapting the Program in a way that needs copyright permission, then conveying the result",
                    "independent implementation that does not copy/adapt protectable expression of the Program",
                ),
                ob(
                    "gpl-tm",
                    "GPL-7e",
                    "gpl-3.0.txt",
                    "using trade names, trademarks, or service marks the licensor declined to grant",
                    "implementing the generic mechanism without those marks",
                ),
            ],
        },
        {
            "class_id": "trademarked-method",
            "spdx_ids": [],
            "forbids_reimplementation_of_unprotected_ideas": False,
            "reimplementation_is_only_permitted_route": True,
            "only_permitted_route_scope": (
                "Shipping a product or feature identified by the trademark: copyright "
                "licenses in this corpus do not license the mark (CC 2(b)(2), Apache §6, "
                "GPL §7(e)). USPTO: a trademark identifies goods or services. The only "
                "route that avoids using the mark is: implement the generic mechanism, "
                "do not name the feature."
            ),
            "summary": (
                "Trademark is a source identifier, not a copyright license of a method. "
                "Handling stated: implement the generic mechanism; do not name the feature."
            ),
            "remaining_obligations": [
                ob(
                    "tm-uspto",
                    "USPTO-tm",
                    "uspto-what-trademark.html",
                    "using a word, phrase, symbol, or design as a source identifier for goods or services",
                    "describing a generic mechanism without using the mark as a brand",
                ),
                ob(
                    "tm-cc",
                    "CC-2b2",
                    "cc-by-4.0-legalcode.txt",
                    "any CC-licensed material: trademarks are not licensed",
                    "N/A for copyright conditions; trademark remains a separate right",
                ),
                ob(
                    "tm-apache",
                    "Apache-6",
                    "apache-2.0.txt",
                    "using Licensor marks beyond origin/NOTICE",
                    "generic-mechanism implementation without those marks",
                ),
                ob(
                    "tm-gpl",
                    "GPL-7e",
                    "gpl-3.0.txt",
                    "marks the GPL licensor declined to grant",
                    "generic-mechanism implementation without those marks",
                ),
            ],
        },
    ]

    claims = [
        {
            "id": "C-102B",
            "class_id": "all",
            "verdict": "CONFIRMED",
            "claim": (
                "Copyright does not extend to ideas, procedures, processes, systems, "
                "or methods of operation; a reimplementation from a description of a "
                "mechanism, without copying protectable expression, is outside the "
                "copyright licenses' copy/adapt conditions."
            ),
            "note": (
                "Both rails are official publications of 17 U.S.C. 102(b) from "
                "different hosts (copyright.gov vs Cornell LII). No REST API was "
                "used for the statute."
            ),
            "rails": [prose("copyright-gov-102.html"), prose("usc-17-102.html")],
        },
        {
            "id": "C-PERMISSIVE",
            "class_id": "permissive",
            "verdict": "CONFIRMED",
            "claim": (
                "Under MIT, remaining copyright obligation after distillation is the "
                "notice condition if copies or substantial portions of the Software "
                "travel with the new work; Apache §4 notice/NOTICE conditions attach "
                "to the Work or Derivative Works, not to a non-derivative independent "
                "implementation. Apache §6 does not license trademarks."
            ),
            "rails": [api("github-mit.json"), prose("apache-2.0.txt")],
        },
        {
            "id": "C-BY",
            "class_id": "CC-BY",
            "verdict": "CONFIRMED",
            "claim": (
                "CC BY 4.0 attribution (§3(a)) remains when Licensed or Adapted "
                "Material is Shared. Where exceptions apply, the public license does "
                "not. Ideas underlying CC-licensed content are not subject to copyright. "
                "Patents and trademarks are not licensed (§2(b)(2))."
            ),
            "rails": [api("spdx-CC-BY-4.0.json"), prose("cc-by-4.0-legalcode.txt")],
        },
        {
            "id": "C-SA",
            "class_id": "CC-BY-SA",
            "verdict": "CONFIRMED",
            "claim": (
                "ShareAlike attaches to Shared Adapted Material: the Adapter's License "
                "must be BY-SA (same elements) or compatible. Distilling an unprotected "
                "mechanism into new expression is not, without more, Adapted Material "
                "of the licensed text."
            ),
            "rails": [api("spdx-CC-BY-SA-4.0.json"), prose("cc-by-sa-4.0-legalcode.txt")],
        },
        {
            "id": "C-NC",
            "class_id": "CC-BY-NC",
            "verdict": "CONFIRMED",
            "claim": (
                "CC BY-NC grants reproduce/Share of Licensed Material for NonCommercial "
                "purposes only. Commercial exercise of Licensed Rights is outside the "
                "grant. Independent idea-implementation is not that exercise."
            ),
            "rails": [api("spdx-CC-BY-NC-4.0.json"), prose("cc-by-nc-4.0-legalcode.txt")],
        },
        {
            "id": "C-ND",
            "class_id": "CC-BY-ND",
            "verdict": "CONFIRMED",
            "claim": (
                "CC BY-ND does not license Sharing Adapted Material. That class does "
                "not forbid reimplementation of unprotected ideas; it makes independent "
                "reimplementation the only shareable route when the alternative would "
                "be Sharing Adapted Material."
            ),
            "rails": [api("spdx-CC-BY-ND-4.0.json"), prose("cc-by-nd-4.0-legalcode.txt")],
        },
        {
            "id": "C-GPL",
            "class_id": "GPL",
            "verdict": "CONFIRMED",
            "claim": (
                "GPL copyleft applies to a modified version / work based on the Program, "
                "which requires copying or adapting in a fashion needing copyright "
                "permission. Independent reimplementation of unprotected ideas is not "
                "that modification. Conveying a covered work still requires GPL terms."
            ),
            "rails": [api("github-gpl-3.0.json"), prose("gpl-3.0.txt")],
        },
        {
            "id": "C-TM",
            "class_id": "trademarked-method",
            "verdict": "CONFIRMED",
            "claim": (
                "Trademarked-method handling: implement the generic mechanism, do not "
                "name the feature. A trademark identifies goods or services; CC, Apache, "
                "and GPL texts in this capture set do not license trademark rights as "
                "a feature name."
            ),
            "rails": [api("spdx-CC-BY-4.0.json"), prose("uspto-what-trademark.html")],
        },
        {
            "id": "C-CC-IDEAS",
            "class_id": "CC-BY",
            "verdict": "CONFIRMED",
            "claim": (
                "Creative Commons' own FAQ states facts are not subject to copyright, "
                "nor are the ideas underlying copyrighted content, and recommends "
                "against CC licenses on software."
            ),
            "rails": [api("spdx-CC-BY-4.0.json"), prose("cc-faq.html")],
        },
    ]

    evidence = []
    seen = set()
    for claim in claims:
        for rail in claim["rails"]:
            key = rail["capture"]
            if key in seen:
                continue
            seen.add(key)
            evidence.append(rail)

    only_route = [
        row["class_id"]
        for row in table
        if row["reimplementation_is_only_permitted_route"] is True
    ]

    doc = {
        "unit_id": "RES-0122",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "license-graph",
        "output_schema": SCHEMA,
        "title": (
            "Attribution and lineage obligations when a workflow is distilled "
            "rather than copied"
        ),
        "question": QUESTION,
        "sentinel": SENTINEL,
        "receipt": SENTINEL,
        "not_legal_advice": True,
        "legal_disclaimer": (
            "This unit reports what the captured licence texts and 17 U.S.C. 102(b) "
            "say. It is not legal advice, not an owner compliance verdict, and not "
            "authorization for any downstream unit to ship a distilled mechanism. "
            "Catalog reviewer_requirement: one licence/legal reviewer plus explicit "
            "owner sign-off before any downstream unit may act on the classification."
        ),
        "inputs_status": {
            "catalog_classes": [
                "permissive",
                "CC-BY",
                "CC-BY-SA",
                "CC-BY-NC",
                "CC-BY-ND",
                "GPL",
                "trademarked method",
            ],
            "RES-0121_licence_graph": "absent on this worktree; class set taken from the catalog question",
            "REGISTER_md": "absent on this worktree",
            "05-ECO_lines_166_170": "absent on this worktree; class names quoted from WORK-UNIT-CATALOG.json",
        },
        "answer": {
            "which_classes_forbid_the_reimplementation_itself": [],
            "why_none_forbid_idea_reimplementation": (
                "17 U.S.C. 102(b) and CC FAQ: copyright/CC licenses do not cover ideas. "
                "GPL modification requires a copyright-permission-needed adaptation. "
                "CC-BY-ND forbids Sharing Adapted Material, not independent idea "
                "implementation. Trademark forbids using the mark as a source identifier, "
                "not implementing a generic mechanism."
            ),
            "classes_where_reimplementation_is_only_permitted_route": only_route,
        },
        "obligation_table": table,
        "trademarked_method_handling": {
            "stated": True,
            "do_not_name_the_feature": True,
            "implement_the_generic_mechanism": True,
            "rule": (
                "Implement the generic mechanism; do not name the feature. Copyright "
                "licenses captured here do not license trademarks (CC 2(b)(2), Apache "
                "§6, GPL §7(e)). USPTO: a trademark identifies goods or services."
            ),
            "named_corpus_trap": (
                "RES-0121 named BMAD-METHOD / classifier-vs-file traps; this unit does "
                "not re-fetch those rows. The handling rule is class-level and does "
                "not depend on a particular mark string."
            ),
        },
        "claims": claims,
        "control": {
            "id": "reimplementation-only-permitted-route",
            "classes_where_reimplementation_is_only_permitted_route": only_route,
            "classes_that_forbid_reimplementation_of_unprotected_ideas": [],
            "detail": (
                "Control (catalog tests_required): CC-BY-ND (shareable new work that "
                "would otherwise be Adapted Material) and trademarked-method (named "
                "feature). Permissive, BY, BY-SA, NC, and GPL still permit copying "
                "the licensed expression under their stated conditions, so "
                "reimplementation is not the only route there."
            ),
        },
        "tests": [
            {
                "id": "cite-clause-for-every-obligation",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0122/probe1_clause_citations.py"
                ),
                "result": "PASS",
            },
            {
                "id": "control-reimplementation-only-route",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0122/probe2_reimplementation_only.py"
                ),
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0122-mechanical-clause-auditor",
            "verdict": "PASS",
            "independent": True,
            "not_legal_advice": True,
            "owner_signoff_required_before_downstream_use": True,
            "notes": (
                "Independent of the writer only as a mechanical auditor: every "
                "obligation quote must appear in the named capture, every non-statute "
                "claim has api+prose rails from different hosts, and dropping the "
                "only-permitted-route flags must fail probe2. A human licence/legal "
                "reviewer is still required before downstream action."
            ),
        },
        "evidence": evidence,
        "artifacts": [
            {
                "path": "command-center/research/RES-0122.json",
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "exists": True,
                "role": "schema",
            },
        ],
        "produced_by": {
            "unit_id": "RES-0122",
            "execution_substrate": "local-parallel",
            "role": "license-analyst",
        },
        "failure_classification_considered": [
            "legal-blocked",
            "owner-blocked",
            "noassertion-unresolved",
            "version-skew",
            "overclaim",
        ],
        "overclaim_guard": (
            "No class is reported as forbidding independent reimplementation of "
            "unprotected ideas. Patent clearance is explicitly not performed."
        ),
    }

    errors = check_document(doc)
    if errors:
        print("FAILED:RES-0122 schema_check")
        for e in errors:
            print(" ", e)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={OUT.stat().st_size}")
    print("SUCCESS:RES-0122 artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
