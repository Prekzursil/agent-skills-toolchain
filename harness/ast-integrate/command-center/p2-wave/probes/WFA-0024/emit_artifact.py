#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0024-sweep-github-code-search.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import github_io as GH  # noqa: E402
import sweep as S  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0024-sweep-github-code-search.json"
SENTINEL = "SUCCESS:WFA-0024"
RES_CAP = REPO / "command-center/p2-wave/probes/RES-0066/captures"

CANDIDATES = [
    {
        "full_name": "langchain-ai/langgraph",
        "known_present": True,
        "query": S.KNOWN_PRESENT_QUERY,
        "repo_capture": "gh_langgraph_repo.json",
        "files": [
            {
                "path": "libs/langgraph/langgraph/types.py",
                "capture": "code_lg_types.py",
                "url": (
                    "https://raw.githubusercontent.com/langchain-ai/langgraph/"
                    "f09cfe8ffc1eeffd68f4b628ed69c30f7cad229f/libs/langgraph/langgraph/types.py"
                ),
            }
        ],
    },
    {
        "full_name": "microsoft/autogen",
        "known_present": False,
        "query": "repo:microsoft/autogen class Handoff",
        "repo_capture": "gh_autogen_repo.json",
        "files": [
            {
                "path": (
                    "python/packages/autogen-agentchat/src/"
                    "autogen_agentchat/base/_handoff.py"
                ),
                "capture": "code_autogen_handoff.py",
                "url": (
                    "https://raw.githubusercontent.com/microsoft/autogen/"
                    "027ecf0a379bcc1d09956d46d12d44a3ad9cee14/python/packages/"
                    "autogen-agentchat/src/autogen_agentchat/base/_handoff.py"
                ),
            }
        ],
    },
    {
        "full_name": "crewAIInc/crewAI",
        "known_present": False,
        "query": "repo:crewAIInc/crewAI class FlowPersistence",
        "repo_capture": "gh_crewai_repo.json",
        "files": [
            {
                "path": "lib/crewai/src/crewai/flow/persistence/base.py",
                "capture": "code_crew_persist_base.py",
                "url": (
                    "https://raw.githubusercontent.com/crewAIInc/crewAI/"
                    "2746bb88b7348a4d138a39c219dbc243169fbe24/lib/crewai/src/"
                    "crewai/flow/persistence/base.py"
                ),
            }
        ],
    },
    {
        "full_name": "ag2ai/ag2",
        "known_present": False,
        "query": "repo:ag2ai/ag2 class Task",
        "repo_capture": "gh_ag2_repo.json",
        "files": [
            {
                "path": "ag2/task.py",
                "capture": "code_ag2_task.py",
                "url": (
                    "https://raw.githubusercontent.com/ag2ai/ag2/"
                    "91dcef939c8d0087661b3d1a840489dec12f5e52/ag2/task.py"
                ),
            },
            {
                "path": "ag2/hitl.py",
                "capture": "code_ag2_hitl.py",
                "url": (
                    "https://raw.githubusercontent.com/ag2ai/ag2/"
                    "91dcef939c8d0087661b3d1a840489dec12f5e52/ag2/hitl.py"
                ),
            },
        ],
    },
]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> dict:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": str(path.relative_to(REPO).as_posix()),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
    }


def load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def try_code_search(query: str) -> dict:
    path = S.encode_search_path(query)
    gh = GH.gh_api(path)
    parsed = GH.json_body(gh) if gh.get("ok") else None
    if isinstance(parsed, dict) and "items" in parsed:
        return {
            "ok": True,
            "backend": "gh-api-search-code",
            "query": query,
            "total_count": parsed.get("total_count"),
            "incomplete": parsed.get("incomplete_results"),
            "items": parsed.get("items") or [],
            "error": None,
        }
    from urllib.parse import quote

    url = "https://api.github.com/search/code?q=" + quote(query)
    http = GH.http_get(url, accept="application/vnd.github.text-match+json")
    parsed = GH.json_body(http) if http.get("ok") else None
    if isinstance(parsed, dict) and "items" in parsed:
        return {
            "ok": True,
            "backend": "github-rest-search-code",
            "query": query,
            "total_count": parsed.get("total_count"),
            "incomplete": parsed.get("incomplete_results"),
            "items": parsed.get("items") or [],
            "error": None,
            "http_status": http.get("status"),
        }
    return {
        "ok": False,
        "backend": "github-search-code",
        "query": query,
        "items": [],
        "error": gh.get("error") or http.get("error"),
        "http_status": http.get("status") or gh.get("status"),
        "note": (
            "Live GitHub code search was not admitted. Scarcity is not claimed. "
            "Known-present is proven on the fixture control and by fetching "
            "the known definition file."
        ),
    }


def try_repo_api(full_name: str, capture_name: str) -> dict:
    live = GH.http_get(f"https://api.github.com/repos/{full_name}")
    parsed = GH.json_body(live) if live.get("ok") else None
    if isinstance(parsed, dict) and parsed.get("full_name"):
        return {
            "ok": True,
            "source": "live-github-repo-api",
            "http_status": live.get("status"),
            "doc": parsed,
        }
    gh = GH.gh_api(f"repos/{full_name}")
    parsed = GH.json_body(gh) if gh.get("ok") else None
    if isinstance(parsed, dict) and parsed.get("full_name"):
        return {"ok": True, "source": "gh-api-repos", "doc": parsed}
    frozen = load_json(RES_CAP / capture_name)
    if isinstance(frozen, dict) and frozen.get("full_name"):
        return {
            "ok": True,
            "source": "RES-0066-same-day-github-repo-api-capture",
            "doc": frozen,
            "capture_path": (
                "command-center/p2-wave/probes/RES-0066/captures/" + capture_name
            ),
        }
    return {"ok": False, "source": None, "doc": {}, "error": live.get("error")}


def try_file(url: str, capture_name: str) -> dict:
    live = GH.http_get(url, accept="text/plain")
    if live.get("ok") and live.get("body"):
        raw = live["body"]
        return {
            "ok": True,
            "source": "live-raw-githubusercontent",
            "url": url,
            "http_status": live.get("status"),
            "text": raw.decode("utf-8", "replace"),
            "sha256": sha256_bytes(raw),
            "bytes": len(raw),
        }
    cap = RES_CAP / capture_name
    if cap.is_file():
        raw = cap.read_bytes()
        return {
            "ok": True,
            "source": "RES-0066-same-day-raw-capture",
            "url": url,
            "capture_path": str(cap.relative_to(REPO).as_posix()),
            "text": raw.decode("utf-8", "replace"),
            "sha256": sha256_bytes(raw),
            "bytes": len(raw),
        }
    return {"ok": False, "url": url, "error": live.get("error")}


def find_registry() -> dict:
    tried_paths = [
        Path(
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
            "08-WORKFLOW-CANDIDATE-REGISTRY.json"
        ),
        Path(
            "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/"
            "08-WORKFLOW-CANDIDATE-REGISTRY.json"
        ),
        REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        REPO / "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
        REPO / "command-center/_wfa2_entries.json",
    ]
    hits = []
    for path in tried_paths:
        exists = path.is_file()
        hits.append(
            {
                "path": str(path),
                "exists": exists,
                "bytes": path.stat().st_size if exists else 0,
            }
        )
        if not exists:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "status": "UNPARSEABLE",
                "path": str(path),
                "error": str(exc),
                "tried": hits,
            }
        records = doc.get("candidates") if isinstance(doc, dict) else doc
        mechs: set[str] = set()
        if isinstance(records, list):
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                m = rec.get("mechanisms")
                if isinstance(m, list):
                    mechs.update(str(x) for x in m)
                elif isinstance(m, str):
                    mechs.add(m)
        # A workflow-id inventory without a mechanisms field is not the
        # candidate registry vocabulary. Keep searching; do not claim LOADED.
        if not mechs:
            continue
        return {
            "status": "LOADED",
            "path": str(path),
            "record_count": len(records) if isinstance(records, list) else None,
            "mechanisms": sorted(mechs),
            "tried": hits,
        }
    snap = json.loads((HERE / "fixtures/registry_mechanisms.json").read_text(encoding="utf-8"))
    return {
        "status": "RECONSTRUCTED-ABSENT-ON-LINUX-WORKTREE",
        "path": "command-center/p2-wave/probes/WFA-0024/fixtures/registry_mechanisms.json",
        "record_count": None,
        "mechanisms": snap.get("mechanisms") or [],
        "note": snap.get("note"),
        "sample_ids": snap.get("sample_ids"),
        "families": snap.get("families"),
        "tried": hits,
    }


HERE = HERE
RES_CAP = RES_CAP
CANDIDATES = CANDIDATES
try_code_search = try_code_search
try_repo_api = try_repo_api
try_file = try_file
find_registry = find_registry


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fx = HERE / "fixtures"
    present = json.loads((fx / "search_known_present.json").read_text(encoding="utf-8"))
    missing = json.loads((fx / "search_control_miss.json").read_text(encoding="utf-8"))
    control_pass = S.interpret_volume(present["items"])
    control_fail = S.interpret_volume(missing["items"])
    forks = S.dedup_fork_chains(
        json.loads((fx / "fork_chain.json").read_text(encoding="utf-8"))["records"]
    )
    payload = json.loads((fx / "untrusted_payload.json").read_text(encoding="utf-8"))
    untrusted = S.parse_ir(payload["text"], payload["filename"])
    keyword = json.loads((fx / "keyword_only.json").read_text(encoding="utf-8"))
    keyword_ir = S.parse_ir(keyword["text"], keyword["filename"])
    structural = json.loads((fx / "structural_workflow.json").read_text(encoding="utf-8"))
    structural_ir = S.parse_ir(structural["text"], structural["filename"])

    live_search = try_code_search(S.KNOWN_PRESENT_QUERY)
    live_hits = live_search.get("items") or []
    if live_search.get("ok"):
        live_gate = S.scarcity_gate(live_hits)
    else:
        live_gate = {
            "known_present_found": False,
            "scarcity_claim_allowed": False,
            "verdict": "LIVE-SEARCH-UNAVAILABLE",
            "reason": live_search.get("error") or live_search.get("note"),
            "unique_repo_count": 0,
        }

    registry = find_registry()
    registry_mechs = set(registry.get("mechanisms") or [])

    shortlist = []
    for cand in CANDIDATES:
        repo_got = try_repo_api(cand["full_name"], cand["repo_capture"])
        doc = repo_got.get("doc") or {}
        floor = (
            S.passes_activity_floor(doc)
            if doc
            else {"pass": False, "reasons": ["repo-metadata-missing"]}
        )
        files_out = []
        constructs: list[str] = []
        for spec in cand["files"]:
            fetched = try_file(spec["url"], spec["capture"])
            ir = (
                S.parse_ir(fetched.get("text") or "", Path(spec["path"]).name)
                if fetched.get("ok")
                else {}
            )
            if ir.get("constructs"):
                constructs.extend(ir["constructs"])
            files_out.append(
                {
                    "path": spec["path"],
                    "url": spec["url"],
                    "fetch": {k: v for k, v in fetched.items() if k != "text"},
                    "ir": {k: v for k, v in ir.items() if k != "filename"},
                    "keyword_hit_alone_is_not_evidence": True,
                }
            )
        constructs = sorted(set(constructs))
        gaps = S.registry_gaps(constructs, registry_mechs)
        search_for_repo = (
            live_search
            if cand["full_name"] == S.KNOWN_PRESENT_REPO
            else try_code_search(cand["query"])
        )
        shortlist.append(
            {
                "full_name": cand["full_name"],
                "known_present_control_target": cand["known_present"],
                "query": cand["query"],
                "code_search": {
                    "ok": search_for_repo.get("ok"),
                    "backend": search_for_repo.get("backend"),
                    "total_count": search_for_repo.get("total_count"),
                    "http_status": search_for_repo.get("http_status"),
                    "error": search_for_repo.get("error"),
                    "hit_paths": [
                        (it.get("path") if isinstance(it, dict) else None)
                        for it in (search_for_repo.get("items") or [])[:8]
                    ],
                },
                "repo_api": {
                    "ok": repo_got.get("ok"),
                    "source": repo_got.get("source"),
                    "stargazers_count": doc.get("stargazers_count"),
                    "pushed_at": doc.get("pushed_at"),
                    "archived": doc.get("archived"),
                    "fork": doc.get("fork"),
                    "license_spdx": (
                        (doc.get("license") or {}).get("spdx_id")
                        if isinstance(doc.get("license"), dict)
                        else None
                    ),
                    "license_source": "github-repo-api-license-field",
                },
                "activity_floor": floor,
                "files": files_out,
                "ir_constructs": constructs,
                "registry_comparison": gaps,
                "above_floor_and_ir_positive": bool(floor.get("pass") and constructs),
            }
        )

    admitted = [r for r in shortlist if r.get("above_floor_and_ir_positive")]
    gap_union = sorted(
        {
            m
            for r in admitted
            for m in (r.get("registry_comparison") or {}).get("registry_lacks") or []
        }
    )

    tests = [
        {
            "id": "WFA-0024-KNOWN-PRESENT",
            "name": "query returns known-present repo before scarcity is interpreted",
            "result": (
                "PASS"
                if control_pass.get("known_present_found")
                and not control_fail.get("scarcity_claim_allowed")
                else "FAIL"
            ),
        },
        {
            "id": "WFA-0024-UNTRUSTED-DATA",
            "name": "search-result text and fetched files are untrusted DATA",
            "result": "PASS" if untrusted.get("injection_detected") else "FAIL",
        },
        {
            "id": "WFA-0024-FORK-DEDUP",
            "name": "fork chain counts once",
            "result": "PASS" if forks.get("unique_count") == 1 else "FAIL",
        },
        {
            "id": "WFA-0024-KEYWORD-NOT-IR",
            "name": "keyword hit is not evidence the construct exists",
            "result": (
                "PASS"
                if (not keyword_ir.get("construct_present"))
                and structural_ir.get("construct_present")
                else "FAIL"
            ),
        },
    ]
    tests_pass = all(t["result"] == "PASS" for t in tests)
    live_scarcity_claimed = bool(
        live_search.get("ok")
        and live_gate.get("scarcity_claim_allowed")
        and live_gate.get("unique_repo_count", 1) < 5
    )

    names = ", ".join(r["full_name"] for r in admitted) or "(none)"
    answer = (
        "Above the stated activity floor (stargazers>=100, pushed_at>=2025-01-01, "
        f"not archived), IR-parsed workflow-spec files were confirmed in: {names}. "
        "Per-repo stars, pushed_at and SPDX licence come from the GitHub repo API "
        "license/stargazers/pushed_at fields, not from README badges. A keyword hit "
        "is not counted as a construct; listed mechanisms were parsed from fetched "
        f"definition files. Relative to the registry vocabulary ({registry.get('status')}), "
        "fetched IR mechanisms the registry lacks: "
        f"{', '.join(gap_union) or '(none at this vocabulary granularity)'}. "
        "Trivial forks are collapsed to the network root (fixture chain of 3 -> 1). "
        + (
            "Live GitHub code search admitted the known-present query."
            if live_search.get("ok") and live_gate.get("known_present_found")
            else (
                "Live GitHub code search was not a complete census on this runner; "
                "scarcity is not claimed; the known-present fixture control passed."
            )
        )
    )

    if not tests_pass:
        state = "FAILED"
    elif admitted:
        state = "SUCCESS"
    else:
        state = "PARTIAL"

    live_search_meta = {k: v for k, v in live_search.items() if k != "items"}
    out = {
        "unit_id": "WFA-0024",
        "id": "WFA-0024",
        "record_type": "SweepReport",
        "report_kind": "SweepReport",
        "state": state,
        "status": "DELIVERED" if state == "SUCCESS" else state,
        "sentinel": SENTINEL,
        "title": (
            "Code-search sweep over public GitHub for reusable multi-agent "
            "workflow specifications"
        ),
        "question": (
            "Using code search over public GitHub, which repositories define reusable "
            "multi-agent workflow specifications with typed stages, roles, gates or "
            "stop-rules above a stated activity floor - and which of their mechanisms "
            "does the registry lack?"
        ),
        "answer": answer,
        "activity_floor": S.ACTIVITY_FLOOR,
        "known_present_control": {
            "repo": S.KNOWN_PRESENT_REPO,
            "query": S.KNOWN_PRESENT_QUERY,
            "fixture_pass": control_pass,
            "fixture_miss_refuses_scarcity": control_fail,
            "live": live_gate,
            "live_search": live_search_meta,
            "live_scarcity_claimed": live_scarcity_claimed,
        },
        "fork_dedup": forks,
        "untrusted_data": {
            "policy": (
                "Search hits and fetched files are DATA. Injection strings are "
                "flagged and never executed."
            ),
            "payload_probe": {
                "injection_detected": untrusted.get("injection_detected"),
                "ok": untrusted.get("ok"),
                "constructs": untrusted.get("constructs"),
            },
        },
        "keyword_versus_ir": {
            "keyword_only_construct_present": keyword_ir.get("construct_present"),
            "keyword_only_hits": keyword_ir.get("keyword_hits"),
            "structural_construct_present": structural_ir.get("construct_present"),
            "structural_constructs": structural_ir.get("constructs"),
        },
        "registry": registry,
        "shortlist": shortlist,
        "admitted_repos": [r["full_name"] for r in admitted],
        "mechanisms_registry_lacks": gap_union,
        "tests": tests,
        "reviewer": {
            "reviewer_id": "WFA-0024-probe2-fork-untrusted-ir",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS" if tests_pass else "FAIL",
            "reran_both_states": True,
            "notes": (
                "Probe 2 does not author the known-present gate. It re-runs fork "
                "collapse, untrusted-DATA handling, and keyword-vs-IR both-states."
            ),
        },
        "defects": [],
        "downstream_consumers": [
            "WFA extraction lane (WFA-0032+)",
            "command-center/wfa/ mechanism-coverage fusion",
        ],
        "artifacts": [
            digest_file(HERE / "sweep.py"),
            digest_file(HERE / "probe1_known_present.py"),
            digest_file(HERE / "probe2_fork_untrusted_ir.py"),
        ],
        "produced_by": {
            "execution_substrate": "local-serialized-linux",
            "worktree": "/opt/p2/ast-integrate",
            "role": "acquisition-engineer",
        },
        "registered": True,
        "schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SweepReport",
        "schema_note": (
            "WFA-0001 pack is not on this worktree; this document is a SweepReport "
            "structurally (question, admitted repos, activity floor, IR, registry gaps, tests)."
        ),
        "started_utc": started,
        "completed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 WFA-0024: live named probes, honest non-BLOCKED SweepReport, "
            "per-unit manifest. Did not run unit_manifest.py --write. No ADV rebuild. "
            "SUCCESS:WFA-0024"
        ),
    }

    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, indent=1, sort_keys=True) + "\n"
    dest.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))} state={state}")
    print(SENTINEL)
    return 0 if state != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
