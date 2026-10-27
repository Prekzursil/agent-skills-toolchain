"""build/wfa-5 : licence + origin provenance probe for the 32 slice candidates.

Prints the full frontmatter block, any `origin:`/`license:` value with its file:line,
every vendored-from / adapted-from attribution line, and the first lines of any LICENSE
file in the skill directory. Emits _wfa5_licence.json.
"""

import json
import os
import re

REPO = "C:/Users/Prekzursil/source/ast-integrate"
FEAT = os.path.join(REPO, "command-center", "_wfa5_skillfeat.json")
OUT = os.path.join(REPO, "command-center", "_wfa5_licence.json")

with open(FEAT, encoding="utf-8") as fh:
    rows = json.load(fh)["rows"]

ATTR = re.compile(
    r"(?i)(vendored\s+from|adapted\s+from|derived\s+from|upstream|source\s*:|"
    r"github\.com/[\w.\-]+/[\w.\-]+|licen[cs]e\s*:|SPDX|copyright|rider|ELv2|"
    r"Elastic\s+License|MIT|Apache|BSD|CC BY)"
)

out = []
for r in rows:
    name = r["skill_dir_name"]
    path = r["primary_path"]
    if not path:  # repo-only candidate
        for cand in (
            os.path.join(REPO, "skills", name, "SKILL.md"),
            os.path.join(REPO, ".agents", "skills", name, "SKILL.md"),
        ):
            if os.path.isfile(cand):
                path = cand.replace("\\", "/")
                break
    body = ""
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
    lines = body.splitlines()

    fm_block = []
    if lines and lines[0].strip() == "---":
        for i, ln in enumerate(lines[1:80], 2):
            if ln.strip() == "---":
                break
            fm_block.append({"line": i, "text": ln[:300]})

    attr = []
    for i, ln in enumerate(lines, 1):
        if ATTR.search(ln):
            attr.append({"line": i, "text": ln.strip()[:260]})
        if len(attr) >= 10:
            break

    lic_files = []
    d = os.path.dirname(path) if path else None
    if d and os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if re.match(r"(?i)^(licen[cs]e|notice|copying)", f):
                fp = os.path.join(d, f)
                with open(fp, encoding="utf-8", errors="replace") as fh:
                    head = [x.strip() for x in fh.read().splitlines() if x.strip()][:4]
                lic_files.append({"path": fp.replace("\\", "/"), "head": head})

    out.append(
        {
            "registry_index": r["registry_index"],
            "name": name,
            "path_used": path,
            "bytes": len(body),
            "frontmatter_block": fm_block,
            "attribution_lines": attr,
            "licence_files": lic_files,
        }
    )

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, indent=1)

for x in out:
    print("=" * 96)
    print(
        "[%d] %s  (%d bytes)  %s"
        % (x["registry_index"], x["name"], x["bytes"], x["path_used"])
    )
    for f in x["frontmatter_block"]:
        t = f["text"]
        if re.match(r"^\s*(name|description)\s*:", t) and len(t) > 120:
            t = t[:120] + " ...[truncated]"
        print("   fm  %4d: %s" % (f["line"], t))
    for a in x["attribution_lines"][:6]:
        print("   ATT %4d: %s" % (a["line"], a["text"]))
    for lf in x["licence_files"]:
        print("   LICFILE:", lf["path"], "|", " / ".join(lf["head"])[:180])
print("\nwrote", OUT)
