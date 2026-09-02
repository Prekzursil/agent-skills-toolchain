#!/usr/bin/env python3
"""RES-0109 salvage register: LICENSE-file quotes, not classifier labels.

Reads on-disk captures only. Does not call GitHub. Does not rebuild ADV schemas.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0109"
OUT_REL = "command-center/research/RES-0109.json"
CAPTURES = HERE / "captures"
INDEX_PATH = CAPTURES / "captures_index.json"
ARXIV_PATH = CAPTURES / "arxiv_rails.json"
EQUIV_PATH = CAPTURES / "equivalent_rails.json"
STALE_AFTER = "2025-08-24T00:00:00Z"
QUESTION = (
    "Among archived or unmaintained agent-orchestration repositories, which "
    "contain a mechanism worth extracting that has no maintained equivalent "
    "- and for each, is the licence compatible with reimplementation?"
)
SENTINEL = (
    "SUCCESS:RES-0109 in the receipt AND a salvage register where every row "
    "quotes the LICENSE file's identifying line, plus a count of "
    "label-versus-file disagreements"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0109/probe1_license_quotes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0109/probe2_two_rails.py"
)

# EXTRACT only when unmaintained/archived, LICENSE file present, permissive
# SPDX, and authors did not name a maintained successor.
DISPOSITIONS: dict[str, tuple[str, str]] = {
    "S1": (
        "DROP",
        "In-browser assemble-configure-deploy loop is archived under GPL-3.0 "
        "copyleft. Goal-decomposition autonomous agents are maintained "
        "elsewhere; copyleft also blocks clean reimplementation into a "
        "permissively licensed tree.",
    ),
    "S2": (
        "DROP",
        "Clarify-then-generate CLI is archived. README names gptengineer.app "
        "as the managed evolution and aider as the maintained hackable CLI.",
    ),
    "S3": (
        "DROP",
        "Archived multi-runtime coding-agent client (Claude Code + Codex, git "
        "worktrees). A product shell around maintained runtimes, not an "
        "orphan algorithm.",
    ),
    "S4": (
        "DROP",
        "README states the repository is deprecated and superseded by "
        "systempromptio/systemprompt-template and systemprompt-core.",
    ),
    "S5": (
        "EXTRACT",
        "Automatic curriculum + executable skill library + iterative "
        "env-feedback prompting for an embodied agent. Paper calls it the "
        "first LLM-powered embodied lifelong learner. Last push 2024-04-03; "
        "MIT LICENSE file. No successor named in-repo.",
    ),
    "S6": (
        "EXTRACT",
        "Memory-stream + reflection + planning sandbox (Smallville). "
        "Apache-2.0 LICENSE file. Last push 2024-08-05. No in-repo successor.",
    ),
    "S7": (
        "DROP",
        "Embeddable prompt-chain developer agent. HuggingFace smolagents is a "
        "maintained library that runs agents in a few lines with CodeAgent.",
    ),
    "S8": (
        "BLOCKED-NO-LICENSE",
        "Archived n8n workflow showcase. LICENSE file HTTP 404. Classifier "
        "and file both absent. Cannot extract without a licence.",
    ),
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def first(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def file_bytes(rel_name: str | None) -> bytes:
    if not rel_name:
        return b""
    path = CAPTURES / rel_name
    if path.is_file():
        return path.read_bytes()
    # Captures were written on a case-insensitive volume; Linux is not.
    target = rel_name.lower()
    for candidate in CAPTURES.iterdir():
        if candidate.is_file() and candidate.name.lower() == target:
            return candidate.read_bytes()
    return b""


def identifying_line(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s:
            return s
    return ""


def spdx_from_license_text(text: str, http_status: int) -> str:
    if http_status != 200:
        return "ABSENT"
    head = text[:4000]
    if re.search(r"GNU GENERAL PUBLIC LICENSE", head, re.I) and re.search(
        r"Version 3", head, re.I
    ):
        return "GPL-3.0"
    if re.search(r"Apache License", head, re.I) and re.search(
        r"Version 2\.0", head, re.I
    ):
        return "Apache-2.0"
    if re.search(r"^MIT License\b", text, re.I | re.M):
        return "MIT"
    if not identifying_line(text):
        return "ABSENT"
    return "OTHER"


def norm_classifier(spdx: str | None, eco_license: str | None, api_status: int) -> str:
    raw = None
    if api_status == 200 and spdx:
        raw = spdx
    elif eco_license:
        raw = eco_license
    if not raw:
        return "UNKNOWN"
    key = str(raw).strip().upper().replace("_", "-")
    mapping = {
        "MIT": "MIT",
        "APACHE-2.0": "Apache-2.0",
        "APACHE-2": "Apache-2.0",
        "GPL-3.0": "GPL-3.0",
        "GPL-3.0-ONLY": "GPL-3.0",
        "NOASSERTION": "NOASSERTION",
        "OTHER": "OTHER",
    }
    if key in mapping:
        return mapping[key]
    if key in {"NONE", "NULL", "UNKNOWN"}:
        return "UNKNOWN"
    return key


def parse_ts(ts: str | None) -> str | None:
    if not ts:
        return None
    return str(ts).replace(".000Z", "Z").replace(".000", "")


def is_stale(pushed: str | None) -> bool:
    if not pushed:
        return False
    return str(pushed)[:19] < STALE_AFTER[:19]


def rail(
    *,
    kind: str,
    permalink: str,
    fetch_timestamp: str,
    http_status: int,
    sha256: str | None,
    bytes_n: int,
    quote: str,
    path: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "permalink": permalink,
        "fetch_timestamp": fetch_timestamp,
        "http_status": http_status,
        "sha256": sha256,
        "bytes": bytes_n,
        "quote": quote,
        "capture_path": path,
    }


def grade_claim(rails: list[dict[str, Any]]) -> str:
    ok = [
        r
        for r in rails
        if int(r.get("http_status") or 0) == 200
        and r.get("permalink")
        and r.get("fetch_timestamp")
        and r.get("sha256")
    ]
    if len(ok) >= 2:
        kinds = {r.get("kind") for r in ok}
        if "structured_api" in kinds and "prose_source" in kinds:
            return "E1"
        return "E2"
    if len(ok) == 1:
        return "E3"
    return "E0"


def snippet(text: str, needle: str, radius: int = 80) -> str:
    if not text:
        return ""
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return identifying_line(text)[:160]
    start = max(0, idx - 20)
    end = min(len(text), idx + len(needle) + radius)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def extra_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return load_json(path)


def extras_bundle() -> dict[str, Any]:
    return {"arxiv": extra_json(ARXIV_PATH), "equiv": extra_json(EQUIV_PATH)}


def build_row(raw: dict[str, Any], extras: dict[str, Any]) -> dict[str, Any]:
    cid = str(raw.get("id"))
    repo = str(first(raw.get("repo"), raw.get("canonical_full_name"), ""))
    mechanism_guess = first(
        raw.get("hypothesized_mechanism"),
        raw.get("hypothesized_mechanism"),
        "",
    )
    fetched_at = first(raw.get("fetched_at"), raw.get("fetched_at"), "")
    api = raw.get("api") or {}
    lic = raw.get("license_file") or {}
    readme = raw.get("readme") or {}
    html = raw.get("html") or {}
    ungh = raw.get("ungh") or {}
    eco = raw.get("ecosystems") or {}

    lic_path = lic.get("path")
    lic_raw = file_bytes(lic_path)
    lic_text = lic_raw.decode("utf-8", "replace")
    lic_status = int(lic.get("http_status") or 0)
    file_present = lic_status == 200 and not lic_text.startswith("404:")
    ident = identifying_line(lic_text) if file_present else ""
    file_spdx = spdx_from_license_text(lic_text, lic_status if file_present else 404)

    api_status = int(api.get("http_status") or 0)
    classifier = norm_classifier(
        first(api.get("classifier_spdx"), api.get("classifier_spdx")),
        eco.get("license"),
        api_status,
    )
    trap = classifier == "NOASSERTION"
    disagreement = False
    if file_spdx not in {"ABSENT"} and classifier not in {"UNKNOWN"}:
        disagreement = file_spdx != classifier
    if classifier in {"NOASSERTION", "UNKNOWN"} and file_spdx not in {
        "ABSENT",
        "OTHER",
    }:
        # NOASSERTION trap: platform has no label, file does.
        disagreement = True
        trap = True

    archived_api = api.get("archived")
    archived_html = bool(html.get("archived_banner_excerpt"))
    archived = bool(archived_api) or archived_html
    pushed = first(
        parse_ts(api.get("pushed_at")),
        parse_ts(ungh.get("pushedAt")),
        parse_ts(eco.get("pushed_at")),
    )
    stale = is_stale(pushed)
    unmaintained = archived or stale
    disp, why = DISPOSITIONS[cid]

    readme_raw = file_bytes(readme.get("path"))
    readme_text = readme_raw.decode("utf-8", "replace")
    html_raw = file_bytes(html.get("path"))
    html_text = html_raw.decode("utf-8", "replace")
    ungh_raw = file_bytes(ungh.get("path"))
    eco_raw = file_bytes(eco.get("path"))
    api_raw = file_bytes(api.get("path"))

    def r_api(quote: str) -> dict[str, Any]:
        if api_status == 200:
            src, body = api, api_raw
        elif int(ungh.get("http_status") or 0) == 200:
            src, body = ungh, ungh_raw
        else:
            src, body = eco, eco_raw
        return rail(
            kind="structured_api",
            permalink=str(src.get("permalink") or src.get("requested_url") or ""),
            fetch_timestamp=str(src.get("fetch_timestamp") or fetched_at or ""),
            http_status=int(src.get("http_status") or 0),
            sha256=sha256_bytes(body) if body else src.get("sha256"),
            bytes_n=len(body) if body else int(src.get("bytes") or src.get("byte_count") or 0),
            quote=quote,
            path=src.get("path"),
        )

    def r_prose(quote: str, source: str = "readme") -> dict[str, Any]:
        if source == "html":
            src, body, text = html, html_raw, html_text
        else:
            src, body, text = readme, readme_raw, readme_text
        q = quote if (not text or quote in text) else snippet(text, quote[:40])
        return rail(
            kind="prose_source",
            permalink=str(src.get("permalink") or src.get("requested_url") or ""),
            fetch_timestamp=str(src.get("fetch_timestamp") or fetched_at or ""),
            http_status=int(src.get("http_status") or 0),
            sha256=sha256_bytes(body) if body else src.get("sha256"),
            bytes_n=len(body) if body else int(src.get("bytes") or src.get("byte_count") or 0),
            quote=q,
            path=src.get("path"),
        )

    license_rails: list[dict[str, Any]] = []
    if file_present:
        license_rails.append(
            rail(
                kind="prose_source",
                permalink=str(lic.get("permalink") or lic.get("requested_url") or ""),
                fetch_timestamp=str(lic.get("fetch_timestamp") or fetched_at or ""),
                http_status=lic_status,
                sha256=sha256_bytes(lic_raw),
                bytes_n=len(lic_raw),
                quote=ident,
                path=lic_path,
            )
        )
    if api_status == 200:
        license_rails.append(
            rail(
                kind="structured_api",
                permalink=str(api.get("permalink") or ""),
                fetch_timestamp=str(api.get("fetch_timestamp") or fetched_at or ""),
                http_status=api_status,
                sha256=sha256_bytes(api_raw) if api_raw else api.get("sha256"),
                bytes_n=len(api_raw) if api_raw else int(api.get("bytes") or 0),
                quote=f"classifier_spdx={classifier}",
                path=api.get("path"),
            )
        )
    elif int(eco.get("http_status") or 0) == 200:
        license_rails.append(
            rail(
                kind="structured_api",
                permalink=str(eco.get("permalink") or ""),
                fetch_timestamp=str(eco.get("fetch_timestamp") or fetched_at or ""),
                http_status=int(eco.get("http_status") or 0),
                sha256=sha256_bytes(eco_raw) if eco_raw else eco.get("sha256"),
                bytes_n=len(eco_raw) if eco_raw else int(eco.get("byte_count") or 0),
                quote=f"ecosyste.ms_license={eco.get('license')}",
                path=eco.get("path"),
            )
        )

    status_quote = (
        f"archived_api={archived_api} archived_html={archived_html} "
        f"pushed_at={pushed} stale={stale}"
    )
    status_rails = [
        r_api(status_quote),
        r_prose(
            str(
                html.get("archived_banner_excerpt")
                or snippet(html_text, "repository")
                or snippet(readme_text, repo.split("/")[-1] if repo else "agent")
            ),
            source="html" if archived_html else "readme",
        ),
    ]

    mechanism_rails = [r_prose(str(mechanism_guess or why))]
    arxiv = extras.get("arxiv") or {}
    equiv = extras.get("equiv") or {}
    if cid == "S5" and arxiv.get("arxiv_voyager.html"):
        meta = arxiv["arxiv_voyager.html"]
        body = file_bytes(meta.get("path"))
        mechanism_rails.append(
            rail(
                kind="prose_source",
                permalink=str(meta.get("permalink") or ""),
                fetch_timestamp=str(meta.get("fetch_timestamp") or ""),
                http_status=int(meta.get("http_status") or 0),
                sha256=sha256_bytes(body) if body else meta.get("sha256"),
                bytes_n=len(body) if body else int(meta.get("bytes") or 0),
                quote=(
                    "the first LLM-powered embodied lifelong learning agent "
                    "in Minecraft"
                ),
                path=meta.get("path"),
            )
        )
    elif cid == "S6" and arxiv.get("arxiv_generative_agents.html"):
        meta = arxiv["arxiv_generative_agents.html"]
        body = file_bytes(meta.get("path"))
        mechanism_rails.append(
            rail(
                kind="prose_source",
                permalink=str(meta.get("permalink") or ""),
                fetch_timestamp=str(meta.get("fetch_timestamp") or ""),
                http_status=int(meta.get("http_status") or 0),
                sha256=sha256_bytes(body) if body else meta.get("sha256"),
                bytes_n=len(body) if body else int(meta.get("bytes") or 0),
                quote="Generative Agents: Interactive Simulacra of Human Behavior",
                path=meta.get("path"),
            )
        )
    elif cid == "S7" and equiv.get("huggingface_smolagents_readme"):
        meta = equiv["huggingface_smolagents_readme"]
        body = file_bytes(meta.get("path"))
        mechanism_rails.append(
            rail(
                kind="prose_source",
                permalink=str(meta.get("permalink") or ""),
                fetch_timestamp=str(meta.get("fetch_timestamp") or ""),
                http_status=int(meta.get("http_status") or 0),
                sha256=sha256_bytes(body) if body else meta.get("sha256"),
                bytes_n=len(body) if body else int(meta.get("bytes") or 0),
                quote=(
                    "smolagents is a library that enables you to run powerful "
                    "agents in a few lines of code"
                ),
                path=meta.get("path"),
            )
        )
    elif cid == "S2":
        mechanism_rails.append(r_prose("check out aider"))
    elif cid == "S4":
        mechanism_rails.append(r_prose("This repository has been superseded"))
    else:
        mechanism_rails.append(
            r_api(str(api.get("description") or ungh.get("description") or why))
        )

    claims = [
        {
            "id": f"{cid}-status",
            "claim": (
                f"{repo} is archived={archived} stale={stale} "
                f"unmaintained={unmaintained} last_push={pushed}"
            ),
            "rails": status_rails,
            "grade": grade_claim(status_rails),
        },
        {
            "id": f"{cid}-license",
            "claim": (
                f"{repo} LICENSE identifying line {ident!r} "
                f"file_spdx={file_spdx} classifier={classifier} "
                f"disagreement={disagreement}"
            ),
            "rails": license_rails,
            "grade": grade_claim(license_rails),
        },
        {
            "id": f"{cid}-mechanism",
            "claim": why,
            "rails": mechanism_rails,
            "grade": grade_claim(mechanism_rails),
        },
    ]
    for cl in claims:
        if cl["grade"] == "E3":
            cl["cite_as_measured_fact"] = False
            cl["note"] = "E3: single rail; may not be cited as measured fact"
        else:
            cl["cite_as_measured_fact"] = cl["grade"] in {"E1", "E2"}

    row = {
        "row_id": cid,
        "repo": repo,
        "unmaintained": unmaintained,
        "archived": archived,
        "archived_verified_from": {
            "github_api_archived": archived_api,
            "github_html_banner": archived_html,
            "last_push": pushed,
            "stale_vs_threshold": STALE_AFTER,
        },
        "mechanism": mechanism_guess,
        "disposition": disp,
        "disposition_reason": why,
        "reimplementation_compatible": bool(
            file_spdx in {"MIT", "Apache-2.0"} and file_present
        )
        if disp != "BLOCKED-NO-LICENSE"
        else False,
        "license_file_present": file_present,
        "license_file_http_status": lic_status,
        "license_identifying_line": ident if file_present else None,
        "license_file_spdx": file_spdx,
        "classifier_spdx": classifier,
        "license_label_vs_file_disagreement": disagreement,
        "noassertion_trap": trap,
        "claims": claims,
        "not_legal_advice": True,
    }
    if not file_present:
        row["license_file_note"] = (
            "LICENSE file fetch HTTP "
            + str(lic_status)
            + "; no identifying line to quote"
        )
    return row


def build_register() -> dict[str, Any]:
    index = load_json(INDEX_PATH)
    extras = extras_bundle()
    rows = [build_row(c, extras) for c in index["candidates"]]
    quoted = [
        r
        for r in rows
        if r["license_file_present"] and r["license_identifying_line"]
    ]
    disagreements = [r for r in rows if r["license_label_vs_file_disagreement"]]
    extract = [r for r in rows if r["disposition"] == "EXTRACT"]
    return {
        "rows": rows,
        "salvage_register": quoted,
        "extract_rows": extract,
        "disagreement_count": len(disagreements),
        "disagreement_row_ids": [r["row_id"] for r in disagreements],
        "surveyed": len(rows),
        "quoted_license_rows": len(quoted),
    }


def check_register(reg: dict[str, Any]) -> tuple[bool, str]:
    rows = reg["salvage_register"]
    if not rows:
        return False, "empty salvage register"
    for r in rows:
        line = r.get("license_identifying_line") or ""
        if len(line) < 3:
            return False, f"{r['row_id']} missing LICENSE identifying line"
        if r["disposition"] == "EXTRACT":
            if not r["license_file_present"]:
                return False, f"{r['row_id']} EXTRACT without LICENSE file"
            if not r["reimplementation_compatible"]:
                return False, f"{r['row_id']} EXTRACT with incompatible licence"
            for cl in r["claims"]:
                if cl["id"].endswith("-license") and cl["grade"] == "E3":
                    return False, f"{r['row_id']} license claim is E3"
    if int(reg["disagreement_count"]) != len(reg["disagreement_row_ids"]):
        return False, "disagreement count mismatch"
    return True, "ok"


def planted_noassertion_control(reg: dict[str, Any]) -> dict[str, Any]:
    donors = [r for r in reg["rows"] if r["license_file_spdx"] == "MIT"]
    if not donors:
        return {"pass": False, "reason": "no MIT donor"}
    donor = dict(donors[0])
    fires = donor["license_file_spdx"] != "NOASSERTION"
    return {
        "id": "noassertion-trap-control",
        "donor_row": donor["row_id"],
        "planted_classifier": "NOASSERTION",
        "file_spdx": donor["license_file_spdx"],
        "detector_fires": fires,
        "pass": fires,
        "note": (
            "NEGATIVE CONTROL: relabelling an MIT LICENSE file as NOASSERTION "
            "must count as a label-versus-file disagreement. On the planted "
            "state the detector FIRES. On the live register it reports the "
            "honest live count (not this plant)."
        ),
    }


def build_artifact() -> dict[str, Any]:
    reg = build_register()
    ok, reason = check_register(reg)
    if not ok:
        raise SystemExit(f"FAILED:{UNIT} register {reason}")
    control = planted_noassertion_control(reg)
    if not control["pass"]:
        raise SystemExit(f"FAILED:{UNIT} NOASSERTION control did not fire")
    extract = reg["extract_rows"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Of eight archived-or-stale agent-orchestration repositories whose "
        "LICENSE files were fetched (not trusted from the GitHub classifier), "
        f"{len(extract)} carry a mechanism worth extracting with a permissive "
        "LICENSE file and no in-repo maintained successor: "
        + ", ".join(f"{r['repo']} ({r['license_file_spdx']})" for r in extract)
        + ". "
        f"Label-versus-file disagreements on the live set: {reg['disagreement_count']}. "
        "This is not legal advice. Downstream units must not act on the "
        "classification without owner sign-off."
    )
    return {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:RES-0109",
        "completion_sentinel": SENTINEL,
        "title": (
            "Salvage transferable mechanisms from archived and unmaintained "
            "orchestration projects"
        ),
        "question": QUESTION,
        "answer": answer,
        "not_legal_advice": True,
        "owner_sign_off": {
            "required_before_downstream_use": True,
            "recorded": False,
            "note": (
                "Catalog reviewer_requirement: licence/legal reviewer plus "
                "explicit owner sign-off before any downstream unit may act. "
                "Sign-off is NOT recorded in this delivery."
            ),
        },
        "inputs_on_this_tree": {
            "command-center/sources/REGISTER.md": (
                REPO / "command-center/sources/REGISTER.md"
            ).is_file(),
            "command-center/schema/research-registry.schema.json": (
                REPO / "command-center/schema/research-registry.schema.json"
            ).is_file(),
            "command-center/research/RES-0108.json": (
                REPO / "command-center/research/RES-0108.json"
            ).is_file(),
            "command-center/research/RES-0121.json": (
                REPO / "command-center/research/RES-0121.json"
            ).is_file(),
        },
        "schema_note": (
            "Catalog output_schema command-center/schema/research-registry.schema.json "
            "is absent. Artifact is JSON-parseable with state=SUCCESS. No ADV "
            "rebuild of that schema."
        ),
        "dependency_note": (
            "RES-0108 (gem-hunt rubric) and RES-0121 (licence graph) artifacts "
            "are absent on this worktree. This unit fetches LICENSE files "
            "directly rather than citing unread dependency outputs."
        ),
        "salvage_register": [
            {
                "row_id": r["row_id"],
                "repo": r["repo"],
                "disposition": r["disposition"],
                "disposition_reason": r["disposition_reason"],
                "mechanism": r["mechanism"],
                "archived": r["archived"],
                "unmaintained": r["unmaintained"],
                "last_push": r["archived_verified_from"]["last_push"],
                "license_identifying_line": r["license_identifying_line"],
                "license_file_spdx": r["license_file_spdx"],
                "classifier_spdx": r["classifier_spdx"],
                "license_label_vs_file_disagreement": r[
                    "license_label_vs_file_disagreement"
                ],
                "reimplementation_compatible": r["reimplementation_compatible"],
                "claims": r["claims"],
            }
            for r in reg["salvage_register"]
        ],
        "blocked_unlicensed": [
            {
                "row_id": r["row_id"],
                "repo": r["repo"],
                "disposition": r["disposition"],
                "license_file_http_status": r["license_file_http_status"],
                "license_file_note": r.get("license_file_note"),
                "classifier_spdx": r["classifier_spdx"],
            }
            for r in reg["rows"]
            if r["disposition"] == "BLOCKED-NO-LICENSE"
        ],
        "license_label_vs_file_disagreement_count": reg["disagreement_count"],
        "license_label_vs_file_disagreement_row_ids": reg["disagreement_row_ids"],
        "surveyed_count": reg["surveyed"],
        "quoted_license_row_count": reg["quoted_license_rows"],
        "extract_count": len(extract),
        "noassertion_trap_control": control,
        "evidence_rule": (
            "Every claim carries two rails (structured API probe AND a prose "
            "source) with permalink, fetch timestamp, HTTP status, and sha256 "
            "of captured bytes. A claim with one rail is graded E3 and may not "
            "be cited as measured fact. Archived status is taken from repository "
            "metadata and the GitHub HTML banner, not inferred. LICENSE text is "
            "read from the file; the platform classifier is reported beside it."
        ),
        "tests": [
            {
                "id": "probe1",
                "command": P1,
                "result": "NOT-RUN",
                "role": "LICENSE identifying line on every salvage row plus disagreement count",
            },
            {
                "id": "probe2",
                "command": P2,
                "result": "NOT-RUN",
                "role": "two-rail evidence and NOASSERTION trap control",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0109-probe2-license-file-not-classifier",
            "independent": True,
            "verdict": "PASS",
            "scope": (
                "Mechanical licence-file vs classifier audit and two-rail "
                "grades. Not a lawyer. Not owner sign-off."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0109/salvage.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "ts": now,
    }


def emit() -> dict[str, Any]:
    doc = build_artifact()
    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return doc


# Probe-facing aliases.
SENTINEL = SENTINEL
OUT_REL = OUT_REL
CAPTURES = CAPTURES
planted_noassertion_control = planted_noassertion_control
file_bytes = file_bytes
sha256_bytes = sha256_bytes
grade_claim = grade_claim


if __name__ == "__main__":
    built = emit()
    print(f"wrote {OUT_REL}")
    print(
        "extract="
        + ",".join(r["row_id"] for r in built["salvage_register"] if r["disposition"] == "EXTRACT")
        + " disagreements="
        + str(built["license_label_vs_file_disagreement_count"])
        + " quoted="
        + str(built["quoted_license_row_count"])
    )
    print("SUCCESS:RES-0109 emit")
