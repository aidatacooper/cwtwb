# MCP Walkthrough

Use this sequence when narrating the demo live.

## 1. Start With the Generic Contract

```text
prompt("dashboard_brief_to_contract", ...)
read_resource("cwtwb://contracts/dashboard_authoring_v1")
```

Narration:

- The system can start directly from a human brief via MCP prompt.
- It still anchors on a generic authoring contract.
- There is no dataset-specific logic hard-coded into the template itself.

## 2. Inspect Dataset Profiles

```text
read_resource("cwtwb://profiles/index")
read_resource("cwtwb://profiles/superstore")
```

Narration:

- Profiles are external JSON bundles.
- They provide dataset-aware defaults and field-signature matching rules.

## 3. Review the Draft Contract

```text
review_authoring_contract(<contents of draft_contract.json>)
prompt("light_elicitation", ...)
prompt("authoring_execution_plan", ...)
```

Narration:

- The review step recognizes the field signature and applies the Superstore profile.
- It returns a normalized contract, recommended skills, and an execution outline.
- The prompts turn that normalized contract into follow-up questions and an MCP plan.

## 4. Execute the Authoring Plan

```text
read_resource("cwtwb://skills/authoring_workflow")
read_resource("cwtwb://skills/chart_builder")
read_resource("cwtwb://skills/dashboard_designer")
create_workbook(...)
add_calculated_field(...)
add_worksheet(...)
configure_chart(...)
add_dashboard(...)
add_dashboard_action(...)
set_worksheet_caption(...)
validate_workbook(...)
```

Narration:

- The agent now has a plan, profile-aware defaults, and phase guidance.
- This is the point where cwtwb behaves like authoring infrastructure rather than a raw XML utility.
