"""Author-free contracts for cross-dashboard filters and parameter toggles."""

import pytest
from lxml import etree
from cwtwb import TWBEditor


def editor():
    e = TWBEditor("")
    e.add_calculated_field(
        "Category", "'A'", datatype="string", role="dimension", field_type="nominal"
    )
    e.add_calculated_field("Value", "7")
    for name in ["Plot", "Detail"]:
        e.add_worksheet(name)
        e.configure_chart(name, columns=["Category"], rows=["SUM(Value)"])
    e.add_parameter("Mode", datatype="integer", default_value="1")
    e.add_parameter("Scale", datatype="integer", default_value="2")
    e.add_dashboard("Details", worksheet_names=["Detail"])
    e.add_dashboard(
        "Summary",
        width=900,
        height=700,
        layout={
            "type": "container",
            "children": [
                {"type": "worksheet", "name": "Plot"},
                {
                    "type": "container",
                    "absolute": {"x": 700, "y": 40, "w": 180, "h": 200},
                    "children": [
                        {"type": "paramctrl", "parameter": "Mode"},
                        {"type": "paramctrl", "parameter": "Scale"},
                    ],
                },
            ],
        },
    )
    return e


@pytest.mark.parametrize(
    "behavior,serialized",
    [("show-all", "all"), ("show-none", "none"), ("keep-current", None)],
)
def test_cross_dashboard_filter_contract(behavior, serialized):
    e = editor()
    e.add_dashboard_action(
        "Summary",
        "filter",
        source_sheet="Plot",
        target_dashboard="Details",
        clear_behavior=behavior,
    )
    action = e.root.find("actions/action")
    assert action.find("source").get("dashboard") == "Summary"
    assert action.find("source").get("worksheet") == "Plot"
    command = action.find("command")
    values = {p.get("name"): p.get("value") for p in command}
    assert values["target"] == "Details"
    assert values["special-fields"] == "all"
    assert values.get("on-empty") == serialized
    assert "exclude" not in values


def test_cross_dashboard_explicit_mapping_destination():
    e = editor()
    e.add_dashboard_action(
        "Summary",
        "filter",
        source_sheet="Plot",
        target_sheet="Detail",
        target_dashboard="Details",
        field_mappings={"Category": "Category"},
    )
    assert (
        e.root.find("actions/action/link").get("expression").startswith("tsl:Details?")
    )


@pytest.mark.parametrize(
    "options",
    [
        {"target_dashboard": "Missing"},
        {"target_dashboard": "Details", "target_sheet": "Plot"},
        {"target_dashboard": "Details", "target_sheets": ["Detail"]},
        {"target_dashboard": "Details", "clear_behavior": "invalid"},
    ],
)
def test_invalid_cross_dashboard_filter_is_atomic(options):
    e = editor()
    before = etree.tostring(e.root)
    with pytest.raises(ValueError):
        e.add_dashboard_action("Summary", "filter", source_sheet="Plot", **options)
    assert etree.tostring(e.root) == before


@pytest.mark.parametrize("hidden", [True, False])
def test_parameter_container_native_toggle(hidden):
    e = editor()
    e.add_dashboard_toggle_button(
        "Summary", target_parameters=["Mode", "Scale"], initially_hidden=hidden
    )
    button = e.root.find("dashboards/dashboard[@name='Summary']/zones/zone/button")
    assert button.get("active-visual-state-index") == ("1" if hidden else "0")
    action = button.findtext("toggle-action")
    assert "tabdoc:toggle-button-click-action" in action
    target_id = action.split("zone-ids=[")[1].split("]")[0]
    target = e.root.find(
        f"dashboards/dashboard[@name='Summary']/.//zone[@id='{target_id}']"
    )
    assert target.get("type-v2", target.get("type")) == "layout-flow"
    assert len(target.findall(".//zone")) == 2
    assert all(
        (z.get("hidden-by-user") == "true") == hidden for z in target.iter("zone")
    )


@pytest.mark.parametrize("parameters", [["Mode"], ["Missing"], ["Mode", "Mode"], []])
def test_parameter_toggle_validation_is_atomic(parameters):
    e = editor()
    before = etree.tostring(e.root)
    with pytest.raises(ValueError):
        e.add_dashboard_toggle_button("Summary", target_parameters=parameters)
    assert etree.tostring(e.root) == before


def test_cross_dashboard_initial_selection_targets_destination_only():
    e = editor()
    e.add_dashboard_action(
        "Summary",
        "filter",
        source_sheet="Plot",
        target_dashboard="Details",
        fields=["Category"],
        caption="Selected",
        clear_behavior="show-none",
    )
    e.initialize_dashboard_filter_action(
        "Summary", "Selected", {"Category": ["No Selection"]}
    )
    assert (
        e.root.find("worksheets/worksheet[@name='Detail']/table/view/filter")
        is not None
    )
    assert e.root.find("worksheets/worksheet[@name='Plot']/table/view/filter") is None
