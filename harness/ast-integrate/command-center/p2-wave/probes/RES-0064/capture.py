#!/usr/bin/env python3
"""Fetch two-rail evidence for RES-0064. No tokens printed."""
from __future__ import annotations

import hashlib
import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "captures" / "raw"
INDEX = HERE / "captures" / "index.json"
UA = "ast-integrate-RES-0064-research/1.0 (+local-worktree; no-auth)"

RAILS = [
    {
        "id": "api-cwl-v12",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/common-workflow-language/cwl-v1.2",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "raw-cwl-clt-yml",
        "kind": "structured-api",
        "permalink": (
            "https://raw.githubusercontent.com/common-workflow-language/"
            "cwl-v1.2/1.2.1/CommandLineTool.yml"
        ),
        "accept": "text/plain",
    },
    {
        "id": "prose-cwl-clt-html",
        "kind": "prose-source",
        "permalink": "https://www.commonwl.org/v1.2/CommandLineTool.html",
        "accept": "text/html",
    },
    {
        "id": "api-cwlprov",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/common-workflow-language/cwlprov",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "prose-cwlprov-readme",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/common-workflow-language/"
            "cwlprov/main/README.md"
        ),
        "accept": "text/plain",
    },
    {
        "id": "api-openwdl",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/openwdl/wdl",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "raw-wdl-spec-11",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/openwdl/wdl/main/versions/1.1/SPEC.md"
        ),
        "accept": "text/plain",
    },
    {
        "id": "raw-wdl-spec-12",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/openwdl/wdl/main/versions/1.2/SPEC.md"
        ),
        "accept": "text/plain",
    },
    {
        "id": "api-nextflow",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/nextflow-io/nextflow",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "prose-nextflow-process",
        "kind": "prose-source",
        "permalink": "https://www.nextflow.io/docs/latest/process.html",
        "accept": "text/html",
    },
    {
        "id": "prose-nextflow-tracing",
        "kind": "prose-source",
        "permalink": "https://www.nextflow.io/docs/latest/tracing.html",
        "accept": "text/html",
    },
    {
        "id": "api-nf-prov",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/nextflow-io/nf-prov",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "prose-nf-prov-readme",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/nextflow-io/nf-prov/master/README.md"
        ),
        "accept": "text/plain",
    },
    {
        "id": "api-snakemake",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/snakemake/snakemake",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "prose-snakemake-rules",
        "kind": "prose-source",
        "permalink": (
            "https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html"
        ),
        "accept": "text/html",
    },
    {
        "id": "prose-snakemake-report",
        "kind": "prose-source",
        "permalink": (
            "https://snakemake.readthedocs.io/en/stable/snakefiles/reporting.html"
        ),
        "accept": "text/html",
    },
    {
        "id": "api-ro-crate",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/ResearchObject/ro-crate",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "prose-rocrate-1-1",
        "kind": "prose-source",
        "permalink": "https://www.researchobject.org/ro-crate/1.1/",
        "accept": "text/html",
    },
    {
        "id": "prose-rocrate-provenance",
        "kind": "prose-source",
        "permalink": (
            "https://www.researchobject.org/ro-crate/1.1/provenance.html"
        ),
        "accept": "text/html",
    },
    {
        "id": "api-workflow-run-crate",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/ResearchObject/workflow-run-crate",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "prose-wfrun-crate",
        "kind": "prose-source",
        "permalink": "https://www.researchobject.org/workflow-run-crate/",
        "accept": "text/html",
    },
]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def fetch(url: str, accept: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": accept},
        method="GET",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=45) as resp:
            body = resp.read()
            final = str(resp.geturl())
            return int(resp.status), body, final
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return int(exc.code), body, url
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        msg = f"FETCH-ERROR:{type(exc).__name__}:{exc}".encode("utf-8")
        return 0, msg, url


def ext_for(kind: str, permalink: str) -> str:
    if "api.github.com" in permalink:
        return ".json"
    lower = permalink.lower()
    if lower.endswith(".md"):
        return ".md"
    if lower.endswith(".yml") or lower.endswith(".yaml"):
        return ".yml"
    if kind == "structured-api":
        return ".json"
    return ".html"


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    failures = []
    for spec in RAILS:
        status, body, final = fetch(spec["permalink"], spec["accept"])
        rel = f"captures/raw/{spec['id']}{ext_for(spec['kind'], spec['permalink'])}"
        path = HERE / rel
        path.write_bytes(body)
        digest = sha256_bytes(body)
        row = {
            "id": spec["id"],
            "kind": spec["kind"],
            "permalink": spec["permalink"],
            "final_url": final,
            "http_status": status,
            "fetch_timestamp": ts,
            "sha256": digest,
            "bytes": len(body.replace(b"\r\n", b"\n")),
            "path": f"command-center/p2-wave/probes/RES-0064/{rel}",
        }
        rows.append(row)
        mark = "OK" if status == 200 and body else "FAIL"
        print(
            f"{mark} {status} {spec['id']} sha256={digest[:12]} bytes={len(body)}"
        )
        if status != 200 or not body:
            failures.append(spec["id"])
    INDEX.write_text(
        json.dumps(
            {
                "unit_id": "RES-0064",
                "fetched_at": ts,
                "user_agent": UA,
                "auth": "none",
                "rails": rows,
                "failed_ids": failures,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    # Hard fail only if we lack a language pair. Individual 404s are recorded.
    needed_groups = {
        "cwl": ["api-cwl-v12", "raw-cwl-clt-yml", "prose-cwl-clt-html"],
        "wdl": ["api-openwdl", "raw-wdl-spec-11", "raw-wdl-spec-12"],
        "nextflow": ["api-nextflow", "prose-nextflow-process"],
        "snakemake": ["api-snakemake", "prose-snakemake-rules"],
        "rocrate": ["api-ro-crate", "prose-rocrate-1-1", "prose-rocrate-provenance"],
    }
    ok_ids = {r["id"] for r in rows if r["http_status"] == 200 and r["bytes"] > 0}
    missing_groups = [
        name
        for name, ids in needed_groups.items()
        if not any(i in ok_ids for i in ids)
    ]
    if missing_groups:
        print(f"FAILED:capture missing groups {missing_groups} failed={failures}")
        return 1
    print(f"SUCCESS:RES-0064-capture n={len(rows)} failed={failures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
