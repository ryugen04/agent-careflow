from __future__ import annotations

from pathlib import Path

import pytest

from agent_careflow.artifacts import ValidationError
from agent_careflow.bootstrap.target_repo import bootstrap_target_repo


def test_business_profile_writes_all_tool_configs(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    written = bootstrap_target_repo(target=target, control_repo=Path.cwd(), profile_name="business")

    assert target / ".careflow" / "careflow.yaml" in written
    assert (target / ".codex" / "hooks.json").exists()
    assert (target / ".claude" / "settings.json").exists()
    assert (target / ".cursor" / "hooks.json").exists()
    assert "claude: true" in (target / ".careflow" / "careflow.yaml").read_text(encoding="utf-8")


def test_private_profile_does_not_write_claude_config(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    bootstrap_target_repo(target=target, control_repo=Path.cwd(), profile_name="private")

    assert (target / ".codex" / "hooks.json").exists()
    assert not (target / ".claude").exists()
    assert (target / ".cursor" / "hooks.json").exists()
    assert "claude: false" in (target / ".careflow" / "careflow.yaml").read_text(encoding="utf-8")


def test_bootstrap_fails_when_central_repo_missing(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="does not exist"):
        bootstrap_target_repo(target=tmp_path, control_repo=tmp_path / "missing", profile_name="business")
