# Upstream Notes

- Official site: `https://frida.re/`
- Common Windows install path: `py -3 -m pip install --upgrade frida-tools`
- Minimum sanity checks:
  - `frida --version`
  - `frida-ps -ai`
  - `frida-ps -Uai` when a mobile device is attached
- Use `frida-mcp` when the request is about AI client integration rather than manual Frida technique
