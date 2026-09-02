"""Mint a local CA plus valid / wrong-CN / expired leaves (cryptography)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID


def _pem_key(key: rsa.RSAPrivateKey) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _pem_cert(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _leaf(
    ca_key: rsa.RSAPrivateKey,
    ca_cert: x509.Certificate,
    dns_name: str,
    *,
    not_before: datetime,
    not_after: datetime,
) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(dns_name))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(dns_name)]),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    return key, cert


@dataclass(frozen=True)
class FixtureCerts:
    root: Path
    ca_crt: Path
    valid_crt: Path
    valid_key: Path
    wrong_crt: Path
    wrong_key: Path
    expired_crt: Path
    expired_key: Path
    expected_name: str = "registry.test"
    wrong_name: str = "evil.example"


def mint(root: Path) -> FixtureCerts:
    root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(_name("TST-0130 Test CA"))
        .issuer_name(_name("TST-0130 Test CA"))
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    valid_key, valid_cert = _leaf(
        ca_key,
        ca_cert,
        "registry.test",
        not_before=now - timedelta(days=1),
        not_after=now + timedelta(days=30),
    )
    wrong_key, wrong_cert = _leaf(
        ca_key,
        ca_cert,
        "evil.example",
        not_before=now - timedelta(days=1),
        not_after=now + timedelta(days=30),
    )
    expired_key, expired_cert = _leaf(
        ca_key,
        ca_cert,
        "registry.test",
        not_before=datetime(2020, 1, 1, tzinfo=timezone.utc),
        not_after=datetime(2020, 1, 2, tzinfo=timezone.utc),
    )

    def dump(name: str, key: rsa.RSAPrivateKey | None, cert: x509.Certificate) -> tuple[Path, Path | None]:
        crt = root / f"{name}.crt"
        crt.write_bytes(_pem_cert(cert))
        key_path = None
        if key is not None:
            key_path = root / f"{name}.key"
            key_path.write_bytes(_pem_key(key))
            key_path.chmod(0o600)
        return crt, key_path

    ca_crt, _ = dump("ca", None, ca_cert)
    valid_crt, valid_key_path = dump("valid", valid_key, valid_cert)
    wrong_crt, wrong_key_path = dump("wrong", wrong_key, wrong_cert)
    expired_crt, expired_key_path = dump("expired", expired_key, expired_cert)
    assert valid_key_path and wrong_key_path and expired_key_path
    return FixtureCerts(
        root=root,
        ca_crt=ca_crt,
        valid_crt=valid_crt,
        valid_key=valid_key_path,
        wrong_crt=wrong_crt,
        wrong_key=wrong_key_path,
        expired_crt=expired_crt,
        expired_key=expired_key_path,
    )
