# Policy YAML Plan

Date: 2026-05-21 JST

## Objective

Move policy configuration into repository-owned YAML files while keeping the Python policy engine deterministic and dependency-free.

## Steps

1. Add `rules/global/command-policy.yaml` and `phase-policy.yaml`.
2. Implement a small YAML subset loader for simple mappings/lists.
3. Let `PolicyEngine` load policy files from the control repo when present.
4. Keep code defaults as fallback.
5. Add tests proving YAML overrides command and phase behavior.
6. Run verification and commit.

## Acceptance Criteria

- Forbidden commands can be loaded from `rules/global/command-policy.yaml`.
- Phase write allow/deny patterns can be loaded from `rules/global/phase-policy.yaml`.
- Existing tests still pass without external YAML parser dependencies.
