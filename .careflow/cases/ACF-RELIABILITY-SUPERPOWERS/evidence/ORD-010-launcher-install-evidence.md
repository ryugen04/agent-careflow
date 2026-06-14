# ORD-010 launcher install evidence

fixture_home: /tmp/agent-careflow-ord-010-home.zqI6hh

## Launcher file

```text
-rwxr-xr-x 1 glaucus03 glaucus03 181 Jun 15 00:25 /tmp/agent-careflow-ord-010-home.zqI6hh/.local/bin/codex-careflow
#!/usr/bin/env bash
# dotfiles managed codex-careflow
set -euo pipefail
export AGENT_CAREFLOW_REPO="/home/glaucus03/dev/projects/agent-careflow"
exec agent-careflow codex exec "$@"
```

## Safe dry-run

```text
dry-run: prompt allowed
```

## Rejected prompt dry-run

```text
possible medical record identifier in prompt
```
