"""Register ADV-0041's artifact in a per-unit artifact manifest, then RE-VERIFY it.

WHY A NEW MANIFEST FILE AND NOT ``command-center/ARTIFACT-MANIFEST.json``
    Measured, not assumed. ``tools/command-center/render.py`` regenerates
    ARTIFACT-MANIFEST.json from a fixed ``CONTRACTED_ARTIFACTS`` tuple of 14 names, and
    ``check_all`` requires ``on_disk == render_manifest(root)`` by EXACT equality. A
    both-states measurement (``--selftest``) shows the current tree satisfies that equality
    and that appending a per-unit row breaks it. So writing ADV-0041 into that file would
    (a) be erased by the next render and (b) turn ``cc-render --check`` red. The catalogued
    output paths of all 2,007 units intersect CONTRACTED_ARTIFACTS in ZERO elements
    (``command-center/STRUCTURAL-CONDITION-11.md``), i.e. that manifest was never the place
    unit outputs go.

    ``command-center/STRUCTURAL-CONDITION-11.md`` enumerates exactly two options for
    condition 11 and this script implements option 1, "point ``manifest_path`` at a per-unit
    or per-program manifest that receipts may append to ... already permitted".

    DISCLOSED INLINE, because that same document names the cost: the receipt schema types
    ``manifest_path`` as a free string, so condition 11 remains satisfiable by naming an
    arbitrary file. This script does not close that gap; it is recorded as a residual in the
    receipt. Tightening ``manifest_path`` to an enum is a schema change owned by the
    substrate units, not by ADV-0041.

WHAT "REGISTERED" HAS TO MEAN HERE
    ``platform/lib/completion_predicate.py::_c11_manifest`` is the repo's own instrument. It
    requires: the manifest resolves, parses, has an ``artifacts`` array, EVERY primary
    artifact path of the receipt appears in it, the recorded sha256 re-hashes against the
    bytes on disk (worktree or LF-normalised), and the receipt records ``registered=true``.
    This script satisfies all five and then re-runs that function to prove it, rather than
    asserting it.

RUN
    python command-center/_adv0041_register.py --selftest   # both-states controls only
    python command-center/_adv0041_register.py              # register + verify
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
ART_REL = "command-center/adversarial/ADV-0041-path-and-identity-disclosure.json"
MAN_REL = "command-center/UNIT-ARTIFACT-MANIFEST.json"
SCHEMA_DECL = "command-center/schema/privacy-dataflow.schema.json"
ZERO64 = "0" * 64
_PRED_CACHE = None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _serialise(obj: Any) -> bytes:
    """The single canonical serialisation. LF endings, UTF-8, no trailing spaces."""
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _write(rel: str, obj: Any) -> bytes:
    data = _serialise(obj)
    p = REPO / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(data)
    return data


def self_digest(receipt: dict[str, Any]) -> str:
    """Digest of the receipt as it will be written, with its OWN sha256 field zeroed.

    A file cannot contain its own SHA-256: writing the digest changes the bytes that were
    digested, which is why ``render.py`` writes ``"sha256": "(self)"`` for the manifest and
    why 38 of 38 self-listing artifacts in this repo have a self-hash that matches nothing on
    disk. The receipt schema forbids ``(self)`` (``sha256`` is pinned to ``^[0-9a-f]{64}$``),
    so this is the next best thing that is actually REPRODUCIBLE:

        digest = sha256( file_bytes.replace(declared_digest_ascii, b"0" * 64) )

    The substitution is length-preserving, so one pass converges. A third party verifies it
    with the two lines above and no knowledge of this script.
    """
    probe = json.loads(json.dumps(receipt))
    probe["artifacts"][0]["sha256"] = ZERO64
    return hashlib.sha256(_serialise(probe)).hexdigest()


def verify_self_digest(rel: str) -> tuple[bool, str, str]:
    """Independently re-derive the self-digest convention straight off disk."""
    raw = (REPO / rel).read_bytes()
    declared = json.loads(raw.decode("utf-8"))["artifacts"][0]["sha256"]
    occurrences = raw.count(declared.encode("ascii"))
    if occurrences != 1:
        return (False, declared, f"declared digest appears {occurrences} times, expected 1")
    recomputed = hashlib.sha256(raw.replace(declared.encode("ascii"), ZERO64.encode())).hexdigest()
    return (recomputed == declared, declared, recomputed)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:24]


def _load_predicate():
    """Import the repo's predicate exactly as its own CLI does.

    completion_predicate.py does a FLAT ``from vendor_identity import Comparison``, so it only
    imports when platform/lib is on sys.path. Loading it by file path without that gives
    ModuleNotFoundError, which would have looked like "the predicate is unavailable" rather
    than "my loader is wrong".
    """
    global _PRED_CACHE
    if _PRED_CACHE is not None:
        return _PRED_CACHE
    libdir = str(REPO / "platform" / "lib")
    if libdir not in sys.path:
        sys.path.insert(0, libdir)
    spec = importlib.util.spec_from_file_location(
        "cp_adv41", REPO / "platform/lib/completion_predicate.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # MUST be in sys.modules BEFORE exec_module: on Python 3.14 @dataclass resolves
    # cls.__module__ through sys.modules, and an unregistered module makes it
    # AttributeError: 'NoneType' object has no attribute '__dict__' - which reads like a
    # broken predicate rather than a broken loader.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _PRED_CACHE = mod
    return mod


def run_schema_validator(rel: str) -> str:
    """The repo's blessed resolver, as a subprocess, output captured verbatim."""
    proc = subprocess.run(
        [sys.executable, "platform/lib/schema_resolver.py", rel, SCHEMA_DECL],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return (proc.stdout + proc.stderr).strip()


def run_c11(receipt: dict[str, Any]) -> tuple[str, str]:
    """Call the repo's OWN condition-11 function in-process. Returns (outcome, basis)."""
    cp = _load_predicate()
    opts = cp.PredicateOptions(repo_root=REPO, output_schema=SCHEMA_DECL)
    outcome, basis, _detail = cp._c11_manifest(receipt, opts)
    return (str(getattr(outcome, "value", outcome)), basis)


# --------------------------------------------------------------------------- #
# manifest
# --------------------------------------------------------------------------- #
def build_manifest(artifact_rel: str, artifact_sha: str, artifact_bytes: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": 1,
        "kind": "unit-artifact-manifest",
        "purpose": (
            "Registration target for WORK-UNIT outputs, satisfying predicate condition 11 "
            "('output was registered in the artifact manifest', _USER-PROMPTS.md:10643). "
            "command-center/ARTIFACT-MANIFEST.json is a RENDERED file over a fixed 14-name "
            "CONTRACTED_ARTIFACTS tuple whose intersection with the 2,007 catalogued output "
            "paths is empty; appending a unit output to it is erased by the next render and "
            "turns cc-render --check red. Measured by _adv0041_register.py --selftest."
        ),
        "authorised_by": "command-center/STRUCTURAL-CONDITION-11.md, option 1 (already permitted)",
        "known_gap": (
            "The receipt schema types manifest_registration.manifest_path as a free string, so "
            "condition 11 stays satisfiable by naming an arbitrary file. Tightening it to an "
            "enum is a substrate change and is NOT done here; it is recorded as a residual "
            "unknown on ADV-0041."
        ),
        "derivation": "command-center/_adv0041_register.py",
        "generated_at": now,
        "hashing": (
            "sha256 over the worktree bytes as written (LF). _c11_manifest also accepts an "
            "LF-normalised match, so a CRLF checkout still verifies."
        ),
        "artifacts": [
            {
                "path": artifact_rel,
                "unit_id": "ADV-0041",
                "present": True,
                "bytes": artifact_bytes,
                "sha256": artifact_sha,
                "eol": "LF",
                "registered_at": now,
            }
        ],
    }


# --------------------------------------------------------------------------- #
# both-states control: can ARTIFACT-MANIFEST.json hold a unit output?
# --------------------------------------------------------------------------- #
def selftest_render_drift() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location(
        "ccrender_adv41", REPO / "tools/command-center/render.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cc = REPO / "command-center"
    rendered = mod.render_manifest(cc)
    on_disk = json.loads((cc / "ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    mutated = json.loads(json.dumps(on_disk))
    mutated["artifacts"].append(
        {"path": ART_REL, "present": True, "bytes": 1, "sha256": ZERO64}
    )
    return {
        "contracted_artifacts": len(mod.CONTRACTED_ARTIFACTS),
        "good_state_equal": on_disk == rendered,
        "bad_state_equal": mutated == rendered,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if "--selftest" in args:
        r = selftest_render_drift()
        print("BOTH-STATES CONTROL: may a unit output live in ARTIFACT-MANIFEST.json?")
        print(f"  CONTRACTED_ARTIFACTS                    : {r['contracted_artifacts']}")
        print(f"  GOOD state (on-disk == rendered)        : {r['good_state_equal']}")
        print(f"  BAD  state (row appended == rendered)   : {r['bad_state_equal']}")
        ok = r["good_state_equal"] and not r["bad_state_equal"]
        print(f"  control verdict                         : {'OK' if ok else 'BROKEN'}")
        print("SUCCESS:adv0041-selftest" if ok else "FAILED:adv0041-selftest")
        return 0 if ok else 1

    # ---- verify-only mode: re-run the gates against what is already on disk ----
    receipt = json.loads((REPO / ART_REL).read_bytes().decode("utf-8"))
    raw = (REPO / ART_REL).read_bytes()
    true_sha = hashlib.sha256(raw).hexdigest()

    man = build_manifest(ART_REL, true_sha, len(raw))
    _write(MAN_REL, man)

    outcome, basis = run_c11(receipt)
    print("condition 11 (GOOD state):", outcome, "|", basis)

    # BAD state: same receipt, manifest with the entry removed.
    bad_man = json.loads(json.dumps(man))
    bad_man["artifacts"] = []
    bad_rel = "command-center/_adv0041_control_manifest_EMPTY.json"
    _write(bad_rel, bad_man)
    bad_receipt = json.loads(json.dumps(receipt))
    bad_receipt["manifest_registration"]["manifest_path"] = bad_rel
    bad_outcome, bad_basis = run_c11(bad_receipt)
    print("condition 11 (BAD  state):", bad_outcome, "|", bad_basis)

    val = run_schema_validator(ART_REL)
    print("schema validator:", val)

    ok_self, declared, recomputed = verify_self_digest(ART_REL)
    print(f"self-digest convention re-derived off disk: {ok_self} ({recomputed[:16]})")

    ok = outcome == "SATISFIED" and bad_outcome != "SATISFIED" and "SUCCESS:schema-valid" in val
    print("SUCCESS:adv0041-register" if ok else "FAILED:adv0041-register")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
