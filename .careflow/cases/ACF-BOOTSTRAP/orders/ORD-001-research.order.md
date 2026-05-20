# ORDER: ORD-001-research

order_id: ORD-001-research
case_id: ACF-BOOTSTRAP
assigned_role: researcher
plan_path: .careflow/cases/ACF-BOOTSTRAP/PLAN.md
plan_hash: sha256:a75d82932dddf724a619acc366e36450ad737d6dd39384a55f6fe1e7894981c6
allowed_actions:
  - read planning files
  - write research report stubs
  - write source registry
forbidden_actions:
  - edit implementation code before bootstrap artifacts exist
  - treat community posts as authoritative
deliverables:
  - research/README.md
  - research/R-001-medical-workflow-patterns.md
  - research/R-002-takt-and-oss-agent-orchestration.md
  - research/R-003-codex-official-surface-2026.md
  - research/R-004-claude-code-official-surface-2026.md
  - research/R-005-cursor-composer-agent-surface-2026.md
  - research/R-006-community-practice-signals-2026.md
  - research/R-007-security-governance-policy.md
expected_result_path: .careflow/cases/ACF-BOOTSTRAP/results/ORD-001-research.result.md
completion_criteria:
  - required report files exist
  - report sections are present
  - source authority levels are explicit

## Situation

The repository is empty except for planning documents. Research structure must be created before implementation code.

## Background

The implementation plan identifies seven required research reports and a source authority model.

## Assessment

Milestone 0 can proceed with draft report stubs and an initial registry from the planning document.

## Recommendation

Create report stubs, source registry validation, and keep all reports in draft until sources are reviewed in detail.
