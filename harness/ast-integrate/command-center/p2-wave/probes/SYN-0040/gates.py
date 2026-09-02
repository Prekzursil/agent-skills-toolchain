"""Phase-14 synthesis-gate predicates used by SYN-0040 both-states control.

Each gate exits 0 on a clean fixture and non-zero when the defect it
guards is present. These are fixture-local implementations of the
predicates specified by SYN-0002, SYN-0013, SYN-0016..SYN-0021, SYN-0030;
producing-unit receipts are not on this worktree.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

from constants import CALIBRATION_ID

Json = dict[str, Any]
STOP = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "do",
    "for",
    "from",
    "have",
    "in",
    "into",
    "is",
    "no",
    "not",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}


def stem(word: str) -> str:
    if len(word) > 4 and word.endswith("s"):
        return word[:-1]
    return word


def tokens(text: str) -> set[str]:
    raw = re.findall(r"[a-z0-9]+", (text or "").lower().replace("_", " "))
    return {stem(w) for w in raw if w not in STOP and len(w) > 1}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def has_cycle(nodes: list[Json], edges: list[Json]) -> bool:
    graph: dict[str, list[str]] = {str(n["id"]): [] for n in nodes}
    for edge in edges:
        src, dst = str(edge.get("src") or ""), str(edge.get("dst") or "")
        graph.setdefault(src, []).append(dst)
    color = {nid: 0 for nid in graph}

    def dfs(uid: str) -> bool:
        color[uid] = 1
        for vid in graph.get(uid, []):
            if vid not in color:
                continue
            if color[vid] == 1:
                return True
            if color[vid] == 0 and dfs(vid):
                return True
        color[uid] = 2
        return False

    return any(dfs(nid) for nid in graph if color[nid] == 0)


def gate_syn_0002(doc: Json) -> tuple[int, list[str]]:
    nodes = {str(n["id"]): n for n in doc.get("nodes") or []}
    issues: list[str] = []
    for claim in doc.get("claims") or []:
        attached = claim.get("attached_to")
        if not attached or str(attached) not in nodes:
            issues.append(f"orphan-claim:{claim.get('id')}")
    for node in doc.get("nodes") or []:
        if node.get("kind") == "CAUSE":
            if not node.get("children") and not node.get("evidence"):
                issues.append(f"empty-cause:{node.get('id')}")
    for edge in doc.get("edges") or []:
        src, dst = str(edge.get("src") or ""), str(edge.get("dst") or "")
        if src not in nodes or dst not in nodes:
            issues.append(f"dangling-edge:{src}->{dst}")
    if has_cycle(list(doc.get("nodes") or []), list(doc.get("edges") or [])):
        issues.append("cycle")
    return (1 if issues else 0), issues


def gate_syn_0013(doc: Json) -> tuple[int, list[str]]:
    issues: list[str] = []
    evidence = [str(x) for x in (doc.get("EVIDENCE") or [])]
    quoted = {str(x) for x in (doc.get("quoted") or [])}
    uses = [item for item in evidence if item not in quoted]
    if not (3 <= len(uses) <= 5):
        issues.append(f"evidence-block-size:{len(uses)}")
    if any(item in quoted for item in evidence):
        issues.append("quoted-token-counted-as-use")
    retention = doc.get("retention_by_class")
    needed = {"UNVERIFIED", "file:line", "URL"}
    if not isinstance(retention, dict) or not needed.issubset(set(retention)):
        issues.append("retention-not-per-class")
    return (1 if issues else 0), issues


def gate_syn_0016(doc: Json) -> tuple[int, list[str]]:
    issues: list[str] = []
    syn_tok = tokens(str(doc.get("synthesis_text") or ""))
    disposals = doc.get("disposals") or {}
    for dissent in doc.get("dissents") or []:
        did = str(dissent.get("id") or "")
        content = tokens(str(dissent.get("text") or ""))
        overlap = (len(content & syn_tok) / max(len(content), 1)) if content else 0.0
        matched = bool(content) and overlap >= 0.6
        reason = str(disposals.get(did) or "").strip()
        if not matched and not reason:
            issues.append(f"unmatched-dissent:{did}")
    return (1 if issues else 0), issues


def _digitless(text: str) -> set[str]:
    return tokens(re.sub(r"\d+", " ", text or ""))


def gate_syn_0017(doc: Json) -> tuple[int, list[str]]:
    issues: list[str] = []
    findings = list(doc.get("findings") or [])
    collapsed = {str(f.get("id")) for f in findings if f.get("collapsed_into")}
    for i, left in enumerate(findings):
        sa = tokens(str(left.get("text") or ""))
        da = _digitless(str(left.get("text") or ""))
        for right in findings[i + 1 :]:
            sb = tokens(str(right.get("text") or ""))
            db = _digitless(str(right.get("text") or ""))
            rename = sa == sb
            paraphrase = jaccard(sa, sb) >= 0.75
            param_fork = da == db and sa != sb
            duplicate = rename or paraphrase or param_fork
            lid, rid = str(left.get("id")), str(right.get("id"))
            either_collapsed = lid in collapsed or rid in collapsed
            if duplicate and not either_collapsed:
                issues.append(f"uncollapsed-duplicate:{lid}:{rid}")
            if not duplicate and (
                left.get("collapsed_into") == rid or right.get("collapsed_into") == lid
            ):
                issues.append(f"over-collapse:{lid}:{rid}")
    return (1 if issues else 0), issues


def _classify_anchor(anchor: Json) -> str:
    if anchor.get("file_gone"):
        return "FILE-GONE"
    if str(anchor.get("capture_text")) != str(anchor.get("report_text")):
        return "CONTENT-CHANGED"
    if anchor.get("capture_line") != anchor.get("report_line"):
        return "LINE-MOVED"
    return "STABLE"


def gate_syn_0018(doc: Json) -> tuple[int, list[str]]:
    issues: list[str] = []
    if str(doc.get("recipe") or "") == "git-archive":
        issues.append("wrong-blob-recipe-git-archive")
    for anchor in doc.get("anchors") or []:
        klass = _classify_anchor(anchor)
        if klass != "STABLE":
            issues.append(f"{klass}:{anchor.get('id')}")
    return (1 if issues else 0), issues


def gate_syn_0019(doc: Json) -> tuple[int, list[str]]:
    issues: list[str] = []
    now = int(doc.get("now") or 0)
    verified = int(doc.get("verified_at") or 0)
    window = int(doc.get("window_seconds") or 0)
    if now - verified > window:
        issues.append("stale-verification")
    files = doc.get("files") or {}
    for entry in doc.get("manifest") or []:
        path = str(entry.get("path") or "")
        blob = files.get(path)
        if blob is None:
            issues.append(f"missing:{path}")
            continue
        if int(blob.get("bytes") or 0) <= 0 or not str(blob.get("content") or ""):
            issues.append(f"empty:{path}")
        if str(blob.get("hash") or "") != str(entry.get("hash") or ""):
            issues.append(f"hash-mismatch:{path}")
    return (1 if issues else 0), issues


def gate_syn_0020(doc: Json) -> tuple[int, list[str]]:
    issues: list[str] = []
    archive_seen = False
    for stmt in doc.get("statements") or []:
        text = str(stmt.get("text") or "").lower()
        verdict = str(stmt.get("verdict") or "")
        test_id = stmt.get("test_id")
        if "git archive" in text or "git-archive" in text:
            archive_seen = True
            if verdict != "CONTRADICT":
                issues.append("archive-recipe-not-CONTRADICT")
        if verdict == "AGREE" and not test_id:
            issues.append(f"untested-counted-AGREE:{stmt.get('id')}")
    if not archive_seen:
        issues.append("archive-line-not-extracted")
    for cmd in doc.get("commands") or []:
        if cmd.get("noexec") and cmd.get("executed"):
            issues.append(f"noexec-executed:{cmd.get('id')}")
    return (1 if issues else 0), issues


_COMPLETION = re.compile(
    r"\b(done|complete|shipped|closed|verified|success)\b", re.I
)


def gate_syn_0021(doc: Json) -> tuple[int, list[str]]:
    issues: list[str] = []
    if str(doc.get("predicate_source") or "") != "shared-reducer":
        issues.append("local-predicate-reimplementation")
    for claim in doc.get("claims") or []:
        if str(claim.get("kind") or "") == "requirement":
            continue
        text = str(claim.get("text") or "")
        if not _COMPLETION.search(text) and str(claim.get("label") or "") != "SUCCESS":
            continue
        missing = bool(claim.get("artifact_missing"))
        predicate = bool(claim.get("predicate_true"))
        backed = predicate and not missing
        if claim.get("counted_backed") and not backed:
            issues.append(f"unbacked-counted-backed:{claim.get('id')}")
        if missing or not predicate:
            issues.append(f"unbacked-completion:{claim.get('id')}")
    return (1 if issues else 0), issues


def gate_syn_0030(doc: Json) -> tuple[int, list[str]]:
    issues: list[str] = []
    if str(doc.get("join_key") or "") != "id":
        issues.append("join-by-title")
        return 1, issues
    units = {str(x) for x in (doc.get("units") or [])}
    artifacts = {str(x) for x in (doc.get("artifacts") or [])}
    tests = {str(x) for x in (doc.get("tests") or [])}
    claims = {str(x) for x in (doc.get("claims") or [])}
    u2a = {str(k): str(v) for k, v in (doc.get("unit_to_artifact") or {}).items()}
    a2u = {str(k): str(v) for k, v in (doc.get("artifact_to_unit") or {}).items()}
    t2c = {str(k): str(v) for k, v in (doc.get("test_to_claim") or {}).items()}
    c2t = {str(k): str(v) for k, v in (doc.get("claim_to_test") or {}).items()}
    u2c = {str(k): str(v) for k, v in (doc.get("unit_to_claim") or {}).items()}
    c2u = {str(k): str(v) for k, v in (doc.get("claim_to_unit") or {}).items()}
    a2t = {str(k): str(v) for k, v in (doc.get("artifact_to_test") or {}).items()}
    t2a = {str(k): str(v) for k, v in (doc.get("test_to_artifact") or {}).items()}
    for uid in units:
        if u2a.get(uid) not in artifacts:
            issues.append(f"unit-without-artifact:{uid}")
        if u2c.get(uid) not in claims:
            issues.append(f"unit-without-claim:{uid}")
    for aid in artifacts:
        if a2u.get(aid) not in units:
            issues.append(f"artifact-without-unit:{aid}")
        if a2t.get(aid) not in tests:
            issues.append(f"artifact-without-test:{aid}")
    for tid in tests:
        if t2c.get(tid) not in claims:
            issues.append(f"test-without-claim:{tid}")
        if t2a.get(tid) not in artifacts:
            issues.append(f"test-without-artifact:{tid}")
    for cid in claims:
        if c2t.get(cid) not in tests:
            issues.append(f"claim-without-test:{cid}")
        if c2u.get(cid) not in units:
            issues.append(f"claim-without-unit:{cid}")
    return (1 if issues else 0), issues


def gate_inert(_doc: Json) -> tuple[int, list[str]]:
    return 0, []


RUNNERS: dict[str, Callable[[Json], tuple[int, list[str]]]] = {
    "SYN-0002": gate_syn_0002,
    "SYN-0013": gate_syn_0013,
    "SYN-0016": gate_syn_0016,
    "SYN-0017": gate_syn_0017,
    "SYN-0018": gate_syn_0018,
    "SYN-0019": gate_syn_0019,
    "SYN-0020": gate_syn_0020,
    "SYN-0021": gate_syn_0021,
    "SYN-0030": gate_syn_0030,
    CALIBRATION_ID: gate_inert,
}


def evaluate(gate_id: str, doc: Json) -> tuple[int, list[str]]:
    runner = RUNNERS.get(gate_id)
    if runner is None:
        return 2, [f"unknown-gate:{gate_id}"]
    return runner(doc)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: gates.py <GATE-ID> <fixture.json>", file=sys.stderr)
        return 2
    gate_id, raw_path = args
    path = Path(raw_path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    code, issues = evaluate(gate_id, doc)
    print(json.dumps({"gate": gate_id, "exit_code": code, "issues": issues}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
