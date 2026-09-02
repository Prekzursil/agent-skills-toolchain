#!/usr/bin/env python3
"""ADV-0108: Sherman-Kent band vs evidence-type ceiling, plus grammar missing-band.

Probe 1 classifies each banded claim's evidence type and flags bands above the
ceiling that type can support.

Probe 2 finds forward-looking sentences by grammatical pattern (modals, should,
looks fine, likely fine) rather than by searching for band tokens.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

RANK = {
    "almost-certain": 5,
    "likely": 4,
    "roughly-even": 3,
    "unlikely": 2,
    "remote": 1,
}
CEILING_RANK = {
    "direct_measurement": 5,
    "single_inference": 4,
    "analogy": 3,
    "none": 1,
}
BAND_ALIASES = {
    "almost-certain": "almost-certain",
    "almost certain": "almost-certain",
    "almost_certain": "almost-certain",
    "likely": "likely",
    "probable": "likely",
    "roughly-even": "roughly-even",
    "roughly even": "roughly-even",
    "even chance": "roughly-even",
    "even-chance": "roughly-even",
    "unlikely": "unlikely",
    "remote": "remote",
    "remote chance": "remote",
}
BAND_KEYS = (
    "sherman_kent_band",
    "confidence_band",
    "confidence",
    "kent_band",
    "confidence_label",
)
MD_BAND = re.compile(
    r"\b(ALMOST CERTAIN|LIKELY|ROUGHLY EVEN|EVEN CHANCE|UNLIKELY|REMOTE)\b",
    re.I,
)
SK_IN_SENTENCE = re.compile(
    r"\b(almost-certain|almost certain|roughly-even|roughly even|unlikely|remote)\b"
    r"|\blikely\s*\(\s*\d"
    r"|\bLIKELY\s*\(",
    re.I,
)
FORWARD = re.compile(
    r"\b(?:should|must|will|would|might|may|shall)\s+[A-Za-z]"
    r"|\bgoing to\b"
    r"|\bwe expect\b"
    r"|\blooks fine\b"
    r"|\blook fine\b"
    r"|\blikely fine\b"
    r"|\blikely to\b"
    r"|\bshould work\b",
    re.I,
)
PAST_MEASURE = re.compile(
    r"\b(?:exited|measured|counted|returned|recorded|observed|was|were|had|did)\b",
    re.I,
)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
CTRL_ID_RE = re.compile(r"\bCTRL-[A-Z0-9-]+\b")
JSON_ROOTS = (
    "command-center/receipts",
    "command-center/research",
    "command-center/confirmation",
)
JSON_FILES = ("command-center/CLAIM-REGISTRY.json",)
MD_FILES = ("command-center/p2-wave/P2-BUILD-ROUND1.md",)


def _norm_token(raw: str) -> str:
    token = raw.strip().lower().replace("_", " ")
    token = re.sub(r"\s+", " ", token)
    token = re.split(r"[;(]", token, maxsplit=1)[0].strip()
    token = re.sub(r"\s*\d.*$", "", token).strip()
    return token


def normalize_band(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    token = _norm_token(raw)
    if token in BAND_ALIASES:
        return BAND_ALIASES[token]
    collapsed = token.replace(" ", "-")
    return BAND_ALIASES.get(collapsed)


def classify_evidence_type(obj: dict, text: str = "") -> str:
    blob = json.dumps(obj, default=str).lower()
    text_l = (text or str(obj.get("text") or obj.get("claim") or "")).lower()
    probes = obj.get("probes") if isinstance(obj.get("probes"), list) else []
    live_probe = any(isinstance(p, dict) and p.get("exit_code") == 0 for p in probes)
    has_anchor = bool(obj.get("anchor") or obj.get("anchors"))
    live_parser = any(
        k in obj
        for k in ("strict_clean", "trailing_comma", "line_comment", "both_states")
    )
    measured_words = bool(
        re.search(
            r"\b(measured|exited|sha-?256|count(?:ed)?|direct measurement)\b",
            text_l,
        )
    )
    direct = 0
    if has_anchor:
        direct += 1
    if live_probe:
        direct += 2
    if live_parser:
        direct += 2
    if measured_words:
        direct += 1
    literature = bool(
        obj.get("source_lineage")
        or obj.get("snapshot_sha256")
        or "literature" in blob
        or "doi" in blob
    )
    if any(w in text_l for w in ("analogous", "similar to", "by analogy")):
        if direct < 2:
            return "analogy"
    if direct >= 2:
        return "direct_measurement"
    if literature and direct < 2:
        return "single_inference"
    if direct == 1:
        return "single_inference"
    if any(
        w in text_l
        for w in ("therefore", "implies", "suggests", "we infer", "snapshot implies")
    ):
        return "single_inference"
    return "none"


def within_ceiling(band: str | None, evidence_type: str) -> bool:
    if band is None:
        return False
    return RANK[band] <= CEILING_RANK[evidence_type]


def strip_quoted(text: str) -> str:
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r'"[^"]*"', " ", text)
    return text


def split_sentences(text: str) -> list[str]:
    chunks = SENT_SPLIT.split(text.replace("\n", " ").strip())
    return [c.strip() for c in chunks if len(c.strip()) >= 12]


def is_forward_looking(sentence: str) -> bool:
    unquoted = strip_quoted(sentence)
    if not FORWARD.search(unquoted):
        return False
    if PAST_MEASURE.search(unquoted) and not FORWARD.search(unquoted):
        return False
    return True


def has_sherman_kent_in_sentence(sentence: str) -> bool:
    return bool(SK_IN_SENTENCE.search(sentence))


def _band_from_obj(obj: dict) -> tuple[str | None, str | None]:
    for key in BAND_KEYS:
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return key, val.strip()
    return None, None


def _walk_json(obj: Any, path: list[Any]) -> Iterator[tuple[list[Any], dict]]:
    if isinstance(obj, dict):
        yield path, obj
        for key, val in obj.items():
            yield from _walk_json(val, path + [key])
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            yield from _walk_json(val, path + [i])


def _claim_id(source: str, path: list[Any], fallback: str) -> str:
    for part in reversed(path):
        if isinstance(part, str) and re.match(r"^[A-Z]{2,5}-[0-9]{4}", part):
            return f"{part}:{fallback}"
    return f"{source}:{fallback}"


def harvest_banded_from_obj(obj: dict, source: str, path: list[Any]) -> dict | None:
    key, raw = _band_from_obj(obj)
    if not key:
        return None
    text = str(
        obj.get("text")
        or obj.get("claim")
        or obj.get("finding")
        or obj.get("statement")
        or raw
    )
    cid = str(obj.get("id") or "")
    if not cid:
        cid = _claim_id(source, path, f"{key}:{abs(hash(text)) % 10**8}")
    ev_type = classify_evidence_type(obj, text)
    band = normalize_band(raw)
    control = bool(str(cid).startswith("CTRL-"))
    return {
        "id": cid,
        "source": source,
        "json_path": "/".join(str(p) for p in path[-6:]),
        "band_key": key,
        "band_raw": raw,
        "band_norm": band,
        "lexicon_ok": band is not None,
        "text": text[:500],
        "evidence_type": ev_type,
        "within_ceiling": within_ceiling(band, ev_type) if band else False,
        "anchor": obj.get("anchor") or obj.get("anchors") or None,
        "control": control,
    }


def harvest_json_file(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    try:
        rel = path.relative_to(REPO).as_posix()
    except ValueError:
        rel = path.as_posix()
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for pth, obj in _walk_json(data, []):
        rec = harvest_banded_from_obj(obj, rel, pth)
        if not rec:
            continue
        key = (rec["source"], rec["id"])
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def harvest_markdown_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    rel = path.relative_to(REPO).as_posix()
    out: list[dict] = []
    for i, para in enumerate(re.split(r"\n\s*\n", text)):
        match = MD_BAND.search(para)
        if not match:
            continue
        raw = match.group(1)
        obj: dict[str, Any] = {
            "id": f"{path.stem}:para{i}",
            "text": para.strip()[:500],
            "confidence": raw,
            "anchor": f"{rel}:para{i}",
        }
        if re.search(r"directly executed|two-sided control|measured", para, re.I):
            obj["probes"] = [{"exit_code": 0, "command": "markdown-census"}]
        rec = harvest_banded_from_obj(obj, rel, ["para", i])
        if rec:
            out.append(rec)
    return out


def iter_corpus_json(repo: Path) -> Iterator[Path]:
    for rel in JSON_FILES:
        path = repo / rel
        if path.is_file():
            yield path
    for root in JSON_ROOTS:
        base = repo / root
        if not base.exists():
            continue
        yield from base.rglob("*.json")
    fx = repo / "command-center/p2-wave/probes/ADV-0108/fixtures/controls.json"
    if fx.is_file():
        yield fx


def harvest_banded_claims(repo: Path | None = None) -> list[dict]:
    repo = repo or REPO
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for path in iter_corpus_json(repo):
        for rec in harvest_json_file(path):
            key = (rec["source"], rec["id"])
            if key in seen:
                continue
            seen.add(key)
            out.append(rec)
    for rel in MD_FILES:
        path = repo / rel
        if path.is_file():
            for rec in harvest_markdown_file(path):
                key = (rec["source"], rec["id"])
                if key in seen:
                    continue
                seen.add(key)
                out.append(rec)
    return out


def iter_text_blobs(repo: Path) -> Iterator[tuple[str, str]]:
    md = repo / "command-center/p2-wave/probes/ADV-0108/fixtures/program_report.md"
    if md.is_file():
        yield md.relative_to(repo).as_posix(), md.read_text(encoding="utf-8")
    for rel in MD_FILES:
        path = repo / rel
        if path.is_file():
            yield rel, path.read_text(encoding="utf-8")
    cr = repo / "command-center/CLAIM-REGISTRY.json"
    if cr.is_file():
        try:
            data = json.loads(cr.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            for i, claim in enumerate(data.get("claims") or []):
                if isinstance(claim, dict) and claim.get("text"):
                    cid = claim.get("id") or i
                    yield f"command-center/CLAIM-REGISTRY.json#{cid}", str(claim["text"])
    receipts = repo / "command-center/receipts"
    if receipts.is_dir():
        for path in sorted(receipts.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            rel = path.relative_to(repo).as_posix()
            if not isinstance(data, dict):
                continue
            for field in ("notes", "answer", "question_or_target"):
                val = data.get(field)
                if isinstance(val, str) and len(val) > 20:
                    yield f"{rel}:{field}", val
            for i, ev in enumerate(data.get("evidence") or []):
                if isinstance(ev, dict) and isinstance(ev.get("claim"), str):
                    yield f"{rel}:evidence[{i}].claim", ev["claim"]
    research = repo / "command-center/research"
    if research.is_dir():
        for path in sorted(research.rglob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            rel = path.relative_to(repo).as_posix()
            for _pth, obj in _walk_json(data, []):
                if isinstance(obj, dict) and isinstance(obj.get("text"), str):
                    txt = obj["text"]
                    if len(txt) > 20:
                        yield f"{rel}#{obj.get('id') or 'text'}", txt


def harvest_forward_sentences(repo: Path | None = None) -> list[dict]:
    repo = repo or REPO
    out: list[dict] = []
    seen: set[str] = set()
    for source, text in iter_text_blobs(repo):
        for sent in split_sentences(text):
            if not is_forward_looking(sent):
                continue
            key = f"{source}::{sent[:180]}"
            if key in seen:
                continue
            seen.add(key)
            banded = has_sherman_kent_in_sentence(sent)
            label = None
            for match in CTRL_ID_RE.finditer(text):
                window = text[match.start() : match.start() + 280]
                if sent[:48] in window:
                    label = match.group(0)
                    break
            out.append(
                {
                    "source": source,
                    "sentence": sent[:500],
                    "forward_looking": True,
                    "has_sherman_kent_band": banded,
                    "missing_band": not banded,
                    "control_id": label,
                    "planted": source.endswith("program_report.md"),
                }
            )
    return out


def probe1_result(repo: Path | None = None) -> dict:
    claims = harvest_banded_claims(repo)
    controls = [c for c in claims if c.get("control")]
    live = [c for c in claims if not c.get("control")]
    by_id = {c["id"]: c for c in claims}
    good = by_id.get("CTRL-GOOD-BANDED")
    over = by_id.get("CTRL-OVERCLAIM")
    infer = by_id.get("CTRL-INFERENCE-OK")
    recognized_live = [c for c in live if c.get("lexicon_ok")]
    over_ceiling = [c for c in recognized_live if not c.get("within_ceiling")]
    non_lex = [c for c in live if not c.get("lexicon_ok")]
    good_ok = bool(
        good
        and good.get("band_norm") == "almost-certain"
        and good.get("evidence_type") == "direct_measurement"
        and good.get("within_ceiling")
    )
    over_flagged = bool(
        over
        and over.get("band_norm") == "almost-certain"
        and over.get("evidence_type") == "none"
        and not over.get("within_ceiling")
    )
    infer_ok = bool(
        infer is None
        or (
            infer.get("band_norm") == "likely"
            and infer.get("evidence_type") == "single_inference"
            and infer.get("within_ceiling")
        )
    )
    return {
        "probe": "probe1-banded-ceiling",
        "unit_id": "ADV-0108",
        "n_banded": len(claims),
        "n_live": len(live),
        "n_controls": len(controls),
        "n_recognized_live": len(recognized_live),
        "n_over_ceiling_live": len(over_ceiling),
        "n_non_lexicon_live": len(non_lex),
        "over_ceiling_ids": [c["id"] for c in over_ceiling[:40]],
        "non_lexicon_sample": [
            {"id": c["id"], "band_raw": c["band_raw"], "source": c["source"]}
            for c in non_lex[:20]
        ],
        "controls": {
            "good_banded_passes": good_ok,
            "overclaim_flagged": over_flagged,
            "inference_within_ceiling": infer_ok,
            "good": {
                "found": good is not None,
                "evidence_type": None if good is None else good.get("evidence_type"),
                "within_ceiling": None if good is None else good.get("within_ceiling"),
            },
            "overclaim": {
                "found": over is not None,
                "evidence_type": None if over is None else over.get("evidence_type"),
                "within_ceiling": None if over is None else over.get("within_ceiling"),
            },
        },
        "pass": good_ok and over_flagged and infer_ok,
        "claims_sample": [
            {
                "id": c["id"],
                "band_norm": c["band_norm"],
                "evidence_type": c["evidence_type"],
                "within_ceiling": c["within_ceiling"],
                "lexicon_ok": c["lexicon_ok"],
                "control": c["control"],
                "source": c["source"],
            }
            for c in claims[:60]
        ],
    }


def probe2_result(repo: Path | None = None) -> dict:
    rows = harvest_forward_sentences(repo)
    planted = [r for r in rows if r.get("planted")]
    live = [r for r in rows if not r.get("planted")]
    missing_live = [r for r in live if r.get("missing_band")]
    missing_planted = [r for r in planted if r.get("missing_band")]

    def has_sent(fragment: str, missing: bool | None = None) -> bool:
        needle = fragment.lower()
        for row in rows:
            if needle not in row["sentence"].lower():
                continue
            if missing is None or row["missing_band"] is missing:
                return True
        return False

    planted_unbanded_fires = has_sent("should work without further calibration", True)
    looks_fine_fires = has_sent("look fine", True)
    likely_fine_fires = has_sent("likely fine", True)
    past_silent = not has_sent("exited 0 on 120 scored items")
    mention_silent = not any(
        "without making a prediction" in r["sentence"].lower() and r["missing_band"]
        for r in rows
    )
    good_not_missing = not has_sent("will match the stored digest", True) and has_sent(
        "will match the stored digest", False
    )
    return {
        "probe": "probe2-missing-band-grammar",
        "unit_id": "ADV-0108",
        "n_forward": len(rows),
        "n_planted": len(planted),
        "n_live": len(live),
        "n_missing_live": len(missing_live),
        "n_missing_planted": len(missing_planted),
        "n_banded_forward": sum(1 for r in rows if r["has_sherman_kent_band"]),
        "controls": {
            "planted_unbanded_fires": planted_unbanded_fires,
            "looks_fine_fires": looks_fine_fires,
            "likely_fine_fires": likely_fine_fires,
            "past_measurement_silent": past_silent,
            "mention_silent": mention_silent,
            "good_banded_not_missing": good_not_missing,
        },
        "pass": (
            planted_unbanded_fires
            and looks_fine_fires
            and likely_fine_fires
            and past_silent
            and mention_silent
            and good_not_missing
        ),
        "missing_live_sample": [
            {"source": r["source"], "sentence": r["sentence"][:240]}
            for r in missing_live[:25]
        ],
        "planted_missing": [
            {"sentence": r["sentence"][:240], "control_id": r.get("control_id")}
            for r in missing_planted
        ],
    }


def full_audit(repo: Path | None = None) -> dict:
    repo = repo or REPO
    p1 = probe1_result(repo)
    p2 = probe2_result(repo)
    claims = harvest_banded_claims(repo)
    live = [c for c in claims if not c.get("control")]
    recognized_live = [c for c in live if c.get("lexicon_ok")]
    over_ceiling = [c for c in recognized_live if not c.get("within_ceiling")]
    non_lex = [c for c in live if not c.get("lexicon_ok")]
    return {
        "probe1": p1,
        "probe2": p2,
        "n_live_banded": len(live),
        "n_over_ceiling_live": len(over_ceiling),
        "n_non_lexicon_live": len(non_lex),
        "over_ceiling_live": over_ceiling[:40],
        "non_lexicon_live": non_lex[:40],
    }
