from __future__ import annotations

from pathlib import Path

from agent_careflow.takt import analyze_takt_workflow, render_takt_analysis, render_takt_import, render_takt_policy_export


def test_takt_analysis_maps_known_concepts(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text("""persona: reviewer
policy: read-only
output: review report
worktree: true
""", encoding="utf-8")

    analysis = analyze_takt_workflow(workflow)
    rendered = render_takt_analysis(analysis)

    assert analysis.mappings["persona"] == "ORDER.assigned_role"
    assert analysis.mappings["policy"] == "POLICY / phase gate"
    assert analysis.mappings["output"] == "ORDER deliverables / RESULT"
    assert "isolation strategy" in rendered
    assert "do not make it a v0.x dependency" in rendered


def test_takt_analysis_flags_persona_without_policy(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text("persona: implementer\noutput: patch\n", encoding="utf-8")

    analysis = analyze_takt_workflow(workflow)

    assert any("persona" in risk for risk in analysis.risks)

def test_takt_import_renders_suggested_order(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text("""persona: reviewer
policy: read-only
output: review report
""", encoding="utf-8")

    rendered = render_takt_import(workflow)

    assert "# TAKT Import" in rendered
    assert "assigned_role: reviewer" in rendered
    assert "review report" in rendered
    assert "POLICY / phase gate" in rendered


def test_takt_policy_export_includes_global_policy_files() -> None:
    rendered = render_takt_policy_export(Path.cwd())

    assert "# TAKT Policy Export" in rendered
    assert "command-policy.yaml" in rendered
    assert "phase-policy.yaml" in rendered
