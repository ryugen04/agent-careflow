from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .artifacts import ValidationError

KEYWORD_MAP = {
    "persona": "ORDER.assigned_role",
    "role": "ORDER.assigned_role",
    "policy": "POLICY / phase gate",
    "rule": "POLICY / phase gate",
    "knowledge": "PLAN context / research evidence",
    "instruction": "ORDER allowed_actions",
    "output": "ORDER deliverables / RESULT",
    "review": "REVIEW artifact",
    "fix": "remediation phase / follow-up ORDER",
    "provider": "adapter profile",
    "worktree": "isolation strategy",
    "clone": "isolation strategy",
}


@dataclass(frozen=True)
class TaktAnalysis:
    source: Path
    mappings: dict[str, str]
    risks: list[str]
    recommendation: str


def analyze_takt_workflow(path: Path) -> TaktAnalysis:
    if not path.exists():
        raise ValidationError(f"workflow not found: {path}")
    text = path.read_text(encoding="utf-8").lower()
    mappings: dict[str, str] = {}
    for keyword, target in KEYWORD_MAP.items():
        if re.search(rf"\b{re.escape(keyword)}\b", text):
            mappings[keyword] = target
    risks: list[str] = []
    if "policy" in mappings and "output" not in mappings:
        risks.append("policy appears without an explicit output/result contract")
    if "persona" in mappings and "policy" not in mappings and "rule" not in mappings:
        risks.append("persona appears without an explicit policy boundary")
    if not mappings:
        risks.append("no recognized TAKT-style workflow concepts found")
    recommendation = "Keep TAKT as an interop/comparison target; do not make it a v0.x dependency."
    return TaktAnalysis(source=path, mappings=mappings, risks=risks, recommendation=recommendation)


def render_takt_analysis(analysis: TaktAnalysis) -> str:
    mapping_lines = [f"| {key} | {value} |" for key, value in sorted(analysis.mappings.items())]
    if not mapping_lines:
        mapping_lines = ["| none | no mapping |"]
    risk_lines = [f"- {risk}" for risk in analysis.risks] or ["- none"]
    return "\n".join(
        [
            f"# TAKT Analysis: {analysis.source}",
            "",
            "## Concept mapping",
            "",
            "| TAKT signal | agent-careflow mapping |",
            "|---|---|",
            *mapping_lines,
            "",
            "## Risks",
            "",
            *risk_lines,
            "",
            "## Recommendation",
            "",
            analysis.recommendation,
            "",
        ]
    )
