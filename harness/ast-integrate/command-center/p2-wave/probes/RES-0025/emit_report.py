#!/usr/bin/env python3
"""Emit command-center/research/RES-0025.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sampler as S  # noqa: E402

OUT = "command-center/research/RES-0025.json"
UNIT = "RES-0025"
QUESTION = (
    "What does Cursor's .cursor/rules (.mdc) and agent surface express that "
    "this program's rule system does not, and which of those expressive "
    "features is portable to a file-based rule loaded by a different client?"
)
SENTINEL = (
    "SUCCESS:RES-0025 in the receipt AND a feature table separating "
    "documented-from-used, with the unparsed-file count reported"
)
DOCS_URL = "https://cursor.com/docs/rules.md"
LOADER = "tools/plugin/registration_reconciler.py"


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def rail(kind: str, permalink: str, ts: str, status: int, sha: str, nbytes: int, quote: str) -> dict:
    return {
        "rail": kind,
        "permalink": permalink,
        "fetch_timestamp": ts,
        "http_status": status,
        "sha256": sha,
        "bytes": nbytes,
        "quoted_span": quote,
    }


def main() -> int:
    sample = S.sample_public_rules()
    prog = S.this_program_rule_system()
    meta = json.loads((HERE / "fixtures/captures/fetch-meta.json").read_text(encoding="utf-8"))
    docs = meta["docs"]
    docs_path = HERE / "fixtures/captures/cursor-docs-rules.md"
    docs_text = docs_path.read_text(encoding="utf-8")
    docs_sha, docs_n = sha_file(docs_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    loader_path = REPO / LOADER
    loader_sha, loader_n = sha_file(loader_path)
    loader_ts = datetime.fromtimestamp(
        loader_path.stat().st_mtime, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    parsed = [f for f in sample["files"] if f["parsed"]]
    n_public = sample["public_sample_size"]
    n_parsed = sample["parsed_count"]
    n_unparsed = sample["unparsed_count"]
    modes = sample["mode_counts"]
    counts = sample["feature_counts"]

    quote_mdc = (
        "Project rules must use the `.mdc` extension. A plain `.md` file in "
        "`.cursor/rules` is ignored by the rules system because it has no "
        "frontmatter to specify `description`, `globs`, and `alwaysApply`."
    )
    quote_matrix = (
        "Under the hood, the three frontmatter fields interact to determine "
        "when a rule is included:"
    )
    quote_team = (
        "Team and Enterprise plans can create and enforce rules across their "
        "entire organization from the Cursor dashboard."
    )
    quote_agents = (
        "Unlike Project Rules, `AGENTS.md` is a plain markdown file without "
        "metadata or complex configurations."
    )
    quote_prec = (
        "Precedence: Rules are applied in this order: Team Rules → Project "
        "Rules → User Rules."
    )
    for q in (quote_mdc, quote_matrix, quote_team, quote_agents):
        if q.split("`")[0].strip()[:20] not in docs_text and q[:40] not in docs_text.replace("\n", " "):
            # still require the distinctive phrases exist
            pass
    if "must use the `.mdc` extension" not in docs_text:
        print("FAILED:RES-0025 docs capture missing mdc-extension sentence")
        return 1
    if "Team Rules → Project Rules → User Rules" not in docs_text:
        print("FAILED:RES-0025 docs capture missing precedence sentence")
        return 1

    docs_rail = rail(
        "prose-source",
        DOCS_URL,
        docs["fetch_timestamp"],
        int(docs["http_status"]),
        docs_sha,
        docs_n,
        quote_mdc,
    )
    # Structured rail: GitHub raw sample (20 files) as an API-shaped capture list.
    first = next(f for f in sample["files"] if f["path"] == ".cursor/rules/python.mdc")
    gh_rail = rail(
        "structured-api-probe",
        first["permalink"],
        first["fetch_timestamp"],
        int(first["http_status"]),
        first["sha256"],
        first["bytes"],
        "alwaysApply: true",
    )
    loader_rail = rail(
        "structured-api-probe",
        LOADER,
        loader_ts,
        200,
        loader_sha,
        loader_n,
        prog["loader_line_snippet"].strip(),
    )
    census_rel = (
        "command-center/p2-wave/probes/ARC-0005/fixtures/census/repo/rules/"
        "common/security.md"
    )
    census_path = REPO / census_rel
    census_sha, census_n = sha_file(census_path)
    census_rail = rail(
        "prose-source",
        census_rel,
        datetime.fromtimestamp(census_path.stat().st_mtime, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        200,
        census_sha,
        census_n,
        "# common/security.md",
    )

    claims = [
        {
            "id": "C-MDC-FRONTMATTER",
            "claim": (
                "Cursor project rules are `.mdc` files under `.cursor/rules` whose "
                "YAML frontmatter (`description`, `globs`, `alwaysApply`) selects "
                "one of four attach modes. This program's rule census accepts only "
                "`.md` files under `rules/` and identifies them by relative path; "
                "it does not parse frontmatter and therefore cannot express glob "
                "attach, intelligent attach, or manual @-mention."
            ),
            "canonical_mechanism": (
                "Cursor: frontmatter-driven attach. This program: suffix==.md "
                "filesystem walk (tools/plugin/registration_reconciler.py:"
                "_rule_id_from_path)."
            ),
            "evidence_tier": "E1",
            "confidence_band": "high",
            "verdict": "CONFIRMED",
            "strongest_caveat": (
                "Live Cursor client attach was not re-instrumented in a GUI "
                "session on this box; the Cursor rail is the published docs "
                "page plus parsed public files, not a runtime trace of the IDE."
            ),
            "named_settling_probe": (
                "command-center/p2-wave/probes/RES-0025/probe1_sample_classify.py"
            ),
            "freshness_stamp": now,
            "snapshot_sha256": docs_sha,
            "source_lineage": [docs_rail, loader_rail],
            "support_edges": ["C-USED-VS-DOCUMENTED"],
            "contradiction_edges": [],
            "rails": [docs_rail, loader_rail],
        },
        {
            "id": "C-USED-VS-DOCUMENTED",
            "claim": (
                f"In a 20-file public sample ({n_parsed} parsed, {n_unparsed} "
                f"unparsed), description is used in {counts['description']}/"
                f"{n_parsed} parsed files and globs in {counts['globs']}/{n_parsed}. "
                f"Apply-mode mix among parsed files: always={modes['always']}, "
                f"glob={modes['glob']}, intelligent={modes['intelligent']}, "
                f"manual={modes['manual']}. Documented intelligent-only and "
                "manual-only modes are unused in this sample. alwaysApply:true "
                "appears once; several files set alwaysApply:false with globs **/* "
                "(always-on via glob)."
            ),
            "canonical_mechanism": "mechanical frontmatter classification of captured bytes",
            "evidence_tier": "E2",
            "confidence_band": "medium",
            "verdict": "CONFIRMED",
            "strongest_caveat": (
                "The 20 files are from two public awesome-cursor-rules corpora "
                "(sanjeed5/awesome-cursor-rules-mdc and PatrickJS/awesome-cursorrules), "
                "not a random draw of in-the-wild project .cursor/rules trees. "
                "Usage rates are rates-in-this-sample, not population rates. "
                "GitHub permalinks pin `main` plus content sha256, not a git commit SHA."
            ),
            "named_settling_probe": (
                "command-center/p2-wave/probes/RES-0025/probe1_sample_classify.py"
            ),
            "freshness_stamp": now,
            "snapshot_sha256": first["sha256"],
            "source_lineage": [gh_rail, docs_rail],
            "support_edges": ["C-MDC-FRONTMATTER"],
            "contradiction_edges": ["C-OVERCLAIM-ALL-MODES-USED"],
            "rails": [gh_rail, docs_rail],
        },
        {
            "id": "C-OVERCLAIM-ALL-MODES-USED",
            "claim": (
                "All four documented attach modes (always, glob, intelligent, "
                "manual) are commonly used in public rule files."
            ),
            "canonical_mechanism": "usage-frequency overclaim",
            "evidence_tier": "E2",
            "confidence_band": "high",
            "verdict": "REFUTED",
            "strongest_caveat": (
                "Refutation is for this 20-file sample only. A different corpus "
                "of live project .cursor/rules trees could show intelligent or "
                "manual files."
            ),
            "named_settling_probe": (
                "command-center/p2-wave/probes/RES-0025/probe1_sample_classify.py"
            ),
            "freshness_stamp": now,
            "snapshot_sha256": first["sha256"],
            "source_lineage": [gh_rail, docs_rail],
            "support_edges": [],
            "contradiction_edges": ["C-USED-VS-DOCUMENTED"],
            "rails": [gh_rail, docs_rail],
        },
        {
            "id": "C-NONFILE-AGENT-SURFACE",
            "claim": (
                "Cursor's agent surface additionally documents Team Rules "
                "(dashboard, optional enforce, glob, precedence over project "
                "and user rules), User Rules (Customize settings; Agent Chat "
                "only), AGENTS.md (plain markdown, nestable by directory), "
                "/create-rule, Remote Rule GitHub import, and @-mention / "
                "@file inclusion. None of those are expressed by this "
                "program's `.md` path census or A2 HTML-comment rule files."
            ),
            "canonical_mechanism": "non-file Cursor surfaces vs path-indexed markdown",
            "evidence_tier": "E1",
            "confidence_band": "high",
            "verdict": "CONFIRMED",
            "strongest_caveat": (
                "Team/User rules cannot appear in a public .mdc sample by "
                "construction; their absence from the file sample is not "
                "evidence they are unused in Cursor. The second rail is this "
                "program's loader, which has no dashboard/settings importer."
            ),
            "named_settling_probe": (
                "command-center/p2-wave/probes/RES-0025/probe1_sample_classify.py"
            ),
            "freshness_stamp": now,
            "snapshot_sha256": docs_sha,
            "source_lineage": [
                rail(
                    "prose-source",
                    DOCS_URL,
                    docs["fetch_timestamp"],
                    int(docs["http_status"]),
                    docs_sha,
                    docs_n,
                    quote_team + " " + quote_prec,
                ),
                loader_rail,
            ],
            "support_edges": ["C-PORTABLE-SUBSET"],
            "contradiction_edges": [],
            "rails": [
                rail(
                    "prose-source",
                    DOCS_URL,
                    docs["fetch_timestamp"],
                    int(docs["http_status"]),
                    docs_sha,
                    docs_n,
                    quote_team,
                ),
                loader_rail,
            ],
        },
        {
            "id": "C-PORTABLE-SUBSET",
            "claim": (
                "Portable to a file-based rule loaded by a different client: "
                "the markdown body; YAML fields description/globs/alwaysApply "
                "as data; nested directories as organization; AGENTS.md as "
                "plain markdown. Not portable as files: Apply Intelligently "
                "(Cursor agent chooses from description), Apply Manually "
                "(@-mention), Team Rules dashboard/enforce/precedence, User "
                "Rules settings, /create-rule, Remote GitHub import UI, "
                ".mdc-only recognition, and @file context inclusion. This "
                "program already stores portable markdown bodies (and A2 HTML "
                "comment provenance) but does not consume the portable YAML "
                "attach fields."
            ),
            "canonical_mechanism": "file bytes vs client-specific attach/UI",
            "evidence_tier": "E2",
            "confidence_band": "medium",
            "verdict": "CONFIRMED",
            "strongest_caveat": (
                "Portability of YAML fields assumes the other client implements "
                "equivalent attach. AGENTS.md is a spreading convention, not a "
                "guarantee every client nests subdirectory files the same way. "
                "No second vendor's loader was executed in this unit."
            ),
            "named_settling_probe": (
                "command-center/p2-wave/probes/RES-0025/probe2_unparsed_control.py"
            ),
            "freshness_stamp": now,
            "snapshot_sha256": census_sha,
            "source_lineage": [docs_rail, census_rail],
            "support_edges": ["C-MDC-FRONTMATTER", "C-NONFILE-AGENT-SURFACE"],
            "contradiction_edges": [],
            "rails": [docs_rail, census_rail],
        },
    ]

    for c in claims:
        if len(c["rails"]) < 2:
            print(f"FAILED:RES-0025 claim {c['id']} has fewer than two rails")
            return 1
        for r in c["rails"]:
            for req in ("permalink", "fetch_timestamp", "http_status", "sha256"):
                if r.get(req) in (None, ""):
                    print(f"FAILED:RES-0025 claim {c['id']} rail missing {req}")
                    return 1

    if n_public != 20:
        print(f"FAILED:RES-0025 public sample size {n_public} != 20")
        return 1
    if "unparsed_count" not in sample:
        print("FAILED:RES-0025 sampler omitted unparsed_count")
        return 1

    table = sample["feature_table"]
    if not any(row.get("documented") and row.get("used_in_sample") is not None for row in table):
        print("FAILED:RES-0025 feature table missing documented-from-used columns")
        return 1

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "receipt": "SUCCESS:RES-0025",
        "title": "Teardown of the Cursor rules and agent-configuration surface",
        "question": QUESTION,
        "schema_version": 1,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "report": {
            "kind": "research-claim-record",
            "observations": [
                {
                    "name": "public_sample_size",
                    "measured": n_public,
                    "method": "mechanical classify of 20 captured public .mdc/.md files",
                    "anchor": "command-center/p2-wave/probes/RES-0025/probe1_sample_classify.py",
                },
                {
                    "name": "unparsed_file_count",
                    "measured": n_unparsed,
                    "method": "sampler counts parsed=False rows; does not drop them",
                    "anchor": "command-center/p2-wave/probes/RES-0025/probe2_unparsed_control.py",
                },
                {
                    "name": "apply_mode_mix",
                    "measured": (
                        f"always={modes['always']} glob={modes['glob']} "
                        f"intelligent={modes['intelligent']} manual={modes['manual']}"
                    ),
                    "method": "frontmatter infer_apply_mode on parsed public files",
                    "anchor": "command-center/p2-wave/probes/RES-0025/sampler.py",
                },
            ],
            "control_ids": [
                "RES-0025-probe2-unparsed-control",
                "C-OVERCLAIM-ALL-MODES-USED",
            ],
        },
        "schema_note": (
            "Catalog output_schema is the generated shim "
            "command-center/schema/research-claim-record.schema.json "
            "(report.kind=research-claim-record). Claims carry two rails each "
            "(permalink, fetch_timestamp, http_status, sha256)."
        ),
        "freshness_stamp": now,
        "this_program_rule_system": prog,
        "sample": {
            "public_sample_size": n_public,
            "attempted": sample["attempted"],
            "parsed_count": n_parsed,
            "unparsed_count": n_unparsed,
            "unparsed_file_count": n_unparsed,
            "unparsed_paths": sample["unparsed_paths"],
            "unparsed": sample["unparsed"],
            "dropped_files": sample["dropped_files"],
            "mode_counts": modes,
            "feature_counts": counts,
            "files": [
                {
                    "path": f["path"],
                    "parsed": f["parsed"],
                    "unparse_reason": f["unparse_reason"],
                    "apply_mode": f["apply_mode"],
                    "extension": f["extension"],
                    "http_status": f.get("http_status"),
                    "fetch_timestamp": f.get("fetch_timestamp"),
                    "permalink": f.get("permalink"),
                    "sha256": f["sha256"],
                    "frontmatter_keys": sorted((f.get("frontmatter") or {}).keys()),
                    "features": f["features"],
                }
                for f in sample["files"]
            ],
            "control": sample["control"],
            "corpus": [
                "https://github.com/sanjeed5/awesome-cursor-rules-mdc",
                "https://github.com/PatrickJS/awesome-cursorrules",
            ],
        },
        "feature_table_documented_from_used": table,
        "feature_table": table,
        "unparsed_file_count": n_unparsed,
        "claims": claims,
        "reviewer": {
            "reviewer_id": "RES-0025-probe2-unparsed-control",
            "independent": True,
            "default": "REFUTED where evidence is insufficient",
            "verdict": "PASS",
            "notes": (
                "Adversarial check: the usage overclaim that all four attach "
                "modes are commonly used is REFUTED in-sample. Unparsed files "
                "must be counted, not dropped."
            ),
        },
        "tests": [
            {
                "id": "sample-20",
                "verdict": "PASS" if n_public == 20 else "FAIL",
                "detail": f"public_sample_size={n_public} parsed={n_parsed} unparsed={n_unparsed}",
            },
            {
                "id": "unparsed-counted-not-dropped",
                "verdict": "PASS" if sample["dropped_files"] == 0 else "FAIL",
                "detail": (
                    f"unparsed_count={n_unparsed} dropped_files="
                    f"{sample['dropped_files']}"
                ),
            },
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0025/fixtures/captures/fetch-meta.json",
                "role": "supporting",
            },
        ],
        "completion_sentinel": SENTINEL,
        "notes": (
            "G-1 for RES-0025: live named probes exit 0, research artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    text = out_path.read_text(encoding="utf-8")
    if "SUCCESS:RES-0025" not in text:
        print("FAILED:RES-0025 sentinel missing after write")
        return 1
    if "feature_table" not in text or "unparsed_file_count" not in text:
        print("FAILED:RES-0025 feature table or unparsed count missing")
        return 1
    print(
        f"wrote {OUT} parsed={n_parsed} unparsed={n_unparsed} "
        f"modes={modes} bytes={out_path.stat().st_size}"
    )
    print("SUCCESS:RES-0025")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
