# ORD-007 Codex Hook Event Matrix

case_id: ACF-RELIABILITY-SUPERPOWERS
order_id: ORD-007
status: active
basis: official Codex hooks docs, OpenAI Codex schema source, local runtime probe plan

## Sources Checked

- OpenAI Codex hooks docs: `https://developers.openai.com/codex/hooks`
- OpenAI Codex config reference: `https://developers.openai.com/codex/config-reference`
- OpenAI Codex hook schema source: `https://github.com/openai/codex/blob/main/codex-rs/hooks/src/schema.rs`
- Local skill references: `codex-hooks-authoring` and `codex-runtime-probing`

## Matrix

| Event | Official trigger | Matcher target | Input keys relied on | Valid stdout used by agent-careflow | Blocks/continues | Fail behavior risk | Careflow use | Must hit | Must not hit | Probe required | ORD-007 action |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SessionStart | Startup, resume, clear, compact | `source` | common fields, `source` | JSON additional context or plain context | Continues only | Bad context fails open into weak guidance | Inject `using-agent-careflow` and fixed labels | Startup/resume before planning or work | File/path permission decisions | Yes | Capture alongside UserPromptSubmit to prove hook source loads |
| UserPromptSubmit | Before user prompt is sent | ignored | common fields, `turn_id`, `prompt` | JSON context or block decision | Can block prompt | Missing event means prompt guard cannot be runtime-guaranteed for that surface | Prompt guard and safety-domain capture before model sees prompt | Initial and subsequent user prompts | Tool permission decisions | Yes | Probe `codex exec` with a capture hook and synthetic MRN prompt |
| PreToolUse | Before supported tool execution | `tool_name` and aliases | common fields, `tool_name`, `tool_input` | JSON deny/block or exit 2 stderr | Can block before execution | Unsupported allow/update fields fail open | Block mutating tools without case/order | Bash/apply_patch/Edit/Write before execution | Approval prompt decisions | Yes | Existing ORD-001 coverage remains authoritative |
| PermissionRequest | When Codex asks approval | `tool_name` and aliases | common fields, `tool_name`, `tool_input` | JSON `decision.behavior` allow/deny | Can short-circuit approval | Reserved fields fail closed | Approval request guard only | Escalation/approval request | Ordinary non-approval commands | Yes | Existing ORD-001 coverage remains authoritative |
| PostToolUse | After supported tool output | `tool_name` and aliases | common fields, `tool_name`, `tool_response` | JSON additional context/block | Continues after completed tool | Cannot undo side effects | Evidence/context updates | After relevant tools | Pre-execution block claims | Yes | Existing ORD-001 coverage remains authoritative |
| Stop | Assistant turn end | ignored | common fields, `last_assistant_message`, `stop_hook_active` | JSON only on exit 0 | Can block/continue | Plain stdout invalid; bad loop can deadlock | Completion claim gate requiring expected result | Turn end before final response | Ordinary command gating | Yes | Existing ORD-001/006 coverage remains authoritative |

## Design Decision

ORD-007 focuses only on the remaining `UserPromptSubmit` residual. It will not alter PreToolUse, PermissionRequest, PostToolUse, or Stop behavior unless the probe shows the residual is caused by shared hook source loading.

## Acceptance For This Matrix

- If `SessionStart` capture fires but `UserPromptSubmit` capture does not, the hook source is loaded and the residual is event/surface-specific.
- If neither fires, the probe is inconclusive for `UserPromptSubmit` and must not be used to close the incident.
- If `UserPromptSubmit` fires, objective audit can require a validated probe record instead of an open incident heuristic.
