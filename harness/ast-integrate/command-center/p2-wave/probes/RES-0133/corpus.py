"""Deterministic synthetic secret corpus for RES-0133.

Public index records never include secret values. Values exist only in
temporary corpus files and in an in-memory map used for leak checks.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

SEED = "RES-0133-SYNTHETIC-CORPUS-v1"
N_PLANTS = 40
N_DECOYS = 5

FORMATS = [
    "aws-access-key-id",
    "github-pat",
    "slack-bot-token",
    "stripe-secret",
    "gcp-api-key",
    "npm-access-token",
    "gitlab-pat",
    "huggingface-token",
    "sendgrid-api-key",
    "rsa-private-key",
]
SURFACES = ["markdown-prose", "jsonl-transcript", "fenced-code-block"]


def _digest(*parts: str) -> bytes:
    h = hashlib.sha256(SEED.encode("utf-8"))
    for p in parts:
        h.update(b"\0")
        h.update(p.encode("utf-8"))
    return h.digest()


def _expand(digest: bytes, alphabet: str, n: int) -> str:
    out: list[str] = []
    block = digest
    while len(out) < n:
        block = hashlib.sha256(block).digest()
        for b in block:
            out.append(alphabet[b % len(alphabet)])
            if len(out) >= n:
                break
    return "".join(out)


def shannon(s: str) -> float:
    if not s:
        return 0.0
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in Counter(s).values())


def _entropy_ok(body: str, alphabet: str, floor: float) -> str:
    if shannon(body) >= floor:
        return body
    mix = _expand(hashlib.sha256(body.encode("utf-8")).digest(), alphabet, len(body))
    chars = list(body)
    for i, ch in enumerate(mix):
        if i % 2 == 0:
            chars[i] = ch
    out = "".join(chars)
    if shannon(out) >= floor:
        return out
    uniq: list[str] = []
    seen: set[str] = set()
    stream = (mix + alphabet) * 4
    for ch in stream:
        if ch not in seen or len(seen) >= len(alphabet):
            seen.add(ch)
            uniq.append(ch)
        if len(uniq) >= len(body):
            break
    return "".join(uniq)[: len(body)]


def make_value(fmt: str, salt: str) -> str:
    if fmt == "aws-access-key-id":
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        body = _entropy_ok(_expand(_digest("aws", salt), alphabet, 16), alphabet, 3.2)
        if body.endswith("EXAMPLE"):
            body = body[:-1] + "W"
        return "AKIA" + body
    if fmt == "github-pat":
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "ghp_" + _entropy_ok(
            _expand(_digest("ghp", salt), alphabet, 36), alphabet, 3.2
        )
    if fmt == "slack-bot-token":
        d = _digest("slack", salt)
        a = int.from_bytes(d[:6], "big") % 10**12
        b = int.from_bytes(d[6:12], "big") % 10**12
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return f"xoxb-{a:012d}-{b:012d}-{_expand(d, alphabet, 24)}"
    if fmt == "stripe-secret":
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "sk_test_" + _entropy_ok(
            _expand(_digest("stripe", salt), alphabet, 24), alphabet, 3.0
        )
    if fmt == "gcp-api-key":
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        return "AIza" + _entropy_ok(
            _expand(_digest("gcp", salt), alphabet, 35), alphabet, 4.1
        )
    if fmt == "npm-access-token":
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "npm_" + _entropy_ok(
            _expand(_digest("npm", salt), alphabet, 36), alphabet, 3.0
        )
    if fmt == "gitlab-pat":
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        return "glpat-" + _entropy_ok(
            _expand(_digest("gitlab", salt), alphabet, 20), alphabet, 3.0
        )
    if fmt == "huggingface-token":
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return "hf_" + _entropy_ok(
            _expand(_digest("hf", salt), alphabet, 34), alphabet, 3.0
        )
    if fmt == "sendgrid-api-key":
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789=_-."
        return "SG." + _entropy_ok(
            _expand(_digest("sendgrid", salt), alphabet, 66), alphabet, 3.0
        )
    if fmt == "rsa-private-key":
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        blob = _expand(_digest("pem", salt), alphabet, 64 * 8)
        lines = "\n".join(blob[i : i + 64] for i in range(0, len(blob), 64))
        return (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            + lines
            + "\n-----END RSA PRIVATE KEY-----"
        )
    raise ValueError(fmt)


def embed(surface: str, plant_id: str, fmt: str, value: str) -> tuple[str, str]:
    note = (
        f"RES-0133 synthetic plant {plant_id} format={fmt}. "
        "Non-functional by construction."
    )
    if surface == "markdown-prose":
        text = (
            f"# Operator runbook\n\n{note}\n\n"
            f"During the outage the on-call pasted the {fmt} material into this "
            f"paragraph so the next shift could reproduce the client: {value}\n"
        )
        return f"{plant_id}.md", text
    if surface == "jsonl-transcript":
        rec = {
            "role": "assistant",
            "channel": "transcript",
            "plant_id": plant_id,
            "format": fmt,
            "text": f"{note} credential_field={value}",
        }
        return f"{plant_id}.jsonl", json.dumps(rec, separators=(",", ":")) + "\n"
    text = (
        f"Setup notes for {plant_id}\n\n{note}\n\n"
        f"```bash\nexport RES0133_PLANT_{plant_id}='{value}'\n```\n"
    )
    return f"{plant_id}.md", text


def decoy_file(i: int, plant_id: str) -> tuple[str, str, str, str]:
    """Return label, surface, filename, text. No format-valid provider token."""
    items = [
        (
            "aws-too-short",
            "markdown-prose",
            f"{plant_id}.md",
            "# note\nThe textbook example access id is AKIAEXAMPLE (truncated, invalid).\n",
        ),
        (
            "github-too-short",
            "jsonl-transcript",
            f"{plant_id}.jsonl",
            json.dumps({"role": "user", "text": "placeholder ghp_notatoken only"})
            + "\n",
        ),
        (
            "uuid-lookalike",
            "fenced-code-block",
            f"{plant_id}.md",
            "id sample\n\n```\nsession=550e8400-e29b-41d4-a716-446655440000\n```\n",
        ),
        (
            "placeholder-token",
            "markdown-prose",
            f"{plant_id}.md",
            "Set YOUR_API_KEY_HERE in the dashboard. No secret is present.\n",
        ),
        (
            "public-certificate-armor",
            "fenced-code-block",
            f"{plant_id}.md",
            "tls\n\n```\n-----BEGIN CERTIFICATE-----\nMIIBdummyNotAPrivateKeyAAAAAAAAAA=\n-----END CERTIFICATE-----\n```\n",
        ),
    ]
    return items[i]


def diverse_text(i: int) -> str:
    paragraphs = [
        "This license grants permission to use, copy, and distribute the software.",
        "Packaging markdown, JSON, and shell snippets does not require a registry token.",
        "Filesystem path separators on Linux are forward slashes; Windows uses backslashes.",
        "A rolling hash of archive members is a packaging concern, not a credential.",
        "The operator runbook lists restart order for the worker pool and the proxy.",
        "Unicode normalization of filenames can change digest equality across platforms.",
        "JSONL transcripts store one object per line with role and text fields only.",
        "Fenced code blocks in markdown start with three backticks and an optional language.",
        "Precision is true positives over predicted positives; recall is over actual positives.",
        "Sherman-Kent bands name confidence without implying a live network call succeeded.",
    ]
    return f"# diverse-control-{i+1:02d}\n\n{paragraphs[i]}\n"


def materialize(root: Path, *, include_controls: bool = True) -> dict:
    root = Path(root)
    plants_dir = root / "plants"
    decoys_dir = root / "decoys"
    plants_dir.mkdir(parents=True, exist_ok=True)
    decoys_dir.mkdir(parents=True, exist_ok=True)
    index: dict = {
        "seed": SEED,
        "n_plants": N_PLANTS,
        "n_decoys": N_DECOYS,
        "plants": [],
        "decoys": [],
        "near": [],
        "diverse": [],
        "_values": {},
    }

    for i in range(N_PLANTS):
        pid = f"P{i+1:02d}"
        fmt = FORMATS[i % 10]
        surface = SURFACES[i % 3]
        val = make_value(fmt, pid)
        name, text = embed(surface, pid, fmt, val)
        (plants_dir / name).write_text(text, encoding="utf-8")
        rel = f"plants/{name}"
        index["_values"][rel] = val
        index["plants"].append(
            {
                "plant_id": pid,
                "format": fmt,
                "surface": surface,
                "relpath": rel,
                "filename": name,
            }
        )

    for i in range(N_DECOYS):
        pid = f"D{i+1:02d}"
        label, surface, name, text = decoy_file(i, pid)
        (decoys_dir / name).write_text(text, encoding="utf-8")
        index["decoys"].append(
            {
                "plant_id": pid,
                "label": label,
                "surface": surface,
                "relpath": f"decoys/{name}",
                "filename": name,
                "kind": "credential-shaped-non-credential",
            }
        )

    if include_controls:
        near_dir = root / "near"
        diverse_dir = root / "diverse"
        near_dir.mkdir(parents=True, exist_ok=True)
        diverse_dir.mkdir(parents=True, exist_ok=True)
        for i in range(10):
            pid = f"N{i+1:02d}"
            fmt = FORMATS[i]
            val = make_value(fmt, pid)
            name, text = embed("markdown-prose", pid, fmt, val)
            (near_dir / name).write_text(text, encoding="utf-8")
            rel = f"near/{name}"
            index["_values"][rel] = val
            index["near"].append(
                {
                    "plant_id": pid,
                    "format": fmt,
                    "surface": "markdown-prose",
                    "relpath": rel,
                    "filename": name,
                }
            )
        for i in range(10):
            pid = f"V{i+1:02d}"
            name = f"{pid}.md"
            (diverse_dir / name).write_text(diverse_text(i), encoding="utf-8")
            index["diverse"].append(
                {
                    "plant_id": pid,
                    "relpath": f"diverse/{name}",
                    "filename": name,
                }
            )
    return index


def drop_values(index: dict) -> dict:
    return {k: v for k, v in index.items() if k != "_values"}


def secret_values(index: dict) -> list[str]:
    vals = index.get("_values") or {}
    return [v for v in vals.values() if isinstance(v, str) and len(v) >= 8]


def assert_text_has_no_secrets(text: str, index: dict, *, label: str) -> None:
    for val in secret_values(index):
        if val in text:
            raise RuntimeError(f"secret value leaked into {label}")
