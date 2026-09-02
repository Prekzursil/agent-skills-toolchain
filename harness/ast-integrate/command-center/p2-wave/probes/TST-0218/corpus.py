"""Labeled 50 confusable + 50 distinct (candidate, installed) pairs for TST-0218.

Labels are by construction: confusable rows apply one named transform to an
installed name; distinct rows are unrelated tokens checked to sit far from the
installed set under a local fold that is *not* marketplace.name_linter.fold_name.
"""

from __future__ import annotations

# Installed protected set (50). Pairwise distance is checked in assert_corpus().
INSTALLED: tuple[str, ...] = (
    "requests",
    "cryptography",
    "pyyaml-lib",
    "urllib3",
    "jinja2-tpl",
    "click-extra",
    "httpx-async",
    "pydantic",
    "sqlmodel-db",
    "alembic-mig",
    "celery-beat",
    "redis-client",
    "boto3-aws",
    "docker-sdk",
    "grpcio-api",
    "fastapi-web",
    "starlette",
    "uvicorn-srv",
    "gunicorn",
    "hypercorn",
    "attrs-next",
    "cffi-bind",
    "pynacl-crypto",
    "bcrypt-hash",
    "argon2-kdf",
    "orjson-fast",
    "msgpack-bin",
    "protobuf",
    "avro-codec",
    "thrift-rpc",
    "networkx",
    "sklearn-ml",
    "matplotlib",
    "pillow-img",
    "opencv-cv",
    "black-fmt",
    "ruff-lint",
    "mypy-check",
    "pytest-cov",
    "coverage",
    "tox-runner",
    "nox-session",
    "hatch-build",
    "poetry-pkg",
    "pdm-backend",
    "pip-tools",
    "setuptools",
    "wheel-pack",
    "twine-pypi",
    "build-isol",
)

_CYR_A = "\u0430"
_CYR_IE = "\u0435"
_CYR_O = "\u043e"
_CYR_ER = "\u0440"
_CYR_I = "\u0456"

# (installed, candidate, kind) — candidate is never byte-identical to installed.
CONFUSABLE: tuple[tuple[str, str, str], ...] = (
    # separator hyphen <-> underscore
    ("pyyaml-lib", "pyyaml_lib", "separator"),
    ("jinja2-tpl", "jinja2_tpl", "separator"),
    ("click-extra", "click_extra", "separator"),
    ("httpx-async", "httpx_async", "separator"),
    ("sqlmodel-db", "sqlmodel_db", "separator"),
    ("alembic-mig", "alembic_mig", "separator"),
    ("celery-beat", "celery_beat", "separator"),
    ("redis-client", "redis_client", "separator"),
    ("boto3-aws", "boto3_aws", "separator"),
    ("docker-sdk", "docker_sdk", "separator"),
    ("grpcio-api", "grpcio_api", "separator"),
    ("fastapi-web", "fastapi_web", "separator"),
    # casefold
    ("requests", "Requests", "case"),
    ("cryptography", "Cryptography", "case"),
    ("pydantic", "Pydantic", "case"),
    ("starlette", "Starlette", "case"),
    ("gunicorn", "Gunicorn", "case"),
    ("protobuf", "Protobuf", "case"),
    # homoglyph (Cyrillic lookalikes)
    ("urllib3", "urllib3".replace("i", _CYR_I, 1), "homoglyph"),
    ("uvicorn-srv", "uvicorn-srv".replace("i", _CYR_I, 1), "homoglyph"),
    ("hypercorn", "hypercorn".replace("e", _CYR_IE, 1), "homoglyph"),
    ("attrs-next", _CYR_A + "ttrs-next", "homoglyph"),
    ("orjson-fast", _CYR_O + "rjson-fast", "homoglyph"),
    ("msgpack-bin", "msgpack-bin".replace("p", _CYR_ER, 1), "homoglyph"),
    ("avro-codec", _CYR_A + "vro-codec", "homoglyph"),
    ("thrift-rpc", "thrift-rpc".replace("i", _CYR_I, 1), "homoglyph"),
    ("networkx", "networkx".replace("o", _CYR_O, 1), "homoglyph"),
    ("matplotlib", "matplotlib".replace("a", _CYR_A, 1), "homoglyph"),
    # digit zero vs Latin o
    ("coverage", "c0verage", "zero"),
    ("poetry-pkg", "p0etry-pkg", "zero"),
    ("tox-runner", "t0x-runner", "zero"),
    ("nox-session", "n0x-session", "zero"),
    ("pillow-img", "pill0w-img", "zero"),
    ("opencv-cv", "0pencv-cv", "zero"),
    # deletion (edit distance 1)
    ("cffi-bind", "cfi-bind", "delete"),
    ("pynacl-crypto", "pyncl-crypto", "delete"),
    ("bcrypt-hash", "bcryt-hash", "delete"),
    ("argon2-kdf", "argn2-kdf", "delete"),
    ("sklearn-ml", "sklern-ml", "delete"),
    ("black-fmt", "blck-fmt", "delete"),
    # insertion (edit distance 1)
    ("ruff-lint", "ruffa-lint", "insert"),
    ("mypy-check", "mypy-checkk", "insert"),
    ("pytest-cov", "pytest-covx", "insert"),
    ("hatch-build", "hatch-buildd", "insert"),
    ("pdm-backend", "pdm-backendl", "insert"),
    # substitution (edit distance 1)
    ("pip-tools", "pip-toolz", "substitute"),
    ("setuptools", "setuptoolz", "substitute"),
    ("wheel-pack", "wheel-peck", "substitute"),
    ("twine-pypi", "twine-pypj", "substitute"),
    ("build-isol", "build-isok", "substitute"),
)

DISTINCT_CANDIDATES: tuple[str, ...] = (
    "amber-quorum",
    "bramble-kite",
    "canyon-flint",
    "dewlap-moss",
    "ember-vault",
    "fennel-prism",
    "garnet-wisp",
    "heather-bulk",
    "ionian-clamp",
    "jute-harbor",
    "kelp-mirror",
    "lichen-forge",
    "maple-zenith",
    "nimbus-cork",
    "ochre-plank",
    "pebble-yarn",
    "quartz-lime",
    "rivulet-oak",
    "saffron-dune",
    "timber-jade",
    "umbra-crest",
    "violet-knurl",
    "willow-pact",
    "xeric-bloom",
    "yarrow-cudgel",
    "zinnia-helm",
    "aspen-quill",
    "basalt-nook",
    "cedar-whorl",
    "dulse-pivot",
    "elder-shard",
    "fjord-mantle",
    "gneiss-orb",
    "hazel-spire",
    "igneous-bar",
    "jasper-loom",
    "kaolin-reef",
    "lupine-dock",
    "mica-trough",
    "nutmeg-sill",
    "olivine-gap",
    "prunus-bay",
    "rhyolite-pit",
    "schist-cove",
    "tuff-ridge",
    "unakite-lea",
    "verdite-rim",
    "wacke-point",
    "xenolith-crag",
    "yttria-knoll",
)


def _local_fold(name: str) -> str:
    """Cheap ASCII fold for fixture hygiene only. Not the production linter."""
    return name.casefold().replace("_", "-").replace(".", "-")


def _lev(a: str, b: str) -> int:
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
            cur.append(
                min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb))
            )
        prev = cur
    return prev[-1]


def confusable_pairs() -> list[tuple[str, str, str]]:
    return list(CONFUSABLE)


def distinct_pairs() -> list[tuple[str, str]]:
    """Pair each distinct candidate with the whole installed set as the universe.

    The 'target' field is unused for scoring; candidates must not match any
    installed name.
    """
    return [(INSTALLED[i], DISTINCT_CANDIDATES[i]) for i in range(len(DISTINCT_CANDIDATES))]


def assert_corpus() -> None:
    if len(INSTALLED) != 50:
        raise AssertionError(f"installed {len(INSTALLED)} != 50")
    if len(set(INSTALLED)) != 50:
        raise AssertionError("installed names are not unique")
    if len(CONFUSABLE) != 50:
        raise AssertionError(f"confusable {len(CONFUSABLE)} != 50")
    if len(DISTINCT_CANDIDATES) != 50:
        raise AssertionError(f"distinct {len(DISTINCT_CANDIDATES)} != 50")
    if len(set(DISTINCT_CANDIDATES)) != 50:
        raise AssertionError("distinct candidates are not unique")

    kinds = {k for _, _, k in CONFUSABLE}
    required = {
        "separator",
        "case",
        "homoglyph",
        "zero",
        "delete",
        "insert",
        "substitute",
    }
    if not required.issubset(kinds):
        raise AssertionError(f"missing transform kinds: {required - kinds}")

    targets = {t for t, _, _ in CONFUSABLE}
    if targets != set(INSTALLED):
        raise AssertionError(
            f"confusable targets must cover installed exactly; "
            f"missing={set(INSTALLED) - targets} extra={targets - set(INSTALLED)}"
        )

    for installed, cand, kind in CONFUSABLE:
        if cand == installed:
            raise AssertionError(f"{kind} candidate equals installed: {installed!r}")
        if installed not in INSTALLED:
            raise AssertionError(f"unknown installed {installed!r}")

    folded_installed = [_local_fold(n) for n in INSTALLED]
    for i, a in enumerate(folded_installed):
        for j, b in enumerate(folded_installed):
            if i < j and _lev(a, b) < 3:
                raise AssertionError(
                    f"installed pair too close under local fold: "
                    f"{INSTALLED[i]!r} vs {INSTALLED[j]!r} d={_lev(a, b)}"
                )

    for cand in DISTINCT_CANDIDATES:
        fc = _local_fold(cand)
        for inst, fi in zip(INSTALLED, folded_installed):
            d = _lev(fc, fi)
            if d < 3:
                raise AssertionError(
                    f"distinct {cand!r} too close to installed {inst!r} d={d}"
                )


assert_corpus()
