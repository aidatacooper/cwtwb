# Guided MCP Authoring Run

This folder is the recommended Excel-first demo for Guided MCP Authoring Run V1.

Use the local datasource in this folder:

```text
examples/agentic_mcp_authoring/Sample - Superstore.xls
```

This workbook has a single `Orders` sheet, which keeps the live demo focused on
the authoring workflow instead of multi-sheet intake decisions.

## What This Demo Proves

The goal is not "AI can draw a chart". The goal is to show a controlled
Agentic BI workflow:

```text
real datasource -> schema summary -> analysis brief -> contract -> wireframe -> execution plan -> workbook
```

The strongest Matthew-facing checkpoints are:

1. `schema_summary.json`
2. `analysis_brief.json`
3. `contract_final.json`
4. `wireframe.json`
5. `execution_plan.json`
6. `final_workbook.twb`
7. `validation_report.json`
8. `analysis_report.json`

## Demo Mode 1: Live MCP Client

Start the server from the project root:

```bash
python -m cwtwb.mcp
```

You can also use `uvx cwtwb` when your local environment supports it.

Then connect from an MCP-capable client such as Claude Desktop, Cursor, VSCode,
or Codex, and use this brief plus datasource path:

```text
Build an executive sales performance dashboard for Matthew.
Audience: sales leaders
Primary question: Which regions, categories, and sub-categories are driving sales and profit, and where should leaders drill deeper?
Please include interactive filtering from the top view into detail, and keep the dashboard simple enough for a polished demo.

Datasource path:
C:\Users\imgwho\Desktop\projects\20260227-cwtwb\examples\agentic_mcp_authoring\Sample - Superstore.xls
```

Recommended live sequence:

1. Ask the client to use the `guided_dashboard_authoring` prompt.
2. Let it call `start_authoring_run(...)`.
3. Let it call `intake_datasource_schema(...)`.
4. Show the generated schema summary and confirm it.
5. Make sure it calls `confirm_authoring_stage(..., stage="schema")`.
6. Let it build and finalize the analysis brief.
7. Show the candidate directions and confirm the selected analysis direction.
8. Make sure it calls `confirm_authoring_stage(..., stage="analysis")`.
9. Let it draft, review, and finalize the contract.
10. Show the finalized contract and confirm it.
11. Make sure it calls `confirm_authoring_stage(..., stage="contract")`.
12. Let it build and finalize the ASCII wireframe.
13. Show the wireframe and support/workaround notes, then confirm it.
14. Make sure it calls `confirm_authoring_stage(..., stage="wireframe")`.
15. Let it build the execution plan.
16. Show the execution plan and confirm it.
17. Make sure it calls `confirm_authoring_stage(..., stage="execution_plan")`.
18. Let it call `generate_workbook_from_run(...)`.
19. End by showing the final workbook path plus validation and analysis artifacts.

What to emphasize while speaking:

- The system starts from a real Excel file, not a baked demo JSON.
- The agent pauses at `schema`, `analysis`, `contract`, `wireframe`, and `execution_plan`.
- The prompts guide; the tools write files and move run state.
- The run is resumable because artifacts live under `tmp/agentic_run/{run_id}/`.
- The human-facing review surface is now paired Markdown artifacts, not just JSON.

## Demo Mode 2: Deterministic Real MCP Client Script

If you want a reproducible fallback that still uses the real MCP protocol, run:

```bash
python examples/agentic_mcp_authoring/demo_guided_authoring_mcp_client.py
```

This script does not call Python functions directly. It uses the official
`mcp` client over stdio to connect to `python -m cwtwb.mcp`, then executes the
full guided flow and prints each checkpoint.

Useful overrides:

```bash
python examples/agentic_mcp_authoring/demo_guided_authoring_mcp_client.py ^
  --datasource "C:\path\to\your.xls" ^
  --output-dir "tmp/agentic_run" ^
  --brief "Build a sales dashboard for regional leaders." ^
  --user-answers-json "{\"audience\":\"regional leaders\",\"primary_question\":\"Which regions need attention first?\",\"require_interaction\":true}"
```

## What Gets Written

Each run writes its own artifacts under:

```text
tmp/agentic_run/{run_id}/
```

Typical output:

```text
tmp/agentic_run/20260319-153045-a1b2c3d4/manifest.json
tmp/agentic_run/20260319-153045-a1b2c3d4/schema_summary.20260319-153046.json
tmp/agentic_run/20260319-153045-a1b2c3d4/schema_summary.20260319-153046.md
tmp/agentic_run/20260319-153045-a1b2c3d4/analysis_brief.20260319-153055.json
tmp/agentic_run/20260319-153045-a1b2c3d4/analysis_brief.20260319-153055.md
tmp/agentic_run/20260319-153045-a1b2c3d4/contract_final.20260319-153120.json
tmp/agentic_run/20260319-153045-a1b2c3d4/contract_final.20260319-153120.md
tmp/agentic_run/20260319-153045-a1b2c3d4/wireframe.20260319-153140.json
tmp/agentic_run/20260319-153045-a1b2c3d4/wireframe.20260319-153140.md
tmp/agentic_run/20260319-153045-a1b2c3d4/execution_plan.20260319-153155.json
tmp/agentic_run/20260319-153045-a1b2c3d4/execution_plan.20260319-153155.md
tmp/agentic_run/20260319-153045-a1b2c3d4/final_workbook.twb
tmp/agentic_run/20260319-153045-a1b2c3d4/validation_report.20260319-153205.json
tmp/agentic_run/20260319-153045-a1b2c3d4/analysis_report.20260319-153206.json
```

Use `list_authoring_runs()` and `get_run_status(run_id)` to recover a run after
the client or server restarts. If generation fails, use
`reopen_authoring_stage(run_id, stage, notes)` instead of editing run artifacts
by hand.
