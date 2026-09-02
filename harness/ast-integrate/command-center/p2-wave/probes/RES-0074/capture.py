#!/usr/bin/env python3
"""Fetch RES-0074 evidence rails. Structured API vs prose HTML/markdown.

Does not print credentials. Network is for capture only; probes re-hash stored bytes.
"""
from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"
UA = "ast-integrate-RES-0074-research/1.0 (Linux worktree evidence capture)"

# (id, rail_kind, format_id, role, url)
SOURCES = [
    # CWL — spec prose + GitHub Contents API (structured)
    (
        "cwl-spec-workflow-html",
        "prose",
        "CWL-1.2",
        "spec",
        "https://www.commonwl.org/v1.2/Workflow.html",
    ),
    (
        "cwltool-pack-api",
        "api",
        "CWL-1.2",
        "writer-reader-cwltool",
        "https://api.github.com/repos/common-workflow-language/cwltool/contents/cwltool/pack.py",
    ),
    (
        "cwltool-readme-raw",
        "prose",
        "CWL-1.2",
        "reader-writer-docs",
        "https://raw.githubusercontent.com/common-workflow-language/cwltool/main/README.rst",
    ),
    (
        "toil-cwl-api",
        "api",
        "CWL-1.2",
        "reader-toil",
        "https://api.github.com/repos/DataBiosphere/toil/contents/src/toil/cwl/cwltoil.py",
    ),
    (
        "cromwell-readme-raw",
        "prose",
        "CWL-1.2",
        "reader-cromwell",
        "https://raw.githubusercontent.com/broadinstitute/cromwell/develop/README.md",
    ),
    (
        "gxformat2-readme",
        "prose",
        "CWL-1.2",
        "writer-galaxy-export",
        "https://raw.githubusercontent.com/galaxyproject/gxformat2/master/README.rst",
    ),
    # WDL
    (
        "openwdl-readme-api",
        "api",
        "WDL",
        "spec-repo",
        "https://api.github.com/repos/openwdl/wdl/readme",
    ),
    (
        "miniwdl-readme-raw",
        "prose",
        "WDL",
        "reader-miniwdl",
        "https://raw.githubusercontent.com/chanzuckerberg/miniwdl/main/README.md",
    ),
    (
        "cromwell-wdl-language-raw",
        "prose",
        "WDL",
        "reader-cromwell-wdl",
        "https://raw.githubusercontent.com/broadinstitute/cromwell/develop/docs/tutorials/FiveMinuteIntro.md",
    ),
    # BPMN 2.0 — two independent engines + OMG/docs
    (
        "camunda-bpmn-docs",
        "prose",
        "BPMN-2.0",
        "camunda-prose",
        "https://docs.camunda.org/manual/7.22/reference/bpmn20/",
    ),
    (
        "camunda-bpmn-parse-api",
        "api",
        "BPMN-2.0",
        "camunda-parser",
        "https://api.github.com/repos/camunda/camunda-bpm-platform/contents/engine/src/main/java/org/camunda/bpm/engine/impl/bpmn/parser/BpmnParse.java",
    ),
    (
        "flowable-bpmn-userguide",
        "prose",
        "BPMN-2.0",
        "flowable-prose",
        "https://www.flowable.com/open-source/docs/bpmn/ch07-BPMN-Introduction",
    ),
    (
        "flowable-bpmn-parse-api",
        "api",
        "BPMN-2.0",
        "flowable-parser",
        "https://api.github.com/repos/flowable/flowable-engine/contents/modules/flowable-bpmn-converter/src/main/java/org/flowable/bpmn/converter/BpmnXMLConverter.java",
    ),
    # n8n
    (
        "n8n-export-docs",
        "prose",
        "n8n-JSON",
        "export-import-docs",
        "https://docs.n8n.io/workflows/export-import/",
    ),
    (
        "n8n-workflow-api",
        "api",
        "n8n-JSON",
        "workflow-type",
        "https://api.github.com/repos/n8n-io/n8n/contents/packages/workflow/src/interfaces.ts",
    ),
    # GitHub Actions (one-way control)
    (
        "gha-workflow-syntax",
        "prose",
        "GHA-YAML",
        "syntax-docs",
        "https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions",
    ),
    (
        "gha-runner-readme-api",
        "api",
        "GHA-YAML",
        "runner-repo",
        "https://api.github.com/repos/actions/runner/readme",
    ),
    # Nextflow (one-way)
    (
        "nextflow-readme-raw",
        "prose",
        "Nextflow-DSL2",
        "readme",
        "https://raw.githubusercontent.com/nextflow-io/nextflow/master/README.md",
    ),
    (
        "nextflow-readme-api",
        "api",
        "Nextflow-DSL2",
        "repo-api",
        "https://api.github.com/repos/nextflow-io/nextflow/readme",
    ),
    # Airflow DAG (one-way)
    (
        "airflow-tutorial-raw",
        "prose",
        "Airflow-DAG",
        "tutorial",
        "https://raw.githubusercontent.com/apache/airflow/main/docs/apache-airflow/tutorial.md",
    ),
    (
        "airflow-readme-api",
        "api",
        "Airflow-DAG",
        "repo-api",
        "https://api.github.com/repos/apache/airflow/readme",
    ),
]


def fetch(url: str) -> tuple[int, str, bytes, dict]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/vnd.github+json, text/html, text/plain, */*",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=45) as resp:
            body = resp.read()
            final = resp.geturl()
            status = resp.status
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return status, final, body, headers
    except urllib.error.HTTPError as e:
        body = e.read() if e.fp else b""
        headers = {k.lower(): v for k, v in (e.headers.items() if e.headers else [])}
        return int(e.code), url, body, headers


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    index = {
        "unit_id": "RES-0074",
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "captures": [],
    }
    fail = 0
    for cid, kind, fmt, role, url in SOURCES:
        time.sleep(0.15)
        status, final, body, headers = fetch(url)
        sha = hashlib.sha256(body).hexdigest()
        body_path = CAP / f"{cid}.body"
        hdr_path = CAP / f"{cid}.headers"
        meta = {
            "id": cid,
            "rail_kind": kind,
            "format_id": fmt,
            "role": role,
            "request_url": url,
            "final_url": final,
            "permalink": final,
            "http_status": status,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sha256": sha,
            "bytes": len(body),
            "content_type": headers.get("content-type", ""),
            "body_path": f"command-center/p2-wave/probes/RES-0074/captures/{cid}.body",
            "ok": 200 <= status < 300 and len(body) > 0,
        }
        body_path.write_bytes(body)
        hdr_lines = [f"HTTP {status}", f"final-url: {final}"]
        for k, v in headers.items():
            if k in {"set-cookie", "authorization"}:
                continue
            hdr_lines.append(f"{k}: {v}")
        hdr_path.write_text("\n".join(hdr_lines) + "\n", encoding="utf-8")
        index["captures"].append(meta)
        mark = "OK" if meta["ok"] else "FAIL"
        print(f"{mark} {status} {cid} bytes={len(body)} sha256={sha[:12]}...")
        if not meta["ok"]:
            fail += 1
    (HERE / "capture-index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote capture-index.json fail={fail}/{len(SOURCES)}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
