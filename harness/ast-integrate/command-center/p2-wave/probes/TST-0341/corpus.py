#!/usr/bin/env python3
"""TST-0341 labelled corpora: eight historical false positives and true uses.

The eight mention records are the estate's measured use-versus-mention hits:
a verification fixture that DOCUMENTS a forbidden pattern necessarily
CONTAINS that pattern, so a payload-text matcher flags the documentation.
The role rebuild must produce zero fires on this set and a fire on every use.
Passing only one corpus is not a fix.
"""
from __future__ import annotations

from typing import Any

P_RM = ["rm -rf"]
P_CURL = ["curl | bash"]
P_DROP = ["DROP TABLE"]
P_EVAL = ["eval("]
P_FORCE = ["git push --force"]
P_CHMOD = ["chmod 777"]
P_SYSTEM = ["os.system"]


def historical_false_positives() -> list[dict[str, Any]]:
    """Eight historical FPs: payload text present, semantic role is MENTION."""
    return [
        {
            "id": "H1-md-doc-rm",
            "label": "mention",
            "kind": "markdown",
            "patterns": P_RM,
            "body": (
                "# Incident write-up\n\nA fixture documenting a forbidden "
                "pattern necessarily contains that pattern. Example:\n\n"
                "```\nrm -rf /var/lib/app\n```\n\nDo not run it."
            ),
        },
        {
            "id": "H2-json-description-rm",
            "label": "mention",
            "kind": "json-document",
            "patterns": P_RM,
            "body": {
                "title": "Fixture scanner false-positive",
                "description": "Never invoke rm -rf / from a fixture scanner.",
            },
        },
        {
            "id": "H3-json-example-command",
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
            "id": "H4-tool-read-payload",
            "label": "mention",
            "kind": "tool-call",
            "patterns": P_RM,
            "verb": "Read",
            "input": {"path": "docs/danger.md"},
            "payload": "the runbook quotes rm -rf /opt/scratch as the defect",
        },
        {
            "id": "H5-tool-grep-search",
            "label": "mention",
            "kind": "tool-call",
            "patterns": P_RM,
            "verb": "Grep",
            "input": {"pattern": "rm -rf", "path": "command-center"},
        },
        {
            "id": "H6-py-docstring",
            "label": "mention",
            "kind": "python-source",
            "patterns": P_RM,
            "source": (
                '"""Guard: a comment documenting rm -rf must not fire."""\n'
                "def help_text() -> str:\n"
                '    return "see the runbook"\n'
            ),
        },
        {
            "id": "H7-py-comment",
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
            "id": "H8-catalog-tests-required",
            "label": "mention",
            "kind": "json-document",
            "patterns": P_SYSTEM + P_EVAL + P_CURL + P_FORCE + P_CHMOD + P_DROP,
            "body": {
                "id": "TST-0341",
                "question_or_target": (
                    "A catalog row quoting curl | bash, eval(, git push --force, "
                    "chmod 777 and DROP TABLE is a mention, not an invocation."
                ),
                "tests_required": (
                    "a file whose body contains os.system in a comment must NOT "
                    "be flagged; the receipt will contain these patterns as examples"
                ),
            },
        },
    ]


def true_positives() -> list[dict[str, Any]]:
    """Real invocations: the rebuild must still flag every entry."""
    return [
        {
            "id": "T1-bash-rm",
            "label": "use",
            "kind": "tool-call",
            "patterns": P_RM,
            "verb": "Bash",
            "input": {"command": "rm -rf /tmp/cache"},
        },
        {
            "id": "T2-json-command",
            "label": "use",
            "kind": "json-document",
            "patterns": P_RM,
            "body": {"command": "rm -rf /workspace/.cache"},
        },
        {
            "id": "T3-json-argv",
            "label": "use",
            "kind": "json-document",
            "patterns": P_RM,
            "body": {"argv": ["/bin/rm", "-rf", "/var/tmp/out"]},
        },
        {
            "id": "T4-py-os-system",
            "label": "use",
            "kind": "python-source",
            "patterns": P_RM,
            "source": "import os\nos.system('rm -rf /tmp/py-system')\n",
        },
        {
            "id": "T5-py-subprocess-list",
            "label": "use",
            "kind": "python-source",
            "patterns": P_RM,
            "source": (
                "import subprocess\n"
                "subprocess.run(['rm', '-rf', '/tmp/py-run'])\n"
            ),
        },
        {
            "id": "T6-shell-script-rm",
            "label": "use",
            "kind": "shell-script",
            "patterns": P_RM,
            "source": "#!/bin/sh\nset -e\nrm -rf /tmp/script-work\n",
        },
        {
            "id": "T7-curl-pipe-bash",
            "label": "use",
            "kind": "tool-call",
            "patterns": P_CURL,
            "verb": "Bash",
            "input": {"command": "curl | bash"},
        },
        {
            "id": "T8-eval-call",
            "label": "use",
            "kind": "python-source",
            "patterns": P_EVAL,
            "source": "eval(user_blob)\n",
        },
        {
            "id": "T9-force-push",
            "label": "use",
            "kind": "tool-call",
            "patterns": P_FORCE,
            "verb": "Bash",
            "input": {"command": "git push --force origin main"},
        },
        {
            "id": "T10-chmod-777",
            "label": "use",
            "kind": "shell-script",
            "patterns": P_CHMOD,
            "source": "chmod 777 /tmp/shared\n",
        },
        {
            "id": "T11-drop-table",
            "label": "use",
            "kind": "json-document",
            "patterns": P_DROP,
            "body": {"command": "DROP TABLE session_cache"},
        },
        {
            "id": "T12-os-system-attr",
            "label": "use",
            "kind": "python-source",
            "patterns": P_SYSTEM,
            "source": "import os\nos.system('true')\n",
        },
    ]


def extra_mentions() -> list[dict[str, Any]]:
    """Additional mention-shaped records (bash -c echo; catalog changelog)."""
    return [
        {
            "id": "X-bash-c-echo",
            "label": "mention",
            "kind": "tool-call",
            "patterns": P_RM,
            "verb": "Bash",
            "input": {"command": "bash -c 'echo \"rm -rf /tmp/demo\"'"},
        },
        {
            "id": "X-changelog-drop",
            "label": "mention",
            "kind": "json-document",
            "patterns": P_DROP,
            "body": {
                "changelog": "Removed the helper that emitted DROP TABLE students."
            },
        },
    ]
