"""Plant three duplicate shapes and three distinct decoys into the real IR corpus."""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from differ import all_items  # noqa: E402
from ir import load_base_corpus, load_catalog_units, unit_to_ir  # noqa: E402

RENAME_HOST = "WFA-0007"
FORK_HOST = "WFA-0094"
PARAPHRASE_HOST = "WFA-0044"
SHAPES = ("exact-rename", "one-parameter-fork", "reworded-paraphrase")


def _require(index: dict[str, dict[str, Any]], uid: str) -> dict[str, Any]:
    ir = index.get(uid)
    if ir is None:
        raise RuntimeError(f"host {uid} missing from real IR corpus")
    return ir


def _rewrite_prose(text: str, salt: str) -> str:
    swapped = (
        str(text)
        .replace("the ", "a ")
        .replace("The ", "A ")
        .replace("must ", "has to ")
        .replace("workflow", "process")
        .replace("differ", "comparator")
    )
    return f"Reworded paraphrase ({salt}): {swapped}"


def exact_rename(host: dict[str, Any]) -> dict[str, Any]:
    plant = copy.deepcopy(host)
    plant["id"] = f"{host['id']}--exact-rename"
    plant["name"] = f"{host.get('name') or host['id']} renamed-copy"
    plant["corpus_kind"] = "planted-mutant"
    plant["plant_shape"] = "exact-rename"
    plant["host_id"] = host["id"]
    return plant


def one_parameter_fork(host: dict[str, Any]) -> dict[str, Any]:
    plant = copy.deepcopy(host)
    plant["id"] = f"{host['id']}--one-parameter-fork"
    plant["corpus_kind"] = "planted-mutant"
    plant["plant_shape"] = "one-parameter-fork"
    plant["host_id"] = host["id"]
    tools = list(plant.get("tools") or [])
    tools.append(
        {
            "id": "tool-fork-parameter",
            "token": f"wfa0096 one parameter fork {host['id']}",
            "source_anchor": "command-center/p2-wave/probes/WFA-0096/plant.py#one_parameter_fork",
        }
    )
    plant["tools"] = tools
    return plant


def reworded_paraphrase(host: dict[str, Any]) -> dict[str, Any]:
    plant = copy.deepcopy(host)
    plant["id"] = f"{host['id']}--reworded-paraphrase"
    plant["name"] = _rewrite_prose(str(host.get("name") or host["id"]), host["id"])
    plant["description"] = _rewrite_prose(str(host.get("description") or ""), host["id"])
    plant["corpus_kind"] = "planted-mutant"
    plant["plant_shape"] = "reworded-paraphrase"
    plant["host_id"] = host["id"]
    return plant


def _max_score_to_sets(ir: dict[str, Any], corpus_sets: list[frozenset[str]]) -> float:
    a = all_items(ir)
    best = 0.0
    for other in corpus_sets:
        union = len(a | other)
        score = 1.0 if union == 0 else len(a & other) / union
        if score > best:
            best = score
    return best


def select_decoy_sources(
    base: list[dict[str, Any]],
    *,
    ceiling: float,
) -> list[dict[str, Any]]:
    """Pick three real non-WFA catalog units that stay below the duplicate threshold."""
    units = load_catalog_units()
    preferred = ("CNF-", "BLD-", "AUD-", "ARC-", "IMP-")
    corpus_sets = [all_items(ir) for ir in base]
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for unit in units:
        uid = str(unit["id"])
        if uid.startswith("WFA-"):
            continue
        if not uid.startswith(preferred):
            continue
        ir = unit_to_ir(unit)
        mx = _max_score_to_sets(ir, corpus_sets)
        if mx >= ceiling:
            continue
        scored.append((mx, uid, ir))
    scored.sort(key=lambda row: (row[0], row[1]))
    picked: list[dict[str, Any]] = []
    used_prefix: set[str] = set()
    for _mx, uid, ir in scored:
        prefix = uid.split("-", 1)[0]
        if prefix in used_prefix and len(picked) < 3:
            continue
        used_prefix.add(prefix)
        picked.append(ir)
        if len(picked) == 3:
            break
    if len(picked) < 3:
        for _mx, uid, ir in scored:
            if ir["id"] in {p["id"] for p in picked}:
                continue
            picked.append(ir)
            if len(picked) == 3:
                break
    if len(picked) < 3:
        raise RuntimeError(
            f"could not find 3 genuine decoys below ceiling {ceiling}; got {len(picked)}"
        )
    return picked


def plant_decoy(source: dict[str, Any], index: int) -> dict[str, Any]:
    plant = copy.deepcopy(source)
    plant["id"] = f"{source['id']}--decoy-distinct"
    plant["name"] = f"distinct decoy {index} from {source['id']}"
    plant["corpus_kind"] = "planted-decoy"
    plant["plant_shape"] = "genuinely-distinct"
    plant["host_id"] = source["id"]
    plant["decoy_index"] = index
    return plant


def plant_into_corpus(
    base: list[dict[str, Any]] | None = None,
    *,
    threshold: float,
) -> dict[str, Any]:
    corpus = list(base if base is not None else load_base_corpus())
    if any(str(ir.get("corpus_kind") or "").startswith("planted") for ir in corpus):
        raise RuntimeError("base corpus already contains plants; refusing double-plant")
    index = {str(ir["id"]): ir for ir in corpus}
    hosts = {
        "exact-rename": _require(index, RENAME_HOST),
        "one-parameter-fork": _require(index, FORK_HOST),
        "reworded-paraphrase": _require(index, PARAPHRASE_HOST),
    }
    mutants = [
        exact_rename(hosts["exact-rename"]),
        one_parameter_fork(hosts["one-parameter-fork"]),
        reworded_paraphrase(hosts["reworded-paraphrase"]),
    ]
    decoy_sources = select_decoy_sources(corpus, ceiling=threshold)
    decoys = [plant_decoy(src, i + 1) for i, src in enumerate(decoy_sources)]
    planted_ids = {p["id"] for p in mutants + decoys}
    if len(planted_ids) != 6:
        raise RuntimeError(f"expected 6 unique plants, got {sorted(planted_ids)}")
    augmented = corpus + mutants + decoys
    return {
        "base": corpus,
        "augmented": augmented,
        "mutants": mutants,
        "decoys": decoys,
        "hosts": {shape: hosts[shape]["id"] for shape in hosts},
        "base_count": len(corpus),
        "augmented_count": len(augmented),
        "planted_into_real_corpus": True,
        "toy_fixture": False,
    }
