# Hook Events and Incidents Plan

Date: 2026-05-25 JST

## Objective

Complete the remaining v0.3 hook surface without adding unsafe hook behavior:

- add Stop commands for Codex, Claude, and Cursor
- add Claude subagent-start and subagent-stop commands
- add an opt-in path for hooks to create incidents when policy denies a tool action
- keep Stop stdout JSON-only and avoid PostToolUse undo semantics

## Hook Event Matrix

| Event | Matcher target | Input keys used | Valid stdout | Blocks/continues | Fail behavior | agent-careflow use | Probe required |
|---|---|---|---|---|---|---|---|
| Codex Stop | ignored | hook_event_name, cwd, last_assistant_message | JSON only | continue unless explicit block | fail open to no-op JSON | final checkpoint placeholder | yes before production enforcement |
| Claude Stop | tool-specific | hook_event_name, cwd | JSON object | continue | fail open to no-op JSON | final checkpoint placeholder | yes before production enforcement |
| Cursor Stop | tool-specific | hook_event_name, cwd | JSON object | continue | fail open to allow JSON | final checkpoint placeholder | yes before production enforcement |
| Claude SubagentStart | tool-specific | hook_event_name, cwd | JSON object | continue | fail open to no-op JSON | subagent lifecycle marker placeholder | yes before production enforcement |
| Claude SubagentStop | tool-specific | hook_event_name, cwd | JSON object | continue | fail open to no-op JSON | subagent lifecycle marker placeholder | yes before production enforcement |
| PreToolUse incident | tool name | cwd, case_id, tool_input | event-specific deny JSON | can block | deny remains deny, incident best-effort | create incident on deny when requested | covered by fixture and local test |

## Acceptance Criteria

- CLI exposes the planned v0.3 stop/subagent commands.
- Codex Stop emits JSON and no plain stdout.
- Hook incident creation is opt-in and never downgrades a deny decision.
- Tests pass.
