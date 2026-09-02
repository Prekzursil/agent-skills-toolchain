"""AUD-0037 claim-evidence-anchor resolution.

Probe 1: mechanical file existence + line count (same question as
tools/council/artifacts/claims.py:resolve_anchor).
Probe 2: semantic SUPPORTS / MENTIONS-ONLY / CONTRADICTS of the cited span.
A mechanically resolved span that is MENTIONS-ONLY is the high-value finding.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
UID = "AUD-0037"
OUT_REL = "command-center/audit/AUD-0037-claim-evidence-anchor-resolution.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
REGISTRY_REL = "command-center/CLAIM-REGISTRY.json"
FIXTURES_REL = "command-center/p2-wave/probes/AUD-0037/fixtures"
SENTINEL = (
    "SUCCESS:AUD-0037 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For every claim in CLAIM-REGISTRY.json, does its cited file:line exist "
    "today, and does the text at that line actually support the claim rather "
    "than merely mention its subject?"
)
PLANTED_TEXT = "The widget protocol requires a signed handshake."

TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
ANCHOR_RE = re.compile(r"^(?P<path>.+?)(?::(?P<start>\d+)(?:-(?P<end>\d+))?)?$")
CONTRAST_RE = re.compile(
    r"\brather than\b|\binstead of\b|\bas opposed to\b", re.I
)
STOP = frozenset(
    """
    a an the of to for and or in on at by as it its this that these those
    be is are was were been being with from into than then so if when while
    which who whom what how has have had do does did can could would should
    may might must shall will only also just any all each every both few more
    most other some such own same too very s t now we they them their our
    you your i me my we us before after
    """.split()
)
NEG = frozenset(
    {
        "not",
        "never",
        "cannot",
        "without",
        "dont",
        "doesnt",
        "isnt",
        "arent",
        "wasnt",
        "werent",
        "cant",
        "wont",
    }
)
LEMMAS = {
    "requires": "require",
    "required": "require",
    "requiring": "require",
    "resolves": "resolve",
    "resolved": "resolve",
    "resolving": "resolve",
    "retrieves": "retrieve",
    "retrieved": "retrieve",
    "retrieving": "retrieve",
    "supports": "support",
    "supported": "support",
    "mentions": "mention",
    "mentioned": "mention",
    "anchors": "anchor",
    "claims": "claim",
    "handshakes": "handshake",
    "protocols": "protocol",
    "widgets": "widget",
    "deliberated": "deliberate",
    "deliberation": "deliberate",
}


def repo_root() -> Path:
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file() and (
            p / "command-center" / "p2-wave" / "_measure_one_delivered.py"
        ).is_file():
            return p
    raise RuntimeError("AUD-0037: cannot locate repo root")


REPO = repo_root()


def catalog_sentinel() -> str:
    catalog = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(
            encoding="utf-8"
        )
    )
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UID:
            return str(unit.get("completion_sentinel") or SENTINEL)
    return SENTINEL


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_path() -> Path:
    return REPO / OUT_REL


def load_registry(path: Path | None = None) -> dict[str, Any]:
    target = path or (REPO / REGISTRY_REL)
    if not target.is_file():
        return {"claims": [], "path": REGISTRY_REL, "present": False}
    doc = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{target} is not a JSON object")
    claims = doc.get("claims") or []
    if not isinstance(claims, list):
        claims = []
    return {
        "claims": [c for c in claims if isinstance(c, Mapping)],
        "path": REGISTRY_REL,
        "present": True,
        "schema_version": doc.get("schema_version"),
        "profile": doc.get("profile"),
    }


def parse_anchor(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        path = str(raw.get("path") or "").replace("\\", "/").strip()
        if not path:
            raise ValueError(f"anchor missing path: {raw!r}")
        start = raw.get("start_line", raw.get("line"))
        end = raw.get("end_line", start)
        start_i = int(start) if start not in (None, "") else None
        end_i = int(end) if end not in (None, "") else start_i
        return {"path": path, "start_line": start_i, "end_line": end_i}
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"empty anchor: {raw!r}")
    text = raw.replace("\\", "/").strip()
    m = ANCHOR_RE.match(text)
    if not m:
        return {"path": text, "start_line": None, "end_line": None}
    start = m.group("start")
    end = m.group("end")
    start_i = int(start) if start else None
    end_i = int(end) if end else start_i
    return {
        "path": m.group("path"),
        "start_line": start_i,
        "end_line": end_i,
    }


def count_lines(path: Path, max_bytes: int = 2_000_000) -> int:
    data = path.read_bytes()[:max_bytes].replace(b"\r\n", b"\n")
    text = data.decode("utf-8", "replace")
    if not text:
        return 0
    if text.endswith("\n"):
        return text.count("\n")
    return text.count("\n") + 1


def mechanical_resolve(raw: Any, *, root: Path | None = None) -> dict[str, Any]:
    """File exists and has at least start_line lines. Not a semantic read."""
    root = root or REPO
    parsed = parse_anchor(raw)
    rel = parsed["path"]
    path = Path(rel)
    if not path.is_absolute():
        path = root / rel
    exists = path.is_file()
    line_count = count_lines(path) if exists else 0
    start = parsed["start_line"]
    end = parsed["end_line"]
    line_ok = start is None or (exists and line_count >= start)
    resolved = bool(exists and line_ok)
    if resolved:
        reason = "ok"
    elif not exists:
        reason = "missing-file"
    else:
        reason = "line-past-eof"
    return {
        "path": rel,
        "start_line": start,
        "end_line": end,
        "exists": exists,
        "line_count": line_count,
        "resolved": resolved,
        "reason": reason,
    }


def library_resolve(raw: Any) -> dict[str, Any]:
    tools = REPO / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    try:
        from council.artifacts.claims import resolve_anchor
    except Exception as exc:
        return {"error": f"{type(exc).__name__}:{exc}", "resolved": None}
    try:
        return dict(resolve_anchor(raw, root=REPO))
    except Exception as exc:
        return {"error": f"{type(exc).__name__}:{exc}", "resolved": None}


def read_span(rel: str, start: int | None, end: int | None) -> str:
    path = REPO / rel
    text = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if start is None:
        return "\n".join(lines)
    i0 = max(1, start) - 1
    i1 = end if end is not None else start
    i1 = max(i1, start)
    return "\n".join(lines[i0:i1])


def stem(word: str) -> str:
    w = word.lower()
    w = LEMMAS.get(w, w)
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ing") and len(w) > 5:
        return w[:-3]
    if w.endswith("ed") and len(w) > 4:
        w2 = w[:-2]
        return LEMMAS.get(w2, w2)
    if w.endswith("es") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def raw_tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


def content_stems(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for tok in raw_tokens(text):
        if tok in STOP or tok in NEG:
            continue
        s = stem(tok)
        if not s or s in STOP or len(s) < 2:
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def split_contrast(text: str) -> tuple[str, str]:
    m = CONTRAST_RE.search(text or "")
    if not m:
        return text or "", ""
    return (text or "")[: m.start()], (text or "")[m.end() :]


def preceding_negated_stems(text: str) -> set[str]:
    raw = raw_tokens(text)
    stems = [stem(t) for t in raw]
    out: set[str] = set()
    for i, s in enumerate(stems):
        if not s or s in STOP:
            continue
        # Only the immediately preceding token. A 3-token window false-fires on
        # "must not carry status VERIFIED unless ...", which supports the claim.
        prev = raw[i - 1] if i else ""
        if prev in NEG:
            out.add(s)
    return out


def semantic_class(
    claim_text: str,
    span_text: str,
    *,
    mechanical_ok: bool,
    subject: str | None = None,
) -> dict[str, Any]:
    if not mechanical_ok:
        return {
            "class": "UNRESOLVED",
            "coverage": 0.0,
            "overlap": [],
            "reason": "span-not-mechanically-resolved",
        }
    span = (span_text or "").strip()
    if not span:
        return {
            "class": "UNRESOLVED",
            "coverage": 0.0,
            "overlap": [],
            "reason": "empty-span",
        }
    affirmed, rejected = split_contrast(claim_text)
    claim_content = content_stems(affirmed or claim_text)
    span_content = content_stems(span)
    rejected_content = set(content_stems(rejected))
    overlap = [s for s in claim_content if s in set(span_content)]
    coverage = (len(overlap) / len(claim_content)) if claim_content else 0.0
    subject_stems = set(content_stems(subject or ""))
    if not subject_stems and claim_content:
        subject_stems = set(claim_content[:2])
    span_set = set(span_content)
    negated = preceding_negated_stems(span)
    affirmed_negated = (set(overlap) & negated) - rejected_content
    if affirmed_negated:
        return {
            "class": "CONTRADICTS",
            "coverage": round(coverage, 4),
            "overlap": overlap,
            "negated_affirmed": sorted(affirmed_negated),
            "reason": "span-negates-affirmed-predicate",
        }
    if (
        len(span_content) <= 2
        and span_set
        and span_set <= (subject_stems | set(claim_content))
        and coverage < 0.4
    ):
        return {
            "class": "MENTIONS-ONLY",
            "coverage": round(coverage, 4),
            "overlap": overlap,
            "reason": "subject-word-without-predicate",
        }
    if coverage >= 0.5 and len(overlap) >= 2:
        return {
            "class": "SUPPORTS",
            "coverage": round(coverage, 4),
            "overlap": overlap,
            "reason": "predicate-coverage",
        }
    if overlap:
        return {
            "class": "MENTIONS-ONLY",
            "coverage": round(coverage, 4),
            "overlap": overlap,
            "reason": "token-overlap-below-support-threshold",
        }
    return {
        "class": "UNRELATED",
        "coverage": 0.0,
        "overlap": [],
        "reason": "no-content-overlap",
    }


def claim_text_of(claim: Mapping[str, Any]) -> str:
    return str(
        claim.get("text")
        or claim.get("claim")
        or claim.get("statement")
        or ""
    ).strip()


def claim_anchors(claim: Mapping[str, Any]) -> list[Any]:
    raw = claim.get("evidence_anchors") or claim.get("anchors") or []
    if isinstance(raw, list):
        return list(raw)
    if raw:
        return [raw]
    return []


def classify_anchor(
    claim: Mapping[str, Any],
    raw_anchor: Any,
    *,
    subject: str | None = None,
) -> dict[str, Any]:
    mech = mechanical_resolve(raw_anchor)
    span = ""
    if mech["resolved"]:
        span = read_span(mech["path"], mech["start_line"], mech["end_line"])
    sem = semantic_class(
        claim_text_of(claim),
        span,
        mechanical_ok=bool(mech["resolved"]),
        subject=subject,
    )
    lib = library_resolve(raw_anchor)
    lib_resolved = lib.get("resolved") if isinstance(lib, dict) else None
    return {
        "anchor": raw_anchor
        if isinstance(raw_anchor, (str, dict))
        else str(raw_anchor),
        "mechanical": mech,
        "library_resolved": lib_resolved,
        "library_error": lib.get("error") if isinstance(lib, dict) else None,
        "span_text": span,
        "semantic": sem,
        "high_value": bool(mech["resolved"] and sem.get("class") == "MENTIONS-ONLY"),
    }


def classify_claim(
    claim: Mapping[str, Any],
    *,
    subject: str | None = None,
    control: str | None = None,
) -> dict[str, Any]:
    anchors = claim_anchors(claim)
    rows = [classify_anchor(claim, a, subject=subject) for a in anchors]
    classes = [r["semantic"]["class"] for r in rows]
    mech_all = bool(rows) and all(r["mechanical"]["resolved"] for r in rows)
    if not rows:
        rollup = "UNRESOLVED"
    elif any(c == "CONTRADICTS" for c in classes):
        rollup = "CONTRADICTS"
    elif any(c == "UNRESOLVED" for c in classes):
        rollup = "UNRESOLVED"
    elif all(c == "SUPPORTS" for c in classes):
        rollup = "SUPPORTS"
    elif "UNRELATED" in classes and not any(
        c in {"SUPPORTS", "MENTIONS-ONLY", "CONTRADICTS"} for c in classes
    ):
        rollup = "UNRELATED"
    else:
        rollup = (
            "MENTIONS-ONLY" if "MENTIONS-ONLY" in classes else classes[0]
        )
    return {
        "id": claim.get("id"),
        "verification_status": str(claim.get("verification_status") or ""),
        "text": claim_text_of(claim),
        "anchor_count": len(anchors),
        "mechanical_all_resolved": mech_all,
        "semantic_rollup": rollup,
        "high_value": any(r["high_value"] for r in rows),
        "control": control,
        "anchors": rows,
    }


def planted_controls() -> list[dict[str, Any]]:
    rel = FIXTURES_REL
    return [
        {
            "id": "AUD-0037-CTRL-mentions-only",
            "text": PLANTED_TEXT,
            "verification_status": "VERIFIED",
            "evidence_anchors": [f"{rel}/mentions-only.txt:1"],
            "subject": "widget",
            "expect_mechanical": True,
            "expect_semantic": "MENTIONS-ONLY",
            "control": "mentions-only",
        },
        {
            "id": "AUD-0037-CTRL-supports",
            "text": PLANTED_TEXT,
            "verification_status": "VERIFIED",
            "evidence_anchors": [f"{rel}/supports.txt:1"],
            "subject": "widget",
            "expect_mechanical": True,
            "expect_semantic": "SUPPORTS",
            "control": "supports",
        },
        {
            "id": "AUD-0037-CTRL-contradicts",
            "text": PLANTED_TEXT,
            "verification_status": "VERIFIED",
            "evidence_anchors": [f"{rel}/contradicts.txt:1"],
            "subject": "widget",
            "expect_mechanical": True,
            "expect_semantic": "CONTRADICTS",
            "control": "contradicts",
        },
        {
            "id": "AUD-0037-CTRL-missing-file",
            "text": PLANTED_TEXT,
            "verification_status": "VERIFIED",
            "evidence_anchors": [f"{rel}/does-not-exist.txt:1"],
            "subject": "widget",
            "expect_mechanical": False,
            "expect_reason": "missing-file",
            "expect_semantic": "UNRESOLVED",
            "control": "missing-file",
        },
        {
            "id": "AUD-0037-CTRL-line-past-eof",
            "text": PLANTED_TEXT,
            "verification_status": "VERIFIED",
            "evidence_anchors": [f"{rel}/short.txt:99"],
            "subject": "widget",
            "expect_mechanical": False,
            "expect_reason": "line-past-eof",
            "expect_semantic": "UNRESOLVED",
            "control": "line-past-eof",
        },
    ]


def tally(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sem_counts: dict[str, int] = {}
    n_mech_ok = 0
    n_mech_bad = 0
    n_high = 0
    n_verified_high = 0
    n_verified = 0
    n_anchors = 0
    n_lib_disagree = 0
    for row in rows:
        n_anchors += int(row.get("anchor_count") or 0)
        if row.get("mechanical_all_resolved"):
            n_mech_ok += 1
        else:
            n_mech_bad += 1
        cls = str(row.get("semantic_rollup") or "")
        sem_counts[cls] = sem_counts.get(cls, 0) + 1
        if row.get("high_value"):
            n_high += 1
        status = str(row.get("verification_status") or "").upper()
        if status == "VERIFIED":
            n_verified += 1
            if row.get("high_value"):
                n_verified_high += 1
        for anc in row.get("anchors") or []:
            lib_r = anc.get("library_resolved")
            loc_r = (anc.get("mechanical") or {}).get("resolved")
            if lib_r is not None and bool(lib_r) != bool(loc_r):
                n_lib_disagree += 1
    return {
        "n_claims": len(rows),
        "n_anchors": n_anchors,
        "n_mechanically_resolved_claims": n_mech_ok,
        "n_mechanically_unresolved_claims": n_mech_bad,
        "semantic_counts": sem_counts,
        "n_high_value_mentions_only": n_high,
        "n_verified": n_verified,
        "n_verified_high_value": n_verified_high,
        "n_library_disagreements": n_lib_disagree,
    }


def evaluate_control(spec: Mapping[str, Any]) -> dict[str, Any]:
    row = classify_claim(
        spec, subject=spec.get("subject"), control=spec.get("control")
    )
    mech_ok = bool(row["mechanical_all_resolved"])
    want_mech = bool(spec.get("expect_mechanical"))
    want_sem = spec.get("expect_semantic")
    want_reason = spec.get("expect_reason")
    reasons = [
        (a.get("mechanical") or {}).get("reason") for a in row.get("anchors") or []
    ]
    reason_ok = True if want_reason is None else want_reason in reasons
    sem_ok = row["semantic_rollup"] == want_sem
    passed = (mech_ok == want_mech) and sem_ok and reason_ok
    return {
        "id": spec.get("id"),
        "control": spec.get("control"),
        "passed": passed,
        "expect_mechanical": want_mech,
        "got_mechanical": mech_ok,
        "expect_semantic": want_sem,
        "got_semantic": row["semantic_rollup"],
        "expect_reason": want_reason,
        "got_reasons": reasons,
        "row": row,
    }


def census() -> dict[str, Any]:
    registry = load_registry()
    live_rows = [classify_claim(c) for c in registry["claims"]]
    controls = [evaluate_control(spec) for spec in planted_controls()]
    live_t = tally(live_rows)
    return {
        "unit_id": UID,
        "registry_present": registry["present"],
        "registry_path": registry["path"],
        "live": live_rows,
        "live_tally": live_t,
        "controls": controls,
        "controls_pass": all(c["passed"] for c in controls),
        "library_disagreements": live_t["n_library_disagreements"],
    }


def slim_anchor(a: dict[str, Any]) -> dict[str, Any]:
    mech = a.get("mechanical") or {}
    sem = a.get("semantic") or {}
    return {
        "path": mech.get("path"),
        "start_line": mech.get("start_line"),
        "end_line": mech.get("end_line"),
        "exists": mech.get("exists"),
        "line_count": mech.get("line_count"),
        "mechanical_resolved": mech.get("resolved"),
        "mechanical_reason": mech.get("reason"),
        "library_resolved": a.get("library_resolved"),
        "span_text": a.get("span_text"),
        "semantic_class": sem.get("class"),
        "semantic_reason": sem.get("reason"),
        "coverage": sem.get("coverage"),
        "overlap": sem.get("overlap"),
        "high_value": a.get("high_value"),
    }


def slim_claim(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "verification_status": row.get("verification_status"),
        "text": row.get("text"),
        "anchor_count": row.get("anchor_count"),
        "mechanical_all_resolved": row.get("mechanical_all_resolved"),
        "semantic_rollup": row.get("semantic_rollup"),
        "high_value": row.get("high_value"),
        "control": row.get("control"),
        "anchors": [slim_anchor(a) for a in row.get("anchors") or []],
    }


def probe1_payload() -> dict[str, Any]:
    data = census()
    mech_controls = [
        c
        for c in data["controls"]
        if c["control"] in {"missing-file", "line-past-eof", "mentions-only"}
    ]
    return {
        "probe": "probe1-mechanical-resolution",
        "unit_id": UID,
        "registry_present": data["registry_present"],
        "live_tally": {
            "n_claims": data["live_tally"]["n_claims"],
            "n_anchors": data["live_tally"]["n_anchors"],
            "n_mechanically_resolved_claims": data["live_tally"][
                "n_mechanically_resolved_claims"
            ],
            "n_mechanically_unresolved_claims": data["live_tally"][
                "n_mechanically_unresolved_claims"
            ],
            "n_library_disagreements": data["live_tally"]["n_library_disagreements"],
        },
        "controls": [
            {
                "id": c["id"],
                "control": c["control"],
                "passed": c["passed"],
                "got_mechanical": c["got_mechanical"],
                "got_reasons": c["got_reasons"],
            }
            for c in mech_controls
        ],
        "library_errors": [
            a.get("library_error")
            for row in data["live"]
            for a in row.get("anchors") or []
            if a.get("library_error")
        ],
        "pass": (
            all(c["passed"] for c in mech_controls)
            and data["live_tally"]["n_library_disagreements"] == 0
            and not any(
                a.get("library_error")
                for row in data["live"]
                for a in row.get("anchors") or []
            )
        ),
    }


def probe2_payload() -> dict[str, Any]:
    data = census()
    sem_controls = [
        c
        for c in data["controls"]
        if c["control"] in {"mentions-only", "supports", "contradicts"}
    ]
    mentions = next(c for c in sem_controls if c["control"] == "mentions-only")
    return {
        "probe": "probe2-semantic-read",
        "unit_id": UID,
        "live_tally": {
            "n_claims": data["live_tally"]["n_claims"],
            "semantic_counts": data["live_tally"]["semantic_counts"],
            "n_high_value_mentions_only": data["live_tally"][
                "n_high_value_mentions_only"
            ],
            "n_verified_high_value": data["live_tally"]["n_verified_high_value"],
        },
        "controls": [
            {
                "id": c["id"],
                "control": c["control"],
                "passed": c["passed"],
                "got_semantic": c["got_semantic"],
                "got_mechanical": c["got_mechanical"],
            }
            for c in sem_controls
        ],
        "mentions_only_not_treated_as_resolved_support": (
            mentions["got_semantic"] == "MENTIONS-ONLY"
            and mentions["got_mechanical"] is True
        ),
        "pass": all(c["passed"] for c in sem_controls)
        and mentions["got_semantic"] == "MENTIONS-ONLY",
    }
