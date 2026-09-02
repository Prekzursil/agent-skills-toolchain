"""Shared checks for RES-0065 dual-rail claims and file:line mapping."""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0065"
ART_REL = "command-center/research/RES-0065.json"
ART = REPO / ART_REL
CAP = HERE / "captures"
SENTINEL = (
    "SUCCESS:RES-0065 in the receipt AND a mechanism-to-requirement mapping "
    "citing this repo's workflows at file:line"
)
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
USER_AGENT = "RES-0065-probes/1.0 (ast-integrate; dual-rail recheck)"

REQ_IDS = {
    "REQ-BP-STABLE-ID",
    "REQ-BP-TYPED-IO",
    "REQ-BP-CONTENT-DIGEST",
    "REQ-BP-CALL-PARAMS",
}
MECH_IDS = {
    "GHA-REUSABLE-WORKFLOW",
    "GHA-COMPOSITE-ACTION",
    "GHA-SHA-PIN",
}
CONTROL_MECH = "GHA-ENVIRONMENTS-REQUIRED-REVIEWERS"

LIVE_PINNED = [
    "docs-reuse-workflows.md",
    "docs-composite-action.md",
    "docs-secure-use.md",
]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_index() -> dict[str, Any]:
    return json.loads((CAP / "INDEX.json").read_text(encoding="utf-8"))


def load_artifact() -> dict[str, Any]:
    if not ART.is_file() or ART.stat().st_size < 400:
        raise SystemExit(f"FAILED:{UNIT} artifact missing")
    return json.loads(ART.read_text(encoding="utf-8"))


def capture_by_id(index: dict[str, Any], cid: str) -> dict[str, Any]:
    for row in index.get("captures") or []:
        if row.get("id") == cid:
            return row
    raise KeyError(cid)


def verify_local_captures(index: dict[str, Any]) -> None:
    for row in index.get("captures") or []:
        rel = str(row["path"])
        path = REPO / rel
        if not path.is_file():
            raise AssertionError(f"capture missing {rel}")
        raw = path.read_bytes()
        if sha256_bytes(raw) != row["sha256"]:
            raise AssertionError(f"capture sha mismatch {rel}")
        if len(raw) != int(row["bytes"]):
            raise AssertionError(f"capture size mismatch {rel}")


def http_get(url: str, timeout: int = 40) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read() if exc.fp else b""


def parse_file_line(cite: str) -> tuple[str, int]:
    if ":" not in cite:
        raise AssertionError(f"citation missing line: {cite}")
    rel, _, rest = cite.rpartition(":")
    if not rest.isdigit():
        raise AssertionError(f"citation line not int: {cite}")
    return rel, int(rest)


def resolve_citation(cite: str, snippet: str | None = None) -> str:
    rel, line = parse_file_line(cite)
    path = REPO / rel
    if not path.is_file():
        raise AssertionError(f"cited file missing {rel}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        raise AssertionError(f"line oob {cite} n={len(lines)}")
    text = lines[line - 1]
    if snippet and snippet not in text:
        raise AssertionError(f"snippet miss {cite}: {snippet!r} vs {text!r}")
    return text


def rails_ok(claim: dict[str, Any], index: dict[str, Any]) -> None:
    rails = claim.get("rails") or []
    if len(rails) < 2:
        raise AssertionError(f"{claim.get('id')} needs two rails, got {len(rails)}")
    kinds = {r.get("kind") for r in rails}
    if "structured-api" not in kinds or "prose-source" not in kinds:
        raise AssertionError(f"{claim.get('id')} rails kinds {kinds}")
    for rail in rails:
        for key in ("permalink", "fetched_at", "http_status", "sha256", "capture_id"):
            if not rail.get(key):
                raise AssertionError(f"{claim.get('id')} rail missing {key}")
        if int(rail["http_status"]) != 200:
            raise AssertionError(f"{claim.get('id')} rail http {rail['http_status']}")
        cap = capture_by_id(index, str(rail["capture_id"]))
        if cap["sha256"] != rail["sha256"]:
            raise AssertionError(f"{claim.get('id')} rail sha != capture")
        if cap["permalink"] != rail["permalink"]:
            raise AssertionError(f"{claim.get('id')} permalink drift")
        if cap["kind"] != rail["kind"]:
            raise AssertionError(f"{claim.get('id')} kind drift {rail['kind']}")
        body = (REPO / cap["path"]).read_bytes()
        if sha256_bytes(body) != rail["sha256"]:
            raise AssertionError(f"{claim.get('id')} body hash fail")
        token = str(rail.get("must_contain") or "")
        if token:
            text = body.decode("utf-8", errors="replace")
            if token not in text:
                raise AssertionError(f"{claim.get('id')} missing token {token!r}")


def check_mapping(doc: dict[str, Any]) -> list[str]:
    mapping = doc.get("mechanism_to_requirement_mapping") or []
    if not isinstance(mapping, list) or len(mapping) < 4:
        raise AssertionError("mapping too short")
    seen_mech: set[str] = set()
    seen_req: set[str] = set()
    cites: list[str] = []
    control = 0
    for row in mapping:
        mid = str(row.get("mechanism_id") or "")
        seen_mech.add(mid)
        analogue = str(row.get("analogue") or "")
        citations = list(row.get("repo_citations") or [])
        if analogue == "none":
            control += 1
            if citations:
                raise AssertionError(
                    f"control {mid} must not cite a false analogue file:line"
                )
            if row.get("requirement_id") not in (None, ""):
                raise AssertionError(f"control {mid} must not claim a requirement id")
            continue
        rid = str(row.get("requirement_id") or "")
        seen_req.add(rid)
        for extra in row.get("also_satisfies") or []:
            seen_req.add(str(extra))
        if not citations:
            raise AssertionError(f"{mid} missing repo_citations")
        for cite in citations:
            if isinstance(cite, dict):
                loc = str(cite.get("file_line") or "")
                snippet = str(cite.get("snippet") or "") or None
                resolve_citation(loc, snippet)
                cites.append(loc)
            else:
                resolve_citation(str(cite), None)
                cites.append(str(cite))
    missing_m = MECH_IDS - seen_mech
    if missing_m:
        raise AssertionError(f"missing mechanisms {missing_m}")
    missing_r = REQ_IDS - seen_req
    if missing_r:
        raise AssertionError(f"missing requirements {missing_r}")
    if CONTROL_MECH not in seen_mech or control < 1:
        raise AssertionError("control CI mechanism with no analogue missing")
    workflow_cites = [c for c in cites if "/workflows/" in c or "registry.json" in c]
    if len(workflow_cites) < 3:
        raise AssertionError(f"need workflow file:line cites, got {cites}")
    return cites


def check_claims(doc: dict[str, Any], index: dict[str, Any]) -> None:
    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 4:
        raise AssertionError("claims too short")
    confirmed = 0
    refuted = 0
    for claim in claims:
        verdict = str(claim.get("verdict") or "")
        grade = str(claim.get("evidence_grade") or "")
        caveat = str(claim.get("strongest_caveat") or "")
        if not caveat or len(caveat) < 24:
            raise AssertionError(f"{claim.get('id')} missing strongest_caveat")
        if verdict in {"CONFIRMED", "PARTIAL"}:
            if grade not in {"E1", "E2"}:
                raise AssertionError(f"{claim.get('id')} measured fact grade {grade}")
            rails_ok(claim, index)
            confirmed += 1
        elif verdict == "REFUTED":
            refuted += 1
            locus = str(claim.get("defect_locus") or "")
            if locus not in {"DESIGN", "SENTENCE"}:
                raise AssertionError(f"{claim.get('id')} REFUTED needs defect_locus")
        else:
            if grade in {"E1", "E2"}:
                raise AssertionError(f"{claim.get('id')} {verdict} cannot be E1/E2")
    if confirmed < 3:
        raise AssertionError(f"confirmed={confirmed}")
    if refuted < 1:
        raise AssertionError("need at least one REFUTED overclaim")


def check_artifact_core(doc: dict[str, Any]) -> str:
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        raise AssertionError("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        raise AssertionError(f"self-declared {st}")
    if str(doc.get("unit_id") or "") != UNIT:
        raise AssertionError("unit_id")
    return text


def live_recheck_pinned_markdown(index: dict[str, Any]) -> dict[str, Any]:
    by_name = {Path(r["path"]).name: r for r in index["captures"]}
    out = {}
    for name in LIVE_PINNED:
        row = by_name[name]
        status, body = http_get(str(row["permalink"]))
        got = sha256_bytes(body)
        out[name] = {
            "http_status": status,
            "sha256": got,
            "match": status == 200 and got == row["sha256"],
        }
        if status != 200:
            raise AssertionError(f"live {name} http {status}")
        if got != row["sha256"]:
            raise AssertionError(
                f"live {name} sha drift (commit-pin should be immutable)"
            )
    return out


def live_recheck_schemas() -> dict[str, Any]:
    """SchemaStore bytes can move; require live JSON + tokens, not exact hash."""
    checks = {
        "https://www.schemastore.org/github-workflow.json": [
            "reusableWorkflowCallJob",
            "Using the commit SHA is the safest for stability and security",
            "workflow_call",
        ],
        "https://www.schemastore.org/github-action.json": [
            '"const": "composite"',
            "runs-composite",
        ],
    }
    out: dict[str, Any] = {}
    for url, tokens in checks.items():
        status, body = http_get(url)
        if status != 200:
            raise AssertionError(f"live schema {url} http {status}")
        text = body.decode("utf-8", errors="replace")
        json.loads(text)
        missing = [t for t in tokens if t not in text]
        if missing:
            raise AssertionError(f"live schema {url} missing {missing}")
        out[url] = {"http_status": status, "bytes": len(body), "tokens_ok": True}
    return out


def mutant_drop_rail(doc: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(doc))
    for claim in clone["claims"]:
        if claim.get("verdict") == "CONFIRMED" and len(claim.get("rails") or []) >= 2:
            claim["rails"] = claim["rails"][:1]
            return clone
    raise AssertionError("no CONFIRMED dual-rail claim to mutate")


def mutant_false_mapping(doc: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(doc))
    for row in clone["mechanism_to_requirement_mapping"]:
        if row.get("analogue") != "none":
            cites = row.get("repo_citations") or []
            if cites and isinstance(cites[0], dict):
                cites[0]["file_line"] = "command-center/no-such-workflow.yml:1"
            else:
                row["repo_citations"] = ["command-center/no-such-workflow.yml:1"]
            return clone
    raise AssertionError("no mapping row to mutate")


FORBIDDEN_CI_KEYS = (
    "environment",
    "permissions",
    "concurrency",
    "runs-on",
    "GITHUB_TOKEN",
)


def cited_workflow_json_paths(doc: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for row in doc.get("mechanism_to_requirement_mapping") or []:
        for cite in row.get("repo_citations") or []:
            loc = cite.get("file_line") if isinstance(cite, dict) else str(cite)
            rel, _ = parse_file_line(str(loc))
            if rel.endswith(".json") and rel not in seen:
                seen.add(rel)
                paths.append(REPO / rel)
    return paths


def assert_no_ci_platform_fields(doc: dict[str, Any]) -> list[str]:
    scanned = []
    for path in cited_workflow_json_paths(doc):
        text = path.read_text(encoding="utf-8")
        scanned.append(str(path.relative_to(REPO)))
        for key in FORBIDDEN_CI_KEYS:
            if key in text:
                raise AssertionError(f"{path.name} unexpectedly contains {key}")
    if len(scanned) < 2:
        raise AssertionError(f"too few cited json files {scanned}")
    return scanned
