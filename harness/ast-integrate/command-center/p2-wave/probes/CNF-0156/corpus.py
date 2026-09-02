#!/usr/bin/env python3
"""Shared planted-control corpus for CNF-0156.

CNF-0133's catalog receipt is absent on this worktree. This module materializes
the labelled planted-true / planted-false set as a local fixture whose mutation
oracle is the on-disk fixture bytes (independent of confirmer verdicts).

Ground-truth labels live ONLY in oracle.json. Dispatch payloads are built from
dispatch_items.json and MUST NOT contain those labels.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
ORACLE_PATH = HERE / "oracle.json"
DISPATCH_PATH = HERE / "dispatch_items.json"
PAYLOAD_DIR = HERE / "payloads"
IDENTICAL_PAYLOAD = PAYLOAD_DIR / "identical.json"

LEAK_TOKENS = (
    "planted_label",
    "ground_truth",
    "ground-truth",
    "planted-true",
    "planted-false",
    "planted_true",
    "planted_false",
    '"label":',
    "oracle.json",
)

MISSING_REL = "command-center/p2-wave/probes/CNF-0156/fixtures/no-such-c156.dat"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def canonical_dumps(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def opaque_id(pair: str, arm: str) -> str:
    digest = hashlib.sha256(f"cnf-0156|{pair}|{arm}".encode("utf-8")).hexdigest()[:8]
    return f"c156-{digest}"


def _rel(name: str) -> str:
    return f"command-center/p2-wave/probes/CNF-0156/fixtures/{name}"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def write_fixtures() -> dict[str, Path]:
    FIX.mkdir(parents=True, exist_ok=True)
    files = {
        "alpha.txt": (
            "CNF-0156 planted fixture alpha\n"
            "This file is the sha256-eq control subject.\n"
            "Do not put confirmer labels in this body.\n"
        ),
        "beta.json": json.dumps(
            {"kind": "skill", "name": "planted-control", "id": "c156-beta"},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "gamma.md": "".join(f"gamma-line-{i}\n" for i in range(1, 8)),
        "epsilon.txt": (
            "CNF-0156 epsilon fixture\n"
            "CNF156SPAN-LEFT\n"
            "CNF156SPAN-RIGHT\n"
            "end of epsilon\n"
        ),
        "zeta.txt": "zeta planted-existence subject\n",
    }
    out: dict[str, Path] = {}
    for name, body in files.items():
        path = FIX / name
        _write_text(path, body)
        out[name] = path
    delta = FIX / "delta.bin"
    delta.write_bytes(b"PLANTED1" + b"\x00\x01\x02\x03DEAD")
    out["delta.bin"] = delta
    missing = FIX / "no-such-c156.dat"
    if missing.exists():
        missing.unlink()
    return out


def _item(
    *,
    pair: str,
    arm: str,
    statement: str,
    evidence: dict[str, Any],
    identity: str,
    ground: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cid = opaque_id(pair, arm)
    dispatch = {"id": cid, "statement": statement, "evidence": evidence}
    oracle = {
        "id": cid,
        "pair": pair,
        "arm": arm,
        "ground_truth": ground,
        "identity": identity,
    }
    return dispatch, oracle


def build_items() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    files = write_fixtures()
    alpha_sha = hashlib.sha256(files["alpha.txt"].read_bytes()).hexdigest()
    mutated = alpha_sha[:-1] + ("0" if alpha_sha[-1] != "0" else "1")
    gamma_lines = files["gamma.md"].read_text(encoding="utf-8").splitlines()
    if len(gamma_lines) != 7:
        raise RuntimeError(f"gamma line count {len(gamma_lines)} != 7")

    specs = [
        _item(
            pair="sha256-alpha",
            arm="pos",
            statement=f"The SHA-256 digest of fixtures/alpha.txt equals {alpha_sha}.",
            evidence={
                "path": _rel("alpha.txt"),
                "kind": "sha256_eq",
                "asserted": alpha_sha,
            },
            identity=_rel("alpha.txt") + "#sha256",
            ground="planted-true",
        ),
        _item(
            pair="sha256-alpha",
            arm="neg",
            statement=f"The SHA-256 digest of fixtures/alpha.txt equals {mutated}.",
            evidence={
                "path": _rel("alpha.txt"),
                "kind": "sha256_eq",
                "asserted": mutated,
            },
            identity=_rel("alpha.txt") + "#sha256-mutant",
            ground="planted-false",
        ),
        _item(
            pair="json-beta",
            arm="pos",
            statement="The JSON object at fixtures/beta.json has kind equal to skill.",
            evidence={
                "path": _rel("beta.json"),
                "kind": "json_field_eq",
                "json_path": ["kind"],
                "asserted": "skill",
            },
            identity=_rel("beta.json") + "#kind",
            ground="planted-true",
        ),
        _item(
            pair="json-beta",
            arm="neg",
            statement="The JSON object at fixtures/beta.json has kind equal to workflow.",
            evidence={
                "path": _rel("beta.json"),
                "kind": "json_field_eq",
                "json_path": ["kind"],
                "asserted": "workflow",
            },
            identity=_rel("beta.json") + "#kind-mutant",
            ground="planted-false",
        ),
        _item(
            pair="lines-gamma",
            arm="pos",
            statement="fixtures/gamma.md contains exactly 7 lines.",
            evidence={
                "path": _rel("gamma.md"),
                "kind": "line_count_eq",
                "asserted": 7,
            },
            identity=_rel("gamma.md") + "#lines",
            ground="planted-true",
        ),
        _item(
            pair="lines-gamma",
            arm="neg",
            statement="fixtures/gamma.md contains exactly 99 lines.",
            evidence={
                "path": _rel("gamma.md"),
                "kind": "line_count_eq",
                "asserted": 99,
            },
            identity=_rel("gamma.md") + "#lines-mutant",
            ground="planted-false",
        ),
        _item(
            pair="prefix-delta",
            arm="pos",
            statement="The first eight bytes of fixtures/delta.bin are PLANTED1.",
            evidence={
                "path": _rel("delta.bin"),
                "kind": "bytes_prefix_eq",
                "asserted": "PLANTED1",
            },
            identity=_rel("delta.bin") + "#prefix",
            ground="planted-true",
        ),
        _item(
            pair="prefix-delta",
            arm="neg",
            statement="The first eight bytes of fixtures/delta.bin are PLANTED9.",
            evidence={
                "path": _rel("delta.bin"),
                "kind": "bytes_prefix_eq",
                "asserted": "PLANTED9",
            },
            identity=_rel("delta.bin") + "#prefix-mutant",
            ground="planted-false",
        ),
        _item(
            pair="span-epsilon",
            arm="pos",
            statement=(
                "fixtures/epsilon.txt contains the spanning token "
                "CNF156SPAN-LEFT then a newline then CNF156SPAN-RIGHT."
            ),
            evidence={
                "path": _rel("epsilon.txt"),
                "kind": "substring_present",
                "asserted": "CNF156SPAN-LEFT\nCNF156SPAN-RIGHT",
            },
            identity=_rel("epsilon.txt") + "#spanning-substring",
            ground="planted-true",
        ),
        _item(
            pair="span-epsilon",
            arm="neg",
            statement="fixtures/epsilon.txt contains the token CNF156SPAN-ABSENT.",
            evidence={
                "path": _rel("epsilon.txt"),
                "kind": "substring_present",
                "asserted": "CNF156SPAN-ABSENT",
            },
            identity=_rel("epsilon.txt") + "#absent-substring",
            ground="planted-false",
        ),
        _item(
            pair="exists-zeta",
            arm="pos",
            statement="The planted fixture fixtures/zeta.txt exists on disk.",
            evidence={"path": _rel("zeta.txt"), "kind": "file_exists"},
            identity=_rel("zeta.txt") + "#exists",
            ground="planted-true",
        ),
        _item(
            pair="exists-zeta",
            arm="neg",
            statement="The planted fixture fixtures/no-such-c156.dat exists on disk.",
            evidence={"path": MISSING_REL, "kind": "file_exists"},
            identity=MISSING_REL + "#exists-mutant",
            ground="planted-false",
        ),
    ]
    dispatch = [d for d, _ in specs]
    oracle = [o for _, o in specs]
    dispatch.sort(key=lambda r: r["id"])
    oracle.sort(key=lambda r: r["id"])
    return dispatch, oracle


def payload_obj(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "unit": "CNF-0156",
        "instruction": (
            "For each item, emit CONFIRMED if the evidence assertion holds on "
            "the cited path, otherwise REFUTED. Inspect disk bytes only. Do not "
            "infer labels. Blocking foreground only. Prompt-by-file. Never "
            "convert a vendor-side 429 or 529 into REFUTED."
        ),
        "items": list(items),
    }


def leakage_hits(raw: bytes) -> list[str]:
    text = raw.decode("utf-8")
    hits = [tok for tok in LEAK_TOKENS if tok in text]
    if ORACLE_PATH.is_file():
        oracle_raw = ORACLE_PATH.read_bytes()
        if oracle_raw and oracle_raw in raw:
            hits.append("oracle-bytes-embedded")
    return hits


def write_corpus() -> dict[str, Any]:
    dispatch, oracle = build_items()
    payload = payload_obj(dispatch)
    raw = canonical_dumps(payload)
    hits = leakage_hits(raw)
    if hits:
        raise RuntimeError(f"payload leakage {hits}")
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    IDENTICAL_PAYLOAD.write_bytes(raw)
    DISPATCH_PATH.write_text(
        json.dumps({"items": dispatch}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    ORACLE_PATH.write_text(
        json.dumps({"items": oracle}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "dispatch": dispatch,
        "oracle": oracle,
        "payload": payload,
        "payload_bytes": raw,
        "payload_sha256": sha256_bytes(raw),
        "payload_size": len(raw),
    }


def load_oracle() -> dict[str, str]:
    doc = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
    return {row["id"]: row["ground_truth"] for row in doc["items"]}


def load_oracle_rows() -> list[dict[str, Any]]:
    return list(json.loads(ORACLE_PATH.read_text(encoding="utf-8"))["items"])


def load_dispatch_items() -> list[dict[str, Any]]:
    return list(json.loads(DISPATCH_PATH.read_text(encoding="utf-8"))["items"])


if __name__ == "__main__":
    info = write_corpus()
    print(
        f"corpus n={len(info['dispatch'])} "
        f"sha256={info['payload_sha256']} bytes={info['payload_size']}"
    )
    print("SUCCESS:CNF-0156-corpus")
