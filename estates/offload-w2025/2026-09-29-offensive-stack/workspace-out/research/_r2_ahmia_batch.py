import subprocess, sys, re
sys.path.insert(0, ".")
QUERIES = ["dread forum", "exploit.in", "xss forum", "forgejo", "gitea", "git hosting onion", "bbgate", "cryptbb", "darkforums breach", "uncensored AI"]
for q in QUERIES:
    print(f"########## {q}")
    try:
        r = subprocess.run([r"C:\Python314\python.exe", "ahmia_search.py", q], capture_output=True, text=True, timeout=90)
        out = r.stdout
        lines = [l for l in out.splitlines() if "onion" in l][:12]
        print("\n".join(lines) if lines else out[:300])
    except Exception as e:
        print("ERR", e)
