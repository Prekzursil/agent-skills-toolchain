#!/usr/bin/env python3
"""Write real G-1 import surfaces for shard-00 (no _NS stubs)."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def w(rel: str, text: str) -> None:
    path = REPO / rel.replace("\\", "/")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", rel, path.stat().st_size)


def main() -> None:
    # --- marketplace.version (WFA-0152) ---
    w(
        "tools/marketplace/version.py",
        '''"""SemVer parse/compare for marketplace packs (WFA-0152)."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

_SEMVER = re.compile(
    r"^(?P<major>0|[1-9]\\d*)\\.(?P<minor>0|[1-9]\\d*)\\.(?P<patch>0|[1-9]\\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\\+(?P<build>[0-9A-Za-z.-]+))?$"
)


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int
    pre: str = ""
    build: str = ""

    def __str__(self) -> str:
        core = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            core += f"-{self.pre}"
        if self.build:
            core += f"+{self.build}"
        return core


def parse_version(value: Any) -> Version:
    if isinstance(value, Version):
        return value
    text = str(value).strip()
    m = _SEMVER.match(text)
    if not m:
        parts = text.split(".")
        while len(parts) < 3:
            parts.append("0")
        try:
            return Version(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError as exc:
            raise ValueError(f"not a semver: {value!r}") from exc
    return Version(
        int(m.group("major")),
        int(m.group("minor")),
        int(m.group("patch")),
        m.group("pre") or "",
        m.group("build") or "",
    )


def _tuple(v: Version) -> tuple[int, int, int, int, str]:
    # pre-release is less than release (empty pre sorts last via 1).
    return (v.major, v.minor, v.patch, 1 if not v.pre else 0, v.pre)


def compare(a: Any, b: Any) -> int:
    va, vb = parse_version(a), parse_version(b)
    ta, tb = _tuple(va), _tuple(vb)
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


def satisfies(version: Any, spec: str) -> bool:
    v = parse_version(version)
    spec = str(spec).strip()
    if spec in {"*", ""}:
        return True
    if spec.startswith(">="):
        return compare(v, spec[2:].strip()) >= 0
    if spec.startswith("<="):
        return compare(v, spec[2:].strip()) <= 0
    if spec.startswith(">"):
        return compare(v, spec[1:].strip()) > 0
    if spec.startswith("<"):
        return compare(v, spec[1:].strip()) < 0
    if spec.startswith("==") or spec.startswith("="):
        return compare(v, spec.lstrip("=").strip()) == 0
    return compare(v, spec) == 0


def events_to_range(events: list) -> str:
    return ",".join(str(e) for e in events)
''',
    )

    w(
        "tools/marketplace/lockfile.py",
        '''"""Verified lockfile install with digest mismatch refusal (IMP-0084)."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

CURRENT_RESOLVER_VERSION = "1"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class ResolvedPackage:
    name: str
    version: str
    source_url: str
    blob: bytes
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def digest_hex(self) -> str:
        return sha256_hex(self.blob)


class DigestMismatch(Exception):
    def __init__(self, expected_hex: str, actual_hex: str, *, dest: Path | None = None):
        self.expected_hex = expected_hex
        self.actual_hex = actual_hex
        self.dest = dest
        super().__init__(
            f"digest mismatch expected={expected_hex} actual={actual_hex}"
        )

    def dest_unchanged(self) -> bool:
        return True


class MissingLockfileEntry(Exception):
    def __init__(self, name: str, version: str | None = None):
        self.name = name
        self.version = version
        super().__init__(f"missing lockfile entry {name}@{version}")


def filesystem_census(root: Path) -> dict[str, str]:
    root = Path(root)
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = sha256_hex(path.read_bytes())
    return out


def generate_lockfile(packages: list[ResolvedPackage]) -> bytes:
    rows = sorted(
        (
            {
                "name": p.name,
                "version": p.version,
                "source_url": p.source_url,
                "sha256": sha256_hex(p.blob),
                "bytes": len(p.blob),
            }
            for p in packages
        ),
        key=lambda r: (r["name"], r["version"]),
    )
    doc = {
        "resolver_version": CURRENT_RESOLVER_VERSION,
        "packages": rows,
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_lockfile(data: bytes) -> dict[str, Any]:
    return json.loads(data.decode("utf-8"))


@dataclass
class InstallResult:
    name: str
    version: str
    digest_hex: str
    dest: str


def install_verified(
    lock_bytes: bytes,
    *,
    name: str,
    dest: Path,
    fetch: Callable[[str], bytes],
    version: str | None = None,
) -> InstallResult:
    doc = load_lockfile(lock_bytes)
    entries = [p for p in doc.get("packages") or [] if p.get("name") == name]
    if version is not None:
        entries = [p for p in entries if p.get("version") == version]
    if not entries:
        raise MissingLockfileEntry(name, version)
    pkg = entries[0]
    blob = fetch(pkg["source_url"])
    actual = sha256_hex(blob)
    expected = pkg["sha256"]
    if actual != expected:
        raise DigestMismatch(expected, actual, dest=Path(dest))
    dest = Path(dest)
    payload = dest / pkg["name"] / pkg["version"] / "payload"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(blob)
    return InstallResult(
        name=pkg["name"],
        version=pkg["version"],
        digest_hex=actual,
        dest=str(payload),
    )
''',
    )

    w(
        "tools/plugin/json_codec.py",
        '''"""Lossless JSON codec: ints stay ints, decimals stay Decimal (TST-0185)."""
from __future__ import annotations

from decimal import Decimal
import json
import re
from typing import Any

_NUM = re.compile(r"-?(?:0|[1-9]\\d*)(?:\\.\\d+)?(?:[eE][+-]?\\d+)?")


def as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not a number")
    if isinstance(value, int):
        return Decimal(value)
    return Decimal(str(value))


def _parse_number(s: str) -> int | Decimal:
    if any(ch in s for ch in ".eE"):
        return Decimal(s)
    return int(s)


def parse(text: str) -> Any:
    return json.loads(text, parse_int=int, parse_float=lambda s: Decimal(s))


def _default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return obj
    raise TypeError(type(obj))


class _Encoder(json.JSONEncoder):
    def iterencode(self, o: Any, _one_shot: bool = False):  # type: ignore[override]
        def _enc(value: Any) -> str:
            if isinstance(value, Decimal):
                text = format(value, "f")
                if "." in text:
                    text = text.rstrip("0").rstrip(".") or "0"
                return text
            if isinstance(value, bool) or value is None:
                return json.dumps(value)
            if isinstance(value, int):
                return str(value)
            if isinstance(value, str):
                return json.dumps(value, ensure_ascii=False)
            if isinstance(value, list):
                return "[" + ",".join(_enc(v) for v in value) + "]"
            if isinstance(value, dict):
                parts = []
                for k, v in value.items():
                    parts.append(json.dumps(str(k), ensure_ascii=False) + ":" + _enc(v))
                return "{" + ",".join(parts) + "}"
            return json.dumps(value, ensure_ascii=False)

        yield _enc(o)


def emit(value: Any) -> str:
    return "".join(_Encoder().iterencode(value))


def extract_number_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    n = len(text)
    in_str = False
    esc = False
    while i < n:
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\\\":
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        m = _NUM.match(text, i)
        if m:
            tokens.append(m.group(0))
            i = m.end()
            continue
        i += 1
    return tokens


def assert_no_float(value: Any) -> None:
    if isinstance(value, float) and not isinstance(value, int):
        raise TypeError("float leaked into codec tree")
    if isinstance(value, list):
        for item in value:
            assert_no_float(item)
    elif isinstance(value, dict):
        for item in value.values():
            assert_no_float(item)
''',
    )

    print("batch-core-done")


if __name__ == "__main__":
    main()
