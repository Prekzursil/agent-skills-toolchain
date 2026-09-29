import json, os, shutil, sys

# Reads the drift-report-derived TSV and byte-copies ONLY the scoped, live-newer rows
# live -> repo. Skips HELD, repo-newer (mtimeSays == REPO), and excluded state files.
# Every row prints SUCCESS/FAILED per AGENTS.md 4.

BASE = r"C:\Users\Prekzursil\source\agent-skills-toolchain"
LIST = r"C:\Users\Prekzursil\.agents\knowledge\audits\MEGAWAVE-A\scoped-reconcile-list.txt"

BANNED = ("secrets", "token", ".pem", ".key", "browser-profiles", "node_modules")

ok = 0
fail = 0
with open(LIST, encoding="utf-8") as f:
    for line in f:
        status, area, repo_path, live_path, mtime_says = line.rstrip("\n").split("\t")
        # scope guards
        if status == "CHANGED" and mtime_says != "LIVE":
            print(f"SKIP(repo-newer) {repo_path}")
            continue
        low = repo_path.lower()
        if any(b in low for b in BANNED):
            print(f"SKIP(banned-pattern) {repo_path}")
            continue
        dest = os.path.join(BASE, repo_path.replace("/", os.sep))
        if status == "CHANGED" and not os.path.isfile(dest):
            print(f"FAILED:{repo_path} reason=repo-file-missing-for-CHANGED")
            fail += 1
            continue
        if not os.path.isfile(live_path):
            print(f"FAILED:{repo_path} reason=live-source-missing")
            fail += 1
            continue
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(live_path, dest)
            print(f"SUCCESS:{repo_path} ({status}, {os.path.getsize(dest)}B)")
            ok += 1
        except OSError as e:
            print(f"FAILED:{repo_path} reason={e}")
            fail += 1

print(f"COPIED_OK={ok} FAILED={fail}")
sys.exit(0 if fail == 0 else 1)
