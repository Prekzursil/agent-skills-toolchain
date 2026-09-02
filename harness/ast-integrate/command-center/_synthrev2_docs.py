"""Synthesis-review pass 2: settle the DOCS-lane 'died' verdict and the owner-decision count."""

import io
import json
import re
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
out = {}


def run(args):
    p = subprocess.run(
        args, cwd=str(REPO), capture_output=True, text=True, errors="replace"
    )
    return p.returncode, p.stdout, p.stderr


now = time.time()

# --- DOCS lane: per-file tracked-ness, mtime age, last commit age -----------------
rows = []
for f in sorted((REPO / "docs").glob("_LANE-DOCS*.md")):
    rel = "docs/" + f.name
    rc_t, _, _ = run(["git", "ls-files", "--error-unmatch", rel])
    rc_c, so_c, _ = run(["git", "log", "-1", "--pretty=%ct%x09%h%x09%s", "--", rel])
    ct = None
    subj = None
    sha = None
    if so_c.strip():
        parts = so_c.strip().split("\t")
        ct = int(parts[0])
        sha = parts[1]
        subj = parts[2] if len(parts) > 2 else ""
    rows.append(
        {
            "file": rel,
            "tracked": rc_t == 0,
            "mtime_hours_ago": round((now - f.stat().st_mtime) / 3600, 1),
            "last_commit_hours_ago": round((now - ct) / 3600, 1) if ct else None,
            "last_commit": sha,
            "last_commit_subject": (subj or "")[:70],
        }
    )
out["lane_docs_files"] = rows
out["lane_docs_untracked_count"] = sum(1 for r in rows if not r["tracked"])

# DOCS commit activity excluding the synthesis lane's own rescue commit
rc, so, _ = run(
    [
        "git",
        "log",
        "--since=36 hours ago",
        "--pretty=%ct%x09%h%x09%s",
        "--",
        "docs/_LANE-DOCS*",
    ]
)
entries = []
for ln in so.split("\n"):
    if not ln.strip():
        continue
    ct, sha, subj = ln.split("\t", 2)
    entries.append(
        {
            "hours_ago": round((now - int(ct)) / 3600, 1),
            "sha": sha,
            "subject": subj[:80],
        }
    )
out["lane_docs_commits_36h"] = {
    "n": len(entries),
    "newest_any": entries[0] if entries else None,
    "newest_excluding_synthesis": next(
        (e for e in entries if "synthesis" not in e["subject"].lower()), None
    ),
}

# subject-tagged DOCS commits (independent of path)
rc, so, _ = run(["git", "log", "--since=36 hours ago", "--pretty=%ct%x09%s"])
subj_hits = []
for ln in so.split("\n"):
    if not ln.strip():
        continue
    ct, s = ln.split("\t", 1)
    if re.search(r"\b(lane-docs|docs-lane)\b", s, re.I):
        subj_hits.append(
            {"hours_ago": round((now - int(ct)) / 3600, 1), "subject": s[:80]}
        )
out["docs_lane_subject_commits_36h"] = {
    "n": len(subj_hits),
    "newest": subj_hits[0] if subj_hits else None,
}

# --- owner decisions: per-row status ---------------------------------------------
od = (REPO / "command-center/OWNER-DECISIONS.md").read_text(
    encoding="utf-8", errors="replace"
)
statuses = re.findall(
    r"^\|\s*(?:\*\*)?((?:OQ-)?Q?\d+|OQ-\d+)(?:\*\*)?\s*\|.*?\|\s*(?:\*\*)?(OPEN|ANSWERED|CLOSED|RESOLVED)",
    od,
    flags=re.M | re.I,
)
cnt = {}
for _, s in statuses:
    cnt[s.upper()] = cnt.get(s.upper(), 0) + 1
out["owner_decisions"] = {
    "rows_parsed": len(statuses),
    "by_status": cnt,
    "raw_OPEN_token_count": len(re.findall(r"\bOPEN\b", od)),
}

# --- does the synthesis carry the credential-transcript owner item? ---------------
cc = (REPO / "command-center/GRIND-STATUS.md").read_text(
    encoding="utf-8", errors="replace"
)
dg = (REPO / "docs/GRIND-STATUS.md").read_text(encoding="utf-8", errors="replace")
out["credential_transcript_item"] = {
    "sha_in_synthesis": "839ca3224e60" in cc,
    "sha_in_docs_status": "839ca3224e60" in dg,
}


# --- cross-document B-id collision ------------------------------------------------
def bmap(text):
    d = {}
    for m in re.finditer(
        r"^\|?\s*(?:\*\*)?(B\d)(?:\*\*)?\s*\|?\s*\|?\s*(?:\*\*)?([^|\n]{0,80})",
        text,
        flags=re.M,
    ):
        d.setdefault(m.group(1), m.group(2).strip()[:60])
    return d


out["b_ids"] = {"synthesis": bmap(cc), "docs_status": bmap(dg)}

# --- citation gate case count -----------------------------------------------------
try:
    g = json.load(
        io.open(REPO / "command-center/_synthrev2_gates.out.json", encoding="utf-8-sig")
    )
    out["citation_gate_tail"] = next(
        (r["tail"] for r in g["results"] if r["gate"] == "test_citation_gate DIRECT"),
        None,
    )
    out["ssot_wiring_tail"] = next(
        (r["tail"] for r in g["results"] if r["gate"] == "ssot_wiring_check"), None
    )
except Exception as e:  # noqa: BLE001
    out["citation_gate_tail"] = f"error: {e}"

print(json.dumps(out, indent=2, ensure_ascii=False))
