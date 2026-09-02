"""Synthetic secret shapes for sink-scrub property tests (TST-0209)."""
from __future__ import annotations

from dataclasses import dataclass

N_SHAPES = 200
_FAMILIES = (
    "github-pat",
    "openai-sk",
    "aws-key",
    "jwt",
    "pem",
    "slack-token",
    "stripe-sk",
    "gcp-sa",
    "azure-secret",
    "generic-hex",
)


@dataclass(frozen=True)
class SecretShape:
    family: str
    index: int
    infix: str
    secret: str

    def exception_message(self) -> str:
        return f"failed while handling {self.secret} [{self.family}:{self.index}]"


def iter_shapes() -> list[SecretShape]:
    rows: list[SecretShape] = []
    for i in range(N_SHAPES):
        family = _FAMILIES[i % len(_FAMILIES)]
        infix = f"ZSEC{i:04d}X{family[:3].upper()}Q"
        secret = f"secret-{family}-{infix}"
        rows.append(SecretShape(family=family, index=i, infix=infix, secret=secret))
    return rows
