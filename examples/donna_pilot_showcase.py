"""Generate a packaged Tableau example for the Donna Coles capability pilot."""

from pathlib import Path

from cwtwb.twb_editor import TWBEditor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = PROJECT_ROOT / "src" / "cwtwb" / "references"
OUTPUT_DIR = PROJECT_ROOT / "backup" / "experiments" / "donnacoles-pilot-v1" / "showcase"
OUTPUT_FILE = OUTPUT_DIR / "dynamic-moving-average-and-parameter-action.twbx"


def build_showcase() -> Path:
    editor = TWBEditor(REFERENCE_DIR / "superstore.twb")

    editor.add_parameter(
        name="Moving Average Window",
        datatype="integer",
        default_value="3",
        domain_type="range",
        min_value="1",
        max_value="12",
        granularity="1",
    )
    editor.add_parameter(
        name="Selected Category",
        datatype="string",
        default_value="All",
        domain_type="list",
        allowed_values=["All", "Furniture", "Office Supplies", "Technology"],
    )
    editor.add_calculated_field(
        field_name="Selected Category Sales",
        formula=(
            'IF [Selected Category] = "All" '
            "OR [Category] = [Selected Category] THEN [Sales] END"
        ),
        datatype="real",
    )
    editor.add_calculated_field(
        field_name="Dynamic Moving Average",
        formula=(
            "WINDOW_AVG(SUM([Selected Category Sales]), "
            "-1 * ([Moving Average Window] - 1), 0)"
        ),
        datatype="real",
        table_calc={"ordering_type": "Rows"},
        default_format="$#,##0",
    )

    editor.add_worksheet("Category Selector")
    editor.configure_chart(
        "Category Selector",
        mark_type="Bar",
        rows=["Category"],
        columns=["SUM(Sales)"],
        color="Category",
        label="Category",
    )

    editor.add_worksheet("Dynamic Moving Average")
    editor.configure_chart(
        "Dynamic Moving Average",
        mark_type="Line",
        columns=["MONTH(Order Date)"],
        rows=["Dynamic Moving Average"],
    )

    layout = {
        "type": "container",
        "direction": "horizontal",
        "children": [
            {
                "type": "container",
                "direction": "vertical",
                "fixed_size": 330,
                "children": [
                    {"type": "worksheet", "name": "Category Selector"},
                    {
                        "type": "paramctrl",
                        "parameter": "Moving Average Window",
                        "mode": "slider",
                        "fixed_size": 80,
                    },
                ],
            },
            {
                "type": "worksheet",
                "name": "Dynamic Moving Average",
                "weight": 2,
            },
        ],
    }
    editor.add_dashboard(
        "Interactive Moving Average",
        width=1200,
        height=720,
        layout=layout,
        worksheet_names=["Category Selector", "Dynamic Moving Average"],
    )
    editor.add_dashboard_action(
        dashboard_name="Interactive Moving Average",
        action_type="parameter",
        source_sheet="Category Selector",
        source_field="Category",
        target_parameter="Selected Category",
        aggregation="attr",
        clear_behavior="set-value",
        clear_value="s:LROOT:All",
        caption="Select Category",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    editor.save(OUTPUT_FILE)
    return OUTPUT_FILE


if __name__ == "__main__":
    print(build_showcase())
