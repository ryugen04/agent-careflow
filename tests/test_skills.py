from __future__ import annotations

from pathlib import Path

from agent_careflow.artifacts import parse_front_matter_lines

REQUIRED_SKILLS = {
    "using-agent-careflow",
    "brainstorming",
    "writing-plans",
    "subagent-driven-development",
    "executing-plans",
    "verification-before-completion",
    "requesting-code-review",
    "receiving-code-review",
    "systematic-debugging",
    "test-driven-development",
    "using-git-worktrees",
    "dispatching-parallel-agents",
    "finishing-a-development-branch",
    "writing-skills",
}


def skill_paths(root: Path) -> list[Path]:
    return sorted((root / "skills").glob("*/SKILL.md"))


def test_agent_careflow_native_skills_cover_superpowers_workflow() -> None:
    names = {path.parent.name for path in skill_paths(Path.cwd())}

    assert REQUIRED_SKILLS <= names


def test_agent_careflow_skills_have_unique_names_and_trigger_descriptions() -> None:
    names: list[str] = []
    for path in skill_paths(Path.cwd()):
        data = parse_front_matter_lines(path.read_text(encoding="utf-8"))
        name = data.get("name")
        description = data.get("description")
        assert isinstance(name, str) and name == path.parent.name
        assert isinstance(description, str) and any(token in description.lower() for token in ["use", "before", "when"])
        names.append(name)

    assert len(names) == len(set(names))


def test_agent_careflow_skills_point_to_careflow_artifacts() -> None:
    for skill in REQUIRED_SKILLS - {"using-agent-careflow"}:
        text = (Path.cwd() / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        assert any(token in text for token in [".careflow", "ORDER", "PLAN", "RESULT", "EVIDENCE", "INCIDENT"])
        assert "third_party/superpowers" in text


def test_using_agent_careflow_skill_defines_fixed_handoff_header() -> None:
    text = (Path.cwd() / "skills" / "using-agent-careflow" / "SKILL.md").read_text(encoding="utf-8")

    assert "PLAN_FILE:" in text
    assert "ORDER_FILE:" in text
    assert "SUBPLAN_FILE:" in text
    assert "EXPECTED_RESULT_PATH:" in text
    assert text.index("PLAN_FILE:") < text.index("ORDER_FILE:") < text.index("EXPECTED_RESULT_PATH:")


def test_delegation_skills_use_careflow_handoff_header_before_superpowers_sections() -> None:
    for skill in ["subagent-driven-development", "dispatching-parallel-agents"]:
        text = (Path.cwd() / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "PLAN_FILE:" in text
        assert "ORDER_FILE:" in text
        assert "SUBPLAN_FILE:" in text
        assert "EXPECTED_RESULT_PATH:" in text
        assert "Do not use the upstream Superpowers" in text
