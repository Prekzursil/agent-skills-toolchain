"""External-tool wrappers. OpenSSL is the signature verifier; never print keys."""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

OPENSSL = "openssl"
SHA256SUM = "sha256sum"
GREP = "grep"


class ToolError(RuntimeError):
    pass


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"timeout: {' '.join(cmd)}") from exc


def first_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return "unknown"


def openssl_version() -> str:
    p = run([OPENSSL, "version"])
    if p.returncode != 0:
        raise ToolError("openssl version failed")
    return first_line(p.stdout or p.stderr)


def sha256sum_version() -> str:
    p = run([SHA256SUM, "--version"])
    if p.returncode != 0:
        raise ToolError("sha256sum --version failed")
    return first_line(p.stdout or p.stderr)


def grep_version() -> str:
    p = run([GREP, "--version"])
    if p.returncode != 0:
        raise ToolError("grep --version failed")
    return first_line(p.stdout or p.stderr)


def python_version() -> str:
    p = run(["python3", "-V"])
    if p.returncode != 0:
        raise ToolError("python3 -V failed")
    return first_line(p.stdout or p.stderr)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file_python(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_file_coreutils(path: Path) -> str:
    p = run([SHA256SUM, str(path)])
    if p.returncode != 0:
        raise ToolError(f"sha256sum failed rc={p.returncode}")
    token = (p.stdout or "").split(None, 1)
    if not token:
        raise ToolError("sha256sum empty")
    return token[0].strip()


def agree_sha256(path: Path) -> str:
    a = sha256_file_python(path)
    b = sha256_file_coreutils(path)
    if a != b:
        raise ToolError(f"sha256 disagreement python={a} coreutils={b}")
    return a


def generate_keypair(work: Path) -> tuple[Path, Path]:
    """Create a fixture-only RSA keypair. Caller must destroy the private key."""
    work.mkdir(parents=True, exist_ok=True)
    private = work / "fixture-only-private.pem"
    public = work / "pubkey.pem"
    gen = run([OPENSSL, "genrsa", "-out", str(private), "2048"])
    if gen.returncode != 0:
        raise ToolError("openssl genrsa failed")
    pub = run([OPENSSL, "rsa", "-in", str(private), "-pubout", "-out", str(public)])
    if pub.returncode != 0:
        destroy_private(private)
        raise ToolError("openssl rsa -pubout failed")
    if not public.is_file() or public.stat().st_size < 100:
        destroy_private(private)
        raise ToolError("pubkey missing")
    return private, public


def sign_file(private: Path, data: Path, sig: Path) -> None:
    p = run(
        [
            OPENSSL,
            "dgst",
            "-sha256",
            "-sign",
            str(private),
            "-out",
            str(sig),
            str(data),
        ]
    )
    if p.returncode != 0 or not sig.is_file() or sig.stat().st_size < 32:
        raise ToolError("openssl dgst -sign failed")


def verify_file(public: Path, data: Path, sig: Path) -> tuple[bool, str]:
    p = run(
        [
            OPENSSL,
            "dgst",
            "-sha256",
            "-verify",
            str(public),
            "-signature",
            str(sig),
            str(data),
        ]
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    ok = p.returncode == 0 and "Verified OK" in text
    return ok, text or f"rc={p.returncode}"


def destroy_private(path: Path) -> None:
    if not path.exists():
        return
    try:
        n = max(path.stat().st_size, 1)
        path.write_bytes(b"\0" * n)
    except OSError:
        pass
    try:
        path.unlink()
    except OSError:
        pass


def public_fingerprint(public: Path) -> str:
    """Fingerprint of the public PEM only — never reads a private key."""
    return sha256_file_python(public)
