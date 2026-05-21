# Prompt Guard Plan

Date: 2026-05-21 JST

## Objective

Add a UserPromptSubmit guard that detects likely secrets or PHI-like identifiers before they enter AI coding-agent context.

## Scope

- Deterministic regex checks only.
- No clinical interpretation.
- Return hook warning/deny JSON through existing hook adapter path.

## Acceptance Criteria

- Prompt text containing obvious API keys or SSN-like values is denied.
- Benign engineering prompts are allowed.
- Codex UserPromptSubmit hook command is available.
- Tests pass and docs explain the guard as an AI coding-agent input safety control.
