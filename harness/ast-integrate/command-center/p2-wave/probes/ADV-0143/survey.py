"""Live corpus extents: file bytes per class plus identifier-byte personal data."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from extent import count_marker_bytes, extract_marked_bytes
from plant_payload import PLANT_REL
from sample import iter_text_files
from taxonomy import PERSONAL_MARKERS, classify_chunk, classify_path


def survey(repo: Path) -> dict:
    class_bytes: dict[str, int] = defaultdict(int)
    class_files: dict[str, int] = defaultdict(int)
    exemplars: dict[str, dict] = {}
    personal = {"bytes": 0, "counts": {m: 0 for m in PERSONAL_MARKERS}}
    total_utf8 = 0
    file_count = 0
    for path in iter_text_files(repo):
        rel = path.resolve().relative_to(repo.resolve()).as_posix()
        try:
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            class_bytes["undecodable-or-binary"] += path.stat().st_size
            class_files["undecodable-or-binary"] += 1
            continue
        file_count += 1
        total_utf8 += len(raw)
        if rel.replace("\\", "/") == PLANT_REL:
            marked = extract_marked_bytes(text)
            class_bytes["third-party-license-notice"] += len(marked)
            class_files["third-party-license-notice"] += 1
            if "third-party-license-notice" not in exemplars:
                exemplars["third-party-license-notice"] = {
                    "path": rel,
                    "line": 4,
                    "snippet": marked.decode("utf-8")[:160],
                }
            continue
        pd = count_marker_bytes(text, PERSONAL_MARKERS)
        personal["bytes"] += pd["bytes"]
        for m, n in pd["counts"].items():
            personal["counts"][m] += n
        cid = classify_path(rel) or classify_chunk(rel, text[:2000])
        if cid is None:
            cid = "first-party-program-records"
        # Personal-data extent is identifier bytes, not whole-file.
        if cid == "third-party-personal-data":
            class_bytes[cid] += pd["bytes"]
        else:
            class_bytes[cid] += len(raw)
        class_files[cid] += 1
        if cid not in exemplars:
            line = 1
            for i, ln in enumerate(text.splitlines(), 1):
                if ln.strip():
                    line = i
                    break
            snippet = (text.splitlines() or [""])[line - 1].strip()[:160]
            exemplars[cid] = {
                "path": rel,
                "line": line,
                "snippet": snippet,
            }
    shares = {}
    denom = total_utf8 if total_utf8 else 1
    for cid, b in class_bytes.items():
        shares[cid] = b / denom
    # Overlay measured personal-data identifier bytes as the class extent
    class_bytes["third-party-personal-data"] = personal["bytes"]
    shares["third-party-personal-data"] = personal["bytes"] / denom
    return {
        "file_count": file_count,
        "total_utf8_bytes": total_utf8,
        "class_bytes": dict(class_bytes),
        "class_files": dict(class_files),
        "byte_share": shares,
        "personal_data_identifiers": personal,
        "exemplars": exemplars,
    }
