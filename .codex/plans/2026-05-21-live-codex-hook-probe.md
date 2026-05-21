# Live Codex Hook Probe Plan

Date: 2026-05-21 JST

## Objective

Capture live Codex hook payloads from a controlled temporary repository and compare them with current adapter assumptions.

## Steps

1. Create a temporary repo with `.codex/hooks.json` pointing to `agent-careflow hook capture`.
2. Run a minimal `codex exec` prompt that should exercise command/tool hooks.
3. Validate the captured JSONL with the runtime probe validator.
4. Promote useful observed payloads to fixtures or research notes.
5. Run tests and commit.

## Safety

- Use a temporary directory under `/tmp`.
- Hook command only appends JSONL; it does not enforce policy or mutate source files.
- Do not run destructive shell commands in the prompt.
