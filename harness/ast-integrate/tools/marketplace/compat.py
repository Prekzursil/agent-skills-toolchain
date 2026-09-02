"""Encoding-compat helpers plus IMP-0085 platform/client resolution."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MATRIX_PLATFORMS = ("linux", "windows", "macos")
MATRIX_CLIENTS = ("1.0.0", "2.0.0")
DEFAULT_INDEX = Path(__file__).resolve().parent / "fixtures" / "compat-index.json"


def strip_bom(raw: bytes) -> bytes:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:]
    if raw.startswith(b"\xff\xfe"):
        return raw[2:]
    if raw.startswith(b"\xfe\xff"):
        return raw[2:]
    return raw


def load_candidates(path: str | Path | None = None):
    import json

    loc = Path(path) if path is not None else DEFAULT_INDEX
    data = json.loads(loc.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("packages"), list):
        return list(data["packages"])
    if isinstance(data, list):
        return list(data)
    raise ValueError("compat candidates missing packages")


def _key(pkg: Mapping[str, Any]) -> str:
    return f"{pkg['id']}@{pkg['version']}"


def candidate_key(pkg: Mapping[str, Any]) -> str:
    """Stable ``id@version`` key for a candidate package record."""
    if "id" not in pkg or "version" not in pkg:
        raise KeyError("candidate needs 'id' and 'version'")
    return _key(pkg)


def _ver_tuple(raw: str) -> tuple[int, int, int]:
    parts = str(raw).strip().lstrip("v").split(".")
    nums = []
    for p in parts[:3]:
        try:
            nums.append(int("".join(ch for ch in p if ch.isdigit()) or "0"))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


@dataclass(frozen=True)
class FilterResult:
    accepted: tuple[str, ...]
    unmet_requirement: str = ""
    rejected: tuple[str, ...] = ()


def filter_candidates(
    packages: Sequence[Mapping[str, Any]],
    *,
    platform: str,
    client_version: str,
    client_name: str | None = None,
) -> FilterResult:
    plat = str(platform).strip().lower()
    aliases = {"win32": "windows", "win": "windows", "darwin": "macos", "osx": "macos"}
    plat = aliases.get(plat, plat)
    req_v = _ver_tuple(client_version)
    accepted: list[str] = []
    rejected: list[str] = []
    unmet = ""
    for pkg in packages:
        key = _key(pkg)
        blob = pkg.get("compatibility")
        if not isinstance(blob, dict) or not blob:
            rejected.append(key)
            continue
        plats = blob.get("platforms")
        if isinstance(plats, list):
            allowed = {aliases.get(str(x).lower(), str(x).lower()) for x in plats}
            if plat not in allowed:
                rejected.append(key)
                continue
        names = blob.get("supported_clients")
        if client_name is not None and isinstance(names, list):
            bag = {str(s).strip().lower() for s in names}
            if client_name.strip().lower() not in bag:
                rejected.append(key)
                continue
        min_raw = blob.get("min_client_version")
        if min_raw is not None and req_v < _ver_tuple(str(min_raw)):
            rejected.append(key)
            unmet = f"requires client >= {min_raw}, you have {client_version}"
            continue
        max_raw = blob.get("max_client_version")
        if max_raw is not None and req_v > _ver_tuple(str(max_raw)):
            rejected.append(key)
            continue
        accepted.append(key)
    accepted_t = tuple(sorted(accepted))
    if not accepted_t and not unmet:
        unmet = "no compatible candidates"
    return FilterResult(accepted=accepted_t, unmet_requirement=unmet, rejected=tuple(sorted(rejected)))


def assert_nonempty_reason_on_empty(result: FilterResult) -> None:
    if result.accepted:
        return
    if not result.unmet_requirement:
        raise AssertionError("empty filter result missing unmet_requirement")


def resolution_matrix(packages: Sequence[Mapping[str, Any]], client_name: str = "claude") -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for plat in MATRIX_PLATFORMS:
        for ver in MATRIX_CLIENTS:
            result = filter_candidates(
                packages, platform=plat, client_version=ver, client_name=client_name
            )
            out[f"{plat}|{ver}"] = list(result.accepted)
    return out


def decode_text(raw: bytes) -> str:
    raw = strip_bom(raw)
    for enc in ("utf-8", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")
