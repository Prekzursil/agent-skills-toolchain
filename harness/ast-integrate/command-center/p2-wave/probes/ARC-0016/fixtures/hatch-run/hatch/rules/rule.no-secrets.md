<!-- a2-generated registry_id=rule.no-secrets artifact_class=rule_deployment generator_id=a2-ssot-generator generator_version=1.0.0 registry_entry_sha256=5ff8a00e935b8ac847927bec60ea30404aef50a7f40411b2520c35f68629c0cd schema=a2-registry/v1 -->
# No secrets in generated artifacts

Generated files must not embed API keys, tokens, or credentials. Fail closed if a registry field matches a secret pattern.
