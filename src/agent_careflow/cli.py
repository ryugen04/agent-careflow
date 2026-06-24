from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .artifacts import ValidationError, case_dir, sha256_file, validate_case, validate_discharge, validate_order, validate_plan, validate_research, write_plan_lock
from .constants import CASES_DIR, RISK_CLASSES
from .context import write_state
from .policy.engine import PolicyEngine
from .hooks.common import evaluate_lifecycle_hook, evaluate_permission_request, evaluate_pre_tool_use, evaluate_session_start, evaluate_user_prompt_submit, load_payload, record_hook_incident
from .hooks import claude as claude_hooks
from .hooks import codex as codex_hooks
from .hooks import cursor as cursor_hooks
from .conformance import append_record, conformance_status, render_status_markdown, validate_file
from .research import scaffold_research
from .templates import render_case, render_discharge, render_plan
from .bootstrap.target_repo import bootstrap_target_repo
from .bootstrap.profiles import install_profile, render_profile, validate_profile
from .lifecycle import advance_phase, case_status, collect_evidence, issue_order, new_incident, new_learning, new_review, new_review_request, promote_learning, require_reviews, validate_result, validate_review
from .claude_review import check_claude_auth, render_claude_auth_report, run_claude_review
from .review_exchange import export_review_bundle, import_review_artifact
from .review_status import render_review_status, review_status
from .repo_status import discover_repositories, render_repo_status
from .orders import order_status, render_order_prompt, render_result_skeleton, write_result_skeleton
from .isolation import cleanup_isolation, create_isolation, export_isolation_patch, plan_isolation, render_isolation_plan
from .takt import analyze_takt_workflow, render_takt_analysis, render_takt_import, render_takt_policy_export
from .doctor import doctor_failed, render_doctor, run_doctor
from .dashboard import render_dashboard, write_dashboard
from .workspace import render_workspace_current, write_workspace
from .acceptance import ensure_acceptance_passed, render_acceptance_report, run_handoff_acceptance, run_install_audit, run_live_claude_transcript_acceptance, run_live_codex_transcript_acceptance, run_objective_audit, run_objective_matrix, run_profile_acceptance, run_transcript_acceptance_from_file, run_transcript_acceptance_from_text
from .codex_wrapper import run_guarded_codex_exec


def ok(message: str) -> int:
    print(message)
    return 0


def fail(error: Exception | str) -> int:
    print(f"error: {error}", file=sys.stderr)
    return 1


def display_path(path: Path, *, root: Path | None = None) -> str:
    base = (root or Path.cwd()).resolve()
    try:
        return path.resolve().relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def cmd_workspace(args: argparse.Namespace) -> int:
    try:
        if args.write:
            written = write_workspace(Path.cwd())
            return ok(f"workspace written: {len(written)} file(s)")
        print(render_workspace_current(Path.cwd()), end="")
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return 0

def cmd_dashboard(args: argparse.Namespace) -> int:
    try:
        if args.write:
            output = write_dashboard(Path.cwd(), Path(args.output) if args.output else None)
            return ok(f"dashboard written: {display_path(output)}")
        print(render_dashboard(Path.cwd()), end="")
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return 0

def cmd_doctor(args: argparse.Namespace) -> int:
    checks = run_doctor(Path.cwd())
    print(render_doctor(checks))
    return 1 if doctor_failed(checks) else 0


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
    (root / "learnings").mkdir()
    (root / "conferences").mkdir()
    (root / "CASE.yaml").write_text(render_case(case_id, args.title, risk), encoding="utf-8")
    (root / "PLAN.md").write_text(render_plan(case_id, args.title, risk), encoding="utf-8")
    (root / "DISCHARGE.md").write_text(render_discharge(case_id), encoding="utf-8")
    try:
        write_state(Path.cwd(), {"active_case": case_id, "active_order": None, "expected_result_path": None, "phase": "planning"})
        validate_case(root / "CASE.yaml")
        validate_plan(root / "PLAN.md")
    except ValidationError as exc:
        return fail(exc)
    return ok(f"created case {case_id}")


def cmd_plan_validate(args: argparse.Namespace) -> int:
    path = case_dir(Path.cwd(), args.case) / "PLAN.md"
    try:
        validate_plan(path, require_lock=args.require_lock, require_signature=args.require_signature, allowed_signers=Path(args.allowed_signers) if args.allowed_signers else None, signing_principal=args.signing_principal)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"plan valid: {display_path(path)}")


def cmd_hash_plan(args: argparse.Namespace) -> int:
    path = case_dir(Path.cwd(), args.case) / "PLAN.md"
    try:
        if args.write_lock:
            lock_path = write_plan_lock(path, signing_key=Path(args.signing_key) if args.signing_key else None, signing_principal=args.signing_principal)
            return ok(f"plan lock written: {display_path(lock_path)}")
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
    return ok(f"order valid: {display_path(path)}")


def cmd_discharge_validate(args: argparse.Namespace) -> int:
    root = case_dir(Path.cwd(), args.case)
    path = root / "DISCHARGE.md"
    try:
        validate_discharge(path, root)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"discharge valid: {display_path(path)}")


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
        result_path = Path(".careflow") / "cases" / args.case / "results" / f"{args.order}.result.md"
        write_state(Path.cwd(), {"active_case": args.case, "active_order": args.order, "expected_result_path": result_path.as_posix(), "phase": "ordered"})
        validate_order(path, Path.cwd())
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"order issued: {display_path(path)}")


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


def cmd_order_result_skeleton(args: argparse.Namespace) -> int:
    try:
        if args.write:
            path = write_result_skeleton(Path.cwd(), args.case, args.order, force=args.force, status=args.status)
            return ok(f"result skeleton written: {display_path(path)}")
        print(render_result_skeleton(Path.cwd(), args.case, args.order, status=args.status), end="")
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return 0


def cmd_result_validate(args: argparse.Namespace) -> int:
    path = case_dir(Path.cwd(), args.case) / "results" / args.result
    try:
        validate_result(path)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"result valid: {display_path(path)}")


def cmd_review_new(args: argparse.Namespace) -> int:
    try:
        path = new_review(
            Path.cwd(),
            args.case,
            tool=args.tool,
            review_id=args.review_id,
            status=args.status,
            scope=args.scope,
            evidence=args.evidence,
            recommendation=args.recommendation,
        )
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"review created: {display_path(path)}")


def cmd_review_require(args: argparse.Namespace) -> int:
    try:
        found = require_reviews(Path.cwd(), args.case, args.tool, strict=args.strict)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    rendered = ", ".join(f"{tool}={display_path(path)}" for tool, path in sorted(found.items()))
    return ok(f"reviews satisfied: {rendered}")


def cmd_review_validate(args: argparse.Namespace) -> int:
    path = case_dir(Path.cwd(), args.case) / "reviews" / args.review
    try:
        validate_review(path, strict=args.strict)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"review valid: {display_path(path)}")


def cmd_review_request(args: argparse.Namespace) -> int:
    try:
        path = new_review_request(Path.cwd(), args.case, tool=args.tool, order_id=args.order, review_id=args.review_id, force=args.force)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"review request written: {display_path(path)}")


def cmd_review_claude_auth(args: argparse.Namespace) -> int:
    try:
        report = check_claude_auth(
            Path.cwd(),
            claude_bin=args.claude_bin,
            model=args.model,
            timeout=args.timeout,
        )
    except (OSError, ValidationError, subprocess.TimeoutExpired) as exc:
        return fail(exc)
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_claude_auth_report(report), end="")
    return 0 if report.get("status") == "pass" else 1


def cmd_review_claude_run(args: argparse.Namespace) -> int:
    try:
        path = run_claude_review(
            Path.cwd(),
            args.case,
            args.order,
            review_id=args.review_id,
            claude_bin=args.claude_bin,
            model=args.model,
            dry_run=args.dry_run,
            timeout=args.timeout,
        )
    except (OSError, ValidationError) as exc:
        return fail(exc)
    action = "review request ready" if args.dry_run else "claude review written"
    return ok(f"{action}: {display_path(path)}")


def cmd_review_export(args: argparse.Namespace) -> int:
    try:
        path = export_review_bundle(
            Path.cwd(),
            args.case,
            args.order,
            tool=args.tool,
            review_id=args.review_id,
            output=Path(args.output) if args.output else None,
        )
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"review bundle exported: {display_path(path)}")


def cmd_review_import(args: argparse.Namespace) -> int:
    try:
        path = import_review_artifact(Path.cwd(), args.case, Path(args.source), strict=args.strict, force=args.force)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"review imported: {display_path(path)}")


def cmd_review_status(args: argparse.Namespace) -> int:
    try:
        status = review_status(Path.cwd(), args.case, profile=args.profile, order_id=args.order)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    if args.format == "json":
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print(render_review_status(status))
    return 0 if status["status"] == "satisfied" else 1


def cmd_repo_status(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else Path.cwd()
    if args.format == "json":
        print(json.dumps({"schema": "agent-careflow.repo_status.v1", "root": root.as_posix(), "repositories": discover_repositories(root)}, indent=2, sort_keys=True))
    else:
        print(render_repo_status(root))
    return 0


def cmd_learning_new(args: argparse.Namespace) -> int:
    try:
        path = new_learning(Path.cwd(), args.case, args.title, source_incident=args.source_incident)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"learning created: {display_path(path)}")


def cmd_learning_promote(args: argparse.Namespace) -> int:
    try:
        path = promote_learning(Path.cwd(), args.case, args.learning, Path(args.target), force=args.force)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"learning promoted: {display_path(path)}")


def cmd_incident_new(args: argparse.Namespace) -> int:
    try:
        path = new_incident(Path.cwd(), args.case, args.trigger)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"incident created: {display_path(path)}")


def cmd_evidence_collect(args: argparse.Namespace) -> int:
    try:
        path = collect_evidence(Path.cwd(), args.case, args.kind)
    except (OSError, ValidationError) as exc:
        return fail(exc)
    return ok(f"evidence collected: {display_path(path)}")


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


def cmd_profile_validate(args: argparse.Namespace) -> int:
    try:
        profile = validate_profile(Path.cwd(), args.name)
    except ValidationError as exc:
        return fail(exc)
    enabled = ",".join(tool for tool, is_enabled in {"codex": profile.codex, "claude": profile.claude, "cursor": profile.cursor}.items() if is_enabled)
    return ok(f"profile valid: {profile.name} tools={enabled}")


def cmd_profile_render(args: argparse.Namespace) -> int:
    try:
        profile = validate_profile(Path.cwd(), args.name)
        written = render_profile(Path.cwd(), profile, Path(args.target))
    except ValidationError as exc:
        return fail(exc)
    return ok(f"profile rendered: {len(written)} file(s)")


def cmd_install(args: argparse.Namespace) -> int:
    try:
        written = install_profile(Path.cwd(), args.profile, Path(args.target).expanduser(), enable=args.enable, disable=args.disable)
    except ValidationError as exc:
        return fail(exc)
    return ok(f"profile installed: {len(written)} file(s)")


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


def cmd_isolation_create(args: argparse.Namespace) -> int:
    try:
        work_dir = create_isolation(target=Path(args.target), case_id=args.case, strategy=args.strategy, base_ref=args.base_ref)
    except ValidationError as exc:
        return fail(exc)
    return ok(f"isolation created: {work_dir}")


def cmd_isolation_cleanup(args: argparse.Namespace) -> int:
    try:
        work_dir = cleanup_isolation(target=Path(args.target), case_id=args.case, strategy=args.strategy, work_dir=Path(args.work_dir) if args.work_dir else None, force=args.force)
    except ValidationError as exc:
        return fail(exc)
    return ok(f"isolation cleaned: {work_dir}")


def cmd_isolation_export_patch(args: argparse.Namespace) -> int:
    try:
        output = export_isolation_patch(work_dir=Path(args.work_dir), output=Path(args.output))
    except ValidationError as exc:
        return fail(exc)
    return ok(f"isolation patch written: {output}")


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


def cmd_takt_import_workflow(args: argparse.Namespace) -> int:
    try:
        report = render_takt_import(Path(args.workflow))
    except ValidationError as exc:
        return fail(exc)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        return ok(f"takt import written: {output}")
    print(report)
    return 0


def cmd_takt_export_policy(args: argparse.Namespace) -> int:
    report = render_takt_policy_export(Path.cwd())
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        return ok(f"takt policy written: {output}")
    print(report)
    return 0


def _print_acceptance_and_status(report: dict[str, object], *, fmt: str) -> int:
    print(render_acceptance_report(report, fmt=fmt), end="")
    try:
        ensure_acceptance_passed(report)
    except ValidationError:
        return 1
    return 0


def cmd_acceptance_profile(args: argparse.Namespace) -> int:
    try:
        report = run_profile_acceptance(Path.cwd(), args.profile, Path(args.target))
    except ValidationError as exc:
        return fail(exc)
    return _print_acceptance_and_status(report, fmt=args.format)


def cmd_acceptance_handoff(args: argparse.Namespace) -> int:
    try:
        report = run_handoff_acceptance(Path(args.target))
    except ValidationError as exc:
        return fail(exc)
    return _print_acceptance_and_status(report, fmt=args.format)


def cmd_acceptance_install_audit(args: argparse.Namespace) -> int:
    try:
        report = run_install_audit(Path(args.careflow_repo), Path(args.target_home), args.tool)
    except ValidationError as exc:
        return fail(exc)
    return _print_acceptance_and_status(report, fmt=args.format)


def cmd_acceptance_objective_audit(args: argparse.Namespace) -> int:
    try:
        report = run_objective_audit(Path(args.careflow_repo), args.case, profile=args.profile)
    except ValidationError as exc:
        return fail(exc)
    return _print_acceptance_and_status(report, fmt=args.format)


def cmd_acceptance_objective_matrix(args: argparse.Namespace) -> int:
    try:
        report = run_objective_matrix(Path(args.careflow_repo), args.case, profile=args.profile)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return _print_acceptance_and_status(report, fmt=args.format)


def cmd_acceptance_transcript(args: argparse.Namespace) -> int:
    try:
        if args.live_codex:
            report = run_live_codex_transcript_acceptance(Path(args.workdir), output=Path(args.output) if args.output else None, timeout=args.timeout)
        elif args.live_claude:
            report = run_live_claude_transcript_acceptance(Path(args.workdir), timeout=args.timeout)
        elif args.file:
            report = run_transcript_acceptance_from_file(Path(args.file))
        else:
            report = run_transcript_acceptance_from_text(sys.stdin.read(), label="stdin")
    except (OSError, subprocess.TimeoutExpired, ValidationError) as exc:
        return fail(exc)
    return _print_acceptance_and_status(report, fmt=args.format)


def cmd_codex_exec(args: argparse.Namespace) -> int:
    stdin_text = sys.stdin.read() if not sys.stdin.isatty() else ""
    codex_args = list(args.codex_args or [])
    if codex_args and codex_args[0] == "--":
        codex_args = codex_args[1:]
    try:
        result = run_guarded_codex_exec(
            codex_args,
            stdin_text=stdin_text,
            codex_bin=args.codex_bin,
            dry_run=args.dry_run,
            probe_output=Path(args.probe_output) if args.probe_output else None,
            cwd=Path.cwd(),
        )
    except OSError as exc:
        return fail(exc)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.exit_code


def cmd_conformance_record(args: argparse.Namespace) -> int:
    try:
        append_record(output=Path(args.output), adapter=args.adapter, event=args.event, fixture=Path(args.fixture), notes=args.notes)
    except ValidationError as exc:
        return fail(exc)
    return ok(f"conformance record written: {args.output}")


def cmd_conformance_validate(args: argparse.Namespace) -> int:
    try:
        count = validate_file(Path(args.input))
    except ValidationError as exc:
        return fail(exc)
    return ok(f"conformance valid: {args.input} ({count} record(s))")


def cmd_conformance_status(args: argparse.Namespace) -> int:
    try:
        status = conformance_status(root=Path.cwd())
    except ValidationError as exc:
        return fail(exc)
    rendered = render_status_markdown(status) if args.format == "markdown" else json.dumps(status, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        return ok(f"conformance status written: {output}")
    print(rendered, end="")
    return 0


def cmd_hook(args: argparse.Namespace) -> int:
    try:
        payload = load_payload(sys.stdin.read())
        if args.event == "session-start":
            decision = evaluate_session_start(payload)
        elif args.event == "permission-request":
            decision = evaluate_permission_request(payload, on_missing_context=args.on_missing_context)
        elif args.event == "user-prompt-submit":
            decision = evaluate_user_prompt_submit(payload)
        elif args.event in {"stop", "subagent-start", "subagent-stop"}:
            decision = evaluate_lifecycle_hook(payload)
        else:
            decision = evaluate_pre_tool_use(payload, on_missing_context=args.on_missing_context)
        if getattr(args, "incident_on_deny", False):
            record_hook_incident(payload, decision)
    except ValidationError as exc:
        return fail(exc)

    if args.tool == "codex":
        if args.event == "session-start":
            print(codex_hooks.render_session_start(decision))
        elif args.event == "permission-request":
            print(codex_hooks.render_permission_request(decision))
        elif args.event == "user-prompt-submit":
            print(codex_hooks.render_user_prompt_submit(decision))
        elif args.event == "post-tool-use":
            print(codex_hooks.render_post_tool_use(decision))
        elif args.event == "stop":
            print(codex_hooks.render_stop(decision))
        else:
            print(codex_hooks.render_pre_tool_use(decision))
    elif args.tool == "claude":
        if args.event == "session-start":
            print(claude_hooks.render_session_start(decision))
        elif args.event == "post-tool-use":
            print(claude_hooks.render_post_tool_use(decision))
        elif args.event == "stop":
            print(claude_hooks.render_stop(decision))
        elif args.event == "subagent-start":
            print(claude_hooks.render_subagent_start(decision))
        elif args.event == "subagent-stop":
            print(claude_hooks.render_subagent_stop(decision))
        else:
            print(claude_hooks.render_pre_tool_use(decision))
    else:
        if args.event == "post-tool-use":
            print(cursor_hooks.render_post_tool_use(decision))
        elif args.event == "stop":
            print(cursor_hooks.render_stop(decision))
        else:
            print(cursor_hooks.render_pre_tool_use(decision))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-careflow")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.set_defaults(func=cmd_init)

    doctor = sub.add_parser("doctor")
    doctor.set_defaults(func=cmd_doctor)

    dashboard = sub.add_parser("dashboard")
    dashboard.add_argument("--write", action="store_true")
    dashboard.add_argument("--output")
    dashboard.set_defaults(func=cmd_dashboard)

    workspace = sub.add_parser("workspace")
    workspace.add_argument("--write", action="store_true")
    workspace.set_defaults(func=cmd_workspace)

    bootstrap = sub.add_parser("bootstrap")
    bootstrap.add_argument("--target", default=".")
    bootstrap.add_argument("--profile", default="business")
    bootstrap.add_argument("--careflow-repo", default=str(Path.cwd()))
    bootstrap.set_defaults(func=cmd_bootstrap)

    install = sub.add_parser("install")
    install.add_argument("--profile", required=True)
    install.add_argument("--target", default="~/.agent-careflow/rendered")
    install.add_argument("--enable", action="append", choices=["codex", "claude", "cursor"], default=[])
    install.add_argument("--disable", action="append", choices=["codex", "claude", "cursor"], default=[])
    install.set_defaults(func=cmd_install)

    profile = sub.add_parser("profile")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    profile_validate = profile_sub.add_parser("validate")
    profile_validate.add_argument("name")
    profile_validate.set_defaults(func=cmd_profile_validate)
    profile_render = profile_sub.add_parser("render")
    profile_render.add_argument("name")
    profile_render.add_argument("--target", required=True)
    profile_render.set_defaults(func=cmd_profile_render)

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
    plan_validate.add_argument("--require-signature", action="store_true")
    plan_validate.add_argument("--allowed-signers")
    plan_validate.add_argument("--signing-principal")
    plan_validate.set_defaults(func=cmd_plan_validate)

    hash_cmd = sub.add_parser("hash")
    hash_sub = hash_cmd.add_subparsers(dest="hash_command", required=True)
    hash_plan = hash_sub.add_parser("plan")
    hash_plan.add_argument("--case", required=True)
    hash_plan.add_argument("--write-lock", action="store_true")
    hash_plan.add_argument("--signing-key")
    hash_plan.add_argument("--signing-principal")
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
    order_result_skeleton = order_sub.add_parser("result-skeleton")
    order_result_skeleton.add_argument("--case", required=True)
    order_result_skeleton.add_argument("--order", required=True)
    order_result_skeleton.add_argument("--status", default="complete")
    order_result_skeleton.add_argument("--write", action="store_true")
    order_result_skeleton.add_argument("--force", action="store_true")
    order_result_skeleton.set_defaults(func=cmd_order_result_skeleton)

    result = sub.add_parser("result")
    result_sub = result.add_subparsers(dest="result_command", required=True)
    result_validate = result_sub.add_parser("validate")
    result_validate.add_argument("--case", required=True)
    result_validate.add_argument("--result", required=True)
    result_validate.set_defaults(func=cmd_result_validate)

    review = sub.add_parser("review")
    repo = sub.add_parser("repo")
    repo_sub = repo.add_subparsers(dest="repo_command", required=True)
    repo_status = repo_sub.add_parser("status")
    repo_status.add_argument("--root")
    repo_status.add_argument("--format", choices=["text", "json"], default="text")
    repo_status.set_defaults(func=cmd_repo_status)

    review_sub = review.add_subparsers(dest="review_command", required=True)
    review_new = review_sub.add_parser("new")
    review_new.add_argument("--case", required=True)
    review_new.add_argument("--tool", choices=["codex", "claude", "cursor", "human"], required=True)
    review_new.add_argument("--review-id")
    review_new.add_argument("--status", choices=["pass", "needs_changes", "blocked"], default="pass")
    review_new.add_argument("--scope", default="PLAN, ORDER, RESULT, and evidence")
    review_new.add_argument("--evidence", default="See case evidence directory")
    review_new.add_argument("--recommendation", default="No blocking findings recorded.")
    review_new.set_defaults(func=cmd_review_new)
    review_require = review_sub.add_parser("require")
    review_require.add_argument("--case", required=True)
    review_require.add_argument("--tool", action="append", choices=["codex", "claude", "cursor", "human"], required=True)
    review_require.add_argument("--strict", action="store_true")
    review_require.set_defaults(func=cmd_review_require)
    review_request = review_sub.add_parser("request")
    review_request.add_argument("--case", required=True)
    review_request.add_argument("--tool", choices=["codex", "claude", "cursor", "human"], required=True)
    review_request.add_argument("--order", required=True)
    review_request.add_argument("--review-id")
    review_request.add_argument("--force", action="store_true")
    review_request.set_defaults(func=cmd_review_request)
    review_claude_auth = review_sub.add_parser("claude-auth")
    review_claude_auth.add_argument("--claude-bin", default="claude")
    review_claude_auth.add_argument("--model")
    review_claude_auth.add_argument("--timeout", type=int, default=60)
    review_claude_auth.add_argument("--format", choices=["text", "json"], default="text")
    review_claude_auth.set_defaults(func=cmd_review_claude_auth)
    review_claude_run = review_sub.add_parser("claude-run")
    review_claude_run.add_argument("--case", required=True)
    review_claude_run.add_argument("--order", required=True)
    review_claude_run.add_argument("--review-id")
    review_claude_run.add_argument("--claude-bin", default="claude")
    review_claude_run.add_argument("--model")
    review_claude_run.add_argument("--dry-run", action="store_true")
    review_claude_run.add_argument("--timeout", type=int, default=300)
    review_claude_run.set_defaults(func=cmd_review_claude_run)
    review_export = review_sub.add_parser("export")
    review_export.add_argument("--case", required=True)
    review_export.add_argument("--tool", choices=["codex", "claude", "cursor", "human"], required=True)
    review_export.add_argument("--order", required=True)
    review_export.add_argument("--review-id")
    review_export.add_argument("--output")
    review_export.set_defaults(func=cmd_review_export)
    review_import = review_sub.add_parser("import")
    review_import.add_argument("--case", required=True)
    review_import.add_argument("--source", required=True)
    review_import.add_argument("--strict", action="store_true")
    review_import.add_argument("--force", action="store_true")
    review_import.set_defaults(func=cmd_review_import)
    review_status_parser = review_sub.add_parser("status")
    review_status_parser.add_argument("--case", required=True)
    review_status_parser.add_argument("--profile", choices=["business", "private"], default="business")
    review_status_parser.add_argument("--order", required=True)
    review_status_parser.add_argument("--format", choices=["text", "json"], default="text")
    review_status_parser.set_defaults(func=cmd_review_status)
    review_validate = review_sub.add_parser("validate")
    review_validate.add_argument("--case", required=True)
    review_validate.add_argument("--review", required=True)
    review_validate.add_argument("--strict", action="store_true")
    review_validate.set_defaults(func=cmd_review_validate)

    incident = sub.add_parser("incident")
    incident_sub = incident.add_subparsers(dest="incident_command", required=True)
    incident_new = incident_sub.add_parser("new")
    incident_new.add_argument("--case", required=True)
    incident_new.add_argument("--trigger", required=True)
    incident_new.set_defaults(func=cmd_incident_new)

    learning = sub.add_parser("learning")
    learning_sub = learning.add_subparsers(dest="learning_command", required=True)
    learning_new = learning_sub.add_parser("new")
    learning_new.add_argument("--case", required=True)
    learning_new.add_argument("--title", required=True)
    learning_new.add_argument("--source-incident")
    learning_new.set_defaults(func=cmd_learning_new)
    learning_promote = learning_sub.add_parser("promote")
    learning_promote.add_argument("--case", required=True)
    learning_promote.add_argument("--learning", required=True)
    learning_promote.add_argument("--target", required=True)
    learning_promote.add_argument("--force", action="store_true")
    learning_promote.set_defaults(func=cmd_learning_promote)

    evidence = sub.add_parser("evidence")
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_collect = evidence_sub.add_parser("collect")
    evidence_collect.add_argument("--case", required=True)
    evidence_collect.add_argument("--kind", choices=["git-status"], required=True)
    evidence_collect.set_defaults(func=cmd_evidence_collect)

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
    isolation_create = isolation_sub.add_parser("create")
    isolation_create.add_argument("--target", default=".")
    isolation_create.add_argument("--case", required=True)
    isolation_create.add_argument("--strategy", choices=["worktree", "shared-clone", "temp-clone"], default="worktree")
    isolation_create.add_argument("--base-ref", default="HEAD")
    isolation_create.set_defaults(func=cmd_isolation_create)
    isolation_cleanup = isolation_sub.add_parser("cleanup")
    isolation_cleanup.add_argument("--target", default=".")
    isolation_cleanup.add_argument("--case", required=True)
    isolation_cleanup.add_argument("--strategy", choices=["worktree", "shared-clone", "temp-clone"], default="worktree")
    isolation_cleanup.add_argument("--work-dir")
    isolation_cleanup.add_argument("--force", action="store_true")
    isolation_cleanup.set_defaults(func=cmd_isolation_cleanup)
    isolation_export = isolation_sub.add_parser("export-patch")
    isolation_export.add_argument("--work-dir", required=True)
    isolation_export.add_argument("--output", required=True)
    isolation_export.set_defaults(func=cmd_isolation_export_patch)

    takt = sub.add_parser("takt")
    takt_sub = takt.add_subparsers(dest="takt_command", required=True)
    takt_analyze = takt_sub.add_parser("analyze")
    takt_analyze.add_argument("--workflow", required=True)
    takt_analyze.add_argument("--output")
    takt_analyze.set_defaults(func=cmd_takt_analyze)
    takt_import = takt_sub.add_parser("import-workflow")
    takt_import.add_argument("--workflow", required=True)
    takt_import.add_argument("--output")
    takt_import.set_defaults(func=cmd_takt_import_workflow)
    takt_export = takt_sub.add_parser("export-policy")
    takt_export.add_argument("--output")
    takt_export.set_defaults(func=cmd_takt_export_policy)

    acceptance = sub.add_parser("acceptance")
    acceptance_sub = acceptance.add_subparsers(dest="acceptance_command", required=True)
    acceptance_profile = acceptance_sub.add_parser("profile")
    acceptance_profile.add_argument("--profile", required=True)
    acceptance_profile.add_argument("--target", required=True)
    acceptance_profile.add_argument("--format", choices=["text", "json"], default="text")
    acceptance_profile.set_defaults(func=cmd_acceptance_profile)
    acceptance_handoff = acceptance_sub.add_parser("handoff")
    acceptance_handoff.add_argument("--target", required=True)
    acceptance_handoff.add_argument("--format", choices=["text", "json"], default="text")
    acceptance_handoff.set_defaults(func=cmd_acceptance_handoff)
    acceptance_install_audit = acceptance_sub.add_parser("install-audit")
    acceptance_install_audit.add_argument("--target-home", required=True)
    acceptance_install_audit.add_argument("--careflow-repo", default=str(Path.cwd()))
    acceptance_install_audit.add_argument("--tool", action="append", choices=["codex", "claude"], default=[])
    acceptance_install_audit.add_argument("--format", choices=["text", "json"], default="text")
    acceptance_install_audit.set_defaults(func=cmd_acceptance_install_audit)
    acceptance_objective = acceptance_sub.add_parser("objective-audit")
    acceptance_objective.add_argument("--case", default="ACF-RELIABILITY-SUPERPOWERS")
    acceptance_objective.add_argument("--careflow-repo", default=str(Path.cwd()))
    acceptance_objective.add_argument("--profile", choices=["business", "private"], default="business")
    acceptance_objective.add_argument("--format", choices=["text", "json"], default="text")
    acceptance_objective.set_defaults(func=cmd_acceptance_objective_audit)
    acceptance_matrix = acceptance_sub.add_parser("objective-matrix")
    acceptance_matrix.add_argument("--case", default="ACF-RELIABILITY-SUPERPOWERS")
    acceptance_matrix.add_argument("--careflow-repo", default=str(Path.cwd()))
    acceptance_matrix.add_argument("--profile", choices=["business", "private"], default="business")
    acceptance_matrix.add_argument("--format", choices=["text", "json"], default="text")
    acceptance_matrix.set_defaults(func=cmd_acceptance_objective_matrix)
    acceptance_transcript = acceptance_sub.add_parser("transcript")
    acceptance_transcript.add_argument("--file")
    acceptance_transcript.add_argument("--live-codex", action="store_true")
    acceptance_transcript.add_argument("--live-claude", action="store_true")
    acceptance_transcript.add_argument("--workdir", default="/tmp/agent-careflow-live-codex")
    acceptance_transcript.add_argument("--output")
    acceptance_transcript.add_argument("--timeout", type=int, default=120)
    acceptance_transcript.add_argument("--format", choices=["text", "json"], default="text")
    acceptance_transcript.set_defaults(func=cmd_acceptance_transcript)

    codex_cmd = sub.add_parser("codex")
    codex_sub = codex_cmd.add_subparsers(dest="codex_command", required=True)
    codex_exec = codex_sub.add_parser("exec")
    codex_exec.add_argument("--codex-bin", default="codex")
    codex_exec.add_argument("--dry-run", action="store_true")
    codex_exec.add_argument("--probe-output")
    codex_exec.add_argument("codex_args", nargs=argparse.REMAINDER)
    codex_exec.set_defaults(func=cmd_codex_exec)

    conformance = sub.add_parser("conformance")
    conformance_sub = conformance.add_subparsers(dest="conformance_command", required=True)
    conformance_record = conformance_sub.add_parser("record")
    conformance_record.add_argument("--adapter", choices=["codex", "claude", "cursor"], required=True)
    conformance_record.add_argument("--event", required=True)
    conformance_record.add_argument("--fixture", required=True)
    conformance_record.add_argument("--output", required=True)
    conformance_record.add_argument("--notes", default="fixture replay")
    conformance_record.set_defaults(func=cmd_conformance_record)
    conformance_validate = conformance_sub.add_parser("validate")
    conformance_validate.add_argument("--input", required=True)
    conformance_validate.set_defaults(func=cmd_conformance_validate)
    conformance_status_parser = conformance_sub.add_parser("status")
    conformance_status_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    conformance_status_parser.add_argument("--output")
    conformance_status_parser.set_defaults(func=cmd_conformance_status)

    hook = sub.add_parser("hook")
    hook_sub = hook.add_subparsers(dest="tool", required=True)
    for tool_name in ("codex", "claude", "cursor"):
        tool_parser = hook_sub.add_parser(tool_name)
        event_sub = tool_parser.add_subparsers(dest="event", required=True)
        events = ["session-start", "pre-tool-use", "post-tool-use", "stop"]
        if tool_name == "codex":
            events.extend(["permission-request", "user-prompt-submit"])
        if tool_name == "claude":
            events.extend(["subagent-start", "subagent-stop"])
        for event_name in events:
            event_parser = event_sub.add_parser(event_name)
            event_parser.add_argument("--on-missing-context", choices=["warn", "deny", "hybrid"], default="warn")
            event_parser.add_argument("--incident-on-deny", action="store_true")
            event_parser.set_defaults(func=cmd_hook)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
