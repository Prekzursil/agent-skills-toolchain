#!/usr/bin/env python3
"""Stop hook: surface gaps that are REAL and CHECKABLE. Silent otherwise.

Owner instruction 2026-09-24: "dont leave gaps at all, they are always addressed
not left or abandoned" -- with the constraint "make it so theres no downsides
while also not being noise and doesnt bleed".

That constraint drives every design choice here:

NOT NOISE
  - STATE-based, never TEXT-based. An earlier text-matching gate fired on the
    string "TODO" inside the FILENAME cv/TODO-CONFIRM.md -- a false positive on a
    file whose entire purpose is tracking those items. This hook never reads the
    assistant's message. It reads disk state only.
  - SILENT WHEN CLEAN. No output, no "all good" chatter. A gate that speaks every
    turn gets tuned out, and a gate that is tuned out is worse than no gate.
  - Each finding names a specific row or SHA. "Something might be unfinished" is
    noise; "L-07 is 3 days past review-by" is actionable.

NO DOWNSIDES
  - NEVER BLOCKS. Exit 0 always, additionalContext only. Per AGENTS.md section 6,
    exit 2 is reserved for irreversible/dangerous actions. An unfinished item is
    neither. Blocking on a gap would strand the user mid-task -- a real downside.
  - FAILS OPEN. Any exception, missing file, or slow git call exits 0 silently.
    A broken gate must never wedge a session.
  - BUDGETED. Hard wall-clock cap; over budget it emits nothing rather than
    delaying the turn.

DOESN'T BLEED
  - Checks ONLY the open-loops register and local git state. It does not inspect
    the conversation, other repos, the CV, or any unrelated tree.
  - Does not duplicate what autopush and push-guard already cover: it reports
    unpushed commits only as a count, because autopush should have made that
    impossible -- a non-zero count means autopush itself has failed, which is the
    genuinely interesting signal.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import time

BUDGET_S = 2.5
REGISTER = os.path.join(os.path.expanduser("~"), ".agents", "knowledge", "OPEN-LOOPS.md")
REPO = os.path.join(os.path.expanduser("~"), ".agents")
ROW = re.compile(r"^\|\s*(L-\d+)\s*\|")
HDR = re.compile(r"^\|\s*ID\s*\|", re.IGNORECASE)
MONTH = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})\b",
    re.IGNORECASE,
)
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def _today() -> datetime.date:
    return datetime.date.today()


def _cells(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _parse_tables(text: str):
    """Yield (row_cells, header_cells) per register row.

    STRUCTURAL, not substring-scanning. The register holds SEVERAL tables with
    DIFFERENT columns -- the academic-calendar table has a `Date` column and no
    `Review by` or `Evidence` at all. Reading by header name per table is the
    only way to avoid two false positives that a substring scan produces:

      1. L-10 is OPEN, but its WHY text contains the word "closed"
         ("must be done with the session closed"), so scanning every cell for
         "CLOSED" misread an open loop as silently closed.
      2. Rows whose date reads "by Dec 2026" are dated, just not in ISO form.
    """
    header = None
    for line in text.splitlines():
        if HDR.match(line):
            header = [h.strip().lower() for h in _cells(line)]
            continue
        if ROW.match(line):
            yield _cells(line), header


def _col(header, *names):
    """Index of the first column whose name contains any of `names`."""
    if not header:
        return None
    for i, h in enumerate(header):
        for n in names:
            if n in h:
                return i
    return None


def _get(cells, idx):
    if idx is None or idx >= len(cells):
        return ""
    return cells[idx].strip()


def _parse_date(text: str):
    """ISO first, then 'Oct 2026' / 'by Dec 2026'. Month-only -> end of month."""
    if not text:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = MONTH.search(text)
    if m:
        mo = _MONTHS[m.group(1)[:3].lower()]
        yr = int(m.group(2))
        # month-granularity: treat as the LAST day, so it is not "expired" early
        nxt = datetime.date(yr + (mo == 12), 1 if mo == 12 else mo + 1, 1)
        return nxt - datetime.timedelta(days=1)
    return None


def check_register(findings):
    if not os.path.exists(REGISTER):
        return
    with open(REGISTER, encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    expired, no_date, closed_no_evidence = [], [], []
    for cells, header in _parse_tables(text):
        tag = cells[0].strip() if cells else ""
        if not tag:
            continue
        i_status = _col(header, "status")
        i_date = _col(header, "review by", "review-by", "date")
        i_evid = _col(header, "evidence")

        status = _get(cells, i_status).upper()
        is_closed = "CLOSED" in status

        if is_closed:
            # Only flag a missing evidence cell when this table HAS one.
            if i_evid is not None and not _get(cells, i_evid):
                closed_no_evidence.append(tag)
            continue

        # Only ask for a date when this table has a date column at all.
        if i_date is None:
            continue
        due = _parse_date(_get(cells, i_date))
        if due is None:
            if _get(cells, i_date):
                continue  # dated, just unparseable -- not a gap, do not nag
            no_date.append(tag)
        elif due < _today():
            expired.append("%s (%s, %d days)" % (tag, due.isoformat(), (_today() - due).days))

    if expired:
        findings.append("%d open loop(s) past review-by: %s" % (len(expired), ", ".join(expired[:6])))
    if closed_no_evidence:
        findings.append(
            "%d loop(s) marked CLOSED with an EMPTY evidence column: %s -- the register's "
            "own rule is that nothing closes silently" % (len(closed_no_evidence), ", ".join(closed_no_evidence[:6]))
        )
    if no_date:
        findings.append("%d open loop(s) with no review-by date: %s" % (len(no_date), ", ".join(no_date[:6])))


# --- the three SSOT stores (owner directives D-4, D-5, D-6, D-9) -------------
# Read the JSON directly rather than shelling out to three scripts: a Stop hook
# blocks the turn, so three subprocess spawns would cost more than the entire
# budget. Each store is small and already machine-readable.
TASKBOX = os.path.join(os.path.expanduser("~"), ".agents", "knowledge", "TASKBOX.json")
DIRECTIVES = os.path.join(os.path.expanduser("~"), ".agents", "knowledge", "DIRECTIVES.json")
INVENTORY = os.path.join(os.path.expanduser("~"), ".agents", "knowledge", "INVENTORY.json")
STALE_TASK_DAYS = 3


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def check_stores(findings):
    """Surface what the three registers know. Silent when they are clean."""
    # TASKBOX: in-flight work that has gone stale, or is blocked on nothing named
    db = _load(TASKBOX)
    if db:
        stale, unnamed = [], []
        for t in db.get("tasks", []):
            if t.get("state") not in ("TODO", "DOING", "BLOCKED"):
                continue
            due = _parse_date(t.get("opened", ""))
            if due and (_today() - due).days > STALE_TASK_DAYS:
                stale.append("%s (%dd)" % (t.get("id"), (_today() - due).days))
            if t.get("state") == "BLOCKED" and not t.get("blocker"):
                unnamed.append(t.get("id"))
        if stale:
            findings.append("%d task(s) open past %d days -- promote to an OPEN-LOOPS row "
                            "with an owner, or close: %s"
                            % (len(stale), STALE_TASK_DAYS, ", ".join(stale[:6])))
        if unnamed:
            findings.append("%d task(s) BLOCKED with no blocker named: %s"
                            % (len(unnamed), ", ".join(unnamed[:6])))

    # DIRECTIVES: the "said it, never acted on it" failure
    db = _load(DIRECTIVES)
    if db:
        unapplied = [d.get("id") for d in db.get("directives", [])
                     if d.get("state") != "STALE" and not d.get("applied")]
        unverified = [d.get("id") for d in db.get("directives", [])
                      if d.get("state") != "STALE" and d.get("applied")
                      and not d.get("verified")]
        if unapplied:
            findings.append("%d owner directive(s) enforced NOWHERE: %s -- this is the "
                            "'said it, never acted on it' failure"
                            % (len(unapplied), ", ".join(unapplied[:6])))
        if unverified:
            findings.append("%d directive(s) applied but never verified: %s"
                            % (len(unverified), ", ".join(unverified[:6])))

    # INVENTORY: something vanished and nobody said why
    db = _load(INVENTORY)
    if db:
        ux = [k for k, r in (db.get("items") or {}).items()
              if r.get("state") == "UNEXPLAINED"]
        if ux:
            findings.append("%d estate item(s) vanished with NO recorded reason: %s -- "
                            "run `python scripts/estate-inventory.py explain <name> "
                            "<state> \"<why>\"`" % (len(ux), ", ".join(ux[:6])))


def check_unpushed(findings, deadline):
    """Unpushed commits should be IMPOSSIBLE now. A hit means autopush broke."""
    if time.time() > deadline:
        return
    try:
        branch = subprocess.run(
            ["git", "-C", REPO, "symbolic-ref", "--short", "HEAD"],
            capture_output=True, text=True, timeout=1.5,
        ).stdout.strip()
        if not branch:
            return
        local = subprocess.run(
            ["git", "-C", REPO, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=1.5,
        ).stdout.strip()
        # cached remote ref only: ls-remote is a network call and would blow the budget.
        remote = subprocess.run(
            ["git", "-C", REPO, "rev-parse", "origin/" + branch],
            capture_output=True, text=True, timeout=1.5,
        ).stdout.strip()
        if local and remote and local != remote:
            ahead = subprocess.run(
                ["git", "-C", REPO, "rev-list", "--count", remote + ".." + local],
                capture_output=True, text=True, timeout=1.5,
            ).stdout.strip()
            if ahead and ahead.isdigit() and int(ahead) > 0:
                findings.append(
                    "%s commit(s) on %s not on the cached remote ref -- autopush should have "
                    "made this impossible, so check ~/.agents/logs/autopush.log" % (ahead, branch)
                )
    except Exception:
        return


def main() -> int:
    start = time.time()
    deadline = start + BUDGET_S
    findings: list[str] = []
    try:
        try:
            sys.stdin.read()
        except Exception:
            pass
        check_register(findings)
        check_stores(findings)
        check_unpushed(findings, deadline)
    except Exception:
        return 0  # fail open, always

    if not findings or time.time() - start > BUDGET_S:
        return 0  # silent when clean, and silent rather than late

    msg = "GAP CHECK - address or defer with an owner; do not leave these:\n" + "\n".join(
        "  - " + f for f in findings
    )
    try:
        json.dump(
            {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": msg}},
            sys.stdout,
        )
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
