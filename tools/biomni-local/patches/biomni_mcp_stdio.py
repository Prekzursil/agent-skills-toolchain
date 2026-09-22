import os
import sys

# The CS daemon spawns this file inside its MCP sandbox with a minimal env:
# BIOMNI_CUSTOM_BASE_URL / BIOMNI_CUSTOM_API_KEY / BIOMNI_LLM live in
# ~/Biomni/.env (the web app loads it via python-dotenv; this standalone
# transport must do the same or A1 construction dies with a KeyError).
from dotenv import load_dotenv

_BIOMNI_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BIOMNI_DIR, ".env"))

sys.path.insert(0, _BIOMNI_DIR)

from biomni_mcp_server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
