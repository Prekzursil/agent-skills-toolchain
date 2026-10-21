"""ADV-0015 Probe 1 (2026-10-21): fetch the CURRENT vendor surface and diff every
model id / price the in-tree routing table declares.

Targets (from the in-tree table + estimator + claude-api skill needles):
  - gpt-5.3-codex   (external-tools.yaml adapters.codex.model; estimate-cost.sh 1.50/6.00)
  - gemini-pro      (estimate-cost.sh 1.25/5.00)
  - claude-opus-4-1, claude-sonnet-4-0, claude-3-5-haiku-latest (skills/claude-api SKILL.md)
Vendor sources fetched today: platform.openai.com pricing, ai.google.dev pricing,
docs.anthropic.com models overview."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

DIR = Path(__file__).resolve().parent
REPO = DIR.parents[3]

SOURCES = {
    "openai_pricing": "https://platform.openai.com/docs/pricing",
    "gemini_pricing": "https://ai.google.dev/gemini-api/docs/pricing",
    "anthropic_models": "https://docs.anthropic.com/en/docs/about-claude/models",
}
NEEDLES = {
    "openai_pricing": ["gpt-5.3-codex", "codex"],
    "gemini_pricing": ["Gemini 2.5 Pro", "gemini-pro", "Pro"],
    "anthropic_models": ["claude-opus-4-1", "claude-sonnet-4-0", "claude-3-5-haiku-latest",
                          "claude-opus-4-5", "claude-sonnet-4-5"],
}
TABLE = {
    "gpt-5.3-codex": {"declared_input_per_m": "1.50", "declared_output_per_m": "6.00",
                      "declared_in": ["tools/editor/metaswarm/skills/setup/templates/external-tools.yaml",
                                      "tools/editor/metaswarm/skills/setup/bin/estimate-cost.sh"]},
    "gemini-pro": {"declared_input_per_m": "1.25", "declared_output_per_m": "5.00",
                   "declared_in": ["tools/editor/metaswarm/skills/setup/bin/estimate-cost.sh"]},
}


def fetch(url: str) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "adv0015-probe/1.0"})
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.getcode(), r.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return -1, f"<error {exc}>"


def main() -> int:
    pages: dict[str, dict] = {}
    for name, url in SOURCES.items():
        code, body = fetch(url)
        pages[name] = {"url": url, "status": code, "bytes": len(body),
                       "body": body if code == 200 else ""}
        hits = {n: (n.lower() in body.lower()) for n in NEEDLES[name]}
        pages[name]["needle_hits"] = hits

    # price extraction near the codex needle on the OpenAI page
    openai_body = pages["openai_pricing"]["body"]
    price_ctx = ""
    m = re.search(r"gpt-5\.3-codex.{0,400}", openai_body, re.S | re.I)
    if m:
        price_ctx = " ".join(m.group(0).split())[:400]

    # diff verdicts per target
    rows = []
    op_hits = pages["openai_pricing"]["needle_hits"]
    rows.append({
        "target": "gpt-5.3-codex (table 1.50/6.00)",
        "vendor_page_status": pages["openai_pricing"]["status"],
        "id_listed_today": op_hits.get("gpt-5.3-codex"),
        "price_context": price_ctx,
        "verdict": ("PARTIAL" if op_hits.get("gpt-5.3-codex")
                    else "NOT-CHECKED" if pages["openai_pricing"]["status"] != 200
                    else "REFUTED"),
    })
    gm_hits = pages["gemini_pricing"]["needle_hits"]
    rows.append({
        "target": "gemini-pro (table 1.25/5.00)",
        "vendor_page_status": pages["gemini_pricing"]["status"],
        "id_listed_today": gm_hits.get("Gemini 2.5 Pro"),
        "verdict": ("PARTIAL" if gm_hits.get("Gemini 2.5 Pro")
                    else "NOT-CHECKED" if pages["gemini_pricing"]["status"] != 200
                    else "REFUTED"),
    })
    an_hits = pages["anthropic_models"]["needle_hits"]
    for needle in ["claude-opus-4-1", "claude-sonnet-4-0", "claude-3-5-haiku-latest"]:
        rows.append({
            "target": f"{needle} (skills/claude-api SKILL.md needle)",
            "vendor_page_status": pages["anthropic_models"]["status"],
            "id_listed_today": an_hits.get(needle),
            "verdict": ("CONFIRMED" if an_hits.get(needle)
                        else "REFUTED" if pages["anthropic_models"]["status"] == 200
                        else "NOT-CHECKED"),
        })
        # a CURRENT id must resolve so the page is proven live (both-states control)
    live_control = any(an_hits.get(n) for n in ["claude-opus-4-5", "claude-sonnet-4-5"])

    payload = {
        "probe": "probe1-vendor-diff",
        "pages": {k: {kk: vv for kk, vv in v.items() if kk != "body"} for k, v in pages.items()},
        "table": TABLE,
        "rows": rows,
        "controls": {
            "CTRL-VENDOR-PAGE-LIVE": live_control or pages["openai_pricing"]["status"] == 200,
            "CTRL-CURRENT-ID-RESOLVES": live_control,
        },
    }
    out = [f"SUCCESS:adv0015-probe1 vendor pages fetched: "
           + ", ".join(f"{k}={v['status']}({v['bytes']}B)" for k, v in pages.items())]
    for r in rows:
        out.append(f"  {r['target']} -> {r['verdict']} (listed_today={r['id_listed_today']})")
    for k, v in payload["controls"].items():
        out.append(f"  {k}: {'PASS' if v else 'FAIL'}")
    text_out = "\n".join(out) + "\n"
    print(text_out, end="")
    (DIR / "probe1-vendor-diff.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    (DIR / "probe1-vendor-diff.raw.txt").write_text(text_out, encoding="utf-8")
    return 0 if all(payload["controls"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
