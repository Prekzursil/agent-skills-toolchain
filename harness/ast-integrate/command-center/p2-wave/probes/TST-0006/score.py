"""Token- and payload-level scores of the linter against gold labels."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from gold_label import label_file
from path_linter import UNVERIFIED, lint_file, normalize_token, stat_cited_path


def _norm_set(tokens: list[str], root: Path) -> set[str]:
    out: set[str] = set()
    for token in tokens:
        norm, _exists = stat_cited_path(root, token)
        out.add(norm)
        out.add(normalize_token(token))
    return {t for t in out if t}


def _ratio(num: int, den: int) -> float | None:
    if den == 0:
        return None
    return num / den


def score_payloads(paths: list[Path], root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    tp = fp = fn = 0
    pay_tp = pay_fp = pay_fn = pay_tn = 0
    mention_n = mention_flagged = 0
    for path in paths:
        gold = label_file(path, root)
        lint = lint_file(path, root)
        gflag = _norm_set(gold["should_flag"], root)
        lflag = _norm_set(lint.flagged_paths, root)
        mention = _norm_set(gold["mention_paths"], root)
        tp += len(lflag & gflag)
        fp += len(lflag - gflag)
        fn += len(gflag - lflag)
        mention_n += len(mention)
        mention_flagged += len(mention & lflag)
        # Fenced-only mentions: those with role MENTION in the linter that
        # gold also listed. Gold mention_paths are fences + documentary keys.
        # Illustrative = gold mention (documentation examples).
        gpos = gold["gold_status"] == UNVERIFIED
        lpos = lint.status == UNVERIFIED
        if gpos and lpos:
            pay_tp += 1
        elif lpos and not gpos:
            pay_fp += 1
        elif gpos and not lpos:
            pay_fn += 1
        else:
            pay_tn += 1
        rel = path.as_posix()
        if str(root) in rel:
            rel = str(path.relative_to(root).as_posix())
        rows.append(
            {
                "path": rel,
                "gold_status": gold["gold_status"],
                "lint_status": lint.status,
                "n_use_gold": len(gold["use_paths"]),
                "n_mention_gold": len(gold["mention_paths"]),
                "n_should_flag": len(gold["should_flag"]),
                "n_lint_flagged": len(lint.flagged_paths),
                "use_paths": gold["use_paths"],
                "mention_paths": gold["mention_paths"],
                "should_flag": gold["should_flag"],
                "lint_flagged": list(lint.flagged_paths),
            }
        )
    token_prec = _ratio(tp, tp + fp)
    token_rec = _ratio(tp, tp + fn)
    pay_prec = _ratio(pay_tp, pay_tp + pay_fp)
    pay_rec = _ratio(pay_tp, pay_tp + pay_fn)
    illus_fp = _ratio(mention_flagged, mention_n)
    return {
        "n_payloads": len(paths),
        "token": {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": token_prec,
            "recall": token_rec,
        },
        "payload": {
            "tp": pay_tp,
            "fp": pay_fp,
            "fn": pay_fn,
            "tn": pay_tn,
            "precision": pay_prec,
            "recall": pay_rec,
        },
        "illustrative": {
            "n_mention_paths": mention_n,
            "n_mention_flagged": mention_flagged,
            "false_positive_rate": illus_fp,
            "definition": (
                "gold MENTION = path tokens inside fenced code or documentary "
                "JSON keys (catalog quotes, titles, examples). FP = linter "
                "flagged a gold-MENTION token as a missing citation."
            ),
        },
        "rows": rows,
    }
