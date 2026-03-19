"""MCP prompts for contract-first dashboard authoring."""

from __future__ import annotations

import json

from ..authoring_contract import review_authoring_contract_payload
from .app import server
from .resources import read_dashboard_authoring_contract, read_profiles_index


def _parse_available_fields(raw_fields: str) -> list[str]:
    tokens: list[str] = []
    for chunk in raw_fields.replace(";", "\n").replace(",", "\n").splitlines():
        value = chunk.strip()
        if value and value not in tokens:
            tokens.append(value)
    return tokens


@server.prompt(
    name="guided_dashboard_authoring",
    title="Guided Dashboard Authoring",
    description="Turn a natural-language dashboard brief into a guided cwtwb MCP authoring workflow.",
)
def guided_dashboard_authoring(
    brief: str,
    dataset: str = "",
    available_fields: str = "",
    output_path: str = "output/agentic_mcp_client_demo.twb",
) -> list[dict[str, str]]:
    """Guide the full MCP workflow from a natural-language dashboard request."""

    field_list = _parse_available_fields(available_fields)
    return [
        {
            "role": "user",
            "content": (
                "You are orchestrating a cwtwb MCP dashboard authoring session.\n"
                "The human request below should stay natural-language in the final interaction, "
                "but your internal workflow must be contract-first.\n\n"
                "Required workflow:\n"
                "1. Call the MCP prompt dashboard_brief_to_contract.\n"
                "2. Read cwtwb://contracts/dashboard_authoring_v1.\n"
                "3. Read cwtwb://profiles/index and inspect any matching dataset profile.\n"
                "4. Call review_authoring_contract on the drafted contract.\n"
                "5. If clarification_questions are returned, stop and ask only those questions.\n"
                "6. If the contract is valid, call the MCP prompts light_elicitation and authoring_execution_plan.\n"
                "7. Read cwtwb://skills/authoring_workflow plus the phase skills you need.\n"
                "8. Create the workbook, build worksheets, dashboard, actions, and captions.\n"
                "9. Save to the requested output path, then run validate_workbook and analyze_twb.\n"
                "10. Finish with a concise summary of the normalized contract, detected profile, output path, validation, and capability analysis.\n\n"
                "Human brief:\n"
                f"{brief}\n\n"
                f"Dataset hint: {dataset or '(none)'}\n"
                f"Available fields: {json.dumps(field_list, ensure_ascii=False)}\n"
                f"Requested output path: {output_path}"
            ),
        }
    ]


@server.prompt(
    name="dashboard_brief_to_contract",
    title="Dashboard Brief To Contract",
    description="Turn a human dashboard brief into a strict cwtwb authoring contract JSON draft.",
)
def dashboard_brief_to_contract(
    brief: str,
    dataset: str = "",
    available_fields: str = "",
) -> list[dict[str, str]]:
    """Convert a human brief into a structured contract draft."""

    template = json.loads(read_dashboard_authoring_contract())
    field_list = _parse_available_fields(available_fields)
    profile_index = read_profiles_index()

    return [
        {
            "role": "user",
            "content": (
                "Draft a cwtwb dashboard authoring contract as strict JSON only.\n\n"
                "Rules:\n"
                "- Output valid JSON only.\n"
                "- Follow the template shape exactly.\n"
                "- Keep dataset blank if unknown.\n"
                "- Put any known fields into available_fields.\n"
                "- Do not invent unsupported worksheets or fields.\n"
                "- Keep actions aligned with the user's analytical flow.\n\n"
                f"Contract template:\n{json.dumps(template, indent=2, ensure_ascii=False)}\n\n"
                f"Known dataset profiles:\n{profile_index}\n\n"
                f"Human brief:\n{brief}\n\n"
                f"Dataset hint: {dataset or '(none)'}\n"
                f"Available fields: {json.dumps(field_list, ensure_ascii=False)}"
            ),
        }
    ]


@server.prompt(
    name="light_elicitation",
    title="Light Elicitation",
    description="Ask only the missing high-value follow-up questions for a dashboard contract.",
)
def light_elicitation(contract_json: str) -> list[dict[str, str]]:
    """Generate concise follow-up questions from a contract review result."""

    review = review_authoring_contract_payload(contract_json)
    normalized_contract = json.dumps(
        review.normalized_contract,
        indent=2,
        ensure_ascii=False,
    )

    if review.valid:
        content = (
            "The reviewed contract is already valid.\n"
            "Respond with exactly: No clarification needed.\n\n"
            f"Review summary: {review.summary}\n"
            f"Normalized contract:\n{normalized_contract}"
        )
    else:
        question_block = "\n".join(f"- {question}" for question in review.clarification_questions)
        content = (
            "Ask the user only the minimum necessary follow-up questions.\n"
            "Rules:\n"
            "- Ask at most 3 questions.\n"
            "- Keep them short and business-oriented.\n"
            "- Do not ask about fields that already have defaults.\n"
            "- Preserve the current analytical direction.\n\n"
            f"Review summary: {review.summary}\n"
            f"Detected profile: {review.detected_profile or '(none)'}\n"
            f"Suggested clarification questions:\n{question_block}\n\n"
            f"Normalized contract:\n{normalized_contract}"
        )

    return [{"role": "user", "content": content}]


@server.prompt(
    name="authoring_execution_plan",
    title="Authoring Execution Plan",
    description="Produce a concise MCP execution plan from a reviewed cwtwb authoring contract.",
)
def authoring_execution_plan(contract_json: str) -> list[dict[str, str]]:
    """Generate an execution-oriented MCP plan from a contract."""

    review = review_authoring_contract_payload(contract_json)
    normalized_contract = json.dumps(
        review.normalized_contract,
        indent=2,
        ensure_ascii=False,
    )
    outline = "\n".join(f"{idx}. {step}" for idx, step in enumerate(review.execution_outline, start=1))
    skills = ", ".join(review.recommended_skills)

    return [
        {
            "role": "user",
            "content": (
                "Create a concise MCP execution plan for cwtwb.\n"
                "Rules:\n"
                "- Use the reviewed contract as the source of truth.\n"
                "- Keep the plan aligned to cwtwb MCP resources, prompts, and tools.\n"
                "- Mention required skills in execution order.\n"
                "- Mention validation before final save.\n"
                "- If the contract is still missing critical intent, say so first.\n\n"
                f"Review valid: {review.valid}\n"
                f"Review summary: {review.summary}\n"
                f"Detected profile: {review.detected_profile or '(none)'}\n"
                f"Recommended skills: {skills}\n"
                f"Execution outline:\n{outline}\n\n"
                f"Normalized contract:\n{normalized_contract}"
            ),
        }
    ]
