"""Run the guided Excel authoring flow through a real MCP client session.

This script uses the official `mcp` Python client over stdio to connect to the
local `cwtwb` server. It is a deterministic fallback demo for the Matthew-facing
guided authoring workflow:

real datasource -> schema -> analysis -> contract -> wireframe -> execution plan -> workbook
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASOURCE = Path(__file__).with_name("Sample - Superstore.xls")
DEFAULT_OUTPUT_DIR = "tmp/agentic_run"
DEFAULT_BRIEF = (
    "Build an executive sales performance dashboard for Matthew.\n"
    "Audience: sales leaders\n"
    "Primary question: Which regions, categories, and sub-categories are driving "
    "sales and profit, and where should leaders drill deeper?\n"
    "Please include interactive filtering from the top view into detail, and keep "
    "the dashboard simple enough for a polished demo."
)
DEFAULT_USER_ANSWERS = {
    "audience": "Sales leaders and Matthew reviewing the authoring workflow",
    "primary_question": (
        "Which regions, categories, and sub-categories are driving sales and "
        "profit, and where should leaders drill deeper?"
    ),
    "require_interaction": True,
}


def _print_block(title: str, payload: str | dict[str, Any] | list[Any]) -> None:
    print(f"\n== {title} ==")
    if isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def _parse_tool_payload(result: Any) -> dict[str, Any]:
    if not result.content:
        return {}
    text = getattr(result.content[0], "text", "")
    if not text:
        return {}
    return json.loads(text)


def _load_json(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return json.loads(path.read_text(encoding="utf-8"))


async def _call_tool(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _parse_tool_payload(await session.call_tool(name, arguments or {}))
    _print_block(f"TOOL {name}", payload)
    return payload


async def run_demo(
    datasource: str,
    brief: str,
    output_dir: str,
    user_answers: dict[str, Any],
) -> None:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cwtwb.mcp"],
        cwd=str(PROJECT_ROOT),
    )

    async with stdio_client(server) as streams:
        read_stream, write_stream = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            guided_prompt = await session.get_prompt(
                "guided_dashboard_authoring",
                {
                    "brief": brief,
                    "datasource_path": datasource,
                    "output_dir": output_dir,
                },
            )
            _print_block(
                "PROMPT guided_dashboard_authoring",
                guided_prompt.messages[0].content.text,
            )

            profiles_index = await session.read_resource("cwtwb://profiles/index")
            _print_block(
                "RESOURCE cwtwb://profiles/index",
                profiles_index.contents[0].text,
            )

            started = await _call_tool(
                session,
                "start_authoring_run",
                {
                    "datasource_path": datasource,
                    "output_dir": output_dir,
                },
            )
            run_id = started["run_id"]

            schema = await _call_tool(session, "intake_datasource_schema", {"run_id": run_id})
            schema_payload = _load_json(schema["artifact"])
            _print_block(
                "SCHEMA SUMMARY SNAPSHOT",
                {
                    "selected_primary_object": schema_payload.get("selected_primary_object"),
                    "sheet_names": [sheet["name"] for sheet in schema_payload.get("sheets", [])],
                    "field_candidates": schema_payload.get("field_candidates"),
                    "recommended_profile_matches": schema_payload.get("recommended_profile_matches"),
                    "notes": schema_payload.get("notes"),
                },
            )

            await _call_tool(
                session,
                "confirm_authoring_stage",
                {
                    "run_id": run_id,
                    "stage": "schema",
                    "approved": True,
                    "notes": "Orders is the only sheet and the schema looks correct for the demo.",
                },
            )

            analysis = await _call_tool(session, "build_analysis_brief", {"run_id": run_id})
            analysis_payload = _load_json(analysis["artifact"])
            _print_block(
                "ANALYSIS BRIEF SNAPSHOT",
                {
                    "selected_direction_id": analysis_payload.get("selected_direction_id"),
                    "selected_direction_title": analysis_payload.get("selected_direction_title"),
                    "direction_titles": [
                        direction.get("title")
                        for direction in analysis_payload.get("directions", [])
                    ],
                },
            )
            await _call_tool(
                session,
                "finalize_analysis_brief",
                {
                    "run_id": run_id,
                    "user_answers_json": json.dumps(
                        {"selected_direction_id": "executive_overview"},
                        ensure_ascii=False,
                    ),
                },
            )
            await _call_tool(
                session,
                "confirm_authoring_stage",
                {
                    "run_id": run_id,
                    "stage": "analysis",
                    "approved": True,
                    "notes": "Executive Overview is the right direction for the demo.",
                },
            )

            await _call_tool(
                session,
                "draft_authoring_contract",
                {
                    "run_id": run_id,
                    "human_brief": brief,
                },
            )
            review = await _call_tool(session, "review_authoring_contract_for_run", {"run_id": run_id})
            review_payload = _load_json(review["artifact"])
            _print_block(
                "CONTRACT REVIEW SNAPSHOT",
                {
                    "valid": review_payload.get("valid"),
                    "summary": review_payload.get("summary"),
                    "clarification_questions": review_payload.get("clarification_questions"),
                    "detected_profile": review_payload.get("detected_profile"),
                },
            )

            elicitation_prompt = await session.get_prompt(
                "light_elicitation",
                {"contract_review_json": json.dumps(review_payload, ensure_ascii=False)},
            )
            _print_block(
                "PROMPT light_elicitation",
                elicitation_prompt.messages[0].content.text,
            )

            final_contract = await _call_tool(
                session,
                "finalize_authoring_contract",
                {
                    "run_id": run_id,
                    "user_answers_json": json.dumps(
                        user_answers,
                        ensure_ascii=False,
                    ),
                },
            )
            final_contract_payload = _load_json(final_contract["artifact"])
            _print_block(
                "FINAL CONTRACT SNAPSHOT",
                {
                    "audience": final_contract_payload.get("audience"),
                    "primary_question": final_contract_payload.get("primary_question"),
                    "require_interaction": final_contract_payload.get("require_interaction"),
                    "dashboard": final_contract_payload.get("dashboard"),
                    "worksheets": final_contract_payload.get("worksheets"),
                    "constraints": final_contract_payload.get("constraints"),
                    "actions": final_contract_payload.get("actions"),
                },
            )

            await _call_tool(
                session,
                "confirm_authoring_stage",
                {
                    "run_id": run_id,
                    "stage": "contract",
                    "approved": True,
                    "notes": "Contract is aligned with the Matthew-facing demo.",
                },
            )

            wireframe = await _call_tool(session, "build_wireframe", {"run_id": run_id})
            wireframe_payload = _load_json(wireframe["artifact"])
            _print_block(
                "WIREFRAME SNAPSHOT",
                {
                    "dashboard_name": wireframe_payload.get("dashboard_name"),
                    "actions": wireframe_payload.get("actions"),
                    "support_notes": wireframe_payload.get("support_notes"),
                    "ascii_wireframe": wireframe_payload.get("ascii_wireframe"),
                },
            )
            await _call_tool(
                session,
                "finalize_wireframe",
                {
                    "run_id": run_id,
                    "user_answers_json": json.dumps({}, ensure_ascii=False),
                },
            )
            await _call_tool(
                session,
                "confirm_authoring_stage",
                {
                    "run_id": run_id,
                    "stage": "wireframe",
                    "approved": True,
                    "notes": "Wireframe and interaction notes look good for the demo.",
                },
            )

            execution_prompt = await session.get_prompt(
                "authoring_execution_plan",
                {"contract_final_json": json.dumps(final_contract_payload, ensure_ascii=False)},
            )
            _print_block(
                "PROMPT authoring_execution_plan",
                execution_prompt.messages[0].content.text,
            )

            plan = await _call_tool(session, "build_execution_plan", {"run_id": run_id})
            plan_payload = _load_json(plan["artifact"])
            _print_block(
                "EXECUTION PLAN SNAPSHOT",
                {
                    "step_count": len(plan_payload.get("steps", [])),
                    "first_steps": plan_payload.get("steps", [])[:6],
                    "post_checks": plan_payload.get("post_checks", []),
                },
            )

            await _call_tool(
                session,
                "confirm_authoring_stage",
                {
                    "run_id": run_id,
                    "stage": "execution_plan",
                    "approved": True,
                    "notes": "Execution plan approved for the demo run.",
                },
            )

            generated = await _call_tool(session, "generate_workbook_from_run", {"run_id": run_id})
            status = await _call_tool(session, "get_run_status", {"run_id": run_id})
            _print_block(
                "FINAL SUMMARY",
                {
                    "run_id": run_id,
                    "final_workbook": generated.get("final_workbook"),
                    "executed_steps": generated.get("executed_steps"),
                    "artifacts_present": status.get("artifacts_present"),
                    "status": status.get("status"),
                    "last_error": status.get("last_error"),
                },
            )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Excel guided authoring flow through a real MCP client session.",
    )
    parser.add_argument(
        "--datasource",
        default=str(DEFAULT_DATASOURCE),
        help="Path to the Excel datasource. Defaults to the bundled Sample - Superstore.xls.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Run artifact root passed to start_authoring_run.",
    )
    parser.add_argument(
        "--brief",
        default=DEFAULT_BRIEF,
        help="Natural-language dashboard brief used for the demo.",
    )
    parser.add_argument(
        "--user-answers-json",
        default="",
        help=(
            "Optional JSON object merged into finalize_authoring_contract. "
            "If omitted, the script uses Matthew-facing defaults only when the "
            "default brief is unchanged."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.user_answers_json.strip():
        user_answers = json.loads(args.user_answers_json)
    elif args.brief == DEFAULT_BRIEF:
        user_answers = dict(DEFAULT_USER_ANSWERS)
    else:
        user_answers = {}
    anyio.run(run_demo, args.datasource, args.brief, args.output_dir, user_answers)


if __name__ == "__main__":
    main()
