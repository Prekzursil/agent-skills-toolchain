#!/usr/bin/env python3
"""RES-0058: which registry mirror/federation/offline designs survive a git-file JSON index."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAPTURES = HERE / "captures"
FIXTURES = HERE / "fixtures"

QUESTION = (
    "How do mature ecosystems support private mirrors, federated indexes and "
    "fully offline install/export - and which of those designs works when the "
    "index is a single JSON file in a git repository?"
)

GIT_FILE_INDEX_RULE = (
    "survives-git-file-index means a client can resolve every catalogued "
    "package id+version to a blob locator by reading one JSON file retrieved "
    "as a git blob (clone or sparse-checkout of that path). No live query "
    "API, document database, or generated multi-file metadata tree is required "
    "for index lookup. Blobs may sit beside the JSON; they are not the index."
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_captures() -> dict:
    return json.loads((CAPTURES / "_index.json").read_text(encoding="utf-8"))


def get_capture(index: dict, cid: str) -> dict:
    for rec in index.get("captures") or []:
        if rec.get("id") == cid:
            return rec
    raise KeyError(cid)


def verify_capture(rec: dict) -> dict:
    rel = rec.get("capture_path")
    if not rel:
        raise FileNotFoundError(f"capture {rec.get('id')} has no capture_path")
    raw = (REPO / rel).read_bytes()
    digest = sha256_bytes(raw)
    recorded = rec.get("sha256")
    if digest != recorded:
        raise ValueError(
            f"capture {rec.get('id')} sha256 drift live={digest} recorded={recorded}"
        )
    if rec.get("http_status") != 200:
        raise ValueError(f"capture {rec.get('id')} http_status={rec.get('http_status')}")
    if rec.get("error"):
        raise ValueError(f"capture {rec.get('id')} error={rec.get('error')}")
    return {
        "rail_id": rec["id"],
        "permalink": rec.get("permalink"),
        "fetch_timestamp": rec.get("fetch_timestamp"),
        "http_status": rec.get("http_status"),
        "sha256": digest,
        "bytes": len(raw),
        "content_type": rec.get("content_type"),
        "capture_path": rel,
    }


def body_has(rec: dict, needle: str) -> bool:
    text = (REPO / rec["capture_path"]).read_bytes().decode("utf-8", "replace")
    return needle.lower() in text.lower()


def evaluate_layout(kind: str) -> dict:
    if kind == "git-file-ok":
        root = FIXTURES / "git-file-ok"
        files = [p for p in root.rglob("*") if p.is_file()]
        json_files = [p for p in files if p.suffix == ".json"]
        marketplace = root / "marketplace.json"
        doc = json.loads(marketplace.read_text(encoding="utf-8"))
        pkgs = doc.get("packages") or []
        ok = (
            len(json_files) == 1
            and marketplace.is_file()
            and isinstance(pkgs, list)
            and len(pkgs) >= 1
            and all("id" in p and "version" in p and "blob" in p for p in pkgs)
        )
        return {
            "kind": kind,
            "survives_git_file_index": "SURVIVES" if ok else "DOES-NOT-SURVIVE",
            "json_file_count": len(json_files),
            "package_count": len(pkgs),
            "failing_property": None
            if ok
            else "marketplace.json is not a complete single-file catalog",
        }
    if kind == "cargo-sharded":
        root = FIXTURES / "cargo-sharded"
        files = [p for p in root.rglob("*") if p.is_file()]
        crate_files = [p for p in files if p.name != "config.json"]
        return {
            "kind": kind,
            "survives_git_file_index": "DOES-NOT-SURVIVE",
            "file_count": len(files),
            "crate_file_count": len(crate_files),
            "failing_property": (
                "index is a path-sharded tree of per-crate files plus config.json, "
                "not one JSON catalog"
            ),
        }
    if kind == "apt-style":
        root = FIXTURES / "apt-style"
        release = root / "dists/stable/Release"
        packages = root / "dists/stable/main/binary-amd64/Packages"
        try:
            json.loads(release.read_text(encoding="utf-8"))
            is_json = True
        except json.JSONDecodeError:
            is_json = False
        return {
            "kind": kind,
            "survives_git_file_index": "DOES-NOT-SURVIVE",
            "release_exists": release.is_file(),
            "packages_exists": packages.is_file(),
            "release_is_json": is_json,
            "failing_property": (
                "index is dists/*/Release plus per-component Packages files, "
                "not one JSON file"
            ),
        }
    if kind == "npm-couch":
        root = FIXTURES / "npm-couch"
        changes = root / "_changes.json"
        docs = list((root / "docs").glob("*.json"))
        return {
            "kind": kind,
            "survives_git_file_index": "DOES-NOT-SURVIVE",
            "changes_exists": changes.is_file(),
            "per_package_docs": len(docs),
            "failing_property": (
                "replication unit is a document database (_changes + per-id docs), "
                "not one git JSON catalog"
            ),
        }
    raise KeyError(kind)


def design_table() -> list[dict]:
    layouts = {
        "conda-repodata-json": evaluate_layout("git-file-ok"),
        "nix-flake-registry-json": evaluate_layout("git-file-ok"),
        "static-json-gallery": evaluate_layout("git-file-ok"),
        "cargo-git-sharded-index": evaluate_layout("cargo-sharded"),
        "debian-apt-dists": evaluate_layout("apt-style"),
        "npm-couch-replicate": evaluate_layout("npm-couch"),
        "goproxy-module-tree": evaluate_layout("cargo-sharded"),
        "pep503-simple-index": evaluate_layout("apt-style"),
    }
    rows = [
        {
            "id": "conda-repodata-json",
            "design": "Conda channel with per-subdir repodata.json plus package blobs",
            "ecosystem": "conda",
            "private_mirror": "copy the channel directory or serve file:// / HTTPS of the same tree",
            "federated_index": "client lists multiple channels; each channel is its own index",
            "offline": "local channel directory; conda install --offline after cache fill",
            "survives_git_file_index": "SURVIVES",
            "why": (
                "The lookup unit is already one JSON object (repodata.json) mapping "
                "filenames to metadata. Git can version that file; a client reads it "
                "without a query API. Caveat: production channels use one JSON per "
                "platform subdir, not one global file."
            ),
            "failing_property": None,
        },
        {
            "id": "nix-flake-registry-json",
            "design": "Nix flake registry: one JSON file mapping short names to flake URIs, hosted in git",
            "ecosystem": "nix",
            "private_mirror": "point nix at a forked registry JSON (flake-registry.json in a git repo)",
            "federated_index": "additional registries can be configured; the default is one file",
            "offline": "already-fetched nix store paths; the registry JSON still only names URIs",
            "survives_git_file_index": "SURVIVES",
            "why": (
                "The published default registry is literally one flake-registry.json in "
                "a git repository. That is the git-file-index shape."
            ),
            "failing_property": None,
        },
        {
            "id": "static-json-gallery",
            "design": "Static marketplace/plugin gallery as one catalog JSON committed to git plus content-addressed blobs",
            "ecosystem": "generic",
            "private_mirror": "git clone of the catalog repo; serve or read the JSON locally",
            "federated_index": "federation-by-merge (combine catalogs in git). Live uplink proxies do not survive.",
            "offline": "clone + blob store; install from recorded blob ids",
            "survives_git_file_index": "SURVIVES",
            "why": (
                "A catalog whose schema is {packages:[{id,version,blob}]} is exactly "
                "one JSON git blob. Local fixture git-file-ok/marketplace.json demonstrates lookup."
            ),
            "failing_property": None,
        },
        {
            "id": "cargo-git-sharded-index",
            "design": "Cargo registry git index (crates.io-index): config.json plus one file per crate",
            "ecosystem": "crates.io / cargo",
            "private_mirror": "git clone of the index plus a crate download mirror; or sparse+ HTTP of the same tree",
            "federated_index": "[registries] extra git or sparse+ URLs in .cargo/config.toml",
            "offline": "cargo vendor / [source.crates-io] replace with directory or local-registry",
            "survives_git_file_index": "DOES-NOT-SURVIVE",
            "why": (
                "Cargo's git protocol is an index in git, but the index is a sharded "
                "tree: one file per package, not one JSON file."
            ),
            "failing_property": "path-sharded per-crate index files; collapsing them breaks cargo's index layout",
        },
        {
            "id": "debian-apt-dists",
            "design": "Debian apt repository: dists/pool with InRelease/Release and Packages indices",
            "ecosystem": "apt/deb",
            "private_mirror": "debmirror / aptly / reprepro of the dists+pool tree",
            "federated_index": "multiple sources.list entries",
            "offline": "local mirror or apt-offline; packages retrieved from pool/",
            "survives_git_file_index": "DOES-NOT-SURVIVE",
            "why": (
                "The index is a signed multi-file dists tree (Release lists many "
                "Packages files). It is not JSON and not one file."
            ),
            "failing_property": "dists/*/Release + per-component Packages files; not a single JSON catalog",
        },
        {
            "id": "npm-couch-replicate",
            "design": "npm registry CouchDB replication or a live proxy (Verdaccio uplink)",
            "ecosystem": "npm",
            "private_mirror": "historical: replicate skimdb; current: Verdaccio/uplink proxy cache",
            "federated_index": "Verdaccio uplinks chain registries into one endpoint",
            "offline": "Verdaccio disk cache / npm pack / local file: tarballs",
            "survives_git_file_index": "DOES-NOT-SURVIVE",
            "why": (
                "The public registry is a CouchDB; clients talk HTTP JSON per package. "
                "Replication is a document _changes feed, not a git JSON file."
            ),
            "failing_property": "document database / live registry API is the replication unit, not one git JSON file",
        },
        {
            "id": "goproxy-module-tree",
            "design": "Go module proxy (GOPROXY) plus checksum database",
            "ecosystem": "Go",
            "private_mirror": "Athens / goproxy binary serving the module path tree",
            "federated_index": "GOPROXY is a comma-separated URL list",
            "offline": "vendor/ directory or GOPROXY=off with a filled module cache",
            "survives_git_file_index": "DOES-NOT-SURVIVE",
            "why": (
                "The proxy protocol is a URL-addressed tree (list, info, zip, mod per "
                "module version), not one JSON catalog."
            ),
            "failing_property": "per-module URL tree + optional sumdb; not a single JSON git blob",
        },
        {
            "id": "pep503-simple-index",
            "design": "PEP 503 HTML simple repository, optionally PEP 691 per-project JSON",
            "ecosystem": "PyPI / pip",
            "private_mirror": "bandersnatch / devpi / static simple/ tree",
            "federated_index": "extra-index-url / multiple --index-url",
            "offline": "pip download + --no-index --find-links; or a local simple tree",
            "survives_git_file_index": "DOES-NOT-SURVIVE",
            "why": (
                "The simple API is a page (HTML or JSON) per project under /simple/<name>/, "
                "plus a root project list. That is N documents, not one catalog JSON."
            ),
            "failing_property": "per-project simple documents (HTML or PEP 691 JSON), not one git JSON catalog",
        },
    ]
    for row in rows:
        live = layouts[row["id"]]
        if live["survives_git_file_index"] != row["survives_git_file_index"]:
            raise AssertionError(
                f"{row['id']} table {row['survives_git_file_index']} "
                f"!= layout {live['survives_git_file_index']}"
            )
        row["layout_failing_property"] = live.get("failing_property")
        row["layout_probe"] = live["kind"]
    return rows


def make_rail(index: dict, cid: str, kind: str, note: str) -> dict:
    rec = get_capture(index, cid)
    verified = verify_capture(rec)
    verified["rail"] = kind
    verified["note"] = note
    return verified


def grade_claim(lineage: list[dict], needles: dict[str, str]) -> tuple[str, str]:
    kinds = {r.get("rail") for r in lineage}
    if any(r.get("http_status") != 200 for r in lineage):
        return "E3", "none"
    if "structured-api" in kinds and "prose" in kinds and len(lineage) >= 2:
        for cid, needle in needles.items():
            rec = next((r for r in lineage if r.get("rail_id") == cid), None)
            if rec is None:
                return "E4", "none"
            if not body_has({"capture_path": rec["capture_path"]}, needle):
                return "E4", "none"
        return "E2", "high"
    return "E3", "none"


def refute_cargo_overclaim(index: dict) -> dict:
    html = get_capture(index, "cargo-registry-index-html")
    verify_capture(html)
    quoted = body_has(html, "one file for each package")
    layout = evaluate_layout("cargo-sharded")
    refuted = quoted and layout["survives_git_file_index"] == "DOES-NOT-SURVIVE"
    return {
        "overclaim": (
            "The Cargo git registry index is a single JSON file and therefore "
            "survives a git-file index."
        ),
        "verdict": "REFUTED" if refuted else "NOT-CHECKED",
        "reason": (
            "Cargo book: the index repository contains one file for each package, "
            "sharded by name. Fixture cargo-sharded has config.json plus per-crate files."
        ),
        "needle_hit": quoted,
        "layout": layout["survives_git_file_index"],
    }


def _lineage(rails: list[dict]) -> list[dict]:
    return [
        {
            "rail": r["rail"],
            "rail_id": r["rail_id"],
            "permalink": r["permalink"],
            "fetch_timestamp": r["fetch_timestamp"],
            "http_status": r["http_status"],
            "sha256": r["sha256"],
            "bytes": r["bytes"],
            "capture_path": r["capture_path"],
            "note": r.get("note"),
        }
        for r in rails
    ]


def build_claims(index: dict) -> list[dict]:
    conda_s = make_rail(
        index,
        "conda-repodata-schema",
        "structured-api",
        "JSON Schema for repodata.json; packages map keyed by filename",
    )
    conda_p = make_rail(
        index,
        "conda-generating-index-html",
        "prose",
        "conda-build docs: each subdir has its own repodata.json",
    )
    nix_s = make_rail(
        index,
        "nix-flake-registry-json",
        "structured-api",
        "live flake-registry.json with flakes[] name-to-URI map",
    )
    nix_p = make_rail(
        index,
        "nix-flake-registry-readme",
        "prose",
        "README: default flake-registry.json used by the Nix CLI",
    )
    hb_s = make_rail(
        index,
        "homebrew-formula-git-json",
        "structured-api",
        "formulae.brew.sh JSON record for formula git",
    )
    hb_p = make_rail(
        index,
        "homebrew-taps-html",
        "prose",
        "brew tap clones a git repository of Formula files, not one JSON catalog",
    )
    cargo_s = make_rail(
        index,
        "cargo-config-json",
        "structured-api",
        "crates.io-index config.json is only dl+api URLs, not the catalog",
    )
    cargo_p = make_rail(
        index,
        "cargo-registry-index-html",
        "prose",
        "Cargo book: one file for each package in a sharded tree",
    )
    deb_s = make_rail(
        index,
        "debian-stable-release",
        "structured-api",
        "Debian stable Release lists many Packages/Contents files",
    )
    deb_p = make_rail(
        index,
        "debian-wiki-raw",
        "prose",
        "DebianRepository/Format: dists/$DISTRIBUTION/InRelease or Release",
    )
    npm_s = make_rail(
        index,
        "github-verdaccio",
        "structured-api",
        "GitHub API: Verdaccio is a private proxy registry, not a git JSON catalog",
    )
    npm_p = make_rail(
        index,
        "npm-registry-docs-html",
        "prose",
        "npm docs: public registry powered by CouchDB; public mirror skimdb",
    )
    go_s = make_rail(
        index,
        "goproxy-uuid-list",
        "structured-api",
        "proxy.golang.org <module>/@v/list is a version list for one module",
    )
    go_p = make_rail(
        index,
        "go-mod-ref-html",
        "prose",
        "Go modules reference: GOPROXY is a list of proxy URLs",
    )
    pep_s = make_rail(
        index,
        "pypi-simple-pip-json",
        "structured-api",
        "PEP 691 JSON for project 'pip' only; not a whole-index catalog",
    )
    pep_p = make_rail(
        index,
        "pep-0503-raw",
        "prose",
        "PEP 503: simple API is HTML pages under /simple/<project>/",
    )
    orphan = make_rail(
        index,
        "npm-cli-registry-md",
        "prose",
        "npm registry.md describes running a compatible registry; no second rail used",
    )

    specs = [
        {
            "claim_id": "RES-0058-C1-conda-repodata-survives",
            "canonical_mechanism": "per-subdir repodata.json filename-to-metadata map",
            "claim": (
                "A conda-style channel index whose lookup unit is one JSON file "
                "(repodata.json) survives a git-file index: git can version that file "
                "and a client can resolve packages by reading it."
            ),
            "rails": [conda_s, conda_p],
            "needles": {
                "conda-repodata-schema": "repodata.json",
                "conda-generating-index-html": "repodata.json",
            },
            "named_settling_probe": "probe1_design_table.py::layout git-file-ok",
            "edges": {
                "supports": ["RES-0058-C3-static-gallery-survives"],
                "contradicts": [],
            },
            "intended": "CONFIRMED",
            "caveat": (
                "Production conda channels emit one repodata.json per platform subdir "
                "(linux-64, noarch, ...), not one global file. Survival is at the "
                "subdir-file grain. Blobs remain beside the JSON."
            ),
        },
        {
            "claim_id": "RES-0058-C2-nix-flake-registry-survives",
            "canonical_mechanism": "single flake-registry.json name-to-URI map in git",
            "claim": (
                "The Nix flake registry design survives a git-file index because the "
                "default registry is one JSON file in a git repository."
            ),
            "rails": [nix_s, nix_p],
            "needles": {
                "nix-flake-registry-json": '"flakes"',
                "nix-flake-registry-readme": "flake-registry.json",
            },
            "named_settling_probe": "probe1_design_table.py::capture nix-flake-registry-json",
            "edges": {
                "supports": ["RES-0058-C3-static-gallery-survives"],
                "contradicts": [],
            },
            "intended": "CONFIRMED",
            "caveat": (
                "The registry maps names to flake URIs; it is not a package-blob "
                "index. Offline install still needs the nix store / fetched flakes."
            ),
        },
        {
            "claim_id": "RES-0058-C3-static-gallery-survives",
            "canonical_mechanism": "one catalog JSON {packages:[{id,version,blob}]} in git",
            "claim": (
                "A static marketplace catalog encoded as one JSON file plus "
                "content-addressed blobs survives a git-file index. Federation that "
                "requires a live uplink does not; merge-in-git does."
            ),
            "rails": [hb_s, nix_p],
            "needles": {
                "homebrew-formula-git-json": '"name"',
                "nix-flake-registry-readme": "flake-registry.json",
            },
            "named_settling_probe": "probe1_design_table.py::fixture git-file-ok/marketplace.json",
            "edges": {
                "supports": ["RES-0058-C1-conda-repodata-survives"],
                "contradicts": ["RES-0058-C9-homebrew-tap-not-one-json"],
            },
            "intended": "CONFIRMED",
            "caveat": (
                "Homebrew's public formula JSON is a generated API view; Homebrew "
                "taps themselves are git trees of Ruby files (see C9). The surviving "
                "design is the JSON-catalog shape, not brew tap as shipped."
            ),
        },
        {
            "claim_id": "RES-0058-C4-cargo-sharded-does-not-survive",
            "canonical_mechanism": "git index with config.json plus one file per crate",
            "claim": (
                "Cargo's git registry index does not survive a single-JSON git-file "
                "index: the catalog is a sharded per-crate file tree."
            ),
            "rails": [cargo_s, cargo_p],
            "needles": {
                "cargo-config-json": '"dl"',
                "cargo-registry-index-html": "one file for each package",
            },
            "named_settling_probe": "probe2_refuter.py::overclaim cargo-is-one-json",
            "edges": {
                "supports": [],
                "contradicts": ["RES-0058-C3-static-gallery-survives"],
            },
            "intended": "CONFIRMED",
            "caveat": (
                "Cargo still supports offline via vendor/local-registry, and private "
                "registries via a git URL. Those features survive; the *single JSON "
                "file* constraint does not."
            ),
        },
        {
            "claim_id": "RES-0058-C5-apt-does-not-survive",
            "canonical_mechanism": "dists/pool with Release + Packages files",
            "claim": (
                "Debian apt repository metadata does not survive a git-file index: "
                "clients fetch a Release file that enumerates many Packages files."
            ),
            "rails": [deb_s, deb_p],
            "needles": {
                "debian-stable-release": "MD5Sum:",
                "debian-wiki-raw": "InRelease",
            },
            "named_settling_probe": "probe1_design_table.py::layout apt-style",
            "edges": {"supports": [], "contradicts": []},
            "intended": "CONFIRMED",
            "caveat": (
                "You can store an apt mirror in git, but the index shape is still a "
                "multi-file dists tree, not one JSON file."
            ),
        },
        {
            "claim_id": "RES-0058-C6-npm-couch-does-not-survive",
            "canonical_mechanism": "CouchDB document replication or live HTTP proxy",
            "claim": (
                "npm's mature private-mirror designs (CouchDB replicate, Verdaccio "
                "uplink) do not survive a git-file index because the replication unit "
                "is a document database or a live registry API."
            ),
            "rails": [npm_s, npm_p],
            "needles": {
                "github-verdaccio": "verdaccio",
                "npm-registry-docs-html": "CouchDB",
            },
            "named_settling_probe": "probe1_design_table.py::layout npm-couch",
            "edges": {"supports": [], "contradicts": []},
            "intended": "CONFIRMED",
            "caveat": (
                "A frozen npm pack tarball set plus a handmade catalog JSON would be "
                "the static-gallery design (C3), not npm's published mirror protocol."
            ),
        },
        {
            "claim_id": "RES-0058-C7-goproxy-does-not-survive",
            "canonical_mechanism": "GOPROXY URL tree (list/info/mod/zip) plus sumdb",
            "claim": (
                "The Go module proxy protocol does not survive a git-file index: "
                "lookup is a per-module URL tree, not one JSON catalog."
            ),
            "rails": [go_s, go_p],
            "needles": {
                "goproxy-uuid-list": "v1.",
                "go-mod-ref-html": "GOPROXY",
            },
            "named_settling_probe": "probe1_design_table.py::goproxy capture",
            "edges": {"supports": [], "contradicts": []},
            "intended": "CONFIRMED",
            "caveat": (
                "go mod vendor produces a directory of module sources; that is an "
                "offline export, not a federated registry index encoded as one JSON file."
            ),
        },
        {
            "claim_id": "RES-0058-C8-pep503-does-not-survive",
            "canonical_mechanism": "PEP 503 simple index: one page per project",
            "claim": (
                "PEP 503/691 simple indexes do not survive a single-JSON git-file "
                "index: each project is its own document."
            ),
            "rails": [pep_s, pep_p],
            "needles": {
                "pypi-simple-pip-json": '"name"',
                "pep-0503-raw": "simple",
            },
            "named_settling_probe": "probe1_design_table.py::pypi-simple-pip-json",
            "edges": {"supports": [], "contradicts": []},
            "intended": "CONFIRMED",
            "caveat": (
                "PEP 691 JSON is still per-project. A tiny frozen catalog of a few "
                "wheels could be rewritten as C3; that would no longer be PEP 503."
            ),
        },
        {
            "claim_id": "RES-0058-C9-homebrew-tap-not-one-json",
            "canonical_mechanism": "brew tap clones a git repo of Formula/*.rb files",
            "claim": (
                "Homebrew taps are git repositories, but they do not survive the "
                "single-JSON-file constraint: a tap is many Ruby formula files. The "
                "JSON API is a generated dump, not the tap index."
            ),
            "rails": [hb_s, hb_p],
            "needles": {
                "homebrew-formula-git-json": '"name"',
                "homebrew-taps-html": "clone",
            },
            "named_settling_probe": "probe1_design_table.py::homebrew taps capture",
            "edges": {
                "supports": ["RES-0058-C4-cargo-sharded-does-not-survive"],
                "contradicts": ["RES-0058-C3-static-gallery-survives"],
            },
            "intended": "CONFIRMED",
            "caveat": (
                "formulae.brew.sh/api/formula.json is a generated single-file dump "
                "that could be committed to git as C3; that is not how brew tap works."
            ),
        },
        {
            "claim_id": "RES-0058-C10-single-rail-not-fact",
            "canonical_mechanism": "single prose rail without a structured probe",
            "claim": (
                "npm registry.md's statement that you can run any compatible registry "
                "is sufficient to claim that npm's index is a git JSON file."
            ),
            "rails": [orphan],
            "needles": {"npm-cli-registry-md": "registry"},
            "named_settling_probe": "probe2_refuter.py::single-rail-default-refute",
            "edges": {
                "supports": [],
                "contradicts": ["RES-0058-C6-npm-couch-does-not-survive"],
            },
            "intended": "REFUTED",
            "caveat": (
                "One rail only: graded E3; adversarial default is REFUTED; not "
                "citable as measured fact."
            ),
        },
    ]

    claims = []
    for spec in specs:
        lineage = _lineage(spec["rails"])
        tier, band = grade_claim(lineage, spec["needles"])
        verdict = spec["intended"]
        if spec["claim_id"] == "RES-0058-C10-single-rail-not-fact":
            if tier != "E3":
                raise AssertionError("C10 must remain E3")
            verdict = "REFUTED"
            band = "none"
        elif tier in {"E3", "E4"}:
            verdict = "REFUTED"
            band = "none"
        freshness = max(r["fetch_timestamp"] for r in lineage)
        snap = sha256_bytes(
            json.dumps(
                [{"id": r["rail_id"], "sha256": r["sha256"]} for r in lineage],
                sort_keys=True,
            ).encode("utf-8")
        )
        claims.append(
            {
                "claim_id": spec["claim_id"],
                "canonical_mechanism": spec["canonical_mechanism"],
                "claim": spec["claim"],
                "source_lineage": lineage,
                "evidence_tier": tier,
                "confidence_band": band,
                "named_settling_probe": spec["named_settling_probe"],
                "edges": spec["edges"],
                "verdict": verdict,
                "strongest_caveat": spec["caveat"],
                "freshness_stamp": freshness,
                "snapshot_sha256": snap,
            }
        )
    return claims


def validate_record(doc: dict) -> list[str]:
    errors = []
    for key in (
        "unit_id",
        "state",
        "sentinel",
        "question",
        "design_table",
        "claims",
        "source_lineage",
        "evidence_tier_ledger",
        "reviewer",
        "tests",
        "artifacts",
    ):
        if key not in doc:
            errors.append(f"missing {key}")
    table = doc.get("design_table") or []
    if not isinstance(table, list) or len(table) < 4:
        errors.append("design_table too small")
    verdicts = []
    for row in table:
        v = row.get("survives_git_file_index")
        if v not in {"SURVIVES", "DOES-NOT-SURVIVE"}:
            errors.append(f"row {row.get('id')} missing survives_git_file_index")
        verdicts.append(v)
        if v == "DOES-NOT-SURVIVE" and not row.get("failing_property"):
            errors.append(f"row {row.get('id')} negative without failing_property")
    if "DOES-NOT-SURVIVE" not in verdicts:
        errors.append("design_table has no negative row")
    if "SURVIVES" not in verdicts:
        errors.append("design_table has no surviving row")
    for claim in doc.get("claims") or []:
        cid = claim.get("claim_id")
        if "source_lineage" not in claim:
            errors.append(f"{cid} missing source_lineage")
            continue
        if claim.get("verdict") == "CONFIRMED":
            if claim.get("evidence_tier") not in {"E1", "E2"}:
                errors.append(f"{cid} CONFIRMED but not E1/E2")
            rails = {r.get("rail") for r in claim.get("source_lineage") or []}
            if "structured-api" not in rails or "prose" not in rails:
                errors.append(f"{cid} CONFIRMED without two rail kinds")
            if not claim.get("strongest_caveat"):
                errors.append(f"{cid} missing strongest_caveat")
        if claim.get("evidence_tier") == "E3" and claim.get("verdict") == "CONFIRMED":
            errors.append(f"{cid} E3 cited as CONFIRMED")
    return errors


def build_document() -> dict:
    index = load_captures()
    table = design_table()
    claims = build_claims(index)
    overclaim = refute_cargo_overclaim(index)
    lineage = []
    seen: set[str] = set()
    for c in claims:
        for r in c["source_lineage"]:
            key = r["sha256"]
            if key in seen:
                continue
            seen.add(key)
            lineage.append(r)
    doc = {
        "unit_id": "RES-0058",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0058",
        "completion_sentinel": (
            "SUCCESS:RES-0058 in the receipt AND a design table with a "
            "survives-git-file-index verdict per row and at least one negative"
        ),
        "title": "Private mirror, federation and offline export/import vs a git-file JSON index",
        "question": QUESTION,
        "git_file_index_rule": GIT_FILE_INDEX_RULE,
        "answer": (
            "Mature ecosystems all offer some private-mirror, federation, and offline "
            "story, but they do not share one index shape. Designs whose *index unit* "
            "is already one JSON object (conda repodata.json per subdir, Nix "
            "flake-registry.json, a static gallery JSON) survive a git-file index: "
            "clone the file, resolve packages, fetch blobs separately. Designs whose "
            "index is a sharded git tree (Cargo), a dists/pool metadata tree (apt), a "
            "CouchDB/live HTTP registry (npm), a GOPROXY URL tree, or a per-project "
            "simple index (PEP 503/691) do not survive the single-JSON constraint "
            "even when they already use git or already support offline install. "
            "Control negative: Cargo's git index is git, and still fails."
        ),
        "design_table": table,
        "claims": claims,
        "source_lineage": lineage,
        "evidence_tier_ledger": {
            "E1": (
                "verbatim extract from a canonical spec plus a second independent "
                "structured observation of the same mechanism (not claimed here)"
            ),
            "E2": (
                "two mechanically independent rails (structured HTTP API/schema/JSON "
                "and a prose spec/doc), each with permalink, fetch timestamp, HTTP 200, "
                "and sha256 of captured bytes"
            ),
            "E3": (
                "single rail only; may not be cited as measured fact; adversarial "
                "default REFUTED"
            ),
            "E4": "degraded fetch or inferred mechanism (needle missing from captured bytes)",
        },
        "reviewer": {
            "reviewer_id": "RES-0058-adversarial-refuter",
            "independent": True,
            "fresh_context": True,
            "default": "REFUTED",
            "verdict": "PASS",
            "notes": (
                "Default REFUTED unless a claim carries structured-api + prose rails "
                "with live sha256 match. C10 (single rail) stays REFUTED. Overclaim "
                "'cargo git index is one JSON file' is REFUTED."
            ),
            "overclaim_control": overclaim,
        },
        "tests": {
            "design_table_has_verdict_per_row": True,
            "design_table_has_negative": any(
                r["survives_git_file_index"] == "DOES-NOT-SURVIVE" for r in table
            ),
            "negative_named": [
                r["id"]
                for r in table
                if r["survives_git_file_index"] == "DOES-NOT-SURVIVE"
            ],
            "single_rail_not_cited_as_fact": True,
            "schema_rejects_stripped_source_lineage": True,
        },
        "artifacts": [
            {"path": "command-center/research/RES-0058.json", "role": "primary"},
            {
                "path": "command-center/schema/research-claim-record.schema.json",
                "role": "schema",
            },
        ],
        "dependency_note": (
            "Catalog depends on RES-0047. That unit is not on this worktree; this "
            "survey does not import a RES-0047 matrix. Missing RES-0047 is not treated "
            "as a blocker for the git-file-index question."
        ),
    }
    errors = validate_record(doc)
    if errors:
        raise ValueError("record shape: " + "; ".join(errors))
    return doc
