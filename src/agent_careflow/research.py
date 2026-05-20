from __future__ import annotations

from pathlib import Path

from .constants import REQUIRED_RESEARCH_REPORTS

REPORT_TEMPLATE = """# {title}

checked_at: 2026-05-20T00:00:00+09:00
owner: researcher
status: draft

## Scope

TBD.

## Sources

| source | type | date checked | authority | notes |
|---|---|---:|---|---|
| TBD | TBD | 2026-05-20 | A | placeholder |

## Verified facts

TBD.

## Implementation implications

TBD.

## Risks / caveats

TBD.

## Open questions

TBD.

## Decisions proposed

TBD.

## References to add to PLAN

TBD.
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
            '{\n  "sources": [\n    {"id": "placeholder", "title": "Placeholder official source", "url": "https://example.com", "authority": "A", "type": "official docs"}\n  ]\n}\n',
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
