"""Confirmation-suite cases for CNF-0147.

The Phase-11 confirmation suite is not present as a named pytest collection on
this worktree (docs/validation/tools/hermetic_probe.py is also absent). This
module is the runnable confirmation suite for the unit: hermetic catalog
confirmations plus the measured silent-download class (get-pip.py) and
declared-network controls.

Silent cases carry the comment 'This test never downloads' while actually
fetching /bootstrap/get-pip.py — the estate's named detector-failure class.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GETPIP_PATH = "/bootstrap/get-pip.py"
DECLARED_PATH = "/declared"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
SILENT_COUNT = 14
_CATALOG_TEXT: str | None = None


def catalog_text() -> str:
    global _CATALOG_TEXT
    if _CATALOG_TEXT is None:
        _CATALOG_TEXT = (REPO / CATALOG_REL).read_text(encoding="utf-8")
    return _CATALOG_TEXT


@dataclass
class Env:
    port: int
    cache_dir: Path | None
    attempts: list


@dataclass
class TestSpec:
    id: str
    declared_network: bool
    claims_never_download: bool
    fn: Callable[[Env], None]


def cache_file(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.body"


def fetch(env: Env, path: str, *, use_cache: bool) -> bytes:
    url = f"http://127.0.0.1:{env.port}{path}"
    env.attempts.append({"url": url, "use_cache": use_cache})
    if use_cache and env.cache_dir is not None:
        cached = cache_file(env.cache_dir, url)
        if cached.is_file():
            env.attempts[-1]["cache_hit"] = True
            return cached.read_bytes()
        env.attempts[-1]["cache_hit"] = False
    try:
        with urlopen(url, timeout=2) as resp:
            body = resp.read()
    except (URLError, OSError, TimeoutError) as exc:
        env.attempts[-1]["error"] = f"{type(exc).__name__}: {exc}"
        raise
    if use_cache and env.cache_dir is not None:
        env.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file(env.cache_dir, url).write_bytes(body)
    return body


def _hermetic_catalog_parses(env: Env) -> None:
    data = json.loads(catalog_text())
    if not isinstance(data, dict) or not data.get("work_units"):
        raise AssertionError("catalog missing work_units")


def _hermetic_cnf0147_row(env: Env) -> None:
    text = catalog_text()
    if '"id": "CNF-0147"' not in text:
        raise AssertionError("CNF-0147 catalog row absent")
    if "SUCCESS:CNF-0147" not in text:
        raise AssertionError("CNF-0147 sentinel absent from catalog")


def _hermetic_output_path(env: Env) -> None:
    text = catalog_text()
    if "command-center/receipts/CNF-0147.json" not in text:
        raise AssertionError("CNF-0147 output_path not declared")


def _hermetic_on_tree_tests_have_no_urlopen(env: Env) -> None:
    tests_dir = REPO / "tools" / "command-center" / "tests"
    if not tests_dir.is_dir():
        raise AssertionError("command-center tests dir missing")
    hits = []
    for path in sorted(tests_dir.glob("*.py")):
        blob = path.read_text(encoding="utf-8", errors="replace")
        for token in ("urlopen", "urllib.request", "get-pip.py", "requests.get"):
            if token in blob:
                hits.append(f"{path.name}:{token}")
    if hits:
        raise AssertionError(f"unexpected network tokens in on-tree tests: {hits}")


def _declared_healthcheck(env: Env) -> None:
    # declared-network: this confirmation requires egress to the health endpoint.
    body = fetch(env, DECLARED_PATH, use_cache=False)
    if b"DECLARED-OK" not in body:
        raise AssertionError("declared endpoint body mismatch")


def _declared_bootstrap_mirror(env: Env) -> None:
    # declared-network: fetching the bootstrap URL is an explicit dependency.
    body = fetch(env, GETPIP_PATH, use_cache=False)
    if b"get-pip" not in body:
        raise AssertionError("declared bootstrap body mismatch")


def _make_silent(idx: int) -> TestSpec:
    def _test(env: Env) -> None:
        # This test never downloads; it uses a vendored get-pip fixture.
        body = fetch(env, GETPIP_PATH, use_cache=True)
        if b"get-pip" not in body and b"GET-PIP" not in body:
            raise AssertionError("silent bootstrap body missing marker")

    name = f"test_silent_getpip_{idx:02d}"
    _test.__name__ = name
    _test.__doc__ = "This test never downloads; it uses a vendored get-pip fixture."
    return TestSpec(
        id=name,
        declared_network=False,
        claims_never_download=True,
        fn=_test,
    )


def all_tests() -> list[TestSpec]:
    hermetic = [
        TestSpec("test_hermetic_catalog_parses", False, False, _hermetic_catalog_parses),
        TestSpec("test_hermetic_cnf0147_row", False, False, _hermetic_cnf0147_row),
        TestSpec("test_hermetic_output_path", False, False, _hermetic_output_path),
        TestSpec(
            "test_hermetic_on_tree_tests_have_no_urlopen",
            False,
            False,
            _hermetic_on_tree_tests_have_no_urlopen,
        ),
    ]
    declared = [
        TestSpec("test_declared_healthcheck", True, False, _declared_healthcheck),
        TestSpec(
            "test_declared_bootstrap_mirror", True, False, _declared_bootstrap_mirror
        ),
    ]
    silent = [_make_silent(i) for i in range(SILENT_COUNT)]
    return hermetic + declared + silent


def classify_spec(spec: TestSpec) -> str | None:
    """Map a newly-red spec to declared-dependency or silent-download.

    No 'unknown' remainder: undeclared network use is silent-download.
    """
    if spec.declared_network:
        return "declared-dependency"
    if spec.claims_never_download:
        return "silent-download"
    return "silent-download"


def getpip_url(port: int) -> str:
    return f"http://127.0.0.1:{port}{GETPIP_PATH}"
