import json, sys
sys.stdin.read()
print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "RES-0009-INJECTED-CONTEXT"}}))
