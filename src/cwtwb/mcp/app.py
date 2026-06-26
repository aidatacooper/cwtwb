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

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..config import (
    CONTRACTS_DIR,
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
    "For layout JSON, use the canonical DSL: container nodes use type='container' with direction and children; "
    "do not use zones or absolute-position dashboard schemas. "
    "Generate layout files with generate_layout_json first for DSL validation, then pass the resulting file path to add_dashboard(layout=...). "
    "Prefer a small fixed layout template and fill worksheet names and sizes instead of free-form layout generation. "
    "Use validate_workbook after saving when the human asks for an explicit validation report. "
    "For deeper semantic validation (formulas, field references, data connectivity), use "
    "validate_workbook_api which calls the Tableau Cloud REST API (requires .env credentials). "
    "Prefer core primitives first, and use list_capabilities or describe_capability "
    "when you need to check whether a chart or feature is core, advanced, or recipe-only. "
    "For professional-quality output, optionally read the agent skills "
    "(cwtwb://skills/index) before starting each phase. "
    "After save_workbook, use upload_workbook to validate the generated .twb on "
    "Tableau Cloud (requires .env with TABLEAU_PAT credentials). Upload success "
    "confirms the workbook is structurally valid. Optionally use screenshot_workbook "
    "to capture a view image for human review.",
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


def read_dashboard_authoring_contract() -> str:
    """Read the dashboard authoring contract template used by external agents."""

    contract_path = CONTRACTS_DIR / "dashboard_authoring_v1.json"
    if not contract_path.exists():
        raise FileNotFoundError(f"Contract template not found at: {contract_path}")
    return contract_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# MCP prompts (formerly prompts.py)
# ---------------------------------------------------------------------------

@server.prompt(
    name="guided_dashboard_authoring",
    title="Guided Dashboard Authoring",
    description="Turn a natural-language dashboard brief plus a datasource path into a gated cwtwb authoring run.",
)
def guided_dashboard_authoring(
    brief: str,
    datasource_path: str,
    output_dir: str = "tmp/agentic_run",
) -> list[dict[str, str]]:
    """Guide the full datasource-first workflow with concise user-facing confirmation gates."""

    return [
        {
            "role": "user",
            "content": (
                "You are orchestrating a cwtwb MCP dashboard authoring run.\n"
                "The human interaction must stay natural-language, but your internal workflow must be datasource-first and gated.\n\n"
                "Required workflow:\n"
                "1. Call start_authoring_run with the datasource path, output_dir, and authoring_mode='agent_first'.\n"
                "2. Call intake_datasource_schema and summarize the resulting schema_summary artifact and its Markdown review file.\n"
                "3. Prefer interactive_stage_confirmation with stage='schema' right after the schema summary.\n"
                "4. If interactive_stage_confirmation returns chat_fallback, stop and ask the human to confirm the schema in chat, then call confirm_authoring_stage with stage='schema'. If the schema is rejected, do not draft the contract yet.\n"
                "5. Call build_analysis_brief to create the analysis scaffold. In agent_first mode, you must author 2-4 explicit dashboard directions yourself based on the schema and the human conversation.\n"
                "6. Show those candidate directions to the human in plain language and ask them to choose one before you proceed. Do not collapse to a single recommendation silently.\n"
                "7. Call finalize_analysis_brief with the full candidate set plus the human-chosen selected_direction_id.\n"
                "8. Prefer interactive_stage_confirmation with stage='analysis' after summarizing the chosen direction.\n"
                "9. If interactive_stage_confirmation returns chat_fallback, stop and ask the human to confirm the chosen direction in chat, then call confirm_authoring_stage with stage='analysis'. If the human rejects it, stay in the analysis phase and revise the options.\n"
                "10. Call dashboard_brief_to_contract to think about the draft shape, then call draft_authoring_contract.\n"
                "11. Call review_authoring_contract_for_run.\n"
                "12. If intent is still missing, call light_elicitation and ask only those questions.\n"
                "13. Call finalize_authoring_contract only after you have written an explicit executable contract spec: worksheet names, mark types, fields, filters, actions, and encodings.\n"
                "14. Summarize that finalized contract as a dashboard proposal focused on audience, business question, core KPI/charts, filters/interactions, and key calculated fields.\n"
                "15. Prefer interactive_stage_confirmation with stage='contract' after the dashboard proposal summary.\n"
                "16. If interactive_stage_confirmation returns chat_fallback, stop and ask the human to confirm the proposal in chat, then call confirm_authoring_stage with stage='contract'. If the human rejects it, stay in the contract phase.\n"
                "17. Call build_wireframe and summarize the ASCII wireframe and support/workaround notes from the Markdown review file.\n"
                "18. Call finalize_wireframe, even if the human keeps the default layout, and then prefer interactive_stage_confirmation with stage='wireframe'.\n"
                "19. If interactive_stage_confirmation returns chat_fallback, stop and ask the human to confirm the wireframe in chat, then call confirm_authoring_stage with stage='wireframe'. If the human rejects it, stay in the wireframe phase.\n"
                "20. Call authoring_execution_plan to reason about the build, then call build_execution_plan. Treat execution_plan.md as an internal read-only artifact and do not ask the human to approve it by default.\n"
                "21. Only after that internal planning step, call generate_workbook_from_run.\n"
                "22. Finish by summarizing the run id, key artifacts, final workbook path, validation, and analysis.\n\n"
                "Hard rules:\n"
                "- Prefer get_client_interaction_capabilities and interactive_stage_confirmation for the default human confirmation gates: schema, analysis, contract, and wireframe.\n"
                "- Use confirm_authoring_stage directly only after a real chat fallback answer or when replaying an already-explicit human decision.\n"
                "- The server requires a fresh interactive_stage_confirmation for the current artifact version before each confirm_authoring_stage call.\n"
                "- Keep schema summaries short: main sheet/table, measures, grouped dimensions, and one line about what the dashboard will use.\n"
                "- Keep contract summaries user-facing: who it is for, what it answers, the 4-6 key KPI/charts, filters/interactions, and any key calculated fields.\n"
                "- Keep wireframe summaries visual and plain-language. Avoid internal layout jargon such as weight, fixed_size, or layout-flow.\n"
                "- Do not ask the human to approve execution steps unless they explicitly ask to inspect the plan.\n"
                "- In agent_first mode, the server will not infer dashboard directions, audiences, KPIs, filters, or chart shapes from keywords. You must author those decisions explicitly.\n"
                "- In agent_first mode, analysis must present 2-4 candidate directions and the human must choose one before contract authoring begins.\n"
                "- If the human adds a new worksheet, KPI, or core interaction after contract confirmation, reopen `contract` instead of hiding the change in wireframe notes.\n"
                "- build_execution_plan validates that wireframe scope still matches the confirmed contract and will reject drift.\n"
                "- build_execution_plan will fail closed if the confirmed contract is not executable; do not rely on server-side defaults.\n"
                "- Never directly edit files under tmp/agentic_run/{run_id}/.\n"
                "- If any guided-run tool fails, stop immediately.\n"
                "- After a failure, call get_run_status(run_id), summarize last_error, and ask the human whether to reopen analysis, contract, wireframe, or execution_plan.\n"
                "- Do not switch to low-level workbook tools unless the human explicitly asks to leave guided mode.\n"
                "- Never promise an interaction as final if it only exists as a workaround in the wireframe review.\n\n"
                f"Human brief:\n{brief}\n\n"
                f"Datasource path: {datasource_path}\n"
                f"Run output root: {output_dir}"
            ),
        }
    ]


@server.prompt(
    name="dashboard_brief_to_contract",
    title="Dashboard Brief To Contract",
    description="Turn a human brief plus schema summary into a strict cwtwb contract draft.",
)
def dashboard_brief_to_contract(
    brief: str,
    schema_summary_json: str,
) -> list[dict[str, str]]:
    """Convert a human brief plus schema context into a contract draft prompt."""

    template = json.loads(read_dashboard_authoring_contract())
    schema_summary = json.loads(schema_summary_json)
    profile_index = read_profiles_index()

    return [
        {
            "role": "user",
            "content": (
                "Draft a cwtwb dashboard authoring contract as strict JSON only.\n\n"
                "Rules:\n"
                "- Output valid JSON only.\n"
                "- Follow the template shape exactly.\n"
                "- Use only fields present in the schema summary.\n"
                "- Keep workbook_template blank unless the human explicitly asks for one.\n"
                "- Make the contract executable: each worksheet should explicitly name its mark_type, dimensions/measures or kpi_fields, and any required encodings/actions.\n"
                "- Do not rely on the server to guess chart types, KPI lists, filters, or interaction targets from keywords.\n"
                "- Prefer simple, supported worksheet ideas over speculative complexity.\n"
                "- Do not continue to execution; this prompt is only for draft thinking.\n\n"
                f"Contract template:\n{json.dumps(template, indent=2, ensure_ascii=False)}\n\n"
                f"Known dataset profiles:\n{profile_index}\n\n"
                f"Schema summary:\n{json.dumps(schema_summary, indent=2, ensure_ascii=False)}\n\n"
                f"Human brief:\n{brief}"
            ),
        }
    ]


@server.prompt(
    name="light_elicitation",
    title="Light Elicitation",
    description="Ask only the missing high-value follow-up questions from a contract review artifact.",
)
def light_elicitation(contract_review_json: str) -> list[dict[str, str]]:
    """Generate concise follow-up questions from a persisted contract review."""

    review = json.loads(contract_review_json)
    normalized_contract = json.dumps(
        review.get("normalized_contract", {}),
        indent=2,
        ensure_ascii=False,
    )

    if review.get("valid"):
        content = (
            "The reviewed contract is already valid.\n"
            "Respond with exactly: No clarification needed.\n\n"
            f"Review summary: {review.get('summary', '')}\n"
            f"Normalized contract:\n{normalized_contract}"
        )
    else:
        question_block = "\n".join(
            f"- {question}" for question in review.get("clarification_questions", [])
        )
        content = (
            "Ask the user only the minimum necessary follow-up questions.\n"
            "Rules:\n"
            "- Ask at most 3 questions.\n"
            "- Keep them short and business-oriented.\n"
            "- Do not ask about fields that already exist in the schema summary.\n"
            "- Preserve the current analytical direction.\n"
            "- Stop after asking; do not continue to generation.\n\n"
            f"Review summary: {review.get('summary', '')}\n"
            f"Detected profile: {review.get('detected_profile') or '(none)'}\n"
            f"Suggested clarification questions:\n{question_block}\n\n"
            f"Normalized contract:\n{normalized_contract}"
        )

    return [{"role": "user", "content": content}]


@server.prompt(
    name="authoring_execution_plan",
    title="Authoring Execution Plan",
    description="Produce a concise build-oriented MCP execution plan from a finalized contract.",
)
def authoring_execution_plan(contract_final_json: str) -> list[dict[str, str]]:
    """Generate an execution-oriented MCP plan from a finalized contract."""

    contract_final = json.loads(contract_final_json)

    return [
        {
            "role": "user",
            "content": (
                "Create a concise MCP execution plan for cwtwb.\n"
                "Rules:\n"
                "- Use the finalized contract as the source of truth.\n"
                "- Assume schema, contract, and wireframe confirmations have already happened. Analysis may exist internally without a separate human confirmation.\n"
                "- Describe the likely tool sequence, but stop before execution.\n"
                "- Treat execution_plan.md as an internal read-only artifact; upstream wireframe or contract changes should rebuild the plan instead of editing it.\n"
                "- Do not introduce a new human approval gate unless the human explicitly asks to inspect the execution plan.\n"
                "- Keep the reasoning aligned to supported workbook tools.\n\n"
                f"Final contract:\n{json.dumps(contract_final, indent=2, ensure_ascii=False)}"
            ),
        }
    ]


@server.prompt(
    name="worksheet_clone_refactor",
    title="Worksheet Clone Refactor",
    description="Clone an existing worksheet and refactor only the cloned worksheet to new core fields.",
)
def worksheet_clone_refactor(
    workbook_path: str,
    source_worksheet: str,
    target_worksheet: str,
    replacements_json: str,
    output_path: str,
) -> list[dict[str, str]]:
    """Guide a worksheet clone + local refactor workflow through workbook tools."""

    replacements = json.loads(replacements_json)

    return [
        {
            "role": "user",
            "content": (
                "Use cwtwb workbook tools to clone one existing worksheet and refactor only the cloned worksheet.\n\n"
                "Required tool order:\n"
                "1. Call open_workbook with the workbook path.\n"
                "2. Call clone_worksheet with the source and target worksheet names.\n"
                "3. Call preview_worksheet_refactor with the target worksheet name and replacements.\n"
                "4. Summarize the preview briefly, focusing on rewritten formulas and cloned calculated fields.\n"
                "5. Call apply_worksheet_refactor with the same worksheet name and replacements.\n"
                "6. Call set_worksheet_hidden with hidden=false for the cloned worksheet so it is visible in Tableau sheet tabs.\n"
                "7. Call save_workbook with the output path.\n"
                "8. Finish by summarizing the source worksheet, target worksheet, replacement map, and saved workbook path.\n\n"
                "Hard rules:\n"
                "- Do not modify the original worksheet in place.\n"
                "- Do not skip the preview step.\n"
                "- Keep the refactor worksheet-scoped; do not describe it as a workbook-wide replace-references action.\n"
                "- If the target worksheet already exists, stop and report the naming conflict instead of overwriting it.\n\n"
                f"Workbook path: {workbook_path}\n"
                f"Source worksheet: {source_worksheet}\n"
                f"Target worksheet: {target_worksheet}\n"
                f"Replacements: {json.dumps(replacements, ensure_ascii=False)}\n"
                f"Output path: {output_path}"
            ),
        }
    ]
