#!/usr/bin/env python3
"""phase1_provider_truth.py - T-4 permanent regression detector (cs-audit phase1).

Checks config-truth consistency between cyberstrike.json (machine truth) and
config.md (prose SSOT):
  (a) prose presenting OpenAI / Astra / Daybreak as a cockpit brain / cyber
      path while `openai` is in disabled_providers OR the active model
      resolves to a non-openai provider id in the json registry;
  (b) phantom registered-model claims: model names the prose claims are
      "registered" that are absent from cyberstrike.json's provider registry.

Exit codes: 0 = clean, 1 = findings emitted, 2 = detector could not run
(missing/unparseable inputs). Never prints credential values: only structural
fields (disabled_providers list, provider ids, model registry keys/ids).
"""

import argparse
import json
import re
import sys
from pathlib import Path

RE_FAMILY = re.compile(r"\b(astra|daybreak|openai)\b", re.I)
RE_ROLE_ROW = re.compile(r"\|\s*OpenAI cyber path\s*\|", re.I)
RE_ROLE_ASSERT = re.compile(
    r"\b(astra|daybreak|openai)\b[^.|]{0,80}\b(is|are|remains?)\s+(the\s+)?"
    r"(live\s+|primary\s+|default\s+|best\s+|sole\s+)?(cockpit\s+)?"
    r"(brain|cyber path|reasoning core|provider for|workhorse)",
    re.I,
)
RE_HONESTY_A = re.compile(
    r"(no OpenAI brain|not a cockpit|external \(ChatGPT|web lanes|shims?\b|"
    r"NVIDIA-hosted|Kimi-K3 fallback)",
    re.I,
)
RE_REG_CLAIM = re.compile(
    r"\b(remain|remains|is|are|stay|stays)\s+registered\b|\bregistered for\b", re.I
)
RE_BACKTICK = re.compile(r"`([^`\n]+)`")
RE_COLOR_VARIANT = re.compile(r"\b(daybreak|astra)[^,.;|]{0,12}?(blue|red)\b", re.I)
RE_MODELISH = re.compile(
    r"\b(gpt-[\d][\w.-]*|glm-[\d][\w.-]*|kimi[\w.-]*|nemotron[\w.-]*|"
    r"abliterated[\w.-]*|heretic[\w.-]*|qwen[\w.-]*)\b",
    re.I,
)
RE_SEGMENT = re.compile(r"(?<=[.;|])\s+")
RE_FILE_EXT = re.compile(r"\.(json|md|py|exe|db|txt|ps1|yml|yaml|toml|log)\b", re.I)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def registry_index(cfg: dict):
    """Return (known_norms, disabled, entries) for lookups."""
    providers = cfg.get("provider", {}) or {}
    disabled = set(cfg.get("disabled_providers", []) or [])
    entries = []
    for pid, pconf in providers.items():
        models = (pconf or {}).get("models", {}) or {}
        for mkey, mconf in models.items():
            mconf = mconf or {}
            alias = mconf.get("id") if isinstance(mconf, dict) else None
            for ident in {mkey, alias}:
                if not ident:
                    continue
                entries.append((pid, ident))
    known = {norm(ident) for _, ident in entries}
    known |= {norm(f"{pid}/{ident}") for pid, ident in entries}
    return known, disabled, entries


def resolve_model(cfg: dict, model_ref):
    """Resolve a '<provider>/<model>' reference to (provider_id, model_id)."""
    if not isinstance(model_ref, str) or "/" not in model_ref:
        return None
    pid, mkey = model_ref.split("/", 1)
    providers = cfg.get("provider", {}) or {}
    if pid in providers:
        mconf = (providers.get(pid) or {}).get("models", {}) or {}
        if mkey in mconf and isinstance(mconf[mkey], dict) and mconf[mkey].get("id"):
            return pid, mconf[mkey].get("id")
        return pid, mkey
    return None


def claim_matches(claim: str, known: set) -> bool:
    c = norm(claim)
    if len(c) < 5:
        return True  # too generic to police (e.g. 'glm', 'kimi' prose)
    for k in known:
        if c == k or k.startswith(c) or c.startswith(k) or k.endswith(c):
            return True
        if len(c) >= 7 and (c in k or k in c):
            return True
    return False


def check_docs(docs_text, cfg, known, disabled):
    findings = []
    openai_disabled = "openai" in disabled
    agent_cfg = (cfg.get("agent", {}) or {}).get(cfg.get("default_agent", ""), {}) or {}
    active = cfg.get("model") or agent_cfg.get("model")
    cond_parts = []
    if openai_disabled:
        cond_parts.append("openai in disabled_providers")
    res = resolve_model(cfg, active) if active else None
    if res and res[0] != "openai":
        cond_parts.append(
            "active model '" + str(active) + "' resolves to provider '" + res[0] + "'"
        )
    condition = " OR ".join(cond_parts) or "no drift condition present"

    for lineno, raw in enumerate(docs_text.splitlines(), 1):
        line = raw.strip()
        if RE_FAMILY.search(line) and (
            RE_ROLE_ROW.search(line) or RE_ROLE_ASSERT.search(line)
        ):
            if not RE_HONESTY_A.search(line):
                if openai_disabled or (res and res[0] != "openai"):
                    named = sorted(
                        set(m.group(0).lower() for m in RE_FAMILY.finditer(line))
                    )
                    findings.append(
                        {
                            "code": "A1",
                            "line": lineno,
                            "message": "prose presents OpenAI/Astra/Daybreak as a cockpit "
                            "brain/cyber-path without honesty marker (shim/external/"
                            "not-a-cockpit); drift condition: "
                            + condition
                            + "; family tokens: "
                            + ", ".join(named),
                        }
                    )
        for segment in RE_SEGMENT.split(line):
            if not RE_REG_CLAIM.search(segment):
                continue
            claims = [m.group(1) for m in RE_BACKTICK.finditer(segment)]
            claims += [m.group(0) for m in RE_COLOR_VARIANT.finditer(segment)]
            claims += [m.group(0) for m in RE_MODELISH.finditer(segment)]
            for claim in claims:
                if RE_FILE_EXT.search(claim):
                    continue
                if "{" in claim or "}" in claim or "shim" in claim.lower():
                    continue  # credential refs / alias labels, not model ids
                if not claim_matches(claim, known):
                    findings.append(
                        {
                            "code": "B1",
                            "line": lineno,
                            "message": "phantom registered-model claim: '"
                            + claim
                            + "' claimed registered in prose but absent from "
                            "cyberstrike.json registry",
                        }
                    )
    return findings


def main():
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="T-4 provider-truth detector")
    ap.add_argument("--config", default=str(here / "cyberstrike.json"))
    ap.add_argument("--docs", default=str(here / "config.md"))
    ap.add_argument("--json", action="store_true", help="emit JSON findings")
    args = ap.parse_args()
    cfg_path, docs_path = Path(args.config), Path(args.docs)
    try:
        cfg = load_json(cfg_path)
        docs_text = docs_path.read_text(encoding="utf-8-sig")
    except Exception as exc:
        print("DETECTOR-ERROR cannot read inputs: " + str(exc), file=sys.stderr)
        return 2
    known, disabled, entries = registry_index(cfg)
    if not entries:
        print("DETECTOR-ERROR empty provider registry - wrong config?", file=sys.stderr)
        return 2
    findings = check_docs(docs_text, cfg, known, disabled)
    active = cfg.get("model")
    res = resolve_model(cfg, active) if active else None
    if res and res[0] in disabled:
        findings.append(
            {
                "code": "C1",
                "line": 0,
                "message": "active model '"
                + str(active)
                + "' resolves to disabled provider '"
                + res[0]
                + "'",
            }
        )
    if args.json:
        print(
            json.dumps(
                {
                    "config": str(cfg_path),
                    "docs": str(docs_path),
                    "findings": findings,
                    "count": len(findings),
                    "openai_disabled": "openai" in disabled,
                },
                indent=1,
            )
        )
    else:
        for f in findings:
            print(
                "FINDING "
                + f["code"]
                + " "
                + docs_path.name
                + ":"
                + str(f["line"])
                + " "
                + f["message"]
            )
        print("phase1_provider_truth: " + str(len(findings)) + " finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
