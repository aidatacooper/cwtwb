# Agentic MCP Authoring Demo

This example demonstrates the intended MCP workflow for a contract-driven,
profile-aware dashboard authoring loop.

## What It Shows

- A generic dashboard contract template, not a hard-coded Superstore spec
- Dataset profile matching from `available_fields`
- MCP resources for contract and profile discovery
- MCP prompts for brief normalization, light elicitation, and execution planning
- MCP tool review before workbook generation
- A workflow that naturally leads into skills, workbook creation, actions, captions, and validation

## Suggested MCP Flow

```text
1. prompt("dashboard_brief_to_contract", ...)
2. read_resource("cwtwb://contracts/dashboard_authoring_v1")
3. read_resource("cwtwb://profiles/index")
4. read_resource("cwtwb://profiles/superstore")
5. review_authoring_contract(draft_contract_json)
6. prompt("light_elicitation", ...)
7. prompt("authoring_execution_plan", ...)
8. read_resource("cwtwb://skills/authoring_workflow")
9. read_resource("cwtwb://skills/chart_builder")
10. read_resource("cwtwb://skills/dashboard_designer")
11. create_workbook(...)
12. add_calculated_field(...)
13. add_worksheet(...)
14. configure_chart(...)
15. add_dashboard(...)
16. add_dashboard_action(...)
17. set_worksheet_caption(...)
18. validate_workbook(...)
```

## Files

- `user_brief.md`: human brief that starts the flow
- `demo_human_prompt_zh.md`: a natural-language prompt suitable for a real MCP client
- `draft_contract.json`: generic contract draft with field list
- `expected_review_result.json`: expected result after profile-aware review
- `mcp_walkthrough.md`: concise tool/resource sequence for live demo narration

## Run It

```text
python examples/scripts/demo_agentic_mcp_authoring.py
```

This writes:

- `output/agentic_mcp_authoring_demo.twb`
- `output/agentic_mcp_authoring_review.json`

The script is optional. The primary demo path is the MCP flow above.

If you want a more human-style client test, start from:

- `demo_human_prompt_zh.md`

That prompt is intentionally natural. The workflow rules are expected to come
from the MCP server's prompts, resources, and instructions.
