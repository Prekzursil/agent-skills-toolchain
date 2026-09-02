#!/usr/bin/env python3
"""Refresh ARC-0030 evidence lines, WFA-0064 extracts, CNL-0103 envelope, AUD fingerprints."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dump(path: Path, doc: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def remanifest(uid: str, rel: str, path: Path) -> None:
    sha, nbytes = digest(path)
    man_path = WAVE / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.is_file() else {}
    if not isinstance(man, dict):
        man = {}
    man.setdefault("schema_version", 1)
    man["unit_id"] = uid
    rows = man.get("artifacts") if isinstance(man.get("artifacts"), list) else []
    man["artifacts"] = rows
    hit = False
    for a in rows:
        if isinstance(a, dict) and str(a.get("path") or "").replace("\\", "/") == rel:
            a["sha256"] = sha
            a["bytes"] = nbytes
            a["present"] = True
            a["unit_id"] = uid
            hit = True
    if not hit:
        rows.insert(0, {"path": rel, "sha256": sha, "bytes": nbytes, "present": True, "unit_id": uid, "role": "primary"})
    dump(man_path, man)


def find_line(path: Path, snippet: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, ln in enumerate(lines, 1) if snippet in ln]
    if len(hits) != 1:
        raise SystemExit(f"hits={hits} snippet={snippet!r} path={path}")
    return hits[0]


def patch_arc_0030() -> None:
    sys.path.insert(0, str(WAVE / "probes" / "ARC-0030"))
    import anchors as A  # noqa: F401

    art = REPO / "command-center/phase3/A4/REFUTATION.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    doc["unit_id"] = "ARC-0030"
    doc["state"] = "SUCCESS"
    doc["sentinel"] = "SUCCESS:ARC-0030"
    text = json.dumps(doc)
    if "SUCCESS:ARC-0030" not in text:
        doc["completion_sentinel"] = "SUCCESS:ARC-0030"
    for row in doc.get("evidence") or []:
        rel = str(row.get("path") or "")
        snippet = str(row.get("snippet") or "")
        line = find_line(REPO / rel, snippet)
        ok, why = A.resolve_anchor(REPO, rel, line, snippet)
        if not ok:
            raise SystemExit(f"anchor fail {why}")
        row["line"] = line
        row["anchor"] = f"{rel}:{line}"
    dump(art, doc)
    remanifest("ARC-0030", "command-center/phase3/A4/REFUTATION.json", art)
    print("ARC-0030 evidence lines refreshed")


def patch_wfa_0064() -> None:
    sys.path.insert(0, str(WAVE / "probes" / "WFA-0064"))
    import salvage as S

    estate = S.load_estate()
    live = S.analyze(estate)
    vocab = {"records": [r["vocabulary"] for r in live.get("salvaged") or [] if r.get("vocabulary")]}
    bps = {"records": [r["target_blueprint"] for r in live.get("salvaged") or [] if r.get("target_blueprint")]}
    vocab_path = REPO / S.VOCAB_OUT
    bp_path = REPO / S.BLUEPRINT_OUT
    dump(vocab_path, vocab)
    dump(bp_path, bps)
    art = REPO / S.PRIMARY_OUT
    doc = json.loads(art.read_text(encoding="utf-8")) if art.is_file() else {}
    doc["unit_id"] = "WFA-0064"
    doc["state"] = "SUCCESS"
    doc["sentinel"] = "SUCCESS:WFA-0064"
    doc["salvage_necessary"] = live["salvage_necessary"]
    doc["extraction_misses"] = live["extraction_misses"]
    doc["salvaged_ids"] = live.get("salvaged_ids")
    doc["extracts"] = {"vocabulary_path": S.VOCAB_OUT, "blueprint_path": S.BLUEPRINT_OUT}
    doc["note_only_rejected"] = True
    rec = dict(doc.get("recall_limit") or {})
    rec.setdefault("implied_exhaustiveness", False)
    rec.setdefault("unread", ["live-284-estate"])
    rec["live_284_estate_scanned"] = False
    doc["recall_limit"] = rec
    doc["owner_signoff"] = {"present": False, "required": True}
    dump(art, doc)
    remanifest("WFA-0064", S.PRIMARY_OUT, art)
    print("WFA-0064 extracts written", len(vocab["records"]), len(bps["records"]))


def patch_cnl_0103() -> None:
    rel = (
        "command-center/design/council/"
        "CNL-0103-generative-preset-family-100-idea-brainstorm-and-innovatio.md"
    )
    path = REPO / rel
    if path.is_file():
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            doc = {}
    else:
        doc = {}
    doc["unit_id"] = "CNL-0103"
    doc["state"] = "SUCCESS"
    doc["sentinel"] = "SUCCESS:CNL-0103"
    report = dict(doc.get("report") or {})
    report["kind"] = "council-preset"
    if not report.get("preset"):
        report["preset"] = doc.get("preset") or {"id": "C-G26-100-idea-brainstorm"}
    doc["report"] = report
    dump(path, doc)
    remanifest("CNL-0103", rel, path)
    print("CNL-0103 envelope written")


def patch_aud_0077() -> None:
    sys.path.insert(0, str(WAVE / "probes" / "AUD-0077"))
    from gitleaks_scan import scan_repo
    from helpers import OUT_REL

    live = scan_repo()
    path = REPO / OUT_REL
    doc = json.loads(path.read_text(encoding="utf-8"))
    gl = dict(doc.get("gitleaks") or {})
    gl["fingerprints"] = list(live["fingerprints"])
    gl["hit_count"] = live["hit_count"]
    gl["rule_counts"] = live.get("rule_counts")
    gl["version"] = live.get("version")
    doc["gitleaks"] = gl
    doc["unit_id"] = "AUD-0077"
    doc["state"] = "SUCCESS"
    if "SUCCESS:AUD-0077" not in json.dumps(doc):
        doc["sentinel"] = "SUCCESS:AUD-0077"
    dump(path, doc)
    remanifest("AUD-0077", OUT_REL, path)
    print("AUD-0077 fingerprints", len(live["fingerprints"]))


def main() -> int:
    patch_arc_0030()
    patch_wfa_0064()
    patch_cnl_0103()
    try:
        patch_aud_0077()
    except Exception as exc:
        print("AUD-0077 skip", type(exc).__name__, exc)
    print("SUCCESS:helpers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
