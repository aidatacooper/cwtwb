"""Regression coverage for the guided MCP authoring run workflow."""

from __future__ import annotations

import asyncio
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.authoring_contract import review_authoring_contract_payload
from cwtwb.authoring_run import _is_expression, validate_generated_workbook_semantics
from cwtwb.mcp.resources import (
    read_dashboard_authoring_contract,
    read_profiles_index,
    read_skill,
    read_skills_index,
)
from cwtwb.mcp.tools_authoring import _STAGE_LABELS
from cwtwb.server import (
    build_analysis_brief,
    build_execution_plan,
    build_wireframe,
    confirm_authoring_stage,
    draft_authoring_contract,
    finalize_analysis_brief,
    finalize_authoring_contract,
    finalize_wireframe,
    generate_workbook_from_run,
    get_client_interaction_capabilities,
    get_run_status,
    intake_datasource_schema,
    interactive_stage_confirmation,
    list_authoring_runs,
    reopen_authoring_stage,
    resume_authoring_run,
    review_authoring_contract_for_run,
    server,
    start_authoring_run,
)

XLS_SOURCE = Path("templates/Sample - Superstore - simple.xls")
HYPER_SOURCE = Path("templates/dashboard/Sample _ Superstore.hyper")
RUN_ROOT = Path("tmp") / "authoring_run_tests"
GLOBAL_RUN_ROOT = Path("tmp") / "agentic_run"


@pytest.fixture(autouse=True)
def clean_authoring_runs():
    for root in (RUN_ROOT, GLOBAL_RUN_ROOT):
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
    yield
    for root in (RUN_ROOT, GLOBAL_RUN_ROOT):
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)


def _load_json(path_value: str | Path) -> dict:
    return json.loads(Path(path_value).read_text(encoding="utf-8"))


def _measure_name_members(workbook_path: Path, worksheet_name: str) -> list[str]:
    root = ET.parse(workbook_path).getroot()
    worksheet = root.find(f".//worksheet[@name='{worksheet_name}']")
    if worksheet is None:
        return []
    members: list[str] = []
    for filter_el in worksheet.findall(".//view/filter"):
        if ":Measure Names" not in filter_el.get("column", ""):
            continue
        for member in filter_el.findall(".//groupfilter[@function='member']"):
            value = member.get("member", "")
            if value:
                members.append(value)
    return members


def _worksheet_encoding_columns(workbook_path: Path, worksheet_name: str, encoding_name: str) -> list[str]:
    root = ET.parse(workbook_path).getroot()
    worksheet = root.find(f".//worksheet[@name='{worksheet_name}']")
    if worksheet is None:
        return []
    return [
        encoding.get("column", "")
        for encoding in worksheet.findall(f".//pane/encodings/{encoding_name}")
        if encoding.get("column", "")
    ]


def _worksheet_pane_mark_classes(workbook_path: Path, worksheet_name: str) -> list[str]:
    root = ET.parse(workbook_path).getroot()
    worksheet = root.find(f".//worksheet[@name='{worksheet_name}']")
    if worksheet is None:
        return []
    return [
        mark.get("class", "")
        for mark in worksheet.findall(".//pane/mark")
        if mark.get("class")
    ]


def _dashboard_action_targets(workbook_path: Path, dashboard_name: str, source_sheet: str) -> list[str]:
    root = ET.parse(workbook_path).getroot()
    dashboard = root.find(f".//dashboards/dashboard[@name='{dashboard_name}']")
    if dashboard is None:
        return []
    dashboard_sheets: list[str] = []
    for zone in dashboard.findall(".//zone"):
        name = zone.get("name", "")
        if name and name not in dashboard_sheets:
            dashboard_sheets.append(name)

    targets: list[str] = []
    for action_el in root.findall("./actions/action"):
        source = action_el.find("source")
        if source is None or source.get("worksheet", "") != source_sheet:
            continue
        command = action_el.find("command")
        if command is None or command.get("command", "") != "tsc:tsl-filter":
            continue
        excluded: set[str] = set()
        for param in command.findall("param"):
            if param.get("name") == "exclude":
                excluded = {item.strip() for item in param.get("value", "").split(",") if item.strip()}
                break
        for name in dashboard_sheets:
            if name not in excluded and name not in targets:
                targets.append(name)
    return targets


def _start_run(
    *,
    authoring_mode: str = "legacy",
    resume_if_exists: bool = False,
    force_new: bool = False,
) -> dict:
    if not XLS_SOURCE.exists():
        pytest.skip("Sample Excel datasource not available")
    payload = json.loads(
        start_authoring_run(
            datasource_path=str(XLS_SOURCE),
            output_dir=str(RUN_ROOT),
            resume_if_exists=resume_if_exists,
            authoring_mode=authoring_mode,
            force_new=force_new,
        )
    )
    return payload


def _request_confirmation(run_id: str, stage: str) -> dict:
    return json.loads(
        asyncio.run(
            interactive_stage_confirmation(
                run_id=run_id,
                stage=stage,
                stage_summary=f"Test confirmation request for {stage}.",
            )
        )
    )


def _approve_schema(run_id: str) -> dict:
    intake_payload = json.loads(intake_datasource_schema(run_id))
    schema_path = Path(intake_payload["artifact"])
    schema_summary = json.loads(schema_path.read_text(encoding="utf-8"))
    if not schema_summary.get("selected_primary_object") and schema_summary.get("sheets"):
        preferred = schema_summary["sheets"][0]["name"]
        intake_payload = json.loads(intake_datasource_schema(run_id, preferred_sheet=preferred))
        schema_summary = _load_json(intake_payload["artifact"])
    _request_confirmation(run_id, "schema")
    confirm_authoring_stage(run_id, "schema", True, "Schema looks correct.")
    return schema_summary


def _approve_analysis(run_id: str, selected_direction_id: str = "") -> dict:
    built = json.loads(build_analysis_brief(run_id))
    assert Path(built["artifact"]).exists()
    assert Path(built["review_artifact"]).exists()
    overrides = (
        json.dumps({"selected_direction_id": selected_direction_id}, ensure_ascii=False)
        if selected_direction_id
        else ""
    )
    finalized = json.loads(
        finalize_analysis_brief(
            run_id,
            user_answers_json=overrides,
        )
    )
    _request_confirmation(run_id, "analysis")
    confirm_authoring_stage(run_id, "analysis", True, "Analysis direction approved.")
    return _load_json(finalized["artifact"])


def _draft_contract(run_id: str, brief: str) -> dict:
    draft = json.loads(draft_authoring_contract(run_id, brief))
    assert Path(draft["artifact"]).exists()
    return _load_json(draft["artifact"])


def _finalize_contract(
    run_id: str,
    *,
    user_answers: dict | None = None,
    markdown_payload: str = "",
) -> dict:
    review_authoring_contract_for_run(run_id)
    kwargs: dict[str, str] = {"run_id": run_id}
    if user_answers is not None:
        kwargs["user_answers_json"] = json.dumps(user_answers, ensure_ascii=False)
    if markdown_payload:
        markdown_path = RUN_ROOT / run_id / "contract_override.md"
        markdown_path.write_text(markdown_payload, encoding="utf-8")
        kwargs["markdown_path"] = str(markdown_path)
    finalized = json.loads(finalize_authoring_contract(**kwargs))
    _request_confirmation(run_id, "contract")
    confirm_authoring_stage(run_id, "contract", True, "Contract approved.")
    return _load_json(finalized["artifact"])


def _approve_wireframe(run_id: str, overrides: dict | None = None) -> dict:
    built = json.loads(build_wireframe(run_id))
    assert Path(built["artifact"]).exists()
    review_path = Path(built["review_artifact"])
    assert review_path.exists()
    finalized = json.loads(
        finalize_wireframe(
            run_id,
            user_answers_json=json.dumps(overrides or {}, ensure_ascii=False),
        )
    )
    _request_confirmation(run_id, "wireframe")
    confirm_authoring_stage(run_id, "wireframe", True, "Wireframe approved.")
    return _load_json(finalized["artifact"])


def _full_brief() -> str:
    return (
        "Build an executive sales performance dashboard for Matthew.\n"
        "Audience: sales leaders\n"
        "Primary question: Which regions, categories, and sub-categories are driving sales and profit?\n"
        "Please include interactive filtering from the top view into detail."
    )


def _agent_first_direction_payload(selected_direction: dict, selected_direction_id: str) -> dict:
    alternate_direction = {
        "id": "regional_focus",
        "title": "Regional Focus",
        "business_question": "Which regions and states need attention first?",
        "why_it_matters": "Helps leaders compare geographic performance before committing to a dashboard direction.",
        "recommended_kpis": ["Sales", "Profit"],
        "primary_view": {
            "name": "Regional Sales",
            "question": "Which State/Province is driving Sales?",
            "mark_type": "Map",
        },
        "detail_view": {
            "name": "Regional Trend",
            "question": "How is regional sales changing over Order Date?",
            "mark_type": "Line",
        },
        "recommended_filters": ["Order Date", "State/Province"],
        "interaction_pattern": "Map filters detail.",
        "caveats": [],
        "contract_seed": {},
    }
    if selected_direction.get("id") == alternate_direction["id"]:
        alternate_direction["id"] = "category_focus"
        alternate_direction["title"] = "Category Focus"
        alternate_direction["business_question"] = "Which categories and sub-categories drive the business?"
        alternate_direction["detail_view"]["name"] = "Category Trend"
    return {
        "directions": [selected_direction, alternate_direction],
        "selected_direction_id": selected_direction_id,
    }


def test_is_expression_does_not_treat_parenthesized_field_labels_as_formulas():
    assert _is_expression("Product (ID)") is False
    assert _is_expression("Revenue (USD)") is False
    assert _is_expression("[Revenue (USD)]") is True
    assert _is_expression("SUM(Revenue (USD))") is True


def test_contract_review_promotes_top_level_worksheet_shorthand_into_encodings():
    review = json.loads(
        review_authoring_contract_payload(
            json.dumps(
                {
                    "goal": "Build an executive dashboard.",
                    "audience": "Executives",
                    "primary_question": "How are sales and profit trending?",
                    "require_interaction": True,
                    "worksheets": [
                        {
                            "name": "Sales & Profit Trend",
                            "mark_type": "Line",
                            "dimensions": ["Order Date"],
                            "measures": ["Sales", "Profit"],
                            "columns": ["YEAR(Order Date)"],
                            "rows": ["SUM(Sales)", "SUM(Profit)"],
                            "color": "Region",
                            "tooltip": ["Order Date", "SUM(Sales)", "SUM(Profit)"],
                        }
                    ],
                }
            ),
            strict_execution=True,
        ).to_json()
    )
    worksheet = review["normalized_contract"]["worksheets"][0]
    encodings = worksheet["encodings"]
    assert encodings["columns"] == ["YEAR(Order Date)"]
    assert encodings["rows"] == ["SUM(Sales)", "SUM(Profit)"]
    assert encodings["color"] == "Region"
    assert encodings["tooltip"] == ["Order Date", "SUM(Sales)", "SUM(Profit)"]


class TestAuthoringResources:
    def test_contract_resource_contains_workbook_template(self):
        contract = json.loads(read_dashboard_authoring_contract())
        assert "workbook_template" in contract
        assert contract["dataset"] == ""

    def test_skills_index_includes_authoring_workflow(self):
        index_text = read_skills_index()
        assert "authoring_workflow" in index_text
        assert "dashboard_designer" in index_text

    def test_profiles_resources_expose_superstore_profile(self):
        index_text = read_profiles_index()
        assert "superstore" in index_text

    def test_authoring_workflow_skill_is_readable(self):
        skill_text = read_skill("authoring_workflow")
        assert "build_analysis_brief" in skill_text
        assert "build_wireframe" in skill_text
        assert "generate_workbook_from_run" in skill_text


class TestAuthoringPrompts:
    def test_guided_dashboard_authoring_prompt_is_registered(self):
        prompt = server._prompt_manager.get_prompt("guided_dashboard_authoring")
        assert prompt is not None

    def test_guided_dashboard_authoring_prompt_requires_analysis_choice_gate(self):
        messages = asyncio.run(
            server._prompt_manager.render_prompt(
                "guided_dashboard_authoring",
                {
                    "brief": "Build an executive sales dashboard.",
                    "datasource_path": str(XLS_SOURCE),
                },
            )
        )
        text = messages[0].content.text
        assert "build_analysis_brief" in text
        assert "build_wireframe" in text
        assert "interactive_stage_confirmation" in text
        assert "chat_fallback" in text
        assert "stage='schema'" in text
        assert "stage='analysis'" in text
        assert "stage='contract'" in text
        assert "stage='wireframe'" in text
        assert "choose one before you proceed" in text
        assert "Do not collapse to a single recommendation silently." in text
        assert "Keep schema summaries short" in text
        assert "dashboard proposal" in text
        assert "Do not ask the human to approve execution steps unless they explicitly ask to inspect the plan." in text
        assert "stage='execution_plan'" not in text
        assert "Never directly edit files under tmp/agentic_run/{run_id}/." in text
        assert "generate_workbook_from_run" in text

    def test_server_instructions_reference_analysis_choice_gate(self):
        text = server.instructions
        assert "Do not automatically enter guided dashboard authoring" in text
        assert "only when the human explicitly asks for guided authoring" in text
        assert "For ordinary workbook requests, use manual workbook editing" in text
        assert "interactive_stage_confirmation('schema')" in text
        assert "interactive_stage_confirmation('analysis')" in text
        assert "interactive_stage_confirmation('contract')" in text
        assert "interactive_stage_confirmation('wireframe')" in text
        assert "confirm_authoring_stage('schema')" in text
        assert "confirm_authoring_stage('analysis')" in text
        assert "confirm_authoring_stage('contract')" in text
        assert "confirm_authoring_stage('wireframe')" in text
        assert "show those options to the human" in text
        assert "asks the human to confirm schema, analysis, contract, and wireframe" in text
        assert "execution-plan approval gate" in text
        assert "interactive_stage_confirmation('execution_plan')" not in text
        assert "get_client_interaction_capabilities" in text
        assert "Do not switch from an active guided run to low-level workbook tools" in text

    def test_contract_stage_uses_dashboard_proposal_label(self):
        assert _STAGE_LABELS["contract"] == "dashboard proposal review"

    def test_dashboard_brief_to_contract_prompt_uses_schema_summary(self):
        schema_summary = {
            "datasource": {"path": str(XLS_SOURCE), "type": "excel"},
            "selected_primary_object": "Orders",
            "fields": [{"name": "Sales"}, {"name": "Region"}],
            "field_candidates": {
                "dimensions": ["Region"],
                "measures": ["Sales"],
                "date_fields": [],
                "geo_fields": [],
            },
        }
        messages = asyncio.run(
            server._prompt_manager.render_prompt(
                "dashboard_brief_to_contract",
                {
                    "brief": "Build a sales dashboard for leaders.",
                    "schema_summary_json": json.dumps(schema_summary, ensure_ascii=False),
                },
            )
        )
        text = messages[0].content.text
        assert "Schema summary" in text
        assert "Use only fields present in the schema summary" in text

    def test_light_elicitation_uses_review_artifact(self):
        review_payload = {
            "valid": False,
            "summary": "Need clarification.",
            "clarification_questions": ["Who is the audience?"],
            "normalized_contract": {"goal": "Build a dashboard"},
            "detected_profile": "superstore",
        }
        messages = asyncio.run(
            server._prompt_manager.render_prompt(
                "light_elicitation",
                {"contract_review_json": json.dumps(review_payload, ensure_ascii=False)},
            )
        )
        text = messages[0].content.text
        assert "Ask the user only the minimum necessary follow-up questions" in text
        assert "Who is the audience?" in text

    def test_authoring_execution_plan_prompt_mentions_wireframe_and_read_only_plan(self):
        messages = asyncio.run(
            server._prompt_manager.render_prompt(
                "authoring_execution_plan",
                {"contract_final_json": json.dumps({"dashboard": {"name": "Exec"}})},
            )
        )
        text = messages[0].content.text
        assert "wireframe" in text
        assert "internal read-only artifact" in text
        assert "Do not introduce a new human approval gate" in text

    def test_worksheet_clone_refactor_prompt_is_registered(self):
        prompt = server._prompt_manager.get_prompt("worksheet_clone_refactor")
        assert prompt is not None

    def test_worksheet_clone_refactor_prompt_mentions_preview_and_visibility(self):
        messages = asyncio.run(
            server._prompt_manager.render_prompt(
                "worksheet_clone_refactor",
                {
                    "workbook_path": "examples/worksheet_refactor_kpi_profit/5 KPI Design Ideas (2).twb",
                    "source_worksheet": "1. KPI",
                    "target_worksheet": "1. KPI Profit",
                    "replacements_json": json.dumps({"Sales": "Profit"}),
                    "output_path": "output/kpi_profit_clone.twb",
                },
            )
        )
        text = messages[0].content.text
        assert "preview_worksheet_refactor" in text
        assert "set_worksheet_hidden" in text


class TestAuthoringRunLifecycle:
    def test_client_capabilities_without_context_prefer_chat_fallback(self):
        payload = json.loads(get_client_interaction_capabilities())
        assert payload["request_context_available"] is False
        assert payload["form_elicitation_supported"] is False
        assert payload["preferred_confirmation_mode"] == "chat_fallback"

    def test_start_list_status_and_resume(self):
        run = _start_run()
        run_id = run["run_id"]

        listed = json.loads(list_authoring_runs(str(RUN_ROOT)))
        assert any(item["run_id"] == run_id for item in listed["runs"])

        status = json.loads(get_run_status(run_id))
        assert status["status"] == "initialized"
        assert status["datasource_path"].endswith("Sample - Superstore - simple.xls")

        resumed = json.loads(resume_authoring_run(run_id))
        assert resumed["run_id"] == run_id
        assert resumed["needs_attention"] is False

    def test_start_run_reports_mode_mismatch_when_resume_reuses_other_mode(self):
        initial = _start_run(authoring_mode="legacy")
        resumed = _start_run(
            authoring_mode="agent_first",
            resume_if_exists=True,
        )
        assert resumed["run_id"] == initial["run_id"]
        assert resumed["resumed"] is True
        assert resumed["mode_mismatch"] is True
        assert resumed["requested_authoring_mode"] == "agent_first"
        assert resumed["resumed_authoring_mode"] == "legacy"

    def test_force_new_bypasses_resume_reuse(self):
        initial = _start_run(authoring_mode="legacy")
        created = _start_run(
            authoring_mode="agent_first",
            resume_if_exists=True,
            force_new=True,
        )
        assert created["run_id"] != initial["run_id"]
        assert created["resumed"] is False
        assert created["force_new"] is True

    def test_excel_schema_intake_creates_json_and_review_markdown(self):
        run = _start_run()
        payload = json.loads(intake_datasource_schema(run["run_id"]))

        artifact = Path(payload["artifact"])
        review_artifact = Path(payload["review_artifact"])
        assert artifact.exists()
        assert review_artifact.exists()

        schema_summary = json.loads(artifact.read_text(encoding="utf-8"))
        assert schema_summary["datasource"]["type"] == "excel"
        assert schema_summary["fields"]
        assert "dimensions" in schema_summary["field_candidates"]
        assert "# Schema Review" in review_artifact.read_text(encoding="utf-8")

    def test_interactive_stage_confirmation_falls_back_to_chat_without_client_support(self):
        run = _start_run()
        run_id = run["run_id"]
        intake_payload = json.loads(intake_datasource_schema(run_id))

        result = json.loads(
            asyncio.run(
                interactive_stage_confirmation(
                    run_id=run_id,
                    stage="schema",
                    stage_summary="Schema review for fallback coverage.",
                )
            )
        )

        assert result["status"] == "awaiting_human_confirmation"
        assert result["confirmation_mode"] == "chat_fallback"
        assert Path(result["review_artifact"]) == Path(intake_payload["review_artifact"])
        status = json.loads(get_run_status(run_id))
        assert status["status"] == "schema_intaked"

    def test_hyper_schema_intake_lists_tables(self):
        if not HYPER_SOURCE.exists():
            pytest.skip("Sample Hyper datasource not available")
        run = json.loads(
            start_authoring_run(
                datasource_path=str(HYPER_SOURCE),
                output_dir=str(RUN_ROOT),
            )
        )
        try:
            payload = json.loads(intake_datasource_schema(run["run_id"]))
        except RuntimeError as exc:
            pytest.skip(f"Hyper inspection unavailable in this environment: {exc}")
        schema_summary = json.loads(Path(payload["artifact"]).read_text(encoding="utf-8"))
        assert schema_summary["datasource"]["type"] == "hyper"
        assert schema_summary["tables"]
        assert schema_summary["selected_primary_object"]

    def test_analysis_brief_creates_candidate_directions_and_markdown(self):
        run = _start_run()
        run_id = run["run_id"]
        _approve_schema(run_id)

        built = json.loads(build_analysis_brief(run_id))
        review_text = Path(built["review_artifact"]).read_text(encoding="utf-8")
        payload = _load_json(built["artifact"])
        assert 2 <= len(payload["directions"]) <= 4
        assert "selected_direction_id" in payload
        assert "## Editable Overrides" in review_text

    def test_start_run_defaults_to_agent_first_mode(self):
        if not XLS_SOURCE.exists():
            pytest.skip("Sample Excel datasource not available")
        run = json.loads(
            start_authoring_run(
                datasource_path=str(XLS_SOURCE),
                output_dir=str(RUN_ROOT),
            )
        )
        assert run["authoring_mode"] == "agent_first"
        status = json.loads(get_run_status(run["run_id"]))
        assert status["authoring_mode"] == "agent_first"

    def test_agent_first_analysis_brief_requires_agent_authored_directions(self):
        run = _start_run(authoring_mode="agent_first")
        run_id = run["run_id"]
        _approve_schema(run_id)

        built = json.loads(build_analysis_brief(run_id))
        payload = _load_json(built["artifact"])
        review_text = Path(built["review_artifact"]).read_text(encoding="utf-8")
        assert payload["directions"] == []
        assert payload["required_next_step"]
        assert "selected_direction_id" in payload["required_fields"]
        assert "fail-closed" in payload["strict_mode_note"]
        assert payload["direction_template"]["contract_seed"]["worksheets"] == []
        assert "ACTION REQUIRED" in review_text
        assert "No candidate directions have been authored yet." in review_text

        direction_payload = _agent_first_direction_payload(
            {
                "id": "executive_overview",
                "title": "Executive Overview",
                "business_question": "Which states and sub-categories drive sales?",
                "why_it_matters": "Gives leaders a fast read on geography and mix.",
                "recommended_kpis": ["Sales", "Profit", "Quantity", "Profit Ratio"],
                "primary_view": {
                    "name": "Regional Sales",
                    "question": "Which State/Province is driving Sales?",
                    "mark_type": "Map",
                },
                "detail_view": {
                    "name": "Sales Trend",
                    "question": "How is Sales changing over Order Date?",
                    "mark_type": "Line",
                },
                "recommended_filters": ["Order Date", "State/Province", "Sub-Category"],
                "interaction_pattern": "Click the map to filter the related detail views.",
                "caveats": [],
                "contract_seed": {
                    "dashboard": {"name": "Executive Overview", "layout_pattern": "executive overview"},
                    "constraints": {
                        "kpis": ["Sales", "Profit", "Quantity", "Profit Ratio"],
                        "filters": ["Order Date", "State/Province", "Sub-Category"],
                        "interaction_pattern": "Click the map to filter related views.",
                        "layout_pattern": "executive overview",
                    },
                    "worksheets": [],
                    "actions": [],
                },
            },
            "executive_overview",
        )
        finalized = json.loads(
            finalize_analysis_brief(
                run_id,
                user_answers_json=json.dumps(direction_payload, ensure_ascii=False),
            )
        )
        assert finalized["selected_direction_id"] == "executive_overview"

    def test_agent_first_finalize_analysis_brief_requires_multiple_directions(self):
        run = _start_run(authoring_mode="agent_first")
        run_id = run["run_id"]
        _approve_schema(run_id)
        build_analysis_brief(run_id)

        with pytest.raises(RuntimeError, match="2-4 explicit candidate directions"):
            finalize_analysis_brief(
                run_id,
                user_answers_json=json.dumps(
                    {
                        "directions": [
                            {
                                "id": "executive_overview",
                                "title": "Executive Overview",
                                "business_question": "Which states and sub-categories drive sales?",
                                "why_it_matters": "Gives leaders a fast read on geography and mix.",
                                "recommended_kpis": ["Sales", "Profit", "Quantity", "Profit Ratio"],
                                "primary_view": {
                                    "name": "Regional Sales",
                                    "question": "Which State/Province is driving Sales?",
                                    "mark_type": "Map",
                                },
                                "detail_view": {
                                    "name": "Sales Trend",
                                    "question": "How is Sales changing over Order Date?",
                                    "mark_type": "Line",
                                },
                                "recommended_filters": ["Order Date", "State/Province", "Sub-Category"],
                                "interaction_pattern": "Click the map to filter the related detail views.",
                                "caveats": [],
                                "contract_seed": {},
                            }
                        ],
                        "selected_direction_id": "executive_overview",
                    },
                    ensure_ascii=False,
                ),
            )

    def test_agent_first_finalize_contract_fails_closed_without_executable_specs(self):
        run = _start_run(authoring_mode="agent_first")
        run_id = run["run_id"]
        _approve_schema(run_id)
        build_analysis_brief(run_id)
        finalize_analysis_brief(
            run_id,
            user_answers_json=json.dumps(
                _agent_first_direction_payload(
                    {
                        "id": "executive_overview",
                        "title": "Executive Overview",
                        "business_question": "Which states drive sales?",
                        "why_it_matters": "Quick leadership view.",
                        "recommended_kpis": ["Sales"],
                        "primary_view": {"name": "Primary View", "question": "Which states drive sales?", "mark_type": "Map"},
                        "detail_view": {"name": "Detail View", "question": "How is sales changing?", "mark_type": "Line"},
                        "recommended_filters": ["Order Date", "State/Province"],
                        "interaction_pattern": "Map filters detail.",
                        "caveats": [],
                        "contract_seed": {},
                    },
                    "executive_overview",
                ),
                ensure_ascii=False,
            ),
        )
        _request_confirmation(run_id, "analysis")
        confirm_authoring_stage(run_id, "analysis", True, "Analysis approved.")
        draft_authoring_contract(run_id, "Build an executive dashboard.")
        review = json.loads(review_authoring_contract_for_run(run_id))
        assert review["valid"] is False
        with pytest.raises(RuntimeError, match="Contract is not executable yet"):
            finalize_authoring_contract(run_id)

    def test_agent_first_finalize_contract_fails_closed_for_unknown_kpi(self):
        run = _start_run(authoring_mode="agent_first")
        run_id = run["run_id"]
        _approve_schema(run_id)
        build_analysis_brief(run_id)
        finalize_analysis_brief(
            run_id,
            user_answers_json=json.dumps(
                _agent_first_direction_payload(
                    {
                        "id": "exec",
                        "title": "Executive Overview",
                        "business_question": "Which states need attention first?",
                        "why_it_matters": "Leadership summary.",
                        "recommended_kpis": ["Sales", "YoY Growth"],
                        "primary_view": {"name": "Regional Sales", "question": "Which State/Province is driving Sales?", "mark_type": "Map"},
                        "detail_view": {"name": "Sales Trend", "question": "How is Sales trending over Order Date?", "mark_type": "Line"},
                        "recommended_filters": ["Order Date", "State/Province"],
                        "interaction_pattern": "Map filters detail.",
                        "caveats": [],
                        "contract_seed": {},
                    },
                    "exec",
                ),
                ensure_ascii=False,
            ),
        )
        _request_confirmation(run_id, "analysis")
        confirm_authoring_stage(run_id, "analysis", True, "Analysis approved.")
        draft_authoring_contract(run_id, "Build an executive dashboard.")
        review_authoring_contract_for_run(run_id)
        with pytest.raises(RuntimeError, match="Could not resolve field 'YoY Growth'"):
            finalize_authoring_contract(
                run_id,
                user_answers_json=json.dumps(
                    {
                        "audience": "Executives",
                        "primary_question": "Which states need attention first?",
                        "require_interaction": False,
                        "constraints": {"kpis": ["Sales", "YoY Growth"]},
                        "dashboard": {"name": "Executive Overview"},
                        "worksheets": [
                            {
                                "name": "KPI Scorecard",
                                "question": "What are the top-level KPIs?",
                                "mark_type": "Text",
                                "priority": "summary",
                                "kpi_fields": ["Sales", "YoY Growth"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
            )

    def test_agent_first_explicit_calculated_fields_are_materialized_in_plan(self):
        run = _start_run(authoring_mode="agent_first")
        run_id = run["run_id"]
        _approve_schema(run_id)
        build_analysis_brief(run_id)
        finalize_analysis_brief(
            run_id,
            user_answers_json=json.dumps(
                _agent_first_direction_payload(
                    {
                        "id": "exec",
                        "title": "Executive Overview",
                        "business_question": "Which states need attention first?",
                        "why_it_matters": "Leadership summary.",
                        "recommended_kpis": ["Sales", "YoY Growth"],
                        "primary_view": {"name": "Regional Sales", "question": "Which State/Province is driving Sales?", "mark_type": "Map"},
                        "detail_view": {"name": "Sales Trend", "question": "How is Sales trending over Order Date?", "mark_type": "Line"},
                        "recommended_filters": ["Order Date", "State/Province"],
                        "interaction_pattern": "Map filters detail.",
                        "caveats": [],
                        "contract_seed": {},
                    },
                    "exec",
                ),
                ensure_ascii=False,
            ),
        )
        _request_confirmation(run_id, "analysis")
        confirm_authoring_stage(run_id, "analysis", True, "Analysis approved.")
        draft_authoring_contract(run_id, "Build an executive dashboard.")
        review_authoring_contract_for_run(run_id)
        final_contract = json.loads(
            finalize_authoring_contract(
                run_id,
                user_answers_json=json.dumps(
                    {
                        "audience": "Executives",
                        "primary_question": "Which states need attention first?",
                        "require_interaction": False,
                        "calculated_fields": [
                            {
                                "name": "YoY Growth",
                                "formula": "SUM([Sales]) - SUM([Profit])",
                                "datatype": "real",
                            }
                        ],
                        "constraints": {"kpis": ["Sales", "YoY Growth"]},
                        "dashboard": {"name": "Executive Overview"},
                        "worksheets": [
                            {
                                "name": "KPI Scorecard",
                                "question": "What are the top-level KPIs?",
                                "mark_type": "Text",
                                "priority": "summary",
                                "kpi_fields": ["Sales", "YoY Growth"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
            )
        )
        assert final_contract["valid"] is True
        _request_confirmation(run_id, "contract")
        confirm_authoring_stage(run_id, "contract", True, "Contract approved.")
        _approve_wireframe(run_id)
        plan = json.loads(build_execution_plan(run_id))
        manifest = json.loads((RUN_ROOT / run_id / "manifest.json").read_text(encoding="utf-8"))
        plan_payload = _load_json(RUN_ROOT / run_id / manifest["artifacts"]["execution_plan"]["current"])
        calc_steps = [
            step for step in plan_payload["steps"]
            if step["tool"] == "add_calculated_field"
        ]
        assert any(step["args"]["field_name"] == "YoY Growth" for step in calc_steps)
        text_step = next(
            step for step in plan_payload["steps"]
            if step["tool"] == "configure_chart" and step["args"]["worksheet_name"] == "KPI Scorecard"
        )
        assert "YoY Growth" in text_step["args"]["measure_values"]
        assert plan["status"] == "execution_planned"

    def test_legacy_unresolved_kpi_surfaces_resolution_warnings(self):
        run = _start_run(authoring_mode="legacy")
        run_id = run["run_id"]
        _approve_schema(run_id)
        _approve_analysis(run_id, selected_direction_id="executive_overview")
        _draft_contract(run_id, "Build an executive overview dashboard.")
        final_contract = _finalize_contract(
            run_id,
            user_answers={
                "audience": "Executives",
                "primary_question": "Which states need attention first?",
                "require_interaction": True,
                "constraints": {
                    "kpis": ["Sales", "Mystery Growth"],
                },
                "dashboard": {"name": "Executive Overview"},
                "worksheets": [
                    {
                        "name": "KPI Scorecard",
                        "question": "What are the top-level KPIs?",
                        "mark_type": "Text",
                        "priority": "summary",
                        "kpi_fields": ["Sales", "Mystery Growth"],
                    },
                    {
                        "name": "Regional Sales",
                        "question": "Which State/Province is driving Sales?",
                        "mark_type": "Map",
                        "priority": "primary",
                    },
                    {
                        "name": "Sales Trend",
                        "question": "How is Sales trending over Order Date?",
                        "mark_type": "Line",
                        "priority": "detail",
                    },
                ],
            },
        )
        assert any(
            warning["field_name"] == "Mystery Growth"
            for warning in final_contract["resolution_warnings"]
        )
        status = json.loads(get_run_status(run_id))
        assert any(
            warning["field_name"] == "Mystery Growth"
            for warning in status["resolution_warnings"]
        )

    def test_finalize_analysis_brief_accepts_markdown_override(self):
        run = _start_run()
        run_id = run["run_id"]
        _approve_schema(run_id)
        built = json.loads(build_analysis_brief(run_id))
        payload = _load_json(built["artifact"])
        if len(payload["directions"]) < 2:
            pytest.skip("Expected at least two directions for markdown override coverage")
        second_id = payload["directions"][1]["id"]
        override_path = RUN_ROOT / run_id / "analysis_override.md"
        override_path.write_text(
            "# Analysis Review\n\n```yaml\n{\n  \"selected_direction_id\": \"%s\"\n}\n```\n" % second_id,
            encoding="utf-8",
        )
        finalized = json.loads(
            finalize_analysis_brief(run_id, markdown_path=str(override_path))
        )
        assert finalized["selected_direction_id"] == second_id
        _request_confirmation(run_id, "analysis")
        confirm_authoring_stage(run_id, "analysis", True, "Analysis approved from markdown.")

    def test_contract_can_be_rewritten_after_rejection(self):
        run = _start_run()
        run_id = run["run_id"]
        _approve_schema(run_id)
        _approve_analysis(run_id)
        draft_authoring_contract(run_id, "Build a regional sales dashboard.")
        review_authoring_contract_for_run(run_id)
        finalize_authoring_contract(run_id)
        _request_confirmation(run_id, "contract")
        confirm_authoring_stage(run_id, "contract", False, "Please rewrite from scratch.")

        rewrite = json.loads(
            draft_authoring_contract(
                run_id,
                "Rewrite this as an executive profitability dashboard.",
                rewrite=True,
            )
        )
        assert rewrite["status"] == "contract_drafted"

    def test_draft_contract_prefers_explicit_audience_and_primary_question_labels(self):
        run = _start_run()
        run_id = run["run_id"]
        _approve_schema(run_id)
        _approve_analysis(run_id)

        draft = json.loads(draft_authoring_contract(run_id, _full_brief()))
        contract = json.loads(Path(draft["artifact"]).read_text(encoding="utf-8"))
        assert contract["audience"] == "sales leaders"
        assert (
            contract["primary_question"]
            == "Which regions, categories, and sub-categories are driving sales and profit?"
        )

    def test_finalize_contract_accepts_markdown_override(self):
        run = _start_run()
        run_id = run["run_id"]
        _approve_schema(run_id)
        _approve_analysis(run_id)
        _draft_contract(run_id, _full_brief())

        markdown_payload = (
            "# Contract Review\n\n"
            "```yaml\n"
            "{\n"
            "  \"audience\": \"regional sales leaders\",\n"
            "  \"require_interaction\": true\n"
            "}\n"
            "```\n"
        )
        contract = _finalize_contract(run_id, markdown_payload=markdown_payload)
        review_artifact = Path(RUN_ROOT / run_id / json.loads(get_run_status(run_id))["artifacts"]["contract_final"]["review_current"])
        assert contract["audience"] == "regional sales leaders"
        assert contract["require_interaction"] is True
        assert review_artifact.exists()

    def test_wireframe_creates_ascii_review_and_support_notes(self):
        run = _start_run()
        run_id = run["run_id"]
        _approve_schema(run_id)
        _approve_analysis(run_id)
        _draft_contract(run_id, _full_brief())
        _finalize_contract(
            run_id,
            user_answers={
                "require_interaction": True,
                "actions": [
                    {
                        "type": "url",
                        "source": "dashboard_title",
                        "url": "https://www.tableau.com",
                        "caption": "Visit Tableau",
                    }
                ],
            },
        )

        wireframe = _approve_wireframe(run_id)
        review_artifact = json.loads(get_run_status(run_id))["artifacts"]["wireframe"]["review_current"]
        review_text = Path(RUN_ROOT / run_id / review_artifact).read_text(encoding="utf-8")
        assert "ascii_wireframe" in wireframe
        assert "layout_description" in wireframe
        assert "layout_tree" in wireframe
        assert wireframe["layout_tree"]["type"] == "container"
        assert "layout_json_artifact" in wireframe
        assert Path(RUN_ROOT / run_id / wireframe["layout_json_artifact"]).exists()
        assert "WORKSHEET [fixed 88]" in wireframe["ascii_wireframe"]
        assert any(action["support_level"] in {"supported", "workaround"} for action in wireframe["actions"])
        assert "```text" in review_text
        assert "## Layout Schema" in review_text

    def test_wireframe_treats_row_based_exec_layout_alias_as_executive_overview(self):
        run = _start_run()
        run_id = run["run_id"]
        _approve_schema(run_id)
        _approve_analysis(run_id)
        _draft_contract(run_id, _full_brief())
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Executives",
                "primary_question": "How is the business performing across sales, profit, regions, and categories?",
                "require_interaction": True,
                "dashboard": {
                    "name": "Executive Overview",
                    "layout_pattern": "top-kpis + trend-row + breakdown-row",
                },
                "constraints": {
                    "layout_pattern": "top-kpis + trend-row + breakdown-row",
                    "filters": ["Order Date", "Region", "Category"],
                },
                "worksheets": [
                    {
                        "name": "KPI Scorecards",
                        "mark_type": "Text",
                        "priority": "summary",
                        "kpi_fields": ["Sales", "Profit", "Quantity"],
                    },
                    {
                        "name": "Sales & Profit Trend",
                        "mark_type": "Line",
                        "priority": "primary",
                        "dimensions": ["Order Date"],
                        "measures": ["Sales", "Profit"],
                        "columns": ["YEAR(Order Date)"],
                        "rows": ["SUM(Sales)", "SUM(Profit)"],
                    },
                    {
                        "name": "Sales by Region",
                        "mark_type": "Bar",
                        "priority": "detail",
                        "dimensions": ["Region"],
                        "measures": ["Sales", "Profit"],
                        "rows": ["Region"],
                        "columns": ["SUM(Sales)"],
                        "color": "SUM(Profit)",
                    },
                    {
                        "name": "Category Mix",
                        "mark_type": "Pie",
                        "dimensions": ["Category"],
                        "measures": ["Sales"],
                        "color": "Category",
                        "wedge_size": "SUM(Sales)",
                    },
                    {
                        "name": "Sub-Category Performance",
                        "mark_type": "Bar",
                        "dimensions": ["Sub-Category"],
                        "measures": ["Sales", "Profit"],
                        "rows": ["Sub-Category"],
                        "columns": ["SUM(Sales)"],
                        "color": "SUM(Profit)",
                    },
                ],
            },
        )

        wireframe = _approve_wireframe(run_id)
        children = wireframe["layout_tree"]["children"]
        assert children[0]["type"] == "worksheet"
        assert children[0]["name"] == "KPI Scorecards"
        assert children[1]["type"] == "container"
        assert children[1]["direction"] == "horizontal"
        assert [child["type"] for child in children[1]["children"]] == ["worksheet", "container"]
        assert children[1]["children"][0]["name"] == "Sales & Profit Trend"
        assert children[2]["type"] == "container"
        assert children[2]["direction"] == "horizontal"
        bottom_names = [
            child.get("name", "")
            for child in children[2]["children"]
            if child.get("type") == "worksheet"
        ]
        assert "Sales by Region" in bottom_names

    def test_execution_plan_requires_wireframe_confirmation(self):
        run = _start_run()
        run_id = run["run_id"]
        _approve_schema(run_id)
        _approve_analysis(run_id)
        _draft_contract(run_id, _full_brief())
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Sales leaders",
                "primary_question": "Which regions and categories are driving sales?",
                "require_interaction": True,
            },
        )
        with pytest.raises(RuntimeError):
            build_execution_plan(run_id)

    def test_execution_plan_prefers_regional_geo_and_multi_target_actions(self):
        run = _start_run()
        run_id = run["run_id"]
        _approve_schema(run_id)
        _approve_analysis(run_id, selected_direction_id="executive_overview")
        _draft_contract(run_id, _full_brief())
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Sales leaders",
                "primary_question": "Which regions, categories, and sub-categories are driving sales and profit?",
                "require_interaction": True,
            },
        )
        _approve_wireframe(run_id)

        plan = json.loads(build_execution_plan(run_id))
        payload = json.loads(Path(plan["artifact"]).read_text(encoding="utf-8"))
        review_text = Path(plan["review_artifact"]).read_text(encoding="utf-8")
        primary_view_step = next(
            step
            for step in payload["steps"]
            if step["tool"] == "configure_chart"
            and step["args"].get("worksheet_name") == "Primary View"
        )
        assert primary_view_step["args"]["geographic_field"] == "State/Province"

        action_steps = [step for step in payload["steps"] if step["tool"] == "add_dashboard_action"]
        assert {step["args"]["target_sheet"] for step in action_steps} == {"Summary View", "Detail View"}
        assert all(step["args"]["source_sheet"] == "Primary View" for step in action_steps)
        assert all(step["args"]["fields"] == ["State/Province"] for step in action_steps)
        assert "read-only" in review_text

        dashboard_step = next(step for step in payload["steps"] if step["tool"] == "add_dashboard")
        assert str(dashboard_step["args"]["layout"]).endswith(".layout.json")
        assert Path(dashboard_step["args"]["layout"]).exists()

    def test_execution_plan_uses_dual_axis_for_bar_line_time_series(self):
        run = _start_run()
        run_id = run["run_id"]
        _approve_schema(run_id)
        _approve_analysis(run_id, selected_direction_id="executive_overview")
        _draft_contract(run_id, "Build an executive overview dashboard.")
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Executives",
                "primary_question": "How are sales and profit trending over time?",
                "require_interaction": True,
                "dashboard": {"name": "Executive Overview"},
                "worksheets": [
                    {
                        "name": "KPI Scorecard",
                        "question": "What are the top-level KPIs?",
                        "mark_type": "Text",
                        "priority": "summary",
                        "kpi_fields": ["Sales", "Profit"],
                    },
                    {
                        "name": "Sales & Profit Trend",
                        "question": "Sales bar + Profit line on a secondary axis over Order Date.",
                        "mark_type": "Bar",
                        "priority": "primary",
                        "dimensions": ["Order Date"],
                        "measures": ["Sales", "Profit"],
                        "encodings": {
                            "columns": ["MONTH(Order Date)"],
                            "rows": ["SUM(Sales)", "SUM(Profit)"],
                            "tooltip": ["Order Date", "SUM(Sales)", "SUM(Profit)"],
                        },
                    },
                    {
                        "name": "Sales by Region",
                        "question": "Which regions drive sales?",
                        "mark_type": "Bar",
                        "priority": "detail",
                        "dimensions": ["Region"],
                        "measures": ["Sales"],
                        "encodings": {
                            "rows": ["Region"],
                            "columns": ["SUM(Sales)"],
                        },
                    },
                ],
                "actions": [
                    {
                        "type": "highlight",
                        "source": "Sales by Region",
                        "targets": ["Sales & Profit Trend"],
                        "fields": ["Region"],
                    }
                ],
            },
        )
        _approve_wireframe(run_id)

        plan = json.loads(build_execution_plan(run_id))
        payload = json.loads(Path(plan["artifact"]).read_text(encoding="utf-8"))
        trend_step = next(
            step
            for step in payload["steps"]
            if step["tool"] == "configure_dual_axis"
            and step["args"].get("worksheet_name") == "Sales & Profit Trend"
        )
        assert trend_step["args"]["mark_type_1"] == "Bar"
        assert trend_step["args"]["mark_type_2"] == "Line"
        assert trend_step["args"]["dual_axis_shelf"] == "rows"
        assert trend_step["args"]["rows"] == ["SUM(Sales)", "SUM(Profit)"]

        _request_confirmation(run_id, "execution_plan")
        confirm_authoring_stage(run_id, "execution_plan", True, "Execution plan approved.")
        generated = json.loads(generate_workbook_from_run(run_id))
        workbook_path = Path(generated["final_workbook"])
        mark_classes = _worksheet_pane_mark_classes(workbook_path, "Sales & Profit Trend")
        assert "Bar" in mark_classes
        assert "Line" in mark_classes

    def test_execution_plan_uses_kpi_pie_specs_and_multi_target_contract_actions(self):
        run = _start_run()
        run_id = run["run_id"]
        _approve_schema(run_id)
        _approve_analysis(run_id, selected_direction_id="executive_overview")
        _draft_contract(run_id, "Build an executive overview dashboard.")
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Executives",
                "primary_question": "Which states and sub-categories drive sales?",
                "require_interaction": True,
                "constraints": {
                    "kpis": ["Sales", "Profit", "Quantity", "Discount", "Profit Ratio"],
                    "filters": ["Order Date", "State/Province", "Category", "Sub-Category", "Segment"],
                },
                "dashboard": {"name": "Executive Overview"},
                "worksheets": [
                    {
                        "name": "KPI Scorecard",
                        "question": "What are the top-level KPIs?",
                        "mark_type": "Text",
                        "priority": "summary",
                        "kpi_fields": ["Sales", "Profit", "Quantity", "Discount", "Profit Ratio"],
                    },
                    {
                        "name": "Regional Sales",
                        "question": "Which State/Province is driving Sales?",
                        "mark_type": "Map",
                        "priority": "primary",
                    },
                    {
                        "name": "Sales Trend",
                        "question": "How is Sales trending over Order Date?",
                        "mark_type": "Line",
                        "priority": "detail",
                    },
                    {
                        "name": "Sub-Category Mix",
                        "question": "Which Sub-Category contributes most to Sales?",
                        "mark_type": "Pie",
                        "priority": "secondary",
                    },
                ],
                "actions": [
                    {
                        "type": "filter",
                        "source": "Regional Sales",
                        "targets": ["KPI Scorecard", "Sales Trend", "Sub-Category Mix"],
                        "fields": ["State/Province"],
                        "caption": "Filter related views from Regional Sales",
                    }
                ],
            },
        )
        _approve_wireframe(run_id)

        plan = json.loads(build_execution_plan(run_id))
        payload = json.loads(Path(plan["artifact"]).read_text(encoding="utf-8"))

        kpi_step = next(
            step
            for step in payload["steps"]
            if step["tool"] == "configure_chart"
            and step["args"].get("worksheet_name") == "KPI Scorecard"
        )
        assert kpi_step["args"]["measure_values"] == [
            "SUM(Sales)",
            "SUM(Profit)",
            "SUM(Quantity)",
            "AVG(Discount)",
            "Profit Ratio",
        ]

        pie_step = next(
            step
            for step in payload["steps"]
            if step["tool"] == "configure_chart"
            and step["args"].get("worksheet_name") == "Sub-Category Mix"
        )
        assert pie_step["args"]["mark_type"] == "Pie"
        assert pie_step["args"]["color"] == "Sub-Category"
        assert pie_step["args"]["wedge_size"] == "SUM(Sales)"

        action_steps = [
            step for step in payload["steps"]
            if step["tool"] == "add_dashboard_action"
        ]
        assert {step["args"]["target_sheet"] for step in action_steps} == {
            "KPI Scorecard",
            "Sales Trend",
            "Sub-Category Mix",
        }

    def test_agent_first_execution_plan_requires_confirmed_layout_tree(self):
        run = _start_run(authoring_mode="agent_first")
        run_id = run["run_id"]
        _approve_schema(run_id)
        build_analysis_brief(run_id)
        finalize_analysis_brief(
            run_id,
            user_answers_json=json.dumps(
                _agent_first_direction_payload(
                    {
                        "id": "executive_overview",
                        "title": "Executive Overview",
                        "business_question": "Which states drive sales?",
                        "why_it_matters": "Quick leadership view.",
                        "recommended_kpis": ["Sales", "Profit"],
                        "primary_view": {"name": "Regional Sales", "question": "Which State/Province is driving Sales?", "mark_type": "Map"},
                        "detail_view": {"name": "Sales Trend", "question": "How is Sales trending over Order Date?", "mark_type": "Line"},
                        "recommended_filters": ["Order Date", "State/Province"],
                        "interaction_pattern": "Map filters detail.",
                        "caveats": [],
                        "contract_seed": {},
                    },
                    "executive_overview",
                ),
                ensure_ascii=False,
            ),
        )
        _request_confirmation(run_id, "analysis")
        confirm_authoring_stage(run_id, "analysis", True, "Analysis approved.")
        draft_authoring_contract(run_id, "Build an executive dashboard.")
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Executives",
                "primary_question": "Which states drive sales?",
                "require_interaction": True,
                "dashboard": {"name": "Executive Overview"},
                "constraints": {
                    "kpis": ["Sales", "Profit"],
                    "filters": ["Order Date", "State/Province"],
                },
                "worksheets": [
                    {
                        "name": "KPI Scorecard",
                        "question": "What are the top-level KPIs?",
                        "mark_type": "Text",
                        "priority": "summary",
                        "kpi_fields": ["Sales", "Profit"],
                    },
                    {
                        "name": "Regional Sales",
                        "question": "Which State/Province is driving Sales?",
                        "mark_type": "Map",
                        "priority": "primary",
                        "dimensions": ["State/Province"],
                        "measures": ["Sales"],
                    },
                    {
                        "name": "Sales Trend",
                        "question": "How is Sales trending over Order Date?",
                        "mark_type": "Line",
                        "priority": "detail",
                        "dimensions": ["Order Date"],
                        "measures": ["Sales"],
                    },
                ],
                "actions": [
                    {
                        "type": "filter",
                        "source": "Regional Sales",
                        "targets": ["KPI Scorecard", "Sales Trend"],
                        "fields": ["State/Province"],
                    }
                ],
            },
        )
        built = json.loads(build_wireframe(run_id))
        finalize_wireframe(
            run_id,
            user_answers_json=json.dumps({"layout_tree": None}, ensure_ascii=False),
        )
        _request_confirmation(run_id, "wireframe")
        confirm_authoring_stage(run_id, "wireframe", True, "Wireframe approved without layout tree.")

        with pytest.raises(RuntimeError, match="missing layout_tree"):
            build_execution_plan(run_id)

    def test_agent_first_contract_finalize_requires_explicit_actions_when_interaction_is_requested(self):
        run = _start_run(authoring_mode="agent_first")
        run_id = run["run_id"]
        _approve_schema(run_id)
        build_analysis_brief(run_id)
        finalize_analysis_brief(
            run_id,
            user_answers_json=json.dumps(
                _agent_first_direction_payload(
                    {
                        "id": "executive_overview",
                        "title": "Executive Overview",
                        "business_question": "Which states drive sales?",
                        "why_it_matters": "Quick leadership view.",
                        "recommended_kpis": ["Sales", "Profit"],
                        "primary_view": {"name": "Regional Sales", "question": "Which State/Province is driving Sales?", "mark_type": "Map"},
                        "detail_view": {"name": "Sales Trend", "question": "How is Sales trending over Order Date?", "mark_type": "Line"},
                        "recommended_filters": ["Order Date", "State/Province"],
                        "interaction_pattern": "Map filters detail.",
                        "caveats": [],
                        "contract_seed": {},
                    },
                    "executive_overview",
                ),
                ensure_ascii=False,
            ),
        )
        _request_confirmation(run_id, "analysis")
        confirm_authoring_stage(run_id, "analysis", True, "Analysis approved.")
        draft_authoring_contract(run_id, "Build an executive dashboard.")
        review_authoring_contract_for_run(run_id)
        with pytest.raises(RuntimeError, match="What dashboard action should be configured"):
            finalize_authoring_contract(
                run_id,
                user_answers_json=json.dumps(
                    {
                        "audience": "Executives",
                        "primary_question": "Which states drive sales?",
                        "require_interaction": True,
                        "dashboard": {"name": "Executive Overview"},
                        "constraints": {
                            "kpis": ["Sales", "Profit"],
                            "filters": ["Order Date", "State/Province"],
                        },
                        "worksheets": [
                            {
                                "name": "KPI Scorecard",
                                "question": "What are the top-level KPIs?",
                                "mark_type": "Text",
                                "priority": "summary",
                                "kpi_fields": ["Sales", "Profit"],
                            },
                            {
                                "name": "Regional Sales",
                                "question": "Which State/Province is driving Sales?",
                                "mark_type": "Map",
                                "priority": "primary",
                                "dimensions": ["State/Province"],
                                "measures": ["Sales"],
                            },
                            {
                                "name": "Sales Trend",
                                "question": "How is Sales trending over Order Date?",
                                "mark_type": "Line",
                                "priority": "detail",
                                "dimensions": ["Order Date"],
                                "measures": ["Sales"],
                            },
                        ],
                        "actions": [],
                    },
                    ensure_ascii=False,
                ),
            )

    def test_confirm_authoring_stage_requires_fresh_interactive_request(self):
        run = _start_run()
        run_id = run["run_id"]

        intake_datasource_schema(run_id)
        with pytest.raises(RuntimeError, match="interactive_stage_confirmation"):
            confirm_authoring_stage(run_id, "schema", True, "Skipping the interactive request should fail.")

    def test_reopen_contract_after_confirmation_clears_downstream_scope(self):
        run = _start_run()
        run_id = run["run_id"]

        _approve_schema(run_id)
        _approve_analysis(run_id, selected_direction_id="executive_overview")
        _draft_contract(run_id, _full_brief())
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Sales leaders",
                "primary_question": "Which regions need attention first?",
                "require_interaction": True,
            },
        )
        _approve_wireframe(run_id)
        build_execution_plan(run_id)

        reopened = json.loads(
            reopen_authoring_stage(
                run_id,
                "contract",
                "Add a Sales by Segment worksheet before execution.",
            )
        )
        assert reopened["status"] == "contract_finalized"
        assert reopened["previous_status"] == "execution_planned"
        assert "wireframe" in reopened["cleared_artifacts"]
        assert "execution_plan" in reopened["cleared_artifacts"]
        assert reopened["next_steps"]

        status = json.loads(get_run_status(run_id))
        assert status["status"] == "contract_finalized"
        assert status["artifacts"]["wireframe"]["current"] == ""
        assert status["artifacts"]["execution_plan"]["current"] == ""
        assert status["pending_confirmation"] == {}

    def test_execution_plan_rejects_wireframe_scope_drift(self):
        run = _start_run()
        run_id = run["run_id"]

        _approve_schema(run_id)
        _approve_analysis(run_id, selected_direction_id="executive_overview")
        _draft_contract(run_id, _full_brief())
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Sales leaders",
                "primary_question": "Which regions need attention first?",
                "require_interaction": True,
            },
        )

        built = json.loads(build_wireframe(run_id))
        assert Path(built["artifact"]).exists()
        finalize_wireframe(
            run_id,
            user_answers_json=json.dumps(
                {
                    "support_notes": [
                        "Add a Sales by Segment bar chart as an additional worksheet alongside the existing views."
                    ]
                },
                ensure_ascii=False,
            ),
        )
        _request_confirmation(run_id, "wireframe")
        confirm_authoring_stage(run_id, "wireframe", True, "Wireframe approved.")

        with pytest.raises(RuntimeError, match="Reopen the contract stage"):
            build_execution_plan(run_id)

    def test_full_guided_run_generates_workbook_and_reports(self):
        run = _start_run()
        run_id = run["run_id"]

        _approve_schema(run_id)
        _approve_analysis(run_id, selected_direction_id="executive_overview")
        _draft_contract(
            run_id,
            "Build an executive sales dashboard for sales leaders with interactive filtering.",
        )
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Sales leaders",
                "primary_question": "Which regions need attention first?",
                "require_interaction": True,
            },
        )
        _approve_wireframe(run_id)

        plan = json.loads(build_execution_plan(run_id))
        assert plan["status"] == "execution_planned"
        _request_confirmation(run_id, "execution_plan")
        confirm_authoring_stage(run_id, "execution_plan", True, "Execution plan approved.")

        generated = json.loads(generate_workbook_from_run(run_id))
        workbook_path = Path(generated["final_workbook"])
        assert workbook_path.exists()
        assert generated["status"] == "analyzed"

        status = json.loads(get_run_status(run_id))
        assert status["status"] == "analyzed"
        assert any(name.startswith("schema_summary.") and name.endswith(".md") for name in status["artifacts_present"])
        assert any(name.startswith("analysis_brief.") and name.endswith(".md") for name in status["artifacts_present"])
        assert any(name.startswith("wireframe.") and name.endswith(".md") for name in status["artifacts_present"])
        assert any(name.startswith("semantic_validation.") for name in status["artifacts_present"])
        assert any(name.startswith("validation_report.") for name in status["artifacts_present"])
        assert any(name.startswith("analysis_report.") for name in status["artifacts_present"])
        assert status["semantic_validation"]["status"] == "semantic_validation_passed"

        root = ET.parse(workbook_path).getroot()
        caption = root.find(".//worksheet[@name='Summary View']/layout-options/caption/formatted-text/run")
        assert caption is not None

    def test_generated_workbook_semantics_cover_multi_kpi_pie_and_actions(self):
        run = _start_run()
        run_id = run["run_id"]

        _approve_schema(run_id)
        _approve_analysis(run_id, selected_direction_id="executive_overview")
        _draft_contract(run_id, "Build an executive overview dashboard.")
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Executives",
                "primary_question": "Which states and sub-categories drive sales?",
                "require_interaction": True,
                "constraints": {
                    "kpis": ["Sales", "Profit", "Quantity", "Discount", "Profit Ratio"],
                    "filters": ["Order Date", "State/Province", "Category", "Sub-Category", "Segment"],
                },
                "dashboard": {"name": "Executive Overview"},
                "worksheets": [
                    {
                        "name": "KPI Scorecard",
                        "question": "What are the top-level KPIs?",
                        "mark_type": "Text",
                        "priority": "summary",
                        "kpi_fields": ["Sales", "Profit", "Quantity", "Discount", "Profit Ratio"],
                    },
                    {
                        "name": "Regional Sales",
                        "question": "Which State/Province is driving Sales?",
                        "mark_type": "Map",
                        "priority": "primary",
                    },
                    {
                        "name": "Sales Trend",
                        "question": "How is Sales trending over Order Date?",
                        "mark_type": "Line",
                        "priority": "detail",
                    },
                    {
                        "name": "Sub-Category Mix",
                        "question": "Which Sub-Category contributes most to Sales?",
                        "mark_type": "Pie",
                        "priority": "secondary",
                    },
                ],
                "actions": [
                    {
                        "type": "filter",
                        "source": "Regional Sales",
                        "targets": ["KPI Scorecard", "Sales Trend", "Sub-Category Mix"],
                        "fields": ["State/Province"],
                        "caption": "Filter related views from Regional Sales",
                    }
                ],
            },
        )
        _approve_wireframe(run_id)
        build_execution_plan(run_id)
        _request_confirmation(run_id, "execution_plan")
        confirm_authoring_stage(run_id, "execution_plan", True, "Execution plan approved.")

        generated = json.loads(generate_workbook_from_run(run_id))
        workbook_path = Path(generated["final_workbook"])
        assert workbook_path.exists()
        assert generated["semantic_validation"]["status"] == "semantic_validation_passed"

        members = _measure_name_members(workbook_path, "KPI Scorecard")
        for token in ("Sales", "Profit", "Quantity", "Discount"):
            assert any(token.casefold() in member.casefold() for member in members)

        pie_colors = _worksheet_encoding_columns(workbook_path, "Sub-Category Mix", "color")
        pie_sizes = _worksheet_encoding_columns(workbook_path, "Sub-Category Mix", "wedge-size")
        assert any("sub-category" in value.casefold() for value in pie_colors)
        assert any("sales" in value.casefold() for value in pie_sizes)

        action_targets = _dashboard_action_targets(
            workbook_path,
            "Executive Overview",
            "Regional Sales",
        )
        assert set(action_targets) >= {"KPI Scorecard", "Sales Trend", "Sub-Category Mix"}

        root = ET.parse(workbook_path).getroot()
        dashboard = root.find(".//dashboards/dashboard[@name='Executive Overview']")
        assert dashboard is not None
        root_zone = dashboard.find("zones/zone")
        assert root_zone is not None
        assert root_zone.get("param") == "vert"
        top_zone = root_zone.find("./zone")
        assert top_zone is not None
        assert top_zone.get("name") == "KPI Scorecard"
        assert top_zone.get("fixed-size") == "88"
        filter_zones = dashboard.findall(".//zone[@type-v2='filter']")
        assert filter_zones

    def test_semantic_validator_detects_missing_confirmed_kpi(self):
        run = _start_run()
        run_id = run["run_id"]

        _approve_schema(run_id)
        _approve_analysis(run_id, selected_direction_id="executive_overview")
        _draft_contract(run_id, "Build an executive overview dashboard.")
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Executives",
                "primary_question": "Which states and sub-categories drive sales?",
                "require_interaction": True,
                "constraints": {
                    "kpis": ["Sales", "Profit", "Quantity", "Discount", "Profit Ratio"],
                },
                "dashboard": {"name": "Executive Overview"},
                "worksheets": [
                    {
                        "name": "KPI Scorecard",
                        "question": "What are the top-level KPIs?",
                        "mark_type": "Text",
                        "priority": "summary",
                        "kpi_fields": ["Sales", "Profit", "Quantity", "Discount", "Profit Ratio"],
                    },
                    {
                        "name": "Regional Sales",
                        "question": "Which State/Province is driving Sales?",
                        "mark_type": "Map",
                        "priority": "primary",
                    },
                    {
                        "name": "Sales Trend",
                        "question": "How is Sales trending over Order Date?",
                        "mark_type": "Line",
                        "priority": "detail",
                    },
                ],
            },
        )
        _approve_wireframe(run_id)
        build_execution_plan(run_id)
        _request_confirmation(run_id, "execution_plan")
        confirm_authoring_stage(run_id, "execution_plan", True, "Execution plan approved.")

        generated = json.loads(generate_workbook_from_run(run_id))
        workbook_path = Path(generated["final_workbook"])
        broken_dir = RUN_ROOT / run_id / "semantic_break"
        broken_dir.mkdir(parents=True, exist_ok=True)
        broken_path = broken_dir / "broken_semantics.twb"
        root = ET.parse(workbook_path)
        worksheet = root.getroot().find(".//worksheet[@name='KPI Scorecard']")
        assert worksheet is not None
        for filter_el in worksheet.findall(".//view/filter"):
            if ":Measure Names" not in filter_el.get("column", ""):
                continue
            member = filter_el.find(".//groupfilter[@function='member']")
            if member is not None:
                parent = filter_el.find(".//groupfilter")
                if parent is not None and member in list(parent):
                    parent.remove(member)
                    break
        root.write(broken_path, encoding="utf-8", xml_declaration=True)

        with pytest.raises(RuntimeError, match="semantic validation failed"):
            validate_generated_workbook_semantics(run_id, str(broken_path))

    def test_generation_surfaces_structured_semantic_validation_failure(self):
        run = _start_run()
        run_id = run["run_id"]

        _approve_schema(run_id)
        _approve_analysis(run_id, selected_direction_id="executive_overview")
        _draft_contract(run_id, "Build an executive overview dashboard.")
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Executives",
                "primary_question": "Which states and sub-categories drive sales?",
                "require_interaction": True,
                "constraints": {
                    "kpis": ["Sales", "Profit", "Quantity", "Discount", "Profit Ratio"],
                },
                "dashboard": {"name": "Executive Overview"},
                "worksheets": [
                    {
                        "name": "KPI Scorecard",
                        "question": "What are the top-level KPIs?",
                        "mark_type": "Text",
                        "priority": "summary",
                        "kpi_fields": ["Sales", "Profit", "Quantity", "Discount", "Profit Ratio"],
                    },
                    {
                        "name": "Regional Sales",
                        "question": "Which State/Province is driving Sales?",
                        "mark_type": "Map",
                        "priority": "primary",
                    },
                    {
                        "name": "Sales Trend",
                        "question": "How is Sales trending over Order Date?",
                        "mark_type": "Line",
                        "priority": "detail",
                    },
                ],
                "actions": [
                    {
                        "type": "filter",
                        "source": "Regional Sales",
                        "targets": ["KPI Scorecard", "Sales Trend"],
                        "fields": ["State/Province"],
                    }
                ],
            },
        )
        _approve_wireframe(run_id)
        build_execution_plan(run_id)

        manifest = json.loads((RUN_ROOT / run_id / "manifest.json").read_text(encoding="utf-8"))
        plan_path = RUN_ROOT / run_id / manifest["artifacts"]["execution_plan"]["current"]
        plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
        for step in plan_payload["steps"]:
            if step["tool"] != "configure_chart":
                continue
            if step["args"].get("worksheet_name") != "KPI Scorecard":
                continue
            step["args"]["measure_values"] = [
                value
                for value in step["args"].get("measure_values", [])
                if "Profit Ratio" not in value
            ]
            break
        plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        _request_confirmation(run_id, "execution_plan")
        confirm_authoring_stage(run_id, "execution_plan", True, "Execution plan approved.")

        with pytest.raises(RuntimeError, match="semantic validation failed"):
            generate_workbook_from_run(run_id)

        status = json.loads(get_run_status(run_id))
        assert status["status"] == "workbook_generation_failed"
        assert status["last_error"]["step_tool"] == "semantic_validation"
        assert status["last_error"]["semantic_validation"]["status"] == "semantic_validation_failed"
        assert status["semantic_validation"]["status"] == "semantic_validation_failed"

    def test_generation_failure_sets_failed_status_and_can_reopen_execution(self):
        run = _start_run()
        run_id = run["run_id"]

        _approve_schema(run_id)
        _approve_analysis(run_id)
        _draft_contract(
            run_id,
            "Build an executive sales dashboard for sales leaders with interactive filtering.",
        )
        _finalize_contract(
            run_id,
            user_answers={
                "audience": "Sales leaders",
                "primary_question": "Which regions need attention first?",
                "require_interaction": True,
            },
        )
        _approve_wireframe(run_id)
        build_execution_plan(run_id)

        manifest = json.loads((RUN_ROOT / run_id / "manifest.json").read_text(encoding="utf-8"))
        plan_path = RUN_ROOT / run_id / manifest["artifacts"]["execution_plan"]["current"]
        plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
        plan_payload["steps"][1]["tool"] = "save_workbook"
        plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        _request_confirmation(run_id, "execution_plan")
        confirm_authoring_stage(run_id, "execution_plan", True, "Approve the broken plan for failure coverage.")
        with pytest.raises(RuntimeError):
            generate_workbook_from_run(run_id)

        failed_status = json.loads(get_run_status(run_id))
        assert failed_status["status"] == "workbook_generation_failed"
        assert failed_status["last_error"]["step_tool"] == "save_workbook"

        reopened = json.loads(
            reopen_authoring_stage(
                run_id,
                "execution_plan",
                "Reopen the read-only plan stage after the failed generation attempt.",
            )
        )
        assert reopened["status"] == "execution_planned"
        recovered_status = json.loads(get_run_status(run_id))
        assert recovered_status["last_error"] == {}
