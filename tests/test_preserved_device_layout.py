"""Custom device layouts preserve the default geometry and action identities."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


def make_editor():
    e = TWBEditor("")
    e.add_calculated_field("Value", "1")
    for name in ("Main", "Picker"):
        e.add_worksheet(name)
        e.configure_chart(name, mark_type="Text", label="SUM(Value)")
    e.add_dashboard(
        "Dashboard",
        width=350,
        height=700,
        layout={
            "type": "floating",
            "children": [
                {
                    "type": "worksheet",
                    "name": "Main",
                    "absolute": {"x": 0, "y": 0, "w": 100000, "h": 100000},
                },
                {
                    "type": "vertical",
                    "absolute": {"x": 0, "y": 0, "w": 60000, "h": 50000},
                    "children": [{"type": "worksheet", "name": "Picker"}],
                },
            ],
        },
    )
    e.add_dashboard_toggle_button("Dashboard", ["Picker"], initially_hidden=True)
    return e


@pytest.mark.parametrize("device", ["Phone", "Tablet"])
def test_geometry_and_hidden_toggle_ids_preserved(device, tmp_path):
    e = make_editor()
    dashboard = e.root.find("dashboards/dashboard")
    original = etree.tostring(dashboard.find("zones"))
    e.copy_default_device_layout("Dashboard", device)
    e.copy_default_device_layout("Dashboard", device)
    layouts = dashboard.findall("devicelayouts/devicelayout")
    assert len(layouts) == 1 and layouts[0].get("name") == device
    assert layouts[0].get("auto-generated") is None
    assert etree.tostring(layouts[0].find("zones")) == original
    assert etree.tostring(dashboard.find("zones")) == original
    assert layouts[0].find("size") is None
    assert layouts[0].find(".//zone[@name='Picker']").get("hidden-by-user") == "true"
    e.save(str(tmp_path / "custom-device.twb"))


def test_invalid_device_is_atomic_and_mcp_forwards(monkeypatch):
    from cwtwb.mcp import tools_workbook

    e = make_editor()
    before = etree.tostring(e.root)
    with pytest.raises(ValueError):
        e.copy_default_device_layout("Dashboard", "Watch")
    assert etree.tostring(e.root) == before
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: e)
    tools_workbook.copy_default_device_layout("Dashboard")
    assert (
        e.root.find("dashboards/dashboard/devicelayouts/devicelayout").get("name")
        == "Phone"
    )
