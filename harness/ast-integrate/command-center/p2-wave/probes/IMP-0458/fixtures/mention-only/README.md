# Mention-only control (must NOT fire)

This document names credential variables without containing a value:

- GITHUB_TOKEN
- GH_TOKEN
- AWS_SECRET_ACCESS_KEY
- AWS_ACCESS_KEY_ID
- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- CURSOR_API_KEY
- API_KEY
- SECRET_KEY
- PRIVATE_KEY
- DATABASE_PASSWORD
- NPM_TOKEN

The secret-scrub gate must name the variable, the scope and the evidence.
It must never rotate, revoke or unset any credential. Rotation is the
owner's action. A zero-entropy prefix is acceptable; a secret body is not.

Export GITHUB_TOKEN from the environment. Do not write AWS_SECRET_ACCESS_KEY
into a receipt. Set CURSOR_API_KEY=$CURSOR_API_KEY in the shell that already
holds it. Placeholder values such as REDACTED, changeme, YOUR_TOKEN_HERE
and ${GITHUB_TOKEN} are mentions, not credentials.
