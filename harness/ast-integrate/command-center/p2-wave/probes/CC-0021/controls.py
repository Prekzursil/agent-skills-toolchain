#!/usr/bin/env python3
"""Executable controls for CC-0021. Shared by named probes and the emitter."""
from __future__ import annotations

from pathlib import Path

from corpus import (
    HARNESS_ID,
    MECH_IDS,
    OPTION_IDS,
    arch_file,
    ensure_corpus,
    estate_root,
    mention_root,
    option_md,
    planted_file,
    tree_paths,
)
from extractor import declaration_ids, extract
from resolver import gate, gate_root, resolve_tree

HERE = Path(__file__).resolve().parent


def harness_census() -> dict:
    ensure_corpus()
    hits = []
    files = set()
    for tree in tree_paths():
        for h in extract(tree, kind="M"):
            if h.number == HARNESS_ID:
                # Path relative to HERE so the two trees do not collide.
                full = (tree / h.path).resolve().relative_to(HERE.resolve()).as_posix()
                hits.append(full + f":{h.line}")
                files.add(full)
    return {
        "refs": len(hits),
        "files": len(files),
        "want_refs": 20,
        "want_files": 16,
        "ok": len(hits) == 20 and len(files) == 16,
        "sample": hits[:4],
    }


def mech_false_positive() -> dict:
    ensure_corpus()
    af = arch_file()
    bare_m = extract(af, kind="M")
    mech = extract(af, kind="MECH")
    ids = declaration_ids(af, kind="MECH")
    return {
        "bare_m_hits": len(bare_m),
        "mech_hits": len(mech),
        "mech_decl_ids": len(ids),
        "want_mech_ids": len(MECH_IDS),
        "ok": len(bare_m) == 0 and set(ids) == set(MECH_IDS),
        "sample_bare_m": [h.as_dict() for h in bare_m[:3]],
    }


def option_partition() -> dict:
    ensure_corpus()
    opt = set(declaration_ids(option_md(), kind="M"))
    # JSON twin lives beside the markdown.
    opt |= set(declaration_ids(estate_root() / "07-OPTION-UNIVERSE.json", kind="M"))
    mech = set(declaration_ids(arch_file(), kind="MECH"))
    inter = opt & mech
    opt_only = opt - mech
    mech_only = mech - opt
    return {
        "option": sorted(opt),
        "mech": sorted(mech),
        "intersection": sorted(inter),
        "option_only": sorted(opt_only),
        "mech_only": sorted(mech_only),
        "ok": (
            opt == set(OPTION_IDS)
            and mech == set(MECH_IDS)
            and len(inter) == 31
            and len(opt_only) == 2
            and len(mech_only) == 7
        ),
    }


def planted_fires() -> dict:
    ensure_corpus()
    g = gate_root(planted_file())
    return {
        "fired": g["fired"],
        "ambiguous_use_count": g["ambiguous_use_count"],
        "ok": g["fired"] is True and g["ambiguous_use_count"] >= 1,
        "sample": g["ambiguous_uses"][:3],
    }


def mention_silent() -> dict:
    ensure_corpus()
    rows = resolve_tree(mention_root())
    g = gate(rows)
    m_hits = [r for r in rows if r["kind"] == "M"]
    mentions = [r for r in m_hits if r["verdict"] == "MENTION"]
    return {
        "fired": g["fired"],
        "m_hits": len(m_hits),
        "mentions": len(mentions),
        "ok": g["fired"] is False and len(m_hits) >= 1 and len(mentions) == len(m_hits),
        "sample": m_hits[:5],
    }


def estate_silent() -> dict:
    ensure_corpus()
    g = gate_root(estate_root())
    return {
        "fired": g["fired"],
        "ambiguous_use_count": g["ambiguous_use_count"],
        "ok": g["fired"] is False,
        "sample": g["ambiguous_uses"][:5],
    }


def regex_agree() -> dict:
    ensure_corpus()
    root = estate_root()
    a = {h.key() for h in extract(root, kind="both", which="primary")}
    b = {h.key() for h in extract(root, kind="both", which="reviewer")}
    return {
        "primary": len(a),
        "reviewer": len(b),
        "only_primary": sorted(repr(x) for x in (a - b))[:8],
        "only_reviewer": sorted(repr(x) for x in (b - a))[:8],
        "ok": a == b and len(a) > 0,
    }


def run_all() -> dict:
    parts = {
        "harness_census": harness_census(),
        "mech_false_positive": mech_false_positive(),
        "option_partition": option_partition(),
        "planted_fires": planted_fires(),
        "mention_silent": mention_silent(),
        "estate_silent": estate_silent(),
        "regex_agree": regex_agree(),
    }
    parts["ok"] = all(v.get("ok") for v in parts.values() if isinstance(v, dict))
    return parts
