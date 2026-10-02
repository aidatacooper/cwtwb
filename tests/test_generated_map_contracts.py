"""Synthetic contracts for generated geography and explicit set members."""
import pytest
from cwtwb import TWBEditor


def synthetic():
    editor = TWBEditor("")
    for name, formula, datatype, role in [("Place", "'A'", "string", "dimension"), ("City", "'B'", "string", "dimension"), ("Value", "1.0", "real", "measure")]:
        editor.add_calculated_field(name, formula, datatype=datatype, role=role)
    editor.add_worksheet("Map")
    return editor


def test_generated_geography_preserves_virtual_fields_layers_and_details(tmp_path):
    editor = synthetic()
    editor.add_set("Picked", "Place", members=['A"#%\\B'])
    editor.configure_layered_chart("Map", columns=["Longitude (generated)"], rows=["Latitude (generated)", "Latitude (generated)"], panes=[{"axis": "Latitude (generated)", "mark_type": "Multipolygon", "detail": "Place", "geometry": "Geometry (generated)"}, {"axis": "Latitude (generated)", "mark_type": "Circle", "detail": "Place", "detail_extra": ["City"], "size": "SUM(Value)"}], filters=[{"column": "Picked", "values": [True]}])
    table = editor.root.find("worksheets/worksheet/table")
    assert table.find("view/mapsources/mapsource").get("name") == "Tableau"
    assert [n.get("y-index") for n in table.findall("panes/pane")] == ["0", "1"]
    assert table.find("panes/pane/encodings/geometry").get("column").endswith(".[Geometry (generated)]")
    assert len(table.findall("panes/pane[2]/encodings/lod")) == 2
    assert not editor.root.findall("datasources/datasource/column[@name='[Geometry (generated)]']")
    assert not table.findall("view/datasource-dependencies/column[@name='[Latitude (generated)]']")
    member = editor.root.find("datasources/datasource/group/groupfilter").get("member")
    assert member == '"A\\"\\#\\%\\\\B"'
    path = tmp_path / "map.twb"
    editor.save(path, validate=False)
    loaded = TWBEditor.open_existing(path)
    assert loaded.root.find(".//encodings/geometry") is not None


@pytest.mark.parametrize("members", [[float("nan")], [{}], "A"])
def test_explicit_set_rejects_invalid_members(members):
    with pytest.raises(ValueError):
        synthetic().add_set("Picked", "Place", members=members)


def test_explicit_set_unions_members_and_rejects_ranking():
    editor = synthetic()
    editor.add_set("Picked", "Place", members=["A", "B"])
    assert len(editor.root.findall("datasources/datasource/group/groupfilter[@function='union']/groupfilter")) == 2
    with pytest.raises(ValueError):
        editor.add_set("Bad", "Place", members=["A"], top_n=3, basis_field="Value")


def test_explicit_empty_set_retains_empty_level():
    editor = synthetic()
    editor.add_set("Picked", "Place", members=[])
    assert editor.root.find("datasources/datasource/group/groupfilter").get("function") == "empty-level"


def test_explicit_set_keeps_numeric_and_boolean_literals_unquoted():
    editor = synthetic()
    editor.add_set("Picked", "Place", members=[True, False, 2, 2.5])
    assert [n.get("member") for n in editor.root.findall("datasources/datasource/group/groupfilter/groupfilter")] == ["true", "false", "2", "2.5"]


def test_layered_detail_dimension_can_sort_numeric_trellis_axes():
    editor = synthetic()
    editor.configure_layered_chart("Map", columns=["SUM(Value)"], rows=["SUM(Value)"], panes=[{"axis": "SUM(Value)", "detail": "Place"}], sort_descending="SUM(Value)", sort_field="Place")
    node = editor.root.find(".//computed-sort")
    assert node is not None and node.get("direction") == "DESC"
    assert node.get("column").endswith("." + editor.field_registry.parse_expression("Place").instance_name)
    assert node.get("using").endswith("." + editor.field_registry.parse_expression("SUM(Value)").instance_name)


def test_geocoding_context_overwrites_template_defaults_and_is_idempotent():
    editor = synthetic()
    for _ in range(2):
        editor.set_geocoding_context(country="United States", state=None)
    nodes = editor.root.findall("datasources/datasource/semantic-values/semantic-value")
    countries = [n for n in nodes if n.get("key") == "[Country].[Name]"]
    states = [n for n in nodes if n.get("key") == "[State].[Name]"]
    assert len(countries) == len(states) == 1
    assert countries[0].get("value") == '"United States"'
    assert states[0].get("value") == "%null%"
    editor.set_geocoding_context(country="Canada", state="Ontario")
    values = {n.get("key"): n.get("value") for n in editor.root.findall("datasources/datasource/semantic-values/semantic-value")}
    assert values["[Country].[Name]"] == '"Canada"'
    assert values["[State].[Name]"] == '"Ontario"'


@pytest.mark.parametrize("kwargs", [{"country": ""}, {"country": None}, {"country": "US", "state": ""}, {"country": "US", "state": 42}])
def test_geocoding_context_rejects_invalid_names(kwargs):
    with pytest.raises(ValueError):
        synthetic().set_geocoding_context(**kwargs)


def test_table_calc_order_uses_inout_instance_for_set_group():
    editor = synthetic()
    editor.add_set("Picked", "Place", members=["A"])
    editor.add_calculated_field("Rank", "RANK_UNIQUE(SUM([Value]))", datatype="integer", table_calc="Rows")
    editor.configure_layered_chart("Map", rows=["Rank"], panes=[{"axis": "Rank", "detail": "Place", "detail_extra": ["Picked"]}], table_calc_overrides={"Rank": [{"ordering_type": "Field", "order": ["Picked", "Place"]}]})
    orders = editor.root.findall(".//datasource-dependencies/column-instance/table-calc/order")
    assert [node.get("field").split(".")[-1] for node in orders] == ["[io:Picked:nk]", editor.field_registry.parse_expression("Place").column_local_name]


def test_hidden_exclusion_preserves_partition_and_uses_binary_set_difference():
    editor = synthetic()
    editor.add_set("Picked", "Place", members=["A"])
    editor.configure_layered_chart("Map", rows=["SUM(Value)"], panes=[{"axis": "SUM(Value)", "detail": "Place", "detail_extra": ["Picked"]}], filters=[{"column": "Picked", "values": [True], "kind": "hide", "exclude": True}])
    view = editor.root.find("worksheets/worksheet/table/view")
    inverse = view.find("filter[@kind='hide']/groupfilter")
    assert inverse.get("function") == "except"
    assert [child.get("function") for child in inverse] == ["level-members", "member"]
    assert inverse[1].get("member") == "true"
    assert not any((node.text or "").endswith(".[io:Picked:nk]") for node in view.findall("slices/column"))


@pytest.mark.parametrize("expressions,operators", [(["Place", "SUM(Value)", "SUM(Value)"], [" * ", " + "]), (["Place", "City"], [" / "]), (["Measure Names", "Multiple Values", "Multiple Values"], [" * ", " + "])])
def test_axis_shelf_crosses_dimensions_and_overlays_continuous_axes(expressions, operators):
    editor = synthetic()
    editor.configure_layered_chart("Map", axis_shelf="columns", columns=expressions, panes=[{"axis": expressions[-1], "detail": "Place"}])
    shelf = editor.root.find("worksheets/worksheet/table/cols").text
    for operator in operators:
        assert operator in shelf
    if expressions[0] == "Place" and len(expressions) == 3:
        assert shelf.index(" * ") < shelf.index(" + ")


def test_layered_sort_rejects_dimension_without_a_mark_or_shelf_binding():
    editor = synthetic()
    with pytest.raises(ValueError, match="bound to a shelf or mark encoding"):
        editor.configure_layered_chart("Map", rows=["SUM(Value)"], panes=[{"axis": "SUM(Value)", "detail": "Place"}], sort_descending="SUM(Value)", sort_field="City")
