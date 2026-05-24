# Profile Commands Plan

Date: 2026-05-25 JST

## Objective

Implement the v0.4 profile command surface:

- `agent-careflow profile validate <name>`
- `agent-careflow profile render <name> --target <dir>`
- `agent-careflow install --profile <name> --enable/--disable <tool>`

## Acceptance Criteria

- Profile validation rejects unknown or empty profiles.
- Render writes only selected tool configuration files under the requested target directory.
- Install writes a local manifest and rendered configs, with explicit enable/disable overrides.
- Tests pass without writing to the user's home directory.
