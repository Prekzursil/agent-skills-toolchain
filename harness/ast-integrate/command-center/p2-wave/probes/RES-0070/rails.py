#!/usr/bin/env python3
"""Frozen dual-rail evidence for RES-0070 (permalink, timestamp, status, sha256)."""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Quotes MUST appear as contiguous bytes in the captured snapshot.
QUOTES: dict[str, list[str]] = {
    "bazel-remote-caching": [
        "The action cache, which is a map of action hashes to action result metadata.",
        "A content-addressable store (CAS) of output files.",
        "has inputs, output names, a command line, and environment variables.",
        "inputs and expected outputs are declared explicitly for each action.",
        "action_env",
    ],
    "bazel-hermeticity": [
        "to the host system.",
        "calculates an action graph",
        "hash inputs to look up in the cache.",
    ],
    "nix-input-address": [
        "hashQuotientDerivation",
        "way it was made",
        "an input-addressed output",
        "function not of the output itself, but of the derivation that produced it.",
    ],
    "nix-store-path": [
        'fingerprint = type ":sha256:" inner-digest ":" store ":" name',
    ],
    "dvc-archive": [
        "The DVC cache is a",
        "content-addressable storage",
        "file hashes are calculated from file contents only.",
    ],
    "gh-bazel-spawn-action-raw": [
        "protected void computeKey(",
        "commandLines.addToFingerprint(",
        "fp.addString(GUID);",
        "env.addTo(fp);",
    ],
    "gh-nix-derivations-raw": [
        "derivation::modulo::hash(store, drv);",
        "the input-addressed derivation has an input address",
    ],
    "gh-bazel-abstract-action-raw": [
        "getKey(actionKeyContext, /* inputMetadataProvider= */ null)",
    ],
}

RAILS: dict[str, dict] = {
    "bazel-remote-caching": {
        "kind": "prose-source",
        "permalink": "https://bazel.build/remote/caching",
        "fetch_timestamp": "2026-08-24T18:45:29Z",
        "http_status": 200,
        "sha256": "9ea8405914842f5d491eae817828ab420f75c6f9d1ca3624616bb5560c308b71",
        "bytes": 388743,
        "snapshot": "snapshots/bazel-remote-caching.bin",
        "engine": "bazel",
    },
    "bazel-hermeticity": {
        "kind": "prose-source",
        "permalink": "https://bazel.build/basics/hermeticity",
        "fetch_timestamp": "2026-08-24T18:45:30Z",
        "http_status": 200,
        "sha256": "8e51dc56cb2d397214763d90caf935bf86dcef8ef43201126fd6270fd2b318bc",
        "bytes": 243104,
        "snapshot": "snapshots/bazel-hermeticity.bin",
        "engine": "bazel",
    },
    "nix-input-address": {
        "kind": "prose-source",
        "permalink": "https://nix.dev/manual/nix/2.35/store/derivation/outputs/input-address",
        "fetch_timestamp": "2026-08-24T18:45:31Z",
        "http_status": 200,
        "sha256": "c44f1219a5a44aa1167951978f8efca54947720eb75e586140ab2c19efb0cb56",
        "bytes": 37672,
        "snapshot": "snapshots/nix-input-address.bin",
        "engine": "nix",
    },
    "nix-store-path": {
        "kind": "prose-source",
        "permalink": "https://nix.dev/manual/nix/2.35/protocols/store-path",
        "fetch_timestamp": "2026-08-24T18:45:32Z",
        "http_status": 200,
        "sha256": "f29290f9f4e499995e51717b439c5ceb216b53b6a504ccc91846a5707479abb9",
        "bytes": 31976,
        "snapshot": "snapshots/nix-store-path.bin",
        "engine": "nix",
    },
    "dvc-archive": {
        "kind": "prose-source",
        "permalink": "https://web.archive.org/web/20251113071323/https://dvc.org/doc/user-guide/project-structure/internal-files",
        "fetch_timestamp": "2026-08-24T18:46:23Z",
        "http_status": 200,
        "sha256": "0b92479f4173353684b728f909d6a547486c6b0e99a350870477b6a677d134be",
        "bytes": 330902,
        "snapshot": "snapshots/dvc-archive.bin",
        "engine": "dvc",
        "note": (
            "Live dvc.org returned HTTP 429 at 2026-08-24T18:45:33Z. "
            "This rail is the Wayback capture of the same document. "
            "DVC-only claims stay E3 (single engine after live 429)."
        ),
    },
    "gh-bazel-abstract-action": {
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/bazelbuild/bazel/contents/src/main/java/com/google/devtools/build/lib/actions/AbstractAction.java",
        "fetch_timestamp": "2026-08-24T18:45:33Z",
        "http_status": 200,
        "sha256": "98a03b95ea384416abb5afcf511c483b08f9961f2fc6f5ee10179570b8483ed6",
        "bytes": 33483,
        "snapshot": "snapshots/gh-bazel-abstract-action.bin",
        "engine": "bazel",
        "html_url": "https://github.com/bazelbuild/bazel/blob/master/src/main/java/com/google/devtools/build/lib/actions/AbstractAction.java",
    },
    "gh-nix-derivations": {
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/NixOS/nix/contents/src/libstore/derivations.cc",
        "fetch_timestamp": "2026-08-24T18:45:34Z",
        "http_status": 200,
        "sha256": "e2bd7d713d42d81caf59b7972cdcb993fbca9038420af6a8ff0172695554225e",
        "bytes": 28499,
        "snapshot": "snapshots/gh-nix-derivations.bin",
        "engine": "nix",
        "html_url": "https://github.com/NixOS/nix/blob/master/src/libstore/derivations.cc",
    },
    "gh-bazel-spawn-action-raw": {
        "kind": "structured-api",
        "permalink": "https://raw.githubusercontent.com/bazelbuild/bazel/master/src/main/java/com/google/devtools/build/lib/analysis/actions/SpawnAction.java",
        "fetch_timestamp": "2026-08-24T18:46:38Z",
        "http_status": 200,
        "sha256": "2f71947da1863b6e6264cfb0480b47b39b9e527135b10cfefacfb4ba3700b5fa",
        "bytes": 49978,
        "snapshot": "snapshots/gh-bazel-spawn-action-raw.bin",
        "engine": "bazel",
    },
    "gh-nix-derivations-raw": {
        "kind": "structured-api",
        "permalink": "https://raw.githubusercontent.com/NixOS/nix/master/src/libstore/derivations.cc",
        "fetch_timestamp": "2026-08-24T18:45:54Z",
        "http_status": 200,
        "sha256": "8ee3219f705b96631d52215afb597685b6b1f38829c24064919602c393a2d138",
        "bytes": 20081,
        "snapshot": "snapshots/gh-nix-derivations-raw.bin",
        "engine": "nix",
    },
    "gh-bazel-abstract-action-raw": {
        "kind": "structured-api",
        "permalink": "https://raw.githubusercontent.com/bazelbuild/bazel/master/src/main/java/com/google/devtools/build/lib/actions/AbstractAction.java",
        "fetch_timestamp": "2026-08-24T18:45:54Z",
        "http_status": 200,
        "sha256": "02e6f567792d285a7139f956238ea990118160ce333d1ac8d88f7a43efbb188a",
        "bytes": 23469,
        "snapshot": "snapshots/gh-bazel-abstract-action-raw.bin",
        "engine": "bazel",
    },
}


def verify_rail(rail_id: str) -> dict:
    rec = RAILS[rail_id]
    path = HERE / rec["snapshot"]
    if not path.is_file():
        return {"id": rail_id, "ok": False, "error": "snapshot-missing", "path": str(path)}
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != rec["sha256"]:
        return {
            "id": rail_id,
            "ok": False,
            "error": "sha256-mismatch",
            "live": sha,
            "recorded": rec["sha256"],
        }
    if len(raw) != rec["bytes"]:
        return {
            "id": rail_id,
            "ok": False,
            "error": "size-mismatch",
            "live": len(raw),
            "recorded": rec["bytes"],
        }
    text = raw.decode("utf-8", "replace")
    missing = []
    for q in QUOTES.get(rail_id, []):
        if q.encode("utf-8") not in raw and q not in text:
            missing.append(q)
    if missing:
        return {"id": rail_id, "ok": False, "error": "quote-absent", "missing": missing}
    for k in ("permalink", "fetch_timestamp", "http_status", "sha256"):
        if rec.get(k) in (None, "", 0):
            return {"id": rail_id, "ok": False, "error": f"rail-field-missing:{k}"}
    if rec["http_status"] != 200:
        return {"id": rail_id, "ok": False, "error": f"http-not-200:{rec['http_status']}"}
    if rec["kind"] not in {"structured-api", "prose-source"}:
        return {"id": rail_id, "ok": False, "error": "kind"}
    return {"id": rail_id, "ok": True, "sha256": sha, "bytes": len(raw)}


def verify_all(ids: list[str] | None = None) -> list[dict]:
    return [verify_rail(i) for i in (ids or list(RAILS))]


def public_rail(rail_id: str) -> dict:
    rec = dict(RAILS[rail_id])
    rec["id"] = rail_id
    rec["quotes"] = list(QUOTES.get(rail_id, []))
    return rec
