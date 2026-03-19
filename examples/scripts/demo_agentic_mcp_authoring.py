"""Demo: Contract-driven, profile-aware Agentic MCP authoring workflow.

Usage:
    python examples/scripts/demo_agentic_mcp_authoring.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from cwtwb.mcp.resources import (  # noqa: E402
    read_dashboard_authoring_contract,
    read_dataset_profile,
    read_profiles_index,
    read_skill,
)
from cwtwb.server import (  # noqa: E402
    add_calculated_field,
    add_dashboard,
    add_dashboard_action,
    add_worksheet,
    analyze_twb,
    configure_chart,
    create_workbook,
    review_authoring_contract,
    save_workbook,
    set_worksheet_caption,
    validate_workbook,
)


def _load_demo_contract(project_root: Path) -> dict:
    contract_path = project_root / "examples" / "agentic_mcp_authoring" / "draft_contract.json"
    return json.loads(contract_path.read_text(encoding="utf-8"))


def _print_step(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    workbook_path = output_dir / "agentic_mcp_authoring_demo.twb"
    normalized_contract_path = output_dir / "agentic_mcp_authoring_review.json"

    _print_step("1. Read Generic Contract Resource")
    contract_template = json.loads(read_dashboard_authoring_contract())
    print(f"Template keys: {', '.join(contract_template.keys())}")

    _print_step("2. Inspect Available Dataset Profiles")
    profiles_index = read_profiles_index()
    print(profiles_index)
    superstore_profile = json.loads(read_dataset_profile("superstore"))
    print(f"Loaded profile: {superstore_profile['id']} -> {superstore_profile['label']}")

    _print_step("3. Draft Contract From Human Brief")
    draft_contract = _load_demo_contract(project_root)
    print(f"Draft dashboard: {draft_contract['dashboard']['name']}")
    print(f"Available fields: {', '.join(draft_contract['available_fields'])}")

    _print_step("4. Review Contract")
    review_result = json.loads(review_authoring_contract(json.dumps(draft_contract)))
    normalized_contract_path.write_text(
        json.dumps(review_result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Detected profile: {review_result['detected_profile']}")
    print(f"Summary: {review_result['summary']}")
    print(f"Recommended skills: {', '.join(review_result['recommended_skills'])}")

    _print_step("5. Read Workflow Skills")
    workflow_skill = read_skill("authoring_workflow")
    dashboard_skill = read_skill("dashboard_designer")
    print(f"Authoring workflow skill lines: {len(workflow_skill.splitlines())}")
    print(f"Dashboard designer skill lines: {len(dashboard_skill.splitlines())}")

    _print_step("6. Execute Workbook Authoring Plan")
    normalized = review_result["normalized_contract"]
    print(create_workbook("", normalized["dashboard"]["name"]))
    print(add_calculated_field("Profit Ratio", "SUM([Profit])/SUM([Sales])", "real"))

    for worksheet in normalized["worksheets"]:
        print(add_worksheet(worksheet["name"]))

    print(
        configure_chart(
            "Sales Map",
            mark_type="Map",
            geographic_field="State/Province",
            color="SUM(Profit)",
            size="SUM(Sales)",
        )
    )
    print(
        configure_chart(
            "Sales Trend",
            mark_type="Line",
            columns=["MONTH(Order Date)"],
            rows=["SUM(Sales)"],
            color="Region",
        )
    )
    print(
        configure_chart(
            "Sub-Category Breakdown",
            mark_type="Bar",
            rows=["Sub-Category"],
            columns=["SUM(Sales)"],
            color="SUM(Profit)",
            sort_descending="SUM(Sales)",
        )
    )

    print(
        add_dashboard(
            dashboard_name=normalized["dashboard"]["name"],
            worksheet_names=[worksheet["name"] for worksheet in normalized["worksheets"]],
            layout="vertical",
        )
    )

    for action in normalized["actions"]:
        print(
            add_dashboard_action(
                dashboard_name=normalized["dashboard"]["name"],
                action_type=action["type"],
                source_sheet=action["source_sheet"],
                target_sheet=action.get("target_sheet", ""),
                fields=action.get("fields"),
                caption=action.get("caption", ""),
                url=action.get("url", ""),
            )
        )

    captions = {
        "Sales Map": "Geographic view of sales and profit, intended to drive the rest of the dashboard.",
        "Sales Trend": "Monthly sales trend after the current dashboard context is applied.",
        "Sub-Category Breakdown": "Sub-category comparison after the current selection.",
    }
    for worksheet_name, caption in captions.items():
        print(set_worksheet_caption(worksheet_name, caption))

    _print_step("7. Validate And Analyze")
    print(save_workbook(str(workbook_path)))
    print(validate_workbook(str(workbook_path)))
    print(analyze_twb(str(workbook_path)))

    _print_step("Artifacts")
    print(f"Workbook: {workbook_path}")
    print(f"Contract review: {normalized_contract_path}")


if __name__ == "__main__":
    main()
