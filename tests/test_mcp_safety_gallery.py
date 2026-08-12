import json

import pytest

from cwtwb.mcp.app import read_gallery_index, read_gallery_template
from cwtwb.server import (
    add_calculated_field,
    audit_calculated_fields,
    create_workbook,
    generate_gallery_layout,
    list_gallery_templates,
    recommend_gallery_templates,
    repair_calculated_field_issues,
    validate_formula,
)


@pytest.fixture(autouse=True)
def fresh_workbook():
    create_workbook("", "Safety and Gallery Tests")


def test_formula_validation_tool_is_read_only_and_structured():
    payload = json.loads(validate_formula("CHR(10)", "Broken Label"))
    assert payload["valid"] is False
    assert payload["field_name"] == "Broken Label"
    assert payload["issues"][0]["suggestion"] == "CHAR"


def test_mcp_add_calculated_field_can_bypass_catalog_explicitly():
    result = add_calculated_field(
        "Future Calc",
        "FUTURE_TABLEAU_FUNCTION([Sales])",
        validate_formula=False,
    )
    assert "Future Calc" in result


def test_audit_and_repair_tools_default_to_dry_run():
    add_calculated_field(
        "Broken Label",
        "'text'",
        datatype="string",
        role="measure",
        field_type="quantitative",
    )
    audit = json.loads(audit_calculated_fields())
    preview = json.loads(repair_calculated_field_issues())
    after_preview = json.loads(audit_calculated_fields())
    applied = json.loads(repair_calculated_field_issues(dry_run=False))
    final = json.loads(audit_calculated_fields())

    assert audit["issue_count"] == 1
    assert preview["dry_run"] is True
    assert preview["mutated"] is False
    assert "next_step" in preview
    assert after_preview["issue_count"] == 1
    assert applied["mutated"] is True
    assert final["issue_count"] == 0


def test_gallery_tools_list_recommend_and_materialize(tmp_path):
    templates = json.loads(list_gallery_templates())
    recommendations = json.loads(
        recommend_gallery_templates(
            kpi_count=2,
            chart_count=3,
            chart_types=["Line", "Bar"],
            has_temporal_data=True,
            primary_intent="trend",
        )
    )
    output = tmp_path / "gallery-layout.json"
    materialized = json.loads(
        generate_gallery_layout(
            "trend-analysis",
            {
                "kpis": ["KPI 1", "KPI 2"],
                "trend": "Trend",
                "details": ["Detail 1", "Detail 2"],
            },
            str(output),
        )
    )

    assert len(templates) == 7
    assert recommendations[0]["template"] == "trend-analysis"
    assert materialized["template"] == "trend-analysis"
    assert output.is_file()


def test_gallery_resources_expose_index_and_yaml():
    index = read_gallery_index()
    template = read_gallery_template("comparison")
    assert "cwtwb://gallery/comparison" in index
    assert "name: comparison" in template
