from cwtwb.charts.dispatcher import (
    configure_chart as dispatch_chart,
    configure_dual_axis as dispatch_dual_axis,
    decide_chart_builder,
    decide_dual_axis_builder,
)
from cwtwb.charts import dispatcher
from cwtwb.charts.pattern_mapping import normalize_chart_pattern
from cwtwb.charts.routing_policy import profile_chart_request, profile_dual_axis_request


def test_advanced_pattern_mapping_normalizes_expected_marks():
    scatter = normalize_chart_pattern("Scatterplot", columns=["SUM(Sales)"], rows=["SUM(Profit)"])
    heatmap = normalize_chart_pattern("Heatmap", columns=["Category"], rows=["Region"])
    tree_map = normalize_chart_pattern("Tree Map", columns=["Category"], rows=["Region"])
    bubble = normalize_chart_pattern("Bubble Chart", columns=["Category"], rows=["Region"])

    assert scatter.actual_mark_type == "Circle"
    assert scatter.columns == ["SUM(Sales)"]
    assert scatter.rows == ["SUM(Profit)"]

    assert heatmap.actual_mark_type == "Square"
    assert heatmap.columns == ["Category"]
    assert heatmap.rows == ["Region"]

    assert tree_map.actual_mark_type == "Square"
    assert tree_map.columns == []
    assert tree_map.rows == []

    assert bubble.actual_mark_type == "Circle"
    assert bubble.columns == []
    assert bubble.rows == []


def test_dispatch_decisions_cover_basic_pie_map_and_dual_axis():
    assert decide_chart_builder("Scatterplot").builder_name == "basic"
    assert decide_chart_builder("Scatterplot").actual_mark_type == "Circle"
    assert decide_chart_builder("Scatterplot").route_family == "pattern"
    assert decide_chart_builder("Scatterplot").support_level == "advanced"
    assert decide_chart_builder("Heatmap").actual_mark_type == "Square"
    assert decide_chart_builder("Pie").builder_name == "pie"
    assert decide_chart_builder("Pie").route_family == "primitive"
    assert decide_chart_builder("Map").builder_name == "map"
    assert decide_chart_builder("Map").route_family == "primitive"
    assert decide_dual_axis_builder().builder_name == "dual_axis"
    assert decide_dual_axis_builder().route_family == "composition"


def test_route_profiles_make_capability_boundaries_explicit():
    core = profile_chart_request("Bar")
    advanced = profile_chart_request("Bubble Chart")
    recipe = profile_chart_request("Donut")
    dual_axis = profile_dual_axis_request()

    assert core.support_level == "core"
    assert core.route_family == "primitive"

    assert advanced.support_level == "advanced"
    assert advanced.route_family == "pattern"
    assert advanced.actual_mark_type == "Circle"

    assert recipe.support_level == "recipe"
    assert recipe.route_family == "compatibility"

    assert dual_axis.support_level == "advanced"
    assert dual_axis.route_family == "composition"


def test_dispatch_routes_pie_and_map_to_specialized_builders(monkeypatch):
    calls: list[tuple[str, tuple, dict]] = []

    class FakePieBuilder:
        def __init__(self, *args, **kwargs):
            calls.append(("pie", args, kwargs))

        def build(self):
            return "pie-built"

    class FakeMapBuilder:
        def __init__(self, *args, **kwargs):
            calls.append(("map", args, kwargs))

        def build(self):
            return "map-built"

    monkeypatch.setattr(dispatcher, "PieChartBuilder", FakePieBuilder)
    monkeypatch.setattr(dispatcher, "MapChartBuilder", FakeMapBuilder)

    assert dispatch_chart(object(), "PieSheet", mark_type="Pie") == "pie-built"
    assert dispatch_chart(object(), "MapSheet", mark_type="Map", geographic_field="State") == "map-built"
    assert calls[0][0] == "pie"
    assert calls[1][0] == "map"


def test_dispatch_routes_basic_and_dual_axis_builders(monkeypatch):
    calls: list[tuple[str, tuple, dict]] = []

    class FakeBasicBuilder:
        def __init__(self, *args, **kwargs):
            calls.append(("basic", args, kwargs))

        def build(self):
            return "basic-built"

    class FakeDualAxisBuilder:
        def __init__(self, *args, **kwargs):
            calls.append(("dual", args, kwargs))

        def build(self):
            return "dual-built"

    monkeypatch.setattr(dispatcher, "BasicChartBuilder", FakeBasicBuilder)
    monkeypatch.setattr(dispatcher, "DualAxisChartBuilder", FakeDualAxisBuilder)

    assert dispatch_chart(object(), "ScatterSheet", mark_type="Scatterplot") == "basic-built"
    assert dispatch_dual_axis(object(), "ComboSheet", columns=["SUM(Sales)", "SUM(Profit)"]) == "dual-built"
    assert calls[0][0] == "basic"
    assert calls[1][0] == "dual"
