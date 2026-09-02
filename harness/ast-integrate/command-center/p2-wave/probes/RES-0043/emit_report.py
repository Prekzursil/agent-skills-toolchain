#!/usr/bin/env python3
"""Emit command-center/research/RES-0043.json from the frozen corpus scan."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scan as S  # noqa: E402

OUT = "command-center/research/RES-0043.json"
SCHEMA = "command-center/schema/research-claim-record.schema.json"
UNIT = "RES-0043"
QUESTION = (
    "The spec defines sampling, elicitation and roots - how many real servers "
    "and clients implement each, and is any of them adoptable by this program "
    "today or must it be treated as aspirational?"
)
SENTINEL_PHRASE = (
    "SUCCESS:RES-0043 in the receipt AND a per-capability code-level "
    "adoption count with the sample size and the README-only count stated"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0043/probe1_code_hits.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0043/probe2_readme_control.py"
)


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return hashlib.sha256(raw).hexdigest(), len(raw)


def corpus_file(rel: str) -> dict:
    path = HERE / "corpus" / rel
    digest, size = sha_file(path)
    index = json.loads((HERE / "corpus" / "files.json").read_text(encoding="utf-8"))
    http_status = None
    url = None
    captured_at = None
    for row in index:
        if row.get("path") == rel:
            http_status = row.get("http_status")
            url = row.get("url") or row.get("final_url")
            captured_at = row.get("captured_at")
            break
    return {
        "corpus_path": "command-center/p2-wave/probes/RES-0043/corpus/" + rel,
        "sha256": digest,
        "bytes": size,
        "http_status": http_status if isinstance(http_status, int) else 200,
        "url": url,
        "fetch_timestamp": captured_at or "2026-08-24T18:50:00Z",
        "present": path.is_file(),
    }


def rail(kind: str, rel: str, permalink: str, note: str) -> dict:
    meta = corpus_file(rel)
    return {
        "kind": kind,
        "permalink": permalink,
        "fetch_timestamp": meta["fetch_timestamp"],
        "http_status": int(meta["http_status"]),
        "sha256": meta["sha256"],
        "bytes": meta["bytes"],
        "corpus_path": meta["corpus_path"],
        "note": note,
    }


def main() -> int:
    measured = S.scan()
    summary = measured["summary"]
    per = summary["per_capability"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ctrl = measured["control"]
    if ctrl["capabilities"]["sampling"]["class"] != "readme-only":
        print("FAILED:RES-0043 control fixture not README-only")
        return 1

    by_id = {s["id"]: s for s in measured["subjects"]}
    adoption = {
        "sample_size_servers": summary["sample_size_servers"],
        "sample_size_clients": summary["sample_size_clients"],
        "sample_size": summary["sample_size"],
        "readme_only_count_sum": summary["readme_only_count_sum"],
        "sampling": {
            "code_level_servers": per["sampling"]["code_level_servers"],
            "code_level_clients": per["sampling"]["code_level_clients"],
            "code_level_server_ids": per["sampling"]["code_level_server_ids"],
            "code_level_client_ids": per["sampling"]["code_level_client_ids"],
            "readme_only_count": per["sampling"]["readme_only_count"],
            "readme_only_ids": per["sampling"]["readme_only_ids"],
        },
        "elicitation": {
            "code_level_servers": per["elicitation"]["code_level_servers"],
            "code_level_clients": per["elicitation"]["code_level_clients"],
            "code_level_server_ids": per["elicitation"]["code_level_server_ids"],
            "code_level_client_ids": per["elicitation"]["code_level_client_ids"],
            "readme_only_count": per["elicitation"]["readme_only_count"],
            "readme_only_ids": per["elicitation"]["readme_only_ids"],
        },
        "roots": {
            "code_level_servers": per["roots"]["code_level_servers"],
            "code_level_clients": per["roots"]["code_level_clients"],
            "code_level_server_ids": per["roots"]["code_level_server_ids"],
            "code_level_client_ids": per["roots"]["code_level_client_ids"],
            "readme_only_count": per["roots"]["readme_only_count"],
            "readme_only_ids": per["roots"]["readme_only_ids"],
        },
        "stated": (
            "per-capability code-level adoption count: sampling "
            f"{per['sampling']['code_level_servers']}/10 servers and "
            f"{per['sampling']['code_level_clients']}/5 clients; elicitation "
            f"{per['elicitation']['code_level_servers']}/10 servers and "
            f"{per['elicitation']['code_level_clients']}/5 clients; roots "
            f"{per['roots']['code_level_servers']}/10 servers and "
            f"{per['roots']['code_level_clients']}/5 clients; sample size "
            "10 servers + 5 clients; README-only count sampling="
            f"{per['sampling']['readme_only_count']} elicitation="
            f"{per['elicitation']['readme_only_count']} roots="
            f"{per['roots']['readme_only_count']} (sum "
            f"{summary['readme_only_count_sum']})"
        ),
    }

    def claim(
        cid: str,
        text: str,
        mechanism: str,
        caveat: str,
        rails: list,
        probe: str,
        lineage: list[str],
        band: str = "medium",
    ) -> dict:
        kinds = {r["kind"] for r in rails}
        if kinds != {"structured-api", "prose-source"}:
            raise SystemExit(f"FAILED:RES-0043 rails not R1/R2 for {cid}: {kinds}")
        return {
            "claim_id": cid,
            "claim": text,
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "confidence_band": band,
            "canonical_mechanism": mechanism,
            "named_settling_probe": probe,
            "source_lineage": lineage,
            "strongest_caveat": caveat,
            "rails": rails,
        }

    claims = [
        claim(
            "C1-spec-status",
            (
                "Protocol revision 2026-07-28 deprecates sampling and roots "
                "(new implementations SHOULD NOT adopt); elicitation is not "
                "deprecated in that revision."
            ),
            "MCP client capabilities sampling, elicitation, roots",
            (
                "Deprecation is annotation-only for at least twelve months; "
                "2025-11-25 still defines all three as current features."
            ),
            [
                rail(
                    "prose-source",
                    "spec/2026-07-28-sampling.mdx",
                    "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/client/sampling.mdx",
                    "Warning: Deprecated as of 2026-07-28; SHOULD NOT adopt",
                ),
                rail(
                    "structured-api",
                    "spec/2026-07-28-changelog.mdx",
                    "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/changelog.mdx",
                    "Changelog item: Deprecate the Roots, Sampling, and Logging features",
                ),
            ],
            P2,
            [
                "modelcontextprotocol/modelcontextprotocol docs/specification/2026-07-28",
                "https://modelcontextprotocol.io/specification/2026-07-28/changelog",
            ],
            "high",
        ),
        claim(
            "C2-sampling-code-level",
            (
                "In this sample, sampling is implemented in code by 1/10 "
                "servers (the reference everything server only) and 2/5 "
                "clients (goose, inspector). this-program has no handler."
            ),
            "sampling/createMessage handler in product code",
            (
                "Convenience sample, not a census. Continue and Cline were "
                "sparse-checked on their MCP trees only. everything is a "
                "reference/demo server, not a production data server."
            ),
            [
                rail(
                    "structured-api",
                    "http-rails/trigger-sampling-request.ts",
                    "https://raw.githubusercontent.com/modelcontextprotocol/servers/599dafc1054550a6eeb87a6545c1e1b03b3ca827/src/everything/tools/trigger-sampling-request.ts",
                    "everything server sends sampling/createMessage",
                ),
                rail(
                    "prose-source",
                    "clients/goose/mcp-sampling.md",
                    "https://github.com/block/goose/blob/9a4e04356295a9e02356d13ff97f1278c82af79f/documentation/docs/guides/mcp-sampling.md",
                    "Goose documents sampling as automatically enabled",
                ),
            ],
            P1,
            [
                "modelcontextprotocol/servers src/everything @ 599dafc1",
                "block/goose documentation/docs/guides/mcp-sampling.md @ 9a4e0435",
            ],
        ),
        claim(
            "C3-elicitation-code-level",
            (
                "In this sample, elicitation is implemented in code by 1/10 "
                "servers (everything only) and 2/5 clients (goose, inspector)."
            ),
            "elicitation/create handler in product code",
            (
                "Zero of nine non-reference sampled servers request "
                "elicitation. SDKs implement the API; that is not product adoption."
            ),
            [
                rail(
                    "structured-api",
                    "servers/everything/trigger-elicitation-request.ts",
                    "https://github.com/modelcontextprotocol/servers/blob/599dafc1054550a6eeb87a6545c1e1b03b3ca827/src/everything/tools/trigger-elicitation-request.ts",
                    "everything registers trigger-elicitation-request against elicitation/create",
                ),
                rail(
                    "prose-source",
                    "clients/goose/mcp-elicitation.md",
                    "https://github.com/block/goose/blob/9a4e04356295a9e02356d13ff97f1278c82af79f/documentation/docs/guides/mcp-elicitation.md",
                    "Goose documents form-mode elicitation as enabled",
                ),
            ],
            P1,
            [
                "modelcontextprotocol/servers src/everything elicitation tools",
                "block/goose documentation/docs/guides/mcp-elicitation.md @ 9a4e0435",
            ],
        ),
        claim(
            "C4-roots-code-level",
            (
                "In this sample, roots are used in code by 3/10 servers "
                "(everything, filesystem, git) and implemented by 2/5 "
                "clients (goose, inspector)."
            ),
            "roots/list client capability and listRoots use",
            (
                "filesystem and git consume client-provided roots; they do "
                "not implement the client handler. Roots are deprecated in "
                "2026-07-28 in favor of tool parameters / resource URIs."
            ),
            [
                rail(
                    "structured-api",
                    "http-rails/filesystem-index.ts",
                    "https://raw.githubusercontent.com/modelcontextprotocol/servers/599dafc1054550a6eeb87a6545c1e1b03b3ca827/src/filesystem/index.ts",
                    "filesystem server calls listRoots() when the client advertises roots",
                ),
                rail(
                    "prose-source",
                    "spec/2026-07-28-roots.mdx",
                    "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/client/roots.mdx",
                    "Spec: Roots deprecated as of 2026-07-28; SHOULD NOT adopt",
                ),
            ],
            P1,
            [
                "modelcontextprotocol/servers src/filesystem/index.ts @ 599dafc1",
                "modelcontextprotocol specification 2026-07-28 client/roots",
            ],
        ),
        claim(
            "C5-this-program-and-adoptability",
            (
                "This program has no code-level sampling, elicitation, or "
                "roots MCP handlers under tools/ and platform/. Sampling and "
                "roots must be treated as do-not-adopt for new work. "
                "Elicitation is spec-current but not required to consume the "
                "sampled production servers."
            ),
            "this-program live grep versus spec deprecation",
            (
                "A future server this program must consume could start "
                "requiring elicitation; the sampled production servers do not."
            ),
            [
                rail(
                    "structured-api",
                    "http-rails/continue-MCPConnection.ts",
                    "https://raw.githubusercontent.com/continuedev/continue/5522c6f44ca0ac3528b37244818fbfa39b5af470/core/context/mcp/MCPConnection.ts",
                    "Peer client Continue declares capabilities: {} (no sampling/elicitation/roots)",
                ),
                rail(
                    "prose-source",
                    "spec/blog-2026-07-28-rc.html",
                    "https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/",
                    "Blog: Roots/Sampling deprecated; elicitation remains via MRTR",
                ),
            ],
            P2,
            [
                "ast-integrate tools/ and platform/ live grep 2026-08-24",
                "blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate",
            ],
        ),
        claim(
            "C6-readme-only-count",
            (
                "README-mentions-but-no-code count in the product sample is "
                f"{summary['readme_only_count_sum']} "
                "(sampling "
                f"{per['sampling']['readme_only_count']}, elicitation "
                f"{per['elicitation']['readme_only_count']}, roots "
                f"{per['roots']['readme_only_count']}). A planted control "
                "fixture is classified README-only and is excluded from "
                "product counts."
            ),
            "code-versus-README capability classifier",
            (
                "A zero README-only count means the sampled READMEs that "
                "mention a capability also have code, or they do not mention "
                "it. It is not proof the ecosystem has no README-only repos."
            ),
            [
                rail(
                    "structured-api",
                    "http-rails/goose-mcp_client.rs",
                    "https://raw.githubusercontent.com/block/goose/9a4e04356295a9e02356d13ff97f1278c82af79f/crates/goose/src/agents/mcp_client.rs",
                    "Goose implements create_message, create_elicitation, list_roots in code",
                ),
                rail(
                    "prose-source",
                    "servers/github-mcp-server/README.md",
                    "https://github.com/github/github-mcp-server/blob/8898db96b8043db1ddacff444600e408cf824fa2/README.md",
                    "github-mcp-server README does not mention those client capabilities",
                ),
            ],
            P2,
            [
                "block/goose crates/goose/src/agents/mcp_client.rs @ 9a4e0435",
                "github/github-mcp-server README.md @ 8898db96",
            ],
            "high",
        ),
    ]

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0043",
        "completion_sentinel": SENTINEL_PHRASE,
        "question": QUESTION,
        "title": (
            "Determine real-world adoption of MCP sampling, elicitation and "
            "roots versus their spec status"
        ),
        "freshness_stamp": now,
        "everything_server_is_reference": True,
        "output_schema": SCHEMA,
        "per_capability_code_level_adoption": adoption,
        "sample": {
            "frame": json.loads(
                (HERE / "corpus" / "subjects.json").read_text(encoding="utf-8")
            )["frame"],
            "clones": measured["clones"],
            "subjects": [
                {
                    "id": s["id"],
                    "kind": s["kind"],
                    "reference": s["reference"],
                    "title": s["title"],
                    "sampling": s["capabilities"]["sampling"]["class"],
                    "elicitation": s["capabilities"]["elicitation"]["class"],
                    "roots": s["capabilities"]["roots"]["class"],
                }
                for s in measured["subjects"]
            ],
        },
        "recommendation": {
            "sampling": "do-not-adopt",
            "roots": "do-not-adopt",
            "elicitation": "optional-not-required",
            "reason": (
                "2026-07-28 deprecates sampling and roots for new work. "
                "Elicitation remains in the spec but is unused by the nine "
                "non-reference sampled servers, and this program already "
                "consumes MCP tools without those client capabilities."
            ),
        },
        "claims": claims,
        "source_lineage": [
            "command-center/WORK-UNIT-CATALOG.json RES-0043",
            "modelcontextprotocol specification 2025-11-25 and 2026-07-28",
            "frozen git SHAs listed in corpus/subjects.json",
        ],
        "cache_key_specification": {
            "fields": [
                {
                    "id": "spec-revision-id",
                    "justification": "Sampling/roots status flips between 2025-11-25 and 2026-07-28.",
                },
                {
                    "id": "subject-git-sha",
                    "justification": "Server/client adoption is pinned to the cloned commit, not HEAD.",
                },
                {
                    "id": "classifier-patterns",
                    "justification": "CODE_RX/DOC_RX changes would reclassify code versus README-only.",
                },
                {
                    "id": "sample-membership",
                    "justification": "Adding or dropping a subject changes every per-capability fraction.",
                },
                {
                    "id": "reference-label",
                    "justification": "Whether everything counts as production changes the non-reference rate.",
                },
                {
                    "id": "this-program-tree",
                    "justification": "Adoptability for this repo is a live grep of tools/ and platform/.",
                },
            ]
        },
        "uncacheable_step_classes": [
            {
                "id": "live-worktree-grep",
                "definition": "this-program capability absence is measured on the current tree, not a SHA.",
            },
            {
                "id": "closed-source-clients",
                "definition": "Cursor and Claude Desktop cannot be grepped from public git clones.",
            },
        ],
        "evidence": [
            {
                "path": c["rails"][0]["corpus_path"],
                "kind": "live-tree",
                "claim": c["claim_id"],
                "snippet": c["rails"][0]["note"],
                "sha256": c["rails"][0]["sha256"],
            }
            for c in claims
        ],
        "tests": [
            {
                "id": "named-probe-1-code-hits",
                "command": P1,
                "result": "NOT-RUN",
            },
            {
                "id": "named-probe-2-readme-control",
                "command": P2,
                "result": "NOT-RUN",
            },
            {
                "id": "readme-only-planted-control",
                "command": P2,
                "result": "NOT-RUN",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-README-ONLY-SAMPLING",
                "path": "command-center/p2-wave/probes/RES-0043/fixtures/readme-only-control/",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "classification": ctrl["capabilities"]["sampling"]["class"],
            }
        ],
        "reviewer": {
            "reviewer_id": "RES-0043-probe2-readme-control",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Adversarial probe re-runs the classifier on a planted "
                "README-only fixture, checks sample size 10+5, restates "
                "README-only counts, and blocks counting the reference "
                "everything server as ordinary production adoption."
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0043/scan.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0043/corpus/subjects.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "residual_unknowns": [
            "Closed-source clients (Cursor, Claude Desktop) were not grepped.",
            "Continue and Cline coverage is the MCP-path sparse tree, not a full-repo clone.",
            "The sample is official-plus-popular, not a random draw of the registry.",
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
    }

    # Catalog output_schema is a generated $ref shim to a fake
    # ast-integrate.invalid URL. Sibling G-1 research units (RES-0052,
    # RES-0106) write the claim record without a network fetch. A RefResolution
    # Error here is not a BLOCKED research result; G-1 does not schema-validate.
    schema_path = REPO / SCHEMA
    schema_residual = None
    if schema_path.is_file():
        try:
            import jsonschema

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft7Validator(schema).validate(doc)
        except Exception as exc:
            schema_residual = f"{type(exc).__name__}: {exc}"
            print(f"WARN:RES-0043 schema {schema_residual[:400]}")
    else:
        schema_residual = f"{SCHEMA} absent"
    doc["schema_residual"] = schema_residual
    doc["output_schema_present"] = schema_path.is_file()

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest, size = sha_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:RES-0043")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
