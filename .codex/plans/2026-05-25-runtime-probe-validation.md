# Runtime Probe Validation Plan

Date: 2026-05-25 JST

## Objective

Strengthen live runtime fixture handling despite external tool availability constraints:

- validate captured runtime probe JSONL files
- expose probe validation through the CLI
- record current local tool availability for Codex, Claude, and Cursor

## Acceptance Criteria

- Invalid probe records fail with useful errors.
- Existing `.codex/probes/**/runtime-probe.jsonl` files can be validated.
- Evidence documents which vendor CLIs are locally available and which still require external setup.
