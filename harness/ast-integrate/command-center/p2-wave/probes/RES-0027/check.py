"""Independent checkers for RES-0027 claim record vs captured snapshots.

Probe 1 uses source-citation + GitHub API/raw identity.
Probe 2 uses two-rail overclaim, non-adoptable control, and mutants.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0027.json"
SNAP = HERE / "snapshots"
SENTINEL = (
    "SUCCESS:RES-0027 in the receipt AND a block-composition summary citing "
    "source file:line plus one named non-adoptable feature"
)
NON_ADOPTABLE = "Continue Hub uses-slug runtime unrolling"
BLOCK_SCHEMA_SNIPPET = "export const blockSchema = baseConfigYamlSchema.and("
BLOCK_SCHEMA_LINE = 194
MEASURED_TIERS = {"E1", "E2"}
RAIL_FIELDS = (
    "kind",
    "permalink",
    "fetch_timestamp",
    "http_status",
    "sha256",
    "snapshot",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_art(path: Path | None = None) -> dict:
    p = path or ART
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_line(repo: Path, rel: str, line: int, snippet: str) -> str | None:
    path = repo / rel
    if not path.is_file():
        return f"missing {rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return f"{rel}:{line} out of range n={len(lines)}"
    if snippet not in lines[line - 1]:
        return f"{rel}:{line} snippet mismatch got={lines[line - 1]!r}"
    return None


def rail_errors(rail: dict, require_200: bool = True) -> list[str]:
    errs: list[str] = []
    if not isinstance(rail, dict):
        return ["rail-not-object"]
    for field in RAIL_FIELDS:
        if not rail.get(field):
            errs.append(f"rail-missing-{field}")
    kind = str(rail.get("kind") or "")
    if kind not in {"structured-api", "prose-source"}:
        errs.append(f"rail-bad-kind:{kind}")
    status = rail.get("http_status")
    if require_200 and status != 200:
        errs.append(f"rail-http:{status}")
    snap_rel = str(rail.get("snapshot") or "").replace("\\", "/")
    sha = str(rail.get("sha256") or "")
    if snap_rel and sha:
        path = REPO / snap_rel
        if not path.is_file():
            errs.append(f"snapshot-absent:{snap_rel}")
        else:
            live = hashlib.sha256(path.read_bytes()).hexdigest()
            if live != sha:
                errs.append(f"snapshot-sha-mismatch:{snap_rel}")
            size = rail.get("captured_bytes")
            if isinstance(size, int) and size != path.stat().st_size:
                errs.append(f"snapshot-bytes-mismatch:{snap_rel}")
    return errs


def claim_kinds(claim: dict) -> set[str]:
    return {str(r.get("kind")) for r in (claim.get("rails") or []) if isinstance(r, dict)}


def e2_two_rail_errors(claim: dict) -> list[str]:
    cid = str(claim.get("id") or "?")
    errs: list[str] = []
    rails = claim.get("rails") or []
    if not isinstance(rails, list) or len(rails) < 2:
        errs.append(f"{cid}:need-two-rails")
        return errs
    kinds = claim_kinds(claim)
    if "structured-api" not in kinds:
        errs.append(f"{cid}:missing-structured-api-rail")
    if "prose-source" not in kinds:
        errs.append(f"{cid}:missing-prose-source-rail")
    for i, rail in enumerate(rails):
        for e in rail_errors(rail):
            errs.append(f"{cid}:rail[{i}]:{e}")
    if not claim.get("source_lineage"):
        errs.append(f"{cid}:missing-source_lineage")
    return errs


def source_citation_errors(doc: dict) -> list[str]:
    errs: list[str] = []
    summary = doc.get("block_composition_summary") or {}
    if not isinstance(summary, dict):
        return ["block_composition_summary-absent"]
    if int(summary.get("source_line") or 0) != BLOCK_SCHEMA_LINE:
        errs.append("summary-source_line-not-194")
    if str(summary.get("source_file_line") or "") != (
        "packages/config-yaml/src/schemas/index.ts:194"
    ):
        errs.append("summary-source_file_line")
    if BLOCK_SCHEMA_SNIPPET not in str(summary.get("snippet") or ""):
        errs.append("summary-snippet-not-blockSchema")
    snap = "command-center/p2-wave/probes/RES-0027/snapshots/github-raw-block-schema.ts"
    err = resolve_line(REPO, snap, BLOCK_SCHEMA_LINE, BLOCK_SCHEMA_SNIPPET)
    if err:
        errs.append(err)
    named = str(summary.get("named_non_adoptable_feature") or "")
    if named != NON_ADOPTABLE:
        errs.append(f"named-non-adoptable-mismatch:{named!r}")
    why = str(summary.get("non_adoptable_why") or "")
    if "opaque passthrough" not in why.lower() and "opaque-passthrough" not in why.lower():
        errs.append("non-adoptable-why-missing-opaque-passthrough")
    if "plugin_id" not in why:
        errs.append("non-adoptable-why-missing-plugin_id")
    return errs


def github_api_raw_identity_errors() -> list[str]:
    errs: list[str] = []
    pairs = (
        ("github-api-schema.json", "github-raw-block-schema.ts"),
        ("github-api-unroll.json", "github-raw-unroll.ts"),
    )
    for api_name, raw_name in pairs:
        api_path = SNAP / api_name
        raw_path = SNAP / raw_name
        try:
            api = json.loads(api_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errs.append(f"api-unparseable:{api_name}:{type(exc).__name__}")
            continue
        if api.get("encoding") != "base64":
            errs.append(f"api-encoding:{api_name}")
        try:
            decoded = base64.b64decode(api["content"])
        except (KeyError, ValueError, TypeError) as exc:
            errs.append(f"api-decode:{api_name}:{type(exc).__name__}")
            continue
        raw = raw_path.read_bytes()
        if decoded != raw:
            errs.append(f"api-raw-mismatch:{api_name}")
        if int(api.get("size") or -1) != len(raw):
            errs.append(f"api-size-mismatch:{api_name}")
        if "sha" not in api or "html_url" not in api:
            errs.append(f"api-missing-envelope-fields:{api_name}")
    schema = (SNAP / "github-raw-block-schema.ts").read_text(encoding="utf-8")
    for needle in (
        "export const blockSchema",
        "models: z.array(modelSchema).length(1)",
        "mcpServers: z.array(mcpServerSchema).length(1)",
        "prompts: z.array(promptSchema).length(1)",
        "uses: usesSchema",
    ):
        if needle not in schema:
            errs.append(f"schema-missing:{needle}")
    unroll = (SNAP / "github-raw-unroll.ts").read_text(encoding="utf-8")
    for needle in (
        'if ("uses" in unrolledBlock)',
        "const blockConfigYaml = await resolveBlock(",
        "export async function unrollBlocks(",
        "const rawYaml = await registry.getContent(id);",
    ):
        if needle not in unroll:
            errs.append(f"unroll-missing:{needle}")
    return errs


def two_rail_claim_errors(doc: dict) -> list[str]:
    errs: list[str] = []
    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 3:
        return ["claims-too-few"]
    measured = 0
    for claim in claims:
        if not isinstance(claim, dict):
            errs.append("claim-not-object")
            continue
        cid = str(claim.get("id") or "?")
        for field in (
            "id",
            "canonical_mechanism",
            "source_lineage",
            "evidence_tier",
            "confidence_band",
            "settling_probe",
            "freshness_stamp",
            "verdict",
            "strongest_caveat",
        ):
            if not claim.get(field):
                errs.append(f"{cid}:missing-{field}")
        tier = str(claim.get("evidence_tier") or "")
        verdict = str(claim.get("verdict") or "")
        if verdict == "CONFIRMED" and tier in MEASURED_TIERS:
            measured += 1
            errs.extend(e2_two_rail_errors(claim))
        if verdict == "CONFIRMED" and tier == "E3":
            # E3 may not be cited as measured fact.
            if claim.get("citable_as_measured_fact") is True:
                errs.append(f"{cid}:e3-cited-as-measured-fact")
        if verdict == "CONFIRMED" and tier in MEASURED_TIERS:
            if claim.get("citable_as_measured_fact") is not True:
                errs.append(f"{cid}:e2-not-marked-citable")
    if measured < 2:
        errs.append(f"measured-confirmed-too-few:{measured}")
    return errs


def fit_verdict_errors(doc: dict) -> list[str]:
    errs: list[str] = []
    fit = str(doc.get("hub_and_block_better_fit_than_plugin_package") or "")
    if fit not in {"NO", "REFUTED"}:
        errs.append(f"fit-verdict-not-no:{fit!r}")
    answer = str(doc.get("answer") or "").lower()
    if "not a better fit" not in answer and "is not a better fit" not in answer:
        errs.append("answer-missing-not-a-better-fit")
    if NON_ADOPTABLE.lower() not in str(doc.get("block_composition_summary") or "").lower() and (
        NON_ADOPTABLE
        not in json.dumps(doc.get("block_composition_summary") or {}, ensure_ascii=True)
    ):
        errs.append("summary-missing-non-adoptable-name")
    # Overclaim: do not treat live hub as measured.
    blob = json.dumps(doc, ensure_ascii=True)
    if "hub.continue.dev" in blob and '"http_status": 200' in blob:
        # Allowed only if that 200 is not attributed to hub.continue.dev.
        for claim in doc.get("claims") or []:
            for rail in claim.get("rails") or []:
                perm = str(rail.get("permalink") or "") + str(rail.get("requested_url") or "")
                if "hub.continue.dev" in perm and rail.get("http_status") == 200:
                    errs.append("overclaim-hub-http-200")
    return errs


def local_control_errors() -> list[str]:
    errs: list[str] = []
    pairs = (
        (
            "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
            5,
            '"additionalProperties": false',
        ),
        (
            "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
            57,
            '"plugin_id"',
        ),
        (
            "command-center/p2-wave/probes/ARC-0010/emit_design.py",
            247,
            "opaque passthrough / untyped blob field copied into generated output",
        ),
    )
    for rel, line, snippet in pairs:
        err = resolve_line(REPO, rel, line, snippet)
        if err:
            errs.append(err)
    return errs


def sentinel_state_errors(doc: dict) -> list[str]:
    errs: list[str] = []
    text = json.dumps(doc, ensure_ascii=True)
    if SENTINEL not in text:
        errs.append("sentinel-absent-from-artifact")
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errs.append(f"self-declared:{state}")
    if str(doc.get("unit_id") or "") != "RES-0027":
        errs.append("unit_id")
    return errs


def validate_source_citation(doc: dict) -> list[str]:
    return (
        sentinel_state_errors(doc)
        + source_citation_errors(doc)
        + github_api_raw_identity_errors()
        + local_control_errors()
    )


def validate_two_rail(doc: dict) -> list[str]:
    return (
        sentinel_state_errors(doc)
        + two_rail_claim_errors(doc)
        + fit_verdict_errors(doc)
        + source_citation_errors(doc)
    )


def mutant_source_lineage_accepted(doc: dict) -> bool:
    mutant = copy.deepcopy(doc)
    stripped = False
    for claim in mutant.get("claims") or []:
        if (
            claim.get("verdict") == "CONFIRMED"
            and str(claim.get("evidence_tier") or "") in MEASURED_TIERS
            and "source_lineage" in claim
        ):
            del claim["source_lineage"]
            stripped = True
            break
    if not stripped:
        return True
    return not two_rail_claim_errors(mutant)


def mutant_drop_rail_accepted(doc: dict) -> bool:
    mutant = copy.deepcopy(doc)
    dropped = False
    for claim in mutant.get("claims") or []:
        if (
            claim.get("verdict") == "CONFIRMED"
            and str(claim.get("evidence_tier") or "") in MEASURED_TIERS
            and isinstance(claim.get("rails"), list)
            and len(claim["rails"]) >= 2
        ):
            claim["rails"] = claim["rails"][:1]
            dropped = True
            break
    if not dropped:
        return True
    return not two_rail_claim_errors(mutant)


def mutant_drop_non_adoptable_accepted(doc: dict) -> bool:
    mutant = copy.deepcopy(doc)
    summary = mutant.get("block_composition_summary")
    if not isinstance(summary, dict) or "named_non_adoptable_feature" not in summary:
        return True
    del summary["named_non_adoptable_feature"]
    return not source_citation_errors(mutant)
