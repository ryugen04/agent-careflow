from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from agent_careflow.artifacts import ValidationError, parse_front_matter_lines
from agent_careflow.bootstrap.profiles import render_profile, validate_profile
from agent_careflow.bootstrap_context import bootstrap_context
from agent_careflow.artifacts import validate_case, validate_order, validate_plan
from agent_careflow.lifecycle import issue_order, require_reviews, validate_result
from agent_careflow.orders import render_order_prompt, write_result_skeleton
from agent_careflow.templates import render_case, render_discharge, render_plan

REQUIRED_SKILLS = (
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
)

BOOTSTRAP_TOKENS = (
    "Skill: using-agent-careflow",
    ".careflow",
    "PLAN",
    "ORDER",
    "RESULT",
)

TRANSCRIPT_REQUIRED_TOKENS = (
    "using-agent-careflow",
    "PLAN_FILE",
    "ORDER_FILE",
    "SUBPLAN_FILE",
    "EXPECTED_RESULT_PATH",
    "RESULT",
)

LIVE_CODEX_PROMPT = """Use the using-agent-careflow skill for this acceptance probe. Do not edit files.

Read the skill instructions, then reply with the fixed careflow handoff header labels from the skill.
Include the exact skill name and the fixed labels only; do not use generic Case/Plan/Order labels.
"""

OBJECTIVE_REQUIREMENTS = (
    {
        "id": "unified_tool_settings",
        "requirement": "Unified Claude and Codex careflow settings, skills, hooks, and artifact locations.",
        "checks": ("codex-claude-config-sources", "native-careflow-skills"),
        "evidence": ("rules/codex/hooks.json", "rules/claude/settings.json", "skills/"),
    },
    {
        "id": "durable_planning",
        "requirement": "Plans are deliberate, visible, durable, and stored under a predictable case directory.",
        "checks": ("case-artifact", "plan-artifact", "careflow-dashboard-index"),
        "evidence": (".careflow/cases/<case_id>/PLAN.md", ".careflow/INDEX.md"),
    },
    {
        "id": "agent_workspace_outputs",
        "requirement": "Intermediate outputs are visible through .agent/.agents or canonical .careflow artifacts.",
        "checks": ("careflow-dashboard-index", "agent-workspace-current", "agent-workspace-support-dirs"),
        "evidence": (".agent/current.md", ".agent/reviews/", ".agent/learnings/", ".agent/incidents/"),
    },
    {
        "id": "troubles_and_learnings",
        "requirement": "Troubles and lessons are persisted so another session can promote them into improvements or docs.",
        "checks": ("learning-promotion", "open-incidents", "runtime-residuals-clear"),
        "evidence": (".careflow/cases/<case_id>/learnings/", "docs/learnings/", ".careflow/cases/<case_id>/incidents/"),
    },
    {
        "id": "fixed_handoff_contract",
        "requirement": "Claude-to-Codex, Codex-to-Claude, and subagent handoffs begin with the fixed plan/order/subplan/result header.",
        "checks": ("session-start-bootstrap", "fixed-handoff-contract"),
        "evidence": (".careflow/cases/<case_id>/orders/*.order.md", "agent-careflow order prompt"),
    },
    {
        "id": "order_as_subplan",
        "requirement": "Each ORDER is the executable subplan and completion requires the expected RESULT path.",
        "checks": ("fixed-handoff-contract", "careflow-dashboard-index", "agent-workspace-current"),
        "evidence": (".careflow/cases/<case_id>/orders/*.order.md", ".careflow/cases/<case_id>/results/*.result.md"),
    },
    {
        "id": "superpowers_style_enforcement",
        "requirement": "Superpowers-style enforcement is substantially implemented rather than added as optional prose.",
        "checks": ("superpowers-vendored", "native-careflow-skills", "codex-claude-config-sources", "session-start-bootstrap"),
        "evidence": ("third_party/superpowers/", "skills/", "rules/"),
    },
    {
        "id": "activation_forgetting_failure_mode",
        "requirement": "Known low activation, missed recognition, and mid-session forgetting failure modes are addressed by runtime evidence and accepted boundaries.",
        "checks": ("session-start-bootstrap", "codex-user-prompt-submit-coverage", "careflow-dashboard-index", "agent-workspace-current"),
        "evidence": (".careflow/cases/<case_id>/evidence/*user-prompt-submit*.jsonl", ".careflow/INDEX.md", ".agent/current.md"),
    },
    {
        "id": "multi_repo_worktree_layout",
        "requirement": "Root repositories and root/.worktrees/{branch}/{repo} layouts are resolved and visible.",
        "checks": ("root-worktree-resolution",),
        "evidence": ("src/agent_careflow/context.py", "src/agent_careflow/repo_status.py", ".agent/repos.md"),
    },
    {
        "id": "distribution_launchers",
        "requirement": "Dotfiles/profile distribution installs explicit guarded Codex and Claude careflow launchers without shadowing the real tools.",
        "checks": ("codex-careflow-launcher-distribution", "claude-careflow-launcher-distribution"),
        "evidence": (".careflow/cases/<case_id>/evidence/*install-audit*.json", "~/.local/bin/codex-careflow", "~/.local/bin/claude-careflow"),
    },
    {
        "id": "objective_completion_audit",
        "requirement": "The original requirement can be audited end-to-end and residual limitations remain explicit.",
        "checks": ("objective-audit-profile-status",),
        "evidence": ("agent-careflow acceptance objective-audit", "agent-careflow acceptance objective-matrix"),
    },
)


@dataclass(frozen=True)
class AcceptanceCheck:
    name: str
    status: str
    details: str


def _skill_roots(target: Path, *, codex: bool, claude: bool) -> list[Path]:
    roots = [target / "skills"]
    if codex:
        roots.append(target / ".agents" / "skills")
    if claude:
        roots.append(target / ".claude" / "skills")
    return roots


def _check_skill_root(root: Path) -> AcceptanceCheck:
    missing = [name for name in REQUIRED_SKILLS if not (root / name / "SKILL.md").exists()]
    if missing:
        return AcceptanceCheck(root.as_posix(), "fail", f"missing skills: {', '.join(missing)}")
    mismatches: list[str] = []
    for name in REQUIRED_SKILLS:
        path = root / name / "SKILL.md"
        data = parse_front_matter_lines(path.read_text(encoding="utf-8"))
        if data.get("name") != name:
            mismatches.append(name)
    if mismatches:
        return AcceptanceCheck(root.as_posix(), "fail", f"frontmatter name mismatch: {', '.join(mismatches)}")
    return AcceptanceCheck(root.as_posix(), "pass", f"{len(REQUIRED_SKILLS)} skills available")


def _check_bootstrap_context(control_repo: Path) -> AcceptanceCheck:
    text = bootstrap_context(control_repo)
    missing = [token for token in BOOTSTRAP_TOKENS if token not in text]
    if missing:
        return AcceptanceCheck("session-start-bootstrap", "fail", f"missing bootstrap tokens: {', '.join(missing)}")
    return AcceptanceCheck("session-start-bootstrap", "pass", "bootstrap context names the careflow skill and required artifact contract")


def run_profile_acceptance(control_repo: Path, profile_name: str, target: Path) -> dict[str, object]:
    control_repo = control_repo.resolve()
    target = target.resolve()
    profile = validate_profile(control_repo, profile_name)
    written = render_profile(control_repo, profile, target)
    checks = [_check_skill_root(root) for root in _skill_roots(target, codex=profile.codex, claude=profile.claude)]
    checks.append(_check_bootstrap_context(control_repo))
    failed = [check for check in checks if check.status != "pass"]
    return {
        "schema": "agent-careflow.acceptance.profile.v1",
        "profile": profile.name,
        "target": target.as_posix(),
        "tools": {"codex": profile.codex, "claude": profile.claude, "cursor": profile.cursor},
        "written_count": len(written),
        "status": "fail" if failed else "pass",
        "checks": [asdict(check) for check in checks],
    }


def run_handoff_acceptance(target: Path) -> dict[str, object]:
    target = target.resolve()
    case_id = "ACF-HANDOFF"
    order_id = "ORD-HANDOFF"
    case_root = target / ".careflow" / "cases" / case_id
    (case_root / "orders").mkdir(parents=True, exist_ok=True)
    (case_root / "results").mkdir(exist_ok=True)
    (case_root / "evidence").mkdir(exist_ok=True)
    (case_root / "incidents").mkdir(exist_ok=True)
    (case_root / "reviews").mkdir(exist_ok=True)
    (case_root / "conferences").mkdir(exist_ok=True)
    (case_root / "CASE.yaml").write_text(render_case(case_id, "Handoff acceptance", "C1"), encoding="utf-8")
    (case_root / "PLAN.md").write_text(render_plan(case_id, "Handoff acceptance", "C1"), encoding="utf-8")
    (case_root / "DISCHARGE.md").write_text(render_discharge(case_id), encoding="utf-8")
    order_path = issue_order(target, case_id, order_id, "implementer")
    result_path = write_result_skeleton(target, case_id, order_id, force=True)

    checks: list[AcceptanceCheck] = []
    try:
        validate_case(case_root / "CASE.yaml")
        validate_plan(case_root / "PLAN.md")
        validate_order(order_path, target)
        validate_result(result_path)
        checks.append(AcceptanceCheck("handoff-artifacts", "pass", "CASE, PLAN, ORDER, and RESULT validate"))
    except ValidationError as exc:
        checks.append(AcceptanceCheck("handoff-artifacts", "fail", str(exc)))

    for tool in ("claude", "codex"):
        prompt = render_order_prompt(target, case_id, order_id, tool)
        required = ("PLAN_FILE:", "ORDER_FILE:", "SUBPLAN_FILE:", "EXPECTED_RESULT_PATH:")
        header_lines = prompt.splitlines()[:8]
        missing = [token for token in required if not any(line.startswith(token) for line in header_lines)]
        if missing:
            checks.append(AcceptanceCheck(f"{tool}-handoff-prompt", "fail", f"missing header token(s): {', '.join(missing)}"))
        elif not prompt.startswith("PLAN_FILE: .careflow/cases/ACF-HANDOFF/PLAN.md"):
            checks.append(AcceptanceCheck(f"{tool}-handoff-prompt", "fail", "PLAN_FILE is not the first line"))
        else:
            checks.append(AcceptanceCheck(f"{tool}-handoff-prompt", "pass", "prompt starts with plan/order/subplan/result contract"))

    failed = [check for check in checks if check.status != "pass"]
    return {
        "schema": "agent-careflow.acceptance.handoff.v1",
        "target": target.as_posix(),
        "case_id": case_id,
        "order_id": order_id,
        "status": "fail" if failed else "pass",
        "checks": [asdict(check) for check in checks],
    }


def _symlink_check(name: str, target: Path, expected: Path) -> AcceptanceCheck:
    if not target.exists() and not target.is_symlink():
        return AcceptanceCheck(name, "fail", f"missing: {target}")
    if not target.is_symlink():
        return AcceptanceCheck(name, "fail", f"unmanaged non-symlink path: {target}")
    actual = target.resolve(strict=False)
    expected_resolved = expected.resolve(strict=False)
    if actual != expected_resolved:
        return AcceptanceCheck(name, "fail", f"expected symlink to {expected_resolved}, got {actual}")
    return AcceptanceCheck(name, "pass", f"linked to {expected_resolved}")


def _text_contains_check(name: str, path: Path, token: str) -> AcceptanceCheck:
    if not path.exists():
        return AcceptanceCheck(name, "fail", f"missing: {path}")
    if path.is_dir():
        return AcceptanceCheck(name, "fail", f"expected file, got directory: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if token not in text:
        return AcceptanceCheck(name, "fail", f"missing token {token!r} in {path}")
    return AcceptanceCheck(name, "pass", f"{path} contains {token!r}")


def _careflow_source_check(control_repo: Path) -> AcceptanceCheck:
    missing = []
    if not (control_repo / "rules" / "codex" / "hooks.json").exists():
        missing.append("rules/codex/hooks.json")
    if not (control_repo / "skills" / "using-agent-careflow" / "SKILL.md").exists():
        missing.append("skills/using-agent-careflow/SKILL.md")
    if missing:
        return AcceptanceCheck("careflow-source", "fail", f"missing source file(s): {', '.join(missing)}")
    return AcceptanceCheck("careflow-source", "pass", f"source repo ready: {control_repo}")


def run_install_audit(control_repo: Path, target_home: Path, tools: list[str] | tuple[str, ...]) -> dict[str, object]:
    control_repo = control_repo.resolve()
    target_home = target_home.expanduser().resolve()
    selected = tuple(dict.fromkeys(tools or ["codex"]))
    unsupported = [tool for tool in selected if tool not in {"codex", "claude"}]
    if unsupported:
        raise ValidationError(f"unsupported install audit tool(s): {', '.join(unsupported)}")

    checks: list[AcceptanceCheck] = [_careflow_source_check(control_repo)]
    if "codex" in selected:
        checks.append(_symlink_check("codex-hooks", target_home / ".codex" / "hooks.json", control_repo / "rules" / "codex" / "hooks.json"))
        checks.append(_text_contains_check("codex-config-hooks-enabled", target_home / ".codex" / "config.toml", "hooks = true"))
        checks.append(_text_contains_check("codex-careflow-launcher", target_home / ".local" / "bin" / "codex-careflow", "agent-careflow codex exec"))
        for skill in REQUIRED_SKILLS:
            checks.append(_symlink_check(f"codex-skill-{skill}", target_home / ".agents" / "skills" / skill, control_repo / "skills" / skill))
    if "claude" in selected:
        checks.append(_text_contains_check("claude-settings-careflow-hook", target_home / ".claude" / "settings.json", "agent-careflow hook claude session-start"))
        checks.append(_text_contains_check("claude-careflow-launcher", target_home / ".local" / "bin" / "claude-careflow", "agent-careflow workspace --write"))
        checks.append(_text_contains_check("claude-careflow-launcher-delegates", target_home / ".local" / "bin" / "claude-careflow", "exec claude"))
        for skill in REQUIRED_SKILLS:
            checks.append(_symlink_check(f"claude-skill-{skill}", target_home / ".claude" / "skills" / skill, control_repo / "skills" / skill))

    failed = [check for check in checks if check.status != "pass"]
    return {
        "schema": "agent-careflow.acceptance.install_audit.v1",
        "target": target_home.as_posix(),
        "control_repo": control_repo.as_posix(),
        "tools": list(selected),
        "status": "fail" if failed else "pass",
        "checks": [asdict(check) for check in checks],
    }


def _check_transcript_text(name: str, text: str) -> AcceptanceCheck:
    missing = [token for token in TRANSCRIPT_REQUIRED_TOKENS if token not in text]
    if missing:
        return AcceptanceCheck(name, "fail", f"missing transcript token(s): {', '.join(missing)}")
    first_plan = text.find("PLAN_FILE")
    first_order = text.find("ORDER_FILE")
    first_result = text.find("EXPECTED_RESULT_PATH")
    if not (0 <= first_plan < first_order < first_result):
        return AcceptanceCheck(name, "fail", "handoff labels are not ordered as PLAN_FILE, ORDER_FILE, EXPECTED_RESULT_PATH")
    return AcceptanceCheck(name, "pass", "transcript contains skill and handoff/result contract tokens")


def run_transcript_acceptance_from_text(text: str, *, label: str = "transcript") -> dict[str, object]:
    checks = [_check_transcript_text(label, text)]
    failed = [check for check in checks if check.status != "pass"]
    return {
        "schema": "agent-careflow.acceptance.transcript.v1",
        "target": label,
        "mode": "text",
        "status": "fail" if failed else "pass",
        "checks": [asdict(check) for check in checks],
    }


def run_transcript_acceptance_from_file(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    report = run_transcript_acceptance_from_text(text, label=path.as_posix())
    report["mode"] = "file"
    return report


def _parse_json_lines(text: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in text.splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def _event_text(events: list[dict[str, object]]) -> str:
    return "\n".join(json.dumps(event, sort_keys=True) for event in events)


def run_live_codex_transcript_acceptance(workdir: Path, *, output: Path | None = None, timeout: int = 120) -> dict[str, object]:
    workdir = workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    output_path = output or (workdir / "codex-transcript-acceptance.txt")
    command = [
        "codex",
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--dangerously-bypass-hook-trust",
        "-C",
        workdir.as_posix(),
        "-o",
        output_path.as_posix(),
        LIVE_CODEX_PROMPT,
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, check=False, timeout=timeout)
    transcript = output_path.read_text(encoding="utf-8", errors="replace") if output_path.exists() else ""
    json_events = _parse_json_lines(result.stdout)
    event_text = _event_text(json_events)
    skill_read = "using-agent-careflow/SKILL.md" in event_text and "PLAN_FILE" in event_text
    checks = [
        AcceptanceCheck(
            "live-codex-command",
            "pass" if result.returncode == 0 else "fail",
            f"exit={result.returncode} output={output_path}",
        ),
        AcceptanceCheck(
            "live-codex-skill-read",
            "pass" if skill_read else "fail",
            "using-agent-careflow skill read with fixed header" if skill_read else "using-agent-careflow skill read with fixed header was not observed",
        ),
        _check_transcript_text("live-codex-transcript", transcript),
    ]
    failed = [check for check in checks if check.status != "pass"]
    return {
        "schema": "agent-careflow.acceptance.transcript.v1",
        "target": workdir.as_posix(),
        "mode": "live-codex",
        "command": command,
        "output_path": output_path.as_posix(),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "json_event_count": len(json_events),
        "exit_code": result.returncode,
        "status": "fail" if failed else "pass",
        "checks": [asdict(check) for check in checks],
    }


def run_live_claude_transcript_acceptance(workdir: Path, *, timeout: int = 120) -> dict[str, object]:
    workdir = workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    command = [
        "claude",
        "-p",
        "--verbose",
        "--output-format",
        "stream-json",
        "--include-hook-events",
        "--no-session-persistence",
        "--permission-mode",
        "plan",
        "--tools",
        "",
        "--debug",
        "hooks",
        "Use the using-agent-careflow skill. Do not edit files or run tools. Reply with the fixed careflow handoff header labels only.",
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, cwd=workdir, check=False, timeout=timeout)
    json_events = _parse_json_lines(result.stdout)
    text = _event_text(json_events)
    hook_observed = '"hook_event":"SessionStart"' in text or '"hook_event": "SessionStart"' in text
    bootstrap_observed = "Skill: using-agent-careflow" in text and "PLAN_FILE" in text and "EXPECTED_RESULT_PATH" in text
    skills_observed = '"using-agent-careflow"' in text and '"skills"' in text
    auth_unavailable = "authentication_failed" in text or "Invalid authentication credentials" in text
    command_ok_for_bootstrap = result.returncode == 0 or (auth_unavailable and hook_observed and bootstrap_observed)
    checks = [
        AcceptanceCheck(
            "live-claude-command",
            "pass" if command_ok_for_bootstrap else "fail",
            f"exit={result.returncode} auth_unavailable={auth_unavailable}",
        ),
        AcceptanceCheck(
            "live-claude-session-start-hook",
            "pass" if hook_observed else "fail",
            "SessionStart hook event observed" if hook_observed else "SessionStart hook event not observed",
        ),
        AcceptanceCheck(
            "live-claude-bootstrap-context",
            "pass" if bootstrap_observed else "fail",
            "bootstrap context contains using-agent-careflow and fixed handoff labels" if bootstrap_observed else "bootstrap context did not include fixed careflow labels",
        ),
        AcceptanceCheck(
            "live-claude-skill-list",
            "pass" if skills_observed else "fail",
            "using-agent-careflow is in Claude skill inventory" if skills_observed else "using-agent-careflow skill inventory entry not observed",
        ),
    ]
    failed = [check for check in checks if check.status != "pass"]
    return {
        "schema": "agent-careflow.acceptance.transcript.v1",
        "target": workdir.as_posix(),
        "mode": "live-claude",
        "command": command,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "json_event_count": len(json_events),
        "exit_code": result.returncode,
        "auth_unavailable": auth_unavailable,
        "status": "fail" if failed else "pass",
        "checks": [asdict(check) for check in checks],
    }


HANDOFF_LABELS = (
    "PLAN_FILE:",
    "ORDER_FILE:",
    "SUBPLAN_FILE:",
    "EXPECTED_RESULT_PATH:",
    "CASE_ID:",
    "ORDER_ID:",
    "ASSIGNED_ROLE:",
    "TARGET_TOOL:",
)

PLACEHOLDER_REVIEW_TOKENS = (
    "placeholder",
    "auth unavailable",
    "authentication failure",
    "authentication_failed",
)


def _exists_check(name: str, path: Path, detail: str | None = None) -> AcceptanceCheck:
    if path.exists():
        return AcceptanceCheck(name, "pass", detail or f"present: {path}")
    return AcceptanceCheck(name, "fail", f"missing: {path}")


def _read_optional(path: Path) -> str:
    if not path.exists() or path.is_dir():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _check_required_files(name: str, paths: list[Path], *, detail: str) -> AcceptanceCheck:
    missing = [path.as_posix() for path in paths if not path.exists()]
    if missing:
        return AcceptanceCheck(name, "fail", f"missing file(s): {', '.join(missing)}")
    return AcceptanceCheck(name, "pass", detail)


def _check_all_tokens(name: str, paths: list[Path], tokens: tuple[str, ...], *, detail: str) -> AcceptanceCheck:
    missing_paths = [path.as_posix() for path in paths if not path.exists()]
    if missing_paths:
        return AcceptanceCheck(name, "fail", f"missing file(s): {', '.join(missing_paths)}")
    text = "\n".join(_read_optional(path) for path in paths)
    missing = [token for token in tokens if token not in text]
    if missing:
        return AcceptanceCheck(name, "fail", f"missing token(s): {', '.join(missing)}")
    return AcceptanceCheck(name, "pass", detail)


def _check_native_skill_root(root: Path) -> AcceptanceCheck:
    check = _check_skill_root(root)
    if check.status != "pass":
        return AcceptanceCheck("native-careflow-skills", check.status, check.details)
    return AcceptanceCheck("native-careflow-skills", "pass", check.details)


def _check_bootstrap_handoff(control_repo: Path) -> AcceptanceCheck:
    try:
        text = bootstrap_context(control_repo)
    except ValidationError as exc:
        return AcceptanceCheck("session-start-bootstrap", "fail", str(exc))
    tokens = ("Skill: using-agent-careflow",) + HANDOFF_LABELS
    missing = [token for token in tokens if token not in text]
    if missing:
        return AcceptanceCheck("session-start-bootstrap", "fail", f"missing bootstrap token(s): {', '.join(missing)}")
    return AcceptanceCheck("session-start-bootstrap", "pass", "bootstrap names the careflow skill and fixed handoff labels")


def _check_fixed_handoff(case_root: Path) -> AcceptanceCheck:
    order_paths = sorted((case_root / "orders").glob("*.order.md")) if (case_root / "orders").exists() else []
    if not order_paths:
        return AcceptanceCheck("fixed-handoff-contract", "fail", f"missing order files under {case_root / 'orders'}")
    bad: list[str] = []
    for path in order_paths:
        lines = _read_optional(path).splitlines()
        positions = []
        for label in HANDOFF_LABELS:
            try:
                positions.append(next(index for index, line in enumerate(lines) if line.startswith(label)))
            except StopIteration:
                bad.append(f"{path.name}: missing {label}")
                break
        else:
            if positions != sorted(positions):
                bad.append(f"{path.name}: handoff labels out of order")
    if bad:
        return AcceptanceCheck("fixed-handoff-contract", "fail", "; ".join(bad))
    return AcceptanceCheck("fixed-handoff-contract", "pass", f"{len(order_paths)} order file(s) contain ordered fixed handoff labels")


def _check_dashboard_and_workspace(control_repo: Path, case_id: str) -> list[AcceptanceCheck]:
    state_path = control_repo / ".careflow" / "state.json"
    state_text = _read_optional(state_path)
    try:
        state = json.loads(state_text) if state_text else {}
    except json.JSONDecodeError:
        state = {}
    active_order = str(state.get("active_order") or "")
    expected_result = str(state.get("expected_result_path") or "")
    dashboard = control_repo / ".careflow" / "INDEX.md"
    current = control_repo / ".agent" / "current.md"
    checks = [
        _check_all_tokens(
            "careflow-dashboard-index",
            [dashboard],
            (case_id, active_order, expected_result) if active_order and expected_result else (case_id,),
            detail=".careflow/INDEX.md names the active case/order/result",
        ),
        _check_all_tokens(
            "agent-workspace-current",
            [current],
            (case_id, active_order, expected_result) if active_order and expected_result else (case_id,),
            detail=".agent/current.md names the active case/order/result",
        ),
        _check_required_files(
            "agent-workspace-support-dirs",
            [
                control_repo / ".agent" / "reviews" / "README.md",
                control_repo / ".agent" / "learnings" / "README.md",
                control_repo / ".agent" / "incidents" / "README.md",
            ],
            detail=".agent support directories are present",
        ),
    ]
    return checks


def _check_learning_promotion(control_repo: Path, case_root: Path) -> AcceptanceCheck:
    learning_paths = sorted((case_root / "learnings").glob("*.md")) if (case_root / "learnings").exists() else []
    promoted: list[str] = []
    missing_docs: list[str] = []
    for path in learning_paths:
        text = _read_optional(path)
        data = parse_front_matter_lines(text)
        if data.get("status") != "promoted":
            continue
        target = str(data.get("promoted_to") or "")
        if not target:
            missing_docs.append(f"{path.name}: missing promoted_to")
            continue
        doc_path = control_repo / target
        if doc_path.exists() and "source_learning:" in _read_optional(doc_path):
            promoted.append(path.name)
        else:
            missing_docs.append(f"{path.name}: missing promoted doc {target}")
    if missing_docs:
        return AcceptanceCheck("learning-promotion", "fail", "; ".join(missing_docs))
    if not promoted:
        return AcceptanceCheck("learning-promotion", "fail", f"no promoted learning found under {case_root / 'learnings'}")
    return AcceptanceCheck("learning-promotion", "pass", f"promoted learning(s): {', '.join(promoted)}")


def _check_reviews(control_repo: Path, case_id: str, *, profile: str) -> list[AcceptanceCheck]:
    checks: list[AcceptanceCheck] = []
    if profile == "private":
        try:
            found = require_reviews(control_repo, case_id, ["codex"], strict=True)
            checks.append(AcceptanceCheck("review-private-codex-only", "pass", ", ".join(path.name for path in found.values())))
        except ValidationError as exc:
            checks.append(AcceptanceCheck("review-private-codex-only", "fail", str(exc)))
        return checks

    try:
        found = require_reviews(control_repo, case_id, ["codex", "claude"], strict=True)
        detail = ", ".join(path.name for path in found.values())
        checks.append(AcceptanceCheck("review-dual-codex-claude", "pass", detail))
    except ValidationError as exc:
        checks.append(AcceptanceCheck("review-dual-codex-claude", "fail", str(exc)))
    try:
        found = require_reviews(control_repo, case_id, ["codex"], strict=True)
        checks.append(AcceptanceCheck("review-private-codex-only", "pass", ", ".join(path.name for path in found.values())))
    except ValidationError as exc:
        checks.append(AcceptanceCheck("review-private-codex-only", "fail", str(exc)))

    claude_reviews = sorted((control_repo / ".careflow" / "cases" / case_id / "reviews").glob("*.review.md"))
    claude_texts = [(_read_optional(path), path) for path in claude_reviews if "tool: claude" in _read_optional(path)]
    if not claude_texts:
        checks.append(AcceptanceCheck("claude-review-not-placeholder", "fail", "missing Claude review artifact"))
    else:
        placeholder_paths = [path.name for text, path in claude_texts if any(token in text.lower() for token in PLACEHOLDER_REVIEW_TOKENS)]
        if placeholder_paths:
            checks.append(AcceptanceCheck("claude-review-not-placeholder", "fail", f"placeholder/auth-unavailable review(s): {', '.join(placeholder_paths)}"))
        else:
            checks.append(AcceptanceCheck("claude-review-not-placeholder", "pass", "Claude review artifact is not a placeholder/auth-unavailable record"))
    return checks


def _load_probe_records(path: Path) -> tuple[list[dict[str, object]], list[str]]:
    records: list[dict[str, object]] = []
    errors: list[str] = []
    if not path.exists():
        return records, [f"missing: {path}"]
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return records, [f"empty probe log: {path.name}"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            errors.append(f"{path.name}:{line_number}: empty line")
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{line_number}: invalid JSON: {exc}")
            continue
        if not isinstance(parsed, dict):
            errors.append(f"{path.name}:{line_number}: record is not an object")
            continue
        if parsed.get("schema") != "codex.runtime_probe.v1":
            errors.append(f"{path.name}:{line_number}: invalid schema")
        if parsed.get("event") != "UserPromptSubmit":
            continue
        records.append(parsed)
    return records, errors


def _check_user_prompt_submit_probe(case_root: Path) -> AcceptanceCheck:
    evidence = case_root / "evidence"
    paths = sorted(evidence.glob("*user-prompt-submit*.jsonl")) if evidence.exists() else []
    if not paths:
        return AcceptanceCheck("codex-user-prompt-submit-proof", "fail", f"missing UserPromptSubmit probe evidence under {evidence}")

    all_records: list[tuple[Path, dict[str, object]]] = []
    errors: list[str] = []
    for path in paths:
        records, path_errors = _load_probe_records(path)
        all_records.extend((path, record) for record in records)
        errors.extend(path_errors)

    if not all_records:
        detail = "; ".join(errors) if errors else "no UserPromptSubmit records found"
        return AcceptanceCheck("codex-user-prompt-submit-proof", "fail", f"missing direct UserPromptSubmit proof: {detail}")

    pass_records = [(path, record) for path, record in all_records if record.get("verdict") == "pass"]
    fail_records = [(path, record) for path, record in all_records if record.get("verdict") == "fail"]
    inconclusive_records = [(path, record) for path, record in all_records if record.get("verdict") == "inconclusive"]
    if pass_records:
        names = ", ".join(f"{path.name}:{record.get('probe')}" for path, record in pass_records)
        return AcceptanceCheck("codex-user-prompt-submit-proof", "pass", f"direct UserPromptSubmit runtime proof: {names}")
    if fail_records:
        names = ", ".join(f"{path.name}:{record.get('probe')}" for path, record in fail_records)
        return AcceptanceCheck("codex-user-prompt-submit-proof", "fail", f"runtime-observed failing UserPromptSubmit probe(s): {names}")
    if inconclusive_records:
        names = ", ".join(f"{path.name}:{record.get('probe')}" for path, record in inconclusive_records)
        return AcceptanceCheck("codex-user-prompt-submit-proof", "fail", f"inconclusive UserPromptSubmit probe(s): {names}")
    return AcceptanceCheck("codex-user-prompt-submit-proof", "fail", "UserPromptSubmit probe records have no pass/fail/inconclusive verdict")


def _check_codex_wrapper_preflight(case_root: Path) -> AcceptanceCheck:
    evidence = case_root / "evidence"
    paths = sorted(evidence.glob("*codex-wrapper-preflight*.jsonl")) if evidence.exists() else []
    if not paths:
        return AcceptanceCheck("codex-wrapper-preflight", "fail", f"missing Codex wrapper preflight evidence under {evidence}")
    records: list[tuple[Path, dict[str, object]]] = []
    errors: list[str] = []
    for path in paths:
        parsed, path_errors = _load_probe_records(path)
        records.extend((path, record) for record in parsed if record.get("probe") == "agent-careflow-codex-wrapper-preflight")
        errors.extend(path_errors)
    blocked_pass = [
        (path, record)
        for path, record in records
        if record.get("verdict") == "pass" and isinstance(record.get("input_payload"), dict) and record["input_payload"].get("blocked") is True
    ]
    if blocked_pass:
        names = ", ".join(f"{path.name}:{record.get('probe')}" for path, record in blocked_pass)
        return AcceptanceCheck("codex-wrapper-preflight", "pass", f"wrapper blocked rejected prompt before Codex invocation: {names}")
    detail = "; ".join(errors) if errors else "no passing blocked wrapper preflight record found"
    return AcceptanceCheck("codex-wrapper-preflight", "fail", detail)


def _check_codex_launcher_distribution(case_root: Path) -> AcceptanceCheck:
    evidence = case_root / "evidence"
    paths = sorted(evidence.glob("*install-audit*.json")) if evidence.exists() else []
    if not paths:
        return AcceptanceCheck("codex-careflow-launcher-distribution", "fail", f"missing install-audit JSON evidence under {evidence}")

    errors: list[str] = []
    for path in paths:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue
        if report.get("schema") != "agent-careflow.acceptance.install_audit.v1":
            errors.append(f"{path.name}: not an install-audit report")
            continue
        if report.get("status") != "pass":
            errors.append(f"{path.name}: install audit status is {report.get('status')}")
            continue
        checks = report.get("checks")
        if not isinstance(checks, list):
            errors.append(f"{path.name}: missing checks")
            continue
        launcher_check = next((check for check in checks if isinstance(check, dict) and check.get("name") == "codex-careflow-launcher"), None)
        if launcher_check and launcher_check.get("status") == "pass" and "agent-careflow codex exec" in str(launcher_check.get("details", "")):
            return AcceptanceCheck("codex-careflow-launcher-distribution", "pass", f"install audit proves guarded launcher: {path.name}")
        errors.append(f"{path.name}: codex-careflow-launcher pass check not found")
    detail = "; ".join(errors) if errors else "no install-audit reports found"
    return AcceptanceCheck("codex-careflow-launcher-distribution", "fail", detail)




def _check_claude_launcher_distribution(case_root: Path) -> AcceptanceCheck:
    evidence = case_root / "evidence"
    paths = sorted(evidence.glob("*install-audit*.json")) if evidence.exists() else []
    if not paths:
        return AcceptanceCheck("claude-careflow-launcher-distribution", "fail", f"missing install-audit JSON evidence under {evidence}")

    errors: list[str] = []
    for path in paths:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue
        if report.get("schema") != "agent-careflow.acceptance.install_audit.v1":
            errors.append(f"{path.name}: not an install-audit report")
            continue
        if report.get("status") != "pass":
            errors.append(f"{path.name}: install audit status is {report.get('status')}")
            continue
        checks = report.get("checks")
        if not isinstance(checks, list):
            errors.append(f"{path.name}: missing checks")
            continue
        launcher_check = next((check for check in checks if isinstance(check, dict) and check.get("name") == "claude-careflow-launcher"), None)
        delegate_check = next((check for check in checks if isinstance(check, dict) and check.get("name") == "claude-careflow-launcher-delegates"), None)
        launcher_ok = launcher_check and launcher_check.get("status") == "pass" and "agent-careflow workspace --write" in str(launcher_check.get("details", ""))
        delegate_ok = delegate_check and delegate_check.get("status") == "pass" and "exec claude" in str(delegate_check.get("details", ""))
        if launcher_ok and delegate_ok:
            return AcceptanceCheck("claude-careflow-launcher-distribution", "pass", f"install audit proves guarded Claude launcher: {path.name}")
        errors.append(f"{path.name}: claude-careflow launcher/delegate pass checks not found")
    detail = "; ".join(errors) if errors else "no install-audit reports found"
    return AcceptanceCheck("claude-careflow-launcher-distribution", "fail", detail)

def _check_codex_exec_mitigation_acceptance(case_root: Path) -> AcceptanceCheck:
    evidence = case_root / "evidence"
    paths = sorted(evidence.glob("*codex-exec-mitigation*.json")) if evidence.exists() else []
    if not paths:
        return AcceptanceCheck("codex-exec-mitigation-acceptance", "fail", f"missing Codex exec mitigation acceptance under {evidence}")

    errors: list[str] = []
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue
        required_checks = record.get("required_checks")
        if record.get("schema") != "agent-careflow.acceptance.codex_exec_mitigation.v1":
            errors.append(f"{path.name}: invalid schema")
            continue
        if record.get("status") != "accepted":
            errors.append(f"{path.name}: status is {record.get('status')}")
            continue
        if record.get("policy_boundary") != "non_interactive_codex_exec_must_use_guarded_launcher":
            errors.append(f"{path.name}: unsupported policy boundary")
            continue
        if not isinstance(required_checks, list) or not {"codex-wrapper-preflight", "codex-careflow-launcher-distribution"}.issubset(set(required_checks)):
            errors.append(f"{path.name}: required checks do not name wrapper preflight and launcher distribution")
            continue
        if not record.get("incident_id"):
            errors.append(f"{path.name}: missing incident_id")
            continue
        return AcceptanceCheck("codex-exec-mitigation-acceptance", "pass", f"accepted guarded launcher policy: {path.name}")
    detail = "; ".join(errors) if errors else "no mitigation acceptance reports found"
    return AcceptanceCheck("codex-exec-mitigation-acceptance", "fail", detail)


def _check_codex_user_prompt_submit_coverage(native: AcceptanceCheck, wrapper: AcceptanceCheck, launcher: AcceptanceCheck, mitigation: AcceptanceCheck) -> AcceptanceCheck:
    if native.status == "pass":
        return AcceptanceCheck("codex-user-prompt-submit-coverage", "pass", f"native UserPromptSubmit proof covers Codex exec: {native.details}")
    if wrapper.status == "pass" and launcher.status == "pass" and mitigation.status == "pass":
        return AcceptanceCheck(
            "codex-user-prompt-submit-coverage",
            "pass",
            f"accepted mitigation covers non-interactive Codex exec; native status remains: {native.details}",
        )
    missing = [check.name for check in (wrapper, launcher, mitigation) if check.status != "pass"]
    suffix = f"; missing mitigation check(s): {', '.join(missing)}" if missing else ""
    return AcceptanceCheck("codex-user-prompt-submit-coverage", "fail", f"{native.details}{suffix}")


def _check_open_incidents(case_root: Path) -> list[AcceptanceCheck]:
    incident_paths = sorted((case_root / "incidents").glob("*.md")) if (case_root / "incidents").exists() else []
    open_incidents = [path for path in incident_paths if "status: closed" not in _read_optional(path)]
    open_paths = [path.name for path in open_incidents]
    checks: list[AcceptanceCheck] = []
    if open_paths:
        checks.append(AcceptanceCheck("open-incidents", "fail", f"open incident(s): {', '.join(open_paths)}"))
    else:
        checks.append(AcceptanceCheck("open-incidents", "pass", "no open incident artifacts"))
    user_prompt_paths = [path.name for path in open_incidents if "user-prompt-submit" in path.name.lower() or "user_prompt_submit" in _read_optional(path).lower()]
    if user_prompt_paths:
        checks.append(AcceptanceCheck("codex-user-prompt-submit-residual", "fail", f"runtime residual incident(s): {', '.join(user_prompt_paths)}"))
    else:
        checks.append(AcceptanceCheck("codex-user-prompt-submit-residual", "pass", "no UserPromptSubmit residual incident recorded"))
    if not open_paths and not user_prompt_paths:
        checks.append(AcceptanceCheck("runtime-residuals-clear", "pass", "no tracked runtime residuals remain open"))
    else:
        checks.append(AcceptanceCheck("runtime-residuals-clear", "fail", "open runtime residuals remain"))
    return checks


def _check_runtime_evidence(case_root: Path) -> AcceptanceCheck:
    result_text = "\n".join(_read_optional(path) for path in sorted((case_root / "results").glob("*.result.md"))) if (case_root / "results").exists() else ""
    tokens = ("install-audit", "live-codex", "live-claude")
    missing = [token for token in tokens if token not in result_text]
    if missing:
        return AcceptanceCheck("install-and-runtime-evidence", "fail", f"missing evidence token(s) in result files: {', '.join(missing)}")
    return AcceptanceCheck("install-and-runtime-evidence", "pass", "result files record install audit and live Codex/Claude transcript evidence")


def run_objective_audit(control_repo: Path, case_id: str = "ACF-RELIABILITY-SUPERPOWERS", *, profile: str = "business") -> dict[str, object]:
    if profile not in {"business", "private"}:
        raise ValidationError(f"unsupported objective audit profile: {profile}")
    control_repo = control_repo.resolve()
    case_root = control_repo / ".careflow" / "cases" / case_id
    checks: list[AcceptanceCheck] = [
        _exists_check("case-artifact", case_root / "CASE.yaml"),
        _exists_check("plan-artifact", case_root / "PLAN.md"),
        _exists_check("superpowers-vendored", control_repo / "third_party" / "superpowers" / "skills" / "using-superpowers" / "SKILL.md"),
        _check_native_skill_root(control_repo / "skills"),
        _check_all_tokens(
            "codex-claude-config-sources",
            [control_repo / "rules" / "codex" / "hooks.json", control_repo / "rules" / "claude" / "settings.json"],
            ("SessionStart", "Stop", "agent-careflow hook codex session-start", "agent-careflow hook claude session-start"),
            detail="Codex and Claude hook source configs include SessionStart and Stop wiring",
        ),
        _check_bootstrap_handoff(control_repo),
        _check_fixed_handoff(case_root),
        _check_required_files(
            "root-worktree-resolution",
            [control_repo / "src" / "agent_careflow" / "context.py", control_repo / "tests" / "test_context.py"],
            detail="root/worktree context resolver and tests are present",
        ),
        _check_runtime_evidence(case_root),
    ]
    native_prompt = _check_user_prompt_submit_probe(case_root)
    wrapper_preflight = _check_codex_wrapper_preflight(case_root)
    launcher_distribution = _check_codex_launcher_distribution(case_root)
    claude_launcher_distribution = _check_claude_launcher_distribution(case_root)
    mitigation_acceptance = _check_codex_exec_mitigation_acceptance(case_root)
    checks.extend([
        native_prompt,
        wrapper_preflight,
        launcher_distribution,
        claude_launcher_distribution,
        mitigation_acceptance,
        _check_codex_user_prompt_submit_coverage(native_prompt, wrapper_preflight, launcher_distribution, mitigation_acceptance),
    ])
    checks.extend(_check_dashboard_and_workspace(control_repo, case_id))
    checks.append(_check_learning_promotion(control_repo, case_root))
    checks.extend(_check_reviews(control_repo, case_id, profile=profile))
    checks.extend(_check_open_incidents(case_root))
    coverage_passed = any(check.name == "codex-user-prompt-submit-coverage" and check.status == "pass" for check in checks)
    failed = [
        check
        for check in checks
        if check.status != "pass"
        and not (coverage_passed and check.name in {"codex-user-prompt-submit-proof", "codex-exec-mitigation-acceptance"})
    ]
    return {
        "schema": "agent-careflow.acceptance.objective_audit.v1",
        "target": control_repo.as_posix(),
        "case_id": case_id,
        "profile": profile,
        "status": "fail" if failed else "pass",
        "checks": [asdict(check) for check in checks],
    }


def _objective_review_requirement(profile: str) -> dict[str, object]:
    if profile == "private":
        return {
            "id": "business_private_review_policy",
            "requirement": "Private/Codex-only workflows require Codex review only while preserving the same artifact contract.",
            "checks": ("review-private-codex-only",),
            "evidence": (".careflow/cases/<case_id>/reviews/REVIEW-CODEX-*.review.md",),
        }
    return {
        "id": "business_private_review_policy",
        "requirement": "Business workflows require both Codex and real non-placeholder Claude review artifacts before close.",
        "checks": ("review-dual-codex-claude", "claude-review-not-placeholder", "review-private-codex-only"),
        "evidence": (".careflow/cases/<case_id>/reviews/REVIEW-CODEX-*.review.md", ".careflow/cases/<case_id>/reviews/REVIEW-CLAUDE-*.review.md"),
    }


def _matrix_requirement_status(requirement: dict[str, object], checks_by_name: dict[str, AcceptanceCheck]) -> tuple[str, str, list[dict[str, str]]]:
    check_names = tuple(str(name) for name in requirement.get("checks", ()))
    check_results: list[dict[str, str]] = []
    failures: list[str] = []
    details_parts: list[str] = []
    for name in check_names:
        check = checks_by_name.get(name)
        if check is None:
            failures.append(f"{name}=missing")
            check_results.append({"name": name, "status": "missing", "details": "check was not produced"})
            details_parts.append(f"{name}=missing")
            continue
        check_results.append({"name": check.name, "status": check.status, "details": check.details})
        details_parts.append(f"{check.name}={check.status}: {check.details}")
        if check.status != "pass":
            failures.append(f"{check.name}={check.status}")
    evidence = ", ".join(str(item) for item in requirement.get("evidence", ()))
    status = "fail" if failures else "pass"
    details = f"checks: {'; '.join(details_parts)}; evidence: {evidence}"
    return status, details, check_results


def run_objective_matrix(control_repo: Path, case_id: str = "ACF-RELIABILITY-SUPERPOWERS", *, profile: str = "business") -> dict[str, object]:
    audit = run_objective_audit(control_repo, case_id, profile=profile)
    checks_by_name: dict[str, AcceptanceCheck] = {
        str(item.get("name")): AcceptanceCheck(str(item.get("name")), str(item.get("status")), str(item.get("details")))
        for item in audit.get("checks", [])
        if isinstance(item, dict) and item.get("name")
    }
    checks_by_name["objective-audit-profile-status"] = AcceptanceCheck(
        "objective-audit-profile-status",
        str(audit.get("status")),
        f"objective-audit profile={profile} status={audit.get('status')}",
    )

    requirements: list[dict[str, object]] = []
    matrix_checks: list[AcceptanceCheck] = []
    definitions = list(OBJECTIVE_REQUIREMENTS) + [_objective_review_requirement(profile)]
    for requirement in definitions:
        status, details, check_results = _matrix_requirement_status(requirement, checks_by_name)
        requirements.append({
            "id": requirement["id"],
            "requirement": requirement["requirement"],
            "status": status,
            "checks": [result["name"] for result in check_results],
            "check_results": check_results,
            "evidence": list(requirement.get("evidence", ())),
            "details": details,
        })
        matrix_checks.append(AcceptanceCheck(f"objective-{requirement['id']}", status, details))

    failed = [check for check in matrix_checks if check.status != "pass"]
    return {
        "schema": "agent-careflow.acceptance.objective_matrix.v1",
        "target": audit["target"],
        "case_id": case_id,
        "profile": profile,
        "status": "fail" if failed else "pass",
        "objective_audit_status": audit.get("status"),
        "requirements": requirements,
        "checks": [asdict(check) for check in matrix_checks],
    }


def render_acceptance_report(report: dict[str, object], *, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(report, indent=2, sort_keys=True) + "\n"
    if report.get("schema") == "agent-careflow.acceptance.objective_audit.v1":
        lines = [f"acceptance={report['status']} objective-audit case={report.get('case_id')} profile={report.get('profile', 'business')} target={report['target']}"]
    elif report.get("schema") == "agent-careflow.acceptance.objective_matrix.v1":
        lines = [f"acceptance={report['status']} objective-matrix case={report.get('case_id')} profile={report.get('profile', 'business')} target={report['target']}"]
    elif "profile" in report:
        lines = [f"acceptance={report['status']} profile={report['profile']} target={report['target']}"]
    elif "case_id" in report:
        lines = [f"acceptance={report['status']} case={report.get('case_id')} order={report.get('order_id')} target={report['target']}"]
    elif report.get("schema") == "agent-careflow.acceptance.transcript.v1":
        lines = [f"acceptance={report['status']} transcript mode={report.get('mode')} target={report['target']}"]
    else:
        tools = ",".join(str(tool) for tool in report.get("tools", []))
        lines = [f"acceptance={report['status']} install_audit tools={tools} target={report['target']}"]
    for item in report["checks"]:
        check = item if isinstance(item, dict) else {}
        lines.append(f"{check.get('status')}: {check.get('name')} - {check.get('details')}")
    return "\n".join(lines) + "\n"


def ensure_acceptance_passed(report: dict[str, object]) -> None:
    if report.get("status") != "pass":
        raise ValidationError("acceptance failed")
