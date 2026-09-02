"""Independent spec-vs-corpus protocol gap.

The 12-COUNCIL-PROTOCOLS-AND-PRESETS.json file and _USER-PROMPTS.md are not
on this worktree. Card names are recovered from WORK-UNIT-CATALOG.json units
CNL-0038..CNL-0046, which enumerate every P-id the catalog says lives in that
file. Spec-named protocols are recovered from catalog units that quote the
spec protocol list at :10915-10946 / :10927 / :10765.

Gap = spec names with no card, recomputed here; not copied from CNL-0050's brief.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
FAMILY_UNITS = [f"CNL-{n:04d}" for n in range(38, 47)]
PID_RE = re.compile(r"\b(P\d{2})\s+([a-z0-9-]+(?:\s+\([^)]+\))?)")
COMMA_PID_RE = re.compile(r",\s*(?=P\d{2}\s)")
STOP = frozenset({"the", "and", "of", "a", "an", "with", "for", "from", "into"})
GENERIC = frozenset(
    {
        "council",
        "councils",
        "protocol",
        "protocols",
        "team",
        "check",
        "round",
        "review",
        "analysis",
        "before",
        "with",
        "from",
    }
)


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def units_by_id(doc: dict) -> dict:
    out = {}
    for unit in doc.get("work_units") or []:
        if isinstance(unit, dict) and isinstance(unit.get("id"), str):
            out[unit["id"]] = unit
    return out


def method_a_regex(question: str) -> list[tuple[str, str]]:
    return [(pid, slug.strip()) for pid, slug in PID_RE.findall(question)]


def method_b_comma_split(question: str) -> list[tuple[str, str]]:
    marker = "named so no member can fall through a family mis-assignment ("
    start = question.find(marker)
    if start < 0:
        return []
    inner_start = start + len(marker)
    tail = question[inner_start:]
    end_m = re.search(r"\): For each", tail)
    inner = tail[: end_m.start()] if end_m else tail
    parts = COMMA_PID_RE.split(inner)
    out: list[tuple[str, str]] = []
    for part in parts:
        m = re.match(r"(P\d{2})\s+(.+)$", part.strip())
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out


def cards_from_catalog(doc: dict) -> dict:
    units = units_by_id(doc)
    by_family = []
    all_a: list[dict] = []
    all_b: list[dict] = []
    for uid in FAMILY_UNITS:
        unit = units.get(uid)
        if not unit:
            raise SystemExit(f"catalog missing {uid}")
        q = str(unit.get("question_or_target") or "")
        a = method_a_regex(q)
        b = method_b_comma_split(q)
        fam = {
            "unit_id": uid,
            "title": unit.get("title"),
            "method_a": [{"id": i, "slug": s} for i, s in a],
            "method_b": [{"id": i, "slug": s} for i, s in b],
            "method_a_n": len(a),
            "method_b_n": len(b),
            "methods_agree": a == b,
        }
        by_family.append(fam)
        all_a.extend(fam["method_a"])
        all_b.extend(fam["method_b"])
    ids_a = [c["id"] for c in all_a]
    ids_b = [c["id"] for c in all_b]
    return {
        "source": str(CATALOG.relative_to(REPO)).replace("\\", "/"),
        "source_present": CATALOG.is_file(),
        "library_file_present": (
            (REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json").is_file()
            or (REPO / "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json").is_file()
        ),
        "family_units": by_family,
        "cards_method_a": all_a,
        "cards_method_b": all_b,
        "n_method_a": len(all_a),
        "n_method_b": len(all_b),
        "unique_ids_a": sorted(set(ids_a)),
        "unique_ids_b": sorted(set(ids_b)),
        "methods_agree": all_a == all_b and len(all_a) == 58,
        "expected_n": 58,
    }


def _split_register_list(question: str) -> list[str]:
    m = re.search(
        r"register\s+(.+?)\s+as library entries that compile a CouncilSpec",
        question,
        re.I,
    )
    if not m:
        return []
    return [p.strip() for p in m.group(1).split(",") if p.strip()]


def spec_names_from_catalog(doc: dict) -> dict:
    units = units_by_id(doc)
    names: list[dict] = []

    imp = units.get("IMP-0256") or {}
    for name in _split_register_list(str(imp.get("question_or_target") or "")):
        names.append(
            {
                "name": name,
                "source_unit": "IMP-0256",
                "source_anchor": "question_or_target (quotes _USER-PROMPTS.md:10915-10946)",
            }
        )

    tst = units.get("TST-0294") or {}
    tq = str(tst.get("question_or_target") or "")
    if "steelman-before-rebuttal" in tq:
        names.append(
            {
                "name": "steelman-before-rebuttal",
                "source_unit": "TST-0294",
                "source_anchor": "question_or_target (quotes :10946 / :10927 protocol list)",
            }
        )

    res = units.get("RES-0158") or {}
    for inp in res.get("inputs") or []:
        text = str(inp)
        if "10927" in text and "incl." in text:
            m = re.search(r"incl\.\s*(.+)$", text)
            if m:
                blob = m.group(1)
                blob = re.sub(r"\)$", "", blob)
                for part in blob.split(","):
                    n = part.strip()
                    if n:
                        names.append(
                            {
                                "name": n,
                                "source_unit": "RES-0158",
                                "source_anchor": "inputs citing _USER-PROMPTS.md:10927",
                            }
                        )

    cnl49 = units.get("CNL-0049") or {}
    if "Steelman-before-rebuttal is required by the spec" in str(
        cnl49.get("question_or_target") or ""
    ):
        names.append(
            {
                "name": "steelman-before-rebuttal",
                "source_unit": "CNL-0049",
                "source_anchor": "question_or_target (spec requirement)",
            }
        )

    seen = set()
    uniq = []
    for row in names:
        key = _norm(row["name"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    return {
        "names": uniq,
        "n": len(uniq),
        "note": (
            "_USER-PROMPTS.md is not on this worktree; names are catalog quotations "
            "of the spec protocol list, not a read of the original file."
        ),
    }


def _norm(s: str) -> str:
    s = s.lower().strip()
    s = s.replace("_", "-")
    s = re.sub(r"\s+", "-", s)
    return s


def _tokens(s: str) -> list[str]:
    parts = re.findall(r"[a-z0-9]+", s.lower())
    return [p for p in parts if p not in STOP and p not in GENERIC]


def method_substring(spec: str, card_slug: str) -> bool:
    a, b = _norm(spec), _norm(card_slug)
    a = re.sub(r"[()]", "", a)
    b = re.sub(r"[()]", "", b)
    if len(a) >= 4 and (a == b or a in b or b in a):
        return True
    return False


def method_token(spec: str, card_slug: str) -> bool:
    st, ct = _tokens(spec), _tokens(card_slug)
    for x in st:
        for y in ct:
            if x == y and len(x) >= 4:
                return True
            lo, hi = (x, y) if len(x) <= len(y) else (y, x)
            if len(lo) >= 6 and hi.startswith(lo):
                return True
    return False


def match_cards(spec_name: str, cards: list[dict]) -> dict:
    sub = [c for c in cards if method_substring(spec_name, c["slug"])]
    tok = [c for c in cards if method_token(spec_name, c["slug"])]
    both = [c for c in sub if c in tok]
    return {
        "substring_hits": [{"id": c["id"], "slug": c["slug"]} for c in sub],
        "token_hits": [{"id": c["id"], "slug": c["slug"]} for c in tok],
        "conservative_hits": [{"id": c["id"], "slug": c["slug"]} for c in both],
        "has_card_conservative": bool(both),
        "has_card_substring": bool(sub),
        "has_card_token": bool(tok),
    }


def gap_report(doc: dict | None = None) -> dict:
    doc = doc or load_catalog()
    cards = cards_from_catalog(doc)
    spec = spec_names_from_catalog(doc)
    card_list = cards["cards_method_a"]
    rows = []
    gap_cons = []
    gap_sub = []
    for item in spec["names"]:
        m = match_cards(item["name"], card_list)
        row = {**item, "match": m}
        rows.append(row)
        if not m["has_card_conservative"]:
            gap_cons.append(item["name"])
        if not m["has_card_substring"]:
            gap_sub.append(item["name"])
    meta = [c for c in card_list if c["id"] in {f"P{n:02d}" for n in range(52, 59)}]
    return {
        "cards": cards,
        "spec": spec,
        "rows": rows,
        "gap_conservative": sorted(gap_cons, key=_norm),
        "gap_substring": sorted(gap_sub, key=_norm),
        "n_gap_conservative": len(gap_cons),
        "n_gap_substring": len(gap_sub),
        "meta_composition_cards": meta,
        "n_meta_composition": len(meta),
        "brief_first_pass_names": ["steelman", "negotiation"],
        "brief_first_pass_is_source_of_gap": False,
        "inherited_from_unit_brief": False,
    }
