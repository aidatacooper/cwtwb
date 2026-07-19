"""Debug test: step-by-step generation to find which part breaks Tableau.

Test 1: bar chart only
Test 2: bar + pie (no dashboard)
Test 3: bar + pie + dashboard
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cwtwb.twb_editor import TWBEditor


def test_bar_only():
    """Test 1: just a bar chart."""
    project_root = Path(__file__).parent.parent
    editor = TWBEditor(project_root / "src" / "cwtwb" / "references" / "superstore.twb")
    editor.clear_worksheets()
    editor.add_worksheet("BarTest")
    editor.configure_chart(
        worksheet_name="BarTest",
        mark_type="Bar",
        rows=["Category"],
        columns=["SUM(Sales)"],
    )
    out = project_root / "output" / "debug_bar.twb"
    editor.save(out)
    print(f"[1] Bar only => {out}")


def test_bar_pie():
    """Test 2: bar + pie, no dashboard."""
    project_root = Path(__file__).parent.parent
    editor = TWBEditor(project_root / "src" / "cwtwb" / "references" / "superstore.twb")
    editor.clear_worksheets()
    editor.add_worksheet("BarTest")
    editor.configure_chart(
        worksheet_name="BarTest",
        mark_type="Bar",
        rows=["Category"],
        columns=["SUM(Sales)"],
    )
    editor.add_worksheet("PieTest")
    editor.configure_chart(
        worksheet_name="PieTest",
        mark_type="Pie",
        color="Segment",
        wedge_size="SUM(Sales)",
    )
    out = project_root / "output" / "debug_bar_pie.twb"
    editor.save(out)
    print(f"[2] Bar+Pie => {out}")


def test_with_calc():
    """Test 3: bar + calculated field."""
    project_root = Path(__file__).parent.parent
    editor = TWBEditor(project_root / "src" / "cwtwb" / "references" / "superstore.twb")
    editor.clear_worksheets()
    editor.add_calculated_field(
        "ProfitRatio",
        "SUM([Profit (Orders)])/SUM([Sales (Orders)])",
        "real",
    )
    editor.add_worksheet("BarTest")
    editor.configure_chart(
        worksheet_name="BarTest",
        mark_type="Bar",
        rows=["Category"],
        columns=["SUM(Sales)"],
    )
    out = project_root / "output" / "debug_calc.twb"
    editor.save(out)
    print(f"[3] Bar+Calc => {out}")


def test_with_dashboard():
    """Test 4: bar + pie + dashboard."""
    project_root = Path(__file__).parent.parent
    editor = TWBEditor(project_root / "src" / "cwtwb" / "references" / "superstore.twb")
    editor.clear_worksheets()
    editor.add_worksheet("BarTest")
    editor.configure_chart(
        worksheet_name="BarTest",
        mark_type="Bar",
        rows=["Category"],
        columns=["SUM(Sales)"],
    )
    editor.add_worksheet("PieTest")
    editor.configure_chart(
        worksheet_name="PieTest",
        mark_type="Pie",
        color="Segment",
        wedge_size="SUM(Sales)",
    )
    editor.add_dashboard(
        dashboard_name="TestDash",
        worksheet_names=["BarTest", "PieTest"],
        layout="horizontal",
    )
    out = project_root / "output" / "debug_dashboard.twb"
    editor.save(out)
    print(f"[4] Bar+Pie+Dashboard => {out}")


if __name__ == "__main__":
    test_bar_only()
    test_bar_pie()
    test_with_calc()
    test_with_dashboard()
    print("\nAll generated. Open each in Tableau to find which one breaks.")
