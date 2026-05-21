from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .artifacts import ValidationError, case_dir, sha256_file, validate_case, validate_discharge, validate_order, validate_plan, validate_research, write_plan_lock
from .constants import CASES_DIR, RISK_CLASSES
from .policy.engine import PolicyEngine
from .hooks.common import evaluate_permission_request, evaluate_pre_tool_use, load_payload
from .hooks.capture import append_capture_record
from .hooks import claude as claude_hooks
from .hooks import codex as codex_hooks
from .hooks import cursor as cursor_hooks
from .research import scaffold_research
from .templates import render_case, render_discharge, render_plan
from .bootstrap.target_repo import bootstrap_target_repo
from .lifecycle import advance_phase, case_status, issue_order, new_incident, validate_result, validate_review
from .orders import order_status, render_order_prompt
from .isolation import plan_isolation, render_isolation_plan
from .takt import analyze_takt_workflow, render_takt_analysis


def ok(message: str) -> int:
    print(message)
    return 0


def fail(error: Exception | str) -> int:
    print(f"error: {error}", file=sys.stderr)
    return 1


def cmd_research_scaffold(args: argparse.Namespace) -> int:
    written = scaffold_research(Path.cwd())
    return ok(f"research scaffold ready ({len(written)} file(s) created)")


def cmd_research_validate(args: argparse.Namespace) -> int:
    try:
        validate_research(Path.cwd())
    except ValidationError as exc:
        return fail(exc)
    return ok("research valid")


def cmd_case_new(args: argparse.Namespace) -> int:
    risk = args.risk.upper()
    if risk not in RISK_CLASSES:
        return fail(f"invalid risk class {args.risk!r}")
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in args.title).strip("-")[:40] or "case"
    case_id = args.case_id or f"ACF-{slug}"
    root = case_dir(Path.cwd(), case_id)
    if root.exists():
        return fail(f"case already exists: {case_id}")
    (root / "orders").mkdir(parents=True)
    (root / "results").mkdir()
    (root / "evidence").mkdir()
    (root / "incidents").mkdir()
    (root / "reviews").mkdir()
    (root / "conferences").mkdir()
    (root / "CASE.yaml").write_text(render_case(case_id, args.title, risk), encoding="utf-8")
    (root / "PLAN.md").write_text(render_plan(case_id, args.title, risk), encoding="utf-8")
    (root / "DISCHARGE.md").write_text(render_discharge(case_id), encoding="utf-8")
    try:
        validate_case(root / "CASE.yaml")
        validate_plan(root / "PLAN.md")
    except ValidationError as exc:
        return fail(exc)
    return ok(f"created case {case_id}")


def cmd_plan_validate(args: argparse.Namespace) -> int:
    path = case_dir(Path.cwd(), args.case) / "PLAN.md"
    try:
        validate_plan(path, require_lock=args.require_lock)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"plan valid: {path}")


def cmd_hash_plan(args: argparse.Namespace) -> int:
    path = case_dir(Path.cwd(), args.case) / "PLAN.md"
    try:
        if args.write_lock:
            lock_path = write_plan_lock(path)
            return ok(f"plan lock written: {lock_path}")
        print(sha256_file(path))
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return 0


def cmd_order_validate(args: argparse.Namespace) -> int:
    order_name = args.order
    if not order_name.endswith(".order.md"):
        order_name = f"{order_name}.order.md"
    path = case_dir(Path.cwd(), args.case) / "orders" / order_name
    try:
        validate_order(path, Path.cwd())
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"order valid: {path}")


def cmd_discharge_validate(args: argparse.Namespace) -> int:
    root = case_dir(Path.cwd(), args.case)
    path = root / "DISCHARGE.md"
    try:
        validate_discharge(path, root)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"discharge valid: {path}")


def cmd_close_validate(args: argparse.Namespace) -> int:
    return cmd_discharge_validate(args)


def cmd_phase_status(args: argparse.Namespace) -> int:
    try:
        status = case_status(Path.cwd(), args.case)
    except ValidationError as exc:
        return fail(exc)
    print(f"case={status['case_id']} phase={status['phase']} status={status['status']} evidence={status['evidence_count']} open_incidents={len(status['open_incidents'])}")
    return 0


def cmd_phase_advance(args: argparse.Namespace) -> int:
    try:
        advance_phase(Path.cwd(), args.case, args.to)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"phase advanced: {args.case} -> {args.to}")


def cmd_order_issue(args: argparse.Namespace) -> int:
    try:
        path = issue_order(Path.cwd(), args.case, args.order, args.role)
        validate_order(path, Path.cwd())
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"order issued: {path}")


def cmd_order_prompt(args: argparse.Namespace) -> int:
    try:
        print(render_order_prompt(Path.cwd(), args.case, args.order, args.tool))
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return 0


def cmd_order_status(args: argparse.Namespace) -> int:
    try:
        status = order_status(Path.cwd(), args.case, args.order)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    completion = "complete" if status["complete"] else "incomplete"
    print(f"order={status['order_id']} case={status['case_id']} status={completion} expected_result_path={status['expected_result_path']}")
    return 0 if status["complete"] else 1


def cmd_result_validate(args: argparse.Namespace) -> int:
    path = case_dir(Path.cwd(), args.case) / "results" / args.result
    try:
        validate_result(path)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"result valid: {path}")


def cmd_review_validate(args: argparse.Namespace) -> int:
    path = case_dir(Path.cwd(), args.case) / "reviews" / args.review
    try:
        validate_review(path)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"review valid: {path}")


def cmd_incident_new(args: argparse.Namespace) -> int:
    try:
        path = new_incident(Path.cwd(), args.case, args.trigger)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"incident created: {path}")


def cmd_init(args: argparse.Namespace) -> int:
    (Path.cwd() / CASES_DIR).mkdir(parents=True, exist_ok=True)
    scaffold_research(Path.cwd())
    return ok("agent-careflow repository initialized")


def cmd_bootstrap(args: argparse.Namespace) -> int:
    try:
        written = bootstrap_target_repo(target=Path(args.target), control_repo=Path(args.careflow_repo), profile_name=args.profile)
    except ValidationError as exc:
        return fail(exc)
    return ok(f"bootstrap complete ({len(written)} file(s) written)")


def cmd_policy_check_file(args: argparse.Namespace) -> int:
    try:
        decision = PolicyEngine(Path.cwd()).check_file(
            case_id=args.case,
            path=args.path,
            operation=args.operation,
            order_id=args.order,
        )
    except ValidationError as exc:
        return fail(exc)
    print(f"{decision.status.value}: {decision.reason}")
    return 0 if decision.allowed else 1


def cmd_policy_check_command(args: argparse.Namespace) -> int:
    decision = PolicyEngine(Path.cwd()).check_command(args.command_text)
    print(f"{decision.status.value}: {decision.reason}")
    return 0 if decision.allowed else 1


def cmd_isolation_plan(args: argparse.Namespace) -> int:
    try:
        plan = plan_isolation(target=Path(args.target), case_id=args.case, strategy=args.strategy, base_ref=args.base_ref)
    except ValidationError as exc:
        return fail(exc)
    print(render_isolation_plan(plan))
    return 0


def cmd_takt_analyze(args: argparse.Namespace) -> int:
    try:
        report = render_takt_analysis(analyze_takt_workflow(Path(args.workflow)))
    except ValidationError as exc:
        return fail(exc)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        return ok(f"takt analysis written: {output}")
    print(report)
    return 0


def cmd_hook_capture(args: argparse.Namespace) -> int:
    try:
        payload = load_payload(sys.stdin.read())
        append_capture_record(
            output=Path(args.output),
            event=args.event_name,
            probe=args.probe,
            cwd=Path.cwd(),
            input_payload=payload,
            verdict=args.verdict,
            notes=args.notes,
        )
    except ValidationError as exc:
        return fail(exc)
    return ok(f"hook payload captured: {args.output}")


def cmd_hook(args: argparse.Namespace) -> int:
    try:
        payload = load_payload(sys.stdin.read())
        if args.event == "permission-request":
            decision = evaluate_permission_request(payload, on_missing_context=args.on_missing_context)
        else:
            decision = evaluate_pre_tool_use(payload, on_missing_context=args.on_missing_context)
    except ValidationError as exc:
        return fail(exc)

    if args.tool == "codex":
        if args.event == "permission-request":
            print(codex_hooks.render_permission_request(decision))
        elif args.event == "post-tool-use":
            print(codex_hooks.render_post_tool_use(decision))
        else:
            print(codex_hooks.render_pre_tool_use(decision))
    elif args.tool == "claude":
        if args.event == "post-tool-use":
            print(claude_hooks.render_post_tool_use(decision))
        else:
            print(claude_hooks.render_pre_tool_use(decision))
    else:
        if args.event == "post-tool-use":
            print(cursor_hooks.render_post_tool_use(decision))
        else:
            print(cursor_hooks.render_pre_tool_use(decision))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-careflow")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.set_defaults(func=cmd_init)

    bootstrap = sub.add_parser("bootstrap")
    bootstrap.add_argument("--target", default=".")
    bootstrap.add_argument("--profile", default="business")
    bootstrap.add_argument("--careflow-repo", default=str(Path.cwd()))
    bootstrap.set_defaults(func=cmd_bootstrap)

    research = sub.add_parser("research")
    research_sub = research.add_subparsers(dest="research_command", required=True)
    research_scaffold = research_sub.add_parser("scaffold")
    research_scaffold.set_defaults(func=cmd_research_scaffold)
    research_validate = research_sub.add_parser("validate")
    research_validate.set_defaults(func=cmd_research_validate)

    case = sub.add_parser("case")
    case_sub = case.add_subparsers(dest="case_command", required=True)
    case_new = case_sub.add_parser("new")
    case_new.add_argument("--title", required=True)
    case_new.add_argument("--risk", default="C1")
    case_new.add_argument("--case-id")
    case_new.set_defaults(func=cmd_case_new)

    plan = sub.add_parser("plan")
    plan_sub = plan.add_subparsers(dest="plan_command", required=True)
    plan_validate = plan_sub.add_parser("validate")
    plan_validate.add_argument("--case", required=True)
    plan_validate.add_argument("--require-lock", action="store_true")
    plan_validate.set_defaults(func=cmd_plan_validate)

    hash_cmd = sub.add_parser("hash")
    hash_sub = hash_cmd.add_subparsers(dest="hash_command", required=True)
    hash_plan = hash_sub.add_parser("plan")
    hash_plan.add_argument("--case", required=True)
    hash_plan.add_argument("--write-lock", action="store_true")
    hash_plan.set_defaults(func=cmd_hash_plan)

    order = sub.add_parser("order")
    order_sub = order.add_subparsers(dest="order_command", required=True)
    order_validate = order_sub.add_parser("validate")
    order_validate.add_argument("--case", required=True)
    order_validate.add_argument("--order", required=True)
    order_validate.set_defaults(func=cmd_order_validate)
    order_issue = order_sub.add_parser("issue")
    order_issue.add_argument("--case", required=True)
    order_issue.add_argument("--order", required=True)
    order_issue.add_argument("--role", required=True)
    order_issue.set_defaults(func=cmd_order_issue)
    order_prompt = order_sub.add_parser("prompt")
    order_prompt.add_argument("--case", required=True)
    order_prompt.add_argument("--order", required=True)
    order_prompt.add_argument("--tool", choices=["codex", "claude", "cursor"], required=True)
    order_prompt.set_defaults(func=cmd_order_prompt)
    order_status_parser = order_sub.add_parser("status")
    order_status_parser.add_argument("--case", required=True)
    order_status_parser.add_argument("--order", required=True)
    order_status_parser.set_defaults(func=cmd_order_status)

    result = sub.add_parser("result")
    result_sub = result.add_subparsers(dest="result_command", required=True)
    result_validate = result_sub.add_parser("validate")
    result_validate.add_argument("--case", required=True)
    result_validate.add_argument("--result", required=True)
    result_validate.set_defaults(func=cmd_result_validate)

    review = sub.add_parser("review")
    review_sub = review.add_subparsers(dest="review_command", required=True)
    review_validate = review_sub.add_parser("validate")
    review_validate.add_argument("--case", required=True)
    review_validate.add_argument("--review", required=True)
    review_validate.set_defaults(func=cmd_review_validate)

    incident = sub.add_parser("incident")
    incident_sub = incident.add_subparsers(dest="incident_command", required=True)
    incident_new = incident_sub.add_parser("new")
    incident_new.add_argument("--case", required=True)
    incident_new.add_argument("--trigger", required=True)
    incident_new.set_defaults(func=cmd_incident_new)

    phase = sub.add_parser("phase")
    phase_sub = phase.add_subparsers(dest="phase_command", required=True)
    phase_status = phase_sub.add_parser("status")
    phase_status.add_argument("--case", required=True)
    phase_status.set_defaults(func=cmd_phase_status)
    phase_advance = phase_sub.add_parser("advance")
    phase_advance.add_argument("--case", required=True)
    phase_advance.add_argument("--to", required=True)
    phase_advance.set_defaults(func=cmd_phase_advance)

    discharge = sub.add_parser("discharge")
    discharge_sub = discharge.add_subparsers(dest="discharge_command", required=True)
    discharge_validate = discharge_sub.add_parser("validate")
    discharge_validate.add_argument("--case", required=True)
    discharge_validate.set_defaults(func=cmd_discharge_validate)

    close = sub.add_parser("close")
    close_sub = close.add_subparsers(dest="close_command", required=True)
    close_validate = close_sub.add_parser("validate")
    close_validate.add_argument("--case", required=True)
    close_validate.set_defaults(func=cmd_close_validate)

    policy = sub.add_parser("policy")
    policy_sub = policy.add_subparsers(dest="policy_command", required=True)
    check_file = policy_sub.add_parser("check-file")
    check_file.add_argument("--case", required=True)
    check_file.add_argument("--path", required=True)
    check_file.add_argument("--operation", choices=["read", "write"], required=True)
    check_file.add_argument("--order")
    check_file.set_defaults(func=cmd_policy_check_file)
    check_command = policy_sub.add_parser("check-command")
    check_command.add_argument("--command", dest="command_text", required=True)
    check_command.set_defaults(func=cmd_policy_check_command)

    isolation = sub.add_parser("isolation")
    isolation_sub = isolation.add_subparsers(dest="isolation_command", required=True)
    isolation_plan = isolation_sub.add_parser("plan")
    isolation_plan.add_argument("--target", default=".")
    isolation_plan.add_argument("--case", required=True)
    isolation_plan.add_argument("--strategy", choices=["worktree", "shared-clone", "temp-clone"], default="worktree")
    isolation_plan.add_argument("--base-ref", default="HEAD")
    isolation_plan.set_defaults(func=cmd_isolation_plan)

    takt = sub.add_parser("takt")
    takt_sub = takt.add_subparsers(dest="takt_command", required=True)
    takt_analyze = takt_sub.add_parser("analyze")
    takt_analyze.add_argument("--workflow", required=True)
    takt_analyze.add_argument("--output")
    takt_analyze.set_defaults(func=cmd_takt_analyze)

    hook = sub.add_parser("hook")
    hook_sub = hook.add_subparsers(dest="tool", required=True)
    capture = hook_sub.add_parser("capture")
    capture.add_argument("--event-name", required=True)
    capture.add_argument("--output", required=True)
    capture.add_argument("--probe", default="hook-payload-capture")
    capture.add_argument("--verdict", choices=["pass", "fail", "inconclusive"], default="inconclusive")
    capture.add_argument("--notes", default="runtime-observed: captured hook stdin payload")
    capture.set_defaults(func=cmd_hook_capture)
    for tool_name in ("codex", "claude", "cursor"):
        tool_parser = hook_sub.add_parser(tool_name)
        event_sub = tool_parser.add_subparsers(dest="event", required=True)
        events = ["pre-tool-use", "post-tool-use"]
        if tool_name == "codex":
            events.append("permission-request")
        for event_name in events:
            event_parser = event_sub.add_parser(event_name)
            event_parser.add_argument("--on-missing-context", choices=["warn", "deny"], default="warn")
            event_parser.set_defaults(func=cmd_hook)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
