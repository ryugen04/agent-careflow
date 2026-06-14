# Learning: Codex exec UserPromptSubmit Surface

case_id: ACF-RELIABILITY-SUPERPOWERS
source_incident: .careflow/cases/ACF-RELIABILITY-SUPERPOWERS/incidents/INC-001-codex-exec-user-prompt-submit-not-observed.md
recorded_at: 2026-06-14T23:10:00+09:00

## Observation

On Codex CLI 0.139.0, live `codex exec` probes did not show `UserPromptSubmit` hook events for a synthetic MRN prompt. In an untrusted `/tmp` workdir without hook trust bypass, no hook events were observed. With hook trust bypass, SessionStart and skill activation were observed, but UserPromptSubmit still did not block the prompt.

## Operational Rule

Use SessionStart bootstrap, skills, mutating-tool gates, Stop gates, fixed ORDER headers, and result/evidence validation as the primary reliability mechanism for Codex exec. Keep prompt guard tests and hook config, but do not depend on Codex exec prompt-submit blocking until a specific runtime surface proves it.

## Follow-up Candidate

Probe a trusted repository interactive Codex session or an official Codex hook payload capture path for `UserPromptSubmit`, then update acceptance criteria and docs if the event is supported there.
