"""Tooltip filters declare their calculated members on both worksheets."""

from lxml import etree

from cwtwb import TWBEditor


def test_compound_tooltip_target_has_recursive_calculated_dependencies(tmp_path):
    editor = TWBEditor("")
    for name, formula in [
        ("Region", "'West'"),
        ("Code", "LEFT([Region], 1)"),
        ("Member", "UPPER([Code])"),
    ]:
        editor.add_calculated_field(
            name, formula, datatype="string", role="dimension", field_type="nominal"
        )
    editor.add_calculated_field("Value", "1.0")
    for name in ("Overview", "Detail"):
        editor.add_worksheet(name)
        editor.configure_chart(name, mark_type="Text", label="SUM(Value)")
    specification = [
        {
            "sheet": {
                "name": "Detail",
                "filter_fields": ["Region", "Member"],
                "filter_context": True,
            }
        }
    ]
    editor.configure_custom_tooltip("Overview", specification)
    editor.configure_custom_tooltip("Overview", specification)
    for name in ("Overview", "Detail"):
        dependencies = editor.root.find(
            f"worksheets/worksheet[@name='{name}']/table/view/datasource-dependencies"
        )
        for field in ("Region", "Code", "Member"):
            local = editor.field_registry._find_field(field).local_name
            assert len(dependencies.findall(f"column[@name='{local}']")) == 1
        for field in ("Region", "Member"):
            ci = editor.field_registry.parse_expression(field)
            assert (
                len(
                    dependencies.findall(f"column-instance[@name='{ci.instance_name}']")
                )
                == 1
            )
        children = list(dependencies)
        assert max(children.index(c) for c in dependencies.findall("column")) < min(
            children.index(c) for c in dependencies.findall("column-instance")
        )
    output = tmp_path / "compound.twb"
    editor.save(str(output))
    target = etree.parse(str(output)).find(
        "worksheets/worksheet[@name='Detail']/table/view"
    )
    assert len(target.findall("filter")) == 1
    assert target.find("filter").get("context") == "true"
