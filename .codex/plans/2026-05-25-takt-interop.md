# TAKT Interop Plan

Date: 2026-05-25 JST

## Objective

Complete the TAKT backlog commands without adding TAKT as a dependency:

- `agent-careflow takt import-workflow` converts a TAKT-style workflow into an agent-careflow import report
- `agent-careflow takt export-policy` emits a TAKT-oriented policy summary from repository policy files

## Acceptance Criteria

- Import output maps recognized workflow concepts to PLAN/ORDER/POLICY/RESULT surfaces.
- Export output includes command and phase policy source files when present.
- Both commands support writing to an output file.
- Tests pass.
