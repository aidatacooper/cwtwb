"""Regression coverage for the guided MCP authoring run workflow."""

from __future__ import annotations

import asyncio
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.mcp.resources import (
    read_dashboard_authoring_contract,
    read_profiles_index,
    read_skill,
    read_skills_index,
)
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


def _start_run() -> dict:
    if not XLS_SOURCE.exists():
        pytest.skip("Sample Excel datasource not available")
    payload = json.loads(
        start_authoring_run(
            datasource_path=str(XLS_SOURCE),
            output_dir=str(RUN_ROOT),
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

    def test_guided_dashboard_authoring_prompt_references_all_confirmation_gates(self):
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
        assert "stage='execution_plan'" in text
        assert "Never directly edit files under tmp/agentic_run/{run_id}/." in text
        assert "generate_workbook_from_run" in text

    def test_server_instructions_reference_all_guided_confirmation_calls(self):
        text = server.instructions
        assert "interactive_stage_confirmation('schema')" in text
        assert "interactive_stage_confirmation('analysis')" in text
        assert "interactive_stage_confirmation('contract')" in text
        assert "interactive_stage_confirmation('wireframe')" in text
        assert "interactive_stage_confirmation('execution_plan')" in text
        assert "confirm_authoring_stage('schema')" in text
        assert "confirm_authoring_stage('analysis')" in text
        assert "confirm_authoring_stage('contract')" in text
        assert "confirm_authoring_stage('wireframe')" in text
        assert "confirm_authoring_stage('execution_plan')" in text
        assert "get_client_interaction_capabilities" in text
        assert "Do not switch to low-level workbook tools" in text

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
        assert "read-only" in text


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
        assert "KPI Zone" in wireframe["ascii_wireframe"]
        assert any(action["support_level"] in {"supported", "workaround"} for action in wireframe["actions"])
        assert "```text" in review_text

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

    def test_execution_plan_prefers_regional_geo_and_primary_to_detail_action(self):
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
        assert primary_view_step["args"]["geographic_field"] == "Region"

        action_step = next(
            step for step in payload["steps"] if step["tool"] == "add_dashboard_action"
        )
        assert action_step["args"]["source_sheet"] == "Primary View"
        assert action_step["args"]["target_sheet"] == "Detail View"
        assert action_step["args"]["fields"] == ["Region"]
        assert "read-only" in review_text

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
        assert any(name.startswith("validation_report.") for name in status["artifacts_present"])
        assert any(name.startswith("analysis_report.") for name in status["artifacts_present"])

        root = ET.parse(workbook_path).getroot()
        caption = root.find(".//worksheet[@name='Summary View']/layout-options/caption/formatted-text/run")
        assert caption is not None

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
