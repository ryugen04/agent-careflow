# careflow protocol + adapter conformance

## Goal

Reframe agent-careflow around careflow protocol normalization and adapter conformance records instead of live runtime probe capture.

## Steps

- [x] Inspect existing hook adapter, runtime probe, docs, tests, and staged evidence.
- [x] Add `agent_careflow.conformance` support for fixture replay, record generation, validation, and status rendering.
- [x] Replace runtime-probe CLI commands with `conformance record|validate|status`.
- [x] Update tests and fixtures to cover adapter conformance behavior and reject old probe records.
- [x] Rewrite docs/research/evidence language from runtime blockers to conformance plus optional compatibility evidence.
- [x] Run focused and full verification.
