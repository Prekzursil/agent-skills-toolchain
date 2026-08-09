"""build/wfa-4 : mechanically verify provenance for canonical slice 97-128.

READ-ONLY. Resolves each candidate across the two live skill vaults and the bare
mirror, and extracts license / maintenance / stage / role / tool / stop-rule /
failure / benchmark anchors WITH file:line, so no field in the final registry is
LLM-asserted where an algorithm could compute it.
"""

import json
import os
import pathlib
import re
import subprocess
import sys

CORPUS = pathlib.Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806")
REG = CORPUS / "08-WORKFLOW-CANDIDATE-REGISTRY.json"
MIRROR = CORPUS / "main-mirror.git"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"
AGENTS_VAULT = pathlib.Path(r"C:/Users/Prekzursil/.agents/skills")
CLAUDE_VAULT = pathlib.Path(r"C:/Users/Prekzursil/.claude/skills")
LO, HI = 97, 128

MIRROR_PREFIXES = ["skills", ".agents/skills", "skills-claude-only"]


def git(*args):
    r = subprocess.run(
        ["git", "--git-dir", str(MIRROR), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def mirror_has(path):
    rc, out, _ = git("ls-tree", "-r", "--name-only", REF, "--", path)
    return rc == 0 and out.strip() != ""


def mirror_read(path):
    rc, out, _ = git("cat-file", "-p", f"{REF}:{path}")
    return out if rc == 0 else None


def mirror_last_commit(path):
    rc, out, _ = git("log", "-1", "--format=%cI|%h", REF, "--", path)
    return out.strip() if rc == 0 and out.strip() else None


# ---------- extraction helpers (all return (value, "file:line") anchors) ----------

LICENSE_PAT = re.compile(
    r"(MIT\b|Apache[- ]2\.0|CC[ -]BY[- ]SA|BSD[- ]\d|GPL|AGPL|MPL[- ]2|"
    r"licen[cs]e\s*[:=]|owner[- ]authored|proprietary|public domain|Unlicense)",
    re.I,
)
STAGE_PAT = re.compile(
    r"^\s{0,4}(?:#{2,4}\s*)?(?:(?:Stage|Step|Phase|Gate|G\d|L\d|Round|Tier|Wave|Pass)\b"
    r"[^\n]{0,90})$",
    re.M,
)
ROLE_PAT = re.compile(
    r"\b(persona|reviewer|critic|judge|referee|architect|adversar\w+|red[- ]team|"
    r"proposer|verifier|orchestrat\w+|worker|lead\b|scout|synthesi[sz]er|"
    r"devil'?s advocate|PM\b|CTO\b|moderator|arbiter|voter)\b",
    re.I,
)
TOOL_PAT = re.compile(
    r"\b(pytest|vitest|jest|playwright|ruff|semgrep|bandit|lizard|trivy|gitleaks|"
    r"hypothesis|crosshair|fast-check|mutmut|cosmic-ray|stryker|ffmpeg|gh\b|git\b|"
    r"codex|Task\(|agent\(|parallel\(|WebSearch|WebFetch|Bash|Grep|Glob|MCP|"
    r"lighthouse|axe|nvda|testmon|longrun)\b"
)
STOP_PAT = re.compile(
    r"[^\n]{0,120}(stop(?:ping)?\s+(?:rule|condition|criteri\w+)|max[_ ]?(?:round|iter|"
    r"attempt|reflection|retr\w+)\w*|until\s+(?:all|every|no\s+new|green|convergen\w+)|"
    r"two[- ]strikes|cap(?:ped)?\s+at|budget|converg\w+|saturat\w+|"
    r"terminal state|escalat\w+ (?:instead|after)|N failures?)[^\n]{0,120}",
    re.I,
)
FAIL_PAT = re.compile(
    r"[^\n]{0,120}(fail[- ]open|fail[- ]closed|never blocks?|does not block|advisory|"
    r"SHADOW mode|degrade\w* gracefully|revert[- ]gate|rollback|blocks? the|"
    r"exit 2|exit code 1|FAILED:|BLOCKED|abort)[^\n]{0,120}",
    re.I,
)
BENCH_PAT = re.compile(
    r"[^\n]{0,140}(arXiv[:\s]*\d{4}\.\d{4,5}|doi\.org/[^\s)]+|\b\d{1,3}(?:\.\d+)?%|"
    r"SWE[- ]bench|HumanEval|JudgeBench|UTBoost|measured\b|benchmark\w*|"
    r"\b\d+/\d+\b)[^\n]{0,140}",
    re.I,
)
ARXIV_PAT = re.compile(r"arXiv[:\s]*(\d{4}\.\d{4,5})", re.I)
URL_PAT = re.compile(r"https?://[^\s)\]\"'>]+")


def anchors(text, pat, rel, limit=6, group=0):
    out = []
    for m in pat.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        val = m.group(group).strip()
        val = re.sub(r"\s+", " ", val)[:200]
        out.append({"v": val, "at": f"{rel}:{line}"})
        if len(out) >= limit:
            break
    return out


def frontmatter(text):
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fm = {}
    for ln in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", ln)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip("\"'")
    return fm


def scan(name):
    """Resolve one skill name everywhere and extract facts."""
    rec = {"skill_dir": name, "locations": [], "absent_everywhere": True}
    best_text = None
    best_rel = None

    for vault, label in ((AGENTS_VAULT, "agents-live"), (CLAUDE_VAULT, "claude-live")):
        p = vault / name / "SKILL.md"
        if p.is_file():
            b = p.read_bytes()
            txt = b.decode("utf-8", "replace")
            st = p.stat()
            rec["locations"].append(
                {
                    "kind": label,
                    "path": str(p).replace("\\", "/"),
                    "bytes": len(b),
                    "mtime_utc": __import__("datetime")
                    .datetime.utcfromtimestamp(st.st_mtime)
                    .isoformat()
                    + "Z",
                    "sibling_files": sorted(
                        x.name for x in (vault / name).iterdir() if x.is_file()
                    )[:12],
                }
            )
            rec["absent_everywhere"] = False
            if best_text is None or len(txt) > len(best_text):
                best_text, best_rel = txt, str(p).replace("\\", "/")

    for pre in MIRROR_PREFIXES:
        mp = f"{pre}/{name}/SKILL.md"
        if mirror_has(mp):
            txt = mirror_read(mp) or ""
            rec["locations"].append(
                {
                    "kind": f"mirror:{pre}",
                    "path": f"{REF[:12]}:{mp}",
                    "bytes": len(txt.encode("utf-8", "replace")),
                    "last_commit": mirror_last_commit(mp),
                }
            )
            rec["absent_everywhere"] = False
            if best_text is None or len(txt) > len(best_text):
                best_text, best_rel = txt, f"{REF[:12]}:{mp}"

    if best_text is None:
        return rec

    rec["primary_anchor"] = best_rel
    rec["primary_bytes"] = len(best_text.encode("utf-8", "replace"))
    rec["primary_lines"] = best_text.count("\n") + 1
    fm = frontmatter(best_text)
    rec["frontmatter_keys"] = sorted(fm.keys())
    rec["fm_name"] = fm.get("name", "")
    rec["fm_description"] = fm.get("description", "")[:900]
    rec["fm_license"] = fm.get("license", "")
    rec["fm_paths"] = fm.get("paths", "")
    rec["license_anchors"] = anchors(best_text, LICENSE_PAT, best_rel, 6)
    rec["stage_anchors"] = anchors(best_text, STAGE_PAT, best_rel, 10)
    rec["role_terms"] = sorted(
        {m.group(1).lower() for m in ROLE_PAT.finditer(best_text)}
    )[:16]
    rec["tool_terms"] = sorted({m.group(1) for m in TOOL_PAT.finditer(best_text)})[:20]
    rec["stop_anchors"] = anchors(best_text, STOP_PAT, best_rel, 5)
    rec["failure_anchors"] = anchors(best_text, FAIL_PAT, best_rel, 5)
    rec["bench_anchors"] = anchors(best_text, BENCH_PAT, best_rel, 6)
    rec["arxiv_ids"] = sorted({m.group(1) for m in ARXIV_PAT.finditer(best_text)})
    rec["urls"] = sorted(
        {m.group(0).rstrip(".,") for m in URL_PAT.finditer(best_text)}
    )[:10]
    low = best_text.lower()
    rec["signals"] = {
        "is_tombstone": bool(
            re.search(r"\b(tombstone|MOVED\b|renamed to|redirect)\b", best_text, re.I)
        ),
        "shadow_mode": "shadow mode" in low or "shadow-mode" in low,
        "never_blocks": "never block" in low or "does not block" in low,
        "has_scripts_dir": False,
        "mentions_council": "council" in low,
        "mentions_vote": "vote" in low or "voting" in low,
        "mentions_worktree": "worktree" in low,
        "mentions_crossvendor": "cross-vendor" in low or "codex" in low,
    }
    return rec


def main():
    doc = json.loads(REG.read_text(encoding="utf-8"))
    cands = doc["candidates"]
    slice_ = [(i, cands[i - 1]) for i in range(LO, HI + 1)]

    # DETECTOR CONTROL: a known-present skill must resolve, a known-absent must not.
    ctl_present = scan("workflow-authoring")
    ctl_absent = scan("zzz-definitely-not-a-real-skill-9f2a")
    print(
        "DETECTOR CONTROL present=workflow-authoring resolved={} locs={} | "
        "absent=zzz-... resolved={} locs={}".format(
            not ctl_present["absent_everywhere"],
            len(ctl_present["locations"]),
            not ctl_absent["absent_everywhere"],
            len(ctl_absent["locations"]),
        )
    )
    assert not ctl_present["absent_everywhere"], (
        "detector cannot find a known-present skill"
    )
    assert ctl_absent["absent_everywhere"], "detector hallucinates a known-absent skill"

    out = []
    for pos, e in slice_:
        name = e["name"].split("/", 1)[-1]
        rec = scan(name)
        rec["canonical_position"] = pos
        rec["prior_id"] = e["id"]
        rec["prior_name"] = e["name"]
        rec["prior_classification"] = e["classification"]
        rec["prior_provenance"] = e["provenance"]
        rec["prior_does"] = e["does"]
        rec["prior_mechanisms"] = e["mechanisms"]
        rec["prior_maintenance"] = e["maintenance"]
        rec["prior_evidence"] = e["evidence"]
        rec["prior_license"] = e["license"]
        rec["prior_runtime"] = e["runtime"]
        out.append(rec)
        print(
            f"{pos:3d} {name:38s} locs={len(rec['locations'])} "
            f"bytes={rec.get('primary_bytes', 0):6d} "
            f"arxiv={len(rec.get('arxiv_ids', []))} "
            f"tomb={rec.get('signals', {}).get('is_tombstone')} "
            f"{'*** ABSENT ***' if rec['absent_everywhere'] else ''}"
        )

    dest = pathlib.Path(
        r"C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa4_provenance.json"
    )
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    n_abs = sum(1 for r in out if r["absent_everywhere"])
    print(f"\nwrote {dest} entries={len(out)} absent_everywhere={n_abs}")
    print(
        "SUCCESS:wfa4-provenance-probe"
        if len(out) == 32
        else "FAILED:wfa4-provenance-probe"
    )


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
