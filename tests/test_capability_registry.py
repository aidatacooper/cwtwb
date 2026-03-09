from cwtwb.capability_registry import (
    format_capability_catalog,
    get_capability,
    get_level_summary,
    list_capabilities,
)


def test_chart_alias_resolution():
    spec = get_capability("chart", "Multipolygon")
    assert spec is not None
    assert spec.canonical == "Map"
    assert spec.level == "core"



def test_recipe_capabilities_are_listed():
    recipe_names = [spec.canonical for spec in list_capabilities(level="recipe")]
    assert "Donut" in recipe_names
    assert "Lollipop" in recipe_names



def test_level_summary_and_catalog_text():
    summary = get_level_summary()
    assert summary["core"] > 0
    assert summary["advanced"] > 0
    assert summary["recipe"] > 0
    assert summary["unsupported"] > 0

    catalog = format_capability_catalog()
    assert "cwtwb capability catalog" in catalog
    assert "[core]" in catalog
    assert "chart: Bar" in catalog

