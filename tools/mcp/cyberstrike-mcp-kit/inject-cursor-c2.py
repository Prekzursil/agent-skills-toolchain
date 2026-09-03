import json, urllib.request
from pathlib import Path
SID="ses_f9c9ab90cffetNo68ohzF6RZAq"
DIR=r"C:\Users\Prekzursil\Cowork\private\cyberstrike-engagements\cursor-auth-recovery-2026-09-02"
PROMPT=Path(r"D:\opt\cyberstrike-mcp\resume-prompt-cursor-c2.txt").read_text(encoding="utf-8").strip()
body=json.dumps({"parts":[{"type":"text","text":PROMPT}]}).encode("utf-8")
req=urllib.request.Request(
    f"http://127.0.0.1:4096/session/{SID}/message",
    data=body, method="POST",
    headers={"Accept":"application/json","Content-Type":"application/json","x-cyberstrike-directory":DIR},
)
try:
    urllib.request.urlopen(req, timeout=8).read()
except Exception as e:
    print(type(e).__name__)
