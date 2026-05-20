from __future__ import annotations

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
            create_command=f"git -C {target.as_posix()} worktree add {work_dir.as_posix()} {base_ref}",
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
