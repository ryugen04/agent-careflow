from __future__ import annotations

from pathlib import Path

from .artifacts import parse_front_matter_lines
from .constants import CARE_DIR
from .context import find_workflow_root, read_state


DASHBOARD_PATH = Path(CARE_DIR) / "INDEX.md"


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _link(root: Path, path: Path, label: str | None = None) -> str:
    rel = _rel(root, path)
    text = label or rel
    return f"[{text}]({rel})"


def _read_data(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return parse_front_matter_lines(path.read_text(encoding="utf-8", errors="replace"))


def _order_path(case_root: Path, order_id: str | None) -> Path | None:
    if not order_id:
        return None
    name = order_id if order_id.endswith(".order.md") else f"{order_id}.order.md"
    return case_root / "orders" / name


def _result_path(root: Path, case_root: Path, expected: str | None, order_id: str | None) -> Path | None:
    if expected:
        candidate = Path(expected)
        return candidate if candidate.is_absolute() else root / candidate
    if order_id:
        return case_root / "results" / f"{order_id}.result.md"
    return None


def _listed_files(directory: Path, pattern: str = "*") -> list[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.glob(pattern) if path.is_file())


def _status_files(files: list[Path], *, status: str | None = None) -> list[Path]:
    if status is None:
        return files
    matched = []
    for path in files:
        data = _read_data(path)
        if str(data.get("status") or "").lower() == status:
            matched.append(path)
    return matched


def _bullet_links(root: Path, files: list[Path], empty: str) -> list[str]:
    if not files:
        return [f"- {empty}"]
    return [f"- {_link(root, path)}" for path in files]


def render_dashboard(cwd: Path) -> str:
    root = find_workflow_root(cwd)
    state = read_state(root)
    active_case = state.get("active_case") if isinstance(state.get("active_case"), str) else None
    active_order = state.get("active_order") if isinstance(state.get("active_order"), str) else None
    expected_result = state.get("expected_result_path") if isinstance(state.get("expected_result_path"), str) else None
    phase = state.get("phase") if isinstance(state.get("phase"), str) else "unknown"

    lines = [
        "# Agent Careflow Index",
        "",
        f"workflow_root: `{root.as_posix()}`",
        f"state_file: `{CARE_DIR}/state.json`",
        f"active_case: `{active_case or 'none'}`",
        f"active_order: `{active_order or 'none'}`",
        f"phase: `{phase}`",
        "",
    ]
    if not active_case:
        lines.extend([
            "## Active Work",
            "",
            'No active case is recorded. Create one with `agent-careflow case new --title "..." --risk C1`.',
            "",
        ])
        return "\n".join(lines).rstrip() + "\n"

    case_root = root / CARE_DIR / "cases" / active_case
    case_path = case_root / "CASE.yaml"
    plan_path = case_root / "PLAN.md"
    order_path = _order_path(case_root, active_order)
    result_path = _result_path(root, case_root, expected_result, active_order)
    case_data = _read_data(case_path)
    plan_data = _read_data(plan_path)

    lines.extend([
        "## Active Work",
        "",
        f"- Case: {_link(root, case_path, active_case)}",
        f"- Title: {case_data.get('title') or plan_data.get('title') or 'unknown'}",
        f"- Risk: `{case_data.get('risk') or plan_data.get('risk') or 'unknown'}`",
        f"- PLAN_FILE: {_link(root, plan_path)}",
    ])
    if order_path:
        lines.append(f"- ORDER_FILE: {_link(root, order_path)}")
        lines.append(f"- SUBPLAN_FILE: {_link(root, order_path)}")
    else:
        lines.append("- ORDER_FILE: `none`")
        lines.append("- SUBPLAN_FILE: `none`")
    if result_path:
        status = "exists" if result_path.exists() else "missing"
        lines.append(f"- EXPECTED_RESULT_PATH: {_link(root, result_path)} (`{status}`)")
    else:
        lines.append("- EXPECTED_RESULT_PATH: `none`")
    lines.extend(["", "## Handoff Header", "", "```text"])
    lines.extend([
        f"PLAN_FILE: {_rel(root, plan_path)}",
        f"ORDER_FILE: {_rel(root, order_path) if order_path else 'none'}",
        f"SUBPLAN_FILE: {_rel(root, order_path) if order_path else 'none'}",
        f"EXPECTED_RESULT_PATH: {_rel(root, result_path) if result_path else 'none'}",
        f"CASE_ID: {active_case}",
        f"ORDER_ID: {active_order or 'none'}",
        "ASSIGNED_ROLE: <researcher|implementer|verifier|reviewer|incident-commander>",
        "TARGET_TOOL: <codex|claude|cursor>",
        "```",
        "",
    ])

    evidence = _listed_files(case_root / "evidence")
    results = _listed_files(case_root / "results", "*.result.md")
    orders = _listed_files(case_root / "orders", "*.order.md")
    reviews = _listed_files(case_root / "reviews")
    incidents = _listed_files(case_root / "incidents")
    open_incidents = _status_files(incidents, status="open")
    learnings = _listed_files(case_root / "learnings")

    lines.extend(["## Orders", "", *_bullet_links(root, orders, "No orders recorded."), ""])
    lines.extend(["## Results", "", *_bullet_links(root, results, "No results recorded."), ""])
    lines.extend(["## Evidence", "", *_bullet_links(root, evidence, "No evidence files recorded."), ""])
    lines.extend(["## Open Incidents", "", *_bullet_links(root, open_incidents, "No open incidents."), ""])
    lines.extend(["## Reviews", "", *_bullet_links(root, reviews, "No review artifacts recorded."), ""])
    lines.extend(["## Learnings", "", *_bullet_links(root, learnings, "No learning artifacts recorded."), ""])
    lines.extend([
        "## Next Step",
        "",
        "1. Read PLAN_FILE and ORDER_FILE before mutating files.",
        "2. Keep this index open when handing work to Claude, Codex, Cursor, or a subagent.",
        "3. Write EXPECTED_RESULT_PATH before claiming completion.",
        "",
    ])
    return "\n".join(lines).rstrip() + "\n"


def write_dashboard(cwd: Path, output: Path | None = None) -> Path:
    root = find_workflow_root(cwd)
    path = output or (root / DASHBOARD_PATH)
    if not path.is_absolute():
        path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard(cwd), encoding="utf-8")
    return path
