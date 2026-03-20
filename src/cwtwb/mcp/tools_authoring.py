"""Run-based MCP tools for guided datasource-first dashboard authoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp import types as mcp_types
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from ..authoring_run import (
    ARTIFACT_CONTRACT_FINAL,
    ARTIFACT_EXECUTION_PLAN,
    ARTIFACT_SCHEMA,
    ARTIFACT_WIREFRAME,
    ARTIFACT_ANALYSIS,
    ARTIFACT_ANALYSIS_BRIEF,
    ARTIFACT_VALIDATION,
    ANALYSIS_STAGE,
    CONTRACT_STAGE,
    EXECUTION_STEP_WHITELIST,
    EXECUTION_STAGE,
    POST_CHECK_WHITELIST,
    SCHEMA_STAGE,
    STATUS_ANALYZED,
    STATUS_VALIDATED,
    WIREFRAME_STAGE,
    _current_review_artifact_path,
    _load_manifest_by_id,
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
    request_stage_confirmation as request_stage_confirmation_impl,
    resume_authoring_run as resume_authoring_run_impl,
    review_authoring_contract_for_run as review_authoring_contract_for_run_impl,
    start_authoring_run as start_authoring_run_impl,
    write_post_check_artifact,
)
from .app import server

_STAGE_REVIEW_ARTIFACTS = {
    SCHEMA_STAGE: ARTIFACT_SCHEMA,
    ANALYSIS_STAGE: ARTIFACT_ANALYSIS_BRIEF,
    CONTRACT_STAGE: ARTIFACT_CONTRACT_FINAL,
    WIREFRAME_STAGE: ARTIFACT_WIREFRAME,
    EXECUTION_STAGE: ARTIFACT_EXECUTION_PLAN,
}

_STAGE_LABELS = {
    SCHEMA_STAGE: "schema review",
    ANALYSIS_STAGE: "analysis direction review",
    CONTRACT_STAGE: "authoring contract review",
    WIREFRAME_STAGE: "wireframe review",
    EXECUTION_STAGE: "execution plan review",
}


class StageConfirmationForm(BaseModel):
    """Primitive elicitation schema for guided authoring approvals."""

    approved: bool = Field(
        description=(
            "Set to true to approve this stage and continue. "
            "Set to false to reject it and keep iterating on the same stage."
        )
    )
    notes: str = Field(
        default="",
        description="Optional review note or change request for this stage.",
    )


def _json_response(**payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _review_artifact_for_stage(run_id: str, stage: str) -> tuple[str, str]:
    if stage not in _STAGE_REVIEW_ARTIFACTS:
        raise ValueError(f"Unsupported confirmation stage '{stage}'.")
    manifest = _load_manifest_by_id(run_id)
    return (
        str(_current_review_artifact_path(manifest, _STAGE_REVIEW_ARTIFACTS[stage])),
        str(manifest.get("status", "")),
    )


def _client_interaction_capabilities(ctx: Context | None) -> dict[str, Any]:
    request_context = getattr(ctx, "request_context", None) if ctx is not None else None
    session = getattr(request_context, "session", None) if request_context is not None else None
    client_params = getattr(session, "client_params", None) if session is not None else None
    client_caps = getattr(client_params, "capabilities", None) if client_params is not None else None
    elicitation_caps = getattr(client_caps, "elicitation", None) if client_caps is not None else None
    client_info = getattr(client_params, "clientInfo", None) if client_params is not None else None
    any_elicitation = bool(elicitation_caps is not None)
    form_supported = bool(any_elicitation and getattr(elicitation_caps, "form", None) is not None)
    url_supported = bool(any_elicitation and getattr(elicitation_caps, "url", None) is not None)
    protocol_check = False
    if session is not None:
        protocol_check = session.check_client_capability(
            mcp_types.ClientCapabilities(elicitation=mcp_types.ElicitationCapability())
        )
    return {
        "request_context_available": request_context is not None,
        "client_name": getattr(client_info, "name", "") if client_info is not None else "",
        "client_version": getattr(client_info, "version", "") if client_info is not None else "",
        "elicitation_supported": any_elicitation,
        "form_elicitation_supported": form_supported,
        "url_elicitation_supported": url_supported,
        "protocol_capability_check": protocol_check,
        "chat_fallback_available": True,
        "preferred_confirmation_mode": "elicitation" if form_supported else "chat_fallback",
    }


def _chat_fallback_payload(
    *,
    run_id: str,
    stage: str,
    review_artifact: str,
    current_status: str,
    capabilities: dict[str, Any],
    reason: str,
) -> str:
    return _json_response(
        run_id=run_id,
        stage=stage,
        stage_label=_STAGE_LABELS.get(stage, stage),
        status="awaiting_human_confirmation",
        current_status=current_status,
        confirmation_mode="chat_fallback",
        review_artifact=review_artifact,
        client_capabilities=capabilities,
        reason=reason,
        instructions=(
            "Show the review artifact to the human, ask for approval or rejection in chat, "
            "and then call confirm_authoring_stage(...) with the human's explicit answer."
        ),
    )


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
def get_client_interaction_capabilities(ctx: Context | None = None) -> str:
    """Report whether the connected MCP client supports form elicitation."""

    return _json_response(**_client_interaction_capabilities(ctx))


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
async def interactive_stage_confirmation(
    run_id: str,
    stage: str,
    stage_summary: str = "",
    ctx: Context | None = None,
) -> str:
    """Prefer MCP elicitation for stage confirmation, with chat fallback when unsupported."""

    review_artifact, current_status = _review_artifact_for_stage(run_id, stage)
    capabilities = _client_interaction_capabilities(ctx)
    if not capabilities["form_elicitation_supported"] or ctx is None:
        request_stage_confirmation_impl(
            run_id=run_id,
            stage=stage,
            confirmation_mode="chat_fallback",
        )
        return _chat_fallback_payload(
            run_id=run_id,
            stage=stage,
            review_artifact=review_artifact,
            current_status=current_status,
            capabilities=capabilities,
            reason="This client does not advertise form elicitation support.",
        )

    summary = stage_summary.strip() or (
        f"Review the {_STAGE_LABELS.get(stage, stage)} artifact and decide whether to continue."
    )
    message = (
        f"You are reviewing the {_STAGE_LABELS.get(stage, stage)} for guided authoring run {run_id}.\n\n"
        f"{summary}\n\n"
        f"Review artifact: {review_artifact}\n"
        "Submit approved=true to continue, or approved=false to keep iterating on this stage. "
        "Use notes for any requested changes."
    )
    request_stage_confirmation_impl(
        run_id=run_id,
        stage=stage,
        confirmation_mode="elicitation",
    )

    try:
        elicitation = await ctx.elicit(message=message, schema=StageConfirmationForm)
    except Exception as exc:  # pragma: no cover - depends on client support
        capabilities["elicitation_error"] = str(exc)
        return _chat_fallback_payload(
            run_id=run_id,
            stage=stage,
            review_artifact=review_artifact,
            current_status=current_status,
            capabilities=capabilities,
            reason=f"Form elicitation was attempted but could not be completed: {exc}",
        )

    if elicitation.action == "cancel":
        return _chat_fallback_payload(
            run_id=run_id,
            stage=stage,
            review_artifact=review_artifact,
            current_status=current_status,
            capabilities=capabilities,
            reason="The elicitation dialog was cancelled before a decision was submitted.",
        )

    if elicitation.action == "decline":
        approved = False
        notes = "Rejected via client elicitation."
    else:
        approved = bool(elicitation.data.approved)
        notes = str(elicitation.data.notes or "").strip()

    confirmed = json.loads(
        confirm_authoring_stage_impl(
            run_id=run_id,
            stage=stage,
            approved=approved,
            notes=notes,
        )
    )
    return _json_response(
        run_id=run_id,
        stage=stage,
        stage_label=_STAGE_LABELS.get(stage, stage),
        status=confirmed.get("status", ""),
        confirmation_mode="elicitation",
        elicitation_action=elicitation.action,
        review_artifact=review_artifact,
        client_capabilities=capabilities,
        approved=confirmed.get("approved"),
        notes=confirmed.get("notes", ""),
        current=confirmed.get("current", {}),
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
    """Reopen analysis, contract, wireframe, or execution_plan after confirmation or generation failure."""

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
