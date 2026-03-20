"""FastMCP server singleton for the cwtwb MCP server.

This module creates the single FastMCP `server` instance that all tool and
resource modules register against via @server.tool() and @server.resource().

Import order matters: app.py must be imported before tools_*.py and resources.py
so that `server` exists when the decorators run.  The entry point (typically
run via `mcp run` or `python -m cwtwb.mcp`) imports all tool modules, which
self-register, and then starts the server transport.

The `instructions` string is what AI agents read when they first connect —
it summarises the required call order and points agents to skill resources.
"""

from mcp.server.fastmcp import FastMCP


server = FastMCP(
    "cwtwb",
    instructions="Tableau Workbook (.twb) generation MCP Server. "
    "Prefer the guided_dashboard_authoring prompt for natural-language dashboard requests. "
    "For guided authoring, start_authoring_run first, then intake_datasource_schema, "
    "then prefer interactive_stage_confirmation('schema') so form elicitation can capture a real human decision. "
    "If the client falls back to chat confirmation, ask the human in chat and only then persist that answer with confirm_authoring_stage('schema'). "
    "Then build_analysis_brief, finalize_analysis_brief, and again prefer interactive_stage_confirmation('analysis'). "
    "If that falls back to chat, ask the human and only then call confirm_authoring_stage('analysis'). "
    "Then draft_authoring_contract, review_authoring_contract_for_run, finalize_authoring_contract, "
    "then prefer interactive_stage_confirmation('contract'). "
    "If that falls back to chat, ask the human and only then call confirm_authoring_stage('contract'). "
    "After that build_wireframe, finalize_wireframe, and prefer interactive_stage_confirmation('wireframe'). "
    "If that falls back to chat, ask the human and only then call confirm_authoring_stage('wireframe'). "
    "After that build_execution_plan, prefer interactive_stage_confirmation('execution_plan'). "
    "If that falls back to chat, ask the human and only then call confirm_authoring_stage('execution_plan'), and only then call generate_workbook_from_run. "
    "Use get_client_interaction_capabilities when you need to explain whether elicitation is available in the current client. "
    "The server enforces a fresh interactive_stage_confirmation before each confirm_authoring_stage call, especially after any contract or wireframe revision. "
    "If the human adds a new worksheet, KPI, or core interaction after contract confirmation, treat that as a contract-scope change and reopen contract instead of smuggling it into wireframe notes. "
    "build_execution_plan will reject wireframe scope drift that no longer matches the confirmed contract. "
    "Use dashboard_brief_to_contract, light_elicitation, and authoring_execution_plan prompts only to guide the agent workflow between those tool calls. "
    "Never directly edit files under tmp/agentic_run/{run_id}/. "
    "If any guided-run tool fails, stop, call get_run_status(run_id), summarize last_error, and ask the human whether to reopen analysis, contract, wireframe, or execution_plan. "
    "Do not switch to low-level workbook tools unless the human explicitly asks to leave guided mode. "
    "Treat execution_plan.md as read-only; rebuild upstream stages instead of editing the plan artifact. "
    "Read the dashboard contract template (cwtwb://contracts/dashboard_authoring_v1) and inspect dataset profiles via cwtwb://profiles/index when needed. "
    "Manual workbook editing still follows create_workbook or open_workbook first, then add_worksheet + configure_chart, and finally save_workbook. "
    "Prefer core primitives first, and use list_capabilities or describe_capability "
    "when you need to check whether a chart or feature is core, advanced, or recipe-only. "
    "For professional-quality output, optionally read the agent skills "
    "(cwtwb://skills/index) before starting each phase.",
)
