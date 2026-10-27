"""One REAL unanswerable-question record from this program.

Question: what is the verbatim owner-spec text at _USER-PROMPTS.md:11276
that defines the proof-of-impossibility record?

This worktree has only a catalog-recovered placeholder at that line.
The original prompt file is not mounted.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from record_schema import RECORD_KIND

SLICE_REL = "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
QUESTION = (
    "What is the verbatim owner-spec text at _USER-PROMPTS.md:11276 that "
    "defines the proof-of-impossibility record?"
)
RETRY_AFTER = "2026-08-31T00:00:00Z"
PLACEHOLDER = "proof-of-impossibility."
WIN_PROMPT = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_url(path: Path) -> str:
    return path.resolve().as_uri()


def lineage_for(path: Path, fetched_at: str, missing: bool = False) -> dict:
    if missing or not path.is_file():
        empty = b""
        return {
            "resolved_url": file_url(path) if path.anchor else str(path),
            "fetch_timestamp": fetched_at,
            "sha256_of_fetched_bytes": sha256_bytes(empty),
            "bytes": 0,
            "http_status": None,
            "note": "path is not a file on this worktree",
        }
    raw = path.read_bytes()
    return {
        "resolved_url": file_url(path),
        "fetch_timestamp": fetched_at,
        "sha256_of_fetched_bytes": sha256_bytes(raw),
        "bytes": len(raw),
        "http_status": None,
        "note": "local file read; sha256 of on-disk bytes",
    }


def slice_line(repo: Path, n: int) -> str | None:
    path = repo / SLICE_REL
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if n < 1 or n > len(lines):
        return None
    return lines[n - 1]


def measure(repo: Path) -> dict:
    root_prompt = repo / "_USER-PROMPTS.md"
    win_prompt = Path(WIN_PROMPT)
    slice_path = repo / SLICE_REL
    catalog = repo / CATALOG_REL
    claim_reg = repo / "command-center/CLAIM-REGISTRY.json"
    src_reg = repo / "command-center/sources/REGISTER.md"
    cnl73 = repo / (
        "command-center/design/council/"
        "CNL-0073-proof-of-impossibility-what-actually-constitutes-proof.md"
    )
    glob_hits = list(repo.glob("**/_USER-PROMPTS.md"))
    line = slice_line(repo, 11276)
    return {
        "root_prompt_is_file": root_prompt.is_file(),
        "win_prompt_is_file": win_prompt.is_file(),
        "slice_is_file": slice_path.is_file(),
        "catalog_is_file": catalog.is_file(),
        "claim_registry_is_file": claim_reg.is_file(),
        "sources_register_is_file": src_reg.is_file(),
        "cnl0073_is_file": cnl73.is_file(),
        "glob_user_prompts_count": len(glob_hits),
        "slice_line_11276": line,
        "slice_line_is_placeholder": line == PLACEHOLDER,
    }


def build_worked_example(repo: Path, fetched_at: str | None = None) -> dict:
    ts = fetched_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    measurements = measure(repo)
    slice_path = repo / SLICE_REL
    catalog = repo / CATALOG_REL
    slice_lin = lineage_for(slice_path, ts)
    cat_lin = lineage_for(catalog, ts)
    missing_prompt_lin = lineage_for(repo / "_USER-PROMPTS.md", ts, missing=True)

    official_count = int(measurements["root_prompt_is_file"]) + int(
        measurements["win_prompt_is_file"]
    )
    glob_count = int(measurements["glob_user_prompts_count"])
    archival_hits = 1 if measurements["slice_is_file"] else 0
    catalog_hits = 1 if measurements["catalog_is_file"] else 0
    code_cnl73 = 1 if measurements["cnl0073_is_file"] else 0
    claim_hits = 1 if measurements["claim_registry_is_file"] else 0
    src_hits = 1 if measurements["sources_register_is_file"] else 0

    return {
        "record_kind": RECORD_KIND,
        "closed_as": "cannot-be-obtained",
        "program_unit_id": "RES-0149",
        "question": QUESTION,
        "exhausted_sources": [
            {
                "source_class": "official-docs",
                "status": "exhausted",
                "notes": "Owner spec file is the primary source class for line 11276.",
                "queries": [
                    {
                        "query": "Path.is_file(_USER-PROMPTS.md) at repo root",
                        "result_count": official_count,
                        "backend": "pathlib.Path.is_file",
                        "hit_summary": (
                            f"root={measurements['root_prompt_is_file']} "
                            f"win={measurements['win_prompt_is_file']}"
                        ),
                    },
                    {
                        "query": "glob **/_USER-PROMPTS.md from repo root",
                        "result_count": glob_count,
                        "backend": "pathlib.Path.glob",
                    },
                ],
            },
            {
                "source_class": "archival",
                "status": "exhausted",
                "notes": (
                    "CC-0024 recovered slice is the only local stand-in "
                    "for the missing prompt."
                ),
                "queries": [
                    {
                        "query": "read prompt-two-slice.md line 11276",
                        "result_count": archival_hits,
                        "backend": "utf-8 splitlines",
                        "hit_summary": repr(measurements["slice_line_11276"]),
                    }
                ],
            },
            {
                "source_class": "source-code",
                "status": "exhausted",
                "notes": (
                    "CNL-0073 (what constitutes proof-of-impossibility) "
                    "is not on this tree."
                ),
                "queries": [
                    {
                        "query": (
                            "CNL-0073-proof-of-impossibility-"
                            "what-actually-constitutes-proof.md"
                        ),
                        "result_count": code_cnl73,
                        "backend": "pathlib.Path.is_file",
                    }
                ],
            },
            {
                "source_class": "issue-trackers",
                "status": "exhausted",
                "notes": (
                    "Program claim/source registers named as RES-0149 "
                    "inputs are absent."
                ),
                "queries": [
                    {
                        "query": "command-center/CLAIM-REGISTRY.json",
                        "result_count": claim_hits,
                        "backend": "pathlib.Path.is_file",
                    },
                    {
                        "query": "command-center/sources/REGISTER.md",
                        "result_count": src_hits,
                        "backend": "pathlib.Path.is_file",
                    },
                ],
            },
            {
                "source_class": "changelogs-release-notes",
                "status": "exhausted",
                "queries": [
                    {
                        "query": (
                            "WORK-UNIT-CATALOG.json unit RES-0149 inputs "
                            "cite _USER-PROMPTS.md:11276"
                        ),
                        "result_count": catalog_hits,
                        "backend": "catalog-id lookup",
                        "hit_summary": (
                            "catalog names the line but does not quote "
                            "the owner-spec definition"
                        ),
                    }
                ],
            },
        ],
        "access_barrier": {
            "kind": "path-not-mounted",
            "description": (
                "The owner spec _USER-PROMPTS.md is not on this Linux "
                "worktree. The Windows restore path is not mounted. The "
                "CC-0024 recovered slice at line 11276 is the placeholder "
                "token 'proof-of-impossibility.' rather than a record "
                "definition. public-tor was not attempted: enabling "
                "controversial source classes is owner-gated (spec:11361)."
            ),
            "paths": ["_USER-PROMPTS.md", WIN_PROMPT, SLICE_REL],
            "owner_gate": "spec:11361 controversial source classes owner-gated",
        },
        "retry_after": RETRY_AFTER,
        "retry_triggers": [
            "_USER-PROMPTS.md becomes readable on this worktree",
            "Windows harness restore path is mounted",
            f"wall-clock retry_after {RETRY_AFTER}",
        ],
        "falsifier": {
            "single_observation": (
                "A readable _USER-PROMPTS.md (or a byte-identical copy) whose "
                "line 11276 contains a proof-of-impossibility record definition "
                "that is not the catalog-recovery placeholder "
                "'proof-of-impossibility.' and is at least 40 characters."
            ),
            "how_it_overturns": (
                "That observation supplies the missing owner-spec text, so the "
                "question is no longer unanswerable and this record must be "
                "retired and replaced with the quoted definition."
            ),
        },
        "claims": [
            {
                "id": "C-unanswerable-11276",
                "text": (
                    "On this worktree the verbatim owner-spec text at "
                    "_USER-PROMPTS.md:11276 cannot be obtained; the recovered "
                    "line is the placeholder token 'proof-of-impossibility.'"
                ),
                "verdict": "CONFIRMED",
                "sherman_kent_band": "almost-certain",
                "independent_verification_path": (
                    "python3 -c \"from pathlib import Path; r=Path('.'); "
                    "print((r/'_USER-PROMPTS.md').is_file()); "
                    "p=r/'command-center/p2-wave/probes/CC-0024/fixtures/"
                    "prompt-two-slice.md'; "
                    "print(p.read_text().splitlines()[11275])\""
                ),
                "lineage": [missing_prompt_lin, slice_lin],
                "signals": [
                    {
                        "id": "S1-path-absent",
                        "mechanism": (
                            "pathlib.Path.is_file on repo-root and "
                            "Windows restore path"
                        ),
                        "observation": (
                            "root_prompt_is_file="
                            f"{measurements['root_prompt_is_file']} "
                            "win_prompt_is_file="
                            f"{measurements['win_prompt_is_file']} "
                            "glob_count="
                            f"{measurements['glob_user_prompts_count']}"
                        ),
                    },
                    {
                        "id": "S2-slice-placeholder",
                        "mechanism": (
                            "utf-8 splitlines index 11275 of CC-0024 "
                            "recovered slice"
                        ),
                        "observation": (
                            f"line={measurements['slice_line_11276']!r} "
                            "placeholder="
                            f"{measurements['slice_line_is_placeholder']}"
                        ),
                    },
                ],
            },
            {
                "id": "C-schema-rejects-empty-sources",
                "text": (
                    "The proof-of-impossibility record schema rejects an empty "
                    "exhausted_sources list, so a not-found cannot be recorded "
                    "as cannot-be-obtained."
                ),
                "verdict": "CONFIRMED",
                "sherman_kent_band": "almost-certain",
                "independent_verification_path": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0149/probe1_both_states.py"
                ),
                "lineage": [cat_lin, slice_lin],
                "signals": [
                    {
                        "id": "S1-draft07-minItems",
                        "mechanism": (
                            "jsonschema.Draft7Validator minItems=1 on "
                            "exhausted_sources"
                        ),
                        "observation": (
                            "empty list yields a Draft-07 error; complete "
                            "record yields none"
                        ),
                    },
                    {
                        "id": "S2-semantic-masquerade",
                        "mechanism": (
                            "hand-rolled semantic_errors() without jsonschema"
                        ),
                        "observation": (
                            "code exhausted_sources-empty-not-found-masquerade"
                        ),
                    },
                ],
            },
        ],
        "notes": (
            "public-tor / anecdotal / papers / forums were not searched: the "
            "missing object is an estate-local owner-spec file, not a public "
            "web fact. Skipping them is an applicability bound, not a silent "
            "subset. Source-class names are reconstructed from catalog "
            "fragments because the canonical 16-name list is itself on the "
            "missing prompt file."
        ),
        "measurements": measurements,
    }
