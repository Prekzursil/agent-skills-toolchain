# RETIRE-bound pre-tool hook candidate

## DEFINE `orphan.hook-pre-tool`
orphan.hook-pre-tool is a workflow mechanism: a named pre-tool hook stage that runs before every tool invocation and may abort the call. Discriminating example: a deny from this hook prevents the tool from running, unlike a post-tool tracer which can only observe.

This candidate also lists `shared.handoff-token` as a mechanism it uses. That token is not unique to this RETIRE record.
