from __future__ import annotations

import json
from pathlib import Path

from agent_careflow.artifacts import ValidationError

from .profiles import Profile, load_profile


def copy_text(src: Path, dst: Path) -> None:
    if not src.exists():
        raise ValidationError(f"missing template source: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def bootstrap_target_repo(*, target: Path, control_repo: Path, profile_name: str) -> list[Path]:
    target = target.resolve()
    control_repo = control_repo.resolve()
    if not control_repo.exists():
        raise ValidationError(f"central careflow repo does not exist: {control_repo}")
    profile = load_profile(control_repo, profile_name)
    written: list[Path] = []
    careflow_dir = target / ".careflow"
    careflow_dir.mkdir(parents=True, exist_ok=True)
    careflow_yaml = careflow_dir / "careflow.yaml"
    careflow_yaml.write_text(
        "\n".join(
            [
                f"careflow_repo: {control_repo.as_posix()}",
                f"profile: {profile.name}",
                "tools:",
                f"  codex: {str(profile.codex).lower()}",
                f"  claude: {str(profile.claude).lower()}",
                f"  cursor: {str(profile.cursor).lower()}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    written.append(careflow_yaml)
    state_json = careflow_dir / "state.json"
    state_json.write_text(json.dumps({"active_case": None, "phase": "intake"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written.append(state_json)
    if profile.codex:
        dst = target / ".codex" / "hooks.json"
        copy_text(control_repo / "rules" / "codex" / "hooks.json", dst)
        written.append(dst)
    if profile.claude:
        dst = target / ".claude" / "settings.json"
        copy_text(control_repo / "rules" / "claude" / "settings.json", dst)
        written.append(dst)
    if profile.cursor:
        dst = target / ".cursor" / "hooks.json"
        copy_text(control_repo / "rules" / "cursor" / "hooks.json", dst)
        written.append(dst)
    return written
