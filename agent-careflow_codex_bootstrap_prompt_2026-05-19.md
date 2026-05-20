# Codex Bootstrap Prompt for agent-careflow

Repository name: agent-careflow

You are implementing agent-careflow, a central control repository for AI coding-agent workflows.

Core idea:
- agent-careflow contains all static rules, settings, schemas, templates, hooks, skills, subagent definitions, profiles, and deployment scripts.
- target repositories contain runtime case artifacts only under .careflow/.
- PLAN.md is the case-level plan.
- ORDER files are separate immutable instructions to subagents.
- Every subagent must receive both plan_path and order_path.
- Hooks and CLI validators enforce phase constraints deterministically.
- Tool-specific configs for Codex, Claude Code, and Cursor are thin adapters.
- Core policy logic must live in the agent-careflow CLI, not in model prompts.

Before implementation:
1. Create .careflow/cases/ACF-BOOTSTRAP/CASE.yaml.
2. Create .careflow/cases/ACF-BOOTSTRAP/PLAN.md.
3. Create .careflow/cases/ACF-BOOTSTRAP/orders/ORD-001-research.order.md.
4. Create research report stubs under research/.
5. Fill an initial source registry from official docs and existing OSS references.
6. Do not implement code before the research scaffold and PLAN are written.

First milestone:
Build Milestone 0 and Milestone 1 only.

Deliver:
- repository layout
- Python package named agent_careflow
- CLI command named agent-careflow
- schemas and templates
- research scaffold and validation
- case creation
- plan validation
- order validation
- discharge validation
- tests
- README explaining the workflow

Use subagents only for bounded review tasks:
- one research reviewer for healthcare workflow mapping
- one research reviewer for TAKT / OSS workflow comparison
- one technical reviewer for Codex / Claude / Cursor adapter assumptions

Each subagent must receive:
- plan_path
- order_path
- expected result_path

Wait for all subagent results, summarize disagreements, and create a conference note before finalizing.

Non-negotiable constraints:
- Do not add implementation code until research scaffold and bootstrap PLAN/ORDER exist.
- Do not embed policy logic separately in Codex/Claude/Cursor configs.
- Do not make Claude required for private profile.
- Do not treat community posts as authoritative; use them only as risk/test signals.
- Use .careflow/ as the runtime directory in target repos.
