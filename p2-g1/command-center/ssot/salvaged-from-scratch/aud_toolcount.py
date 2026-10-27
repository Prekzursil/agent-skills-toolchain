import json
import pathlib

BASE = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate/command-center/mcp-audit")
rows = json.loads((BASE / "disposition.json").read_text(encoding="utf-8"))["rows"]

# Tool names transcribed from THIS auditor session's deferred-tool listing (the harness'
# own inventory).  Mechanically independent of the lane's stdio handshake: the lane counted
# tools by spawning a stdio child and reading tools/list; this counts what the Claude
# harness actually exposed to me.  Two different producers, same quantity.
SESSION = {
    "context7": ["query-docs", "resolve-library-id"],
    "claude-code-mcp": ["claude_code"],
    "codex": ["codex", "codex-reply"],
    "qlty": ["qlty_check", "qlty_coverage_transform", "qlty_metrics", "qlty_smells",
             "qlty_status"],
    "repomix": ["attach_packed_output", "file_system_read_directory",
                "file_system_read_file", "generate_skill", "grep_repomix_output",
                "pack_codebase", "pack_remote_repository", "read_repomix_output"],
    "angr": ["close_project", "decompile_function", "find_functions_by_pattern",
             "get_basic_blocks", "get_callgraph", "get_cfg", "get_exports",
             "get_function_info", "get_imports", "get_strings", "get_xrefs",
             "list_functions", "list_projects", "load_binary"],
    "frida-mcp": ["attach_to_process", "create_interactive_session", "create_simple_hook",
                  "enumerate_devices", "enumerate_processes", "execute_in_session",
                  "get_device", "get_process_by_name", "get_usb_device", "kill_process",
                  "list_processes", "resume_process", "spawn_process"],
    "scholarly-access": ["paper_access_status", "paper_batch_resolve",
                         "paper_citation_graph", "paper_download_oa_pdf",
                         "paper_fetch_metadata", "paper_find_oa_pdf", "paper_resolve",
                         "paper_summarize"],
    "searxng": ["searxng_instance_info", "searxng_search_suggestions",
                "searxng_web_search", "web_url_read"],
    "playwright": ["browser_click", "browser_close", "browser_console_messages",
                   "browser_drag", "browser_drop", "browser_evaluate",
                   "browser_file_upload", "browser_fill_form", "browser_find",
                   "browser_handle_dialog", "browser_hover", "browser_navigate",
                   "browser_navigate_back", "browser_network_request",
                   "browser_network_requests", "browser_press_key", "browser_resize",
                   "browser_run_code_unsafe", "browser_select_option", "browser_snapshot",
                   "browser_tabs", "browser_take_screenshot", "browser_type",
                   "browser_wait_for"],
    "chrome-devtools": ["click", "close_page", "drag", "emulate", "evaluate_script",
                        "fill", "fill_form", "get_console_message", "get_network_request",
                        "handle_dialog", "hover", "lighthouse_audit",
                        "list_console_messages", "list_network_requests", "list_pages",
                        "navigate_page", "new_page", "performance_analyze_insight",
                        "performance_start_trace", "performance_stop_trace", "press_key",
                        "resize_page", "select_page", "take_memory_snapshot",
                        "take_screenshot", "take_snapshot", "type_text", "upload_file",
                        "wait_for"],
}

by = {r["name"]: r for r in rows}
agree = dis = 0
print(f"{'server':20} {'lane tool_count':>15} {'my session':>11}  verdict")
for name, tools in sorted(SESSION.items()):
    lane = by[name].get("tool_count")
    mine = len(tools)
    ok = lane == mine
    agree += ok
    dis += (not ok)
    print(f"{name:20} {str(lane):>15} {mine:>11}  {'AGREE' if ok else 'DISAGREE'}")
print()
print(f"agree={agree} disagree={dis} of {len(SESSION)} cross-checked")

# CONTROL: the detector must be able to disagree.  Perturb one count and confirm it flags.
probe = dict(SESSION)
probe["context7"] = ["query-docs"]  # deliberately wrong (1 instead of 2)
ctl = [n for n, t in probe.items() if by[n].get("tool_count") != len(t)]
print(f"CONTROL (context7 count deliberately wrong) -> flagged: {ctl} "
      f"=> detector can disagree: {ctl == ['context7']}")
