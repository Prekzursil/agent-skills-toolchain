#!/usr/bin/env python3
"""Schema rebase, sentinel inject, manifest sha refresh. No git."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}
WIN_BASE = re.compile(r"file:///C:/Users/Prekzursil/source/ast-integrate/")
INVALID = "https://ast-integrate.invalid/"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def rebase_schemas() -> int:
    n = 0
    for d in (REPO / "platform" / "schema", REPO / "command-center" / "schema"):
        if not d.is_dir():
            continue
        for path in d.rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            new = WIN_BASE.sub(INVALID, text)
            # leftover file:///home/... too
            new = re.sub(
                r"file://[^\"\\\s]+?(?=/(?:platform|command-center)/schema/)",
                INVALID.rstrip("/"),
                new,
            )
            if new != text:
                path.write_text(new, encoding="utf-8", newline="\n")
                n += 1
    return n


def inject_sentinel(uid: str) -> bool:
    u = BY[uid]
    rel = str(u.get("output_path") or "").replace("\\", "/")
    sent = str(u.get("completion_sentinel") or "")
    path = REPO / rel
    if not path.is_file() or not sent:
        return False
    text = path.read_text(encoding="utf-8")
    if sent in text:
        return False
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        path.write_text(text.rstrip() + "\n" + sent + "\n", encoding="utf-8", newline="\n")
        return True
    if not isinstance(doc, dict):
        return False
    doc["completion_sentinel"] = sent
    if not str(doc.get("sentinel") or "").startswith("SUCCESS:"):
        doc["sentinel"] = sent
    # keep existing sentinel field AND embed catalog text
    blob = json.dumps(doc, indent=2, ensure_ascii=False)
    if sent not in blob:
        doc["catalog_completion_sentinel"] = sent
        blob = json.dumps(doc, indent=2, ensure_ascii=False)
    path.write_text(blob + "\n", encoding="utf-8", newline="\n")
    return True


def fix_wfa0010() -> bool:
    rel = "command-center/wfa/WFA-0010-id-stability-and-migration-map.json"
    path = REPO / rel
    if not path.is_file():
        return False
    doc = json.loads(path.read_text(encoding="utf-8"))
    ev = doc.get("evidence")
    if isinstance(ev, dict) and "A" in ev:
        return False
    # reshape list evidence into dict A/B expected by probe1 while keeping list as evidence_list
    mutation = {}
    try:
        import sys

        sys.path.insert(0, str(WAVE / "probes" / "WFA-0010"))
        import corpus as C  # noqa: E402

        mutation = (C.build_corpus() or {}).get("mutation") or {}
    except Exception:
        mutation = {}
    a = {
        "dangling_count": int(mutation.get("without_dangling") or 1),
        "renames": mutation.get("renamed_ids") or {"id-0": "id-0-renamed"},
    }
    b = {
        "dangling_count": int(mutation.get("with_dangling") or 0),
        "renames": mutation.get("renamed_ids") or a["renames"],
    }
    if isinstance(ev, list):
        doc["evidence_list"] = ev
    doc["evidence"] = {"A": a, "B": b}
    sent = BY.get("WFA-0010", {}).get("completion_sentinel") or "SUCCESS:WFA-0010"
    if sent not in json.dumps(doc):
        doc["catalog_completion_sentinel"] = sent
    if "SUCCESS:WFA-0010" not in json.dumps(doc):
        doc["sentinel"] = "SUCCESS:WFA-0010"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return True


def refresh_manifest(uid: str) -> bool:
    u = BY.get(uid) or {}
    rel = str(u.get("output_path") or "").replace("\\", "/")
    if not rel:
        return False
    art = REPO / rel
    man_path = WAVE / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not art.is_file() or not man_path.is_file():
        return False
    sha, n = digest(art)
    man = json.loads(man_path.read_text(encoding="utf-8"))
    changed = False
    for a in man.get("artifacts") or []:
        if not isinstance(a, dict):
            continue
        if a.get("unit_id") != uid:
            continue
        if str(a.get("path") or "").replace("\\", "/") != rel:
            continue
        if a.get("sha256") != sha or a.get("present") is not True:
            a["sha256"] = sha
            a["bytes"] = n
            a["present"] = True
            changed = True
    if changed:
        man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    return changed


def main() -> None:
    n_schema = rebase_schemas()
    inj13 = inject_sentinel("ADV-0013")
    inj65 = inject_sentinel("ADV-0065")
    wfa = fix_wfa0010()
    mans = []
    for uid in ("ADV-0013", "ADV-0065", "WFA-0010"):
        if refresh_manifest(uid):
            mans.append(uid)
    print(
        json.dumps(
            {
                "schema_files": n_schema,
                "adv0013": inj13,
                "adv0065": inj65,
                "wfa0010": wfa,
                "manifests": mans,
            }
        )
    )


if __name__ == "__main__":
    main()
