# COUNCIL-STRUCTURAL-MEMORY_2026-08-28

## Issue 4: Home directory is the Cursor workspace root (Double-loading MCPs)

**Problem:** Because `C:\Users\Prekzursil` is the workspace root, Cursor loads `~/.cursor/mcp.json` twice (once as the global config, once as the project config). This duplicates MCP servers and skills, wasting RAM and confusing server state.

### Options

1. **Migrate to a Dedicated Workspace Root (Recommended)**
   * **Description:** Create a small, dedicated folder (e.g., `C:\Users\Prekzursil\workspace` or `C:\Users\Prekzursil\projects`) to serve as the default Cursor workspace.
   * **Tradeoffs:** Solves the double-loading issue cleanly. Requires the user to change their habit of opening the home directory.
   * **Value x Effort:** High value, low effort (mostly behavioral change).
   * **Reversibility:** Easily reversible by opening the home directory again.
   * **Migration Cost/Risk:** Low risk, but requires updating any scripts or shortcuts that launch Cursor in the home directory.
   * **Dissent (Pragmatist):** "Users hate changing their habits. If they are used to having their entire home directory available in the file explorer, this will feel like a downgrade."

2. **Remove Global MCP Config and Rely Only on Project Config**
   * **Description:** Delete `~/.cursor/mcp.json` and rely solely on the project-level `.cursor/mcp.json` within the home directory workspace.
   * **Tradeoffs:** Fixes the duplication, but breaks MCP availability if the user ever opens a different folder as a workspace.
   * **Value x Effort:** Medium value, very low effort.
   * **Reversibility:** Reversible by restoring the global config file.
   * **Migration Cost/Risk:** High risk of breaking MCPs in other projects.
   * **Dissent (Architect):** "This is a fragile hack. It relies on the user *never* opening a subfolder as a workspace, which defeats the purpose of project-level configs."

3. **Symlink/Junction Reorg (Creative)**
   * **Description:** Create a dedicated workspace folder (e.g., `C:\Users\Prekzursil\CursorWorkspace`) and use NTFS junctions (`mklink /J`) to link specific important folders (like `source`, `Documents`, `Desktop`) into it. Open this folder in Cursor.
   * **Tradeoffs:** Keeps the workspace root separate from the home directory (fixing the MCP bug) while still providing easy access to necessary files.
   * **Value x Effort:** High value, medium effort (requires initial setup of junctions).
   * **Reversibility:** Reversible by deleting the workspace folder and junctions.
   * **Migration Cost/Risk:** Low risk. Junctions are transparent to most tools.
   * **Dissent (Security):** "Junctions can sometimes confuse backup tools or recursive searches if not handled carefully, potentially leading to infinite loops or duplicated backups."

### Recommended Pick
**Migrate to a Dedicated Workspace Root.** It's the cleanest solution that aligns with Cursor's intended design. The Symlink/Junction approach is a strong alternative if the user insists on having home directory content immediately visible.

---

## Issue 5: basic-memory daemon flaps under RAM pressure

**Problem:** The `basic-memory` daemon crash-loops when memory is tight (~1.8 GB free). The watchdog kills it during slow warm-ups, and large embedding operations (like a 1,482-chunk entity) cause OOMs or stalls.

### Options

1. **Disable Vector Sync / Reranker (Recommended)**
   * **Description:** Set `BASIC_MEMORY_SEMANTIC_SEARCH_ENABLED=false` and `BASIC_MEMORY_RERANKER_ENABLED=false` in the environment.
   * **Tradeoffs:** Drastically reduces memory usage and CPU load by skipping embedding generation and cross-encoder reranking. Sacrifices semantic search capabilities (falling back to keyword/FTS search).
   * **Value x Effort:** High value (stability), very low effort.
   * **Reversibility:** Easily reversible by flipping the environment variables back.
   * **Migration Cost/Risk:** Low risk. The database remains intact, just without updated vectors.
   * **Dissent (Critic):** "Semantic search is a core feature of basic-memory. Disabling it neuters the tool. We should fix the resource usage, not turn off the features."

2. **Cap Process Working Set via Windows Job Objects**
   * **Description:** Wrap the `basic-memory` daemon launch in a tool (like `jobrun` or a custom script) that assigns it to a Windows Job Object with a strict `ProcessMemoryLimit` or `JobMemoryLimit`.
   * **Tradeoffs:** Enforces a hard RAM cap, preventing `basic-memory` from taking down other processes. However, if the daemon hits the cap during a legitimate large operation, it will crash (though the watchdog will restart it).
   * **Value x Effort:** High value, medium effort (requires setting up the job object wrapper).
   * **Reversibility:** Reversible by removing the wrapper.
   * **Migration Cost/Risk:** Medium risk. Might lead to more frequent, but contained, crashes if the limit is set too low.
   * **Dissent (Pragmatist):** "A hard cap just changes the failure mode from 'system bogs down' to 'daemon crashes instantly'. It doesn't solve the underlying inefficiency of the embedding process."

3. **Offload to a Dedicated Tiny VM / WSL with cgroups (Creative)**
   * **Description:** Move the `basic-memory` daemon (and potentially its SQLite DB) to a lightweight WSL2 instance or a small, always-on VM (like a Raspberry Pi), using Linux `cgroups` to strictly limit its memory.
   * **Tradeoffs:** Completely isolates the memory pressure from the main Windows host. Violates the "no new always-on daemon / RAM" lock if run locally, but perfectly valid if moved to external hardware.
   * **Value x Effort:** High value (total isolation), high effort.
   * **Reversibility:** Harder to reverse; requires moving the DB and config back.
   * **Migration Cost/Risk:** High risk. Introduces network latency and complexity.
   * **Dissent (Chief-of-Staff):** "Violates standing orders against new always-on daemons if done locally. If done externally, it breaks the 'local-first, plain text on your disk' ethos of basic-memory."

### Recommended Pick
**Disable Vector Sync / Reranker.** Given the chronic memory pressure (~1.8 GB free), running local embeddings and cross-encoders is simply too heavy for this machine. Falling back to FTS (Full Text Search) ensures stability, which is the user's top priority ("Memory can be lost without notice — this is the user's stated top fear").

---

## Creative Options & Cross-Cluster Interactions

*   **Creative Escalation:** The **Symlink/Junction Reorg** for the workspace is the most elegant way to satisfy the user's desire to see their home directory without triggering Cursor's double-loading bug.
*   **Cluster A Interaction:** If Cluster A implements a **RAM admission controller**, it could intercept large `basic-memory` embedding tasks and queue them until memory frees up, rather than letting them crash the daemon. This would allow keeping semantic search enabled while preventing OOMs.
*   **Cluster C Interaction:** The fix for Issue 4 (moving the workspace root) will require Cluster C's drift-check to update its assertions about where `mcp.json` lives and how it's loaded.

## Challenges to Standing Decisions
*   **CHALLENGES STANDING DECISION:** The recommendation to disable vector sync challenges the assumption that `basic-memory` must provide semantic search. However, on a chronically memory-pressured machine, stability must trump advanced features.
*   **CHALLENGES STANDING DECISION:** If the WSL/VM offload option is considered, it challenges the "no new always-on daemon" rule, arguing that an isolated daemon is better than a crashing local one.