# agent-careflow Design Philosophy

## Purpose

`agent-careflow` is a control repository for engineers who use AI coding agents such as Codex, Claude Code, and Cursor. It is not a replacement agent and it is not a clinical system.

The project deliberately imports mature workflow-control patterns from healthcare operations into software engineering work with AI coding agents. The transferable ideas are planning discipline, bounded orders, handoff quality, evidence requirements, incident handling, multidisciplinary review, and explicit closure.

## Central Thesis

AI coding agents should not be governed only by prompts or chat memory. They should operate inside a recorded, inspectable workflow where every actor can see:

- what the task is
- what the current plan says
- what order was given to the current agent
- what scope is allowed
- what evidence is required
- what incidents occurred
- what review decisions were made
- why the task is safe to close

The formal state is the artifact set, not the chat transcript.

## Healthcare Pattern, Engineering Target

The healthcare analogy is a governance model, not a domain target.

| Healthcare workflow pattern | agent-careflow adaptation |
|---|---|
| case / patient chart | coding task case directory |
| care plan | `PLAN.md` |
| clinical order | bounded `orders/*.order.md` for one agent role |
| handoff | `results/*.result.md` and expected result paths |
| evidence and observations | test, lint, diff, and runtime evidence files |
| incident report | policy deviation, scope drift, unsafe command, failed verification |
| review / conference | review artifact and phase transition decision |
| discharge | final closure check, PR-ready summary, archive readiness |

The system does not perform clinical reasoning. It uses healthcare operations as a source of disciplined process design.

## Core Model

A development task is a `Case`.

```text
.careflow/cases/<case_id>/
  CASE.yaml
  PLAN.md
  PLAN.lock.json
  orders/
  results/
  evidence/
  incidents/
  reviews/
  conferences/
  DISCHARGE.md
```

The central repository owns static controls:

```text
agent-careflow/
  schemas/
  templates/
  rules/
  profiles/
  hooks/
  research/
  src/agent_careflow/
```

Target repositories own runtime artifacts only under `.careflow/`.

## PLAN / ORDER Separation

`PLAN.md` is case-level intent. It contains objective, non-goals, acceptance criteria, risk class, allowed scope, phase plan, evidence requirements, rollback plan, and unresolved questions.

`ORDER.md` is a bounded instruction to an agent role. It contains assigned role, `plan_path`, `plan_hash`, allowed actions, forbidden actions, deliverables, `expected_result_path`, and completion criteria.

This separation prevents a subagent from receiving a vague task like "fix this". Every subagent should receive both:

- `plan_path`
- `order_path`

And every order should point to an expected result file.

## Deterministic Gates Over Self-Report

The design does not rely on an LLM saying it followed the plan. It uses deterministic checks:

- `PLAN.lock.json` binds work to a specific plan hash
- ORDER validation rejects stale plan hashes
- policy checks deny disallowed commands and file writes
- hooks route tool events through the shared policy engine
- prompt guards block likely secret or PHI-like input before agent context entry
- discharge/close validation requires evidence and no open incidents
- `doctor` checks repository health in one command

Prompts can guide behavior, but artifacts and validators decide state.

## Risk Class

Ceremony scales with risk.

| Class | Meaning | Expected control level |
|---|---|---|
| C0 | no-change question or small investigation | case-lite |
| C1 | small low-risk change | plan-lite, order, evidence |
| C2 | normal feature or bugfix | full plan, order, verification, review as needed |
| C3 | auth, payment, data, security, migration | research, review, rollback, conference |
| C4 | release, destructive, irreversible | C3 plus explicit human signoff |

The point is not bureaucracy. The point is proportional control.

## Tool Adapter Principle

Codex, Claude Code, Cursor, and future tools are adapters. Policy logic must not be duplicated inside tool-specific config files. Tool-specific hooks should call the shared `agent-careflow` CLI, and the CLI should make the decision.

## Careflow Protocol and Adapter Conformance

The core protocol normalizes runtime-shaped input into a careflow event, runs shared policy, and returns a `Decision`. Runtime adapters are intentionally thin: they render that decision into the JSON shape expected by Codex, Claude, Cursor, or another tool.

Adapter conformance verifies that boundary with fixture replay:

- fixture input is parsed as runtime-shaped JSON
- the input is normalized into a careflow event
- shared policy returns the decision
- the selected adapter renders valid runtime-specific JSON
- the result is recorded as `agent-careflow.adapter_conformance.v1` JSONL

Live runtime execution is compatibility evidence, not a required condition for core correctness. If a local Codex, Claude, or Cursor installation is unavailable or behaves differently, that observation belongs in evidence notes without blocking protocol conformance.

## Incident Philosophy

An incident is not only a production outage. In AI-agent work, incidents include:

- writing outside ordered scope
- running a forbidden command
- proceeding with a stale plan
- missing required evidence
- failing verification after claiming success
- leaking secrets or PHI-like identifiers into prompt context

Incidents are learning artifacts. They should create correction and review, not disappear into chat history.

## Closure Philosophy

A case is not done because an agent says it is done. It is done when closure criteria pass:

- expected results exist
- required evidence exists
- reviews are complete for the risk class
- no blocking incident is open
- discharge/close validation passes

`DISCHARGE.md` keeps the careflow metaphor. `close validate` exists as a technical alias for users who prefer engineering language.

## Supporting Mechanisms

The following features support the core model but are not the model itself:

- hook adapters
- prompt guard
- adapter conformance fixture replay
- TAKT comparison
- isolation planning
- profile bootstrap
- doctor

They should stay subordinate to the lifecycle: Case, PLAN, ORDER, RESULT, EVIDENCE, INCIDENT, REVIEW, CONFERENCE, DISCHARGE.
