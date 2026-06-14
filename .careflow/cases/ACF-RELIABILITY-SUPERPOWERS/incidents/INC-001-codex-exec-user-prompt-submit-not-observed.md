# INCIDENT: INC-001-codex-exec-user-prompt-submit-not-observed

incident_id: INC-001-codex-exec-user-prompt-submit-not-observed
case_id: ACF-RELIABILITY-SUPERPOWERS
trigger: codex_exec_user_prompt_submit_not_observed
status: closed
created_at: 2026-06-14T23:08:25+09:00
severity: medium

## Summary

Codex `exec` did not surface or enforce the configured `UserPromptSubmit` hook for a synthetic prompt that the agent-careflow prompt guard blocks in direct CLI/conformance tests: `debug synthetic patient MRN: ABC123456 in this fixture`. With `--dangerously-bypass-hook-trust`, SessionStart and careflow skill activation were observed but the prompt was not blocked. Without hook trust bypass in `/tmp`, neither SessionStart nor UserPromptSubmit hook events were observed.

## Impact

This does not invalidate the SessionStart bootstrap, fixed handoff contract, install audit, mutation gate, Stop gate, or direct prompt-guard implementation. It does mean agent-careflow cannot honestly claim pre-model prompt blocking for every `codex exec` invocation on Codex CLI 0.139.0 from the current runtime evidence.

## Corrective action

- Keep `UserPromptSubmit` configured and unit/conformance tested because supported hook surfaces can still call it.
- Treat live `codex exec` prompt blocking as a runtime limitation until an interactive or trusted-repo probe proves otherwise.
- Add future acceptance coverage for an interactive/trusted Codex surface if the CLI exposes a reliable non-interactive way to observe `UserPromptSubmit`.
- Avoid using live prompt-guard success as a completion criterion for this case; record the limitation in RESULT and evidence instead.
## ORD-007 Follow-up

Runtime-observed on 2026-06-14: `codex exec` with inline `SessionStart` and `UserPromptSubmit` capture hooks completed successfully, but no hook capture records were written. The command-level probe evidence is `.careflow/cases/ACF-RELIABILITY-SUPERPOWERS/evidence/ORD-007-user-prompt-submit-runtime-observed.jsonl` with `verdict: fail`.

This incident remained open after ORD-007 because direct `UserPromptSubmit` proof was still missing. Objective audit now checks probe evidence explicitly via `codex-user-prompt-submit-proof` instead of relying only on this incident filename.
## ORD-009 Mitigation

Added guarded wrapper `agent-careflow codex exec`, which runs the same prompt policy before invoking `codex exec`. Runtime evidence `.careflow/cases/ACF-RELIABILITY-SUPERPOWERS/evidence/ORD-009-codex-wrapper-preflight.jsonl` shows a synthetic MRN prompt was blocked with `invoked: false`.

This mitigates non-interactive Codex usage only when the wrapper is used or installed as the standard entrypoint. It does not prove native Codex `UserPromptSubmit` fired; ORD-011 closes this incident by explicitly accepting the wrapper mitigation as the policy boundary.

## ORD-011 Closure

status: closed
closed_at: 2026-06-15T00:00:00+09:00
closure_reason: accepted_guarded_launcher_policy
mitigation_acceptance: .careflow/cases/ACF-RELIABILITY-SUPERPOWERS/evidence/ORD-011-codex-exec-mitigation.json

The native Codex `UserPromptSubmit` limitation is not fixed or hidden. Closure means the incident no longer blocks the objective under the explicit policy boundary: non-interactive Codex execution must use the guarded `codex-careflow` / `agent-careflow codex exec` entrypoint. Objective audit keeps reporting native proof separately and accepts coverage only when wrapper preflight, launcher distribution, and this mitigation acceptance artifact are present.
