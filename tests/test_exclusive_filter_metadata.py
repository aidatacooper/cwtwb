"""Exclusion mode must survive native filter serialization and REST overrides."""

import pytest

from cwtwb import TWBEditor

USER_NS = "{http://www.tableausoftware.com/xml/user}"


@pytest.mark.parametrize("values", [["A"], ["A", "B"]])
@pytest.mark.parametrize("context", [False, True])
def test_exclusive_filter_owns_selection_mode(values, context, tmp_path):
    editor = TWBEditor("")
    editor.add_calculated_field("Category", "'A'", datatype="string", role="dimension")
    editor.add_calculated_field("Amount", "1.0", datatype="real", role="measure")
    editor.add_worksheet("Bars")
    editor.configure_layered_chart(
        "Bars",
        rows=["SUM(Amount)"],
        panes=[{"axis": "SUM(Amount)", "detail": "Category"}],
        filters=[{
            "column": "Category", "values": values, "exclude": True,
            "context": context, "ui_domain": "database",
        }],
    )
    path = tmp_path / "exclusive.twb"
    editor.save(path, validate=False)
    loaded = TWBEditor.open_existing(path)
    node = loaded.root.find("worksheets/worksheet/table/view/filter")
    inverse = node.find("groupfilter")
    assert inverse.get("function") == "except"
    assert inverse.get(f"{USER_NS}ui-enumeration") == "exclusive"
    assert inverse.get(f"{USER_NS}ui-domain") == "database"
    assert inverse.get(f"{USER_NS}ui-marker") == "enumerate"
    assert inverse[0].get("function") == "level-members"
    operand = inverse[1]
    assert operand.get("function") == ("member" if len(values) == 1 else "union")
    assert not any(key.startswith(USER_NS) for key in operand.attrib)
    members = [operand] if len(values) == 1 else list(operand)
    assert [member.get("member") for member in members] == [f'"{v}"' for v in values]


def test_inclusive_filter_retains_inclusive_selection_mode():
    editor = TWBEditor("")
    editor.add_calculated_field("Category", "'A'", datatype="string", role="dimension")
    editor.add_calculated_field("Amount", "1.0", datatype="real", role="measure")
    editor.add_worksheet("Bars")
    editor.configure_layered_chart(
        "Bars", rows=["SUM(Amount)"],
        panes=[{"axis": "SUM(Amount)", "detail": "Category"}],
        filters=[{"column": "Category", "values": ["A"]}],
    )
    group = editor.root.find("worksheets/worksheet/table/view/filter/groupfilter")
    assert group.get("function") == "member"
    assert group.get(f"{USER_NS}ui-enumeration") == "inclusive"
