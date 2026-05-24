# Signed PLAN Locks Plan

Date: 2026-05-25 JST

## Objective

Add optional cryptographic signatures to `PLAN.lock.json` while preserving existing deterministic hash locks:

- sign lock payloads with OpenSSH signatures
- verify signatures with an allowed signers file and principal
- expose signing and signature verification through CLI flags

## Acceptance Criteria

- Existing unsigned lock validation remains compatible.
- `hash plan --write-lock --signing-key ... --signing-principal ...` writes signature fields.
- `plan validate --require-signature --allowed-signers ... --signing-principal ...` verifies the signature.
- Tampered locks fail signature verification.
- Tests pass.
