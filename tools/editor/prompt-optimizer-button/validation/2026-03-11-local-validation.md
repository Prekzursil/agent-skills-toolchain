# 2026-03-11 local validation

- `node --check extension.js` passes.
- `node .\scripts\smoke-test.js` passes.
- Packaged VSIX installs successfully as `prekzursil-local.prompt-optimizer-button@0.1.0`.
- Installed package contains no `openExternal` or browser optimizer URL.
- Compatibility aliases remain present for the old command IDs.
