import json
from pathlib import Path

import pytest

from cwtwb.dashboards import extract_layout_worksheets, load_dashboard_layout_file
from cwtwb.gallery import (
    DashboardRequirements,
    list_gallery_templates,
    materialize_gallery_layout,
    recommend_gallery_templates,
)


def _top(**kwargs):
    return recommend_gallery_templates(DashboardRequirements(**kwargs), limit=1)[0]


def test_all_seven_packaged_templates_load():
    templates = list_gallery_templates()
    assert {template.name for template in templates} == {
        "comparison",
        "executive-briefing",
        "executive-summary",
        "geo-explorer",
        "kpi-detail",
        "left-filter",
        "trend-analysis",
    }


def test_trend_recommendation_is_explainable():
    recommendation = _top(
        primary_intent="trend",
        has_temporal_data=True,
        kpi_count=2,
        chart_count=3,
        chart_types=("Line", "Bar"),
    )
    assert recommendation.template == "trend-analysis"
    assert any("primary intent" in reason for reason in recommendation.matched)
    assert any("preferred chart types" in reason for reason in recommendation.matched)


def test_geographic_and_filter_heavy_intents_select_expected_templates():
    assert _top(
        primary_intent="geographic",
        has_geographic_data=True,
        chart_count=2,
        chart_types=("Map", "Bar"),
    ).template == "geo-explorer"
    assert _top(
        primary_intent="filter-heavy",
        filter_count=5,
        kpi_count=2,
        chart_count=3,
    ).template == "left-filter"


def test_comparison_and_executive_briefing_select_expected_templates():
    assert _top(
        primary_intent="comparison", chart_count=3, chart_types=("Bar",)
    ).template == "comparison"
    assert _top(
        primary_intent="overview", kpi_count=5, chart_count=1
    ).template == "executive-briefing"


def test_generic_request_has_stable_default_and_excludes_hard_requirements():
    recommendations = recommend_gallery_templates(DashboardRequirements(), limit=7)
    assert recommendations[0].template == "executive-summary"
    assert "trend-analysis" not in [item.template for item in recommendations]
    assert "geo-explorer" not in [item.template for item in recommendations]


def test_materialization_binds_exact_worksheet_names_and_writes_dsl(tmp_path):
    output = tmp_path / "trend-layout.json"
    result = materialize_gallery_layout(
        "trend-analysis",
        worksheet_slots={
            "kpis": ["Revenue KPI", "Margin KPI"],
            "trend": "Monthly Revenue",
            "details": ["Revenue by Region", "Revenue by Segment"],
        },
        output_path=output,
    )
    assert output.is_file()
    assert extract_layout_worksheets(result["layout_schema"]) == [
        "Revenue KPI",
        "Margin KPI",
        "Monthly Revenue",
        "Revenue by Region",
        "Revenue by Segment",
    ]
    loaded = load_dashboard_layout_file(output)
    assert extract_layout_worksheets(loaded) == extract_layout_worksheets(
        result["layout_schema"]
    )
    assert json.loads(output.read_text(encoding="utf-8"))["layout_schema"]


def test_materialized_layout_creates_real_dashboard(editor, tmp_path):
    worksheets = ["KPI 1", "KPI 2", "Trend", "Detail 1", "Detail 2"]
    for worksheet in worksheets:
        editor.add_worksheet(worksheet)
    result = materialize_gallery_layout(
        "trend-analysis",
        worksheet_slots={
            "kpis": worksheets[:2],
            "trend": worksheets[2],
            "details": worksheets[3:],
        },
    )
    message = editor.add_dashboard(
        "Trend Dashboard",
        worksheet_names=worksheets,
        layout=result["layout_schema"],
    )
    output = tmp_path / "gallery-dashboard.twb"
    editor.save(output, validate=False)
    assert "Trend Dashboard" in message
    assert output.is_file()
    assert editor.root.find("./dashboards/dashboard[@name='Trend Dashboard']") is not None


def test_materialization_rejects_missing_unknown_and_wrong_capacity_slots():
    with pytest.raises(ValueError, match="Missing worksheet binding"):
        materialize_gallery_layout(
            "comparison", worksheet_slots={}
        )
    with pytest.raises(ValueError, match="Unknown Gallery worksheet slots"):
        materialize_gallery_layout(
            "comparison", worksheet_slots={"charts": ["A", "B"], "extra": "C"}
        )
    with pytest.raises(ValueError, match="accepts 2-4"):
        materialize_gallery_layout(
            "comparison", worksheet_slots={"charts": ["A"]}
        )


def test_unknown_template_and_invalid_limit_fail_clearly():
    with pytest.raises(ValueError, match="Unknown Gallery template"):
        materialize_gallery_layout("missing", worksheet_slots={})
    with pytest.raises(ValueError, match="at least 1"):
        recommend_gallery_templates(DashboardRequirements(), limit=0)


def test_gallery_yaml_files_are_inside_package_tree():
    package_gallery = Path(__file__).parents[1] / "src" / "cwtwb" / "gallery"
    assert len(list(package_gallery.glob("*.yaml"))) == 7
