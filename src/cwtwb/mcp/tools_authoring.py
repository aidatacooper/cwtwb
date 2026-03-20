"""Run-based MCP tools for guided datasource-first dashboard authoring."""

from __future__ import annotations

import json
from pathlib import Path

from ..authoring_run import (
    ARTIFACT_ANALYSIS,
    ARTIFACT_ANALYSIS_BRIEF,
    ARTIFACT_VALIDATION,
    ANALYSIS_STAGE,
    EXECUTION_STEP_WHITELIST,
    EXECUTION_STAGE,
    POST_CHECK_WHITELIST,
    STATUS_ANALYZED,
    STATUS_VALIDATED,
    WIREFRAME_STAGE,
    build_analysis_brief as build_analysis_brief_impl,
    build_execution_plan as build_execution_plan_impl,
    build_wireframe as build_wireframe_impl,
    confirm_authoring_stage as confirm_authoring_stage_impl,
    draft_authoring_contract as draft_authoring_contract_impl,
    finalize_analysis_brief as finalize_analysis_brief_impl,
    finalize_authoring_contract as finalize_authoring_contract_impl,
    finalize_wireframe as finalize_wireframe_impl,
    get_run_status as get_run_status_impl,
    intake_datasource_schema as intake_datasource_schema_impl,
    list_authoring_runs as list_authoring_runs_impl,
    load_execution_plan_for_run,
    mark_generation_failed,
    mark_generation_started,
    mark_generation_success,
    reopen_authoring_stage as reopen_authoring_stage_impl,
    resume_authoring_run as resume_authoring_run_impl,
    review_authoring_contract_for_run as review_authoring_contract_for_run_impl,
    start_authoring_run as start_authoring_run_impl,
    write_post_check_artifact,
)
from .app import server


@server.tool()
def start_authoring_run(
    datasource_path: str,
    output_dir: str = "tmp/agentic_run",
    resume_if_exists: bool = False,
) -> str:
    """Initialize a new guided authoring run from an Excel or Hyper datasource."""

    return start_authoring_run_impl(
        datasource_path=datasource_path,
        output_dir=output_dir,
        resume_if_exists=resume_if_exists,
    )


@server.tool()
def list_authoring_runs(output_dir: str = "tmp/agentic_run") -> str:
    """List all known authoring runs and their current status."""

    return list_authoring_runs_impl(output_dir=output_dir)


@server.tool()
def get_run_status(run_id: str) -> str:
    """Return the manifest-backed status for one authoring run."""

    return get_run_status_impl(run_id)


@server.tool()
def resume_authoring_run(run_id: str) -> str:
    """Resume a previous authoring run by id."""

    return resume_authoring_run_impl(run_id)


@server.tool()
def intake_datasource_schema(run_id: str, preferred_sheet: str = "") -> str:
    """Inspect the datasource declared in the run manifest and persist schema_summary."""

    return intake_datasource_schema_impl(run_id=run_id, preferred_sheet=preferred_sheet)


@server.tool()
def build_analysis_brief(run_id: str) -> str:
    """Build analysis_brief.json and .md with 2-4 candidate dashboard directions."""

    return build_analysis_brief_impl(run_id=run_id)


@server.tool()
def finalize_analysis_brief(
    run_id: str,
    user_answers_json: str = "",
    markdown_path: str = "",
) -> str:
    """Finalize analysis_brief from chat overrides or an edited Markdown review file."""

    return finalize_analysis_brief_impl(
        run_id=run_id,
        user_answers_json=user_answers_json,
        markdown_path=markdown_path,
    )


@server.tool()
def draft_authoring_contract(run_id: str, human_brief: str, rewrite: bool = False) -> str:
    """Create a contract draft from the current schema summary plus a human brief."""

    return draft_authoring_contract_impl(
        run_id=run_id,
        human_brief=human_brief,
        rewrite=rewrite,
    )


@server.tool()
def review_authoring_contract_for_run(run_id: str) -> str:
    """Review the current contract draft and persist contract_review.json."""

    return review_authoring_contract_for_run_impl(run_id=run_id)


@server.tool()
def finalize_authoring_contract(
    run_id: str,
    user_answers_json: str = "",
    markdown_path: str = "",
) -> str:
    """Merge contract review defaults with human answers and persist contract_final.json."""

    return finalize_authoring_contract_impl(
        run_id=run_id,
        user_answers_json=user_answers_json,
        markdown_path=markdown_path,
    )


@server.tool()
def confirm_authoring_stage(run_id: str, stage: str, approved: bool, notes: str = "") -> str:
    """Approve or reject one gated authoring stage."""

    return confirm_authoring_stage_impl(
        run_id=run_id,
        stage=stage,
        approved=approved,
        notes=notes,
    )


@server.tool()
def build_wireframe(run_id: str) -> str:
    """Build wireframe.json and .md, including an ASCII dashboard sketch."""

    return build_wireframe_impl(run_id=run_id)


@server.tool()
def finalize_wireframe(
    run_id: str,
    user_answers_json: str = "",
    markdown_path: str = "",
) -> str:
    """Finalize wireframe review notes or normalized actions before planning."""

    return finalize_wireframe_impl(
        run_id=run_id,
        user_answers_json=user_answers_json,
        markdown_path=markdown_path,
    )


@server.tool()
def reopen_authoring_stage(run_id: str, stage: str, notes: str = "") -> str:
    """Reopen analysis, contract, wireframe, or execution_plan after generation failure."""

    return reopen_authoring_stage_impl(run_id=run_id, stage=stage, notes=notes)


@server.tool()
def build_execution_plan(run_id: str) -> str:
    """Build a mechanical execution_plan.json from the current final contract."""

    return build_execution_plan_impl(run_id=run_id)


def _tool_map():
    from .tools_support import analyze_twb, validate_workbook
    from .tools_workbook import (
        add_calculated_field,
        add_dashboard,
        add_dashboard_action,
        add_parameter,
        add_worksheet,
        configure_chart,
        configure_chart_recipe,
        configure_dual_axis,
        configure_worksheet_style,
        create_workbook,
        open_workbook,
        save_workbook,
        set_excel_connection,
        set_hyper_connection,
        set_mysql_connection,
        set_tableauserver_connection,
        set_worksheet_caption,
    )

    return {
        "create_workbook": create_workbook,
        "open_workbook": open_workbook,
        "add_calculated_field": add_calculated_field,
        "add_parameter": add_parameter,
        "add_worksheet": add_worksheet,
        "configure_chart": configure_chart,
        "configure_dual_axis": configure_dual_axis,
        "configure_chart_recipe": configure_chart_recipe,
        "configure_worksheet_style": configure_worksheet_style,
        "add_dashboard": add_dashboard,
        "add_dashboard_action": add_dashboard_action,
        "set_worksheet_caption": set_worksheet_caption,
        "set_excel_connection": set_excel_connection,
        "set_mysql_connection": set_mysql_connection,
        "set_tableauserver_connection": set_tableauserver_connection,
        "set_hyper_connection": set_hyper_connection,
        "save_workbook": save_workbook,
        "validate_workbook": validate_workbook,
        "analyze_twb": analyze_twb,
    }


@server.tool()
def generate_workbook_from_run(run_id: str, output_twb_path: str = "") -> str:
    """Execute the confirmed execution plan, save the workbook, and persist reports."""

    manifest = mark_generation_started(run_id)
    plan = load_execution_plan_for_run(run_id)
    tool_map = _tool_map()
    run_dir = Path(manifest["run_dir"])
    final_output = output_twb_path or str(run_dir / "final_workbook.twb")
    executed_steps: list[str] = []
    current_tool = "initialization"

    try:
        for step in plan.get("steps", []):
            tool_name = str(step.get("tool", "")).strip()
            current_tool = tool_name
            if tool_name not in EXECUTION_STEP_WHITELIST:
                raise RuntimeError(f"Execution plan step '{tool_name}' is not in the allowed whitelist.")
            tool = tool_map[tool_name]
            args = step.get("args", {}) or {}
            tool(**args)
            executed_steps.append(tool_name)

        tool_map["save_workbook"](final_output)
        mark_generation_success(run_id, final_output)

        for check in plan.get("post_checks", []):
            tool_name = str(check.get("tool", "")).strip()
            if tool_name not in POST_CHECK_WHITELIST:
                raise RuntimeError(f"Execution plan post-check '{tool_name}' is not allowed.")
            args = dict(check.get("args", {}) or {})
            if tool_name in {"validate_workbook", "analyze_twb"} and "file_path" not in args:
                args["file_path"] = final_output
            result = tool_map[tool_name](**args)
            if tool_name == "validate_workbook":
                write_post_check_artifact(
                    run_id,
                    ARTIFACT_VALIDATION,
                    {"result": result},
                    STATUS_VALIDATED,
                )
            elif tool_name == "analyze_twb":
                write_post_check_artifact(
                    run_id,
                    ARTIFACT_ANALYSIS,
                    {"result": result},
                    STATUS_ANALYZED,
                )

        return json.dumps(
            {
                "run_id": run_id,
                "final_workbook": final_output,
                "executed_steps": executed_steps,
                "post_checks": list(POST_CHECK_WHITELIST),
                "status": STATUS_ANALYZED,
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as exc:
        mark_generation_failed(run_id, current_tool, str(exc))
        raise RuntimeError(
            f"generate_workbook_from_run failed after steps {executed_steps or ['(none)']}: {exc}"
        ) from exc
