# Schema Runtime Validation Plan

Date: 2026-05-21 JST

## Objective

Wire the concrete JSON Schema files into runtime artifact validation without adding third-party dependencies.

## Steps

1. Add a lightweight schema subset validator for required/type/enum/const/pattern.
2. Apply schema validation inside artifact validators after parsing front matter.
3. Add tests proving schema files influence validation failures.
4. Run verification and commit.

## Acceptance Criteria

- Invalid enum values fail through schema validation.
- Missing required fields still fail with useful errors.
- Existing artifact validators and CLI checks continue to pass.
