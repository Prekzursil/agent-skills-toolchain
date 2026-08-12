"""LANE C1 read-only probe: map each of the 20 Phase-15 spec deliverables (_USER-PROMPTS.md
:11104-11123) and each of the 10 Phase-16 loop steps (:11139-11148) onto catalog units.

Mechanical part: keyword match over unit title+question_or_target, across ALL 2,007 units, and
separately restricted to the 43 P15/P16 units. Judgement (which unit actually OWNS a deliverable)
is left to the human-readable output.

Also: does any file on disk satisfy each deliverable? Probed by path existence for the
document-shaped deliverables, with a detector control.
"""

import json
import os
import re

d = json.load(open("command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
seq = d["work_units"]
p1516 = {u["id"] for u in seq if str(u.get("phase")) in ("15", "16")}


def blob(u):
    return " ".join(str(u.get(k) or "") for k in
                    ("title", "question_or_target", "output_path", "evidence_requirement"))


P15 = [
    ("1 semantic version", r"semantic[- ]version|version bump|versioning rule"),
    ("2 changelog", r"changelog|change log"),
    ("3 migration guide", r"migration guide|migrat\w+ (?:guide|path|doc)|legacy .*migration"),
    ("4 rollback guide", r"rollback (?:guide|manifest|contract|coverage)"),
    ("5 signed artifacts", r"signature|signed|signing|sigstore|cosign"),
    ("6 provenance attestation", r"provenance attestation|attestation"),
    ("7 SBOM", r"\bsbom\b"),
    ("8 license inventory", r"licen[cs]e inventory|licen[cs]e (?:and rights|roll)"),
    ("9 vulnerability scan", r"vulnerabilit|advisory (?:re-?)?scan|osv|cve scan"),
    ("10 compatibility matrix", r"compatibilit\w* matrix|support matrix"),
    ("11 marketplace listing", r"marketplace (?:listing|manifest|index|entry)"),
    ("12 install/update/uninstall docs",
     r"install.*(?:update|uninstall)|uninstall|lifecycle (?:drill|operation)"),
    ("13 quick-start examples", r"quick[- ]?start|getting started"),
    ("14 advanced workflow examples", r"advanced (?:workflow|example)|example workflow|worked example"),
    ("15 security policy", r"security polic"),
    ("16 contribution guide", r"contribution guide|contributing"),
    ("17 governance guide", r"governance"),
    ("18 support policy", r"support polic"),
    ("19 deprecation policy", r"deprecation polic|deprecat\w+ (?:and|then) revoke|withdrawal"),
    ("20 release notes", r"release notes"),
]

P16 = [
    ("1 observe failure/opportunity", r"improvement[- ]candidate|candidate intake|observe"),
    ("2 structured candidate", r"structured candidate|candidate improvement|intake"),
    ("3 reproduce baseline", r"baseline reproduc|reproduce.*baseline"),
    ("4 implement in isolation", r"isolat\w+ implementation|in isolation"),
    ("5 benchmark+regression suite", r"benchmark.*regress|regression suite|meta[- ]benchmark"),
    ("6 independently review", r"independent\w* (?:review|re-?measur|confirm)"),
    ("7 keep only when measured", r"keep only|measured (?:win|benefit)|benefit gate|retention"),
    ("8 revert when neutral/harmful", r"revert|auto[- ]?revert"),
    ("9 record lesson in skill/rule/workflow", r"lesson (?:writeback|write-back)|writeback"),
    ("10 update the benchmark", r"benchmark augmentation|update the benchmark|regression (?:seed|case)"),
]


def report(name, spec, anchor):
    print(f"\n{'=' * 78}\n### {name}  ({anchor})\n{'=' * 78}")
    for label, pat in spec:
        rx = re.compile(pat, re.I)
        allhits = [u["id"] for u in seq if rx.search(blob(u))]
        inphase = [i for i in allhits if i in p1516]
        titles = {u["id"]: u.get("title", "")[:74] for u in seq if u["id"] in set(inphase)}
        print(f"\n[{label}]")
        print(f"  units anywhere in catalog: {len(allhits)}   IN PHASE 15/16: {len(inphase)}")
        if inphase:
            for i in inphase:
                print(f"    - {i}: {titles[i]}")
        else:
            print("    - NONE in phase 15/16"
                  + (f"  (nearest elsewhere: {allhits[:6]})" if allhits else "  (NONE anywhere)"))


report("PHASE 15 — 20 required deliverables", P15, "_USER-PROMPTS.md:11104-11123")
report("PHASE 16 — 10 loop steps", P16, "_USER-PROMPTS.md:11139-11148")

# --- on-disk existence of the document-shaped deliverables ---
print(f"\n{'=' * 78}\n### ON-DISK PROBE for document-shaped P15 deliverables\n{'=' * 78}")
cands = {
    "changelog": ["CHANGELOG.md", "docs/CHANGELOG.md", "command-center/CHANGELOG.md"],
    "migration guide": ["MIGRATION.md", "docs/MIGRATION.md", "docs/migration.md"],
    "rollback guide": ["command-center/ROLLBACK-MANIFEST.md", "ROLLBACK.md"],
    "SBOM": ["sbom.json", "SBOM.json", "sbom.spdx.json", "sbom.cdx.json", "dist/sbom.json"],
    "license inventory": ["LICENSE", "LICENSE.md", "licenses.json", "THIRD-PARTY-NOTICES.md"],
    "compatibility matrix": ["command-center/COMPATIBILITY-MATRIX.json",
                             "docs/compatibility-matrix.md"],
    "marketplace listing": [".claude-plugin/marketplace.json"],
    "install docs": ["docs/INSTALL.md", "INSTALL.md", "release/README.md"],
    "quick-start": ["docs/QUICKSTART.md", "QUICKSTART.md"],
    "security policy": ["SECURITY.md"],
    "contribution guide": ["CONTRIBUTING.md", ".github/CONTRIBUTING.md"],
    "governance guide": ["GOVERNANCE.md", "docs/GOVERNANCE.md"],
    "support policy": ["SUPPORT.md", ".github/SUPPORT.md"],
    "deprecation policy": ["DEPRECATION.md", "docs/DEPRECATION.md"],
    "release notes": ["RELEASE-NOTES.md", "docs/RELEASE-NOTES.md"],
    "provenance attestation": [".provenance", "provenance.json"],
    "version": ["VERSION", "package.json", ".claude-plugin/plugin.json"],
}
for k, paths in cands.items():
    found = [p for p in paths if os.path.exists(p)]
    print(f"  {'FOUND  ' if found else 'ABSENT '} | {k:24s} | "
          f"{found if found else 'tried ' + str(paths)}")
print("\nDETECTOR CONTROL (known-present): SECURITY.md exists =", os.path.exists("SECURITY.md"),
      "| bogus path exists =", os.path.exists("NO-SUCH-FILE-C1.md"))
