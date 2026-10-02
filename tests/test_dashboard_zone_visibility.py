"""Synthetic dynamic visibility and relevant-value filter control contracts."""
import pytest
from cwtwb import TWBEditor
from cwtwb.mcp import tools_workbook


def fixture():
    editor = TWBEditor("")
    editor.add_parameter("Selection", "string", "")
    editor.add_calculated_field("Panel Visible", "[Selection] <> ''", datatype="boolean", role="dimension", field_type="nominal")
    editor.add_worksheet("Details")
    editor.configure_chart("Details", mark_type="Text", label="SUM(Sales)")
    return editor


def layout(field="Panel Visible"):
    return {"type": "container", "direction": "vertical", "visibility": {"field": field, "initially_visible": False}, "children": [{"type": "worksheet", "name": "Details"}, {"type": "filter", "worksheet": "Details", "field": "Customer Name", "mode": "dropdown", "values": "relevant", "show_all": False}]}


def test_visibility_graph_and_relevant_control_round_trip(tmp_path):
    editor = fixture()
    editor.add_dashboard("Overview", layout=layout())
    db = editor.root.find("dashboards/dashboard")
    graph = editor.root.find("datagraph/graph")
    source = graph.find("nodes/single-value-field-node")
    target = graph.find("nodes/dashboard-zone-visibility-node")
    assert target.get("dashboard-identifier") == db.find("simple-id").get("uuid")
    assert db.find("zones/zone").get("id") == target.get("zone-id")
    local = editor.field_registry._find_field("Panel Visible").local_name
    assert source.get("fieldname").endswith("." + local)
    assert graph.find("edges/edge").attrib == {"from": source.get("value-output-guid"), "to": target.get("visibility-input-guid")}
    assert all(z.get("hidden-by-user") == "true" for z in db.findall("zones//zone"))
    control = db.find("zones//zone[@type-v2='filter']")
    assert control.get("values") == "relevant" and control.get("show-all") == "false"
    assert db.find("datasource-dependencies/column[@name='%s']/calculation" % local) is not None
    path = tmp_path / "roundtrip.twb"
    editor.save(path, validate=False)
    loaded = TWBEditor(str(path))
    assert loaded.root.find("datagraph/graph/edges/edge").attrib == graph.find("edges/edge").attrib


def test_replacing_dashboard_removes_stale_graph_bindings():
    editor = fixture()
    editor.add_dashboard("Overview", layout=layout())
    editor.add_dashboard("Other", layout=layout())
    editor.add_dashboard("Overview", layout=layout())
    graph = editor.root.find("datagraph/graph")
    assert len(graph.findall("nodes/dashboard-zone-visibility-node")) == 2
    assert len(graph.findall("nodes/single-value-field-node")) == 2
    assert len(graph.findall("node-execution-subgraphs/pair")) == 4
    assert len(graph.findall("edges/edge")) == 2


@pytest.mark.parametrize("field", ["Sales", "Customer Name"])
def test_visibility_rejects_non_boolean_fields(field):
    with pytest.raises(ValueError, match="boolean"):
        fixture().add_dashboard("Overview", layout=layout(field))


@pytest.mark.parametrize("visibility", [{}, {"field": ""}, {"field": "Panel Visible", "initially_visible": "false"}])
def test_invalid_visibility_contracts(visibility):
    config = layout()
    config["visibility"] = visibility
    with pytest.raises(ValueError):
        fixture().add_dashboard("Overview", layout=config)


def test_mcp_layout_preserves_visibility(monkeypatch):
    editor = fixture()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.add_dashboard("Overview", ["Details"], layout=layout())
    assert editor.root.find("datagraph/graph/nodes/dashboard-zone-visibility-node") is not None


def test_dashboard_text_parameter_run_has_live_reference_and_dependencies():
    editor = fixture()
    editor.add_dashboard("Title", layout={"type":"text", "runs":[{"text":"Selection: "}, {"parameter":"Selection", "bold":True}]})
    db = editor.root.find("dashboards/dashboard")
    assert db.find("zones/zone/formatted-text/run[@bold='true']").text == "<[Parameters].[Parameter 1]>"
    assert db.find("datasource-dependencies[@datasource='Parameters']/column[@caption='Selection']") is not None


@pytest.mark.parametrize("run", [{"parameter":"unknown"},{"parameter":None},{"parameter":"Selection","text":"literal"}])
def test_dashboard_parameter_text_run_validation(run):
    with pytest.raises(ValueError):
        fixture().add_dashboard("Title",layout={"type":"text","runs":[run]})


def test_selected_worksheet_filters_share_group_and_keep_other_sheet_independent():
    editor = fixture()
    for name in ["Orders", "KPIs", "Map"]:
        editor.add_worksheet(name)
        editor.configure_chart(name,mark_type="Text",label="SUM(Sales)",filters=[{"column":"Customer Name","values":[]}])
    editor.link_worksheet_filters("Customer Name",["Orders","KPIs"])
    filters = {n.get("name"):n.find("table/view/filter") for n in editor.root.findall("worksheets/worksheet") if n.get("name") in ["Orders","KPIs","Map"]}
    assert filters['Orders'].get('filter-group') == filters['KPIs'].get('filter-group')
    assert filters['Orders'].get('filter-group') and filters['Map'].get('filter-group') is None


def test_missing_linked_filter_rejected_without_mutating_existing_filter():
    editor = fixture()
    editor.add_worksheet("Orders")
    editor.configure_chart("Orders",mark_type="Text",label="SUM(Sales)",filters=[{"column":"Customer Name","values":[]}])
    with pytest.raises(ValueError,match="categorical filter"):
        editor.link_worksheet_filters("Customer Name",["Orders","Details"])
    assert editor.root.find("worksheets/worksheet[@name='Orders']/table/view/filter").get("filter-group") is None


def test_linked_filters_reject_different_initial_members():
    editor = fixture()
    for name, members in [("Orders",["A"]),("KPIs",["B"])]:
        editor.add_worksheet(name)
        editor.configure_chart(name,mark_type="Text",label="SUM(Sales)",filters=[{"column":"Customer Name","values":members}])
    with pytest.raises(ValueError,match="identical initial members"):
        editor.link_worksheet_filters("Customer Name",["Orders","KPIs"])


def test_rounded_corner_manifest_and_saved_zone_serialization(tmp_path):
    editor = fixture()
    editor.add_dashboard("Rounded",layout={"type":"container","corner_radius":5,"children":[{"type":"worksheet","name":"Details","corner_radius":20}]})
    tag="_.fcp.DashboardRoundedCorners.true..."
    assert editor.root.find("document-format-change-manifest/"+tag+"DashboardRoundedCorners") is not None
    zones=editor.root.find("dashboards/dashboard/zones")
    assert sorted(n.get("value") for n in zones.findall(".//"+tag+"format"))==["20","5"]
    path=tmp_path/"rounded.twb";editor.save(path,validate=False)
    from lxml import etree
    assert sorted(n.get("value") for n in etree.parse(str(path)).findall(".//"+tag+"format")) == ["20", "5"]


@pytest.mark.parametrize("radius", [-1,"5",True,float('nan'),float('inf')])
def test_rounded_corner_rejects_invalid_values(radius):
    with pytest.raises(ValueError,match="nonnegative"):
        fixture().add_dashboard("Rounded",layout={"type":"empty","corner_radius":radius})
