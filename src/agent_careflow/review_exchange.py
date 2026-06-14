from __future__ import annotations

from pathlib import Path

from .artifacts import ValidationError, case_dir, parse_front_matter_lines
from .lifecycle import new_review_request, validate_review


def _review_id(tool: str, order_id: str, review_id: str | None) -> str:
    return review_id or f"REVIEW-{tool.upper()}-{order_id}"


def export_review_bundle(root: Path, case_id: str, order_id: str, *, tool: str, review_id: str | None = None, output: Path | None = None) -> Path:
    rid = _review_id(tool, order_id, review_id)
    request = new_review_request(root, case_id, tool=tool, order_id=order_id, review_id=rid, force=True)
    text = request.read_text(encoding="utf-8")
    output_path = output or request
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        text
        + "\n## Return Path\n\n"
        + "After the reviewer writes the `.review.md` artifact, import it on the control machine with:\n\n"
        + f"```bash\nagent-careflow review import --case {case_id} --source /path/to/{rid}.review.md --strict\n```\n",
        encoding="utf-8",
    )
    return output_path


def import_review_artifact(root: Path, case_id: str, source: Path, *, strict: bool = True, force: bool = False) -> Path:
    if not source.exists() or source.is_dir():
        raise ValidationError(f"review source not found: {source}")
    text = source.read_text(encoding="utf-8")
    data = parse_front_matter_lines(text)
    if str(data.get("case_id") or "") != case_id:
        raise ValidationError(f"{source}: review case_id does not match {case_id}")
    review_id = str(data.get("review_id") or "")
    if not review_id:
        raise ValidationError(f"{source}: missing review_id")
    target = case_dir(root, case_id) / "reviews" / f"{review_id}.review.md"
    if target.exists() and not force:
        raise ValidationError(f"review exists: {target.name}; use --force to overwrite")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    try:
        validate_review(target, strict=strict)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target
