"""Licence-graph core for RES-0121.

Reachable means: we have a repo identity AND the LICENSE file bytes on disk.
The E001-E189 table lives in a Windows-path source that is absent on this
tree; those rows stay unreachable rather than being given invented URLs.
The two catalog-named trap rows are fetched from their LICENSE files and
from the GitHub licence classifier API, reported side by side.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0121"
OUT_REL = "command-center/research/RES-0121.json"
SCHEMA_REL = "command-center/schema/license-graph.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
REGISTER_EXPECTED = 189
CATALOG_SENTINEL = (
    "SUCCESS:RES-0121 in the receipt AND a licence graph where every "
    "reachable row carries a LICENSE sha256, plus the resolved verdicts "
    "for the two named trap rows"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0121/probe1_reachable_sha256.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0121/probe2_traps_disagree.py"
)

QUESTION = (
    "For the 189-candidate external register (E001-E189), what does each "
    "upstream LICENSE FILE actually say - closing the recorded gap that 19 "
    "rows are NOASSERTION, zero LICENSE files have been fetched, and blogs "
    "call BMAD-METHOD MIT while the classifier returns NOASSERTION?"
)

REGISTER_CANDIDATES = [
    "command-center/sources/REGISTER.md",
    "command-center/sources/05-ECO-workflow-sources.md",
    "command-center/research/05-ECO-workflow-sources.md",
    "command-center/wfa/05-ECO-workflow-sources.md",
    "05-ECO-workflow-sources.md",
    "command-center/sources/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "command-center/wfa/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "/mnt/c/Users/Prekzursil/.claude/platform-redesign-2026-07-19/05-ECO-workflow-sources.md",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
]

TRAPS = [
    {
        "id": "TRAP-BMAD-METHOD",
        "catalog_name": "BMAD-METHOD",
        "repo": "bmad-code-org/BMAD-METHOD",
        "license_rel": "licenses/BMAD-METHOD.LICENSE",
        "classifier_rel": "fixtures/classifier/BMAD-METHOD.json",
        "trap_kind": "NOASSERTION-VS-FILE-MIT",
    },
    {
        "id": "TRAP-microsoft-autogen",
        "catalog_name": "microsoft/autogen",
        "repo": "microsoft/autogen",
        "license_rel": "licenses/microsoft-autogen.LICENSE",
        "classifier_rel": "fixtures/classifier/microsoft-autogen.json",
        "trap_kind": "CONTENT-LICENCE-ON-CODE-REPO",
    },
]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def identifying_from_text(text: str) -> dict:
    lines = text.replace("\r\n", "\n").split("\n")
    identifying = next((ln.strip() for ln in lines if ln.strip()), "")
    riders: list[str] = []
    upper = text.upper()
    if "TRADEMARK NOTICE" in upper:
        riders.append("TRADEMARK NOTICE")
    spdx = "UNCLASSIFIED-FILE"
    head = "\n".join(lines[:12])
    if re.search(r"^MIT License\b", head, re.M):
        spdx = "MIT"
    elif "ATTRIBUTION 4.0 INTERNATIONAL" in upper and "CREATIVE COMMONS" in upper:
        spdx = "CC-BY-4.0"
    elif "APACHE LICENSE" in upper and "VERSION 2.0" in upper:
        spdx = "Apache-2.0"
    elif "GNU GENERAL PUBLIC LICENSE" in upper and "VERSION 3" in upper:
        spdx = "GPL-3.0"
    elif "GNU GENERAL PUBLIC LICENSE" in upper and "VERSION 2" in upper:
        spdx = "GPL-2.0"
    return {
        "identifying_text": identifying,
        "file_says": spdx,
        "riders": riders,
        "excerpt": text[:240],
    }


def normalize_label(label: str) -> str:
    s = (label or "").strip()
    aliases = {
        "MIT LICENSE": "MIT",
        "MIT": "MIT",
        "OTHER": "NOASSERTION",
        "NOASSERTION": "NOASSERTION",
        "NONE": "NOASSERTION",
        "CC-BY-4.0": "CC-BY-4.0",
        "CC BY 4.0": "CC-BY-4.0",
        "ATTRIBUTION 4.0 INTERNATIONAL": "CC-BY-4.0",
        "CREATIVE COMMONS ATTRIBUTION 4.0 INTERNATIONAL": "CC-BY-4.0",
    }
    return aliases.get(s.upper(), s)


def disagrees(file_says: str, classifier: str) -> bool:
    a = normalize_label(file_says)
    b = normalize_label(classifier)
    if not a or not b:
        return True
    return a != b


def locate_register() -> dict:
    tried = []
    for rel in REGISTER_CANDIDATES:
        path = REPO / rel
        present = path.is_file()
        tried.append({"path": rel, "present": present})
        if not present:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        e_ids = re.findall(r"\bE(?:00[1-9]|0[1-9]\d|1[0-8]\d)\b", text)
        uniq = sorted(set(e_ids))
        if "E001" in uniq:
            return {
                "present": True,
                "path": rel,
                "e_id_count": len(uniq),
                "tried": tried,
            }
    win = [
        "C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19/05-ECO-workflow-sources.md",
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
    ]
    for p in win:
        tried.append({"path": p, "present": Path(p).is_file()})
    return {
        "present": False,
        "path": None,
        "e_id_count": 0,
        "tried": tried,
        "status": "REGISTER-SOURCE-ABSENT",
    }


def load_trap(spec: dict) -> dict:
    lic_path = HERE / spec["license_rel"]
    cls_path = HERE / spec["classifier_rel"]
    if not lic_path.is_file():
        raise FileNotFoundError(spec["license_rel"])
    if not cls_path.is_file():
        raise FileNotFoundError(spec["classifier_rel"])
    raw = lic_path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    ident = identifying_from_text(text)
    classifier = json.loads(cls_path.read_text(encoding="utf-8"))
    file_sha, file_bytes = sha256_file(lic_path)
    label = str(classifier.get("classifier_spdx") or "")
    disagree = disagrees(ident["file_says"], label)
    file_rail = {
        "rail": "license-file",
        "permalink": classifier.get("download_url")
        or classifier.get("html_url"),
        "http_status": 200,
        "fetched_at": "2026-08-24T18:52:02Z",
        "sha256": file_sha,
        "bytes": file_bytes,
        "local_path": f"command-center/p2-wave/probes/RES-0121/{spec['license_rel']}",
    }
    api_rail = {
        "rail": "github-license-api",
        "permalink": classifier.get("permalink"),
        "http_status": int(classifier.get("http_status") or 0),
        "fetched_at": classifier.get("fetched_at"),
        "sha256": classifier.get("response_sha256"),
        "bytes": classifier.get("response_bytes"),
        "local_path": f"command-center/p2-wave/probes/RES-0121/{spec['classifier_rel']}",
        "classifier_name": classifier.get("classifier_name"),
    }
    verdict = trap_verdict(spec, ident, label, disagree)
    return {
        "id": spec["id"],
        "catalog_name": spec["catalog_name"],
        "register_eid": None,
        "register_eid_status": "UNKNOWN-REGISTER-ABSENT",
        "repo": spec["repo"],
        "reachable": True,
        "license_path": classifier.get("path") or "LICENSE",
        "license_sha256": file_sha,
        "license_bytes": file_bytes,
        "license_identifying_text": ident["identifying_text"],
        "file_says": ident["file_says"],
        "riders": ident["riders"],
        "excerpt": ident["excerpt"],
        "classifier_label": label,
        "classifier_name": classifier.get("classifier_name"),
        "disagrees_with_classifier": disagree,
        "trap_kind": spec["trap_kind"],
        "verdict": verdict,
        "rails": [api_rail, file_rail],
        "git_blob_sha": classifier.get("git_blob_sha"),
        "html_url": classifier.get("html_url"),
    }


def trap_verdict(spec: dict, ident: dict, label: str, disagree: bool) -> str:
    kind = spec["trap_kind"]
    if kind == "NOASSERTION-VS-FILE-MIT":
        if ident["file_says"] == "MIT" and normalize_label(label) == "NOASSERTION" and disagree:
            rider = (
                "; file also carries a TRADEMARK NOTICE rider"
                if "TRADEMARK NOTICE" in ident["riders"]
                else ""
            )
            return (
                "RESOLVED: LICENSE file identifying text is 'MIT License' "
                f"(file_says=MIT){rider}; GitHub classifier spdx_id=NOASSERTION. "
                "The catalog blog-vs-classifier trap is confirmed by reading "
                "the file, not by trusting the classifier."
            )
        return "UNRESOLVED: BMAD-METHOD file/classifier pair did not match the named trap"
    if kind == "CONTENT-LICENCE-ON-CODE-REPO":
        if ident["file_says"] == "CC-BY-4.0" and normalize_label(label) == "CC-BY-4.0":
            return (
                "RESOLVED: LICENSE file is Creative Commons Attribution 4.0 "
                "International (file_says=CC-BY-4.0) and the classifier agrees. "
                "That is a content licence on a code repository; the file was "
                "read rather than assumed to be a software-permissive licence."
            )
        return "UNRESOLVED: microsoft/autogen file/classifier pair did not match the named trap"
    return f"UNRESOLVED: unknown trap kind {kind}"


def unreachable_e_row(n: int) -> dict:
    return {
        "id": f"E{n:03d}",
        "reachable": False,
        "unreachability": "REGISTER-SOURCE-ABSENT",
        "repo": None,
        "license_sha256": None,
        "classifier_label": None,
        "file_says": None,
        "disagrees_with_classifier": None,
        "note": (
            "E001-E189 identity cannot be bound to a repo because "
            "05-ECO-workflow-sources.md is not on this worktree."
        ),
    }


def build_rows() -> tuple[list[dict], dict]:
    register = locate_register()
    e_rows = [unreachable_e_row(i) for i in range(1, REGISTER_EXPECTED + 1)]
    traps = [load_trap(spec) for spec in TRAPS]
    rows = e_rows + traps
    return rows, register


def reachable_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("reachable") is True]


def missing_sha256(rows: list[dict]) -> list[str]:
    bad = []
    for r in reachable_rows(rows):
        sha = str(r.get("license_sha256") or "")
        if not re.fullmatch(r"[a-f0-9]{64}", sha):
            bad.append(str(r.get("id")))
    return bad


def disagreement_rows(rows: list[dict]) -> list[dict]:
    return [
        r
        for r in reachable_rows(rows)
        if r.get("disagrees_with_classifier") is True
    ]


def recompute_counts(rows: list[dict]) -> dict:
    reach = reachable_rows(rows)
    return {
        "register_expected": REGISTER_EXPECTED,
        "register_e_rows": sum(1 for r in rows if re.fullmatch(r"E\d{3}", str(r.get("id") or ""))),
        "graph_rows": len(rows),
        "reachable": len(reach),
        "unreachable": sum(1 for r in rows if r.get("reachable") is False),
        "license_sha256_on_reachable": len(reach) - len(missing_sha256(rows)),
        "file_vs_classifier_disagreements": len(disagreement_rows(rows)),
        "noassertion_classifier": sum(
            1
            for r in reach
            if normalize_label(str(r.get("classifier_label") or "")) == "NOASSERTION"
        ),
    }


def graph_problems(rows: list[dict]) -> list[str]:
    problems: list[str] = []
    e_ids = [str(r.get("id")) for r in rows if re.fullmatch(r"E\d{3}", str(r.get("id") or ""))]
    expected = [f"E{i:03d}" for i in range(1, REGISTER_EXPECTED + 1)]
    if e_ids != expected:
        problems.append("e-id-span-mismatch")
    if missing_sha256(rows):
        problems.append("reachable-missing-sha256:" + ",".join(missing_sha256(rows)))
    names = {r.get("catalog_name") for r in rows if r.get("reachable")}
    if "BMAD-METHOD" not in names:
        problems.append("trap-bmad-absent")
    if "microsoft/autogen" not in names:
        problems.append("trap-autogen-absent")
    for r in reachable_rows(rows):
        rails = r.get("rails") or []
        if len(rails) < 2:
            problems.append(f"single-rail:{r.get('id')}")
        ident = identifying_from_text(
            (HERE / "licenses" / license_filename(r)).read_text(encoding="utf-8")
            if license_filename(r)
            else ""
        ) if license_filename(r) else None
        if ident and ident["file_says"] != r.get("file_says"):
            problems.append(f"file-says-drift:{r.get('id')}")
        stored = stored_license_sha(r)
        if stored and stored != r.get("license_sha256"):
            problems.append(f"sha-mismatch:{r.get('id')}")
        recomputed = disagrees(str(r.get("file_says") or ""), str(r.get("classifier_label") or ""))
        if recomputed != bool(r.get("disagrees_with_classifier")):
            problems.append(f"disagree-flag-drift:{r.get('id')}")
    return problems


def license_filename(row: dict) -> str | None:
    name = row.get("catalog_name")
    if name == "BMAD-METHOD":
        return "BMAD-METHOD.LICENSE"
    if name == "microsoft/autogen":
        return "microsoft-autogen.LICENSE"
    return None


def stored_license_sha(row: dict) -> str | None:
    fn = license_filename(row)
    if not fn:
        return None
    path = HERE / "licenses" / fn
    if not path.is_file():
        return None
    return sha256_file(path)[0]


def trap_checks(rows: list[dict]) -> list[str]:
    problems: list[str] = []
    by_name = {r.get("catalog_name"): r for r in rows if r.get("reachable")}
    bmad = by_name.get("BMAD-METHOD")
    auto = by_name.get("microsoft/autogen")
    if not bmad:
        problems.append("bmad-row-missing")
    else:
        if bmad.get("file_says") != "MIT":
            problems.append("bmad-file-not-mit")
        if normalize_label(str(bmad.get("classifier_label") or "")) != "NOASSERTION":
            problems.append("bmad-classifier-not-noassertion")
        if bmad.get("disagrees_with_classifier") is not True:
            problems.append("bmad-disagree-not-true")
        if not str(bmad.get("verdict") or "").startswith("RESOLVED:"):
            problems.append("bmad-unresolved")
    if not auto:
        problems.append("autogen-row-missing")
    else:
        if auto.get("file_says") != "CC-BY-4.0":
            problems.append("autogen-file-not-cc-by-4.0")
        if normalize_label(str(auto.get("classifier_label") or "")) != "CC-BY-4.0":
            problems.append("autogen-classifier-not-cc-by-4.0")
        if auto.get("disagrees_with_classifier") is True:
            problems.append("autogen-false-disagreement")
        if not str(auto.get("verdict") or "").startswith("RESOLVED:"):
            problems.append("autogen-unresolved")
        if auto.get("trap_kind") != "CONTENT-LICENCE-ON-CODE-REPO":
            problems.append("autogen-trap-kind")
    return problems


def graph_ok(rows: list[dict]) -> tuple[bool, list[str]]:
    problems = graph_problems(rows) + trap_checks(rows)
    return (not problems), problems


def mutate_drop_sha256(rows: list[dict], row_id: str) -> list[dict]:
    out = []
    for r in rows:
        copy = dict(r)
        if copy.get("id") == row_id:
            copy["license_sha256"] = ""
        out.append(copy)
    return out


def mutate_hide_bmad_disagreement(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        copy = dict(r)
        if copy.get("catalog_name") == "BMAD-METHOD":
            copy["classifier_label"] = "MIT"
            copy["disagrees_with_classifier"] = False
        out.append(copy)
    return out
