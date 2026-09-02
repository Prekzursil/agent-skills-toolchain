# 03-PLUGIN-LIFECYCLE-MAP.md

## Table of contents

- Plugin enablement is a state machine

## Plugin enablement is a state machine

Plugin lifecycle is a named state machine from install through enable, disable and uninstall, not a boolean flag CONFIRMED.

Allowed tags are CONFIRMED, REFUTED, PARTIAL, NOT-CHECKED.
