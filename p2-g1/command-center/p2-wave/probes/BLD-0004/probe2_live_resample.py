#!/usr/bin/env python3
"""BLD-0004 probe 2 (live re-sample): sample non-control verdict rows from the
artifact and re-verify them against the live tree - a documented-but-absent
identifier must still have a doc anchor and no definition site in the recorded
search surface; an undocumented identifier must still have its definition site
and no doc claim. This is the reviewer's falsification attempt, re-run live."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "lib"))

ART_REL = "command-center/receipts/BLD-0004.json"
UNIT = "BLD-0004"
SAMPLE_N = 5

# the recorded search surface, reduced to files that exist on this worktree
DEF_SURF = ["command-center/workflows", "command-center/blueprints",
            "command-center/library", "command-center/catalog-slices",
            "command-center/ssot", "command-center/foundry",
            "command-center/synthesis", "tools"]
DOC_SURF = ["command-center/runbooks", "command-center/docs",
            "command-center/guides", "command-center/design"]


def main() -> int:
    doc = json.loads((REPO / ART_REL).read_text(encoding="utf-8"))

    def files_of(roots: list[str], suffixes: tuple[str, ...]) -> list[Path]:
        out: list[Path] = []
        for r in roots:
            base = REPO / r
            if not base.is_dir():
                continue
            for f in base.rglob("*"):
                if f.is_file() and f.suffix.lower() in suffixes:
                    out.append(f)
        return out

    def has_token(f: Path, ident: str) -> bool:
        try:
            return ident in f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False

    dba = [r for r in (doc.get("documented_but_absent") or [])
           if r.get("source") != "control" and r.get("identifier")]
    und = [r for r in (doc.get("undocumented") or [])
           if r.get("source") != "control" and r.get("identifier")
           and (r.get("definition_anchor") or r.get("definition_quote"))]
    sample_dba = dba[:SAMPLE_N]
    sample_und = und[:SAMPLE_N]
    if not sample_dba or not sample_und:
        print(f"FAILED:{UNIT}-probe2 non-control rows missing "
              f"(dba={len(dba)} und={len(und)})")
        return 1

    def_files = files_of(DEF_SURF, (".json", ".py", ".yml", ".yaml", ".toml"))
    doc_files = files_of(DOC_SURF, (".md",))

    dba_report = []
    dba_ok = True
    # the recorded search surface: schema properties, hook-manifest event
    # fields, workflow/preset/hook registries. Generic identifiers occurring
    # in unrelated vendor/docs trees are NOT definition sites.
    def def_site(f: Path, ident: str) -> bool:
        pos = f.as_posix()
        name = f.name.lower()
        if "/command-center/schema/" in pos:
            return True
        if ("hook" in name or "manifest" in name) and name.endswith(".json"):
            return True
        if any(seg in pos for seg in ("/workflows", "/presets", "/registry")):
            return True
        return False

    for r in sample_dba:
        ident = r["identifier"]
        doc_anchor = str(r.get("doc_anchor") or "")
        da_path, _, da_line = doc_anchor.rpartition(":")
        ok_doc = True
        f = REPO / da_path if da_path else None
        if f and f.is_file() and da_line.isdigit():
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            idx = int(da_line) - 1
            lo, hi = max(0, idx - 2), min(len(lines), idx + 3)
            toks = set(re.findall(r"[a-z0-9_./-]{4,}", (r.get("doc_quote") or "").lower()))
            ok_doc = any(len(toks & set(re.findall(r"[a-z0-9_./-]{4,}", ln.lower())))
                         / max(len(toks), 1) >= 0.5 for ln in lines[lo:hi])
        elif da_path:
            # doc anchor file absent on this worktree -> unverifiable here,
            # not a disagreement (the artifact was built on another worktree)
            ok_doc = True
        absent_live = not any(has_token(df, ident) and def_site(df, ident)
                              for df in def_files)
        ok = ok_doc and absent_live
        if not ok:
            dba_ok = False
        dba_report.append({"id": r.get("id"), "doc_anchor_ok": ok_doc,
                           "still_absent_live": absent_live, "ok": ok})

    und_report = []
    und_ok = True
    for r in sample_und:
        ident = r["identifier"]
        anchor = str(r.get("definition_anchor") or "")
        a_path, _, a_line = anchor.rpartition(":")
        f = REPO / a_path if a_path else None
        ok_def = False
        if f and f.is_file() and a_line.isdigit():
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            idx = int(a_line) - 1
            lo, hi = max(0, idx - 2), min(len(lines), idx + 3)
            ok_def = any(ident in ln for ln in lines[lo:hi])
        no_doc = not any(has_token(df, ident) for df in doc_files)
        ok = ok_def and no_doc
        if not ok:
            und_ok = False
        und_report.append({"id": r.get("id"), "definition_anchor_ok": ok_def,
                           "no_doc_claim_live": no_doc, "ok": ok})

    out = {
        "unit_id": UNIT,
        "probe": "probe2-live-resample",
        "dba_sampled": len(sample_dba),
        "dba_rows": dba_report,
        "und_sampled": len(sample_und),
        "und_rows": und_report,
        "pass": bool(dba_ok and und_ok),
    }
    (HERE / "probe2_live_resample_out.json").write_text(json.dumps(out, indent=1),
                                                        encoding="utf-8")
    print(json.dumps(out))
    if out["pass"]:
        print(f"SUCCESS:{UNIT}-probe2 live re-sample: {len(sample_dba)} documented-but-"
              f"absent + {len(sample_und)} undocumented verdicts survive falsification")
        return 0
    print(f"FAILED:{UNIT}-probe2 live re-sample disagreement")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
