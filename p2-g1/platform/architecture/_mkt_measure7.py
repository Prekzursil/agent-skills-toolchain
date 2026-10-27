"""Seventh pass: the LICENSE surface of the already-committed .claude-plugin/marketplace.json.

The manifest declares "license": "MIT" for a package whose `skills` array enumerates
directories under .agents/skills/. Question: does that payload contain third-party skills
whose own LICENSE is NOT MIT (esp. copyleft / share-alike)?

Detector controls:
  A KNOWN-PRESENT: classify() must fire on a literal CC BY-SA string.
  B KNOWN-PRESENT: classify() must fire on a literal MIT string.
  C KNOWN-ABSENT : classify() must NOT fire on 'hello world'.
A classifier that returns 0 copyleft must first prove it can SEE a known copyleft string.

Run: python platform/architecture/_mkt_measure7.py
"""

import json
import os
import re
from collections import Counter

REPO = "C:/Users/Prekzursil/source/ast-integrate"
COPYLEFT = [
    ("AGPL", r"AGPL|Affero General Public License"),
    ("GPL", r"GNU GENERAL PUBLIC LICENSE|\bGPL-[23]"),
    ("LGPL", r"Lesser General Public License|\bLGPL"),
    ("CC-BY-SA", r"Attribution-ShareAlike|CC BY-SA|by-sa/4\.0"),
    ("MPL", r"Mozilla Public License"),
    ("EPL", r"Eclipse Public License"),
]
PERMISSIVE = [
    ("MIT", r"\bMIT License\b|Permission is hereby granted, free of charge"),
    ("Apache-2.0", r"Apache License\s*,?\s*Version 2\.0"),
    ("BSD", r"BSD [23]-Clause|Redistribution and use in source and binary forms"),
    ("CC-BY", r"Attribution 4\.0 International|CC BY 4\.0"),
    ("CC0", r"CC0 1\.0|Creative Commons Zero"),
    ("ISC", r"ISC License"),
    ("Unlicense", r"This is free and unencumbered software"),
]


def classify(text):
    hits = []
    for name, pat in COPYLEFT:
        if re.search(pat, text, re.I):
            hits.append(("COPYLEFT/SHARE-ALIKE", name))
    for name, pat in PERMISSIVE:
        if re.search(pat, text, re.I):
            hits.append(("permissive", name))
    return hits


def main():
    print("=== repo ROOT license file present? ===")
    root_lic = [
        f
        for f in os.listdir(REPO)
        if f.upper().startswith(("LICENSE", "COPYING", "NOTICE"))
    ]
    print("  root LICENSE/COPYING/NOTICE:", root_lic or "NONE")
    print(
        "  control: README.md present ->",
        os.path.exists(os.path.join(REPO, "README.md")),
    )
    print()

    with open(
        os.path.join(REPO, ".claude-plugin/marketplace.json"), encoding="utf-8"
    ) as fh:
        mp = json.load(fh)
    plug = mp["plugins"][0]
    print("=== the COMMITTED marketplace manifest ===")
    print("  marketplace name :", mp["name"])
    print("  plugin name      :", plug["name"], "version", plug["version"])
    print("  declared license :", plug["license"])
    skills = plug["skills"]
    print("  skills enumerated:", len(skills))
    by_root = Counter(
        (s[2:] if s.startswith("./") else s).split("/")[0] for s in skills
    )
    print("  by source root   :", dict(by_root))
    print()

    print("=== per-skill LICENSE scan over the enumerated payload ===")
    licensed, unlicensed, verdicts = 0, 0, Counter()
    copyleft_dirs = []
    for s in skills:
        # NOTE: lstrip("./") is WRONG here -- it also eats the leading dot of
        # ".agents", turning it into "agents" and reporting 346 phantom
        # missing paths. Strip the exact "./" prefix instead.
        relp = s[2:] if s.startswith("./") else s
        d = os.path.join(REPO, relp.replace("/", os.sep))
        if not os.path.isdir(d):
            verdicts["<path missing on disk>"] += 1
            continue
        lics = [
            f
            for f in os.listdir(d)
            if f.upper().startswith(("LICENSE", "COPYING", "NOTICE"))
        ]
        if not lics:
            unlicensed += 1
            verdicts["no LICENSE file in skill dir"] += 1
            continue
        licensed += 1
        txt = ""
        for f in lics:
            try:
                with open(os.path.join(d, f), encoding="utf-8", errors="replace") as fh:
                    txt += fh.read()
            except OSError:
                pass
        hits = classify(txt)
        if not hits:
            verdicts["LICENSE present, UNRECOGNIZED text"] += 1
        for kind, name in hits:
            verdicts[f"{kind}:{name}"] += 1
            if kind.startswith("COPYLEFT"):
                copyleft_dirs.append((s, name))
    print("  skill dirs WITH a LICENSE file :", licensed)
    print("  skill dirs WITHOUT one         :", unlicensed)
    print("  verdict histogram:")
    for k, v in verdicts.most_common():
        print(f"     {k:44s} {v}")
    print()
    print("  COPYLEFT / SHARE-ALIKE payload entries:", len(copyleft_dirs))
    for s, n in copyleft_dirs:
        print(f"     {n:12s} {s}")
    print()

    print("=== DETECTOR CONTROLS ===")
    print(
        "  A KNOWN-PRESENT CC BY-SA ->",
        classify("Attribution-ShareAlike 4.0 International"),
    )
    print(
        "  B KNOWN-PRESENT MIT      ->",
        classify("Permission is hereby granted, free of charge"),
    )
    print("  C KNOWN-ABSENT  noise    ->", classify("hello world"))
    print()

    print("=== tree-wide LICENSE file count (independent of the manifest) ===")
    n = 0
    roots = Counter()
    for dp, dn, fn in os.walk(REPO):
        dn[:] = [
            x
            for x in dn
            if x not in {".git", "__pycache__", ".ruff_cache", "node_modules"}
        ]
        for f in fn:
            if f.upper().startswith(("LICENSE", "COPYING")):
                n += 1
                key = "/".join(
                    os.path.relpath(dp, REPO).replace("\\", "/").split("/")[:2]
                )
                roots[key] += 1
    print("  LICENSE/COPYING files tree-wide:", n)
    for k, v in roots.most_common(10):
        print(f"     {k:34s} {v}")
    print()
    print("SUCCESS:mkt-measure7")


if __name__ == "__main__":
    main()
