# rule.no-secrets

Generated and runtime artifacts must not embed API keys, tokens, or
credentials. Fail closed if a field matches a secret pattern.

This rule body is loaded into the session rule table on activate and
removed on deactivate (unload-rule-table). It is not always-on context.

Padding for a measurable byte cost:
NO-SECRETS-RULE-BODY-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ
NO-SECRETS-RULE-BODY-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ
NO-SECRETS-RULE-BODY-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ
NO-SECRETS-RULE-BODY-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ
