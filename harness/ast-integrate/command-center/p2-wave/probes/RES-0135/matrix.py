"""Licence-compatibility lattice for marketplace aggregation (RES-0135).

Verdicts answer the catalog question for one downloadable marketplace SKU of
independent workflows/skills/prompts (not the IMP-0157 fusion solver):

  TOGETHER          — may ship in one SKU (notices kept; outbound noted)
  SEPARATE-PACKAGE  — each work is redistributable, but not as one SKU
  FORBIDDEN         — at least one work has no grant to redistribute here

Unlicensed is ALL-RIGHTS-RESERVED. Vendor riders fail closed. Cross-family
share-alike (CC-BY-SA vs software copyleft) is SEPARATE-PACKAGE.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
SNAP = HERE / "snapshots"
CAPTURE = SNAP / "CAPTURE.json"

AXES: tuple[str, ...] = (
    "MIT",
    "Apache-2.0",
    "BSD",
    "GPL-3.0",
    "AGPL-3.0",
    "MPL-2.0",
    "CC-BY",
    "CC-BY-SA",
    "CC0",
    "unlicensed",
    "vendor-riders",
)

TOGETHER = "TOGETHER"
SEPARATE_PACKAGE = "SEPARATE-PACKAGE"
FORBIDDEN = "FORBIDDEN"
VERDICTS = (TOGETHER, SEPARATE_PACKAGE, FORBIDDEN)

CANONICAL_SPDX = {
    "MIT": "MIT",
    "Apache-2.0": "Apache-2.0",
    "BSD": "BSD-3-Clause",
    "GPL-3.0": "GPL-3.0-only",
    "AGPL-3.0": "AGPL-3.0-only",
    "MPL-2.0": "MPL-2.0",
    "CC-BY": "CC-BY-4.0",
    "CC-BY-SA": "CC-BY-SA-4.0",
    "CC0": "CC0-1.0",
    "unlicensed": "NOASSERTION",
    "vendor-riders": "LicenseRef-VendorRider",
}

PERMISSIVE = frozenset({"MIT", "Apache-2.0", "BSD", "CC0", "CC-BY"})
WEAK_COPYLEFT = frozenset({"MPL-2.0"})
STRONG_COPYLEFT = frozenset({"GPL-3.0", "AGPL-3.0"})
SOFTWARE_COPYLEFT = WEAK_COPYLEFT | STRONG_COPYLEFT
CONTENT_SA = frozenset({"CC-BY-SA"})
NO_GRANT = frozenset({"unlicensed"})
RIDER = frozenset({"vendor-riders"})

# Driving clause catalog. Needles must occur in the frozen snapshot bytes.
CLAUSES: dict[str, dict[str, str]] = {
    "USC17:106": {
        "snapshot": "uscode-17-106.html",
        "clause_number": "17 USC §106",
        "needle": "Exclusive rights in copyrighted works",
        "kind": "licence-text",
    },
    "USC17:106-bundle": {
        "snapshot": "uscode-17-106.html",
        "clause_number": "17 USC §106",
        "needle": "the owner of copyright under this title has the exclusive rights",
        "kind": "independent-commentary",
    },
    "N8N:limitations": {
        "snapshot": "n8n-sustainable-use-LICENSE.md",
        "clause_number": "Sustainable Use License / Limitations",
        "needle": "You may distribute the software or provide it to others only if you do so free of charge for",
        "kind": "licence-text",
    },
    "N8N:no-other-rights": {
        "snapshot": "n8n-sustainable-use-LICENSE.md",
        "clause_number": "Sustainable Use License / No Other Rights",
        "needle": "These terms do not imply any licenses other than those expressly granted",
        "kind": "independent-commentary",
    },
    "MIT:grant": {
        "snapshot": "mit.txt",
        "clause_number": "MIT permission notice",
        "needle": "Permission is hereby granted, free of charge",
        "kind": "licence-text",
    },
    "MIT:notice": {
        "snapshot": "mit.txt",
        "clause_number": "MIT copyright-notice condition",
        "needle": "The above copyright notice and this permission notice shall be included",
        "kind": "licence-text",
    },
    "BSD:cond1": {
        "snapshot": "bsd-3-clause.txt",
        "clause_number": "BSD-3-Clause condition 1",
        "needle": "Redistributions of source code must retain the above copyright notice",
        "kind": "licence-text",
    },
    "APACHE:2": {
        "snapshot": "apache-2.0.txt",
        "clause_number": "Apache-2.0 §2",
        "needle": "2. Grant of Copyright License.",
        "kind": "licence-text",
    },
    "APACHE:4": {
        "snapshot": "apache-2.0.txt",
        "clause_number": "Apache-2.0 §4",
        "needle": "4. Redistribution. You may reproduce and distribute copies of the",
        "kind": "licence-text",
    },
    "GPL:5c": {
        "snapshot": "gpl-3.0.txt",
        "clause_number": "GPL-3.0 §5(c)",
        "needle": "You must license the entire work, as a whole, under this",
        "kind": "licence-text",
    },
    "GPL:5-agg": {
        "snapshot": "gpl-3.0.txt",
        "clause_number": "GPL-3.0 §5 aggregate",
        "needle": 'in an aggregate does not cause this License to apply to the other',
        "kind": "licence-text",
    },
    "GPL:13": {
        "snapshot": "gpl-3.0.txt",
        "clause_number": "GPL-3.0 §13",
        "needle": "13. Use with the GNU Affero General Public License.",
        "kind": "licence-text",
    },
    "AGPL:13": {
        "snapshot": "agpl-3.0.txt",
        "clause_number": "AGPL-3.0 §13",
        "needle": "13. Remote Network Interaction; Use with the GNU General Public License.",
        "kind": "licence-text",
    },
    "AGPL:13-combine": {
        "snapshot": "agpl-3.0.txt",
        "clause_number": "AGPL-3.0 §13",
        "needle": "permission to link or combine any covered work with a work licensed",
        "kind": "licence-text",
    },
    "MPL:1.12": {
        "snapshot": "mpl-2.0.txt",
        "clause_number": "MPL-2.0 §1.12",
        "needle": '1.12. "Secondary License"',
        "kind": "licence-text",
    },
    "MPL:3.3": {
        "snapshot": "mpl-2.0.txt",
        "clause_number": "MPL-2.0 §3.3",
        "needle": "3.3. Distribution of a Larger Work",
        "kind": "licence-text",
    },
    "CCBY:2a": {
        "snapshot": "cc-by-4.0.txt",
        "clause_number": "CC-BY-4.0 §2(a)",
        "needle": "a. License grant.",
        "kind": "licence-text",
    },
    "CCBY:3a": {
        "snapshot": "cc-by-4.0.txt",
        "clause_number": "CC-BY-4.0 §3(a)",
        "needle": "a. Attribution.",
        "kind": "licence-text",
    },
    "CCSA:3b": {
        "snapshot": "cc-by-sa-4.0.txt",
        "clause_number": "CC-BY-SA-4.0 §3(b)",
        "needle": "b. ShareAlike.",
        "kind": "licence-text",
    },
    "CCSA:adapter": {
        "snapshot": "cc-by-sa-4.0.txt",
        "clause_number": "CC-BY-SA-4.0 §3(b)(1)",
        "needle": "The Adapter's License You apply must be a Creative Commons",
        "kind": "licence-text",
    },
    "CC0:2": {
        "snapshot": "cc0-1.0.txt",
        "clause_number": "CC0-1.0 §2",
        "needle": "2. Waiver. To the greatest extent permitted by, but not in contravention",
        "kind": "licence-text",
    },
    "FSF:apache2-gplv3": {
        "snapshot": "fsf-license-list.html",
        "clause_number": "FSF license-list #apache2",
        "needle": "compatible with version 3 of the",
        "kind": "independent-commentary",
    },
    "FSF:mpl-3.3": {
        "snapshot": "fsf-license-list.html",
        "clause_number": "FSF license-list #MPL-2.0",
        "needle": "Section 3.3 provides indirect",
        "kind": "independent-commentary",
    },
    "FSF:cc-by-sa-one-way": {
        "snapshot": "fsf-license-list.html",
        "clause_number": "FSF license-list CC BY-SA 4.0",
        "needle": "CC BY-SA 4.0 is one-way compatible with the GNU GPL version 3",
        "kind": "independent-commentary",
    },
    "ASF:gplv3": {
        "snapshot": "apache-gpl-compatibility.html",
        "clause_number": "ASF GPL-compatibility",
        "needle": "Apache 2 software can therefore be included in GPLv3 projects",
        "kind": "independent-commentary",
    },
    "CC:compat-gplv3": {
        "snapshot": "cc-compatible-licenses.html",
        "clause_number": "CC compatible-licenses / BY-SA / GPLv3",
        "needle": "compatibility with the GPLv3 is one-way only",
        "kind": "independent-commentary",
    },
    "CC:compat-list-only": {
        "snapshot": "cc-compatible-licenses.html",
        "clause_number": "CC compatible-licenses / BY-SA 4.0 list",
        "needle": "Your contributions to adaptations of BY-SA 4.0 materials may only be licensed under:",
        "kind": "independent-commentary",
    },
    "FSF:expat": {
        "snapshot": "fsf-license-list.html",
        "clause_number": "FSF license-list (Expat/MIT)",
        "needle": "non-copyleft free software license, compatible with the GNU GPL",
        "kind": "independent-commentary",
    },
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_capture() -> dict:
    return json.loads(CAPTURE.read_text(encoding="utf-8"))


def snapshot_bytes(name: str) -> bytes:
    return (SNAP / name).read_bytes()


def snapshot_text(name: str) -> str:
    return snapshot_bytes(name).decode("utf-8", errors="replace").replace("\r\n", "\n")


def verify_clause_needles() -> list[str]:
    """Return missing needle descriptions. Empty means all clauses are live."""
    missing: list[str] = []
    for cid, spec in CLAUSES.items():
        text = snapshot_text(spec["snapshot"])
        if spec["needle"] not in text:
            missing.append(f"{cid} needle absent from {spec['snapshot']}")
    return missing


def _grant_clauses(axis: str) -> tuple[str, str]:
    """Primary licence-text clause plus an independent commentary/companion."""
    if axis == "MIT":
        return "MIT:grant", "FSF:expat"
    if axis == "Apache-2.0":
        return "APACHE:2", "FSF:apache2-gplv3"
    if axis == "BSD":
        return "BSD:cond1", "FSF:expat"
    if axis == "GPL-3.0":
        return "GPL:5c", "GPL:5-agg"
    if axis == "AGPL-3.0":
        return "AGPL:13", "AGPL:13-combine"
    if axis == "MPL-2.0":
        return "MPL:3.3", "FSF:mpl-3.3"
    if axis == "CC-BY":
        return "CCBY:2a", "CCBY:3a"
    if axis == "CC-BY-SA":
        return "CCSA:3b", "FSF:cc-by-sa-one-way"
    if axis == "CC0":
        return "CC0:2", "FSF:expat"
    if axis == "unlicensed":
        return "USC17:106", "USC17:106-bundle"
    return "N8N:limitations", "N8N:no-other-rights"


def _outbound(a: str, b: str) -> str | None:
    pair = {a, b}
    if pair & NO_GRANT or pair & RIDER:
        return None
    if "AGPL-3.0" in pair:
        return "AGPL-3.0"
    if "GPL-3.0" in pair:
        return "GPL-3.0"
    if "MPL-2.0" in pair:
        return "mixed-per-file (MPL-2.0 files stay MPL-2.0)"
    if "CC-BY-SA" in pair:
        return "CC-BY-SA-4.0 (adapted content) / per-file otherwise"
    if "Apache-2.0" in pair:
        return "Apache-2.0 notices on Apache files; per-file otherwise"
    if "CC-BY" in pair:
        return "CC-BY-4.0 attribution on CC files; per-file otherwise"
    if "BSD" in pair:
        return "BSD-3-Clause notices"
    if "MIT" in pair:
        return "MIT notices"
    return "CC0-1.0 / public-domain"


def pair_cell(left: str, right: str) -> dict:
    if left not in AXES or right not in AXES:
        raise KeyError((left, right))
    pair = {left, right}

    if pair & NO_GRANT:
        primary, secondary = "USC17:106", "USC17:106-bundle"
        return _cell(
            left,
            right,
            FORBIDDEN,
            "NO_GRANT",
            CLAUSES[primary]["clause_number"],
            [primary, secondary],
            None,
            "almost-certain",
            (
                "Unlicensed is ALL-RIGHTS-RESERVED. 17 USC §106 keeps exclusive "
                "reproduction and distribution rights with the owner. Absence of "
                "a grant is never treated as MIT/permissive-by-default."
            ),
        )

    if pair & RIDER:
        primary, secondary = "N8N:limitations", "N8N:no-other-rights"
        return _cell(
            left,
            right,
            FORBIDDEN,
            "VENDOR_RIDER_NO_MARKETPLACE_GRANT",
            CLAUSES[primary]["clause_number"],
            [primary, secondary],
            None,
            "almost-certain",
            (
                "Corpus class 'vendor riders' is fail-closed. Live n8n Sustainable "
                "Use License grants distribution only free of charge for "
                "non-commercial purposes, is non-sublicensable, and grants no "
                "other rights. A marketplace SKU is outside that grant. Specific "
                "riders are classified by RES-0136; this cell does not invent a "
                "redistribution permission."
            ),
        )

    cross = (left in SOFTWARE_COPYLEFT and right in CONTENT_SA) or (
        right in SOFTWARE_COPYLEFT and left in CONTENT_SA
    )
    if cross:
        ids = ["CCSA:3b", "CCSA:adapter"]
        if "GPL-3.0" in pair:
            ids = ["CCSA:3b", "FSF:cc-by-sa-one-way", "CC:compat-gplv3"]
            note = (
                "CC-BY-SA-4.0 §3(b) requires the Adapter's License to be BY-SA "
                "or a listed BY-SA Compatible License. CC/FSF declare one-way "
                "compatibility to GPLv3 only: a CC-BY-SA adaptation may be "
                "released under GPLv3, but GPLv3 material may not be relicensed "
                "under CC-BY-SA. A mixed-licence marketplace SKU that keeps both "
                "is SEPARATE-PACKAGE. Conversion of the CC-BY-SA work onto GPLv3 "
                "is a different act (then TOGETHER under GPL-3.0)."
            )
        elif "AGPL-3.0" in pair:
            ids = ["CCSA:3b", "CC:compat-list-only"]
            note = (
                "The CC BY-SA 4.0 compatible-licenses list names GPLv3, not "
                "AGPL-3.0. Share-alike families differ; do not ship as one SKU."
            )
        else:
            ids = ["CCSA:3b", "CC:compat-list-only", "MPL:3.3"]
            note = (
                "MPL-2.0 secondary licenses are GPL/LGPL/AGPL, not CC-BY-SA. "
                "CC compatible-licenses does not list MPL. Cross-family "
                "share-alike cannot share one combined SKU."
            )
        return _cell(
            left,
            right,
            SEPARATE_PACKAGE,
            "CROSS_FAMILY_SHARE_ALIKE",
            CLAUSES["CCSA:3b"]["clause_number"],
            ids,
            "each SKU keeps its own licence",
            "almost-certain",
            note,
        )

    # Remaining pairs are legally redistributable together.
    if left in STRONG_COPYLEFT and right in STRONG_COPYLEFT:
        ids = ["GPL:13", "AGPL:13", "AGPL:13-combine"]
        reason = "GPL_AGPL_SECTION_13"
        note = (
            "GPL-3.0 §13 and AGPL-3.0 §13 expressly permit combining the two "
            "into one work. Outbound of a combined work is AGPL-3.0; the GPL "
            "part stays GPL-3.0. Network source-offer (AGPL §13) attaches to "
            "the combination."
        )
        driving = "AGPL-3.0 §13" if "AGPL-3.0" in pair else "GPL-3.0 §13"
        band = "almost-certain"
    elif (left in WEAK_COPYLEFT or right in WEAK_COPYLEFT) and (
        left in STRONG_COPYLEFT or right in STRONG_COPYLEFT
    ):
        ids = ["MPL:1.12", "MPL:3.3", "FSF:mpl-3.3"]
        reason = "MPL_SECONDARY_LICENSE"
        note = (
            "MPL-2.0 §1.12 names GPL-2.0, LGPL-2.1, and AGPL-3.0 as Secondary "
            "Licenses; §3.3 allows a Larger Work with those GNU licences "
            "unless Exhibit B (Incompatible With Secondary Licenses) is present. "
            "This matrix assumes no Exhibit B. MPL files stay available under MPL."
        )
        driving = "MPL-2.0 §3.3"
        band = "almost-certain"
    elif left in SOFTWARE_COPYLEFT or right in SOFTWARE_COPYLEFT:
        copyleft = left if left in SOFTWARE_COPYLEFT else right
        if copyleft == "MPL-2.0":
            other = right if left == "MPL-2.0" else left
            g1, g2 = _grant_clauses(other)
            ids = ["MPL:3.3", "FSF:mpl-3.3", g1, g2]
            reason = "MPL_FILE_LEVEL_WITH_PERMISSIVE"
            driving = "MPL-2.0 §3.3"
            note = (
                "MPL-2.0 is file-level copyleft. Permissive files may sit in "
                "the same SKU; MPL covered files stay MPL. Larger Work under "
                "§3.3 with terms of your choice provided MPL conditions hold."
            )
        else:
            ids = ["GPL:5c", "GPL:5-agg"]
            other = right if left in SOFTWARE_COPYLEFT else left
            g1, g2 = _grant_clauses(other)
            ids.append(g1)
            if other == "Apache-2.0":
                ids.extend(["FSF:apache2-gplv3", "ASF:gplv3"])
            reason = "COPYLEFT_ABSORBS_PERMISSIVE"
            driving = "GPL-3.0 §5(c)" if copyleft == "GPL-3.0" else "AGPL-3.0 §13"
            if copyleft == "AGPL-3.0":
                ids = ["AGPL:13", "GPL:5-agg", g1]
            note = (
                "Permissive licences grant redistribution. If the SKU is a "
                "combined covered work, GPL-3.0 §5(c) / AGPL copyleft covers "
                "the whole; if the other works stay separate and independent, "
                "GPL-3.0 §5 (aggregate) does not infect them. This cell is "
                "TOGETHER either as an aggregate of independent workflows or "
                "as a combined work outbound under the copyleft licence. "
                "Apache-2.0 is GPLv3-compatible (FSF #apache2 and ASF page) "
                "but not GPLv2; the corpus licence is GPL-3.0."
            )
        band = "almost-certain"
    else:
        g_left = _grant_clauses(left)
        g_right = _grant_clauses(right)
        ids = [g_left[0], g_left[1], g_right[0], g_right[1]]
        reason = "COMPATIBLE_PERMISSIVE"
        driving = CLAUSES[g_left[0]]["clause_number"]
        note = (
            "Both licences grant redistribution subject to notice/attribution. "
            "Keep per-file copyright and licence notices. Apache-2.0 §4 and "
            "CC-BY-4.0 §3(a) add notice/attribution; they do not forbid a "
            "shared SKU with MIT/BSD/CC0."
        )
        band = "almost-certain"
        if left == right:
            reason = "SAME_LICENCE"

    return _cell(
        left,
        right,
        TOGETHER,
        reason,
        driving,
        ids,
        _outbound(left, right),
        band,
        note,
    )


def _cell(
    left: str,
    right: str,
    verdict: str,
    reason_code: str,
    clause_number: str,
    clause_ids: Iterable[str],
    outbound: str | None,
    band: str,
    notes: str,
) -> dict:
    ids = list(dict.fromkeys(clause_ids))
    for cid in ids:
        if cid not in CLAUSES:
            raise KeyError(cid)
    return {
        "left": left,
        "right": right,
        "verdict": verdict,
        "reason_code": reason_code,
        "clause_number": clause_number,
        "clause_ids": ids,
        "outbound": outbound,
        "confidence_band": band,
        "independent_verification_path": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/RES-0135/probe1_rebuild_matrix.py"
        ),
        "notes": notes,
        "canonical_spdx": {
            "left": CANONICAL_SPDX[left],
            "right": CANONICAL_SPDX[right],
        },
    }


def build_cells() -> list[dict]:
    return [pair_cell(a, b) for a in AXES for b in AXES]


def assert_every_cell_cites_clause(cells: list[dict]) -> None:
    if len(cells) != len(AXES) * len(AXES):
        raise AssertionError(f"matrix not square: {len(cells)}")
    seen: set[tuple[str, str]] = set()
    for cell in cells:
        key = (cell["left"], cell["right"])
        if key in seen:
            raise AssertionError(f"duplicate cell {key}")
        seen.add(key)
        if cell["verdict"] not in VERDICTS:
            raise AssertionError(f"bad verdict {cell['verdict']}")
        if not cell.get("clause_number"):
            raise AssertionError(f"cell {key} missing clause_number")
        ids = cell.get("clause_ids") or []
        if len(ids) < 2:
            raise AssertionError(f"cell {key} needs two clause signals, got {ids}")
        for cid in ids:
            if cid not in CLAUSES:
                raise AssertionError(f"cell {key} unknown clause {cid}")
    expected = {(a, b) for a in AXES for b in AXES}
    if seen != expected:
        raise AssertionError("axis coverage hole")


def verdict_counts(cells: list[dict]) -> dict[str, int]:
    counts = {v: 0 for v in VERDICTS}
    for cell in cells:
        counts[cell["verdict"]] += 1
    return counts


def index_verdicts(cells: list[dict]) -> dict[tuple[str, str], str]:
    return {(c["left"], c["right"]): c["verdict"] for c in cells}
