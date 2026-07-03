"""E2EE DM backends for the T4 fb_dm_* tools.

  * fbchat_v2_backend.FbchatV2Backend - default; wraps the pip `fbchat-v2`
    library, which spawns a compiled mautrix/meta Go bridge (AGPL-3.0) and
    talks to it over stdio JSON-RPC. Authenticates with facebook.com cookies.
"""
