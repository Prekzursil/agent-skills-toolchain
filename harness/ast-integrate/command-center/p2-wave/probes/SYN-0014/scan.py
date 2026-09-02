"""Extract claims and pair each band against its anchor set."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bands import (
    BAND_RANK,
    DECLARED_BANDS,
    FLAG_NO_ANCHOR,
    FLAG_UNSUPPORTED,
    ceiling_rank,
    evidence_type_of,
    find_band_in_text,
    find_hedges,
    normalize_band,
    residue_tokens,
)

TEXT_KEYS = ("claim", "text", "statement", "sentence", "question_or_target")
BAND_KEYS = (
    "confidence",
    "band",
    "confidence_band",
    "sherman_kent",
    "sherman_kent_band",
)
ID_KEYS = ("id", "claim_id", "uid")
SKIP_KEYS = {
    "named_probes",
    "tests",
    "schema",
    "completion_sentinel",
    "question",
    "residual_unknowns",
    "negative_controls",
    "retry",
    "timestamps",
    "downstream_consumers",
    "manifest_registration",
    "produced_by",
    "failure",
    "defects",
    "extensions",
}

# Repo-relative path tokens inside free-text evidence strings.
_PATHISH = re.compile(
    r"(?:(?:command-center|tools|agent-self|platform|tests)/[A-Za-z0-9_./:-]+"
    r"|[A-Za-z0-9_./-]+\.(?:json|py|md|yml|yaml|txt))"
)


def _first_str(obj: dict, keys: tuple[str, ...]) -> str:
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _anchor_entries(obj: dict) -> list[dict]:
    out: list[dict] = []

    def add(path: str, snippet: str, et: object) -> None:
        path = (path or "").strip()
        snippet = (snippet or "").strip()
        if not path and not snippet:
            return
        out.append(
            {
                "path": path,
                "snippet": snippet,
                "evidence_type": str(et).strip() if et else "",
            }
        )

    for key in ("anchors", "evidence_anchors"):
        v = obj.get(key)
        if isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    add(item, "", None)
                elif isinstance(item, dict):
                    add(
                        str(
                            item.get("path")
                            or item.get("anchor")
                            or item.get("file")
                            or ""
                        ),
                        str(
                            item.get("snippet")
                            or item.get("quote")
                            or item.get("raw_output")
                            or ""
                        ),
                        item.get("evidence_type") or item.get("type"),
                    )
        elif isinstance(v, str) and v.strip():
            add(v, "", None)
    a = obj.get("anchor")
    if isinstance(a, str) and a.strip():
        add(a, "", None)
    elif isinstance(a, dict):
        add(
            str(a.get("path") or a.get("file") or ""),
            str(a.get("snippet") or a.get("quote") or ""),
            a.get("evidence_type"),
        )
    probes = obj.get("probes")
    if isinstance(probes, list):
        for p in probes:
            if not isinstance(p, dict):
                continue
            raw = str(p.get("raw_output") or "")
            cmd = str(p.get("command") or "")
            if raw or cmd:
                et = (
                    "direct-measurement"
                    if p.get("exit_code") == 0
                    else "single-inference"
                )
                add(cmd, raw[:500], et)

    # CLAIM-REGISTRY and similar: evidence is a string, probes are prose fields.
    ev = obj.get("evidence")
    if isinstance(ev, str) and ev.strip():
        for m in _PATHISH.findall(ev):
            add(m.rstrip(".,;"), ev[:240], None)
        if not _PATHISH.search(ev):
            add("", ev[:240], None)
    elif isinstance(ev, list):
        for item in ev:
            if isinstance(item, str) and item.strip():
                add(item, "", None)
            elif isinstance(item, dict):
                add(
                    str(item.get("path") or item.get("anchor") or item.get("file") or ""),
                    str(item.get("snippet") or item.get("quote") or item.get("claim") or ""),
                    item.get("evidence_type") or item.get("type"),
                )

    src = str(obj.get("source_probe") or "").strip()
    ver = str(obj.get("verifier_probe") or "").strip()
    src_ok = bool(src) and "not yet run" not in src.lower()
    ver_ok = bool(ver) and "not yet run" not in ver.lower()
    if src_ok and ver_ok:
        add("source_probe+verifier_probe", f"{src[:200]} | {ver[:200]}", "direct-measurement")
    elif src_ok:
        add("source_probe", src[:400], "single-inference")
    elif ver_ok:
        add("verifier_probe", ver[:400], "single-inference")
    return out


def _has_anchor(anchors: list[dict]) -> bool:
    return any((a.get("path") or a.get("snippet")) for a in anchors)


def _path_exists(repo: Path, path: str) -> bool | None:
    rel = path.replace("\\", "/").split(":")[0].strip()
    if not rel:
        return None
    # Probe-field labels are not filesystem paths.
    if rel in {"source_probe", "verifier_probe", "source_probe+verifier_probe"}:
        return None
    if "/" not in rel and "." not in rel:
        return None
    cand = repo / rel
    return cand.is_file()


def anchors_support_band(
    band: str, anchors: list[dict], repo: Path | None = None
) -> tuple[bool, str]:
    need = BAND_RANK.get(band)
    if need is None:
        return False, "unknown-band"
    if not _has_anchor(anchors):
        return False, "no-anchor"
    best = -1
    reasons: list[str] = []
    root = repo or Path()
    for a in anchors:
        et = evidence_type_of(a)
        ceil = ceiling_rank(et)
        path = str(a.get("path") or "")
        exists = _path_exists(root, path) if path else None
        if exists is False:
            ceil = -1
            reasons.append(f"unresolved:{path}")
        snippet = str(a.get("snippet") or "").lower()
        if any(
            w in snippet
            for w in ("unverified", "n=1", "n = 1", "maybe", "todo", "unknown")
        ):
            ceil = min(ceil, -1)
            reasons.append("weak-snippet")
        best = max(best, ceil)
        reasons.append(f"{et}:{ceil}")
    if best >= need:
        return True, f"ceiling={best} need={need}"
    return False, f"ceiling={best} need={need} {' '.join(reasons[:4])}"


def classify_claim(claim: dict, repo: Path | None = None) -> dict:
    text = str(claim.get("text") or "")
    band = normalize_band(claim.get("confidence"))
    band_source = "field" if band else None
    if band is None:
        band = find_band_in_text(text)
        if band:
            band_source = "text"
    hedges = find_hedges(text)
    hedges.extend(residue_tokens(text))
    # If the only "likely" is inside "likely fine", do not keep a band from that collocation.
    if band == "likely" and "likely fine" in hedges and band_source == "text":
        body_wo = text.lower().replace("likely fine", " ")
        if find_band_in_text(body_wo) != "likely" and not normalize_band(
            claim.get("confidence")
        ):
            band = None
            band_source = None
    anchors = list(claim.get("anchors") or [])
    has = _has_anchor(anchors)
    flags: list[str] = []
    support_reason = ""
    if band and not has:
        flags.append(FLAG_NO_ANCHOR)
    if band and has:
        ok, support_reason = anchors_support_band(band, anchors, repo)
        if not ok:
            flags.append(FLAG_UNSUPPORTED)
    return {
        "id": str(claim.get("id") or ""),
        "text": text,
        "band": band,
        "band_source": band_source,
        "unknown_hedges": sorted(set(hedges)),
        "anchor_count": len(anchors) if has else 0,
        "anchors": anchors,
        "flags": flags,
        "support_reason": support_reason,
        "source": str(claim.get("source") or ""),
        "stratum": str(claim.get("stratum") or ""),
    }


def looks_like_claim(obj: dict) -> bool:
    text = _first_str(obj, TEXT_KEYS)
    if not text:
        return False
    if any(obj.get(k) not in (None, "") for k in BAND_KEYS):
        return True
    if find_band_in_text(text) or find_hedges(text) or residue_tokens(text):
        return True
    return False


def normalize_obj(obj: dict, source: str, fallback_id: str) -> dict:
    cid = _first_str(obj, ID_KEYS) or fallback_id
    text = _first_str(obj, TEXT_KEYS)
    conf = None
    for k in BAND_KEYS:
        if obj.get(k) not in (None, ""):
            conf = obj.get(k)
            break
    return {
        "id": cid,
        "text": text,
        "confidence": conf,
        "anchors": _anchor_entries(obj),
        "source": source,
        "stratum": "live" if source.startswith("live:") else "fixture",
    }


def extract_from_obj(
    obj: Any, source: str, acc: list[dict], trail: str = "root", seen: set[int] | None = None
) -> None:
    if seen is None:
        seen = set()
    oid = id(obj)
    if oid in seen:
        return
    seen.add(oid)
    if isinstance(obj, dict):
        extracted = False
        if looks_like_claim(obj):
            acc.append(normalize_obj(obj, source, f"{source}:{trail}"))
            extracted = True
        keys = (
            ("claims", "evidence", "findings", "adjudications", "candidates", "syntheses")
            if extracted
            else obj.keys()
        )
        for k in keys:
            if k not in obj:
                continue
            if k in SKIP_KEYS:
                continue
            extract_from_obj(obj[k], source, acc, f"{trail}/{k}", seen)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            extract_from_obj(item, source, acc, f"{trail}[{i}]", seen)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_from_file(path: Path, source: str) -> list[dict]:
    acc: list[dict] = []
    try:
        doc = load_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return acc
    extract_from_obj(doc, source, acc)
    return acc


def classify_all(claims: list[dict], repo: Path | None = None) -> list[dict]:
    return [classify_claim(c, repo) for c in claims]


def stratified_sample(rows: list[dict], min_n: int = 30) -> list[dict]:
    anchored = [r for r in rows if r.get("anchor_count", 0) > 0 and r.get("band")]
    by_band: dict[str, list[dict]] = {b: [] for b in DECLARED_BANDS}
    by_band["other"] = []
    for r in anchored:
        band = r.get("band") or "other"
        by_band.setdefault(band, []).append(r)
    sample: list[dict] = []
    seen: set[str] = set()
    progressed = True
    while len(sample) < min_n and progressed:
        progressed = False
        for band in list(DECLARED_BANDS) + ["other"]:
            bucket = by_band.get(band) or []
            while bucket:
                row = bucket.pop(0)
                rid = str(row.get("id"))
                if rid in seen:
                    continue
                seen.add(rid)
                sample.append(row)
                progressed = True
                break
            if len(sample) >= min_n:
                break
    if len(sample) < min_n:
        for r in anchored:
            rid = str(r.get("id"))
            if rid in seen:
                continue
            seen.add(rid)
            sample.append(r)
            if len(sample) >= min_n:
                break
    return sample


def summarize(rows: list[dict], sample: list[dict]) -> dict:
    banded = [r for r in rows if r.get("band")]
    no_anchor = [r for r in banded if FLAG_NO_ANCHOR in (r.get("flags") or [])]
    unsupported = [
        r for r in sample if FLAG_UNSUPPORTED in (r.get("flags") or [])
    ]
    hedges = []
    for r in rows:
        for p in r.get("unknown_hedges") or []:
            hedges.append({"claim_id": r.get("id"), "phrase": p})
    return {
        "banded_n": len(banded),
        "no_anchor": no_anchor,
        "unsupported_in_sample": unsupported,
        "sample": sample,
        "hedges": hedges,
        "rows": rows,
    }


NAMED_INPUTS = {
    "adjudications": Path("command-center/synthesis/SYN-0011.adjudications.json"),
    "candidate_syntheses": Path("command-center/synthesis/SYN-0008.candidate-syntheses.json"),
    "claim_registry": Path("command-center/CLAIM-REGISTRY.json"),
    "agents_md": Path("AGENTS.md"),
}

# Catalog names AGENTS.md §7; on this tree that Sherman-Kent text lives here.
SHERMAN_KENT_AGENTS = Path("agent-self/config/AGENTS.md")


def named_input_status(repo: Path) -> dict:
    out: dict[str, dict] = {}
    for key, rel in NAMED_INPUTS.items():
        path = repo / rel
        present = path.is_file() and path.stat().st_size > 0
        out[key] = {
            "path": rel.as_posix(),
            "present": present,
            "bytes": path.stat().st_size if path.is_file() else 0,
        }
    sk = repo / SHERMAN_KENT_AGENTS
    out["sherman_kent_agents"] = {
        "path": SHERMAN_KENT_AGENTS.as_posix(),
        "present": sk.is_file() and sk.stat().st_size > 0,
        "bytes": sk.stat().st_size if sk.is_file() else 0,
        "note": "Catalog input 'AGENTS.md section 7' is this file, not repo-root AGENTS.md.",
    }
    return out


def live_claims(repo: Path) -> list[dict]:
    files: list[Path] = []
    for root_rel in (
        "command-center/receipts",
        "command-center/phase3",
        "command-center/synthesis",
    ):
        root = repo / root_rel
        if root.is_dir():
            files.extend(root.rglob("*.json"))
    extra = repo / "command-center/CLAIM-REGISTRY.json"
    if extra.is_file():
        files.append(extra)
    acc: list[dict] = []
    for path in files:
        posix = path.as_posix()
        if path.name == "SYN-0014.json":
            continue
        if "/probes/SYN-0014/" in posix:
            continue
        try:
            rel = path.relative_to(repo).as_posix()
        except ValueError:
            rel = posix
        acc.extend(extract_from_file(path, f"live:{rel}"))
    return acc
