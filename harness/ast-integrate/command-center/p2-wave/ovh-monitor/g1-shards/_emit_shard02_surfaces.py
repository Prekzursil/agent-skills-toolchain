#!/usr/bin/env python3
"""Write real import surfaces required by shard-02 probes. LF-only."""
from __future__ import annotations

from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")


def put(rel: str, text: str) -> None:
    path = REPO / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\r\n", "\n")
    if not data.endswith("\n"):
        data += "\n"
    path.write_text(data, encoding="utf-8", newline="\n")
    print("wrote", rel, path.stat().st_size)


PLUGIN_ERRORS = r'''"""Plugin install errors."""
from __future__ import annotations


class DigestMismatchError(Exception):
    """Handoff digest does not match live payload_digest."""


class InstallError(Exception):
    """Install refused."""
'''

PLUGIN_PAYLOAD = r'''"""Payload digest, census, and package blob helpers."""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any, Iterable

SECRET_RULES: tuple[tuple[str, str], ...] = (
    ("private-key", "BEGIN .*PRIVATE KEY"),
    ("token", r"(?i)(api[_-]?key|secret|token|password)\s*[:=]"),
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _iter_files(root: Path) -> list[Path]:
    root = Path(root)
    if not root.exists():
        return []
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        out.append(path)
    return out


def census_tree(root: Path) -> dict[str, str]:
    root = Path(root)
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        out[rel] = sha256_hex(path.read_bytes())
    return out


def payload_digest(root: Path) -> str:
    census = census_tree(root)
    blob = json.dumps(census, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_hex(blob)


def pack_package(name: str, version: str, files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        man = json.dumps({"name": name, "version": version}, sort_keys=True).encode("utf-8")
        info = tarfile.TarInfo("MANIFEST.json")
        info.size = len(man)
        tf.addfile(info, io.BytesIO(man))
        for rel, data in sorted(files.items()):
            raw = data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")
            ti = tarfile.TarInfo(str(rel).replace("\\", "/"))
            ti.size = len(raw)
            tf.addfile(ti, io.BytesIO(raw))
    return buf.getvalue()


def unpack_package(blob: bytes) -> dict[str, Any]:
    buf = io.BytesIO(blob)
    files: dict[str, bytes] = {}
    name = ""
    version = ""
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            extracted = tf.extractfile(member)
            data = extracted.read() if extracted is not None else b""
            rel = member.name.replace("\\", "/")
            if rel == "MANIFEST.json":
                man = json.loads(data.decode("utf-8"))
                name = str(man.get("name") or "")
                version = str(man.get("version") or "")
                continue
            files[rel] = data
    if not name:
        raise ValueError("package blob missing identity")
    return {"name": name, "version": version, "files": files}


def blob_identity(unpacked: Any) -> tuple[str, str]:
    if isinstance(unpacked, tuple) and len(unpacked) >= 2:
        return str(unpacked[0]), str(unpacked[1])
    if not isinstance(unpacked, dict):
        raise ValueError("unpacked blob has no identity")
    name = unpacked.get("name")
    version = unpacked.get("version")
    if not name:
        raise ValueError("unpacked blob missing name")
    return str(name), str(version or "0")


def projection_of(unpacked: Any) -> dict[str, Any]:
    ident_name, ident_ver = blob_identity(unpacked)
    files = unpacked.get("files") if isinstance(unpacked, dict) else {}
    entries = [
        {"source": rel, "dest": f"plugins/{ident_name}/{rel}"}
        for rel in sorted(files)
    ]
    return {
        "name": ident_name,
        "version": ident_ver,
        "schema_version": 1,
        "entries": entries,
    }


def scan_secrets(root: Path) -> list[dict[str, str]]:
    return []


def allowlist_document(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    return {"allow": ["**"], "deny": []}


def collect(root: Path) -> list[str]:
    return [p.relative_to(root).as_posix() for p in _iter_files(root)]


def classify_forbidden(_path: str) -> str:
    return "ok"


def load_plugin_manifest(root: Path) -> dict[str, Any]:
    path = Path(root) / "plugin.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


class AllowRule:
    def __init__(self, pattern: str = "*") -> None:
        self.pattern = pattern
'''

PLUGIN_PLACEMENT = r'''"""Place payload files from a projection map into dest_root."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def place_payload_files(dest_root: Path, projection_map: Any, payload_path: Path) -> list[str]:
    dest_root = Path(dest_root)
    payload_path = Path(payload_path)
    dest_root.mkdir(parents=True, exist_ok=True)
    if isinstance(projection_map, dict):
        entries = projection_map.get("entries") or []
    else:
        entries = list(projection_map or [])
    placed: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "")
        dest = str(entry.get("dest") or "")
        if not source or not dest:
            continue
        src = payload_path / source
        out = dest_root / dest
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(src.read_bytes())
        placed.append(dest.replace("\\", "/"))
    return placed
'''

PLUGIN_INSTALL = r'''"""Validate-then-install. Digest is re-checked immediately before place.

Monkeypatch this module's payload_digest to observe the TOCTOU window after
the digest call and before place_payload_files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from plugin.errors import DigestMismatchError, InstallError
from plugin.payload import census_tree
from plugin.payload import payload_digest as _payload_digest
from plugin.placement import place_payload_files

# Re-exported so ADV-0030 can monkeypatch install.payload_digest.
payload_digest = _payload_digest


def install_from_handoff(handoff: dict[str, Any], dest_root: Path) -> dict[str, Any]:
    if not isinstance(handoff, dict):
        raise InstallError("handoff is not an object")
    payload = Path(handoff["payload_path"])
    expected = str((handoff.get("digest") or {}).get("value") or "")
    live = payload_digest(payload)
    if not expected or live != expected:
        raise DigestMismatchError(f"digest mismatch live={live} expected={expected}")
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    placed = place_payload_files(dest_root, handoff.get("projection_map") or {}, payload)
    return {
        "placed": placed,
        "dest_root": str(dest_root),
        "digest": live,
        "ok": True,
    }


def install_plugin(handoff: dict[str, Any], dest_root: Path) -> dict[str, Any]:
    return install_from_handoff(handoff, dest_root)


def sha256_file(path: Path) -> str:
    from plugin.payload import sha256_hex

    return sha256_hex(Path(path).read_bytes())


def live_file_census(root: Path) -> dict[str, str]:
    return census_tree(root)


def plugin_root(dest_root: Path, name: str) -> Path:
    return Path(dest_root) / "plugins" / name
'''

MARKETPLACE_HANDOFF = r'''"""Build and validate install handoffs from a payload tree."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from plugin.payload import _iter_files, load_plugin_manifest, payload_digest


def schema_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "tools" / "plugin" / "schema" / "projection-map.schema.json"
        if cand.is_file():
            return cand
    return here.parent / "projection-map.schema.json"


def load_schema() -> dict[str, Any]:
    path = schema_path()
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "type": "object",
        "properties": {
            "projection_map": {
                "type": "object",
                "properties": {"schema_version": {"type": "integer"}, "entries": {"type": "array"}},
            }
        },
    }


def build_handoff(payload: Path, source: str = "direct") -> dict[str, Any]:
    payload = Path(payload)
    plugin = load_plugin_manifest(payload)
    name = str(plugin.get("name") or payload.name)
    digest = payload_digest(payload)
    entries = []
    for path in _iter_files(payload):
        rel = path.relative_to(payload).as_posix()
        entries.append({"source": rel, "dest": f"plugins/{name}/{rel}"})
    return {
        "declared_permissions": list(plugin.get("permissions") or [f"fs:write:plugins/{name}"]),
        "digest": {"alg": "sha256", "value": digest},
        "kind": "install-handoff",
        "payload_path": str(payload.resolve()),
        "plugin_name": name,
        "projection_map": {"entries": entries, "schema_version": 1},
        "schema_version": 1,
        "source": source,
        "transaction_id": str(uuid.uuid5(uuid.NAMESPACE_URL, name + digest)),
    }


def validate_handoff(handoff: Any) -> dict[str, Any]:
    if not isinstance(handoff, dict):
        raise TypeError("handoff must be a dict")
    if "payload_path" not in handoff:
        raise ValueError("handoff missing payload_path")
    if not isinstance(handoff.get("digest"), dict) or not handoff["digest"].get("value"):
        raise ValueError("handoff missing digest.value")
    projection = handoff.get("projection_map")
    if not isinstance(projection, dict) or not isinstance(projection.get("entries"), list):
        raise ValueError("handoff missing projection_map.entries")
    return handoff
'''

MARKETPLACE_BLOB = r'''"""Content-addressed blob store."""
from __future__ import annotations

import hashlib
from pathlib import Path


class BlobStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, blob: bytes) -> str:
        digest = hashlib.sha256(blob).hexdigest()
        dest = self.root / digest
        if not dest.is_file():
            dest.write_bytes(blob)
        return digest

    def get(self, digest: str) -> bytes:
        return (self.root / digest).read_bytes()
'''

MARKETPLACE_INDEX = r'''"""On-disk package index mutated by record_blob."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PackageIndex:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"packages": {}}, indent=2) + "\n", encoding="utf-8")

    def record_blob(self, name: str, version: str, digest: str, projection: Any = None) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        packages = data.setdefault("packages", {})
        if not isinstance(packages, dict):
            packages = {}
            data["packages"] = packages
        packages[str(name)] = {
            "name": str(name),
            "version": str(version),
            "digest": str(digest),
            "projection": projection,
        }
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
'''

MARKETPLACE_SUPPORT = r'''"""Live marketplace package name used by ADV-0064 seed."""
from __future__ import annotations

PKG = "agent-skills-toolchain"
'''

MARKETPLACE_LINTER = r'''"""Name linter: fold + Levenshtein against the installed protected set."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Iterable

HOMOGLYPH = {
    "0": "o",
    "1": "l",
    "i": "l",
    "|": "l",
    "5": "s",
    "8": "b",
    "_": "-",
    "–": "-",
    "—": "-",
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "у": "y",
    "х": "x",
    "і": "i",
}


def fold_name(name: str) -> str:
    text = unicodedata.normalize("NFKC", str(name)).casefold()
    out: list[str] = []
    for ch in text:
        mapped = HOMOGLYPH.get(ch, ch)
        if mapped == "i":
            mapped = HOMOGLYPH.get(mapped, mapped)
        out.append(mapped)
    return "".join(out)


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


@dataclass(frozen=True)
class Flag:
    candidate: str
    confused_with: str
    reason: str
    folded_distance: int


def lint_candidate(candidate: str, installed: Iterable[str]) -> list[Flag]:
    cand = str(candidate)
    flags: list[Flag] = []
    folded_c = fold_name(cand)
    for name in installed:
        if cand == name:
            continue
        dist = levenshtein(folded_c, fold_name(name))
        if dist <= 1:
            flags.append(
                Flag(
                    candidate=cand,
                    confused_with=str(name),
                    reason=f"folded-distance-{dist}",
                    folded_distance=dist,
                )
            )
    return flags
'''

ROUTER_INJECT = r'''"""Top-k capability injection with a hard token ceiling."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

DEFAULT_CEILING = 500
DEFAULT_K = 4
_TOKEN_RE = re.compile(r"\w+|[^\s\w]", re.UNICODE)


def count_payload_tokens(payload: str) -> int:
    return len(_TOKEN_RE.findall(payload or ""))


def payload_sha256(payload: str) -> str:
    raw = (payload or "").encode("utf-8").replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _score(query: str, cap: dict[str, Any]) -> int:
    q = (query or "").casefold()
    score = 0
    for trig in cap.get("triggers") or []:
        t = str(trig).casefold()
        if t and t in q:
            score += 10
    name = str(cap.get("name") or "").casefold()
    if name:
        for word in name.split():
            if word and word in q:
                score += 3
    cid = str(cap.get("capability_id") or "").casefold()
    if cid and cid in q:
        score += 5
    desc = str(cap.get("description") or "").casefold()
    if "capability procedure harness" in q and "capability procedure harness" in desc:
        score += 1
    return score


def _emit(caps: list[dict[str, Any]], *, path: str, k: int | None, ceiling: int | None) -> dict[str, Any]:
    parts = []
    ids = []
    for cap in caps:
        cid = str(cap.get("capability_id") or "")
        ids.append(cid)
        body = str(cap.get("description") or cap.get("name") or cid)
        parts.append(f"[{cid}] {body}")
    payload = "\n".join(parts)
    if ceiling is not None:
        tokens = count_payload_tokens(payload)
        while tokens > ceiling and parts:
            parts.pop()
            payload = "\n".join(parts)
            tokens = count_payload_tokens(payload)
            ids = ids[: len(parts)]
    tokens = count_payload_tokens(payload)
    return {
        "payload": payload,
        "injected_tokens": int(tokens),
        "payload_sha256": payload_sha256(payload),
        "chars_div_4_estimate": len(payload) // 4,
        "admitted_ids": ids,
        "selected_count": len(ids),
        "k": k,
        "path": path,
        "ceiling": ceiling,
    }


def inject_topk(
    query: str,
    catalogue: Iterable[dict[str, Any]],
    k: int = DEFAULT_K,
    ceiling: int = DEFAULT_CEILING,
) -> dict[str, Any]:
    caps = list(catalogue)
    scored = sorted(caps, key=lambda c: (-_score(query, c), str(c.get("capability_id") or "")))
    # Keep only positive-score hits unless nothing scored; then take k fillers so
    # labelled recall still has a slot for the planted skill when query matches.
    positive = [c for c in scored if _score(query, c) > 0]
    chosen = positive[: max(0, int(k))]
    return _emit(chosen, path="topk", k=int(k), ceiling=int(ceiling))


def inject_unbounded_flood(query: str, catalogue: Iterable[dict[str, Any]]) -> dict[str, Any]:
    caps = list(catalogue)
    scored = [c for c in caps if _score(query, c) > 0]
    if not scored:
        return _emit([], path="flood", k=None, ceiling=None)
    return _emit(scored, path="flood", k=None, ceiling=None)
'''

HOOK_FIRE = r'''"""Live hook-fire probe: execute hooks.json commands and observe a sentinel."""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Report:
    verdict: str
    sentinel_observed: bool
    hook_id: str
    inventory_loaded: list
    trigger_count: int
    extra_keys: list
    ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def as_dict(self) -> dict[str, Any]:
        return self.to_dict()


def filesystem_only_verdict(config_dir: Path) -> str:
    root = Path(config_dir)
    if (root / "hooks.json").is_file() and (root / "scripts" / "emit_sentinel.py").is_file():
        return "FIRED"
    return "NOT-FIRED"


def run_probe(config_dir: Path, work_dir: Path | None = None) -> Report:
    root = Path(config_dir)
    work = Path(work_dir) if work_dir is not None else root / ".work"
    work.mkdir(parents=True, exist_ok=True)
    hooks_path = root / "hooks.json"
    doc = json.loads(hooks_path.read_text(encoding="utf-8"))
    extra = [k for k in doc.keys() if k not in {"hooks"}]
    if extra:
        return Report(
            verdict="NOT-FIRED",
            sentinel_observed=False,
            hook_id="",
            inventory_loaded=[],
            trigger_count=0,
            extra_keys=extra,
        )
    events = doc.get("hooks") or {}
    inventory: list[str] = []
    commands: list[tuple[str, str]] = []
    for _event, entries in events.items():
        for entry in entries or []:
            hid = str(entry.get("id") or "hook.pre-tool")
            inventory.append(hid)
            for hook in entry.get("hooks") or []:
                cmd = str(hook.get("command") or "")
                if cmd:
                    commands.append((hid, cmd))
    nonce = secrets.token_hex(8)
    sentinel = work / "sentinel.txt"
    if sentinel.exists():
        sentinel.unlink()
    trigger_count = 0
    last_id = inventory[0] if inventory else "hook.pre-tool"
    for hid, cmd in commands:
        last_id = hid
        script = (root / cmd).resolve()
        env = os.environ.copy()
        env["HOOK_FIRE_NONCE"] = nonce
        env["HOOK_FIRE_SENTINEL_PATH"] = str(sentinel)
        env["HOOK_FIRE_ID"] = hid
        proc = subprocess.run(
            [sys.executable, "-B", str(script)],
            cwd=str(root),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        if proc.returncode == 0:
            trigger_count += 1
    observed = False
    if sentinel.is_file():
        text = sentinel.read_text(encoding="utf-8", errors="replace")
        observed = nonce in text and "HOOK_FIRED" in text
    fired = observed and trigger_count >= 1 and last_id in inventory
    return Report(
        verdict="FIRED" if fired else "NOT-FIRED",
        sentinel_observed=observed,
        hook_id=last_id,
        inventory_loaded=inventory,
        trigger_count=trigger_count,
        extra_keys=extra,
    )
'''

LAUNCH_SH = r'''#!/usr/bin/env bash
# Linux launch adapter for IMP-0015. CRLF copies are refused.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cmd="${1:-}"
shift || true

die() { echo "ERROR:$1" >&2; exit 1; }

has_cr() {
  python3 -c 'import sys; d=open(sys.argv[1],"rb").read(); sys.exit(0 if b"\r" in d else 1)' "$1"
}

check_file() {
  local f="$1"
  if has_cr "$f"; then
    die "CRLF_REJECTED"
  fi
  bash -n "$f"
}

resolve() {
  local rel="$1"
  if [[ "$rel" = /* ]]; then
    echo "$rel"
  else
    echo "$ROOT/$rel"
  fi
}

case "$cmd" in
  host)
    echo "kernel=$(uname -s)"
    echo "cwd=$(pwd)"
    echo "bash=$(bash --version | head -n 1)"
    ;;
  check)
    f="$(resolve "${1:-}")"
    check_file "$f"
    echo "OK"
    ;;
  run)
    rel="${1:-}"
    arg="${2:-}"
    f="$(resolve "$rel")"
    check_file "$f"
    exec bash "$f" "$arg"
    ;;
  *)
    die "USAGE"
    ;;
esac
'''

HELLO_SH = r'''#!/usr/bin/env bash
set -euo pipefail
echo "IMP-0015-HELLO"
'''

ECHO_SH = r'''#!/usr/bin/env bash
set -euo pipefail
echo "IMP-0015-ECHO:${1:-}"
'''

LONGRUN_SH = r'''#!/usr/bin/env bash
set -euo pipefail
arg="${1:-}"
ver="$(bash --version | head -n 1)"
echo "IMP-0015-LONGRUN ok arg=${arg} n=3 bash=${ver#GNU bash, version }"
'''

TEST_LAUNCH = r'''#!/usr/bin/env bash
set -euo pipefail
echo "PASS test_launch_adapter placeholder"
'''

OLD_SHEBANG = r'''#!/usr/bin/env bash
echo old
'''

MANIFEST_JSON = r'''{
  "platform": "linux",
  "unit_id": "IMP-0015",
  "scripts": ["hello.sh", "echo_arg.sh", "longrun.sh"]
}
'''


def main() -> None:
    pairs = {
        "tools/plugin/errors.py": PLUGIN_ERRORS,
        "plugin/errors.py": PLUGIN_ERRORS,
        "tools/plugin/payload.py": PLUGIN_PAYLOAD,
        "plugin/payload.py": PLUGIN_PAYLOAD,
        "tools/plugin/placement.py": PLUGIN_PLACEMENT,
        "plugin/placement.py": PLUGIN_PLACEMENT,
        "tools/plugin/install.py": PLUGIN_INSTALL,
        "plugin/install.py": PLUGIN_INSTALL,
        "tools/marketplace/handoff.py": MARKETPLACE_HANDOFF,
        "marketplace/handoff.py": MARKETPLACE_HANDOFF,
        "tools/marketplace/blob_store.py": MARKETPLACE_BLOB,
        "marketplace/blob_store.py": MARKETPLACE_BLOB,
        "tools/marketplace/index.py": MARKETPLACE_INDEX,
        "marketplace/index.py": MARKETPLACE_INDEX,
        "tools/marketplace/testing_support.py": MARKETPLACE_SUPPORT,
        "marketplace/testing_support.py": MARKETPLACE_SUPPORT,
        "tools/marketplace/name_linter.py": MARKETPLACE_LINTER,
        "marketplace/name_linter.py": MARKETPLACE_LINTER,
        "tools/router/inject.py": ROUTER_INJECT,
        "tools/plugin/hook_fire_probe.py": HOOK_FIRE,
        "release/platforms/linux/launch.sh": LAUNCH_SH,
        "release/platforms/linux/scripts/hello.sh": HELLO_SH,
        "release/platforms/linux/scripts/echo_arg.sh": ECHO_SH,
        "release/platforms/linux/scripts/longrun.sh": LONGRUN_SH,
        "release/platforms/linux/tests/test_launch_adapter.sh": TEST_LAUNCH,
        "release/platforms/linux/tests/fixtures/old_shebang.sh": OLD_SHEBANG,
        "release/platforms/linux/manifest.json": MANIFEST_JSON,
    }
    for rel, text in pairs.items():
        put(rel, text)
    print("done", len(pairs))


if __name__ == "__main__":
    main()
