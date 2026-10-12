"""Tiny compute probe: forces a real container start (paused workspaces fail here)."""
import modal

app = modal.App("estate-probe")

@app.function(timeout=60)
def ping():
    return "pong"
