"""Fixture hybrid estate for ARC-0063 staged adoption.

Each stage writes artifacts that exist at that stage. Later stages must not
rewrite earlier control-plane files (forward preservation). A1 trees are an
import source, never a second live catalog.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CANARY_SECRET = "CANARY-SECRET:arc0063-not-for-vendor"
PLANTED_BYPASS = "side-door:marketplace-activate-without-eval"
S1_EVALUATOR_REL = "hybrid/permission-evaluator.json"
ENUMERATED_PATHS = [
    "install-time:package-unpack",
    "activation-time:gateway-select",
    "dispatch-time:adapter-forward",
    "workflow-invocation-time:ledger-dispatch",
]

STAGE_IDS = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj: Any) -> None:
    write_text(path, dumps(obj))


def snapshot_hybrid(root: Path) -> dict[str, str]:
    hybrid = root / "hybrid"
    if not hybrid.is_dir():
        return {}
    out: dict[str, str] = {}
    for p in sorted(hybrid.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = sha256_file(p)
    return out


def baseline_files() -> dict[str, str]:
    return {
        "README.txt": (
            "ARC-0063 fixture estate: pre-hybrid baseline. "
            "No hybrid/ control planes exist yet. PR-ONLY: later stages land as commits, not deploys.\n"
        )
    }


def stage_files(stage_id: str) -> dict[str, str]:
    if stage_id == "S1":
        return {
            S1_EVALUATOR_REL: dumps(
                {
                    "id": "a7-single-choke",
                    "authority": "permission-evaluator",
                    "borrowed_from": "A7",
                    "covered_paths": list(ENUMERATED_PATHS),
                    "unique": True,
                }
            ),
            "hybrid/enumerated-paths.json": dumps(
                {
                    "paths": list(ENUMERATED_PATHS),
                    "times": [
                        "install-time",
                        "activation-time",
                        "dispatch-time",
                        "workflow-invocation-time",
                    ],
                    "source": "catalog ARC-0062 question (A9 security entry-path enumeration)",
                }
            ),
            "hybrid/planted-bypass.json": dumps(
                {
                    "path": PLANTED_BYPASS,
                    "crosses_evaluator": False,
                    "role": "detector-control",
                }
            ),
            "hybrid/control-planes.json": dumps(
                {
                    "rows": [
                        {
                            "capability_class": "permission-evaluation",
                            "authority": "permission-evaluator",
                            "lands_at_stage": "S1",
                            "borrowed_from": "A7",
                        }
                    ]
                }
            ),
        }
    if stage_id == "S2":
        registry = {
            "schema": "a2-registry/v1",
            "authority": "generated-ssot-registry",
            "borrowed_from": "A2",
            "a1_is_import_only": True,
            "entries": [
                {
                    "id": "skill.council",
                    "kind": "skill",
                    "sha256": "pending",
                },
                {
                    "id": "wf.catalog-class.discovery-only",
                    "kind": "workflow_blueprint",
                    "sha256": "pending",
                },
            ],
        }
        generated = {
            "id": "skill.council",
            "kind": "skill",
            "provenance": {
                "registry_id": "skill.council",
                "generator_version": "1.0.0",
            },
            "body": "Four-voice prompt skill. No executable policy.",
        }
        a1_import = {
            "id": "skill.council",
            "kind": "skill",
            "form": "static-config/v1",
            "body": "Four-voice prompt skill. No executable policy.",
            "live_unique_line": "LIVE-ONLY-LINE:synthetic-ARC-0063-a1-remainder",
        }
        return {
            "hybrid/registry.json": dumps(registry),
            "hybrid/generated/skill.council.json": dumps(generated),
            "hybrid/a1-import/skill.council.skill.json": dumps(a1_import),
            "hybrid/adjudication-queue.json": dumps(
                {
                    "held": [
                        {
                            "path": "hybrid/a1-import/skill.council.skill.json",
                            "line": "LIVE-ONLY-LINE:synthetic-ARC-0063-a1-remainder",
                            "decision": "QUEUE-NOT-DROP",
                        }
                    ]
                }
            ),
            "hybrid/load-order.json": dumps(
                {
                    "authority_order": [
                        "hybrid/permission-evaluator.json",
                        "hybrid/registry.json",
                        "hybrid/generated/",
                    ],
                    "not_authority": ["hybrid/a1-import/"],
                    "note": "A1 trees are extract sources. Catalog authority is the A2 registry only.",
                }
            ),
            "hybrid/control-planes.json": dumps(
                {
                    "rows": [
                        {
                            "capability_class": "permission-evaluation",
                            "authority": "permission-evaluator",
                            "lands_at_stage": "S1",
                            "borrowed_from": "A7",
                        },
                        {
                            "capability_class": "capability-identity",
                            "authority": "generated-ssot-registry",
                            "lands_at_stage": "S2",
                            "borrowed_from": "A2",
                            "not_authority": "A1-static-tree (import only)",
                        },
                    ]
                }
            ),
        }
    if stage_id == "S3":
        return {
            "hybrid/gateway-index.json": dumps(
                {
                    "authority": "gateway-activation",
                    "borrowed_from": "A4",
                    "ids": [
                        "skill.council",
                        "wf.catalog-class.discovery-only",
                    ],
                    "indexes_registry": True,
                }
            ),
            "hybrid/activation-log.json": dumps(
                {
                    "events": [
                        {
                            "capability_id": "skill.council",
                            "state": "selected",
                            "permission_ticket": "a7-single-choke:skill.council",
                            "installed": True,
                        }
                    ]
                }
            ),
            "hybrid/resident-set.json": dumps(
                {
                    "when_nothing_selected": [
                        "hybrid/permission-evaluator.json",
                        "hybrid/gateway-index.json",
                    ],
                    "does_not_include": ["hybrid/generated/skill.council.json"],
                }
            ),
            "hybrid/selection-state.json": dumps(
                {
                    "not_installed": ["mcp.missing.example"],
                    "not_selected": ["wf.catalog-class.discovery-only"],
                    "selected": ["skill.council"],
                }
            ),
            "hybrid/control-planes.json": dumps(
                {
                    "rows": [
                        {
                            "capability_class": "permission-evaluation",
                            "authority": "permission-evaluator",
                            "lands_at_stage": "S1",
                            "borrowed_from": "A7",
                        },
                        {
                            "capability_class": "capability-identity",
                            "authority": "generated-ssot-registry",
                            "lands_at_stage": "S2",
                            "borrowed_from": "A2",
                        },
                        {
                            "capability_class": "activation-resident-set",
                            "authority": "gateway-activation",
                            "lands_at_stage": "S3",
                            "borrowed_from": "A4",
                        },
                    ]
                }
            ),
        }
    if stage_id == "S4":
        pkg = {
            "package": "pkg-skill-council",
            "registry_id": "skill.council",
            "bytes": "skill-council-payload",
        }
        pkg_raw = dumps(pkg)
        return {
            "hybrid/packages/pkg-skill-council.json": pkg_raw,
            "hybrid/lockfile.json": dumps(
                {
                    "authority": "package-lockfile",
                    "borrowed_from": "A3",
                    "publish_channel": None,
                    "release_mode": "PR-ONLY",
                    "pins": {
                        "pkg-skill-council": sha256_bytes(pkg_raw.encode("utf-8")),
                    },
                }
            ),
            "hybrid/package-map.json": dumps(
                {
                    "pkg-skill-council": "skill.council",
                    "note": "packages name registry ids; they are not a second catalog",
                }
            ),
            "hybrid/control-planes.json": dumps(
                {
                    "rows": [
                        {
                            "capability_class": "permission-evaluation",
                            "authority": "permission-evaluator",
                            "lands_at_stage": "S1",
                            "borrowed_from": "A7",
                        },
                        {
                            "capability_class": "capability-identity",
                            "authority": "generated-ssot-registry",
                            "lands_at_stage": "S2",
                            "borrowed_from": "A2",
                        },
                        {
                            "capability_class": "activation-resident-set",
                            "authority": "gateway-activation",
                            "lands_at_stage": "S3",
                            "borrowed_from": "A4",
                        },
                        {
                            "capability_class": "package-identity",
                            "authority": "package-lockfile",
                            "lands_at_stage": "S4",
                            "borrowed_from": "A3",
                            "not_authority": "public-marketplace-index (PR-ONLY: publish_channel is null)",
                        },
                    ]
                }
            ),
        }
    if stage_id == "S5":
        return {
            "hybrid/adapter-contract.json": dumps(
                {
                    "authority": "vendor-adapter",
                    "borrowed_from": "A6",
                    "fields": {
                        "unit_id": "GUARANTEED",
                        "artifact_schema": "GUARANTEED",
                        "permission_ticket": "GUARANTEED",
                        "streaming": "BEST-EFFORT",
                        "model_naming": "VENDOR-ONLY",
                    },
                }
            ),
            "hybrid/conformance-matrix.json": dumps(
                {
                    "vendors": {
                        "anthropic": ["GUARANTEED", "BEST-EFFORT", "VENDOR-ONLY"],
                        "openai": ["GUARANTEED", "BEST-EFFORT"],
                    },
                    "downgrade_refusal": {
                        "unit": "needs-GUARANTEED",
                        "vendor_lacking": "none-vendor",
                        "result": "FAIL-LOUD",
                    },
                }
            ),
            "hybrid/untrusted-forward-log.json": dumps(
                {
                    "forwarded": ["unit_id", "artifact_schema"],
                    "never_forward": [CANARY_SECRET],
                    "permission_ticket": "a7-single-choke:adapter-forward",
                }
            ),
            "hybrid/control-planes.json": dumps(
                {
                    "rows": [
                        {
                            "capability_class": "permission-evaluation",
                            "authority": "permission-evaluator",
                            "lands_at_stage": "S1",
                            "borrowed_from": "A7",
                        },
                        {
                            "capability_class": "capability-identity",
                            "authority": "generated-ssot-registry",
                            "lands_at_stage": "S2",
                            "borrowed_from": "A2",
                        },
                        {
                            "capability_class": "activation-resident-set",
                            "authority": "gateway-activation",
                            "lands_at_stage": "S3",
                            "borrowed_from": "A4",
                        },
                        {
                            "capability_class": "package-identity",
                            "authority": "package-lockfile",
                            "lands_at_stage": "S4",
                            "borrowed_from": "A3",
                        },
                        {
                            "capability_class": "vendor-contract",
                            "authority": "vendor-adapter",
                            "lands_at_stage": "S5",
                            "borrowed_from": "A6",
                        },
                    ]
                }
            ),
        }
    if stage_id == "S6":
        ledger_lines = [
            json.dumps(
                {
                    "seq": 1,
                    "unit_id": "ARC-0063-demo-1",
                    "state": "dispatched",
                    "permission_ticket": "a7-single-choke:ledger-dispatch",
                    "via_adapter": True,
                },
                sort_keys=True,
                ensure_ascii=True,
            ),
            json.dumps(
                {
                    "seq": 2,
                    "unit_id": "ARC-0063-demo-1",
                    "state": "duplicate-claim-rejected",
                    "winner": "dispatcher-a",
                    "loser": "dispatcher-b",
                },
                sort_keys=True,
                ensure_ascii=True,
            ),
        ]
        return {
            "hybrid/ledger.jsonl": "".join(line + "\n" for line in ledger_lines),
            "hybrid/in-flight.json": dumps(
                {
                    "units": ["ARC-0063-demo-2"],
                    "dropped": [],
                    "fold_ad_hoc_rails": True,
                }
            ),
            "hybrid/duplicate-dispatch.json": dumps(
                {
                    "unit_id": "ARC-0063-demo-1",
                    "winners": 1,
                    "claimants": 2,
                }
            ),
            "hybrid/control-planes.json": dumps(
                {
                    "rows": [
                        {
                            "capability_class": "permission-evaluation",
                            "authority": "permission-evaluator",
                            "lands_at_stage": "S1",
                            "borrowed_from": "A7",
                        },
                        {
                            "capability_class": "capability-identity",
                            "authority": "generated-ssot-registry",
                            "lands_at_stage": "S2",
                            "borrowed_from": "A2",
                        },
                        {
                            "capability_class": "activation-resident-set",
                            "authority": "gateway-activation",
                            "lands_at_stage": "S3",
                            "borrowed_from": "A4",
                        },
                        {
                            "capability_class": "package-identity",
                            "authority": "package-lockfile",
                            "lands_at_stage": "S4",
                            "borrowed_from": "A3",
                        },
                        {
                            "capability_class": "vendor-contract",
                            "authority": "vendor-adapter",
                            "lands_at_stage": "S5",
                            "borrowed_from": "A6",
                        },
                        {
                            "capability_class": "work-unit-delivery",
                            "authority": "runtime-ledger",
                            "lands_at_stage": "S6",
                            "borrowed_from": "A5",
                        },
                    ]
                }
            ),
        }
    if stage_id == "S7":
        return {
            "hybrid/error-contract.json": dumps(
                {
                    "authority": "product-error-surface",
                    "borrowed_from": "A8",
                    "required_fields": ["happened", "means", "next_action"],
                    "samples": [
                        {
                            "happened": "adapter refused silent downgrade",
                            "means": "vendor lacks GUARANTEED tier",
                            "next_action": "re-dispatch to a vendor that declares GUARANTEED or split the unit",
                        }
                    ],
                }
            ),
            "hybrid/aliases.json": dumps(
                {
                    "council": "skill.council",
                    "discover": "wf.catalog-class.discovery-only",
                }
            ),
            "hybrid/control-planes.json": dumps(
                {
                    "rows": [
                        {
                            "capability_class": "permission-evaluation",
                            "authority": "permission-evaluator",
                            "lands_at_stage": "S1",
                            "borrowed_from": "A7",
                        },
                        {
                            "capability_class": "capability-identity",
                            "authority": "generated-ssot-registry",
                            "lands_at_stage": "S2",
                            "borrowed_from": "A2",
                        },
                        {
                            "capability_class": "activation-resident-set",
                            "authority": "gateway-activation",
                            "lands_at_stage": "S3",
                            "borrowed_from": "A4",
                        },
                        {
                            "capability_class": "package-identity",
                            "authority": "package-lockfile",
                            "lands_at_stage": "S4",
                            "borrowed_from": "A3",
                        },
                        {
                            "capability_class": "vendor-contract",
                            "authority": "vendor-adapter",
                            "lands_at_stage": "S5",
                            "borrowed_from": "A6",
                        },
                        {
                            "capability_class": "work-unit-delivery",
                            "authority": "runtime-ledger",
                            "lands_at_stage": "S6",
                            "borrowed_from": "A5",
                        },
                        {
                            "capability_class": "operator-error-surface",
                            "authority": "product-error-surface",
                            "lands_at_stage": "S7",
                            "borrowed_from": "A8",
                        },
                    ]
                }
            ),
        }
    raise KeyError(stage_id)


def apply_files(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        write_text(root / rel, text)


def apply_stage(root: Path, stage_id: str, prior: dict[str, str] | None) -> dict[str, str]:
    incoming = stage_files(stage_id)
    if prior:
        for rel, digest in prior.items():
            if rel in incoming:
                continue
            path = root / rel
            if not path.is_file():
                raise FileNotFoundError(f"prior artifact missing before {stage_id}: {rel}")
            live = sha256_file(path)
            if live != digest:
                raise ValueError(
                    f"forward preservation failed at {stage_id}: {rel} sha {live} != {digest}"
                )
    apply_files(root, incoming)
    return snapshot_hybrid(root)


def build_through(root: Path, through: str = "S7") -> dict[str, str]:
    apply_files(root, baseline_files())
    prior: dict[str, str] = {}
    for sid in STAGE_IDS:
        prior = apply_stage(root, sid, prior if sid != "S1" else None)
        if sid == through:
            break
    return prior
