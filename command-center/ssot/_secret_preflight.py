"""Pre-commit secret preflight for the SSOT artifacts.

Scans every file this lane is about to commit for credential-shaped material BEFORE it
enters git history. Rationale: inbound-refs.json was produced by scanning ~/.claude.json,
~/.mcp.json and ~/.claude/settings.local.json -- all credential-bearing. The inventory
CLAIMS no credential line was printed; a claim is not a measurement.

Classifies by STRUCTURE (prefix shape, length, entropy). Never prints a candidate value:
only its file, a redacted shape, and its entropy. Fails CLOSED on any HIGH finding.

Detector control is built in: --control injects known-secret-shaped strings into the
scanned corpus and asserts each detector FIRES. A detector that cannot find a planted
secret proves nothing about the real files.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]

# Prefix families that are unambiguously credential material on this estate.
# The prefix itself is zero-entropy and safe to name (AGENTS.md 9).
PREFIX_PATTERNS: list[tuple[str, str]] = [
    ("anthropic-key", r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("openai-key", r"sk-(?:proj-)?[A-Za-z0-9_\-]{32,}"),
    ("github-pat", r"gh[pousr]_[A-Za-z0-9]{30,}"),
    ("github-fine-grained", r"github_pat_[A-Za-z0-9_]{40,}"),
    ("hf-token", r"hf_[A-Za-z0-9]{30,}"),
    ("slack-token", r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    ("aws-akid", r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    ("google-key", r"AIza[0-9A-Za-z_\-]{35}"),
    ("databricks-pat", r"dapi[0-9a-f]{32}"),
    ("private-key-block", r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    ("jwt", r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ("bearer-inline", r"[Bb]earer\s+[A-Za-z0-9_\-\.]{25,}"),
]

# Keys whose VALUE is credential material regardless of shape.
SENSITIVE_KEY = re.compile(
    r"(?i)\"?(?:api[_-]?key|apikey|secret|token|password|passwd|credential|"
    r"access[_-]?key|private[_-]?key|session[_-]?key|cookie|auth)\"?\s*[:=]\s*"
    r"\"([^\"]{16,})\""
)


def _plants() -> dict[str, str]:
    """Assemble synthetic credential-SHAPED strings at runtime.

    Deliberately NOT written as literals: a literal here would be indexed by every
    secret scanner (and by this repo's own gate) forever, manufacturing a permanent
    false positive in the very file that exists to prevent false negatives. Assembling
    from fragments keeps the control genuine -- the scanner still sees a full
    credential-shaped string in `scan_text` -- while the source file holds none.
    """
    az = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    lo = az.lower()
    dg = "0123456789"
    b64 = lo + az + dg
    return {
        "anthropic-key": "sk-" + "ant-" + (b64 * 2)[:28],
        "github-pat": "gh" + "p_" + (lo + az)[:38],
        "hf-token": "h" + "f_" + (lo + dg)[:36],
        "aws-akid": "AK" + "IA" + (az + dg)[:16],
        "jwt": "ey" + "J" + b64[:14] + "." + "ey" + "J" + b64[:16] + "." + b64[:20],
    }


def _is_credential_shaped(val: str) -> bool:
    """Structural gate on the VALUE, after a sensitive KEY NAME matched.

    Measured false-positive that forced this function into existence: in
    refs-verified.json the key `"token"` means a *search needle*, and its value is
    `source/agent-skills-toolchain`. Entropy 3.88 clears any reasonable threshold, so
    entropy alone produced 12 HIGH findings on a file holding zero credentials -- a
    use-vs-mention failure at the field level, inside the detector itself. The tell was
    the output: 12 hits, one file, all beginning `sour`, all entropy 3.88-3.90. A
    suspiciously uniform cluster is a detector failure, not a finding.

    A real credential is an opaque single token: no path separators, no whitespace, and
    not a run of dictionary-ish words joined by - or _.
    """
    if any(c in val for c in "/\\ \t\n"):
        return False
    if val.startswith(("C:", "c:", "/", "~", "http://", "https://", "$", ".", "%")):
        return False
    # Dictionary-ish compound (my-service-name, agent_skills_toolchain): every segment
    # is alphabetic and short. Credentials do not decompose this way.
    segments = re.split(r"[-_.]", val)
    if len(segments) >= 2 and all(s.isalpha() and len(s) <= 14 for s in segments if s):
        return False
    # Require an actual character-class mix: letters AND digits, or non-alnum padding.
    has_alpha = any(c.isalpha() for c in val)
    has_digit = any(c.isdigit() for c in val)
    has_pad = any(c in "+=/" for c in val)
    return has_alpha and (has_digit or has_pad)


def shannon(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def redact(value: str) -> str:
    """Never return the secret. Prefix (zero-entropy) + length + entropy only."""
    head = value[:4] if len(value) > 12 else ""
    return f"{head}...[{len(value)} chars]"


def scan_text(text: str, origin: str) -> list[dict]:
    findings: list[dict] = []
    for name, pat in PREFIX_PATTERNS:
        for m in re.finditer(pat, text):
            val = m.group(0)
            findings.append(
                {
                    "file": origin,
                    "detector": name,
                    "severity": "HIGH",
                    "shape": redact(val),
                    "entropy": round(shannon(val), 2),
                }
            )
    for m in SENSITIVE_KEY.finditer(text):
        val = m.group(1)
        ent = shannon(val)
        # A path or a plain word has low entropy; a real credential does not.
        if ent < 3.6:
            continue
        if not _is_credential_shaped(val):
            continue
        findings.append(
            {
                "file": origin,
                "detector": "sensitive-key-value",
                "severity": "HIGH",
                "shape": redact(val),
                "entropy": round(ent, 2),
            }
        )
    return findings


def collect(paths: list[pathlib.Path]) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for p in paths:
        if p.is_dir():
            out.extend(q for q in sorted(p.rglob("*")) if q.is_file())
        elif p.is_file():
            out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+")
    ap.add_argument(
        "--control", action="store_true", help="run the both-states detector control"
    )
    args = ap.parse_args()

    files = collect([pathlib.Path(t).resolve() for t in args.targets])

    if args.control:
        # BOTH-STATES CONTROL: plant a known secret of each family and require a FIRE.
        print("=== DETECTOR CONTROL (known-BROKEN state: secrets planted) ===")
        ok = True
        for name, planted in _plants().items():
            hits = scan_text(f'{{"x": "{planted}"}}', "<control>")
            fired = [h for h in hits if h["detector"] == name]
            status = "FIRED" if fired else "SILENT <-- DETECTOR BROKEN"
            if not fired:
                ok = False
            print(f"  {name:24s} {status}")
        neg = scan_text(
            '{"path": "C:/Users/Prekzursil/source/agent-skills-toolchain"}', "<control>"
        )
        print(f"  {'clean-path (must be 0)':24s} {len(neg)} hits")
        if neg:
            ok = False

        # The measured false positive that _is_credential_shaped exists to kill.
        # Must be SILENT. This is the known-CLEAN state for the sensitive-key detector.
        fp = scan_text('{"token": "source/agent-skills-toolchain"}', "<control>")
        print(f"  {'needle-path FP (must be 0)':24s} {len(fp)} hits")
        if fp:
            ok = False
        fp2 = scan_text('{"token": "source\\\\agent-skills-toolchain"}', "<control>")
        print(f"  {'needle-path win FP (must=0)':24s} {len(fp2)} hits")
        if fp2:
            ok = False

        # ...but a sensitive KEY carrying a genuinely opaque value must STILL fire,
        # otherwise the false-positive fix has silently disabled the detector.
        b64 = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEF"
        live = scan_text('{"api_key": "' + b64 + '"}', "<control>")
        fired = [h for h in live if h["detector"] == "sensitive-key-value"]
        print(
            f"  {'opaque value (must fire)':24s} {'FIRED' if fired else 'SILENT <-- OVER-FILTERED'}"
        )
        if not fired:
            ok = False
        print(
            f"CONTROL: {'PASS' if ok else 'FAIL'} -- detectors {'can' if ok else 'CANNOT'} see a planted secret\n"
        )
        if not ok:
            print("FAILED: preflight-control-broken")
            return 2

    findings: list[dict] = []
    scanned = 0
    total_bytes = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace", newline="")
        except OSError as exc:
            print(f"  SKIP {f}: {exc}")
            continue
        scanned += 1
        total_bytes += len(text)
        findings.extend(scan_text(text, str(f.relative_to(REPO)).replace("\\", "/")))

    print(f"=== REAL SCAN: {scanned} files, {total_bytes:,} chars ===")
    if not findings:
        print("0 credential-shaped findings.")
        print(f"SUCCESS:secret-preflight scanned={scanned} findings=0")
        return 0

    print(f"{len(findings)} credential-shaped finding(s) -- values NEVER printed:")
    for h in findings:
        print(
            f"  [{h['severity']}] {h['file']} :: {h['detector']} shape={h['shape']} H={h['entropy']}"
        )
    print(json.dumps({"findings": len(findings)}))
    print("FAILED:secret-preflight credential-shaped material present -- DO NOT COMMIT")
    return 1


if __name__ == "__main__":
    sys.exit(main())
