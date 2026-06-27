# cwtwb Skills

Skills are expert-level guidance files that help AI agents produce
professional Tableau workbooks. Prompts explain what to build. Skills explain
how to build it well, phase by phase.

## Workflow Phases

```text
Phase 1: calculation_builder   -> Define parameters, calculated fields, LOD logic
Phase 2: chart_builder         -> Choose chart types, configure encodings, filters
Phase 3: dashboard_designer    -> Layout, worksheet captions, interaction actions
Phase 4: formatting            -> Number formats, colors, sorting, tooltips
```

## Recommended Resource Flow

```text
1. read_resource("cwtwb://skills/calculation_builder")
2. read_resource("cwtwb://skills/chart_builder")
3. read_resource("cwtwb://skills/dashboard_designer")
4. read_resource("cwtwb://skills/formatting")
5. create_workbook(...) or open_workbook(...)
6. list_fields(...)
7. add_worksheet(...)
8. configure_chart(...) / configure_dual_axis(...) / configure_chart_recipe(...)
9. add_dashboard(...)
10. save_workbook(...)
```

## Design Philosophy

- Skills are phase-specific, not generic prompt stuffing.
- Load only the skill needed for the current phase.
- Keep the workflow direct, workbook-oriented, and self-validating.
