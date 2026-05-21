from __future__ import annotations

from pathlib import Path

from .constants import REQUIRED_RESEARCH_REPORTS

REPORT_TEMPLATE = """# {title}

checked_at: 2026-05-20T00:00:00+09:00
owner: researcher
status: draft

## Scope

Initial draft scope. Replace this with the concrete question, adapter surface, policy area, or workflow pattern being evaluated before marking the report reviewed.

## Sources

| source | type | date checked | authority | notes |
|---|---|---:|---|---|
| Initial official source required | official docs | 2026-05-20 | A | add concrete source before acceptance |

## Verified facts

No verified facts have been accepted yet. Draft reports must not be used as policy authority until this section is updated from sources.

## Implementation implications

No implementation implication is accepted yet. Add concrete implications only after verified facts are recorded.

## Risks / caveats

Draft report. Treat all claims as unreviewed until status is changed to reviewed or accepted.

## Open questions

- Which facts need official-source confirmation?

## Decisions proposed

- Keep this report in draft until source-backed facts are added.

## References to add to PLAN

- None until reviewed.
"""

def scaffold_research(root: Path) -> list[Path]:
    research_dir = root / "research"
    research_dir.mkdir(exist_ok=True)
    written: list[Path] = []
    readme = research_dir / "README.md"
    if not readme.exists():
        readme.write_text("# agent-careflow Research\n", encoding="utf-8")
        written.append(readme)
    registry = research_dir / "source-registry.json"
    if not registry.exists():
        registry.write_text(
            '{\n  "sources": [\n    {"id": "initial-official-source-required", "title": "Initial official source required", "url": "https://example.com/replace-before-acceptance", "authority": "A", "type": "official docs"}\n  ]\n}\n',
            encoding="utf-8",
        )
        written.append(registry)
    for name in REQUIRED_RESEARCH_REPORTS:
        path = research_dir / name
        if not path.exists():
            title = name.removesuffix(".md").replace("-", " ").title()
            path.write_text(REPORT_TEMPLATE.format(title=title), encoding="utf-8")
            written.append(path)
    return written
