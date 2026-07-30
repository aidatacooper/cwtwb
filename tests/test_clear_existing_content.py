from pathlib import Path

from lxml import etree

from cwtwb.twb_editor import TWBEditor


TWB_FILE = Path(__file__).parent.parent / "src" / "cwtwb" / "references" / "superstore.twb"


def test_clear_worksheets_removes_stale_dashboard_actions():
    editor = TWBEditor.open_existing(TWB_FILE)
    actions = etree.Element("actions")
    action = etree.SubElement(actions, "action", caption="Old Action")
    etree.SubElement(
        action,
        "source",
        dashboard="Old Dashboard",
        worksheet="Old Worksheet",
        type="sheet",
    )
    editor.root.find("worksheets").addprevious(actions)

    editor.clear_worksheets()

    assert editor.root.find("actions") is None
