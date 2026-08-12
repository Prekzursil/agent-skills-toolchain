"""Dump one journal record's result to a readable text file."""
import json
import os
import sys

ROOT = os.path.expanduser(
    "~/.claude/projects/C--Users-Prekzursil/30bd50d4-5a72-4c19-8fd5-85b6430c7b7d/subagents/workflows"
)


def main():
    wf = sys.argv[1]
    target_line = int(sys.argv[2])
    out = sys.argv[3]
    jp = os.path.join(ROOT, wf, "journal.jsonl")
    with open(jp, "r", encoding="utf-8", errors="replace") as fh:
        for lineno, line in enumerate(fh, 1):
            if lineno != target_line:
                continue
            rec = json.loads(line)
            res = rec.get("result")
            with open(out, "w", encoding="utf-8") as ofh:
                ofh.write(f"# agentId={rec.get('agentId')}\n# type={rec.get('type')}\n\n")
                if isinstance(res, dict):
                    for k, v in res.items():
                        ofh.write(f"\n===== {k} =====\n")
                        ofh.write(v if isinstance(v, str) else json.dumps(v, indent=1))
                        ofh.write("\n")
                else:
                    ofh.write(str(res))
            print(f"WROTE {out} bytes={os.path.getsize(out)}")
            return
    print("LINE NOT FOUND")


if __name__ == "__main__":
    main()
