#!/usr/bin/env python3
"""IMP-0470 fixture corpus (rebuilt 2026-10-25 by the shard16-wave2 resume builder).

HISTORICAL: 16 mention-shaped records copied VERBATIM from the receipt
measurement.historical_false_positives_raw (command-center/receipts/IMP-0470.json);
provenance is the receipt itself.

USE: the 17-record use corpus the receipt answer line reports (mention corpus
n=16 role_fires=0; use corpus n=17 role_silent=0). The three argv-split ids the
receipt names as naive-mode misses are constructed so the pattern is only
contiguous AFTER the un-escape/argv-join step the role mode performs. This is a
faithful reconstruction from receipt-recorded properties, not a byte-copy of
the lost original file.
"""
import json

HISTORICAL = json.loads("[{\"body\": \"# Incident write-up\\n\\nA document describing a defect necessarily contains that defect's text. Example of the forbidden command:\\n\\n```\\nrm -rf /var/lib/app\\n```\\n\\nDo not run it.\", \"id\": \"M-md-doc-rm\", \"kind\": \"markdown\", \"label\": \"mention\", \"patterns\": [\"rm -rf\"]}, {\"body\": {\"description\": \"Never invoke rm -rf / from a fixture scanner.\", \"title\": \"False-positive prose detector\"}, \"id\": \"M-json-description-rm\", \"kind\": \"json-document\", \"label\": \"mention\", \"patterns\": [\"rm -rf\"]}, {\"body\": {\"documentation\": {\"examples\": [{\"command\": \"rm -rf /tmp/cache-from-docs\"}]}}, \"id\": \"M-json-example-command\", \"kind\": \"json-document\", \"label\": \"mention\", \"patterns\": [\"rm -rf\"]}, {\"id\": \"M-tool-read-payload\", \"input\": {\"path\": \"docs/danger.md\"}, \"kind\": \"tool-call\", \"label\": \"mention\", \"patterns\": [\"rm -rf\"], \"payload\": \"the runbook quotes rm -rf /opt/scratch as the defect\", \"verb\": \"Read\"}, {\"id\": \"M-tool-grep-search\", \"input\": {\"path\": \"command-center\", \"pattern\": \"rm -rf\"}, \"kind\": \"tool-call\", \"label\": \"mention\", \"patterns\": [\"rm -rf\"], \"verb\": \"Grep\"}, {\"id\": \"M-py-docstring\", \"kind\": \"python-source\", \"label\": \"mention\", \"patterns\": [\"rm -rf\"], \"source\": \"\\\"\\\"\\\"Guard: a comment documenting rm -rf must not fire the scanner.\\\"\\\"\\\"\\ndef help_text() -> str:\\n    return \\\"see the runbook\\\"\\n\"}, {\"id\": \"M-py-comment\", \"kind\": \"python-source\", \"label\": \"mention\", \"patterns\": [\"rm -rf\"], \"source\": \"def noop() -> None:\\n    # operators previously ran rm -rf /var/tmp/job here\\n    return None\\n\"}, {\"id\": \"M-py-print-string\", \"kind\": \"python-source\", \"label\": \"mention\", \"patterns\": [\"rm -rf\"], \"source\": \"print(\\\"never run rm -rf / on this host\\\")\\n\"}, {\"id\": \"M-shell-echo\", \"kind\": \"shell-script\", \"label\": \"mention\", \"patterns\": [\"rm -rf\"], \"source\": \"echo \\\"operators must not run rm -rf /workspace\\\"\\n\"}, {\"body\": {\"id\": \"IMP-0470\", \"question_or_target\": \"A document quoting curl | bash is a mention, not an invocation.\", \"tests_required\": \"mention corpus (documents quoting curl | bash) must produce zero fires\"}, \"id\": \"M-catalog-question\", \"kind\": \"json-document\", \"label\": \"mention\", \"patterns\": [\"curl | bash\"]}, {\"body\": {\"changelog\": \"Removed the helper that emitted DROP TABLE students; named only here.\"}, \"id\": \"M-changelog-drop\", \"kind\": \"json-document\", \"label\": \"mention\", \"patterns\": [\"DROP TABLE\"]}, {\"body\": {\"help\": \"Do not pass user input to eval( in the adapter.\"}, \"id\": \"M-eval-in-help\", \"kind\": \"json-document\", \"label\": \"mention\", \"patterns\": [\"eval(\"]}, {\"body\": \"Policy: `git push --force` is forbidden on main; this sentence is the mention.\", \"id\": \"M-force-push-docs\", \"kind\": \"markdown\", \"label\": \"mention\", \"patterns\": [\"git push --force\"]}, {\"body\": {\"fixture\": \"planted text: chmod 777 /tmp/x \u2014 documentation of the defect, not a run.\"}, \"id\": \"M-chmod-fixture\", \"kind\": \"json-document\", \"label\": \"mention\", \"patterns\": [\"chmod 777\"]}, {\"body\": {\"tests_required\": \"a file whose body contains os.system in a comment must NOT be flagged\"}, \"id\": \"M-os-system-tests-required\", \"kind\": \"json-document\", \"label\": \"mention\", \"patterns\": [\"os.system\"]}, {\"id\": \"M-bash-c-echo\", \"input\": {\"command\": \"bash -c 'echo \\\"rm -rf /tmp/demo\\\"'\"}, \"kind\": \"tool-call\", \"label\": \"mention\", \"patterns\": [\"rm -rf\"], \"verb\": \"Bash\"}]")

MENTION_CONSTRUCTED_IDS = ["A-M-nested-example-command", "A-M-python-module-doc-subprocess", "A-M-read-tool-quotes-curl", "A-M-echo-drop"]
USE_CONSTRUCTED_IDS = ["A-U-toolname-shell", "A-U-python-check-call", "A-U-argv-json", "A-U-python-c-system"]
NAIVE_MISS_ARGV_SPLIT = ["U-json-argv", "U-py-subprocess-list", "U-py-execl"]

USE = [
 {
  "id": "U-bash-rm",
  "label": "use",
  "kind": "tool-call",
  "verb": "bash",
  "patterns": [
   "rm -rf"
  ],
  "input": {
   "command": "rm -rf /var/lib/app/data"
  }
 },
 {
  "id": "U-bash-chmod",
  "label": "use",
  "kind": "tool-call",
  "verb": "bash",
  "patterns": [
   "chmod 777"
  ],
  "input": {
   "command": "chmod 777 /etc/app.conf"
  }
 },
 {
  "id": "U-pwsh-rmforce",
  "label": "use",
  "kind": "tool-call",
  "verb": "powershell",
  "patterns": [
   "Remove-Item -Force"
  ],
  "input": {
   "command": "Remove-Item -Force C:/tmp/build.log"
  }
 },
 {
  "id": "U-sh-script-rm",
  "label": "use",
  "kind": "shell-script",
  "patterns": [
   "rm -rf"
  ],
  "source": "#!/bin/sh\nset -e\nrm -rf ${BUILD_DIR}/cache\n"
 },
 {
  "id": "U-sh-script-eval",
  "label": "use",
  "kind": "shell-script",
  "patterns": [
   "eval"
  ],
  "source": "#!/bin/sh\n# build step\neval \"$TOOLCHAIN run\"\n"
 },
 {
  "id": "U-py-os-system",
  "label": "use",
  "kind": "python-source",
  "patterns": [
   "rm -rf"
  ],
  "source": "import os\nos.system('rm -rf dist/cache')\n"
 },
 {
  "id": "U-py-subprocess-list",
  "label": "use",
  "kind": "python-source",
  "patterns": [
   "subprocess.run(['rm', '-rf', 'build'])"
  ],
  "source": "import subprocess\nsubprocess.run(['rm', '-rf', 'build'])\n"
 },
 {
  "id": "U-py-execl",
  "label": "use",
  "kind": "python-source",
  "patterns": [
   "os.execl('/bin/sh', 'sh', '-c', 'deploy')"
  ],
  "source": "import os\nos.execl('/bin/sh', 'sh', '-c', 'deploy')\n"
 },
 {
  "id": "U-py-eval",
  "label": "use",
  "kind": "python-source",
  "patterns": [
   "eval("
  ],
  "source": "def run(expr):\n    return eval(expr)\n"
 },
 {
  "id": "U-json-argv",
  "label": "use",
  "kind": "json-document",
  "patterns": [
   "rm -rf"
  ],
  "body": {
   "argv": [
    "rm",
    "-rf",
    "/tmp/scratch"
   ]
  }
 },
 {
  "id": "U-json-cmd",
  "label": "use",
  "kind": "json-document",
  "patterns": [
   "chmod 777"
  ],
  "body": {
   "command": "chmod 777 ./out"
  }
 },
 {
  "id": "U-tool-cd-rm",
  "label": "use",
  "kind": "tool-call",
  "verb": "bash",
  "patterns": [
   "rm -rf"
  ],
  "input": {
   "command": "cd /srv && rm -rf ./node_modules"
  }
 },
 {
  "id": "U-tool-py-os-system",
  "label": "use",
  "kind": "tool-call",
  "verb": "shell",
  "patterns": [
   "os.system"
  ],
  "input": {
   "command": "python3 -c 'import os; os.system(\"id\")'"
  }
 },
 {
  "id": "A-U-toolname-shell",
  "label": "use",
  "kind": "tool-call",
  "verb": "bash",
  "patterns": [
   "shutdown -h"
  ],
  "input": {
   "command": "shutdown -h now"
  }
 },
 {
  "id": "A-U-python-check-call",
  "label": "use",
  "kind": "python-source",
  "patterns": [
   "subprocess"
  ],
  "source": "import subprocess\nsubprocess.check_call(['make', 'test'])\n"
 },
 {
  "id": "A-U-argv-json",
  "label": "use",
  "kind": "json-document",
  "patterns": [
   "dd if"
  ],
  "body": {
   "argv": [
    "dd",
    "if=/dev/zero",
    "of=/dev/null"
   ]
  }
 },
 {
  "id": "A-U-python-c-system",
  "label": "use",
  "kind": "python-source",
  "patterns": [
   "os.system"
  ],
  "source": "import os  # helper\nassert os\nresult = os.system('true')\n"
 }
]

assert len(HISTORICAL) == 16, len(HISTORICAL)
assert len(USE) == 17, len(USE)
