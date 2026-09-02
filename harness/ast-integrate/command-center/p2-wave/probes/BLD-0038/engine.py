#!/usr/bin/env python3
"""Speaker-attributing miner + decision/catalog reconcilation for BLD-0038."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE_CORPUS = HERE / "fixtures" / "labelled-corpus.md"
FIXTURE_GOLD = HERE / "fixtures" / "labelled-sample.json"
FIXTURE_DECISIONS = HERE / "fixtures" / "decision-log.md"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

LIVE_CORPUS_CANDIDATES = [
    Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"),
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"),
    REPO / "_USER-PROMPTS.md",
    REPO / "command-center" / "_USER-PROMPTS.md",
]
LIVE_DECISION_CANDIDATES = [
    REPO / "command-center" / "OWNER-DECISIONS.md",
    REPO / "command-center" / "17-DECISION-LOG.md",
    REPO / "17-DECISION-LOG.md",
    REPO / "32-OWNER-DECISIONS.md",
]

TURN_RE = re.compile(
    r"^## Message[^\n]*\n"
    r"\*\*Speaker:\*\*\s*(?P<speaker>\w+)\n"
    r"\*\*Kind:\*\*\s*(?P<kind>[\w-]+)\n"
    r"(?P<body>.*?)(?=^## Message|\Z)",
    re.M | re.S,
)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")
NORMATIVE_RE = re.compile(
    r"\b("
    r"never|always|must(?:\s+not)?|shall|do\s+not|don't|"
    r"prefer|prohibit(?:ed)?|required|forbidden|no longer"
    r")\b",
    re.I,
)
STOP = frozenset(
    """
    a an the of to for and or in on at by with from as is are was were be been
    this that those these it its their our your not do does did doing done
    must never always shall should would could may might about into over after
    before than then also just only very more most such other some any each
    """.split()
)
OPUS_RE = re.compile(
    r"opus.{0,48}not.{0,24}sonnet|prefer\s+opus|opus,?\s+not\s+sonnet|not\s+sonnet",
    re.I,
)


def sha256_file(path: Path) -> tuple[str, int]:
    import hashlib

    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        try:
            if p.is_file() and p.stat().st_size > 0:
                return p
        except OSError:
            continue
    return None


def load_gold() -> dict:
    return json.loads(FIXTURE_GOLD.read_text(encoding="utf-8"))


def line_of(text: str, snippet: str) -> int:
    idx = text.find(snippet)
    if idx < 0:
        return 0
    return text[:idx].count("\n") + 1


def parse_turns(text: str) -> list[dict]:
    turns = []
    for m in TURN_RE.finditer(text):
        body = m.group("body").strip("\n")
        turns.append(
            {
                "speaker": m.group("speaker").strip().lower(),
                "kind": m.group("kind").strip().lower(),
                "body": body,
                "start_line": text[: m.start()].count("\n") + 1,
            }
        )
    return turns


def split_sentences(body: str) -> list[str]:
    chunks = []
    for para in re.split(r"\n+", body):
        para = para.strip()
        if not para or para.startswith("```") or para.startswith("#"):
            continue
        if para.startswith("**"):
            continue
        parts = SENTENCE_RE.split(para) if para[:1].isupper() or '"' in para[:1] else [para]
        for p in parts:
            s = p.strip().strip("`")
            if len(s) >= 12:
                chunks.append(s)
    return chunks


def is_normative(sentence: str) -> bool:
    if not NORMATIVE_RE.search(sentence):
        return False
    lowered = sentence.lower()
    if "that is not a requirement" in lowered:
        return False
    return True


def is_formal_prompt(turn: dict) -> bool:
    if turn["kind"] in {"formal-prompt-block", "prompt-block"}:
        return True
    body = turn["body"]
    return "```prompt-block" in body or re.search(
        r"^# Prompt (One|Two)\b", body, re.M
    ) is not None


def mine_asides(text: str, source_path: str) -> list[dict]:
    rows = []
    n = 0
    for turn in parse_turns(text):
        speaker = turn["speaker"]
        formal = is_formal_prompt(turn)
        for sent in split_sentences(turn["body"]):
            if speaker != "owner":
                continue
            if formal:
                continue
            if not is_normative(sent):
                continue
            n += 1
            line = line_of(text, sent) or turn["start_line"]
            cls = "opus-not-sonnet" if OPUS_RE.search(sent) else "owner-aside"
            rows.append(
                {
                    "id": f"REQ-{n:03d}",
                    "owner_quote": sent,
                    "line": int(line),
                    "source_path": source_path,
                    "speaker": "owner",
                    "outside_formal_prompt_block": True,
                    "normative_class": cls,
                }
            )
    return rows


def tokens(s: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z0-9][a-z0-9_-]{3,}", s.lower())
        if t not in STOP
    }


def haystack_for_unit(u: dict) -> str:
    bits = [
        str(u.get("id") or ""),
        str(u.get("title") or ""),
        str(u.get("question_or_target") or u.get("target") or ""),
        str(u.get("evidence_requirement") or ""),
    ]
    tests = u.get("tests_required") or u.get("tests_required") or []
    if isinstance(tests, list):
        bits.extend(str(t) for t in tests)
    role = u.get("assigned_model_vendor_role") or {}
    if isinstance(role, dict):
        bits.append(str(role.get("basis") or ""))
        bits.append(str(role.get("model") or ""))
    return "\n".join(bits)


def load_catalog_index() -> list[dict]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    out = []
    for u in data.get("work_units") or []:
        if not isinstance(u, dict) or not u.get("id"):
            continue
        text = haystack_for_unit(u)
        out.append({"id": u["id"], "kind": "catalog-unit", "text": text})
    return out


def load_decision_index() -> tuple[list[dict], dict]:
    rows: list[dict] = []
    resolved = {
        "fixture": {
            "path": str(FIXTURE_DECISIONS.relative_to(REPO)).replace("\\", "/"),
            "present": FIXTURE_DECISIONS.is_file(),
        },
        "live": [],
    }
    if FIXTURE_DECISIONS.is_file():
        text = FIXTURE_DECISIONS.read_text(encoding="utf-8")
        rows.append(
            {
                "id": "FIXTURE-DECISION-LOG",
                "kind": "decision-log",
                "text": text,
            }
        )
    live = []
    for p in LIVE_DECISION_CANDIDATES:
        rec = {
            "path": str(p),
            "present": False,
            "bytes": 0,
        }
        try:
            if p.is_file():
                rec["present"] = True
                rec["bytes"] = p.stat().st_size
                rec["path"] = (
                    str(p.relative_to(REPO)).replace("\\", "/")
                    if REPO in p.parents or p.parent == REPO
                    else str(p)
                )
                rows.append(
                    {
                        "id": p.name,
                        "kind": "decision-log",
                        "text": p.read_text(encoding="utf-8", errors="replace"),
                    }
                )
        except OSError:
            pass
        live.append(rec)
    resolved["live"] = live
    return rows, resolved


def phrase_hit(quote: str, hay: str) -> bool:
    q = quote.lower()
    h = hay.lower()
    checks = [
        ("pr-only" in q or "pr only" in q) and ("pr-only" in h or "pr only" in h),
        ("delete-all" in q or "delete all" in q) and ("delete-all" in h or "delete all" in h),
        ("tools/lib" in q or "tools/lib/" in q) and ("tools/lib" in h),
        ("remote" in q and "never" in q)
        and ("never create remotes" in h or "no-remote" in h or "no remotes" in h),
        OPUS_RE.search(quote) is not None
        and (
            "opus floor" in h
            or "opus-not-sonnet" in h
            or "not-sonnet" in h
            or ("opus" in h and "sonnet" in h)
        ),
    ]
    if any(checks):
        return True
    qt = tokens(quote)
    ht = tokens(hay)
    if len(qt) < 4:
        return False
    overlap = qt & ht
    return len(overlap) >= 5 and len(overlap) / max(len(qt), 1) >= 0.45


def reconcile(rows: list[dict], catalogs: list[dict], decisions: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        quote = row["owner_quote"]
        hit = None
        for d in decisions:
            if phrase_hit(quote, d["text"]):
                hit = f"{d['kind']}:{d['id']}"
                break
        if hit is None:
            for c in catalogs:
                if phrase_hit(quote, c["text"]):
                    hit = f"{c['kind']}:{c['id']}"
                    break
        covered = "COVERED" if hit else "GAP"
        rec = dict(row)
        rec["coverage"] = covered
        rec["covered_by"] = hit or ""
        out.append(rec)
    return out


def resolve_corpus() -> dict:
    live = first_existing(LIVE_CORPUS_CANDIDATES)
    rec = {
        "labelled_fixture": {
            "path": str(FIXTURE_CORPUS.relative_to(REPO)).replace("\\", "/"),
            "present": FIXTURE_CORPUS.is_file(),
        },
        "live": {
            "present": live is not None,
            "path": str(live) if live else None,
            "bytes": live.stat().st_size if live else 0,
        },
        "catalog_declared": (
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"
        ),
    }
    return rec


def attributed_quotes(rows: list[dict]) -> str:
    return "\n".join(r.get("owner_quote") or "" for r in rows)


def speaker_control(rows: list[dict], gold: dict | None = None) -> dict:
    gold = gold or load_gold()
    blob = attributed_quotes(rows)
    leaked = []
    for item in gold["agent_must_not_attribute"]:
        if item["snippet"] in blob:
            leaked.append(item["id"])
    missing = []
    for item in gold["owner_asides_must_find"]:
        if item["snippet"] not in blob:
            missing.append(item["id"])
    prompt_leaked = []
    for item in gold["in_prompt_block_must_not_mine_as_aside"]:
        if item["snippet"] in blob:
            prompt_leaked.append(item["id"])
    weather = []
    for item in gold.get("non_normative_owner_must_not_mine") or []:
        if item["snippet"] in blob:
            weather.append(item["id"])
    opus = [r for r in rows if r.get("normative_class") == "opus-not-sonnet" or OPUS_RE.search(r.get("owner_quote") or "")]
    return {
        "pass": not leaked and not missing and not prompt_leaked and not weather and bool(opus),
        "agent_leaked": leaked,
        "owner_missing": missing,
        "prompt_block_leaked": prompt_leaked,
        "non_normative_mined": weather,
        "opus_not_sonnet_found": bool(opus),
        "opus_quotes": [r["owner_quote"] for r in opus],
        "agent_sentences_rejected": len(gold["agent_must_not_attribute"]),
    }


def coverage_control(rows: list[dict], gold: dict | None = None) -> dict:
    gold = gold or load_gold()
    blob_cov = [(r.get("owner_quote") or "", r.get("coverage")) for r in rows]
    pr = [r for r in rows if "pr-only" in (r.get("owner_quote") or "").lower()]
    planted = [r for r in rows if "hedge word" in (r.get("owner_quote") or "").lower()]
    pr_ok = bool(pr) and all(r.get("coverage") == "COVERED" for r in pr)
    gap_ok = bool(planted) and all(r.get("coverage") == "GAP" for r in planted)
    return {
        "pass": pr_ok and gap_ok,
        "pr_only_rows": len(pr),
        "pr_only_covered": pr_ok,
        "planted_gap_rows": len(planted),
        "planted_gap_ok": gap_ok,
        "gold_covered_control_present": any(
            g["class"] == "covered-control" for g in gold["owner_asides_must_find"]
        ),
        "coverage_blob_n": len(blob_cov),
    }


def mine_fixture() -> tuple[list[dict], str]:
    text = FIXTURE_CORPUS.read_text(encoding="utf-8")
    rel = str(FIXTURE_CORPUS.relative_to(REPO)).replace("\\", "/")
    return mine_asides(text, rel), text


def mine_live(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        rel = str(path.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        rel = str(path)
    # Live Prompt One export is not the labelled fixture format. Only mine
    # labelled turns when the speaker headers exist; otherwise record skip.
    if "**Speaker:**" in text and "## Message" in text:
        return mine_asides(text, rel)
    return []


def build_rows() -> tuple[list[dict], dict]:
    fixture_rows, _ = mine_fixture()
    corpus_res = resolve_corpus()
    live_path = first_existing(LIVE_CORPUS_CANDIDATES)
    live_rows = mine_live(live_path) if live_path else []
    catalogs = load_catalog_index()
    decisions, dec_res = load_decision_index()
    rows = reconcile(fixture_rows + live_rows, catalogs, decisions)
    meta = {
        "corpus": corpus_res,
        "decisions": dec_res,
        "catalog": {
            "path": "command-center/WORK-UNIT-CATALOG.json",
            "present": CATALOG.is_file(),
            "units_indexed": len(catalogs),
        },
        "fixture_rows": len(fixture_rows),
        "live_rows": len(live_rows),
    }
    return rows, meta
