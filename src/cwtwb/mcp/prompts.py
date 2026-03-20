"""MCP prompts for guided datasource-first dashboard authoring."""

from __future__ import annotations

import json

from .app import server
from .resources import read_dashboard_authoring_contract, read_profiles_index


@server.prompt(
    name="guided_dashboard_authoring",
    title="Guided Dashboard Authoring",
    description="Turn a natural-language dashboard brief plus a datasource path into a gated cwtwb authoring run.",
)
def guided_dashboard_authoring(
    brief: str,
    datasource_path: str,
    output_dir: str = "tmp/agentic_run",
) -> list[dict[str, str]]:
    """Guide the full datasource-first workflow with explicit confirmation gates."""

    return [
        {
            "role": "user",
            "content": (
                "You are orchestrating a cwtwb MCP dashboard authoring run.\n"
                "The human interaction must stay natural-language, but your internal workflow must be datasource-first and gated.\n\n"
                "Required workflow:\n"
                "1. Call start_authoring_run with the datasource path and output_dir.\n"
                "2. Call intake_datasource_schema and summarize the resulting schema_summary artifact and its Markdown review file.\n"
                "3. Prefer interactive_stage_confirmation with stage='schema' right after the schema summary.\n"
                "4. If interactive_stage_confirmation returns chat_fallback, stop and ask the human to confirm the schema in chat, then call confirm_authoring_stage with stage='schema'. If the schema is rejected, do not draft the contract yet.\n"
                "5. Call build_analysis_brief and summarize the candidate dashboard directions using the generated Markdown review file.\n"
                "6. Call finalize_analysis_brief, even if the human keeps the default direction, and then prefer interactive_stage_confirmation with stage='analysis'.\n"
                "7. If interactive_stage_confirmation returns chat_fallback, stop and ask the human to confirm the analysis direction in chat, then call confirm_authoring_stage with stage='analysis'. If the human rejects it, stay in the analysis phase.\n"
                "8. Call dashboard_brief_to_contract to think about the draft shape, then call draft_authoring_contract.\n"
                "9. Call review_authoring_contract_for_run.\n"
                "10. If intent is still missing, call light_elicitation and ask only those questions.\n"
                "11. Call finalize_authoring_contract using chat overrides or an edited Markdown review file.\n"
                "12. Prefer interactive_stage_confirmation with stage='contract' after you summarize the finalized contract.\n"
                "13. If interactive_stage_confirmation returns chat_fallback, stop and ask the human to confirm the contract in chat, then call confirm_authoring_stage with stage='contract'. If the human rejects it, stay in the contract phase.\n"
                "14. Call build_wireframe and summarize the ASCII wireframe and support/workaround notes from the Markdown review file.\n"
                "15. Call finalize_wireframe, even if the human keeps the default layout, and then prefer interactive_stage_confirmation with stage='wireframe'.\n"
                "16. If interactive_stage_confirmation returns chat_fallback, stop and ask the human to confirm the wireframe in chat, then call confirm_authoring_stage with stage='wireframe'. If the human rejects it, stay in the wireframe phase.\n"
                "17. Call authoring_execution_plan to reason about the build, then call build_execution_plan.\n"
                "18. Prefer interactive_stage_confirmation with stage='execution_plan' after you summarize the execution plan. Treat execution_plan.md as read-only.\n"
                "19. If interactive_stage_confirmation returns chat_fallback, stop and ask the human to confirm the execution plan in chat, then call confirm_authoring_stage with stage='execution_plan'.\n"
                "20. Only after confirmation, call generate_workbook_from_run.\n"
                "21. Finish by summarizing the run id, key artifacts, final workbook path, validation, and analysis.\n\n"
                "Hard rules:\n"
                "- Prefer get_client_interaction_capabilities and interactive_stage_confirmation for every confirmation gate.\n"
                "- Use confirm_authoring_stage directly only after a real chat fallback answer or when replaying an already-explicit human decision.\n"
                "- The server requires a fresh interactive_stage_confirmation for the current artifact version before each confirm_authoring_stage call.\n"
                "- If the human adds a new worksheet, KPI, or core interaction after contract confirmation, reopen `contract` instead of hiding the change in wireframe notes.\n"
                "- build_execution_plan validates that wireframe scope still matches the confirmed contract and will reject drift.\n"
                "- Never directly edit files under tmp/agentic_run/{run_id}/.\n"
                "- If any guided-run tool fails, stop immediately.\n"
                "- After a failure, call get_run_status(run_id), summarize last_error, and ask the human whether to reopen analysis, contract, wireframe, or execution_plan.\n"
                "- Do not switch to low-level workbook tools unless the human explicitly asks to leave guided mode.\n"
                "- Never promise an interaction as final if it only exists as a workaround in the wireframe review.\n\n"
                f"Human brief:\n{brief}\n\n"
                f"Datasource path: {datasource_path}\n"
                f"Run output root: {output_dir}"
            ),
        }
    ]


@server.prompt(
    name="dashboard_brief_to_contract",
    title="Dashboard Brief To Contract",
    description="Turn a human brief plus schema summary into a strict cwtwb contract draft.",
)
def dashboard_brief_to_contract(
    brief: str,
    schema_summary_json: str,
) -> list[dict[str, str]]:
    """Convert a human brief plus schema context into a contract draft prompt."""

    template = json.loads(read_dashboard_authoring_contract())
    schema_summary = json.loads(schema_summary_json)
    profile_index = read_profiles_index()

    return [
        {
            "role": "user",
            "content": (
                "Draft a cwtwb dashboard authoring contract as strict JSON only.\n\n"
                "Rules:\n"
                "- Output valid JSON only.\n"
                "- Follow the template shape exactly.\n"
                "- Use only fields present in the schema summary.\n"
                "- Keep workbook_template blank unless the human explicitly asks for one.\n"
                "- Prefer simple, supported worksheet ideas over speculative complexity.\n"
                "- Do not continue to execution; this prompt is only for draft thinking.\n\n"
                f"Contract template:\n{json.dumps(template, indent=2, ensure_ascii=False)}\n\n"
                f"Known dataset profiles:\n{profile_index}\n\n"
                f"Schema summary:\n{json.dumps(schema_summary, indent=2, ensure_ascii=False)}\n\n"
                f"Human brief:\n{brief}"
            ),
        }
    ]


@server.prompt(
    name="light_elicitation",
    title="Light Elicitation",
    description="Ask only the missing high-value follow-up questions from a contract review artifact.",
)
def light_elicitation(contract_review_json: str) -> list[dict[str, str]]:
    """Generate concise follow-up questions from a persisted contract review."""

    review = json.loads(contract_review_json)
    normalized_contract = json.dumps(
        review.get("normalized_contract", {}),
        indent=2,
        ensure_ascii=False,
    )

    if review.get("valid"):
        content = (
            "The reviewed contract is already valid.\n"
            "Respond with exactly: No clarification needed.\n\n"
            f"Review summary: {review.get('summary', '')}\n"
            f"Normalized contract:\n{normalized_contract}"
        )
    else:
        question_block = "\n".join(
            f"- {question}" for question in review.get("clarification_questions", [])
        )
        content = (
            "Ask the user only the minimum necessary follow-up questions.\n"
            "Rules:\n"
            "- Ask at most 3 questions.\n"
            "- Keep them short and business-oriented.\n"
            "- Do not ask about fields that already exist in the schema summary.\n"
            "- Preserve the current analytical direction.\n"
            "- Stop after asking; do not continue to generation.\n\n"
            f"Review summary: {review.get('summary', '')}\n"
            f"Detected profile: {review.get('detected_profile') or '(none)'}\n"
            f"Suggested clarification questions:\n{question_block}\n\n"
            f"Normalized contract:\n{normalized_contract}"
        )

    return [{"role": "user", "content": content}]


@server.prompt(
    name="authoring_execution_plan",
    title="Authoring Execution Plan",
    description="Produce a concise build-oriented MCP execution plan from a finalized contract.",
)
def authoring_execution_plan(contract_final_json: str) -> list[dict[str, str]]:
    """Generate an execution-oriented MCP plan from a finalized contract."""

    contract_final = json.loads(contract_final_json)

    return [
        {
            "role": "user",
            "content": (
                "Create a concise MCP execution plan for cwtwb.\n"
                "Rules:\n"
                "- Use the finalized contract as the source of truth.\n"
                "- Assume schema, analysis, contract, and wireframe confirmations have already happened.\n"
                "- Describe the likely tool sequence, but stop before execution.\n"
                "- Mention the final human confirmation gate before generate_workbook_from_run.\n"
                "- Treat execution_plan.md as read-only; upstream wireframe or contract changes should rebuild the plan instead of editing it.\n"
                "- Keep the reasoning aligned to supported workbook tools.\n\n"
                f"Final contract:\n{json.dumps(contract_final, indent=2, ensure_ascii=False)}"
            ),
        }
    ]
