"""Regression coverage for Agentic BI Authoring V1 surfaces."""

from __future__ import annotations

import asyncio
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import uuid4

import pytest

from cwtwb.mcp.resources import (
    read_dataset_profile,
    read_dashboard_authoring_contract,
    read_profiles_index,
    read_skill,
    read_skills_index,
)
from cwtwb.server import (
    add_dashboard,
    add_dashboard_action,
    add_worksheet,
    configure_chart,
    create_workbook,
    review_authoring_contract,
    save_workbook,
    server,
    set_worksheet_caption,
    validate_workbook,
    analyze_twb,
)


TEMPLATE = Path("templates/twb/superstore.twb")


@pytest.fixture(autouse=True)
def fresh_workbook():
    create_workbook(str(TEMPLATE), "Agentic BI Tests")


@pytest.fixture
def tmp_file_factory():
    root = Path("tmp")
    root.mkdir(exist_ok=True)
    created: list[Path] = []

    def build(name: str) -> Path:
        path = root / f"{uuid4().hex}_{name}"
        created.append(path)
        return path

    try:
        yield build
    finally:
        for path in created:
            path.unlink(missing_ok=True)


class TestAuthoringResources:
    def test_contract_resource_contains_expected_sections(self):
        contract = json.loads(read_dashboard_authoring_contract())
        assert "goal" in contract
        assert "audience" in contract
        assert "constraints" in contract
        assert "dashboard" in contract
        assert "actions" in contract
        assert contract["dataset"] == ""
        assert contract["dataset_profile"] == ""

    def test_skills_index_includes_authoring_workflow(self):
        index_text = read_skills_index()
        assert "authoring_workflow" in index_text
        assert "dashboard_designer" in index_text

    def test_profiles_resources_expose_superstore_profile(self):
        index_text = read_profiles_index()
        profile = json.loads(read_dataset_profile("superstore"))
        assert "superstore" in index_text
        assert profile["id"] == "superstore"
        assert "Sales" in profile["match"]["fields_all_of"]

    def test_authoring_workflow_skill_is_readable(self):
        skill_text = read_skill("authoring_workflow")
        assert "review_authoring_contract" in skill_text
        assert "set_worksheet_caption" in skill_text


class TestAuthoringPrompts:
    def test_guided_dashboard_authoring_prompt_is_registered(self):
        prompt = server._prompt_manager.get_prompt("guided_dashboard_authoring")
        assert prompt is not None

    def test_guided_dashboard_authoring_prompt_keeps_workflow_inside_mcp(self):
        messages = asyncio.run(
            server._prompt_manager.render_prompt(
                "guided_dashboard_authoring",
                {
                    "brief": "Build an executive sales dashboard for sales leaders.",
                    "available_fields": "Sales, Profit, Region, State/Province, Order Date",
                    "output_path": "output/demo.twb",
                },
            )
        )
        text = messages[0].content.text
        assert "The human request below should stay natural-language" in text
        assert "Call the MCP prompt dashboard_brief_to_contract" in text
        assert "Requested output path: output/demo.twb" in text

    def test_dashboard_brief_to_contract_prompt_is_registered(self):
        prompt = server._prompt_manager.get_prompt("dashboard_brief_to_contract")
        assert prompt is not None

    def test_dashboard_brief_to_contract_prompt_renders_contract_guidance(self):
        messages = asyncio.run(
            server._prompt_manager.render_prompt(
                "dashboard_brief_to_contract",
                {
                    "brief": "Build a sales dashboard for regional leaders.",
                    "available_fields": "Sales, Profit, Region",
                },
            )
        )
        text = messages[0].content.text
        assert "strict JSON only" in text
        assert "Contract template" in text
        assert "Known dataset profiles" in text

    def test_light_elicitation_prompt_uses_review_feedback(self):
        messages = asyncio.run(
            server._prompt_manager.render_prompt(
                "light_elicitation",
                {"contract_json": json.dumps({"goal": "", "audience": ""})},
            )
        )
        text = messages[0].content.text
        assert "Ask the user only the minimum necessary follow-up questions" in text
        assert "What is the main business goal" in text

    def test_authoring_execution_plan_prompt_renders_outline(self):
        payload = {
            "goal": "Build a sales dashboard",
            "audience": "Sales leaders",
            "primary_question": "Which regions are driving sales?",
            "require_interaction": True,
            "available_fields": [
                "Order Date",
                "Region",
                "State/Province",
                "Sales",
                "Profit",
                "Quantity",
            ],
        }
        messages = asyncio.run(
            server._prompt_manager.render_prompt(
                "authoring_execution_plan",
                {"contract_json": json.dumps(payload)},
            )
        )
        text = messages[0].content.text
        assert "Create a concise MCP execution plan for cwtwb" in text
        assert "Execution outline" in text
        assert "Detected profile: superstore" in text


class TestContractReview:
    def test_complete_contract_is_valid(self):
        payload = {
            "goal": "Create an executive sales dashboard",
            "audience": "Sales leaders",
            "dataset": "",
            "primary_question": "Which regions and categories are driving sales and profit?",
            "require_interaction": True,
            "available_fields": [
                "Order Date",
                "Region",
                "State/Province",
                "Sales",
                "Profit",
                "Quantity",
            ],
            "constraints": {
                "max_dashboards": 1,
                "allowed_support_levels": ["core", "advanced"],
            },
            "worksheets": [
                {"name": "Sales Map", "question": "Where are sales concentrated?", "mark_type": "Map"},
            ],
            "dashboard": {"name": "Executive Overview"},
            "actions": [],
            "acceptance_checks": ["Workbook validates successfully"],
        }

        result = json.loads(review_authoring_contract(json.dumps(payload)))
        assert result["valid"] is True
        assert result["clarification_questions"] == []
        assert result["recommended_skills"][0] == "authoring_workflow"
        assert result["execution_outline"][0].startswith("Read resource")
        assert result["detected_profile"] == "superstore"
        assert result["normalized_contract"]["constraints"]["filters"] == [
            "Order Date",
            "Region",
            "State/Province",
        ]

    def test_blank_contract_applies_defaults_and_limits_questions(self):
        result = json.loads(review_authoring_contract("{}"))
        normalized = result["normalized_contract"]
        assert result["valid"] is False
        assert len(result["clarification_questions"]) == 3
        assert normalized["dataset"] == ""
        assert normalized["constraints"]["layout_pattern"] == "executive overview"
        assert normalized["constraints"]["filters"] == []
        assert result["detected_profile"] is None

    def test_dataset_name_also_matches_profile(self):
        payload = {
            "goal": "Build a sales dashboard",
            "audience": "Regional managers",
            "dataset": "Sample Superstore",
            "primary_question": "Which regions are leading?",
            "require_interaction": True,
        }
        result = json.loads(review_authoring_contract(json.dumps(payload)))
        assert result["detected_profile"] == "superstore"
        assert result["normalized_contract"]["dashboard"]["name"] == "Executive Overview"


class TestWorksheetCaption:
    def test_set_caption_writes_plain_text_formatted_text(self, tmp_file_factory):
        add_worksheet("Sales Trend")
        set_worksheet_caption(
            worksheet_name="Sales Trend",
            caption="Monthly sales trend after current dashboard filters.",
        )

        output = tmp_file_factory("captioned.twb")
        save_workbook(str(output))

        root = ET.parse(output).getroot()
        run = root.find(
            ".//worksheet[@name='Sales Trend']/layout-options/caption/formatted-text/run"
        )
        assert run is not None
        assert run.text == "Monthly sales trend after current dashboard filters."

    def test_caption_can_be_overwritten_and_cleared(self, tmp_file_factory):
        add_worksheet("Sales Trend")
        set_worksheet_caption("Sales Trend", "First caption")
        set_worksheet_caption("Sales Trend", "Updated caption")
        set_worksheet_caption("Sales Trend", "")

        output = tmp_file_factory("caption-cleared.twb")
        save_workbook(str(output))

        root = ET.parse(output).getroot()
        assert root.find(".//worksheet[@name='Sales Trend']/layout-options/caption") is None

    def test_captioned_workbook_validates_against_schema(self, tmp_file_factory):
        add_worksheet("Sales Trend")
        baseline_output = tmp_file_factory("baseline.twb")
        save_workbook(str(baseline_output))
        baseline_validation = validate_workbook(str(baseline_output))

        set_worksheet_caption("Sales Trend", "Monthly sales trend.")

        output = tmp_file_factory("caption-valid.twb")
        save_workbook(str(output))

        validation = validate_workbook(str(output))
        assert ("FAIL" in baseline_validation) == ("FAIL" in validation)
        assert "layout-options" not in validation.lower()


class TestAuthoringActionsAndAnalyzer:
    def test_analyzer_detects_url_and_go_to_sheet_actions(self, tmp_file_factory):
        add_worksheet("Source")
        configure_chart("Source", mark_type="Bar", rows=["Category"], columns=["SUM(Sales)"])
        add_worksheet("Detail")
        configure_chart("Detail", mark_type="Line", columns=["MONTH(Order Date)"], rows=["SUM(Sales)"])
        add_dashboard("Executive Overview", ["Source", "Detail"])
        add_dashboard_action(
            dashboard_name="Executive Overview",
            action_type="url",
            source_sheet="Source",
            url="https://example.com/detail",
            caption="Open Detail",
        )
        add_dashboard_action(
            dashboard_name="Executive Overview",
            action_type="go-to-sheet",
            source_sheet="Source",
            target_sheet="Detail",
            caption="Open Detail Sheet",
        )

        output = tmp_file_factory("actions-analysis.twb")
        save_workbook(str(output))
        report = analyze_twb(str(output))

        assert "URL Action" in report
        assert "Go-To-Sheet Action" in report
