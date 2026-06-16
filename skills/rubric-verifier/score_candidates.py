#!/usr/bin/env python3
"""
score_candidates.py — rubric-verifier helper

Reads a rubric JSON file and a candidates manifest, then emits a ready-to-use
scorer prompt for each candidate diff.  Output goes to stdout (one block per
candidate, separated by a ruler) or, with --out, to individual .txt files.

Manifest format (JSON array):
    [
      {"id": "C_1", "diff_path": "path/to/candidate1.diff"},
      {"id": "C_2", "diff_path": "path/to/candidate2.diff"},
      ...
    ]

Rubric format: the JSON block emitted by Phase 1 of the rubric-verifier skill.

Usage:
    python score_candidates.py --rubric rubric.json --manifest manifest.json
    python score_candidates.py --rubric rubric.json --manifest manifest.json --out scoring-prompts/
"""

import argparse
import json
import sys
from pathlib import Path

SCORER_TEMPLATE = """\
TASK: Score candidate patch {candidate_id} against the rubric below.

Rubric:
---
{rubric_json}
---

Candidate diff (unified diff format):
---
{diff_text}
---

For each criterion C_i:
  - Score: FULL (earns weight_i points) | PARTIAL (earns weight_i / 2, round down) | MISS (0 points)
  - One-line justification citing a specific hunk or the absence of one.

Then compute:
  total_score = sum of earned points
  max_score   = rubric.total_weight

Flag the candidate as SPEC_MISALIGNED if:
  - It scores MISS on ANY criterion with weight == 3, OR
  - It modifies files outside the scope implied by the rubric criteria.

Output a JSON score sheet:
{{
  "candidate_id": "{candidate_id}",
  "scores": [
    {{"criterion": "C1", "score": "FULL|PARTIAL|MISS", "earned": <int>, "justification": "..."}},
    ...
  ],
  "total_score": <int>,
  "max_score": <int>,
  "pct": <float, 0-100>,
  "spec_misaligned": <bool>,
  "misalignment_reason": "<null or string>"
}}
"""

RULER = "\n" + "=" * 72 + "\n"


def load_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"ERROR: {label} file not found: {path}")
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR: {label} is not valid JSON: {exc}")


def load_diff(diff_path: Path, candidate_id: str) -> str:
    if not diff_path.exists():
        sys.exit(f"ERROR: diff file for {candidate_id} not found: {diff_path}")
    return diff_path.read_text(encoding="utf-8", errors="replace")


def validate_manifest(manifest: object) -> list[dict]:
    if not isinstance(manifest, list):
        sys.exit("ERROR: manifest must be a JSON array.")
    for i, entry in enumerate(manifest):
        if not isinstance(entry, dict):
            sys.exit(f"ERROR: manifest entry {i} is not an object.")
        if "id" not in entry or "diff_path" not in entry:
            sys.exit(f"ERROR: manifest entry {i} must have 'id' and 'diff_path' keys.")
    return manifest


def validate_rubric(rubric: object) -> dict:
    if not isinstance(rubric, dict):
        sys.exit("ERROR: rubric must be a JSON object.")
    if "criteria" not in rubric or "total_weight" not in rubric:
        sys.exit("ERROR: rubric must have 'criteria' and 'total_weight' keys.")
    return rubric


def build_prompt(candidate_id: str, rubric_json_str: str, diff_text: str) -> str:
    return SCORER_TEMPLATE.format(
        candidate_id=candidate_id,
        rubric_json=rubric_json_str,
        diff_text=diff_text,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Emit rubric-verifier scorer prompts for each candidate diff."
    )
    parser.add_argument("--rubric", required=True, help="Path to rubric.json (Phase 1 output)")
    parser.add_argument("--manifest", required=True, help="Path to candidates manifest JSON")
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory for per-candidate .txt files (default: stdout)",
    )
    args = parser.parse_args()

    rubric_path = Path(args.rubric)
    manifest_path = Path(args.manifest)
    out_dir = Path(args.out) if args.out else None

    rubric_raw = load_json(rubric_path, "rubric")
    rubric = validate_rubric(rubric_raw)
    rubric_json_str = json.dumps(rubric, indent=2)

    manifest_raw = load_json(manifest_path, "manifest")
    candidates = validate_manifest(manifest_raw)

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    for entry in candidates:
        candidate_id = entry["id"]
        diff_path = Path(entry["diff_path"])
        diff_text = load_diff(diff_path, candidate_id)
        prompt = build_prompt(candidate_id, rubric_json_str, diff_text)

        if out_dir:
            out_file = out_dir / f"score_{candidate_id}.txt"
            out_file.write_text(prompt, encoding="utf-8")
            print(f"Written: {out_file}")
        else:
            print(RULER)
            print(f"--- Scorer prompt for {candidate_id} ---")
            print(RULER)
            print(prompt)

    if not out_dir:
        print(RULER)
        print(f"Total candidates: {len(candidates)}")
        print(
            "Paste each block above into a fresh Task() call (one per candidate).\n"
            "Collect the JSON score sheets, then aggregate per Phase 3 of SKILL.md."
        )


if __name__ == "__main__":
    main()
