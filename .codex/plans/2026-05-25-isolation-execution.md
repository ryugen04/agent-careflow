# Isolation Execution Plan

Date: 2026-05-25 JST

## Objective

Move isolation beyond plan-only while keeping destructive cleanup guarded:

- create worktree, shared-clone, and temp-clone work directories
- write an isolation marker into created directories
- cleanup only directories that carry a matching marker
- export patches from an isolation work directory without mutating the target repo

## Acceptance Criteria

- Worktree creation uses `git worktree add --detach`.
- Clone cleanup refuses to remove unmarked directories.
- Patch export records `git diff` output.
- CLI exposes `isolation create`, `isolation cleanup`, and `isolation export-patch`.
- Tests pass.
