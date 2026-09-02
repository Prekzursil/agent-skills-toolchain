"""Raw-source control synthesizer: reads only admitted files, never sibling conclusions."""
from __future__ import annotations

import re
from pathlib import Path

from denylist import RAW, classify, posix
from inventory import control_inventory

FACT_RE = re.compile(
    r"SYN-0009-FACT\s+id=(?P<id>[A-Z0-9-]+)\s+span=(?P<span>[A-Za-z0-9-]+)"
)
DIGEST_FRAME_RE = re.compile(r"SYN-0009-DIGEST-FRAMING:\s*(?P<span>\S+)")
LEAK_RE = re.compile(r"SYN-0009-SIBLING-LEAK:\s*(?P<span>\S+)")

RAW_ONLY_FACT_ID = "RAW-ONLY-001"
RAW_ONLY_SPAN = "detector-control-fires-on-unsummarized-transcript-span"

SIBLING_LIVE = "command-center/synthesis/SYN-0008.candidate-syntheses.json"
SIBLING_FIXTURE = (
    "command-center/p2-wave/probes/SYN-0009/fixtures/corpus/sibling/"
    "SYN-0008.candidate-syntheses.json"
)


class DeniedRead(Exception):
    def __init__(self, path: str, klass: str) -> None:
        super().__init__(f"DENIED {klass} {path}")
        self.path = path
        self.klass = klass


class GuardedReader:
    """Every open is classified first. Digest-class and sibling paths never yield bytes."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.reads: list[dict] = []
        self.denials: list[dict] = []

    def request(self, rel: str) -> str:
        path = posix(rel)
        klass = classify(path)
        if klass != RAW:
            rec = {"path": path, "class": klass, "result": "DENIED"}
            self.denials.append(rec)
            raise DeniedRead(path, klass)
        fp = self.repo / path
        if not fp.is_file():
            rec = {"path": path, "class": klass, "result": "ABSENT"}
            self.reads.append(rec)
            raise FileNotFoundError(path)
        text = fp.read_text(encoding="utf-8", errors="replace")
        self.reads.append(
            {
                "path": path,
                "class": klass,
                "result": "READ",
                "bytes": len(text.encode("utf-8")),
            }
        )
        return text


def extract_facts(text: str, source_path: str, source_class: str) -> list[dict]:
    findings: list[dict] = []
    for match in FACT_RE.finditer(text):
        findings.append(
            {
                "id": match.group("id"),
                "statement": match.group("span"),
                "source_path": source_path,
                "source_class": source_class,
                "kind": "fact",
            }
        )
    for match in DIGEST_FRAME_RE.finditer(text):
        findings.append(
            {
                "id": "DIGEST-FRAMING",
                "statement": match.group("span"),
                "source_path": source_path,
                "source_class": source_class,
                "kind": "digest-framing",
            }
        )
    for match in LEAK_RE.finditer(text):
        findings.append(
            {
                "id": "SIBLING-LEAK",
                "statement": match.group("span"),
                "source_path": source_path,
                "source_class": source_class,
                "kind": "sibling-leak",
            }
        )
    return findings


def _attempt(reader: GuardedReader, rel: str) -> dict:
    try:
        reader.request(rel)
        return {"path": posix(rel), "result": "READ", "class": classify(rel)}
    except DeniedRead as exc:
        return {"path": exc.path, "result": "DENIED", "class": exc.klass}
    except FileNotFoundError:
        return {"path": posix(rel), "result": "ABSENT", "class": classify(rel)}


def run(repo: Path, *, apply_deny: bool = True, digest_only: bool = False) -> dict:
    """Produce control findings from the fixture corpus.

    apply_deny=False is the known-broken state: digest-class files are admitted.
    digest_only=True reads only digest-class files (digest-cascade simulation).
    """
    inv = control_inventory(repo)
    reader = GuardedReader(repo)
    findings: list[dict] = []
    if digest_only:
        targets = [r for r in inv["excluded"] if r["class"] == "digest-class"]
        # Bypass the guard for the cascade simulation only: we must prove that
        # reading digests does not recover the raw-only fact.
        for row in targets:
            fp = repo / row["path"]
            text = fp.read_text(encoding="utf-8", errors="replace")
            findings.extend(extract_facts(text, row["path"], row["class"]))
            reader.reads.append(
                {"path": row["path"], "class": row["class"], "result": "READ-DIGEST-ONLY"}
            )
    else:
        rows = list(inv["admitted"])
        if not apply_deny:
            rows = rows + list(inv["excluded"])
        for row in rows:
            rel = row["path"]
            klass = classify(rel)
            if apply_deny and klass != RAW:
                continue
            if apply_deny:
                text = reader.request(rel)
                findings.extend(extract_facts(text, rel, klass))
            else:
                fp = repo / rel
                text = fp.read_text(encoding="utf-8", errors="replace")
                findings.extend(extract_facts(text, rel, klass))
                reader.reads.append(
                    {"path": rel, "class": klass, "result": "READ-UNGUARDED"}
                )

    leak_live = _attempt(reader, SIBLING_LIVE)
    leak_fix = _attempt(reader, SIBLING_FIXTURE)

    fact_hits = [f for f in findings if f["id"] == RAW_ONLY_FACT_ID]
    raw_hits = [f for f in fact_hits if f["source_class"] == RAW]
    digest_hits = [f for f in findings if f.get("kind") == "digest-framing"]
    leak_hits = [f for f in findings if f.get("kind") == "sibling-leak"]

    admitted_paths = [r["path"] for r in inv["admitted"]]
    exists_only_in_raw = bool(raw_hits) and not any(
        RAW_ONLY_SPAN in (repo / r["path"]).read_text(encoding="utf-8", errors="replace")
        for r in inv["excluded"]
        if (repo / r["path"]).is_file()
    )

    return {
        "inventory": inv,
        "findings": findings,
        "read_log": reader.reads,
        "denials": reader.denials,
        "sibling_read_attempts": [leak_live, leak_fix],
        "known_present_control": {
            "fact_id": RAW_ONLY_FACT_ID,
            "span": RAW_ONLY_SPAN,
            "present": bool(raw_hits),
            "source_path": raw_hits[0]["source_path"] if raw_hits else "",
            "exists_only_in_raw": exists_only_in_raw,
            "hit_count": len(fact_hits),
        },
        "digest_framing_present": bool(digest_hits),
        "sibling_leak_present": bool(leak_hits),
        "admitted_paths": admitted_paths,
        "apply_deny": apply_deny,
        "digest_only": digest_only,
    }
