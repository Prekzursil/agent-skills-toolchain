# Feature inventory at HEAD f88b120 (replaces the failed simplification lens; input to the core split)

## Lines per file
```
  5276 total
  1158 app.py
   719 openai_protocol.py
   615 file_bench.py
   600 agent_tools.py
   483 web_tools.py
   226 tests/test_openai_protocol.py
   209 maintenance/update_deps_and_deploy.py
   201 tool_parse.py
   188 tests/test_web_tools.py
   164 tests/test_file_bench.py
   145 tests/test_vision_protocol.py
   123 tests/test_personas.py
   103 tests/test_tool_parse.py
   101 system_prompt.py
    85 openai_api.py
    65 maintenance/watch.py
    52 deploy_space.py
    39 maintenance/keepalive.py
     0 tests/__init__.py
```

## app.py top-level definitions (line: name)
```
36:MODEL_ID = "heretic-org/Qwen3.8-27B-heretic-ara"
37:DRAFT_ID = "Qwen/Qwen3.5-2B"  # speculative-decoding draft (same qwen3_5 family)
41:MODEL_PATH = "/models/qwen38-heretic-nf4"   # prequant mount (fast boot) — once exported
42:MODEL_FALLBACK_PATH = "/models/qwen38-heretic"  # bf16 mount (quantize at load)
43:DRAFT_PATH = "/models/qwen35-2b"
46:def _model_source() -> str:
54:def _log_mount_state() -> None:
70:def _draft_source() -> str:
77:DURATION_CAP = 600
78:TOK_PER_SEC = 22.0  # conservative 27B NF4 decode (Blackwell large runs faster)
79:STREAMER_TIMEOUT = 180.0  # unblock the consumer if the generate thread dies
80:MAX_TOOL_ROUNDS = 8
90:def _load_target():
133:IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
134:VID_EXT = {".mp4", ".webm", ".mkv", ".mov", ".avi"}
135:MAX_API_IMAGES = 4
136:MAX_IMAGE_BYTES = 10_000_000
162:def _spec_available() -> bool:
166:def _token_count(text: str) -> int:
179:EFFORTS = ("low", "medium", "xhigh")
192:def _wait_models() -> None:
201:def _upload_nf4_async(out: str) -> None:
224:def _maybe_nf4_export_inline() -> None:
264:def _as_messages(history) -> list[dict]:
306:def _user_text(message) -> str:
321:def _estimate(*args, msgs=None, think=False, max_new_tokens=4096, images=None, videos=None, **kwargs) -> i
342:def _encode_messages(
389:def _generate_kwargs(encoded, streamer, assistant=None, **kw):
426:def _gpu_impl(
517:@spaces.GPU(duration=_estimate)
518:def _gpu_large(**kw):
522:@spaces.GPU(size="xlarge", duration=_estimate)
523:def _gpu_xlarge(**kw):
527:def _gpu_generate(gpu_size="large", **kw):
532:def api_generate(
582:def _bench_for(request) -> FileBench:
591:def _state_for(request) -> dict:
600:def _execute_tool(
610:def _tool_preview(call: ParsedToolCall) -> str:
620:def _render(think_text: str, visible: str, tool_msgs: list[dict] | None = None):
636:def chat(
826:CSS = """
831:PRESETS = {
907:def _apply_preset(name):
925:def _persona_prompt_text(label):
1053:_ADDL = [
1075:def _example_row(
1103:demo = gr.ChatInterface(
```
