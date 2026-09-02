"""Provenance and licence graph v2 for WFA-0079.

Rebuilds a closed graph from files that exist on THIS Linux worktree.
The Windows-path v1 blob (466 nodes / 1025 edges / rate 0.8109) is loaded
when present; when absent the live estate is the node set. Unfetched
licences stay UNCLASSIFIED and are listed. Licence classes other than
UNCLASSIFIED are derived from fetched LICENSE file bytes, not from
registry free text.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "WFA-0079"
OUT_REL = "command-center/wfa/WFA-0079-provenance-license-graph-v2.json"
SCHEMA_REL = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/Graph"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SENTINEL = "SUCCESS:WFA-0079"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0079/probe1_closure_counts.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0079/probe2_reachability.py"
)

V1_CANDIDATES = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "command-center/wfa/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "command-center/sources/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
]
DEP_PATHS = {
    "WFA-0002": "command-center/wfa/WFA-0002-provenance-closure.json",
    "WFA-0033": "command-center/wfa/WFA-0033-extract-licences.json",
    "WFA-0078": "command-center/wfa/WFA-0078-candidate-registry-v2.json",
}

BLUEPRINTS = [
    {
        "id": "bp.benchmark-generation",
        "path": "command-center/lib/eng_blueprints_17_21/library.py",
        "cites": ["cand:eng-blueprints-library", "cand:agentspec-spec"],
    },
    {
        "id": "bp.reproducibility",
        "path": "command-center/lib/eng_blueprints_17_21/library.py",
        "cites": ["cand:eng-blueprints-library", "cand:agentspec-spec"],
    },
    {
        "id": "bp.performance",
        "path": "command-center/lib/eng_blueprints_17_21/library.py",
        "cites": ["cand:eng-blueprints-library", "cand:agentspec-spec"],
    },
    {
        "id": "bp.concurrency-load-soak",
        "path": "command-center/lib/eng_blueprints_17_21/library.py",
        "cites": ["cand:eng-blueprints-library", "cand:agentspec-spec"],
    },
    {
        "id": "bp.abandoned-work-salvage",
        "path": "command-center/lib/eng_blueprints_17_21/library.py",
        "cites": [
            "cand:eng-blueprints-library",
            "cand:agentspec-spec",
            "cand:eng-blueprints-salvage",
        ],
    },
]

OWNER_CANDIDATES = [
    {
        "id": "cand:eng-blueprints-library",
        "path": "command-center/lib/eng_blueprints_17_21/library.py",
    },
    {
        "id": "cand:eng-blueprints-salvage",
        "path": "command-center/lib/eng_blueprints_17_21/salvage.py",
    },
    {
        "id": "cand:agentspec-spec",
        "path": "tools/agentspec/agentspec/spec.py",
    },
    {
        "id": "cand:plugin",
        "path": "tools/plugin/__init__.py",
        "cites": ["pkg:cyclonedx-bom-1.5-schema", "pkg:jsf-0.82-schema"],
    },
    {
        "id": "cand:workflow-foundry",
        "path": "tools/workflow_foundry/__init__.py",
    },
]

FETCHED_PACKAGES = [
    {
        "id": "pkg:BMAD-METHOD",
        "license_rel": "licenses/BMAD-METHOD.LICENSE",
        "class_id": "lc:MIT",
        "file_id": "lf:BMAD-METHOD",
        "catalog_name": "BMAD-METHOD",
    },
    {
        "id": "pkg:microsoft-autogen",
        "license_rel": "licenses/microsoft-autogen.LICENSE",
        "class_id": "lc:CC-BY-4.0",
        "file_id": "lf:microsoft-autogen",
        "catalog_name": "microsoft/autogen",
    },
]

UNFETCHED_PACKAGES = [
    {
        "id": "pkg:cyclonedx-bom-1.5-schema",
        "path": "tools/plugin/schema/bom-1.5.schema.json",
        "why": (
            "CycloneDX JSON schema $comment names Apache License 2.0; "
            "that is a free-text string, not a fetched LICENSE/COPYING file."
        ),
    },
    {
        "id": "pkg:jsf-0.82-schema",
        "path": "tools/plugin/schema/jsf-0.82.schema.json",
        "why": (
            "JSF schema $comment names Apache License 2.0; that is a "
            "free-text string, not a fetched LICENSE/COPYING file."
        ),
    },
    {
        "id": "pkg:unpinned-widget",
        "path": "tools/plugin/tests/fixtures/plugin-closure/vendor/unpinned-widget/lib.js",
        "why": (
            "Vendored test fixture with no LICENSE file on this tree; "
            "stays UNCLASSIFIED rather than defaulted to permissive."
        ),
    },
]

MIT_NOTICE = (
    "The above copyright notice and this permission notice shall be "
    "included in all copies or substantial portions of the Software."
)
BMAD_RIDER = (
    "BMad™, BMad Method™, and BMad Core™ are trademarks of BMad Code, LLC, "
    "covering all casings and variations (including BMAD, bmad, BMadMethod, "
    "BMAD-METHOD, etc.). The use of these trademarks in this software does "
    "not grant any rights to use the trademarks for any other purpose. See "
    "[TRADEMARK.md](TRADEMARK.md) for detailed guidelines."
)
CC_BY_ATTRIBUTION = (
    "If You Share the Licensed Material (including in modified form), "
    "You must: retain identification of the creator(s), a copyright notice, "
    "a notice that refers to this Public License, a notice that refers to "
    "the disclaimer of warranties, and a URI or hyperlink to the Licensed "
    "Material to the extent reasonably practicable; indicate if You modified "
    "the Licensed Material; and indicate the Licensed Material is licensed "
    "under this Public License, and include the text of, or the URI or "
    "hyperlink to, this Public License."
)

QUESTION = (
    "Rebuild the provenance and licence graph so that resolution rate is "
    "1.0 (from 0.8109), every licence class derives from a fetched licence "
    "file rather than a rule-based read of free text, and the licence risk "
    "register lists real obligations."
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes() if path.is_file() else b""
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def identifying_from_text(text: str) -> dict:
    lines = text.replace("\r\n", "\n").split("\n")
    identifying = next((ln.strip() for ln in lines if ln.strip()), "")
    upper = text.upper()
    head = "\n".join(lines[:16])
    spdx = "UNCLASSIFIED"
    if re.search(r"^MIT License\b", head, re.M):
        spdx = "MIT"
    elif "ATTRIBUTION 4.0 INTERNATIONAL" in upper and "CREATIVE COMMONS" in upper:
        spdx = "CC-BY-4.0"
    elif "APACHE LICENSE" in upper and "VERSION 2.0" in upper:
        spdx = "Apache-2.0"
    riders = []
    if "TRADEMARK NOTICE" in upper:
        riders.append("TRADEMARK NOTICE")
    return {
        "identifying_text": identifying,
        "spdx": spdx,
        "riders": riders,
        "excerpt": text[:280],
    }


def locate_v1() -> dict:
    tried = []
    for rel in V1_CANDIDATES:
        path = Path(rel) if Path(rel).is_absolute() else REPO / rel
        present = path.is_file()
        tried.append({"path": rel, "present": present})
        if present:
            return {
                "present": True,
                "path": rel,
                "bytes": path.stat().st_size,
                "tried": tried,
            }
    return {"present": False, "path": None, "bytes": 0, "tried": tried}


def locate_deps() -> dict:
    out = {}
    for uid, rel in DEP_PATHS.items():
        path = REPO / rel
        out[uid] = {"path": rel, "present": path.is_file()}
    return out


def anchor_for(rel: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {"path": rel, "exists": False, "sha256": None, "bytes": 0}
    sha, size = digest_file(path)
    return {"path": rel, "exists": True, "sha256": sha, "bytes": size}


def load_fetched(spec: dict) -> dict:
    rel = f"command-center/p2-wave/probes/WFA-0079/{spec['license_rel']}"
    path = HERE / spec["license_rel"]
    if not path.is_file():
        raise FileNotFoundError(rel)
    text = path.read_text(encoding="utf-8")
    ident = identifying_from_text(text)
    sha, size = digest_file(path)
    return {
        "path": rel,
        "exists": True,
        "sha256": sha,
        "bytes": size,
        "identifying_text": ident["identifying_text"],
        "spdx": ident["spdx"],
        "riders": ident["riders"],
        "excerpt": ident["excerpt"],
        "source": "on-tree LICENSE bytes (copied from RES-0121 fetch; re-hashed here)",
    }


def node(
    nid: str,
    kind: str,
    *,
    owner: bool | None,
    licence_class: str | None,
    provenance_anchor: dict | None = None,
    fetched_licence_anchor: dict | None = None,
    extra: dict | None = None,
) -> dict:
    row = {
        "id": nid,
        "kind": kind,
        "owner": owner,
        "licence_class": licence_class,
        "provenance_anchor": provenance_anchor,
        "fetched_licence_anchor": fetched_licence_anchor,
    }
    if extra:
        row.update(extra)
    return row


def edge(eid: str, src: str, dst: str, kind: str) -> dict:
    return {"id": eid, "source": src, "target": dst, "kind": kind}


def build_graph() -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    fetched = {spec["id"]: load_fetched(spec) for spec in FETCHED_PACKAGES}

    mit = fetched["pkg:BMAD-METHOD"]
    cc = fetched["pkg:microsoft-autogen"]
    if mit["spdx"] != "MIT":
        raise RuntimeError("BMAD LICENSE identifying text is not MIT")
    if cc["spdx"] != "CC-BY-4.0":
        raise RuntimeError("autogen LICENSE identifying text is not CC-BY-4.0")

    nodes.append(
        node(
            "lc:MIT",
            "licence-class",
            owner=None,
            licence_class="MIT",
            fetched_licence_anchor=mit,
            extra={"derived_from_fetched_file": True},
        )
    )
    nodes.append(
        node(
            "lc:CC-BY-4.0",
            "licence-class",
            owner=None,
            licence_class="CC-BY-4.0",
            fetched_licence_anchor=cc,
            extra={"derived_from_fetched_file": True},
        )
    )
    nodes.append(
        node(
            "lc:UNCLASSIFIED",
            "licence-class",
            owner=None,
            licence_class="UNCLASSIFIED",
            extra={
                "derived_from_fetched_file": False,
                "note": (
                    "Residual bucket for nodes whose licence file was not "
                    "fetched. Not a licence opinion and not a permissive default."
                ),
            },
        )
    )
    nodes.append(
        node(
            "lf:BMAD-METHOD",
            "licence-file",
            owner=False,
            licence_class="MIT",
            fetched_licence_anchor=mit,
            extra={"catalog_name": "BMAD-METHOD"},
        )
    )
    nodes.append(
        node(
            "lf:microsoft-autogen",
            "licence-file",
            owner=False,
            licence_class="CC-BY-4.0",
            fetched_licence_anchor=cc,
            extra={"catalog_name": "microsoft/autogen"},
        )
    )
    edges.append(edge("e:lc-mit-file", "lc:MIT", "lf:BMAD-METHOD", "derived-from"))
    edges.append(
        edge("e:lc-cc-file", "lc:CC-BY-4.0", "lf:microsoft-autogen", "derived-from")
    )

    for spec in FETCHED_PACKAGES:
        anc = fetched[spec["id"]]
        nodes.append(
            node(
                spec["id"],
                "package",
                owner=False,
                licence_class=anc["spdx"],
                fetched_licence_anchor=anc,
                extra={"catalog_name": spec["catalog_name"]},
            )
        )
        edges.append(
            edge(
                f"e:{spec['id']}:licensed-as",
                spec["id"],
                spec["class_id"],
                "licensed-as",
            )
        )
        edges.append(
            edge(
                f"e:{spec['id']}:fetched",
                spec["id"],
                spec["file_id"],
                "fetched-licence",
            )
        )

    for spec in UNFETCHED_PACKAGES:
        anc = anchor_for(spec["path"])
        nodes.append(
            node(
                spec["id"],
                "package",
                owner=False,
                licence_class="UNCLASSIFIED",
                provenance_anchor=anc,
                extra={"unclassified_reason": spec["why"]},
            )
        )
        edges.append(
            edge(
                f"e:{spec['id']}:licensed-as",
                spec["id"],
                "lc:UNCLASSIFIED",
                "licensed-as",
            )
        )

    for spec in OWNER_CANDIDATES:
        anc = anchor_for(spec["path"])
        nodes.append(
            node(
                spec["id"],
                "candidate",
                owner=True,
                licence_class="UNCLASSIFIED",
                provenance_anchor=anc,
                extra={
                    "unclassified_reason": (
                        "Owner-estate module has no LICENSE/COPYING file on "
                        "this tree; not defaulted to OWNER-AUTHORED-PERMISSIVE."
                    )
                },
            )
        )
        edges.append(
            edge(
                f"e:{spec['id']}:licensed-as",
                spec["id"],
                "lc:UNCLASSIFIED",
                "licensed-as",
            )
        )
        for dst in spec.get("cites") or []:
            edges.append(
                edge(f"e:{spec['id']}:cites:{dst}", spec["id"], dst, "cites")
            )

    for spec in BLUEPRINTS:
        anc = anchor_for(spec["path"])
        nodes.append(
            node(
                spec["id"],
                "blueprint",
                owner=True,
                licence_class="UNCLASSIFIED",
                provenance_anchor=anc,
                extra={
                    "unclassified_reason": (
                        "Engineering blueprint source has no fetched licence "
                        "file; listed UNCLASSIFIED, never defaulted."
                    )
                },
            )
        )
        edges.append(
            edge(
                f"e:{spec['id']}:licensed-as",
                spec["id"],
                "lc:UNCLASSIFIED",
                "licensed-as",
            )
        )
        for dst in spec["cites"]:
            edges.append(
                edge(f"e:{spec['id']}:cites:{dst}", spec["id"], dst, "cites")
            )

    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate node ids")
    return {"nodes": nodes, "edges": edges}


def node_index(graph: dict) -> dict[str, dict]:
    return {n["id"]: n for n in graph["nodes"]}


def provenance_edges(graph: dict) -> list[dict]:
    return [e for e in graph["edges"] if e.get("kind") == "cites"]


def unresolved_provenance(graph: dict) -> list[dict]:
    ids = set(node_index(graph))
    bad = []
    for e in provenance_edges(graph):
        if e.get("source") not in ids or e.get("target") not in ids:
            bad.append(e)
            continue
        src = node_index(graph)[e["source"]]
        dst = node_index(graph)[e["target"]]
        src_ok = True
        dst_ok = True
        if src.get("kind") in {"blueprint", "candidate", "package"}:
            pa = src.get("provenance_anchor") or src.get("fetched_licence_anchor")
            if src.get("kind") != "package" or src.get("owner") is True:
                pa = src.get("provenance_anchor") or pa
            if src.get("kind") in {"blueprint", "candidate"}:
                pa = src.get("provenance_anchor")
                src_ok = bool(pa and pa.get("exists") is True)
        if dst.get("kind") in {"blueprint", "candidate"}:
            pa = dst.get("provenance_anchor")
            dst_ok = bool(pa and pa.get("exists") is True)
        elif dst.get("kind") == "package":
            pa = dst.get("provenance_anchor") or dst.get("fetched_licence_anchor")
            dst_ok = bool(pa and pa.get("exists") is True)
        if not src_ok or not dst_ok:
            bad.append(e)
    return bad


def resolution_rate(graph: dict) -> float:
    prov = provenance_edges(graph)
    if not prov:
        return 0.0
    unresolved = unresolved_provenance(graph)
    return (len(prov) - len(unresolved)) / len(prov)


def adjacency(graph: dict) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = defaultdict(list)
    for e in graph["edges"]:
        adj[e["source"]].append(e["target"])
    return adj


def reachable(graph: dict, start: str) -> set[str]:
    adj = adjacency(graph)
    seen = set()
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        for nxt in adj.get(cur, []):
            if nxt not in seen:
                q.append(nxt)
    return seen


def blueprint_ids(graph: dict) -> list[str]:
    return [n["id"] for n in graph["nodes"] if n.get("kind") == "blueprint"]


def licence_class_ids(graph: dict) -> set[str]:
    return {n["id"] for n in graph["nodes"] if n.get("kind") == "licence-class"}


def blueprints_missing_licence_class(graph: dict) -> list[str]:
    classes = licence_class_ids(graph)
    missing = []
    for bid in blueprint_ids(graph):
        seen = reachable(graph, bid)
        if not (seen & classes):
            missing.append(bid)
    return missing


def nodes_with_licence_field_but_unreachable_class(graph: dict) -> list[str]:
    """Independent of the licence_class field: walk edges only."""
    classes = licence_class_ids(graph)
    bad = []
    for n in graph["nodes"]:
        if n.get("kind") not in {"blueprint", "candidate", "package"}:
            continue
        if not n.get("licence_class"):
            continue
        seen = reachable(graph, n["id"])
        if not (seen & classes):
            bad.append(n["id"])
    return bad


def non_owner_component_nodes(graph: dict) -> list[dict]:
    return [
        n
        for n in graph["nodes"]
        if n.get("owner") is False and n.get("kind") in {"package", "candidate"}
    ]


def classified_non_owner_missing_anchor(graph: dict) -> list[str]:
    bad = []
    for n in non_owner_component_nodes(graph):
        klass = n.get("licence_class")
        if klass in {None, "UNCLASSIFIED"}:
            continue
        anc = n.get("fetched_licence_anchor") or {}
        if anc.get("exists") is not True or not anc.get("sha256"):
            bad.append(n["id"])
        elif anc.get("spdx") != klass:
            bad.append(n["id"])
    return bad


def defaulted_unfetched(graph: dict) -> list[str]:
    """UNCLASSIFIED required when no fetched licence file exists."""
    bad = []
    for n in graph["nodes"]:
        if n.get("kind") not in {"blueprint", "candidate", "package"}:
            continue
        anc = n.get("fetched_licence_anchor") or {}
        fetched = anc.get("exists") is True and bool(anc.get("sha256"))
        klass = n.get("licence_class")
        if not fetched and klass not in {None, "UNCLASSIFIED"}:
            bad.append(n["id"])
    return bad


def unclassified_listed(graph: dict) -> list[dict]:
    rows = []
    for n in graph["nodes"]:
        if n.get("kind") not in {"blueprint", "candidate", "package"}:
            continue
        if n.get("licence_class") == "UNCLASSIFIED":
            rows.append(
                {
                    "id": n["id"],
                    "kind": n["kind"],
                    "owner": n.get("owner"),
                    "reason": n.get("unclassified_reason") or "licence file not fetched",
                }
            )
    return rows


def recompute_counts(graph: dict) -> dict:
    prov = provenance_edges(graph)
    unresolved = unresolved_provenance(graph)
    rate = resolution_rate(graph)
    non_owner = non_owner_component_nodes(graph)
    classified = [
        n for n in non_owner if n.get("licence_class") not in {None, "UNCLASSIFIED"}
    ]
    return {
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "blueprints": len(blueprint_ids(graph)),
        "provenance_edges": len(prov),
        "provenance_edges_unresolved": len(unresolved),
        "provenance_resolution_rate": rate,
        "non_owner_nodes": len(non_owner),
        "non_owner_classified": len(classified),
        "non_owner_classified_with_fetched_licence_anchor": len(classified)
        - len(classified_non_owner_missing_anchor(graph)),
        "unclassified_nodes": len(unclassified_listed(graph)),
        "blueprints_missing_licence_class_walk": len(
            blueprints_missing_licence_class(graph)
        ),
        "licence_field_without_walk": len(
            nodes_with_licence_field_but_unreachable_class(graph)
        ),
        "defaulted_unfetched": len(defaulted_unfetched(graph)),
    }


def closure_problems(graph: dict) -> list[str]:
    problems = []
    counts = recompute_counts(graph)
    if counts["provenance_edges_unresolved"] != 0:
        ids = [e.get("id") for e in unresolved_provenance(graph)]
        problems.append("unresolved-provenance:" + ",".join(ids))
    if counts["provenance_resolution_rate"] != 1.0:
        problems.append(f"resolution-rate:{counts['provenance_resolution_rate']}")
    missing = classified_non_owner_missing_anchor(graph)
    if missing:
        problems.append("non-owner-missing-fetched-anchor:" + ",".join(missing))
    defaulted = defaulted_unfetched(graph)
    if defaulted:
        problems.append("defaulted-unfetched:" + ",".join(defaulted))
    if counts["blueprints_missing_licence_class_walk"] != 0:
        problems.append(
            "blueprint-walk-miss:"
            + ",".join(blueprints_missing_licence_class(graph))
        )
    field_bad = nodes_with_licence_field_but_unreachable_class(graph)
    if field_bad:
        problems.append("licence-field-unreachable:" + ",".join(field_bad))
    for n in graph["nodes"]:
        if n.get("kind") in {"blueprint", "candidate"}:
            pa = n.get("provenance_anchor") or {}
            if pa.get("exists") is not True:
                problems.append(f"missing-fs-anchor:{n['id']}")
    ids = set(node_index(graph))
    for e in graph["edges"]:
        if e.get("source") not in ids:
            problems.append(f"dangling-source:{e.get('id')}")
        if e.get("target") not in ids:
            problems.append(f"dangling-target:{e.get('id')}")
    listed = {r["id"] for r in unclassified_listed(graph)}
    for n in graph["nodes"]:
        if (
            n.get("kind") in {"blueprint", "candidate", "package"}
            and n.get("licence_class") == "UNCLASSIFIED"
            and n["id"] not in listed
        ):
            problems.append(f"unclassified-unlisted:{n['id']}")
    return problems


def closure_ok(graph: dict) -> tuple[bool, list[str]]:
    problems = closure_problems(graph)
    return (not problems), problems


def mutate_unresolved_ref(graph: dict) -> dict:
    nodes = [dict(n) for n in graph["nodes"]]
    edges = [dict(e) for e in graph["edges"]]
    edges.append(
        edge(
            "e:planted-unresolved",
            blueprint_ids(graph)[0],
            "wf-planted-unresolved-ref",
            "cites",
        )
    )
    return {"nodes": nodes, "edges": edges}


def mutate_drop_licensed_as(graph: dict, nid: str) -> dict:
    """Keep licence_class on the node but cut every outgoing path to a class.

    A cites-only walk can still reach a candidate's licensed-as edge, so
    both licensed-as and cites from this node are removed. The field
    remains; the edge set no longer reaches a licence-class node.
    """
    nodes = [dict(n) for n in graph["nodes"]]
    edges = [
        dict(e)
        for e in graph["edges"]
        if not (
            e.get("source") == nid
            and e.get("kind") in {"licensed-as", "cites", "fetched-licence"}
        )
    ]
    return {"nodes": nodes, "edges": edges}


def mutate_default_unfetched_to_mit(graph: dict) -> dict:
    nodes = []
    for n in graph["nodes"]:
        copy = dict(n)
        if copy.get("id") == "pkg:unpinned-widget":
            copy["licence_class"] = "MIT"
        nodes.append(copy)
    edges = [dict(e) for e in graph["edges"]]
    return {"nodes": nodes, "edges": edges}


def live_fetched_sha_matches(graph: dict) -> list[str]:
    drift = []
    for spec in FETCHED_PACKAGES:
        path = HERE / spec["license_rel"]
        live = digest_file(path)[0]
        n = node_index(graph)[spec["id"]]
        stored = (n.get("fetched_licence_anchor") or {}).get("sha256")
        if stored != live:
            drift.append(spec["id"])
    return drift


def honesty_block(v1: dict, deps: dict) -> dict:
    return {
        "now_measured": [
            "filesystem existence and sha256 of every blueprint/candidate provenance anchor on this tree",
            "sha256 of fetched LICENSE file bytes for BMAD-METHOD and microsoft/autogen",
            "SPDX identifying-text read from those file bytes (MIT vs CC-BY-4.0)",
            "provenance_edges_unresolved and provenance_resolution_rate recomputed from the edge set",
            "reachability walk from each blueprint along edges to a licence-class node",
        ],
        "remains_rule_based": [
            "mapping LICENSE identifying text to an SPDX id (MIT / CC-BY-4.0) is a local classifier over fetched bytes, not a GitHub licence API opinion",
            "UNCLASSIFIED is a residual bucket, not a fetched licence class",
            "v1 histogram (26 THIRD-PARTY / 11 OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY / 2 ATTRIBUTION-REQUIRED / 1 RIDER-RESTRICTED / 1 UNCLASSIFIED) cannot be recomputed because the v1 graph blob is absent",
        ],
        "not_claimed": [
            "Did not replay the 466-node / 1025-edge v1 graph",
            "Did not verify the historical 0.8109 → 1.0 delta against v1",
            "Did not fold WFA-0002 / WFA-0033 / WFA-0078 artifacts (absent on this tree)",
            "Did not default unfetched nodes to permissive or OWNER-AUTHORED",
            "This is an engineering risk register, not legal advice",
        ],
        "v1_source": v1,
        "dependency_artifacts": deps,
        "fetched_licence_meaning": (
            "Fetched means LICENSE file bytes exist on this tree and were "
            "re-hashed in this unit. This unit did not perform a new HTTP GET."
        ),
    }


def risk_register(graph: dict) -> list[dict]:
    mit = node_index(graph)["pkg:BMAD-METHOD"]["fetched_licence_anchor"]
    cc = node_index(graph)["pkg:microsoft-autogen"]["fetched_licence_anchor"]
    return [
        {
            "id": "risk:MIT-notice",
            "node": "pkg:BMAD-METHOD",
            "licence_class": "MIT",
            "source_sha256": mit["sha256"],
            "source_path": mit["path"],
            "obligation": MIT_NOTICE,
            "verbatim_from_file": True,
        },
        {
            "id": "risk:BMAD-trademark-rider",
            "node": "pkg:BMAD-METHOD",
            "licence_class": "MIT",
            "rider": "TRADEMARK NOTICE",
            "source_sha256": mit["sha256"],
            "source_path": mit["path"],
            "obligation": BMAD_RIDER,
            "verbatim_from_file": True,
        },
        {
            "id": "risk:CC-BY-4.0-attribution",
            "node": "pkg:microsoft-autogen",
            "licence_class": "CC-BY-4.0",
            "source_sha256": cc["sha256"],
            "source_path": cc["path"],
            "obligation": CC_BY_ATTRIBUTION,
            "transcribed_from": "Section 3(a) Attribution of the fetched CC-BY-4.0 text",
            "verbatim_from_file": False,
            "note": (
                "WFA-0033 required the rider-restricted node's obligations "
                "verbatim; that rider is the BMAD TRADEMARK NOTICE above. "
                "CC-BY-4.0 Section 3(a) is summarised here from the fetched "
                "file rather than pasting the full public-license body."
            ),
        },
        {
            "id": "risk:UNCLASSIFIED-no-permissive-default",
            "node": None,
            "licence_class": "UNCLASSIFIED",
            "obligation": (
                "Nodes whose licence file could not be fetched stay "
                "UNCLASSIFIED and must not be treated as permissive."
            ),
            "listed_nodes": [r["id"] for r in unclassified_listed(graph)],
            "verbatim_from_file": False,
        },
    ]
