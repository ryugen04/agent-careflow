# Hook Capture Entry Point Plan

Date: 2026-05-21 JST

## Objective

Add a safe hook payload capture command that records stdin payloads as `codex.runtime_probe.v1` JSONL so live runtime fixtures can be collected later without changing core adapters.

## Steps

1. Implement `hook capture` helper that reads stdin and appends JSONL.
2. Add CLI command with event/output/probe options.
3. Add tests for valid JSONL output and invalid event handling.
4. Document usage and record evidence.
5. Run tests and commit.

## Acceptance Criteria

- Capture logs validate with the existing runtime probe validator shape.
- Capture does not make policy decisions.
- The command can be used from hook config as a sidecar probe.
