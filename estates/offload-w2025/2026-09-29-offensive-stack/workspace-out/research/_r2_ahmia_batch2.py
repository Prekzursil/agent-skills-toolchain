import subprocess
QUERIES = ["breachforums", "leakbase", "shinyhunters", "nulled forum", "altenen", "cracked.io", "damage forum", "RAMP ransomware forum", "BHF forum", "exploit2", "xss.is"]
for q in QUERIES:
    print(f"########## {q}")
    try:
        r = subprocess.run([r"C:\Python314\python.exe", "ahmia_search.py", q], capture_output=True, text=True, timeout=90)
        out = r.stdout
        lines = [l for l in out.splitlines() if ".onion" in l][:8]
        print("\n".join(lines) if lines else out[:200])
    except Exception as e:
        print("ERR", e)
