from __future__ import annotations

from pathlib import Path

import pytest

from agent_careflow.artifacts import ValidationError
from agent_careflow.bootstrap.profiles import install_profile, render_profile, validate_profile
from agent_careflow.bootstrap.target_repo import bootstrap_target_repo


def test_business_profile_writes_only_careflow_runtime_files(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    written = bootstrap_target_repo(target=target, control_repo=Path.cwd(), profile_name="business")

    assert written == [target / ".careflow" / "careflow.yaml", target / ".careflow" / "state.json"]
    assert (target / ".careflow" / "careflow.yaml").exists()
    assert (target / ".careflow" / "state.json").exists()
    assert not (target / ".codex").exists()
    assert not (target / ".claude").exists()
    assert not (target / ".cursor").exists()
    assert "claude: true" in (target / ".careflow" / "careflow.yaml").read_text(encoding="utf-8")


def test_private_profile_records_tool_intent_without_tool_configs(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    bootstrap_target_repo(target=target, control_repo=Path.cwd(), profile_name="private")

    assert not (target / ".codex").exists()
    assert not (target / ".claude").exists()
    assert not (target / ".cursor").exists()
    assert "claude: false" in (target / ".careflow" / "careflow.yaml").read_text(encoding="utf-8")


def test_bootstrap_fails_when_central_repo_missing(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="does not exist"):
        bootstrap_target_repo(target=tmp_path, control_repo=tmp_path / "missing", profile_name="business")

def test_profile_validate_accepts_business_profile() -> None:
    profile = validate_profile(Path.cwd(), "business")

    assert profile.codex is True
    assert profile.claude is True
    assert profile.cursor is True


def test_profile_render_writes_enabled_tool_configs(tmp_path: Path) -> None:
    profile = validate_profile(Path.cwd(), "private")

    written = render_profile(Path.cwd(), profile, tmp_path / "rendered")

    assert tmp_path / "rendered" / "codex" / "hooks.json" in written
    assert tmp_path / "rendered" / "cursor" / "hooks.json" in written
    assert not (tmp_path / "rendered" / "claude").exists()
    assert (tmp_path / "rendered" / "profile.json").exists()


def test_install_profile_applies_tool_overrides(tmp_path: Path) -> None:
    written = install_profile(Path.cwd(), "codex-only", tmp_path / "install", enable=["cursor"], disable=[])

    assert tmp_path / "install" / "codex-only" / "codex" / "hooks.json" in written
    assert tmp_path / "install" / "codex-only" / "cursor" / "hooks.json" in written
    assert not (tmp_path / "install" / "codex-only" / "claude").exists()


def test_profile_render_writes_native_skills(tmp_path: Path) -> None:
    profile = validate_profile(Path.cwd(), "codex-only")

    written = render_profile(Path.cwd(), profile, tmp_path / "rendered")

    assert tmp_path / "rendered" / "skills" / "using-agent-careflow" / "SKILL.md" in written
    assert tmp_path / "rendered" / "skills" / "brainstorming" / "SKILL.md" in written
    assert tmp_path / "rendered" / "skills" / "subagent-driven-development" / "SKILL.md" in written
    assert tmp_path / "rendered" / ".agents" / "skills" / "using-agent-careflow" / "SKILL.md" in written
    assert tmp_path / "rendered" / ".agents" / "skills" / "writing-plans" / "SKILL.md" in written
    assert not (tmp_path / "rendered" / ".claude" / "skills").exists()
    rendered_skills = sorted((tmp_path / "rendered" / "skills").glob("*/SKILL.md"))
    rendered_codex_skills = sorted((tmp_path / "rendered" / ".agents" / "skills").glob("*/SKILL.md"))
    assert len(rendered_skills) >= 14
    assert len(rendered_codex_skills) == len(rendered_skills)


def test_profile_render_writes_claude_skill_root_when_enabled(tmp_path: Path) -> None:
    profile = validate_profile(Path.cwd(), "business")

    written = render_profile(Path.cwd(), profile, tmp_path / "rendered")

    assert tmp_path / "rendered" / ".agents" / "skills" / "using-agent-careflow" / "SKILL.md" in written
    assert tmp_path / "rendered" / ".claude" / "skills" / "using-agent-careflow" / "SKILL.md" in written
    assert tmp_path / "rendered" / ".claude" / "skills" / "subagent-driven-development" / "SKILL.md" in written
