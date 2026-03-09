"""MCP resources exposed by cwtwb."""

from __future__ import annotations

from ..config import SKILLS_DIR, TABLEAU_FUNCTIONS_JSON
from .app import server


@server.resource("file://docs/tableau_all_functions.json")
def read_tableau_functions() -> str:
    """Read the complete list of Tableau calculation functions."""

    if not TABLEAU_FUNCTIONS_JSON.exists():
        raise FileNotFoundError(f"Tableau functions JSON not found at: {TABLEAU_FUNCTIONS_JSON}")

    with TABLEAU_FUNCTIONS_JSON.open("r", encoding="utf-8") as f:
        return f.read()


_SKILL_NAMES = [
    "calculation_builder",
    "chart_builder",
    "dashboard_designer",
    "formatting",
]


@server.resource("cwtwb://skills/index")
def read_skills_index() -> str:
    """List all available cwtwb agent skills."""

    lines = [
        "# cwtwb Agent Skills",
        "",
        "Load a skill before each phase for expert-level guidance.",
        "Read a skill with: read_resource('cwtwb://skills/<skill_name>')",
        "",
        "## Available Skills (in recommended order)",
        "",
    ]
    for name in _SKILL_NAMES:
        skill_path = SKILLS_DIR / f"{name}.md"
        if skill_path.exists():
            content = skill_path.read_text(encoding="utf-8")
            desc = ""
            for line in content.split("\n"):
                if line.startswith("description:"):
                    desc = line.split(":", 1)[1].strip()
                    break
            lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)


@server.resource("cwtwb://skills/{skill_name}")
def read_skill(skill_name: str) -> str:
    """Read a specific cwtwb agent skill."""

    skill_path = SKILLS_DIR / f"{skill_name}.md"
    if not skill_path.exists():
        available = ", ".join(_SKILL_NAMES)
        raise FileNotFoundError(
            f"Skill '{skill_name}' not found. Available skills: {available}"
        )
    return skill_path.read_text(encoding="utf-8")
