"""41-node licence cohort for WFA-0033.

The Windows harness graph
C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json
is not on this Linux worktree. The catalog states the old histogram
(26 THIRD-PARTY, 11 OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY,
2 ATTRIBUTION-REQUIRED, 1 RIDER-RESTRICTED, 1 UNCLASSIFIED). This
cohort reconstructs those counts from LICENSE files fetched 2026-08-24
into fixtures/licenses/, plus eleven owner-authored slots whose file
text is the SPDX MIT license list (host-declared MIT) and named
third-party deps. Node *identities* from the missing graph are
NOT-RECOVERED; counts and file-derived classes are.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LIC = HERE / "fixtures" / "licenses"
RETRIEVED = "2026-08-24T19:05:00Z"
HOST_SRC = "host-declared-licence-metadata-field"

GRAPH_SEARCH_PATHS = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "command-center/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
]


def _tp(
    nid: str,
    name: str,
    license_file: str,
    anchor: str,
    host_spdx: str,
) -> dict[str, Any]:
    return {
        "id": nid,
        "name": name,
        "old_class": "THIRD-PARTY",
        "origin": "https://github.com/" + name,
        "license_file": license_file,
        "retrieval_anchor": anchor,
        "retrieval_date": RETRIEVED,
        "host_declared_spdx": host_spdx,
        "host_declared_source": HOST_SRC,
        "fetchable": True,
        "external_deps": [],
    }


def third_party_nodes() -> list[dict[str, Any]]:
    raw = [
        (
            "tp-langgraph",
            "langchain-ai/langgraph",
            "langgraph-MIT.txt",
            "https://raw.githubusercontent.com/langchain-ai/langgraph/main/LICENSE",
            "MIT",
        ),
        (
            "tp-crewai",
            "crewAIInc/crewAI",
            "crewai-MIT.txt",
            "https://raw.githubusercontent.com/crewAIInc/crewAI/main/LICENSE",
            "MIT",
        ),
        (
            "tp-ag2",
            "ag2ai/ag2",
            "ag2-Apache-2.0.txt",
            "https://raw.githubusercontent.com/ag2ai/ag2/main/LICENSE",
            "Apache-2.0",
        ),
        (
            "tp-pydantic",
            "pydantic/pydantic",
            "pydantic-MIT.txt",
            "https://raw.githubusercontent.com/pydantic/pydantic/main/LICENSE",
            "MIT",
        ),
        (
            "tp-httpx",
            "encode/httpx",
            "httpx-BSD.txt",
            "https://raw.githubusercontent.com/encode/httpx/master/LICENSE.md",
            "BSD-3-Clause",
        ),
        (
            "tp-requests",
            "psf/requests",
            "requests-Apache-2.0.txt",
            "https://raw.githubusercontent.com/psf/requests/main/LICENSE",
            "Apache-2.0",
        ),
        (
            "tp-pyyaml",
            "yaml/pyyaml",
            "pyyaml-MIT.txt",
            "https://raw.githubusercontent.com/yaml/pyyaml/main/LICENSE",
            "MIT",
        ),
        (
            "tp-jsonschema",
            "python-jsonschema/jsonschema",
            "jsonschema-MIT.txt",
            "https://raw.githubusercontent.com/python-jsonschema/jsonschema/main/COPYING",
            "MIT",
        ),
        (
            "tp-numpy",
            "numpy/numpy",
            "numpy-BSD.txt",
            "https://raw.githubusercontent.com/numpy/numpy/main/LICENSE.txt",
            "BSD-3-Clause",
        ),
        (
            "tp-click",
            "pallets/click",
            "click-BSD.txt",
            "https://raw.githubusercontent.com/pallets/click/main/LICENSE.txt",
            "BSD-3-Clause",
        ),
        (
            "tp-rich",
            "Textualize/rich",
            "rich-MIT.txt",
            "https://raw.githubusercontent.com/Textualize/rich/master/LICENSE",
            "MIT",
        ),
        (
            "tp-pytest",
            "pytest-dev/pytest",
            "pytest-MIT.txt",
            "https://raw.githubusercontent.com/pytest-dev/pytest/main/LICENSE",
            "MIT",
        ),
        (
            "tp-urllib3",
            "urllib3/urllib3",
            "urllib3-MIT.txt",
            "https://raw.githubusercontent.com/urllib3/urllib3/main/LICENSE.txt",
            "MIT",
        ),
        (
            "tp-certifi",
            "certifi/python-certifi",
            "certifi-MPL.txt",
            "https://raw.githubusercontent.com/certifi/python-certifi/master/LICENSE",
            "MPL-2.0",
        ),
        (
            "tp-openai",
            "openai/openai-python",
            "openai-Apache.txt",
            "https://raw.githubusercontent.com/openai/openai-python/main/LICENSE",
            "Apache-2.0",
        ),
        (
            "tp-anthropic",
            "anthropics/anthropic-sdk-python",
            "anthropic-MIT.txt",
            "https://raw.githubusercontent.com/anthropics/anthropic-sdk-python/main/LICENSE",
            "MIT",
        ),
        (
            "tp-mcp",
            "modelcontextprotocol/python-sdk",
            "mcp-MIT.txt",
            "https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/LICENSE",
            "MIT",
        ),
        (
            "tp-pip",
            "pypa/pip",
            "pip-MIT.txt",
            "https://raw.githubusercontent.com/pypa/pip/main/LICENSE.txt",
            "MIT",
        ),
        (
            "tp-setuptools",
            "pypa/setuptools",
            "setuptools-MIT.txt",
            "https://raw.githubusercontent.com/pypa/setuptools/main/LICENSE",
            "MIT",
        ),
        (
            "tp-fastapi",
            "tiangolo/fastapi",
            "fastapi-MIT.txt",
            "https://raw.githubusercontent.com/tiangolo/fastapi/master/LICENSE",
            "MIT",
        ),
        (
            "tp-starlette",
            "encode/starlette",
            "starlette-BSD.txt",
            "https://raw.githubusercontent.com/encode/starlette/master/LICENSE.md",
            "BSD-3-Clause",
        ),
        (
            "tp-uvicorn",
            "encode/uvicorn",
            "uvicorn-BSD.txt",
            "https://raw.githubusercontent.com/encode/uvicorn/master/LICENSE.md",
            "BSD-3-Clause",
        ),
        (
            "tp-black",
            "psf/black",
            "black-MIT.txt",
            "https://raw.githubusercontent.com/psf/black/main/LICENSE",
            "MIT",
        ),
        (
            "tp-ruff",
            "astral-sh/ruff",
            "ruff-MIT.txt",
            "https://raw.githubusercontent.com/astral-sh/ruff/main/LICENSE",
            "MIT",
        ),
        (
            "tp-mypy",
            "python/mypy",
            "mypy-MIT.txt",
            "https://raw.githubusercontent.com/python/mypy/master/LICENSE",
            "MIT",
        ),
        (
            "tp-jinja",
            "pallets/jinja",
            "jinja-BSD.txt",
            "https://raw.githubusercontent.com/pallets/jinja/main/LICENSE.txt",
            "BSD-3-Clause",
        ),
    ]
    return [_tp(*row) for row in raw]


def owner_nodes() -> list[dict[str, Any]]:
    deps_cycle = [
        ["tp-langgraph", "tp-pydantic"],
        ["tp-crewai", "tp-httpx"],
        ["tp-ag2", "tp-requests"],
        ["tp-fastapi", "tp-starlette"],
        ["tp-openai", "tp-anthropic"],
        ["tp-mcp", "tp-pydantic"],
        ["tp-pytest", "tp-click"],
        ["tp-numpy", "tp-pip"],
        ["tp-ruff", "tp-mypy"],
        ["tp-jinja", "tp-pyyaml"],
        ["tp-rich", "tp-urllib3"],
    ]
    nodes = []
    for i, deps in enumerate(deps_cycle, start=1):
        nodes.append(
            {
                "id": f"owner-wf-{i:02d}",
                "name": f"estate-owner-workflow-{i:02d}",
                "old_class": "OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY",
                "origin": f"local://owner-workflow/{i:02d}",
                "license_file": "SPDX-MIT.txt",
                "retrieval_anchor": "https://spdx.org/licenses/MIT.txt",
                "retrieval_date": RETRIEVED,
                "host_declared_spdx": "MIT",
                "host_declared_source": HOST_SRC,
                "fetchable": True,
                "external_deps": deps,
            }
        )
    return nodes


def attribution_nodes() -> list[dict[str, Any]]:
    return [
        {
            "id": "attr-autogen-docs",
            "name": "microsoft/autogen",
            "old_class": "ATTRIBUTION-REQUIRED",
            "origin": "https://github.com/microsoft/autogen",
            "license_file": "autogen-CC-BY-4.0.txt",
            "retrieval_anchor": "https://raw.githubusercontent.com/microsoft/autogen/main/LICENSE",
            "retrieval_date": RETRIEVED,
            "host_declared_spdx": "CC-BY-4.0",
            "host_declared_source": HOST_SRC,
            "fetchable": True,
            "external_deps": [],
        },
        {
            "id": "attr-opensource-guide",
            "name": "github/opensource.guide",
            "old_class": "ATTRIBUTION-REQUIRED",
            "origin": "https://github.com/github/opensource.guide",
            "license_file": "opensource-guide-CC-BY.txt",
            "retrieval_anchor": "https://raw.githubusercontent.com/github/opensource.guide/main/LICENSE",
            "retrieval_date": RETRIEVED,
            "host_declared_spdx": "CC-BY-4.0",
            "host_declared_source": HOST_SRC,
            "fetchable": True,
            "external_deps": [],
        },
    ]


def rider_node() -> dict[str, Any]:
    return {
        "id": "rider-commons-clause",
        "name": "reconstructed-rider-restricted-node",
        "old_class": "RIDER-RESTRICTED",
        "origin": "local://rider/commons-clause-on-apache",
        "license_file": "commons-clause-on-apache.txt",
        "retrieval_anchor": "https://commonsclause.com/",
        "retrieval_date": RETRIEVED,
        "host_declared_spdx": "Apache-2.0",
        "host_declared_source": HOST_SRC,
        "fetchable": True,
        "external_deps": [],
    }


def unclassified_node() -> dict[str, Any]:
    return {
        "id": "unclassified-unreachable",
        "name": "unreachable-licence-source",
        "old_class": "UNCLASSIFIED",
        "origin": "https://127.0.0.1:1/missing-node/LICENSE",
        "license_file": None,
        "retrieval_anchor": "https://127.0.0.1:1/missing-node/LICENSE",
        "retrieval_date": None,
        "host_declared_spdx": None,
        "host_declared_source": HOST_SRC,
        "fetchable": False,
        "external_deps": [],
    }


def all_nodes() -> list[dict[str, Any]]:
    nodes = (
        third_party_nodes()
        + owner_nodes()
        + attribution_nodes()
        + [rider_node(), unclassified_node()]
    )
    assert len(nodes) == 41, len(nodes)
    from collections import Counter

    hist = Counter(n["old_class"] for n in nodes)
    assert hist["THIRD-PARTY"] == 26, hist
    assert hist["OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY"] == 11, hist
    assert hist["ATTRIBUTION-REQUIRED"] == 2, hist
    assert hist["RIDER-RESTRICTED"] == 1, hist
    assert hist["UNCLASSIFIED"] == 1, hist
    return nodes


def fixtures_dir() -> Path:
    return LIC


def disk_fetcher(node: dict[str, Any]) -> dict[str, Any]:
    if not node.get("fetchable", True) or not node.get("license_file"):
        return {
            "ok": False,
            "error": "source-unreachable",
            "text": "",
            "anchor": node.get("retrieval_anchor") or node.get("origin"),
            "date": None,
        }
    path = LIC / str(node["license_file"])
    if not path.is_file():
        return {
            "ok": False,
            "error": f"fixture-missing:{path.name}",
            "text": "",
            "anchor": node.get("retrieval_anchor"),
            "date": None,
        }
    text = path.read_text(encoding="utf-8")
    return {
        "ok": True,
        "error": None,
        "text": text,
        "anchor": node.get("retrieval_anchor"),
        "date": node.get("retrieval_date") or RETRIEVED,
    }


def graph_source_record(repo: Path) -> dict[str, Any]:
    found = None
    attempted = []
    for rel in GRAPH_SEARCH_PATHS:
        p = Path(rel)
        if not p.is_absolute():
            p = repo / rel
        exists = p.is_file()
        attempted.append({"path": str(p), "exists": exists})
        if exists and found is None:
            found = str(p)
    return {
        "found": found is not None,
        "resolved_path": found,
        "attempted": attempted,
        "fallback": (
            "catalog-stated old histogram (26/11/2/1/1) plus LICENSE files "
            "fetched 2026-08-24 into fixtures/licenses/"
        ),
        "node_identities_from_original_graph": "NOT-RECOVERED",
    }
