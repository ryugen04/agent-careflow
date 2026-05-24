from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .artifacts import ValidationError

STRATEGIES = {"worktree", "shared-clone", "temp-clone"}


@dataclass(frozen=True)
class IsolationPlan:
    strategy: str
    case_id: str
    target: Path
    work_dir: Path
    create_command: str
    cleanup_command: str
    notes: list[str]


def plan_isolation(*, target: Path, case_id: str, strategy: str = "worktree", base_ref: str = "HEAD") -> IsolationPlan:
    if strategy not in STRATEGIES:
        raise ValidationError(f"unsupported isolation strategy: {strategy}")
    target = target.resolve()
    if not target.exists():
        raise ValidationError(f"target repo does not exist: {target}")
    safe_case = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in case_id)
    parent = target.parent
    if strategy == "worktree":
        work_dir = parent / f"{target.name}-{safe_case}-worktree"
        return IsolationPlan(
            strategy=strategy,
            case_id=case_id,
            target=target,
            work_dir=work_dir,
            create_command=f"git -C {target.as_posix()} worktree add --detach {work_dir.as_posix()} {base_ref}",
            cleanup_command=f"git -C {target.as_posix()} worktree remove {work_dir.as_posix()}",
            notes=["default v0.x isolation strategy", "shares object database with target repo"],
        )
    if strategy == "shared-clone":
        work_dir = parent / f"{target.name}-{safe_case}-shared-clone"
        return IsolationPlan(
            strategy=strategy,
            case_id=case_id,
            target=target,
            work_dir=work_dir,
            create_command=f"git clone --shared {target.as_posix()} {work_dir.as_posix()}",
            cleanup_command=f"rm -rf {work_dir.as_posix()}",
            notes=["optional only after symlink/path traversal review", "cleanup command is destructive and requires explicit approval"],
        )
    work_dir = Path("/tmp") / f"{target.name}-{safe_case}-temp-clone"
    return IsolationPlan(
        strategy=strategy,
        case_id=case_id,
        target=target,
        work_dir=work_dir,
        create_command=f"git clone {target.as_posix()} {work_dir.as_posix()}",
        cleanup_command=f"rm -rf {work_dir.as_posix()}",
        notes=["highest separation of working directory", "patch export needed for integration"],
    )


def render_isolation_plan(plan: IsolationPlan) -> str:
    notes = "\n".join(f"- {note}" for note in plan.notes)
    return f"""strategy: {plan.strategy}
case_id: {plan.case_id}
target: {plan.target.as_posix()}
work_dir: {plan.work_dir.as_posix()}
create_command: {plan.create_command}
cleanup_command: {plan.cleanup_command}
notes:
{notes}
"""

MARKER = ".careflow-isolation.json"


def _run_git(args: list[str], *, cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise ValidationError(f"git command failed: {detail}")
    return result.stdout


def _write_marker(plan: IsolationPlan) -> Path:
    marker = plan.work_dir / MARKER
    marker.write_text(
        json.dumps(
            {
                "case_id": plan.case_id,
                "strategy": plan.strategy,
                "target": plan.target.as_posix(),
                "work_dir": plan.work_dir.as_posix(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return marker


def _load_marker(work_dir: Path) -> dict[str, str]:
    marker = work_dir / MARKER
    if not marker.exists():
        raise ValidationError(f"isolation marker missing: {marker}")
    data = json.loads(marker.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationError(f"invalid isolation marker: {marker}")
    return {str(key): str(value) for key, value in data.items()}


def create_isolation(*, target: Path, case_id: str, strategy: str = "worktree", base_ref: str = "HEAD") -> Path:
    plan = plan_isolation(target=target, case_id=case_id, strategy=strategy, base_ref=base_ref)
    if plan.work_dir.exists():
        raise ValidationError(f"isolation work_dir already exists: {plan.work_dir}")
    if strategy == "worktree":
        _run_git(["worktree", "add", "--detach", plan.work_dir.as_posix(), base_ref], cwd=plan.target)
    elif strategy == "shared-clone":
        _run_git(["clone", "--shared", plan.target.as_posix(), plan.work_dir.as_posix()], cwd=plan.target.parent)
    elif strategy == "temp-clone":
        _run_git(["clone", plan.target.as_posix(), plan.work_dir.as_posix()], cwd=plan.target.parent)
    else:
        raise ValidationError(f"unsupported isolation strategy: {strategy}")
    _write_marker(plan)
    return plan.work_dir


def cleanup_isolation(*, target: Path, case_id: str, strategy: str = "worktree", work_dir: Path | None = None, force: bool = False) -> Path:
    plan = plan_isolation(target=target, case_id=case_id, strategy=strategy)
    work_dir = (work_dir or plan.work_dir).resolve()
    marker = _load_marker(work_dir)
    if marker.get("case_id") != case_id or marker.get("strategy") != strategy:
        raise ValidationError("isolation marker does not match requested cleanup")
    if strategy == "worktree":
        command = ["worktree", "remove"]
        if force:
            command.append("--force")
        command.append(work_dir.as_posix())
        _run_git(command, cwd=plan.target)
    elif strategy in {"shared-clone", "temp-clone"}:
        shutil.rmtree(work_dir)
    else:
        raise ValidationError(f"unsupported isolation strategy: {strategy}")
    return work_dir


def export_isolation_patch(*, work_dir: Path, output: Path) -> Path:
    work_dir = work_dir.resolve()
    _load_marker(work_dir)
    patch = _run_git(["diff", "--binary"], cwd=work_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(patch, encoding="utf-8")
    return output
