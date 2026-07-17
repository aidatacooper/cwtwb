"""FastMCP server singleton and mutable workbook state for the cwtwb MCP server.

This module creates the single FastMCP `server` instance that all tool and
resource modules register against via @server.tool() and @server.resource().

It also holds the single active TWBEditor instance (singleton state).
All tools that need to read or mutate the workbook call get_editor(), which
raises RuntimeError if no workbook has been opened yet.

State transitions:
  (none)  →  set_editor(editor)   [create_workbook / open_workbook]
          →  get_editor()         [any subsequent tool call]
          →  set_editor(editor)   [create_workbook / open_workbook again resets]

There is no "close workbook" operation — saving the file is the final step.
The state is process-local and resets when the MCP server process restarts.

Import order matters: app.py must be imported before tools_*.py and resources.py
so that `server` exists when the decorators run.  The entry point (typically
run via `mcp run` or `python -m cwtwb.mcp_server`) imports all tool modules, which
self-register, and then starts the server transport.

The `instructions` string is what AI agents read when they first connect —
it summarises the required call order and points agents to skill resources.
"""

from __future__ import annotations

import os
import sys
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..config import (
    SKILLS_DIR,
    TABLEAU_FUNCTIONS_JSON,
    find_profile_path,
    get_profile_dirs,
    iter_profile_files,
)
from ..twb_editor import TWBEditor

server = FastMCP(
    "cwtwb",
    instructions="Tableau Workbook (.twb) generation MCP Server. "
    "Call the exposed MCP tools directly through the connected client tool surface; "
    "do not run shell commands like 'mcp call', 'mcp list-tools', or 'gh api' to discover "
    "or invoke cwtwb tools. If tool discovery looks empty, ask the user to restart or "
    "reconnect the MCP client instead of inventing a CLI command. "
    "Use manual workbook editing: create_workbook or open_workbook first, "
    "then list_fields, add_worksheet, configure_chart or configure_dual_axis, "
    "optionally add_dashboard and add_dashboard_action, and finally save_workbook. "
    "add_dashboard exists in the default MCP tool surface and should be used when "
    "a dashboard is requested. "
    "save_workbook is the only default MCP tool that writes the active in-memory "
    "workbook to a .twb/.twbx file on disk; do not use validate_workbook, "
    "analyze_twb, or migration tools as substitutes for saving. "
    "validate_workbook only validates the active workbook or an existing file and "
    "does not write output. analyze_twb requires an existing .twb/.twbx file path, "
    "so call save_workbook before analyze_twb when analyzing a newly generated workbook. "
    "Do not infer tool availability from list_capabilities; list_capabilities is a "
    "feature support catalog, not a tool inventory. "
    "Use set_excel_connection, set_csv_connection, set_hyper_connection, set_mysql_connection, or "
    "set_tableauserver_connection when the workbook datasource must be changed. "
    "Use inspect_excel_connection when you need a read-only preview of Excel sheet parsing, inferred datatypes, "
    "or likely multi-table relationships before mutating the workbook. "
    "When authoring a dashboard layout, first call list_worksheets and lock the exact worksheet names; "
    "reuse those exact names in layout nodes to avoid name drift. "
    "For layout files, use the canonical DSL: container nodes use type='container' with direction and children; "
    "do not use zones or absolute-position dashboard schemas. "
    "Generate layout files with generate_layout_json first for DSL validation, then pass the resulting JSON or YAML file path to add_dashboard(layout=...). "
    "Prefer a small fixed layout template and fill worksheet names and sizes instead of free-form layout generation. "
    "Use validate_workbook after saving when the human asks for an explicit validation report. "
    "For deeper semantic validation (formulas, field references, data connectivity), use "
    "validate_workbook_api which calls the Tableau Cloud REST API. Pass env_path for "
    "one-off Tableau credentials; do not edit MCP server configuration just to switch "
    "credentials for a single validation call. "
    "Prefer core primitives first, and use list_capabilities or describe_capability "
    "when you need to check whether a chart or feature is core, advanced, or recipe-only. "
    "For professional-quality output, optionally read the agent skills "
    "(cwtwb://skills/index) before starting each phase. "
    "If a guessed documentation resource such as cwtwb://docs/manual-editing is unavailable, "
    "list resources and use cwtwb://tool-surface or cwtwb://skills/index. "
    "If an agent is unsure whether it is connected to the expected cwtwb server, call "
    "get_mcp_status. After save_workbook, prefer validate_workbook_api(env_path=...) "
    "for Tableau Cloud semantic validation because it does not publish or store the workbook. "
    "Use upload_workbook only when the user explicitly needs a published workbook_id, "
    "a screenshot, TWBX packaging validation, or publish/openability evidence. "
    "Use screenshot_workbook only after upload_workbook returns a workbook_id.",
)

_editor: Optional[TWBEditor] = None


def get_editor() -> TWBEditor:
    """Get the current editor instance, raising if none exists."""

    if _editor is None:
        raise RuntimeError("No active workbook. Call create_workbook or open_workbook first.")
    return _editor


def set_editor(editor: TWBEditor) -> None:
    """Replace the current editor instance."""

    global _editor
    _editor = editor


@server.tool()
def get_mcp_status() -> dict:
    """Report cwtwb MCP server version, workbook state, and safe usage guardrails.

    Use this when an AI client seems stale, cannot see expected tools, or is
    about to edit MCP configuration to switch Tableau credentials. This tool
    never returns secret values.
    """

    try:
        package_version = version("cwtwb")
    except PackageNotFoundError:
        package_version = "editable/local"

    tsc_available = find_spec("tableauserverclient") is not None
    try:
        tsc_version = version("tableauserverclient") if tsc_available else None
    except PackageNotFoundError:
        tsc_version = "importable, metadata unavailable"

    env_names = [
        "TABLEAU_SERVER",
        "TABLEAU_SITE",
        "TABLEAU_PAT_NAME",
        "TABLEAU_PAT_SECRET",
        "TABLEAU_PROJECT_ID",
        "TABLEAU_ENV_FILE",
    ]
    return {
        "server": "cwtwb",
        "version": package_version,
        "python_executable": sys.executable,
        "tableauserverclient_available": tsc_available,
        "tableauserverclient_version": tsc_version,
        "active_workbook": _editor is not None,
        "tableau_env_vars_present": [name for name in env_names if os.environ.get(name)],
        "credential_priority": [
            "explicit constructor arguments",
            "tool env_path",
            "process environment variables",
            "TABLEAU_ENV_FILE",
            "workbook sibling .env",
            "current working directory .env",
            "cwtwb project .env",
            "home .env",
        ],
        "guardrails": [
            "Use MCP tools directly; do not run shell commands named mcp to invoke cwtwb tools.",
            "Use env_path on validate_workbook_api, upload_workbook, and screenshot_workbook for one-off Tableau credentials.",
            "Prefer validate_workbook_api for cloud semantic validation; it is lighter because it does not publish or store the workbook.",
            "Use upload_workbook only for explicit publish/openability evidence, TWBX packaging validation, or as the required precursor to screenshot_workbook.",
            "Do not edit MCP server configuration just to switch Tableau credentials for one workbook.",
            "If a newly released tool parameter is missing, reconnect or restart the MCP client to reload the tool schema.",
            "Call save_workbook to write the active workbook; validate_workbook and analyze_twb do not save files.",
        ],
    }


def main():
    """Run the MCP server via stdio transport."""

    server.run(transport="stdio")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# MCP resources (formerly resources.py)
# ---------------------------------------------------------------------------

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
    "validation",
]


def _tool_surface_text() -> str:
    """Return a compact agent-facing contract for stable MCP usage."""

    return "\n".join(
        [
            "# cwtwb MCP Tool Surface",
            "",
            "Use MCP tools directly from the connected client. Do not call a shell command named `mcp`; most client environments do not install one.",
            "",
            "## Stable workbook flow",
            "",
            "0. Optional troubleshooting: call `get_mcp_status` if the client seems stale, expected tools are missing, or Tableau credential handling is unclear",
            "1. `create_workbook` or `open_workbook`",
            "2. `set_excel_connection`, `set_csv_connection`, `set_hyper_connection`, `set_mysql_connection`, or `set_tableauserver_connection` when changing the datasource",
            "3. `list_fields` and `list_worksheets`",
            "4. `add_worksheet` plus `configure_chart`, `configure_dual_axis`, or `configure_chart_recipe`",
            "5. `list_worksheets` before dashboard authoring; reuse exact worksheet names",
            "6. `generate_layout_json` or `generate_layout_yaml` for custom dashboard layout files, then `add_dashboard`",
            "7. `save_workbook` to write the `.twb` or `.twbx` file",
            "8. Optional validation: `validate_workbook`, then prefer `validate_workbook_api(env_path=...)` for cloud semantic validation",
            "9. Optional publish/visual evidence only: `upload_workbook(env_path=...)`, then `screenshot_workbook(env_path=...)` if a screenshot is required",
            "",
            "## Important boundaries",
            "",
            "- `save_workbook` is the default tool that writes the active workbook to disk.",
            "- `validate_workbook` validates only; it does not save or export.",
            "- `list_capabilities` describes supported chart/features; it is not a tool inventory.",
            "- `get_mcp_status` reports version/state and credential guardrails without exposing secrets.",
            "- `env_path` on validation/upload/screenshot tools is the correct way to switch Tableau credentials for a single call.",
            "- Chart inputs expect user-facing fields or expressions such as `Sales`, `SUM(Sales)`, or `MONTH(Order Date)`; do not copy generated `.twb` column-instance names such as `[sum:Sales:qk]`, `[none:Category:nk]`, or `[federated.xxx].[sum:Profit:qk]` from reference workbooks.",
            "- `validate_workbook_api` is the default Tableau Cloud validation tool for `.twb` because it does not publish the workbook.",
            "- `upload_workbook` publishes the workbook; use it only for explicit publish/openability evidence, TWBX validation, or screenshots.",
            "- `screenshot_workbook` requires a `workbook_id` returned by `upload_workbook`.",
            "- Do not edit MCP server configuration just to switch Tableau credentials for one workbook.",
            "- For phase guidance, read `cwtwb://skills/index` and then the relevant `cwtwb://skills/<skill_name>` resource.",
            "- For Tableau calculation functions, read `file://docs/tableau_all_functions.json`.",
            "",
            "If a client cannot see tools such as `create_workbook`, the MCP client connection is misconfigured or stale. Reconnect/restart the client rather than trying `mcp call` in a terminal.",
        ]
    )


def _manual_editing_text() -> str:
    """Compatibility resource for agents that guess older docs-style URIs."""

    return "\n".join(
        [
            "# cwtwb Manual Editing",
            "",
            "This compatibility resource exists because some AI clients guess `cwtwb://docs/manual-editing`.",
            "The canonical guidance is the MCP tool surface plus skills:",
            "",
            "- Read `cwtwb://tool-surface` for the stable tool call order.",
            "- Read `cwtwb://skills/index` for phase-specific Tableau authoring guidance.",
            "- For dashboards, read `cwtwb://skills/dashboard_designer`.",
            "",
            _tool_surface_text(),
        ]
    )


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


@server.resource("cwtwb://tool-surface")
def read_tool_surface() -> str:
    """Describe the stable MCP tool surface and correct client usage."""

    return _tool_surface_text()


@server.resource("cwtwb://docs/manual-editing")
def read_manual_editing_compat() -> str:
    """Compatibility alias for agents that guess a docs/manual-editing URI."""

    return _manual_editing_text()


@server.resource("cwtwb://docs/tool-surface")
def read_docs_tool_surface_compat() -> str:
    """Compatibility alias for agents that put docs under cwtwb://docs."""

    return _tool_surface_text()


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

