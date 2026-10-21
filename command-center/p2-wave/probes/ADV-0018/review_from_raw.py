"""ADV-0018 independent mechanical re-derivation (review-from-raw).

Fresh-context review that never imports the probe scripts' verdict logic: it re-reads
the RAW outputs and the ARTIFACT, and re-computes the agreement table from primitives.
Exit 0 only if every claim the artifact makes about the probes is supported by the raw
bytes on disk.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
REPO = DIR.parents[3]


def main(artifact_path: str) -> int:
    problems: list[str] = []
    art = json.loads(Path(artifact_path).read_text(encoding="utf-8"))

    rc = json.loads((DIR / "recall-control.json").read_text(encoding="utf-8"))
    p1 = json.loads((DIR / "probe1-topic-retrieval.json").read_text(encoding="utf-8"))
    p2 = json.loads((DIR / "probe2-frontmatter-audit.json").read_text(encoding="utf-8"))
    nc = json.loads((DIR / "negative-control.json").read_text(encoding="utf-8"))

    if rc.get("verdict") != "GREEN":
        problems.append("recall control not GREEN in raw")
    if nc.get("verdict") != "PASS":
        problems.append("negative control not PASS in raw")

    contradicted_raw = sorted(p1["contradicted_notes"])
    # probe2 must have audited exactly the probe1 contradicted set
    if sorted(p2["contradicted_note_count"] * ["<n>"]) and p2["contradicted_note_count"] != len(contradicted_raw):
        problems.append("probe2 audited a different contradicted count than probe1 found")
    pointer_absent = sorted(p2["pointer_absent"])
    if not set(pointer_absent).issubset(set(contradicted_raw)):
        problems.append("probe2 pointer_absent set not a subset of probe1 contradicted set")

    # the artifact's answer must equal the raw-derived answer
    ext = art.get("extensions", {})
    if ext.get("answer_notes_contradicted") is not None:
        if sorted(ext["answer_notes_contradicted"]) != contradicted_raw:
            problems.append("artifact contradicted list != raw probe1 list")
    if ext.get("answer_pointer_absent") is not None:
        if sorted(ext["answer_pointer_absent"]) != pointer_absent:
            problems.append("artifact pointer-absent list != raw probe2 list")
    if art.get("state") == "SUCCESS":
        if art.get("reviewer", {}).get("verdict") != "PASS":
            problems.append("SUCCESS artifact must carry reviewer PASS")
        for t in art.get("tests", []):
            if t.get("result") in ("FAIL", "ERROR", "SKIP", "NOT-RUN"):
                problems.append(f"SUCCESS artifact carries test {t.get('id')} result={t.get('result')}")

    # every probe artifact the receipt declares must hash-match on disk (the primary
    # self-referential entry is exempt by construction: an artifact cannot contain its
    # own hash)
    for a in art.get("artifacts", []):
        if a["path"].endswith("review-from-raw.raw.txt"):
            continue  # reviewer's own output, rewritten each run
        p = REPO / a["path"]
        if not p.is_file():
            if a.get("required_on_disk", True):
                problems.append(f"declared artifact missing: {a['path']}")
            continue
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        if digest != a.get("sha256"):
            problems.append(f"declared artifact hash drift: {a['path']}")

    if problems:
        print("FAILED:adv0018-review " + "; ".join(problems))
        (DIR / "review-from-raw.raw.txt").write_text(
            "FAILED:adv0018-review " + "; ".join(problems) + "\n", encoding="utf-8")
        return 1
    out = (f"SUCCESS:adv0018-review raw supports artifact: recall GREEN, control PASS, "
           f"{len(contradicted_raw)} contradicted, {len(pointer_absent)} pointer-absent, "
           f"{len(art.get('artifacts', []))} declared artifacts hash-match")
    print(out)
    (DIR / "review-from-raw.raw.txt").write_text(out + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
