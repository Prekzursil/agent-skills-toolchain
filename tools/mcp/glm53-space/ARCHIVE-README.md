# archive/glm53-space-2026-09 - git safety for the deleted glm53-space MCP lane (D1 = hard delete)

This branch is the archive ref named by DECISION-QUEUE.md D1 / BUILD-WAVE-PROPOSAL.md T0-1.

What it holds today (pushed from the cloud worker, 2026-09-02):

- the last registry state that still carried the `glm53-space` row (`.agents/agents.json`, the
  `mcp.servers.glm53-space` entry: `uv.exe run --locked --directory ...\tools\mcp\glm53-space python
  mcp_server.py`, `HUGGINGFACE_TOKEN` by name, tags approved / claude-only / hosted-inference /
  owner-requested / stdio), the Cursor safe-default attach slot in
  `.agents/scripts/merge_generated_cursor_mcp.py`, the pinned live tests in
  `.agents/tests/test_mcp_control_plane_live.py`, and the provenance line in
  `.provenance/.agents/agents.json.md`.

What it does NOT hold yet, and why: the code of `tools/mcp/glm53-space/` (`mcp_server.py`,
`glm53_core.py`, `openai_proxy.py`, `pyproject.toml`, `uv.lock`) exists ONLY in the Windows executed
checkout (`~/source/agent-skills-toolchain`); it was never on any remote ref (CONSOLIDATED-GEM-DECISIONS
V1: `git ls-tree` empty on all 57 origin refs). A cloud worker cannot read that disk.

Owner step (OWNER-CLICKS.md, D1-1), from the Windows box, before or after the PR merges - the deletion
on the PR branch removes nothing that git holds:

    git -C C:\Users\Prekzursil\source\agent-skills-toolchain fetch origin
    git -C C:\Users\Prekzursil\source\agent-skills-toolchain worktree add D:\wt-archive-glm53 archive/glm53-space-2026-09
    robocopy C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\glm53-space D:\wt-archive-glm53\tools\mcp\glm53-space /E /XD .venv __pycache__
    git -C D:\wt-archive-glm53 add tools/mcp/glm53-space
    git -C D:\wt-archive-glm53 commit -m "archive(glm53-space): box copy of the retired lane (parity oracle for glm53_chat)"
    git -C D:\wt-archive-glm53 push origin archive/glm53-space-2026-09
    git -C C:\Users\Prekzursil\source\agent-skills-toolchain worktree remove D:\wt-archive-glm53

The capability is preserved elsewhere: `.agents/models.json` model `glm-5.3` (endpoint `hf-router`,
`zai-org/GLM-5.3:zai-org`) served by `inference-hub` (`tools/mcp/inference-hub/`), reachable from
Claude Code and Cursor through the same safe-default adapter slot glm53-space used to occupy.
