#!/usr/bin/env python3
"""IMP-0470 labelled corpora: mention, use, historical false positives.

Historical false positives are the mention-shaped records that a payload-text
matcher fires on (documents, fixtures, catalog rows, comments, quoted examples).
The role library must produce zero fires on mention and a fire on every use.
Passing only one corpus is not a fix.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "hooks" / "_shared"))
import use_vs_mention as uvm  # noqa: E402

P_RM = ["rm -rf"]
P_CURL = ["curl | bash"]
P_DROP = ["DROP TABLE"]
P_EVAL = ["eval("]
P_FORCE = ["git push --force"]
P_CHMOD = ["chmod 777"]
P_SYSTEM = ["os.system"]


def mention_corpus() -> list[dict[str, Any]]:
    return [
        {
            "id": "M-md-doc-rm",
            "label": "mention",
            "kind": "markdown",
            "patterns": P_RM,
            "body": (
                "# Incident write-up\n\nA document describing a defect necessarily "
                "contains that defect's text. Example of the forbidden command:\n\n"
                "```\nrm -rf /var/lib/app\n```\n\nDo not run it."
            ),
        },
        {
            "id": "M-json-description-rm",
            "label": "mention",
            "kind": "json-document",
            "patterns": P_RM,
            "body": {
                "title": "False-positive prose detector",
                "description": "Never invoke rm -rf / from a fixture scanner.",
            },
        },
        {
            "id": "M-json-example-command",
            "label": "mention",
            "kind": "json-document",
            "patterns": P_RM,
            "body": {
                "documentation": {
                    "examples": [{"command": "rm -rf /tmp/cache-from-docs"}]
                }
            },
        },
        {
            "id": "M-tool-read-payload",
            "label": "mention",
            "kind": "tool-call",
            "patterns": P_RM,
            "verb": "Read",
            "input": {"path": "docs/danger.md"},
            "payload": "the runbook quotes rm -rf /opt/scratch as the defect",
        },
        {
            "id": "M-tool-grep-search",
            "label": "mention",
            "kind": "tool-call",
            "patterns": P_RM,
            "verb": "Grep",
            "input": {"pattern": "rm -rf", "path": "command-center"},
        },
        {
            "id": "M-py-docstring",
            "label": "mention",
            "kind": "python-source",
            "patterns": P_RM,
            "source": (
                '"""Guard: a comment documenting rm -rf must not fire the scanner."""\n'
                "def help_text() -> str:\n"
                '    return "see the runbook"\n'
            ),
        },
        {
            "id": "M-py-comment",
            "label": "mention",
            "kind": "python-source",
            "patterns": P_RM,
            "source": (
                "def noop() -> None:\n"
                "    # operators previously ran rm -rf /var/tmp/job here\n"
                "    return None\n"
            ),
        },
        {
            "id": "M-py-print-string",
            "label": "mention",
            "kind": "python-source",
            "patterns": P_RM,
            "source": 'print("never run rm -rf / on this host")\n',
        },
        {
            "id": "M-shell-echo",
            "label": "mention",
            "kind": "shell-script",
            "patterns": P_RM,
            "source": 'echo "operators must not run rm -rf /workspace"\n',
        },
        {
            "id": "M-catalog-question",
            "label": "mention",
            "kind": "json-document",
            "patterns": P_CURL,
            "body": {
                "id": "IMP-0470",
                "question_or_target": (
                    "A document quoting curl | bash is a mention, not an invocation."
                ),
                "tests_required": (
                    "mention corpus (documents quoting curl | bash) must produce zero fires"
                ),
            },
        },
        {
            "id": "M-changelog-drop",
            "label": "mention",
            "kind": "json-document",
            "patterns": P_DROP,
            "body": {
                "changelog": "Removed the helper that emitted DROP TABLE students; named only here."
            },
        },
        {
            "id": "M-eval-in-help",
            "label": "mention",
            "kind": "json-document",
            "patterns": P_EVAL,
            "body": {"help": "Do not pass user input to eval( in the adapter."},
        },
        {
            "id": "M-force-push-docs",
            "label": "mention",
            "kind": "markdown",
            "patterns": P_FORCE,
            "body": "Policy: `git push --force` is forbidden on main; this sentence is the mention.",
        },
        {
            "id": "M-chmod-fixture",
            "label": "mention",
            "kind": "json-document",
            "patterns": P_CHMOD,
            "body": {
                "fixture": "planted text: chmod 777 /tmp/x — documentation of the defect, not a run."
            },
        },
        {
            "id": "M-os-system-tests-required",
            "label": "mention",
            "kind": "json-document",
            "patterns": P_SYSTEM,
            "body": {
                "tests_required": "a file whose body contains os.system in a comment must NOT be flagged"
            },
        },
        {
            "id": "M-bash-c-echo",
            "label": "mention",
            "kind": "tool-call",
            "patterns": P_RM,
            "verb": "Bash",
            "input": {"command": "bash -c 'echo \"rm -rf /tmp/demo\"'"},
        },
    ]


def use_corpus() -> list[dict[str, Any]]:
    return [
        {
            "id": "U-bash-rm",
            "label": "use",
            "kind": "tool-call",
            "patterns": P_RM,
            "verb": "Bash",
            "input": {"command": "rm -rf /tmp/cache"},
        },
        {
            "id": "U-shell-parameters",
            "label": "use",
            "kind": "tool-call",
            "patterns": P_RM,
            "name": "Shell",
            "parameters": {"command": "rm -rf /opt/tmp/work"},
        },
        {
            "id": "U-sudo-rm",
            "label": "use",
            "kind": "tool-call",
            "patterns": P_RM,
            "verb": "Bash",
            "input": {"command": "sudo rm -rf /var/tmp/job"},
        },
        {
            "id": "U-bash-c-rm",
            "label": "use",
            "kind": "tool-call",
            "patterns": P_RM,
            "verb": "Bash",
            "input": {"command": "bash -c 'rm -rf /tmp/boxed'"},
        },
        {
            "id": "U-json-command",
            "label": "use",
            "kind": "json-document",
            "patterns": P_RM,
            "body": {"command": "rm -rf /workspace/.cache"},
        },
        {
            "id": "U-json-argv",
            "label": "use",
            "kind": "json-document",
            "patterns": P_RM,
            "body": {"argv": ["/bin/rm", "-rf", "/var/tmp/out"]},
        },
        {
            "id": "U-py-os-system",
            "label": "use",
            "kind": "python-source",
            "patterns": P_RM,
            "source": "import os\nos.system('rm -rf /tmp/py-system')\n",
        },
        {
            "id": "U-py-subprocess-list",
            "label": "use",
            "kind": "python-source",
            "patterns": P_RM,
            "source": (
                "import subprocess\n"
                "subprocess.run(['rm', '-rf', '/tmp/py-run'])\n"
            ),
        },
        {
            "id": "U-py-popen-shell",
            "label": "use",
            "kind": "python-source",
            "patterns": P_RM,
            "source": (
                "import subprocess\n"
                "subprocess.Popen('rm -rf /tmp/py-popen', shell=True)\n"
            ),
        },
        {
            "id": "U-py-execl",
            "label": "use",
            "kind": "python-source",
            "patterns": P_RM,
            "source": "import os\nos.execl('/bin/rm', 'rm', '-rf', '/tmp/py-exec')\n",
        },
        {
            "id": "U-shell-script-rm",
            "label": "use",
            "kind": "shell-script",
            "patterns": P_RM,
            "source": "#!/bin/sh\nset -e\nrm -rf /tmp/script-work\n",
        },
        {
            "id": "U-curl-pipe-bash",
            "label": "use",
            "kind": "tool-call",
            "patterns": P_CURL,
            "verb": "Bash",
            "input": {"command": "curl | bash"},
        },
        {
            "id": "U-drop-table",
            "label": "use",
            "kind": "json-document",
            "patterns": P_DROP,
            "body": {"command": "DROP TABLE session_cache"},
        },
        {
            "id": "U-eval-call",
            "label": "use",
            "kind": "python-source",
            "patterns": P_EVAL,
            "source": "eval(user_blob)\n",
        },
        {
            "id": "U-force-push",
            "label": "use",
            "kind": "tool-call",
            "patterns": P_FORCE,
            "verb": "Bash",
            "input": {"command": "git push --force origin main"},
        },
        {
            "id": "U-chmod-777",
            "label": "use",
            "kind": "shell-script",
            "patterns": P_CHMOD,
            "source": "chmod 777 /tmp/shared\n",
        },
        {
            "id": "U-os-system-attr",
            "label": "use",
            "kind": "python-source",
            "patterns": P_SYSTEM,
            "source": "import os\nos.system('true')\n",
        },
    ]


def historical_false_positives() -> list[dict[str, Any]]:
    """Mention records that the naive matcher fires on — the historical FP corpus."""
    return mention_corpus()


def adversarial_mentions() -> list[dict[str, Any]]:
    """Held-out mentions the refuter constructed (not in the training corpora)."""
    return [
        {
            "id": "A-M-nested-example-command",
            "label": "mention",
            "kind": "json-document",
            "patterns": P_RM,
            "body": {
                "docs": {
                    "examples": [
                        {"title": "bad", "command": "rm -rf /var/lib/held-out"}
                    ]
                }
            },
        },
        {
            "id": "A-M-python-module-doc-subprocess",
            "label": "mention",
            "kind": "python-source",
            "patterns": P_RM,
            "source": (
                '"""Example (do not execute): subprocess.run("rm -rf /", shell=True)"""\n'
                "x = 1\n"
            ),
        },
        {
            "id": "A-M-read-tool-quotes-curl",
            "label": "mention",
            "kind": "tool-call",
            "patterns": P_CURL,
            "verb": "Read",
            "input": {"path": "README.md"},
            "payload": "install docs show curl | bash as the anti-pattern",
        },
        {
            "id": "A-M-echo-drop",
            "label": "mention",
            "kind": "shell-script",
            "patterns": P_DROP,
            "source": 'printf "%s\\n" "never emit DROP TABLE in production"\n',
        },
    ]


def adversarial_uses() -> list[dict[str, Any]]:
    """Held-out uses the refuter constructed (not in the training corpora)."""
    return [
        {
            "id": "A-U-toolname-shell",
            "label": "use",
            "kind": "tool-call",
            "patterns": P_RM,
            "toolName": "Shell",
            "tool_input": {"command": "rm -rf /opt/held-out"},
        },
        {
            "id": "A-U-python-check-call",
            "label": "use",
            "kind": "python-source",
            "patterns": P_RM,
            "source": (
                "import subprocess\n"
                "subprocess.check_call(['rm', '-rf', '/tmp/held-out'])\n"
            ),
        },
        {
            "id": "A-U-argv-json",
            "label": "use",
            "kind": "json-document",
            "patterns": P_FORCE,
            "body": {"argv": ["git", "push", "--force", "origin", "topic"]},
        },
        {
            "id": "A-U-python-c-system",
            "label": "use",
            "kind": "tool-call",
            "patterns": P_RM,
            "verb": "Bash",
            "input": {
                "command": "python3 -c \"import os; os.system('rm -rf /tmp/py-c')\""
            },
        },
    ]


def evaluate_split(
    records: list[dict[str, Any]], *, require_label: str | None = None
) -> dict[str, Any]:
    naive = uvm.confusion_matrix(records, mode="naive")
    role = uvm.confusion_matrix(records, mode="role")
    fires_role = [r["id"] for r in role["rows"] if r.get("fires")]
    silent_role = [r["id"] for r in role["rows"] if not r.get("fires")]
    naive_fires = [r["id"] for r in naive["rows"] if r.get("fires")]
    if require_label == "mention":
        ok = role["fp"] == 0 and role["tn"] == role["labelled"] and naive["fp"] == naive["labelled"]
        if not ok or role["tp"] or role["fn"]:
            ok = role["fp"] == 0 and all(not r.get("fires") for r in role["rows"])
            ok = ok and all(r.get("fires") for r in naive["rows"])
    elif require_label == "use":
        # Role must fire on every use. Naive substring may miss argv-split
        # forms (`['rm', '-rf']`); that miss is evidence the role library
        # measures something payload-text does not.
        ok = (
            role["fn"] == 0
            and role["tp"] == role["labelled"]
            and all(r.get("fires") for r in role["rows"])
        )
    else:
        ok = True
    return {
        "n": len(records),
        "naive": {k: naive[k] for k in ("tp", "fp", "fn", "tn", "false_positive_rate", "recall_use", "labelled")},
        "role": {k: role[k] for k in ("tp", "fp", "fn", "tn", "false_positive_rate", "recall_use", "labelled")},
        "role_fires_ids": fires_role,
        "role_silent_ids": silent_role,
        "naive_fires_ids": naive_fires,
        "surviving_false_positives": uvm.surviving_false_positives(records),
        "missed_uses": uvm.missed_uses(records),
        "ok": ok,
    }


def both_corpora_pass() -> dict[str, Any]:
    mention = evaluate_split(mention_corpus(), require_label="mention")
    use = evaluate_split(use_corpus(), require_label="use")
    hist = evaluate_split(historical_false_positives(), require_label="mention")
    # Passing only one corpus is not a fix.
    ok = bool(mention["ok"] and use["ok"] and hist["ok"])
    return {
        "mention": mention,
        "use": use,
        "historical": hist,
        "ok": ok,
        "both_required": True,
        "mention_only_would_not_count": mention["ok"] and not use["ok"],
        "use_only_would_not_count": use["ok"] and not mention["ok"],
    }
