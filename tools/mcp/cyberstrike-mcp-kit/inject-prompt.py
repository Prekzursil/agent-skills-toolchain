import json, os, sys, urllib.request
from pathlib import Path

SID = "ses_f9a40bf69ffeY2c0WX3S2jrsAP"
DIR = r"C:\Users\Prekzursil"
PROMPT = (
    Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else r"D:\opt\cyberstrike-mcp\resume-prompt-fullpower-3.txt"
    )
    .read_text(encoding="utf-8")
    .strip()
)

body = json.dumps({"parts": [{"type": "text", "text": PROMPT}]}).encode("utf-8")
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "x-cyberstrike-directory": DIR,
}
pw = os.environ.get("CYBERSTRIKE_SERVER_PASSWORD", "")
if pw:
    headers["Authorization"] = "Bearer " + pw

req = urllib.request.Request(
    f"http://127.0.0.1:4096/session/{SID}/message",
    data=body,
    method="POST",
    headers=headers,
)
try:
    resp = urllib.request.urlopen(req, timeout=15).read()
    print("OK", resp[:200])
except Exception as e:
    print(type(e).__name__, e)
