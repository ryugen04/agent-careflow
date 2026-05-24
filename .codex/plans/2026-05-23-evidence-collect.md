# Evidence Collect Plan

Date: 2026-05-23 JST

## Objective

Complete the remaining v0.2 CLI surface for local evidence capture:

- add `agent-careflow evidence collect --case <case_id> --kind git-status`
- write deterministic evidence files under the case evidence directory
- keep collection local and non-destructive

## Acceptance Criteria

- `git-status` evidence records `git status --short` output for the current repository.
- Missing cases and unsupported evidence kinds fail with useful errors.
- Focused tests and the full test suite pass.
