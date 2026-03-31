# Ghidra Bridge Notes

## Upstream

- Repository: https://github.com/justfoxing/ghidra_bridge

## Local install

- Python environment: `%USERPROFILE%\.local\opt\ghidra-bridge\.venv\`
- Ghidra-side scripts staged in: `%APPDATA%\ghidra\ghidra_12.0.3_PUBLIC\ghidra_scripts\`

## Required host step

Inside Ghidra, run `ghidra_bridge_server_background.py` (or the foreground variant) from Script Manager before expecting the external Python client to connect.
