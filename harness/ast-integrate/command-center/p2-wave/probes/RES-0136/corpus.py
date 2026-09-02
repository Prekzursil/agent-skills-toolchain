"""Candidate licence corpus for RES-0136."""
from __future__ import annotations

import json
from pathlib import Path

from extractor import FIXTURES, classify_path, load_spdx_mit

HERE = Path(__file__).resolve().parent


def lineage() -> dict:
    return json.loads((FIXTURES / "lineage.json").read_text(encoding="utf-8"))


def corpus_rows() -> list[dict]:
    spdx = load_spdx_mit()
    meta = {row["id"]: row for row in lineage()["files"]}
    specs = [
        {
            "id": "mcp_agent_mail",
            "role": "in-estate-named-example",
            "expect_osi_rider": True,
            "expect_non_osi_licence": False,
            "distribution_modes": ["invoking-local-socket", "optional-vendoring"],
        },
        {
            "id": "jsonschema",
            "role": "negative-control-plain-osi",
            "expect_osi_rider": False,
            "expect_non_osi_licence": False,
            "distribution_modes": ["pip-runtime-dependency"],
        },
        {
            "id": "spdx_MIT",
            "role": "osi-template-control",
            "expect_osi_rider": False,
            "expect_non_osi_licence": False,
            "distribution_modes": ["template-only"],
        },
        {
            "id": "llama3",
            "role": "planned-council-model-cnl-0005",
            "expect_osi_rider": False,
            "expect_non_osi_licence": True,
            "distribution_modes": ["invoking-hosted-or-local-weights"],
        },
    ]
    decoy_path = FIXTURES / "decoy-prose.txt"
    decoy = classify_path(decoy_path, spdx)
    decoy.update(
        {
            "id": "decoy_prose",
            "role": "prose-decoy",
            "expect_osi_rider": False,
            "expect_non_osi_licence": False,
            "distribution_modes": ["not-a-dependency"],
            "filename": decoy_path.name,
            "source_lineage": {
                "resolved_url": (
                    "file:command-center/p2-wave/probes/RES-0136/fixtures/decoy-prose.txt"
                ),
                "human_url": None,
                "upstream_repo_path": "fixtures/decoy-prose.txt",
                "fetch_timestamp_utc": lineage()["fetched_at_utc"],
                "sha256": decoy["sha256"],
                "bytes": decoy["bytes"],
            },
        }
    )
    rows = []
    for spec in specs:
        info = meta[spec["id"]]
        path = FIXTURES / info["filename"]
        got = classify_path(path, spdx)
        got.update(spec)
        got["filename"] = info["filename"]
        got["source_lineage"] = {
            "resolved_url": info["resolved_url"],
            "human_url": info["human_url"],
            "upstream_repo_path": info["upstream_repo_path"],
            "fetch_timestamp_utc": info["fetch_timestamp_utc"],
            "sha256": info["sha256"],
            "bytes": info["bytes"],
        }
        if got["sha256"] != info["sha256"]:
            raise RuntimeError(f"sha256 drift {spec['id']}")
        rows.append(got)
    rows.append(decoy)
    return rows
