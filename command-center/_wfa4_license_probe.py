"""Corrected license/origin probe for the wfa-4 slice.

The first pass matched 'mit' inside 'commit'/'limit'/'submit' (a use-vs-mention
detector failure). This version is case-sensitive with word boundaries and carries a
BOTH-STATES control: it must FIRE on a known-present license line and must STAY SILENT
on the commit/limit/submit decoys.
"""

import json
import pathlib
import re
import subprocess

CORPUS = pathlib.Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806")
MIRROR = CORPUS / "main-mirror.git"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"
PROV = pathlib.Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa4_provenance.json"
)

SPDX = re.compile(
    r"\bMIT\b|\bApache[- ]2\.0\b|\bAGPL(?:[- ]3(?:\.0)?)?\b|\bGPL[- ]\d(?:\.\d)?\b|"
    r"\bLGPL[- ]\d\b|\bBSD[- ]\d\b|\bMPL[- ]2\.0\b|CC[ -]BY[- ]SA(?:\s*4\.0)?|"
    r"\bUnlicense\b|\bISC\b"
)
LIC_LINE = re.compile(r"^.*licen[cs]e\s*[:=].*$", re.I | re.M)
OWNER = re.compile(r"owner[- ]authored|private estate|proprietary", re.I)


def git(*a):
    r = subprocess.run(
        ["git", "--git-dir", str(MIRROR), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout or ""


def control():
    decoys = "we commit the limit and submit it; permit transmit summit"
    hits = SPDX.findall(decoys)
    known = "license: MIT\nHypoFuzz is AGPL-3.0 now.\nCC BY-SA 4.0 applies."
    fires = SPDX.findall(known)
    print(f"CONTROL decoys(commit/limit/submit/permit/transmit/summit) -> {hits} (must be [])")
    print(f"CONTROL known-license string -> {fires} (must be non-empty)")
    assert hits == [], "detector still matches 'mit' inside words"
    assert fires, "detector fails on a known-present license"
    return True


def read_primary(rec):
    for want in ("agents-live", "claude-live"):
        for loc in rec["locations"]:
            if loc["kind"] == want:
                return pathlib.Path(loc["path"]).read_text(
                    encoding="utf-8", errors="replace"
                ), loc["path"]
    for loc in rec["locations"]:
        if loc["kind"].startswith("mirror:"):
            mp = loc["path"].split(":", 1)[1]
            rc, out = git("cat-file", "-p", f"{REF}:{mp}")
            if rc == 0:
                return out, loc["path"]
    return None, None


def anchored(text, pat, rel, limit=8):
    out = []
    seen = set()
    for m in pat.finditer(text):
        ln = text.count("\n", 0, m.start()) + 1
        v = re.sub(r"\s+", " ", m.group(0)).strip()[:160]
        key = (v, ln)
        if key in seen:
            continue
        seen.add(key)
        out.append({"v": v, "at": f"{rel}:{ln}"})
        if len(out) >= limit:
            break
    return out


def main():
    control()

    # repo-level LICENSE at the pinned ref (the license SOURCE for vendored skills)
    print("\n=== repo-level license files at the pinned ref ===")
    rc, out = git("ls-tree", "-r", "--name-only", REF)
    names = out.splitlines() if rc == 0 else []
    lic_files = [
        n
        for n in names
        if re.search(r"(^|/)(LICEN[CS]E|COPYING|NOTICE)(\.[A-Za-z]+)?$", n, re.I)
    ]
    print(f"tree entries={len(names)}  license-ish files={len(lic_files)}")
    for n in lic_files[:25]:
        print("   ", n)
    root_lic = None
    for n in lic_files:
        if "/" not in n:
            rc2, body = git("cat-file", "-p", f"{REF}:{n}")
            if rc2 == 0:
                first = [ln for ln in body.splitlines() if ln.strip()][:3]
                root_lic = {"path": f"{REF[:12]}:{n}", "head": first}
                print(f"  ROOT LICENSE {n}: {first}")
    if root_lic is None:
        print("  ROOT LICENSE: ABSENT at this ref (no top-level LICENSE/COPYING/NOTICE)")

    recs = json.loads(PROV.read_text(encoding="utf-8"))
    results = []
    print("\n=== per-candidate license / origin ===")
    for rec in recs:
        txt, rel = read_primary(rec)
        name = rec["skill_dir"]
        if txt is None:
            results.append({"skill_dir": name, "status": "UNREADABLE"})
            print(f"{name:34s} UNREADABLE")
            continue
        # per-skill license file?
        skill_lic = []
        for loc in rec["locations"]:
            if loc["kind"] in ("agents-live", "claude-live"):
                d = pathlib.Path(loc["path"]).parent
                for f in d.iterdir():
                    if re.match(r"LICEN[CS]E|COPYING|NOTICE", f.name, re.I):
                        skill_lic.append(str(f).replace("\\", "/"))
        for pre in ("skills", ".agents/skills"):
            rc3, o3 = git("ls-tree", "-r", "--name-only", REF, "--", f"{pre}/{name}/")
            if rc3 == 0:
                for n in o3.splitlines():
                    if re.search(r"(LICEN[CS]E|COPYING|NOTICE)", n, re.I):
                        skill_lic.append(f"{REF[:12]}:{n}")
        fm_origin = ""
        m = re.search(r"^origin\s*:\s*(.+)$", txt[:1500], re.M)
        if m:
            fm_origin = m.group(1).strip().strip("\"'")
        fm_lic = ""
        m = re.search(r"^license\s*:\s*(.+)$", txt[:1500], re.M | re.I)
        if m:
            fm_lic = m.group(1).strip().strip("\"'")
        row = {
            "skill_dir": name,
            "canonical_position": rec["canonical_position"],
            "read_from": rel,
            "fm_license": fm_lic,
            "fm_origin": fm_origin,
            "spdx_anchors": anchored(txt, SPDX, rel, 8),
            "license_lines": anchored(txt, LIC_LINE, rel, 5),
            "owner_authored_anchors": anchored(txt, OWNER, rel, 3),
            "skill_local_license_files": sorted(set(skill_lic)),
        }
        results.append(row)
        print(
            f"{name:34s} fm_license={fm_lic or '-':6s} fm_origin={(fm_origin or '-')[:44]:44s} "
            f"spdx={[a['v'] for a in row['spdx_anchors']][:4]} localLIC={len(row['skill_local_license_files'])}"
        )

    dest = pathlib.Path(
        r"C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa4_license.json"
    )
    dest.write_text(
        json.dumps({"root_license": root_lic, "candidates": results}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nwrote {dest}")
    print("SUCCESS:wfa4-license-probe")


if __name__ == "__main__":
    main()
