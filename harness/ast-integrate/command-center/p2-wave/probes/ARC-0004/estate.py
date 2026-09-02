"""Build a scratch A1 config-first tree from DESIGN.json samples and apply
three real additions (skill, workflow blueprint, council preset).

Production command-center/control-plane/A1/ is absent on this worktree. The
scratch estate is the measurable A1 tree (same honesty pattern as ARC-0005
fixtures when host rules trees were absent).
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DESIGN = REPO / "command-center/phase3/A1/DESIGN.json"
FIX = HERE / "fixtures"
_DESIGN_CACHE: dict | None = None

FALLBACK_LOAD_ORDER = [
    {"path": "command-center/control-plane/A1/MANIFEST.json"},
    {"path": "command-center/control-plane/A1/capabilities/rules/"},
    {"path": "command-center/control-plane/A1/capabilities/skills/"},
    {"path": "command-center/control-plane/A1/capabilities/hooks/"},
    {"path": "command-center/control-plane/A1/capabilities/mcp/"},
    {"path": "command-center/control-plane/A1/capabilities/workflows/"},
    {"path": "command-center/control-plane/A1/capabilities/council/protocols/"},
    {"path": "command-center/control-plane/A1/capabilities/council/presets/"},
    {"path": "command-center/control-plane/A1/precedence.json"},
]

FALLBACK_SAMPLE_RELS = (
    ("skill.council", "capabilities/skills/skill.council.skill.json"),
    (
        "wf.catalog-class.discovery-only",
        "capabilities/workflows/wf.catalog-class.discovery-only.wf.json",
    ),
    (
        "council.preset.catalog-class.editable",
        "capabilities/council/presets/council.preset.catalog-class.editable.preset.json",
    ),
)


def load_design() -> dict:
    """Load A1 DESIGN.json, or reconstruct samples from the scratch t0 tree.

    Production command-center/phase3/A1/DESIGN.json is ARC-0003's artifact and
    is absent on this worktree. The scratch estate already holds the three
    transcribed samples from a prior successful run; resume from those files
    rather than rewriting ARC-0003's output_path.
    """
    global _DESIGN_CACHE
    if _DESIGN_CACHE is not None:
        return _DESIGN_CACHE
    if DESIGN.is_file():
        _DESIGN_CACHE = json.loads(DESIGN.read_text(encoding="utf-8"))
        return _DESIGN_CACHE
    t0 = FIX / "estate" / "t0-baseline"
    samples: list[dict] = []
    for cap_id, rel in FALLBACK_SAMPLE_RELS:
        path = t0 / rel
        if not path.is_file():
            raise FileNotFoundError(
                f"ARC-0004 DESIGN.json absent and fixture {rel} missing"
            )
        body = json.loads(path.read_text(encoding="utf-8"))
        samples.append(
            {
                "id": cap_id,
                "source_id": body.get("source_id"),
                "transcription": {"config": dict(body)},
            }
        )
    load_order = list(FALLBACK_LOAD_ORDER)
    man = t0 / "MANIFEST.json"
    if man.is_file():
        listed = json.loads(man.read_text(encoding="utf-8")).get("load_order") or []
        if listed:
            load_order = [{"path": p} for p in listed]
    _DESIGN_CACHE = {
        "architecture_id": "A1",
        "samples": samples,
        "load_order": load_order,
        "_source": "arc-0004-fixture-resume",
    }
    return _DESIGN_CACHE


def wipe(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _sample(design: dict, cap_id: str) -> dict:
    for row in design.get("samples") or []:
        if row.get("id") == cap_id:
            return row
    raise KeyError(cap_id)


def capability_files(root: Path) -> list[Path]:
    cap = root / "capabilities"
    if not cap.is_dir():
        return []
    return sorted(p for p in cap.rglob("*") if p.is_file())


def refresh_manifest(root: Path, design: dict) -> None:
    files: list[dict[str, str]] = []
    for path in capability_files(root):
        rel = path.relative_to(root).as_posix()
        files.append({"path": rel, "sha256": sha256_file(path)})
    prec = root / "precedence.json"
    if prec.is_file():
        files.append(
            {"path": "precedence.json", "sha256": sha256_file(prec)}
        )
    dump(
        root / "MANIFEST.json",
        {
            "architecture_id": "A1",
            "form": "static-config/v1",
            "load_order": [row["path"] for row in (design.get("load_order") or [])],
            "files": files,
            "notes": (
                "A file absent from MANIFEST.json.files is not loaded, even if "
                "it sits under capabilities/."
            ),
        },
    )


def _from_design_sample(sample: dict, kind: str, extra: dict | None = None) -> dict:
    body = dict(sample.get("transcription", {}).get("config") or {})
    body.update(
        {
            "id": sample["id"],
            "kind": kind,
            "form": "static-config/v1",
            "source_id": sample.get("source_id"),
        }
    )
    if extra:
        body.update(extra)
    return body


def write_baseline(root: Path, design: dict) -> None:
    wipe(root)
    root.mkdir(parents=True, exist_ok=True)

    skill = _from_design_sample(_sample(design, "skill.council"), "skill")
    wf = _from_design_sample(
        _sample(design, "wf.catalog-class.discovery-only"), "workflow_blueprint"
    )
    preset = _from_design_sample(
        _sample(design, "council.preset.catalog-class.editable"),
        "council_preset",
        extra={"protocol_id": "council.protocol.catalog-class"},
    )
    protocol = {
        "id": "council.protocol.catalog-class",
        "kind": "council_protocol",
        "form": "static-config/v1",
        "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
        "voting": {"quorum": 4, "rule": "unanimous-or-record-dissent"},
        "stopping": {"max_rounds": 8, "on_timeout": "halt", "on_unresolved": "BLOCKED"},
        "notes": "Declarative protocol the catalog-class preset references.",
    }
    rule = {
        "id": "rule.no-secrets",
        "kind": "rule",
        "form": "static-config/v1",
        "statement": "Do not print, rotate, or commit API keys or tokens.",
        "enforcement": "review-surface",
    }
    hook = {
        "id": "hook.pre-tool",
        "kind": "hook",
        "form": "static-config/v1",
        "event": "pre-tool",
        "script": "hooks/pre-tool.py",
        "enabled": True,
    }
    mcp = {
        "id": "mcp.stdio.example",
        "kind": "mcp_mount",
        "form": "static-config/v1",
        "transport": "stdio",
        "command": "example-server",
        "tools_allow": ["list", "read"],
        "description": "Example MCP mount used as the gateway activated-set third class.",
    }
    dump(root / "capabilities/skills/skill.council.skill.json", skill)
    dump(root / "capabilities/workflows/wf.catalog-class.discovery-only.wf.json", wf)
    dump(
        root / "capabilities/council/presets/council.preset.catalog-class.editable.preset.json",
        preset,
    )
    dump(
        root / "capabilities/council/protocols/council.protocol.catalog-class.protocol.json",
        protocol,
    )
    dump(root / "capabilities/rules/rule.no-secrets.rule.json", rule)
    dump(root / "capabilities/hooks/hook.pre-tool.hook.json", hook)
    dump(root / "capabilities/mcp/mcp.stdio.example.mount.json", mcp)
    dump(
        root / "precedence.json",
        {
            "rule": (
                "When two loaded files declare the same capability id, the file "
                "with the greater load_order replaces the earlier declaration entirely."
            ),
            "tie_break": (
                "Equal load_order: the path with the greater UTF-8 lexicographic "
                "order wins. No timestamp, no mtime, no runtime coin-flip."
            ),
            "duplicate_in_one_file": "FAIL-CLOSED: the file is invalid and the load aborts.",
            "merge": "No field-level merge. Replacement is whole-object.",
            "no_generated_layer": True,
            "no_resident_runtime": True,
        },
    )
    refresh_manifest(root, design)


ADDITIONS = [
    {
        "kind": "skill",
        "id": "skill.arc0004.marginal-probe",
        "rel": "capabilities/skills/skill.arc0004.marginal-probe.skill.json",
        "body": {
            "id": "skill.arc0004.marginal-probe",
            "kind": "skill",
            "form": "static-config/v1",
            "frontmatter": {
                "name": "arc0004-marginal-probe",
                "description": (
                    "Scratch skill added to measure A1 authoring cost. Four-voice "
                    "prompt sections only. No CouncilSpec. No executable policy."
                ),
            },
            "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
            "instructions": (
                "Invoke the four named roles as static prompt sections. Count this "
                "file as one real skill addition under config-first. Do not evaluate "
                "predicates over prior rounds."
            ),
            "councilspec": False,
            "runtime": False,
            "schema": False,
            "origin": "ARC-0004-scratch",
        },
    },
    {
        "kind": "workflow_blueprint",
        "id": "wf.arc0004.marginal-probe",
        "rel": "capabilities/workflows/wf.arc0004.marginal-probe.wf.json",
        "body": {
            "id": "wf.arc0004.marginal-probe",
            "kind": "workflow_blueprint",
            "form": "static-config/v1",
            "discovery_only": True,
            "stages": [
                {
                    "id": "measure",
                    "kind": "static-scan",
                    "inputs": ["scratch-tree"],
                    "outputs": ["numstat.json"],
                },
                {
                    "id": "record",
                    "kind": "write-config",
                    "inputs": ["numstat.json"],
                    "outputs": ["cost-addition.json"],
                },
            ],
            "gates": [
                {"id": "human-ack", "when": "before-publish", "type": "checkpoint"}
            ],
            "stopping": {"max_stages": 2, "on_error": "halt"},
            "roles": ["scanner"],
            "tool_policy": {"allow": ["Read", "Grep", "Glob"]},
        },
    },
    {
        "kind": "council_preset",
        "id": "council.preset.arc0004.marginal-probe",
        "rel": (
            "capabilities/council/presets/"
            "council.preset.arc0004.marginal-probe.preset.json"
        ),
        "body": {
            "id": "council.preset.arc0004.marginal-probe",
            "kind": "council_preset",
            "form": "static-config/v1",
            "protocol_id": "council.protocol.catalog-class",
            "editable": True,
            "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
            "voting": {"quorum": 4, "rule": "unanimous-or-record-dissent"},
            "consensus": {
                "reducer": "shared-completion-predicate-name",
                "local_completion_forbidden": True,
            },
            "anti_failure": {
                "no_silent_average": True,
                "on_split": "surface-disagreement",
            },
            "audit": {"hash_inputs": True, "persist_transcript": True},
            "stopping": {
                "max_rounds": 8,
                "on_timeout": "halt",
                "on_unresolved": "BLOCKED",
            },
        },
    },
]


def apply_addition(root: Path, design: dict, spec: dict) -> Path:
    dest = root / spec["rel"]
    dump(dest, spec["body"])
    refresh_manifest(root, design)
    return dest


def copy_tree(src: Path, dest: Path) -> None:
    wipe(dest)
    shutil.copytree(src, dest)


def build_snapshots() -> dict[str, Path]:
    design = load_design()
    base = FIX / "estate"
    t0 = base / "t0-baseline"
    snaps = {"t0": t0}
    write_baseline(t0, design)
    prev = t0
    for i, spec in enumerate(ADDITIONS, start=1):
        nxt = base / f"t{i}-{spec['kind']}"
        copy_tree(prev, nxt)
        apply_addition(nxt, design, spec)
        snaps[f"t{i}"] = nxt
        snaps[spec["kind"]] = nxt
        prev = nxt
    return snaps


def host_candidates() -> list[dict]:
    rows = []
    for p in (
        REPO / "command-center/control-plane/A1",
        REPO / "rules",
        Path.home() / ".claude",
        Path.home() / ".claude" / "rules",
        Path.home() / ".claude",
        Path.home() / ".cursor" / "rules",
    ):
        n = 0
        if p.is_dir():
            n = sum(1 for q in p.rglob("*") if q.is_file())
        rows.append(
            {
                "path": str(p),
                "exists": p.exists(),
                "is_dir": p.is_dir(),
                "file_count": n,
            }
        )
    return rows


host_candidates = host_candidates
build_snapshots = build_snapshots
