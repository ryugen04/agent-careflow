from __future__ import annotations

from pathlib import Path

from agent_careflow.artifacts import ValidationError

BOOTSTRAP_SKILL = "using-agent-careflow"


def control_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + 5 :]


def bootstrap_skill_path(root: Path | None = None) -> Path:
    repo = root or control_repo_root()
    return repo / "skills" / BOOTSTRAP_SKILL / "SKILL.md"


def bootstrap_context(root: Path | None = None) -> str:
    path = bootstrap_skill_path(root)
    if not path.exists():
        raise ValidationError(f"bootstrap skill not found: {path}")
    body = _strip_frontmatter(path.read_text(encoding="utf-8")).strip()
    return (
        "<EXTREMELY_IMPORTANT>\n"
        "You have agent-careflow.\n\n"
        "Skill: using-agent-careflow\n\n"
        "Acceptance-critical handoff header labels, in order: "
        "PLAN_FILE, ORDER_FILE, SUBPLAN_FILE, EXPECTED_RESULT_PATH, CASE_ID, ORDER_ID, ASSIGNED_ROLE, TARGET_TOOL. "
        "Do not replace them with generic CASE/PLAN/ORDER labels.\n\n"
        "The agent-careflow bootstrap skill is already loaded below. "
        "Use native skill tooling for any other applicable skills.\n\n"
        f"{body}\n"
        "</EXTREMELY_IMPORTANT>"
    )
