#!/usr/bin/env python3
"""Isolated synthesizer worker for SYN-0008.

Reads ONLY paths listed in the prompt-file allow_read set. A sibling-output
request that is not on that set is DENIED and recorded. The worker never
sees sibling sandboxes; independence is the dispatcher's copy-in allowlist,
not a promise in this prompt.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def guarded_read(path: Path, allow: set[Path]) -> tuple[str | None, dict[str, Any] | None]:
    resolved = path.resolve()
    if resolved not in allow:
        return None, {
            "status": "DENIED",
            "reason": "not-on-partition-allowlist",
            "path": str(resolved),
        }
    if not resolved.is_file():
        return None, {
            "status": "DENIED",
            "reason": "allowlisted-path-missing",
            "path": str(resolved),
        }
    return resolved.read_text(encoding="utf-8"), None


def extract_findings(doc: dict[str, Any], source: str, lens: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    token = str(doc.get("exclusive_token") or "")
    cls = str(doc.get("evidence_class") or "")
    if token:
        findings.append(
            {
                "kind": "token",
                "evidence_class": cls,
                "source": source,
                "token": token,
                "claim": f"observed exclusive token {token} in {cls}",
            }
        )
    for node in doc.get("nodes") or []:
        if isinstance(node, dict) and node.get("claim"):
            findings.append(
                {
                    "kind": "cause",
                    "evidence_class": cls,
                    "source": source,
                    "id": node.get("id"),
                    "claim": node["claim"],
                    "lens": lens,
                }
            )
    for item in doc.get("decisions") or []:
        if isinstance(item, dict) and item.get("decision"):
            findings.append(
                {
                    "kind": "decision",
                    "evidence_class": cls,
                    "source": source,
                    "id": item.get("id"),
                    "claim": item["decision"],
                    "owner": item.get("owner"),
                    "lens": lens,
                }
            )
    for key in ("mutations", "citations", "reproductions", "receipts"):
        for item in doc.get(key) or []:
            if isinstance(item, dict) and item.get("claim"):
                findings.append(
                    {
                        "kind": key.rstrip("s"),
                        "evidence_class": cls,
                        "source": source,
                        "id": item.get("id"),
                        "claim": item["claim"],
                        "lens": lens,
                    }
                )
    return findings


def synthesize(prompt: dict[str, Any]) -> dict[str, Any]:
    allow = {Path(p).resolve() for p in (prompt.get("allow_read") or [])}
    lens = str(prompt.get("lens") or "generic")
    files_read: list[str] = []
    findings: list[dict[str, Any]] = []
    tokens: list[str] = []
    denials: list[dict[str, Any]] = []

    sibling = prompt.get("request_sibling_output")
    sibling_request: dict[str, Any] | None = None
    if sibling:
        _text, denial = guarded_read(Path(str(sibling)), allow)
        sibling_request = denial or {
            "status": "LEAKED",
            "reason": "sibling-output-was-readable",
            "path": str(Path(str(sibling)).resolve()),
        }
        if denial:
            denials.append(denial)

    for raw in prompt.get("allow_read") or []:
        text, denial = guarded_read(Path(str(raw)), allow)
        if denial:
            denials.append(denial)
            continue
        assert text is not None
        files_read.append(str(Path(str(raw)).resolve()))
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            findings.append(
                {
                    "kind": "unparsed",
                    "source": str(raw),
                    "claim": "evidence file did not parse as JSON",
                }
            )
            continue
        if not isinstance(doc, dict):
            continue
        tok = str(doc.get("exclusive_token") or "")
        if tok:
            tokens.append(tok)
        findings.extend(extract_findings(doc, str(raw), lens))

    return {
        "agent_id": prompt.get("agent_id"),
        "vendor": prompt.get("vendor"),
        "model": prompt.get("model"),
        "lens": lens,
        "files_read": files_read,
        "tokens_observed": sorted(set(tokens)),
        "findings": findings,
        "sibling_request": sibling_request,
        "denials": denials,
        "prompt_file": prompt.get("prompt_file"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--mode", default="complete", choices=("complete", "severed"))
    args = ap.parse_args()
    prompt_path = Path(args.prompt_file)
    out_path = Path(args.output)
    if not prompt_path.is_file():
        print(f"FAILED:synthesizer prompt missing {prompt_path}", file=sys.stderr)
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.mode == "severed":
        body = {
            "job_id": "job-planted-severed-syn0008",
            "status": "queued",
            "progress": "started",
            "background": True,
        }
        out_path.write_text(
            json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("SEVERED:synthesizer wrote job-receipt only")
        return 0
    prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
    if not isinstance(prompt, dict):
        print("FAILED:synthesizer prompt is not an object", file=sys.stderr)
        return 1
    prompt["prompt_file"] = str(prompt_path)
    body = synthesize(prompt)
    out_path.write_text(
        json.dumps(body, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"SUCCESS:synthesizer wrote {out_path} findings={len(body['findings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
