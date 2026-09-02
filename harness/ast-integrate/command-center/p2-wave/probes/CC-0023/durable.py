"""Durable OWNER-QUESTION-PACKET.md and OWNER-DECISIONS.md records."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

BEGIN = "<!-- BEGIN CC-0023 -->"
END = "<!-- END CC-0023 -->"
REC_START = "<!--CC-0023:START:{qid}-->"
REC_END = "<!--CC-0023:END:{qid}-->"
FIELD_RE = re.compile(r"^([a-z_]+):\s?(.*)$")


def render_packet(questions: list[dict[str, Any]]) -> str:
    lines = [
        "# Owner question packet (CC-0023)",
        "",
        "Presentation rule: one foundation-level question at a time. "
        "Do not answer by inference. An inferred, majority-of-agents, or "
        "most-likely-meaning answer is not evidence.",
        "",
        f"Questions in this packet: {len(questions)}.",
        "",
    ]
    for i, q in enumerate(questions, 1):
        lines.extend(
            [
                f"## {q['id']} ({i} of {len(questions)})",
                "",
                f"**Question:** {q['question']}",
                "",
                f"**Recommendation:** {q['recommendation']}",
                "",
                f"**Strongest tradeoff:** {q['strongest_tradeoff']}",
                "",
                f"**Default if unanswered:** {q['default_if_unanswered']}",
                "",
                "**Settling experiment cost:** One owner turn naming the namespace; "
                "no tree rewrite until the answer is recorded here.",
                "",
                f"**Token:** `{q['token']}`",
                "",
                f"**References covered:** {q['reference_count']}",
                "",
                f"**Impact if unanswered:** {q['impact_statement']}",
                "",
            ]
        )
    inner = "\n".join(lines)
    return f"{BEGIN}\n{inner}\n{END}\n"


def render_decisions(
    questions: list[dict[str, Any]], *, recorded_at: str
) -> str:
    blocks = [
        "# Owner decisions (CC-0023)",
        "",
        "Ask once per decision. Unanswered questions take the stated default "
        "(DEFERRED) and are not re-asked.",
        "",
    ]
    for q in questions:
        qid = q["id"]
        refs = ",".join(q["reference_ids"])
        blocks.extend(
            [
                REC_START.format(qid=qid),
                f"question_id: {qid}",
                f"token: {q['token']}",
                f"question: {q['question']}",
                f"recommendation: {q['recommendation']}",
                f"strongest_tradeoff: {q['strongest_tradeoff']}",
                f"default_if_unanswered: {q['default_if_unanswered']}",
                "terminal_state: DEFERRED",
                "owner_answer:",
                f"recorded_at: {recorded_at}",
                "default_applied: true",
                f"impact: {q['impact_statement']}",
                f"reference_count: {q['reference_count']}",
                f"reference_ids: {refs}",
                REC_END.format(qid=qid),
                "",
            ]
        )
    inner = "\n".join(blocks)
    return f"{BEGIN}\n{inner}\n{END}\n"


def upsert_section(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        if BEGIN in existing and END in existing:
            pre = existing.split(BEGIN, 1)[0]
            post = existing.split(END, 1)[1]
            text = pre + body
            if not text.endswith("\n"):
                text += "\n"
            if post and not post.startswith("\n"):
                text += post
            else:
                text += post
            path.write_text(text, encoding="utf-8", newline="\n")
            return
        merged = existing.rstrip() + "\n\n" + body
        path.write_text(merged, encoding="utf-8", newline="\n")
        return
    path.write_text(body, encoding="utf-8", newline="\n")


def parse_decisions(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    chunks = re.split(r"<!--CC-0023:START:([^>]+)-->", text)
    # split yields [pre, qid1, body1, qid2, body2, ...]
    i = 1
    while i + 1 < len(chunks):
        qid = chunks[i].strip()
        body = chunks[i + 1].split(REC_END.format(qid=qid), 1)[0]
        rec: dict[str, str] = {"question_id": qid}
        for line in body.splitlines():
            m = FIELD_RE.match(line)
            if m:
                rec[m.group(1)] = m.group(2)
        records.append(rec)
        i += 2
    return records
