# Editor Tools

`tools/editor/` is the live home for editor-local tooling such as VS Code extensions and vendored host-local agent frameworks that do not fit the MCP-native or browser-mediated surfaces.

Use this surface for projects that run inside an editor host rather than as MCP-native servers or browser-mediated tools. Keep the runtime boundary, installation path, and validation steps explicit.

Current live editor tool projects:

- [`metaswarm/`](metaswarm/README.md) - vendored upstream `dsifry/metaswarm` multi-agent orchestration framework snapshot at commit `03ce5da2beea391524c2e8f31187cabf090febe4`.
