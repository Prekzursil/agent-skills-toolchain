#!/usr/bin/env python3
"""STEP 1b: normalize the output_schema strings and re-count.

The raw distinct count (367) mixes three encodings:
  - bare path                 command-center/schema/x.schema.json
  - path + JSON pointer       command-center/schema/receipt.schema.json#/$defs/security_report
  - path + prose annotation   command-center/schema/receipt.schema.json profile=... (required: ...)
  - an absolute URL           https://json-schema.org/draft/2020-12/schema
Normalizing to the FILE part is what makes the 'how many files must exist' question
answerable. The brief said 269 distinct paths / 1,896 refs -- test that.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict

REPO = "C:/Users/Prekzursil/source/ast-integrate"
CATALOG = os.path.join(REPO, "command-center", "WORK-UNIT-CATALOG.json")


def normalize(v: str):
    """-> (file_part, fragment, annotation, kind)"""
    s = v.strip()
    if s.startswith("http://") or s.startswith("https://"):
        return (None, None, None, "url")
    annotation = None
    # prose annotation begins at the first space
    if " " in s:
        s, annotation = s.split(" ", 1)
    frag = None
    if "#" in s:
        s, frag = s.split("#", 1)
    return (s.replace("\\", "/"), frag, annotation, "path")


def main():
    with open(CATALOG, "r", encoding="utf-8") as fh:
        d = json.load(fh)
    wus = d["work_units"]

    raw = [wu["output_schema"] for wu in wus]
    files = Counter()
    frags = defaultdict(set)
    kinds = Counter()
    annotated = 0
    fragmented = 0
    for v in raw:
        f, frag, ann, kind = normalize(v)
        kinds[kind] += 1
        if kind == "url":
            continue
        files[f] += 1
        if frag:
            fragmented += 1
            frags[f].add(frag)
        if ann:
            annotated += 1

    out = {
        "raw_reference_total": len(raw),
        "raw_distinct": len(set(raw)),
        "kind_profile": dict(kinds),
        "normalized_distinct_FILES": len(files),
        "normalized_file_reference_total": sum(files.values()),
        "references_carrying_json_pointer": fragmented,
        "references_carrying_prose_annotation": annotated,
        "brief_claimed_distinct_269": len(files) == 269,
        "brief_claimed_refs_1896": sum(files.values()) == 1896,
    }

    # bucket by directory
    bydir = Counter(os.path.dirname(f) for f in files)
    out["distinct_files_by_directory"] = dict(bydir.most_common())
    out["reference_count_by_directory"] = dict(
        Counter({k: 0 for k in bydir}).most_common()
    )
    refs_by_dir = Counter()
    for f, n in files.items():
        refs_by_dir[os.path.dirname(f)] += n
    out["reference_count_by_directory"] = dict(refs_by_dir.most_common())

    out["all_distinct_files_sorted"] = sorted(files)
    out["fragments_per_file"] = {k: sorted(v) for k, v in sorted(frags.items())}
    out["file_reference_counts"] = dict(files.most_common())

    with open(os.path.join(REPO, "command-center", "_sub1_normalize_probe_out.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    slim = {k: v for k, v in out.items() if k not in ("all_distinct_files_sorted", "fragments_per_file", "file_reference_counts")}
    print(json.dumps(slim, indent=2))
    print("\n--- all distinct fragments (JSON-pointer subschemas demanded) ---")
    allfrags = sorted({fr for v in frags.values() for fr in v})
    print(json.dumps(allfrags, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
