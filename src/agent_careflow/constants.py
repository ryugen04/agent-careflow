from __future__ import annotations

from pathlib import Path

CARE_DIR = ".careflow"
CASES_DIR = Path(CARE_DIR) / "cases"
REQUIRED_RESEARCH_REPORTS = [
    "R-001-medical-workflow-patterns.md",
    "R-002-takt-and-oss-agent-orchestration.md",
    "R-003-codex-official-surface-2026.md",
    "R-004-claude-code-official-surface-2026.md",
    "R-005-cursor-composer-agent-surface-2026.md",
    "R-006-community-practice-signals-2026.md",
    "R-007-security-governance-policy.md",
]
REQUIRED_REPORT_SECTIONS = [
    "## Scope",
    "## Sources",
    "## Verified facts",
    "## Implementation implications",
    "## Risks / caveats",
    "## Open questions",
]
AUTHORITY_LEVELS = {"A", "B", "C", "D"}
RISK_CLASSES = {"C0", "C1", "C2", "C3", "C4"}
