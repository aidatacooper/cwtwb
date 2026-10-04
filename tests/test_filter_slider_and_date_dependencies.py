"""Slider visibility and expression filter dependencies use synthetic dates."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


def make():
    e = TWBEditor("")
    e.add_calculated_field(
        "Observed Date",
        "#2020-01-01#",
        datatype="date",
        role="dimension",
        field_type="ordinal",
    )
    e.add_calculated_field("Metric", "1.0")
    e.add_worksheet("Plot")
    e.configure_chart(
        "Plot",
        mark_type="Line",
        columns=["YEAR(Observed Date)"],
        rows=["SUM(Metric)"],
        filters=[{"column": "YEAR(Observed Date)", "values": [2020]}],
    )
    return e


def layout(**extra):
    return {
        "type": "vertical",
        "children": [
            {"type": "worksheet", "name": "Plot"},
            {
                "type": "filter",
                "worksheet": "Plot",
                "field": "YEAR(Observed Date)",
                "mode": "slider",
                **extra,
            },
        ],
    }


@pytest.mark.parametrize("visible", [True, False])
def test_slider_boolean_and_filter_expression_dependencies(visible, tmp_path):
    e = make()
    for _ in range(2):
        e.add_dashboard("Dash", layout=layout(show_slider=visible, show_all=False))
    z = e.root.find(".//dashboard/zones//zone[@type-v2='filter']")
    assert z.get("show-slider") == str(visible).lower()
    deps = e.root.find(".//dashboard/datasource-dependencies")
    ci = e.field_registry.parse_expression("YEAR(Observed Date)")
    assert deps.find(f"column[@name='{ci.column_local_name}']") is not None
    assert len(deps.findall(f"column-instance[@name='{ci.instance_name}']")) == 1
    e.save(str(tmp_path / "slider.twb"))


def test_default_slider_visibility_keeps_native_default():
    e = make()
    e.add_dashboard("Dash", layout=layout())
    assert (
        e.root.find(".//dashboard/zones//zone[@type-v2='filter']").get("show-slider")
        is None
    )


@pytest.mark.parametrize("invalid", [None, "false", 0, {}])
def test_invalid_slider_preserves_existing_dashboard(invalid):
    e = make()
    e.add_dashboard("Dash", layout=layout())
    before = etree.tostring(e.root)
    with pytest.raises(ValueError, match="boolean"):
        e.add_dashboard("Dash", layout=layout(show_slider=invalid))
    assert etree.tostring(e.root) == before
