# GLM 5.3 token bundle connectivity verification

Date: 10.09.2026
Provenance: disk-verified
Result: SUCCESS for basic Model API text generation; Coding Plan remains quota-blocked.

The user supplied a screenshot of an active, paid Usage Bundle with a displayed balance of 20,000,000 tokens and asked to retest after purchase. Z.AI identifies Usage Bundles as Model API token packages. Its official ZCode documentation distinguishes the Model API route for resource packages/prepaid balance from the separate Coding Plan route.

## Live checks

Coding Plan retest at 2026-09-10T12:59:02.2543264Z:
- Endpoint: https://api.z.ai/api/coding/paas/v4/chat/completions
- Requested model: glm-5.3
- Result: HTTP 429, error 1310
- Provider message: Weekly/Monthly Limit Exhausted. Your limit will reset at 2026-09-13 01:52:26
- No generated response.

Model API test at 2026-09-10T12:59:38.2829070Z:
- Endpoint: https://api.z.ai/api/paas/v4/chat/completions
- Requested and returned model: glm-5.3
- Result: HTTP 200
- Exact generated text: GLM53_BUNDLE_OK:5
- Finish reason: stop
- Request ID: 2026091020593931f6a104925947f1
- Usage reported by service: 41 prompt tokens, 25 completion tokens, 66 total tokens.
- Completion includes 15 reasoning tokens.
- Elapsed time: 3.63 seconds.
- Test prompt was a harmless arithmetic coding check.
- No tools were sent.
- Output cap was 1024 tokens.
- Authentication reused the existing ZAI_API_KEY environment binding without displaying or changing the credential.

## Scope and billing precision

The successful response verifies basic GLM 5.3 inference through the route documented for Model API token packages. The individual bundle's before/after balance was not queried, so this receipt does not assert an exact bundle deduction or rule out any account-specific billing priority.

This was a direct provider connectivity test. CyberStrike's autonomous workflow was not launched or modified. CyberStrike's existing defaults remain GPT-6 Astra and Daybreak; its existing zai provider still points to the Coding Plan endpoint.

Live configuration SHA256 before and after:
83744CF475451EBF125B8B30197FC019D1AFDC4EF4B574CD401BB4C205B648B9

## Artifacts and sources

- coding-plan-retest.json: sanitized Coding Plan result, parsed and re-read.
- model-api-bundle-test.json: sanitized successful Model API result, parsed and re-read.
- https://z.ai/model-api
- https://zcode.z.ai/en/docs/configuration
- https://docs.z.ai/guides/llm/glm-5.3

UNIT-COMPLETE: check-glm53-token-bundle