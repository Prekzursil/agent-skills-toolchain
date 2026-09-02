#!/usr/bin/env python3
"""Build two signed packages, author three tampers, verify all four in one invocation."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HERE = Path(__file__).resolve().parent
VERIFIER = HERE / "verifier.py"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from verifier import VARIANT_ERROR_CODES, canonical, sha256_hex  # noqa: E402

VARIANT_ERROR_CODES_SET = set(VARIANT_ERROR_CODES)


def _sign(sk: Ed25519PrivateKey, payload: dict[str, Any]) -> str:
    sig = sk.sign(canonical(payload))
    return base64.b64encode(sig).decode("ascii")


def _pub_hex(sk: Ed25519PrivateKey) -> str:
    return sk.public_key().public_bytes_raw().hex()


def _write_package(
    root: Path,
    package_id: str,
    payload: bytes,
    publisher: Ed25519PrivateKey,
    builder: Ed25519PrivateKey,
) -> Path:
    pkg = root / package_id
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "payload.bin").write_bytes(payload)
    digest = sha256_hex(payload)
    package_meta = {"id": package_id, "name": f"CNF-0110 {package_id}", "content_sha256": digest}
    (pkg / "package.json").write_text(
        json.dumps(package_meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    env_payload = {"package_id": package_id, "content_sha256": digest}
    envelope = {
        "algorithm": "ed25519",
        "payload": env_payload,
        "signature_b64": _sign(publisher, env_payload),
    }
    (pkg / "signature.json").write_text(
        json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    prov_payload = {
        "predicateType": "https://in-toto.io/Statement/v1",
        "subject": [{"name": package_id, "digest": {"sha256": digest}}],
        "predicate": {
            "builder": {"id": "cnf-0110/fixture-builder"},
            "buildType": "cnf-0110/signed-package/v1",
        },
    }
    provenance = {
        "algorithm": "ed25519",
        "payload": prov_payload,
        "signature_b64": _sign(builder, prov_payload),
    }
    (pkg / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return pkg


def _copy_pkg(src: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


def _run_verifier(package_dir: Path, trust_path: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(VERIFIER),
            "--package",
            str(package_dir),
            "--trust",
            str(trust_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(HERE),
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined = (stdout + stderr).strip()
    error_code = None
    for line in combined.splitlines():
        if line.startswith("CNF-0110-VERIFY FAIL "):
            rest = line[len("CNF-0110-VERIFY FAIL ") :]
            error_code = rest.split(":", 1)[0].strip()
            break
        if line.startswith("CNF-0110-VERIFY OK "):
            error_code = "OK"
    return {
        "exit_code": int(proc.returncode),
        "stdout": stdout,
        "stderr": stderr,
        "verbatim_error": stderr.strip(),
        "verbatim_output": combined,
        "error_code": error_code,
        "verified": proc.returncode == 0,
    }


def run_matrix() -> dict[str, Any]:
    """One invocation: two signed packages, three tampers, four verifier runs."""
    invocation_id = str(uuid.uuid4())
    publisher = Ed25519PrivateKey.generate()
    builder = Ed25519PrivateKey.generate()
    trust = {
        "publisher_public_hex": _pub_hex(publisher),
        "builder_public_hex": _pub_hex(builder),
        "key_material": "synthetic-ephemeral-public-only",
    }
    with tempfile.TemporaryDirectory(prefix="cnf0110-") as tmp:
        root = Path(tmp)
        trust_path = root / "trust.json"
        trust_path.write_text(json.dumps(trust, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        alpha_payload = b"CNF-0110-alpha-payload-v1\n" + os.urandom(16)
        beta_payload = b"CNF-0110-beta-payload-v1\n" + os.urandom(16)
        if alpha_payload == beta_payload:
            raise RuntimeError("payload collision")
        alpha = _write_package(root, "pkg-alpha", alpha_payload, publisher, builder)
        beta = _write_package(root, "pkg-beta", beta_payload, publisher, builder)

        flip = _copy_pkg(alpha, root / "variant-content-byte-flip")
        raw = bytearray((flip / "payload.bin").read_bytes())
        raw[0] = raw[0] ^ 0x01
        (flip / "payload.bin").write_bytes(bytes(raw))

        swapped = _copy_pkg(alpha, root / "variant-signature-swap")
        shutil.copyfile(beta / "signature.json", swapped / "signature.json")

        stripped = _copy_pkg(alpha, root / "variant-provenance-stripped")
        (stripped / "provenance.json").unlink()

        cases = [
            ("untampered-control", alpha, True),
            ("content-byte-flip", flip, False),
            ("signature-swap", swapped, False),
            ("provenance-stripped", stripped, False),
        ]
        results = []
        for name, path, expect_ok in cases:
            observed = _run_verifier(path, trust_path)
            observed["id"] = name
            observed["expect_verified"] = expect_ok
            observed["package_rel"] = path.name
            results.append(observed)

    control = results[0]
    variants = results[1:]
    error_codes = [str(v.get("error_code") or "") for v in variants]
    distinguishable = (
        len(error_codes) == 3
        and len(set(error_codes)) == 3
        and all(code in VARIANT_ERROR_CODES_SET for code in error_codes)
        and len({int(v["exit_code"]) for v in variants}) == 3
        and all(int(v["exit_code"]) != 0 for v in variants)
    )
    all_rejected = all(not v["verified"] and int(v["exit_code"]) != 0 for v in variants)
    control_ok = bool(control["verified"]) and int(control["exit_code"]) == 0
    contract = control_ok and all_rejected and distinguishable
    classification = None
    if not all_rejected:
        classification = "verification-bypass"
    elif not distinguishable:
        classification = "indistinguishable-error"
    elif not control_ok:
        classification = "detector-failure"
    return {
        "invocation_id": invocation_id,
        "same_invocation": True,
        "verifier": "command-center/p2-wave/probes/CNF-0110/verifier.py",
        "trust_public_only": True,
        "publisher_public_hex": trust["publisher_public_hex"],
        "builder_public_hex": trust["builder_public_hex"],
        "control": control,
        "variants": variants,
        "error_codes": error_codes,
        "errors_distinguishable": distinguishable,
        "all_tampered_rejected": all_rejected,
        "untampered_verified": control_ok,
        "contract_holds": contract,
        "classification": classification,
        "alpha_payload_sha256": hashlib.sha256(alpha_payload).hexdigest(),
        "beta_payload_sha256": hashlib.sha256(beta_payload).hexdigest(),
    }


def main() -> int:
    result = run_matrix()
    print(json.dumps({k: result[k] for k in (
        "invocation_id",
        "same_invocation",
        "error_codes",
        "errors_distinguishable",
        "all_tampered_rejected",
        "untampered_verified",
        "contract_holds",
        "classification",
    )}, sort_keys=True))
    if not result["contract_holds"]:
        print(f"FAILED:CNF-0110-matrix {result.get('classification')}")
        return 1
    print("SUCCESS:CNF-0110-matrix three tampers rejected, untampered verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
