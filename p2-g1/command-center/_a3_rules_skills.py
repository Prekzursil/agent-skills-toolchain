"""R-H10 + R-H09 re-measurement (2026-08-10), lane A3. READ-ONLY."""
import hashlib
import json
import os
import subprocess

REPO = r"C:\Users\Prekzursil\source\ast-integrate"
REPO_RULES = os.path.join(REPO, "rules", "common")
LIVE_RULES = r"C:\Users\Prekzursil\.claude\rules\common"

REPO_AGENT_SKILLS = os.path.join(REPO, ".agents", "skills")
REPO_SKILLS = os.path.join(REPO, "skills")
LIVE_AGENT_SKILLS = r"C:\Users\Prekzursil\.agents\skills"
LIVE_CLAUDE_SKILLS = r"C:\Users\Prekzursil\.claude\skills"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha_lf(p):
    """EOL-normalised hash so CRLF-only divergence is not reported as content drift."""
    with open(p, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def rules():
    out = {"repo_dir": REPO_RULES, "live_dir": LIVE_RULES, "files": {}}
    rn = {f for f in os.listdir(REPO_RULES) if f.endswith(".md")}
    ln = {f for f in os.listdir(LIVE_RULES) if f.endswith(".md")}
    out["counts"] = {"repo": len(rn), "live": len(ln),
                     "repo_only": sorted(rn - ln), "live_only": sorted(ln - rn)}
    ident = ident_lf = diff = 0
    for f in sorted(rn & ln):
        rp, lp = os.path.join(REPO_RULES, f), os.path.join(LIVE_RULES, f)
        rs, ls = sha(rp), sha(lp)
        rl, ll = sha_lf(rp), sha_lf(lp)
        rec = {"repo_bytes": os.path.getsize(rp), "live_bytes": os.path.getsize(lp),
               "raw_identical": rs == ls, "lf_identical": rl == ll}
        if rs == ls:
            ident += 1
        elif rl == ll:
            ident_lf += 1
        else:
            diff += 1
            # DIRECTION settling experiment: does the LIVE content match ANY historical
            # blob of that path in git?  If yes -> live is an OLD repo version (repo-ahead).
            # If no  -> live holds content that was never committed (live-ahead / live-only).
            revs = git("log", "--all", "--format=%H", "--", f"rules/common/{f}").stdout.split()
            hit = None
            for r in revs[:200]:
                blob = git("show", f"{r}:rules/common/{f}")
                if blob.returncode != 0:
                    continue
                b = blob.stdout.encode("utf-8", "replace")
                if hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest() == ll:
                    hit = r
                    break
            rec["live_matches_history_rev"] = hit
            rec["n_revs_scanned"] = min(len(revs), 200)
            rec["direction"] = "REPO-AHEAD (live == older commit)" if hit else \
                               "LIVE-NOT-IN-HISTORY (live-ahead or hand-edited)"
        out["files"][f] = rec
    out["summary"] = {"identical_raw": ident, "identical_after_lf_norm": ident_lf,
                      "content_diff": diff}
    return out


def count_skills(root):
    if not os.path.isdir(root):
        return {"exists": False}
    dirs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    withskill = [d for d in dirs
                 if os.path.exists(os.path.join(root, d, "SKILL.md"))]
    return {"exists": True, "n_dirs": len(dirs), "n_with_SKILL_md": len(withskill),
            "names": sorted(withskill)}


def skills():
    r = {
        "repo_.agents_skills": count_skills(REPO_AGENT_SKILLS),
        "repo_skills": count_skills(REPO_SKILLS),
        "live_.agents_skills": count_skills(LIVE_AGENT_SKILLS),
        "live_.claude_skills": count_skills(LIVE_CLAUDE_SKILLS),
    }
    sets = {k: set(v.get("names", [])) for k, v in r.items() if v.get("exists")}
    canon = sets.get("repo_.agents_skills", set())
    for k, v in sets.items():
        if k == "repo_.agents_skills":
            continue
        r[k + "__vs_canonical"] = {
            "only_here": sorted(v - canon)[:40], "n_only_here": len(v - canon),
            "missing_here": sorted(canon - v)[:40], "n_missing_here": len(canon - v)}
    return r


if __name__ == "__main__":
    print(json.dumps({"rules_R-H10": rules(), "skills_R-H09": skills()}, indent=1))
