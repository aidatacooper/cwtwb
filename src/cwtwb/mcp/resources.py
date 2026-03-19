"""MCP resources exposed by cwtwb — read-only reference data for AI agents.

Resources are different from tools: they are read-only data blobs that an
AI agent fetches for context, not actions that modify state.

AVAILABLE RESOURCES
-------------------
  file://docs/tableau_all_functions.json
      Complete list of Tableau calculation functions with syntax and examples.
      Source: docs/tableau_all_functions.json (bundled with cwtwb).
      Use this to look up function signatures when writing calculated fields.

  cwtwb://profiles/index
      Markdown index listing all available dataset profiles.

  cwtwb://profiles/{profile_name}
      A specific dataset profile JSON payload used by contract review.

  cwtwb://skills/index
      Markdown index listing all available agent skill files with descriptions.
      Read this first to understand which skills exist before fetching one.

  cwtwb://skills/{skill_name}
      A specific agent skill Markdown file.  Skills are expert-level guides
      for common phases of workbook construction:
        - calculation_builder  → writing Tableau formulas and calculated fields
        - chart_builder        → choosing mark types and encoding best practices
        - dashboard_designer   → layout patterns, zone sizing, action wiring
        - formatting           → color palettes, font choices, style consistency

USAGE PATTERN (recommended by server instructions)
---------------------------------------------------
  Before each major phase, fetch the relevant skill:
    read_resource("cwtwb://skills/chart_builder")    # before configure_chart
    read_resource("cwtwb://skills/dashboard_designer") # before add_dashboard
"""

from __future__ import annotations

from ..config import (
    CONTRACTS_DIR,
    SKILLS_DIR,
    TABLEAU_FUNCTIONS_JSON,
    find_profile_path,
    get_profile_dirs,
    iter_profile_files,
)
from .app import server


@server.resource("file://docs/tableau_all_functions.json")
def read_tableau_functions() -> str:
    """Read the complete list of Tableau calculation functions."""

    if not TABLEAU_FUNCTIONS_JSON.exists():
        raise FileNotFoundError(f"Tableau functions JSON not found at: {TABLEAU_FUNCTIONS_JSON}")

    with TABLEAU_FUNCTIONS_JSON.open("r", encoding="utf-8") as f:
        return f.read()


_SKILL_NAMES = [
    "authoring_workflow",
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


@server.resource("cwtwb://profiles/index")
def read_profiles_index() -> str:
    """List available dataset profiles used by contract review."""

    lines = [
        "# cwtwb Dataset Profiles",
        "",
        "Dataset profiles provide external default bundles and field signatures.",
        "Read a profile with: read_resource('cwtwb://profiles/<profile_name>')",
        "",
    ]
    profile_files = iter_profile_files()
    if not profile_files:
        lines.append("(no dataset profiles found)")
        return "\n".join(lines)

    lines.append("Configured directories:")
    for directory in get_profile_dirs():
        lines.append(f"- {directory}")
    lines.append("")

    for profile_path in profile_files:
        lines.append(f"- `{profile_path.stem}`")
    return "\n".join(lines)


@server.resource("cwtwb://profiles/{profile_name}")
def read_dataset_profile(profile_name: str) -> str:
    """Read a specific dataset profile JSON payload."""

    profile_path = find_profile_path(profile_name)
    if profile_path is None:
        available = ", ".join(sorted(path.stem for path in iter_profile_files()))
        raise FileNotFoundError(
            f"Dataset profile '{profile_name}' not found. Available profiles: {available}"
        )
    return profile_path.read_text(encoding="utf-8")


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


@server.resource("cwtwb://contracts/dashboard_authoring_v1")
def read_dashboard_authoring_contract() -> str:
    """Read the dashboard authoring contract template used by external agents."""

    contract_path = CONTRACTS_DIR / "dashboard_authoring_v1.json"
    if not contract_path.exists():
        raise FileNotFoundError(f"Contract template not found at: {contract_path}")
    return contract_path.read_text(encoding="utf-8")
