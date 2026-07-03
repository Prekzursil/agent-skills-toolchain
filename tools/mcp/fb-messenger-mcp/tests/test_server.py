"""Server wiring: original tools preserved + full expanded tool set present."""
from __future__ import annotations

ORIGINAL_5 = {"whoami", "list_threads", "read_thread", "search_messages", "thread_info"}

T3_SEND = {
    "fb_send_message", "fb_send_file", "fb_react_to_message", "fb_unsend_message",
    "fb_forward_message", "fb_mark_read", "fb_send_typing", "fb_create_group",
}

T1_GRAPH = {
    "fb_graph_token_info", "fb_page_post", "fb_page_schedule_post",
    "fb_page_upload_photo", "fb_page_upload_video", "fb_page_upload_reel",
    "fb_page_upload_story", "fb_page_read_posts", "fb_page_read_comments",
    "fb_page_moderate", "fb_page_insights", "fb_page_message",
    "ig_graph_publish", "ig_graph_insights", "ig_graph_moderate_comments",
}

T4_DM = {"fb_dm_status", "fb_dm_list", "fb_dm_read", "fb_dm_send", "fb_dm_react"}


def _names(mcp_server):
    return {t.name for t in mcp_server._tool_manager.list_tools()}


def test_original_five_preserved(mcp_server):
    assert ORIGINAL_5 <= _names(mcp_server)


def test_all_tiers_registered(mcp_server):
    names = _names(mcp_server)
    for expected in (T3_SEND, T1_GRAPH, T4_DM):
        assert expected <= names, sorted(expected - names)


def test_no_duplicate_or_missing(mcp_server):
    names = _names(mcp_server)
    assert names == ORIGINAL_5 | T3_SEND | T1_GRAPH | T4_DM


def test_tool_names_are_clean(mcp_server):
    # keep names snake_case + original (they will sit behind the social-hub).
    for name in _names(mcp_server):
        assert name == name.lower()
        assert " " not in name and "-" not in name
