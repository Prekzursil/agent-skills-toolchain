#!/usr/bin/env python3
"""AUD-0062 Probe 1: tokenize each always-on injected file and sum (tiktoken cl100k)."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe1-tokenize-sum.json"
RAW = PROBE / "probe1-tokenize.raw.txt"


def get_encoder():
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base"), "tiktoken-cl100k_base"
    except Exception:
        return None, "fallback-whitespace"


def count_tokens(text: str, enc) -> int:
    if enc is not None:
        return len(enc.encode(text))
    return len(re.findall(r"\S+", text))


def char4_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def collect_injection_set(enc) -> list[dict]:
    """Always-on injection set for THIS checkout (Cursor cloud + repo rules)."""
    candidates = [
        ("CLAUDE.md", "repo-root"),
        ("AGENTS.md", "repo-root"),
        (".agents/skills/llm-security/AGENTS.md", "always-applied-workspace-rule"),
        (".agents/skills/humanizer/AGENTS.md", "always-applied-workspace-rule"),
        (".agents/skills/code-security/AGENTS.md", "always-applied-workspace-rule"),
    ]
    items = []
    for rel, kind in candidates:
        p = REPO / rel
        if not p.is_file():
            items.append(
                {
                    "path": rel,
                    "kind": kind,
                    "exists": False,
                    "bytes": 0,
                    "tokens_model": 0,
                    "tokens_char4": 0,
                }
            )
            continue
        data = p.read_bytes()
        text = data.decode("utf-8", errors="replace")
        items.append(
            {
                "path": rel,
                "kind": kind,
                "exists": True,
                "bytes": len(data),
                "tokens_model": count_tokens(text, enc),
                "tokens_char4": char4_tokens(text),
            }
        )

    skills_root = REPO / ".agents" / "skills"
    skill_meta_tokens = 0
    skill_meta_count = 0
    if skills_root.is_dir():
        for skill_md in sorted(skills_root.glob("*/SKILL.md"))[:80]:
            text = skill_md.read_text(encoding="utf-8", errors="replace")
            fm = re.match(r"^---\n(.*?)\n---", text, re.S)
            if not fm:
                continue
            block = fm.group(1)
            m = re.search(r"(?m)^description:\s*(.+)$", block)
            if not m:
                m2 = re.search(r"(?ms)^description:\s*[|>].*?(?=\n\w|\Z)", block)
                desc = m2.group(0) if m2 else block
            else:
                desc = m.group(1)
            tok = count_tokens(desc, enc)
            skill_meta_tokens += tok
            skill_meta_count += 1
            if skill_meta_count <= 5:
                items.append(
                    {
                        "path": str(skill_md.relative_to(REPO)),
                        "kind": "skill-description-metadata",
                        "exists": True,
                        "bytes": len(desc.encode()),
                        "tokens_model": tok,
                        "tokens_char4": char4_tokens(desc),
                    }
                )
    items.append(
        {
            "path": ".agents/skills/*/SKILL.md#description (aggregate)",
            "kind": "skill-description-metadata-aggregate",
            "exists": True,
            "bytes": skill_meta_tokens * 4,
            "tokens_model": skill_meta_tokens,
            "tokens_char4": skill_meta_tokens,
            "skill_meta_count": skill_meta_count,
        }
    )
    return items


def main() -> int:
    enc, enc_name = get_encoder()
    items = collect_injection_set(enc)
    present = [i for i in items if i.get("exists")]
    total_model = sum(i["tokens_model"] for i in present)
    total_c4 = sum(i["tokens_char4"] for i in present)
    full = [
        i
        for i in present
        if i["kind"]
        not in ("skill-description-metadata", "skill-description-metadata-aggregate")
    ]
    dominant = max(full, key=lambda x: x["tokens_model"]) if full else None

    result = {
        "ok": True,
        "unit": "AUD-0062",
        "probe": 1,
        "tokenizer": enc_name,
        "items": items,
        "item_count": len(present),
        "total_tokens_model": total_model,
        "total_tokens_char4": total_c4,
        "full_file_tokens_model": sum(i["tokens_model"] for i in full),
        "full_file_tokens_char4": sum(i["tokens_char4"] for i in full),
        "dominant_item": dominant,
        # keep aliases for older packers
        "total_tokens_whitespace": total_model,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0062 NAMED PROBE 1: tokenize always-on injection set and sum",
        "unit=AUD-0062",
        f"tokenizer={enc_name}",
        f"item_count={len(present)}",
        f"total_tokens_model={total_model}",
        f"total_tokens_char4={total_c4}",
        f"full_file_tokens_model={result['full_file_tokens_model']}",
    ]
    for i in items:
        lines.append(
            f"ITEM\t{i['path']}\texists={i['exists']}\tbytes={i['bytes']}\t"
            f"tok_model={i['tokens_model']}\ttok_c4={i['tokens_char4']}\tkind={i['kind']}"
        )
    if dominant:
        lines.append(
            f"DOMINANT\t{dominant['path']}\ttok_model={dominant['tokens_model']}"
        )
    lines.append("SUCCESS:AUD-0062-probe1")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
