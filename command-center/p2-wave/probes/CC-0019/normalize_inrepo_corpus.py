#!/usr/bin/env python3
"""CC-0019 impl pass 2: normalize the IN-REPO source families into claim records.

POPULATION SUBSTITUTION (disclosed, not silent):
  The catalog-contracted corpus (~/.claude/harness-restore-20260806/, the
  1.49 MB Prompt One corpus) is ABSENT on this machine - measured by probe1 and
  independently by reviewer c5-cc-0019 (3 signals, 2026-09-19). Per the wave
  lead's re-scope instruction, this pass normalizes the in-repo families that
  DO exist (adversarial findings, owner option-cards, slop claims, casualty
  incidents, catalog-listed sources). Nothing about the contracted corpus is
  fabricated; probe1 keeps reporting it absent.

Extraction reuses tools/command-center/corpus_normalize shaping with two
additions documented here (the tool's container list was tuned to the Prompt
One corpus shape):
  - container keys for dict JSON extended with "evidence" and
    "residual_unknowns" (unit receipts, e.g. ADV-*.json, carry their findings
    there; each evidence claim becomes its own record);
  - title derivation falls back through title/id/claim_id/name/unit_id and a
    claim[:200] prefix so every emitted record's title is VERBATIM in its
    source file (blocks without a verbatim title are dropped + enumerated).

Every emitted record carries a repo-relative forward-slash anchor `path:line`
pointing at the quoted title text, verified at build time. Idempotent by
construction (stable ids from title+anchor+body).
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import claim_rank as cr  # noqa: E402
import claim_record as crec  # noqa: E402
import corpus_normalize as cn  # noqa: E402

PROBE_DIR = Path(__file__).resolve().parent
CENSUS_PATH = PROBE_DIR / "source-census.json"
CORPUS_DIR = REPO / "command-center" / "corpus"
RECORDS_JSONL = CORPUS_DIR / "claim-records.jsonl"
SUMMARY_JSON = CORPUS_DIR / "normalize-summary.json"
MARKER = CORPUS_DIR / "__cc0019_planted_synthetic__.marker"
CORPUS_REL = "command-center/corpus"

SAMPLE_SIZE = 20
SAMPLE_SEED = 19

# Tool containers + receipt containers (see module docstring).
CONTAINER_KEYS = (
    "claims",
    "findings",
    "options",
    "incidents",
    "failures",
    "evidence",
    "residual_unknowns",
)
TITLE_KEYS = ("title", "id", "claim_id", "name", "unit_id", "unit", "question")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def derive_title(item: object) -> str | None:
    """A title that is verbatim findable in the source file, or None."""
    if not isinstance(item, dict):
        return None
    for key in TITLE_KEYS:
        v = item.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()[:200]
    claim = item.get("claim")
    if isinstance(claim, str) and claim.strip():
        return claim.strip()[:200]
    return None


def json_blocks(rel: str, data: object) -> list[dict]:
    """Dict/list dispatch mirroring cn._extract_blocks with receipt containers."""
    if isinstance(data, list):
        return [cn._json_item_to_block(rel, i, item) for i, item in enumerate(data)]
    if isinstance(data, dict):
        for key in CONTAINER_KEYS:
            if isinstance(data.get(key), list):
                return [
                    cn._json_item_to_block(f"{rel}#{key}", i, item)
                    for i, item in enumerate(data[key])
                ]
        return [cn._json_item_to_block(rel, 0, data)]
    return [
        {
            "_unparseable": True,
            "path": rel,
            "reason": f"json-root-type:{type(data).__name__}",
        }
    ]


def real_line_for_title(text: str, title: str) -> int | None:
    idx = text.find(title)
    if idx < 0:
        return None
    return text.count("\n", 0, idx) + 1


def process_file(rel: str, blocks_out: list, drops: list[dict]) -> None:
    p = REPO / rel
    text = cn._read_text(p)
    if not text.strip():
        drops.append({"input_id": rel, "path": rel, "reason": "empty-file"})
        return
    suffix = p.suffix.lower()
    try:
        if suffix == ".json":
            blocks = json_blocks(rel, json.loads(text))
        else:
            blocks = cn._extract_blocks(Path(rel), text)
    except json.JSONDecodeError as exc:
        drops.append(
            {"input_id": rel, "path": rel, "reason": f"json-decode:{str(exc)[:80]}"}
        )
        return
    except Exception as exc:  # per-artifact pivot: one bad file never aborts
        drops.append(
            {
                "input_id": rel,
                "path": rel,
                "reason": f"extract-error:{type(exc).__name__}",
            }
        )
        return
    n_lines = text.count("\n") + 1
    for block in blocks:
        if block.get("_unparseable"):
            drops.append(
                {
                    "input_id": rel,
                    "path": rel,
                    "reason": str(block.get("reason") or "unparseable")[:120],
                }
            )
            continue
        title = str(block.get("title") or "").strip()
        body = str(block.get("body") or "").strip()
        raw_item = block.get("raw")
        if (not title or re.fullmatch(r"item-\d+", title)) and raw_item is not None:
            title = derive_title(raw_item) or ""
        if not title and not body:
            drops.append({"input_id": rel, "path": rel, "reason": "empty-block"})
            continue
        # Forward-slash repo-relative anchors (portable file:line citations).
        block["path"] = str(block.get("path") or rel).replace("\\", "/")
        if suffix in (".json", ".jsonl"):
            line = real_line_for_title(text, title) if title else None
            if line is None:
                drops.append(
                    {
                        "input_id": rel,
                        "path": rel,
                        "reason": "no-verbatim-anchor-title(json)",
                    }
                )
                continue
        else:
            line = int(block.get("line") or 1)
            if title and title not in text:
                drops.append(
                    {
                        "input_id": rel,
                        "path": rel,
                        "reason": "no-verbatim-anchor-title(md)",
                    }
                )
                continue
        if not (1 <= line <= n_lines):
            drops.append(
                {"input_id": rel, "path": rel, "reason": f"line-out-of-range:{line}"}
            )
            continue
        block["title"] = title
        block["line"] = line
        blocks_out.append(block)


def normalize_once(census: dict) -> dict:
    blocks: list[dict] = []
    drops: list[dict] = []
    fam_stats: dict[str, dict] = {}
    for family, fam in census["families"].items():
        before_blocks = len(blocks)
        before_drops = len(drops)
        for row in fam["files"]:
            process_file(row["path"], blocks, drops)
        fam_stats[family] = {
            "files": fam["n_files"],
            "blocks_extracted": len(blocks) - before_blocks,
            "blocks_dropped": len(drops) - before_drops,
        }

    merges: list[dict] = []
    emitted: list[dict] = []
    by_mech: dict[str, str] = {}
    for block in blocks:
        mech_raw = str(block.get("body") or block.get("title") or "")
        claim = cn._block_to_claim(
            block,
            mechanism_key=hashlib.sha256(mech_raw.encode("utf-8")).hexdigest(),
        )
        mech_key = re.sub(r"\s+", " ", claim["canonical_mechanism"].strip().lower())
        if mech_key in by_mech:
            merges.append(
                {
                    "input_id": claim["claim_id"],
                    "merged_into": by_mech[mech_key],
                    "reason": "duplicate-canonical-mechanism",
                }
            )
            continue
        by_mech[mech_key] = claim["claim_id"]
        emitted.append(claim)

    # Planted synthetic detector control (+1 input, +1 emitted).
    emitted.append(cn.planted_synthetic_record(Path(CORPUS_REL)))

    errs = crec.validate_registry(emitted)
    if errs:
        raise RuntimeError("registry invalid: " + "; ".join(errs[:12]))

    n_inputs = len(blocks) + len(drops) + 1  # +1 planted
    conservation = {
        "inputs": n_inputs,
        "emitted": len(emitted),
        "merged": len(merges),
        "dropped": len(drops),
        "equation": "inputs = emitted + merged + dropped",
        "reconciles": n_inputs == len(emitted) + len(merges) + len(drops),
        "dropped_enumerated": drops,
        "merged_enumerated": merges,
    }
    if not conservation["reconciles"]:
        raise RuntimeError(f"conservation failed: {conservation}")

    ranked = cr.rank_claims(emitted)
    return {
        "records": emitted,
        "conservation": conservation,
        "family_stats": fam_stats,
        "record_ids": sorted(r["claim_id"] for r in emitted),
        "ranked_order": [
            str(row.get("representative_claim_id") or row.get("cluster_key") or "")
            for row in ranked
        ],
        "planted_synthetic_present": any(
            r["claim_id"] == cn.PLANTED_SYNTHETIC_ID for r in emitted
        ),
    }


def quote_candidates(rec: dict) -> list[str]:
    """Text the record quotes that should be findable at its anchor line.

    canonical_mechanism = body[:500]; for md blocks the body starts with the
    raw heading, for json evidence blocks it starts with the claim, so the
    mechanism's first line is the anchor-line text in both cases. claim_text
    is f"{title}: {body[:300]}", so each ": " split prefix of it is a title
    candidate (titles may themselves contain ": ").
    """
    cands: list[str] = []
    mech = str(rec.get("canonical_mechanism") or "").strip()
    if mech:
        parts = mech.splitlines()
        first = parts[0].strip() if parts else ""
        if first:
            cands.append(first[:200])
    ct = str(rec.get("claim_text") or "")
    for i in range(min(len(ct), 252)):
        if ct[i : i + 2] == ": " and 0 < i <= 250:
            cand = ct[:i]
            if len(cand) >= 8:
                cands.append(cand)
    # De-dup, longest first (longest match is the strictest evidence).
    return sorted({c for c in cands if len(c) >= 8}, key=len, reverse=True)


def strict_sample(records: list[dict], seed: int, size: int) -> dict:
    eligible = [r for r in records if r.get("claim_id") != cn.PLANTED_SYNTHETIC_ID]
    rng = random.Random(seed)
    sample = list(eligible)
    rng.shuffle(sample)
    sample = sample[: min(size, len(sample))]
    resolved = 0
    at_line = 0
    rows = []
    for rec in sample:
        lineage = rec.get("source_lineage") or []
        anchor = lineage[0].get("anchor") if lineage else None
        ok = False
        detail = "no-anchor"
        if isinstance(anchor, str) and anchor:
            path_part, _, line_part = anchor.partition(":")
            path_part = path_part.split("#", 1)[0]
            p = REPO / path_part
            if not p.is_file():
                detail = "missing-file"
            else:
                try:
                    line = int(line_part)
                except ValueError:
                    line = 0
                lines = cn._read_text(p).splitlines()
                cands = quote_candidates(rec)
                if not (1 <= line <= len(lines)):
                    detail = "line-out-of-range"
                elif any(c in lines[line - 1] for c in cands):
                    ok = True
                    at_line += 1
                    detail = "quoted-text-at-anchor-line"
                elif any(c in "\n".join(lines) for c in cands):
                    ok = True
                    detail = "quoted-text-in-file-not-at-line"
                else:
                    detail = "quoted-text-not-in-file"
        rows.append(
            {
                "claim_id": rec.get("claim_id"),
                "anchor": anchor,
                "resolved": ok,
                "detail": detail,
            }
        )
        if ok:
            resolved += 1
    n = len(rows)
    return {
        "mode": "strict-author-sample",
        "sample_size_requested": size,
        "sample_size_actual": n,
        "resolved": resolved,
        "resolved_at_anchor_line": at_line,
        "resolve_fraction_strict": f"{resolved}/{n}" if n else "0/0",
        "seed": seed,
        "rows": rows,
    }


def main() -> int:
    census = json.loads(CENSUS_PATH.read_text(encoding="utf-8"))
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    started = now()

    result_a = normalize_once(census)
    result_b = normalize_once(census)
    idempotent = result_a["record_ids"] == result_b["record_ids"]
    records = result_a["records"]

    RECORDS_JSONL.write_text(
        "".join(
            json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in records
        ),
        encoding="utf-8",
    )
    MARKER.write_text(cn.PLANTED_MARKER + "\n", encoding="utf-8")

    sample = strict_sample(records, SAMPLE_SEED, SAMPLE_SIZE)
    tool_sample = cn.sample_anchors_resolve(
        records, sample_size=SAMPLE_SIZE, seed=SAMPLE_SEED
    )

    drop_reasons: dict[str, int] = {}
    for d in result_a["conservation"]["dropped_enumerated"]:
        key = d["reason"].split("(")[0]
        drop_reasons[key] = drop_reasons.get(key, 0) + 1

    summary = {
        "unit": "CC-0019",
        "impl_pass": 2,
        "generated_at": now(),
        "started_at": started,
        "population_substitution": {
            "contracted_input": "~/.claude/harness-restore-20260806/ (Prompt One corpus, 1.49 MB)",
            "contracted_input_status": "ABSENT (probe1 2026-09-19; independent reviewer c5-cc-0019, 3 signals)",
            "substituted_population": "in-repo families per wave-lead re-scope 2026-09-19 (census: "
            "command-center/p2-wave/probes/CC-0019/source-census.json)",
            "fabricated_contracted_contents": False,
        },
        "corpus_root": CORPUS_REL,
        "records_file": "command-center/corpus/claim-records.jsonl",
        "n_records": len(records),
        "families": result_a["family_stats"],
        "conservation": result_a["conservation"],
        "drop_reasons": drop_reasons,
        "planted_synthetic_present": result_a["planted_synthetic_present"],
        "idempotent": idempotent,
        "author_sample_strict": {k: v for k, v in sample.items() if k != "rows"},
        "author_sample_tool_fraction": {
            "resolve_fraction": tool_sample["resolve_fraction"],
            "resolved": tool_sample["resolved"],
            "sample_size_actual": tool_sample["sample_size_actual"],
            "note": "tool sampler counts file-exists-nonempty as weak resolve; strict sample is the load-bearing number",
        },
        "anchor_convention": (
            "repo-relative forward-slash path:line; md lines point at the heading line, "
            "json/jsonl lines point at the first verbatim occurrence of the record title; "
            "#fragments name the json container key"
        ),
        "record_ids": result_a["record_ids"],
        "ranked_order": result_a["ranked_order"],
    }
    SUMMARY_JSON.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    (PROBE_DIR / "sample-resolve.json").write_text(
        json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (PROBE_DIR / "tool-sample-resolve.json").write_text(
        json.dumps(tool_sample, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    cons = result_a["conservation"]
    fams = ", ".join(
        f"{f}={s['blocks_extracted']}em/{s['blocks_dropped']}dr"
        for f, s in result_a["family_stats"].items()
    )
    ok = (
        cons["reconciles"]
        and result_a["planted_synthetic_present"]
        and idempotent
        and sample["resolved"] == sample["sample_size_actual"]
        and sample["sample_size_actual"] == SAMPLE_SIZE
    )
    verdict = (
        "SUCCESS:CC-0019-inrepo-normalize" if ok else "FAILED:CC-0019-inrepo-normalize"
    )
    raw = (
        f"CC-0019 in-repo normalize pass 2 at {now()}\n"
        f"population= in-repo families (substituted; contracted mount ABSENT, see summary)\n"
        f"files={sum(f['files'] for f in result_a['family_stats'].values())} "
        f"records={len(records)} inputs={cons['inputs']} emitted={cons['emitted']} "
        f"merged={cons['merged']} dropped={cons['dropped']} reconciles={cons['reconciles']}\n"
        f"families emitted/dropped: {fams}\n"
        f"drop_reasons={drop_reasons}\n"
        f"planted_synthetic_present={result_a['planted_synthetic_present']} idempotent={idempotent}\n"
        f"author_sample_strict={sample['resolve_fraction_strict']} "
        f"at_line={sample['resolved_at_anchor_line']} seed={SAMPLE_SEED}\n"
        f"tool_sample_fraction={tool_sample['resolve_fraction']}\n"
        f"{verdict}\n"
    )
    (PROBE_DIR / "normalize-run.raw.txt").write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
