# cwtwb Skills

Skills are expert-level guidance files that help AI agents produce
professional Tableau workbooks. Prompts explain what to build. Skills explain
how to build it well, phase by phase.

## Workflow Phases

```text
Phase 0: authoring_workflow    -> Review the contract, ask only needed questions
Phase 1: calculation_builder   -> Define parameters, calculated fields, LOD logic
Phase 2: chart_builder         -> Choose chart types, configure encodings, filters
Phase 3: dashboard_designer    -> Layout, worksheet captions, interaction actions
Phase 4: formatting            -> Number formats, colors, sorting, tooltips
```

## Recommended Resource Flow

```text
1. read_resource("cwtwb://contracts/dashboard_authoring_v1")
2. read_resource("cwtwb://profiles/index")
3. review_authoring_contract(contract_json)
4. read_resource("cwtwb://skills/authoring_workflow")
5. read_resource("cwtwb://skills/calculation_builder")
6. read_resource("cwtwb://skills/chart_builder")
7. read_resource("cwtwb://skills/dashboard_designer")
8. read_resource("cwtwb://skills/formatting")
```

## Design Philosophy

- Skills are phase-specific, not generic prompt stuffing.
- Load only the skill needed for the current phase.
- Keep the workflow contract-first, skill-guided, and self-validating.
- Use light elicitation: ask follow-up questions only when the contract misses critical intent.
