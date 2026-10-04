"""Native set controls authored from synthetic fields and explicit memberships."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


def make_editor():
    e = TWBEditor("")
    e.add_calculated_field(
        "Category", "'A'", datatype="string", role="dimension", field_type="nominal"
    )
    e.add_calculated_field("Value", "1")
    e.add_set("Selected Categories", "Category", members=["A", "B"])
    e.add_worksheet("Plot")
    e.configure_chart(
        "Plot", mark_type="Bar", rows=["Category"], columns=["SUM(Value)"]
    )
    return e


def tree(**changes):
    control = {
        "type": "set_control",
        "field": "Selected Categories",
        "worksheet": "Plot",
        "caption": "Choose categories",
    }
    control.update(changes)
    return {
        "type": "vertical",
        "children": [{"type": "worksheet", "name": "Plot"}, control],
    }


def test_native_zone_card_manifest_and_membership_survive_save(tmp_path):
    e = make_editor()
    e.add_dashboard("Dashboard", worksheet_names=["Plot"], layout=tree())
    e.add_dashboard("Dashboard", worksheet_names=["Plot"], layout=tree())
    ds = e.root.find("datasources/datasource").get("name")
    expected = f"[{ds}].[Selected Categories]"
    zone = e.root.find("dashboards/dashboard/zones/.//zone[@type-v2='setMembership']")
    assert zone.get("param") == expected and zone.get("name") == "Plot"
    assert zone.get("mode") == "dropdown"
    assert zone.find("formatted-text/run").text == "Choose categories"
    cards = e.root.findall(
        "windows/window[@name='Plot']/cards/edge/strip/card[@type='setMembership']"
    )
    assert len(cards) == 1 and cards[0].get("param") == expected
    assert (
        e.root.find("document-format-change-manifest/SetMembershipControl") is not None
    )
    assert (
        e.root.find(f"dashboards/dashboard/datasources/datasource[@name='{ds}']")
        is not None
    )
    assert e.root.findall("datasources/datasource/group/groupfilter/groupfilter")
    output = tmp_path / "controls.twb"
    e.save(str(output))
    saved = etree.parse(str(output))
    assert saved.find(".//zone[@type-v2='setMembership']").get("param") == expected


@pytest.mark.parametrize(
    "changes",
    [
        {"field": "Missing"},
        {"field": "Category"},
        {"worksheet": "Missing"},
        {"worksheet": ""},
        {"mode": "bad"},
        {"show_apply": "true"},
        {"show_apply": 1},
    ],
)
def test_invalid_control_preserves_existing_dashboard(changes):
    e = make_editor()
    e.add_dashboard("Dashboard", worksheet_names=["Plot"])
    before = etree.tostring(e.root)
    with pytest.raises(ValueError):
        e.add_dashboard("Dashboard", worksheet_names=["Plot"], layout=tree(**changes))
    assert etree.tostring(e.root) == before


def test_mcp_dashboard_accepts_control_layout(monkeypatch):
    from cwtwb.mcp import tools_workbook

    e = make_editor()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: e)
    tools_workbook.add_dashboard(
        "Dashboard",
        worksheet_names=["Plot"],
        layout=tree(show_title=False, mode="checkdropdown"),
    )
    assert e.root.find(".//zone[@type-v2='setMembership']").get("show-title") == "false"


@pytest.mark.parametrize("mode", ["", "dropdown", "checkdropdown"])
def test_set_control_modes_survive_save_and_card_replacement(tmp_path, mode):
    e = make_editor()
    e.add_dashboard("Dashboard", worksheet_names=["Plot"], layout=tree())
    e.add_dashboard("Dashboard", worksheet_names=["Plot"], layout=tree(mode=mode))
    output = tmp_path / "set-control-modes.twb"
    e.save(str(output))
    saved = etree.parse(str(output))
    zone = saved.find(".//zone[@type-v2='setMembership']")
    cards = saved.findall(
        ".//window[@name='Plot']/cards/edge/strip/card[@type='setMembership']"
    )
    assert zone.get("mode") == (mode or "dropdown")
    assert len(cards) == 1 and cards[0].get("mode") == (mode or "dropdown")
    assert cards[0].get("param") == zone.get("param")
    assert (
        len(saved.findall(".//document-format-change-manifest/SetMembershipControl"))
        == 1
    )
    assert (
        len(saved.findall(".//datasources/datasource/group/groupfilter/groupfilter"))
        == 2
    )


@pytest.mark.parametrize("show_apply", [True, False])
def test_set_control_apply_flag_is_native_and_explicit(show_apply):
    e = make_editor()
    e.add_dashboard(
        "Dashboard",
        worksheet_names=["Plot"],
        layout=tree(mode="checkdropdown", show_apply=show_apply),
    )
    zone = e.root.find(".//zone[@type-v2='setMembership']")
    assert zone.get("show-apply") == str(show_apply).lower()
    assert zone.get("mode") == "checkdropdown"
