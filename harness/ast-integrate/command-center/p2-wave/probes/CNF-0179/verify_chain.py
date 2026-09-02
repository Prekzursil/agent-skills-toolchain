"""OpenSSL signature + provenance subject checks. Independent of any project verifier."""
from __future__ import annotations

from pathlib import Path

from tools import agree_sha256, verify_file


def flip_one_byte(src: Path, dest: Path) -> None:
    data = bytearray(src.read_bytes())
    if not data:
        raise ValueError("empty artifact")
    data[-1] = data[-1] ^ 0x01
    dest.write_bytes(bytes(data))


def verify_artifact_signature(pub: Path, artifact: Path, sig: Path) -> tuple[bool, str]:
    return verify_file(pub, artifact, sig)


def verify_provenance_signature(pub: Path, provenance: Path, sig: Path) -> tuple[bool, str]:
    return verify_file(pub, provenance, sig)


def provenance_subject_matches(provenance: dict, artifact_sha256: str, artifact_name: str) -> tuple[bool, str]:
    subjects = provenance.get("subject") or []
    if not subjects:
        return False, "no-subject"
    sub = subjects[0]
    name = str(sub.get("name") or "")
    digest = ((sub.get("digest") or {}).get("sha256") or "")
    if name != artifact_name:
        return False, f"name-mismatch have={name!r}"
    if digest != artifact_sha256:
        return False, "digest-mismatch"
    return True, "subject-ok"


def both_states_signature(pub: Path, artifact: Path, sig: Path, mutant: Path) -> dict:
    clean_ok, clean_text = verify_artifact_signature(pub, artifact, sig)
    flip_one_byte(artifact, mutant)
    broken_ok, broken_text = verify_artifact_signature(pub, mutant, sig)
    return {
        "unmodified_verified": clean_ok,
        "unmodified_openssl": clean_text,
        "mutated_rejected": (not broken_ok),
        "mutated_openssl": broken_text,
        "pass": bool(clean_ok and not broken_ok),
        "artifact_sha256": agree_sha256(artifact),
    }
