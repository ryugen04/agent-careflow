from __future__ import annotations

import subprocess
from pathlib import Path

DEFAULT_CLAUDE_REVIEW_FALLBACK_MODEL = "sonnet"
DEPRECATED_THINKING_ERROR_TOKENS = (
    "claude-opus-4-6",
    "thinking.type=enabled",
    "deprecated",
)

from .artifacts import ValidationError, case_dir
from .lifecycle import new_review_request, validate_review


def _review_id(order_id: str, review_id: str | None) -> str:
    return review_id or f"REVIEW-CLAUDE-{order_id}"


def _review_path(root: Path, case_id: str, order_id: str, review_id: str | None) -> Path:
    rid = _review_id(order_id, review_id)
    return case_dir(root, case_id) / "reviews" / f"{rid}.review.md"


def build_claude_review_prompt(root: Path, case_id: str, order_id: str, *, review_id: str | None = None, force_request: bool = True) -> str:
    rid = _review_id(order_id, review_id)
    request = new_review_request(root, case_id, tool="claude", order_id=order_id, review_id=rid, force=force_request)
    request_text = request.read_text(encoding="utf-8")
    return (
        request_text
        + "\n## Claude Execution Contract\n\n"
        + "Return only the complete review artifact markdown for EXPECTED_REVIEW_PATH. "
        + "Do not wrap it in prose or code fences.\n\n"
        + "Do not submit an auth-unavailable placeholder. If you cannot perform the review, "
        + "return a review artifact with `status: blocked`, concrete blocker evidence, and no placeholder language.\n"
    )


def _run_claude_command(command: list[str], *, root: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        check=False,
        timeout=timeout,
    )


def _deprecated_default_thinking_error(result: subprocess.CompletedProcess[str]) -> bool:
    text = f"{result.stderr}\n{result.stdout}"
    return result.returncode != 0 and all(token in text for token in DEPRECATED_THINKING_ERROR_TOKENS)


def _claude_review_command(claude_bin: str, prompt: str, *, model: str | None = None) -> list[str]:
    command = [claude_bin, "-p", "--output-format", "text", "--no-session-persistence"]
    if model:
        command.extend(["--model", model])
    command.append(prompt)
    return command


def check_claude_auth(
    root: Path,
    *,
    claude_bin: str = "claude",
    model: str | None = None,
    timeout: int = 60,
) -> dict[str, object]:
    prompt = "Reply with exactly: agent-careflow-claude-auth-ok"
    command = _claude_review_command(claude_bin, prompt, model=model)
    result = _run_claude_command(command, root=root, timeout=timeout)
    fallback_used = False
    effective_model = model
    if model is None and _deprecated_default_thinking_error(result):
        fallback_used = True
        effective_model = DEFAULT_CLAUDE_REVIEW_FALLBACK_MODEL
        command = _claude_review_command(claude_bin, prompt, model=effective_model)
        result = _run_claude_command(command, root=root, timeout=timeout)
    detail = (result.stderr.strip() or result.stdout.strip() or "no output")
    status = "pass" if result.returncode == 0 else "fail"
    return {
        "schema": "agent-careflow.claude_auth.v1",
        "status": status,
        "root": root.resolve().as_posix(),
        "claude_bin": claude_bin,
        "model": effective_model or "default",
        "fallback_used": fallback_used,
        "exit_code": result.returncode,
        "details": detail,
    }


def render_claude_auth_report(report: dict[str, object]) -> str:
    return (
        f"claude-auth={report.get('status')} "
        f"model={report.get('model')} "
        f"fallback_used={str(report.get('fallback_used')).lower()} "
        f"exit={report.get('exit_code')} "
        f"details={report.get('details')}\n"
    )


def run_claude_review(
    root: Path,
    case_id: str,
    order_id: str,
    *,
    review_id: str | None = None,
    claude_bin: str = "claude",
    model: str | None = None,
    dry_run: bool = False,
    timeout: int = 300,
) -> Path:
    rid = _review_id(order_id, review_id)
    prompt = build_claude_review_prompt(root, case_id, order_id, review_id=rid, force_request=True)
    review_path = _review_path(root, case_id, order_id, rid)
    if dry_run:
        return review_path

    command = _claude_review_command(claude_bin, prompt, model=model)
    result = _run_claude_command(command, root=root, timeout=timeout)
    if model is None and _deprecated_default_thinking_error(result):
        command = _claude_review_command(claude_bin, prompt, model=DEFAULT_CLAUDE_REVIEW_FALLBACK_MODEL)
        result = _run_claude_command(command, root=root, timeout=timeout)
    if result.returncode != 0:
        detail = (result.stderr.strip() or result.stdout.strip() or "no output")
        raise ValidationError(f"claude review command failed with exit={result.returncode}: {detail}")
    output = result.stdout.strip()
    if not output:
        raise ValidationError("claude review command produced empty stdout")
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(output + "\n", encoding="utf-8")
    validate_review(review_path, strict=True)
    return review_path
