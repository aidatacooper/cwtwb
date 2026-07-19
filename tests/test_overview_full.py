"""Full integration test: replicate Overview Dashboard page 1.

Uses MCP server functions to reproduce the first page of Overview.twb,
including:
  - 4 worksheets: SaleMap, SalesbyProduct, SalesbySegment, Total Sales (KPI)
  - Parameters: Target Profit, Churn Rate, New Business Growth
  - Calculated fields: Profit Ratio, Order Profitable?, etc.
  - Measure Names/Values for Total Sales KPI card
  - Dashboard with filter zones, color legend zone, complex layout
  - Dashboard actions
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cwtwb.server import (
    create_workbook,
    add_parameter,
    add_calculated_field,
    add_worksheet,
    configure_chart,
    add_dashboard,
    add_dashboard_action,
    save_workbook,
)


def main():
    project_root = Path(__file__).parent.parent
    template = str(project_root / "src" / "cwtwb" / "references" / "superstore.twb")
    output = str(project_root / "output" / "overview_full.twb")

    # ============================================================
    # 1. Create workbook
    # ============================================================
    print("=== 1. Create workbook ===")
    result = create_workbook(template, "Overview Full")
    print(result[:200], "...\n")

    # ============================================================
    # 2. Add parameters
    # ============================================================
    print("=== 2. Add parameters ===")
    print(add_parameter(
        name="Target Profit", datatype="real", default_value="10000.0",
        domain_type="range", min_value="-30000.0", max_value="100000.0", granularity="10000.0",
    ))
    print(add_parameter(
        name="Churn Rate", datatype="real", default_value="0.168",
        domain_type="range", min_value="0.0", max_value="1.0", granularity="0.05",
    ))
    print(add_parameter(
        name="New Business Growth", datatype="real", default_value="0.599",
        domain_type="range", min_value="0.0", max_value="1.0", granularity="0.05",
    ))
    print()

    # ============================================================
    # 3. Add calculated fields
    # ============================================================
    print("=== 3. Add calculated fields ===")
    print(add_calculated_field("Profit Ratio", "SUM([Profit])/SUM([Sales])", "real"))
    print(add_calculated_field(
        "Order Profitable?",
        "IF SUM([Profit]) > [Target Profit] THEN 'Profitable' ELSE 'Unprofitable' END",
        "string",
    ))
    print(add_calculated_field("Sales estimate", "[Sales]*(1-[Churn Rate])*(1+[New Business Growth])", "real"))
    print(add_calculated_field("Profit per Customer", "SUM([Profit])/COUNTD([Customer Name])", "real"))
    print(add_calculated_field("Profit per Order", "SUM([Profit])/COUNTD([Order ID])", "real"))
    print(add_calculated_field("Units estimate", "ROUND([Quantity]*(1-[Churn Rate])*(1+[New Business Growth]),0)", "real"))
    print()

    # ============================================================
    # 4. Add worksheets
    # ============================================================
    print("=== 4. Add worksheets ===")
    for name in ["SaleMap", "SalesbyProduct", "SalesbySegment", "Total Sales"]:
        add_worksheet(name)
        print(f"Added: {name}")
    print()

    # ============================================================
    # 5. Configure charts
    # ============================================================
    print("=== 5. Configure charts ===")

    # SaleMap — Filled Map
    print(configure_chart(
        worksheet_name="SaleMap",
        mark_type="Map",
        geographic_field="State/Province",
        color="Order Profitable?",
        size="SUM(Sales)",
        tooltip="SUM(Profit)",
        filters=[
            {"column": "Order Date", "type": "quantitative", "min": "#2022-01-03#", "max": "#2025-12-30#"},
            {"column": "Region"},
            {"column": "State/Province"},
            {"column": "Profit Ratio"}
        ]
    ))

    # SalesbyProduct — Area chart
    print(configure_chart(
        worksheet_name="SalesbyProduct",
        mark_type="Area",
        columns=["MONTH(Order Date)"],
        rows=["SUM(Sales)"],
        color="Order Profitable?",
        detail="Category",
        tooltip="SUM(Profit)",
    ))

    # SalesbySegment — Area chart
    print(configure_chart(
        worksheet_name="SalesbySegment",
        mark_type="Area",
        columns=["MONTH(Order Date)"],
        rows=["SUM(Sales)"],
        color="Order Profitable?",
        detail="Segment",
        tooltip="SUM(Profit)",
    ))

    # Total Sales — KPI card with Measure Names/Values
    print(configure_chart(
        worksheet_name="Total Sales",
        mark_type="Text",
        measure_values=[
            "SUM(Sales)",
            "SUM(Profit)",
            "Profit Ratio",
            "SUM(Quantity)",
            "AVG(Discount)",
            "Profit per Customer",
            "Profit per Order",
        ],
    ))
    print()

    # ============================================================
    # 6. Add dashboard with complex layout
    # ============================================================
    print("=== 6. Add dashboard ===")
    layout = {
        "type": "container",
        "direction": "vertical",
        "children": [
            # Top KPI bar
            {"type": "worksheet", "name": "Total Sales", "height_percent": 15},
            # Main content area
            {
                "type": "container",
                "direction": "horizontal",
                "children": [
                    # Left sidebar: filters + color legend
                    {
                        "type": "container",
                        "direction": "vertical",
                        "width_percent": 18,
                        "children": [
                            {"type": "filter", "worksheet": "SaleMap", "field": "Order Date"},
                            {"type": "filter", "worksheet": "SaleMap", "field": "Region", "mode": "dropdown"},
                            {"type": "filter", "worksheet": "SaleMap", "field": "State/Province", "mode": "checkdropdown"},
                            {"type": "filter", "worksheet": "SaleMap", "field": "Profit Ratio"},
                            {"type": "color", "worksheet": "SaleMap", "field": "Order Profitable?"},
                        ],
                    },
                    # Right main area
                    {
                        "type": "container",
                        "direction": "vertical",
                        "width_percent": 82,
                        "children": [
                            {"type": "worksheet", "name": "SaleMap", "height_percent": 55},
                            {
                                "type": "container",
                                "direction": "horizontal",
                                "height_percent": 45,
                                "children": [
                                    {"type": "worksheet", "name": "SalesbySegment", "width_percent": 50},
                                    {"type": "worksheet", "name": "SalesbyProduct", "width_percent": 50},
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
    }

    print(add_dashboard(
        dashboard_name="Overview",
        worksheet_names=["Total Sales", "SaleMap", "SalesbySegment", "SalesbyProduct"],
        width=936, height=650,
        layout=layout,
    ))
    print()

    # ============================================================
    # 7. Add dashboard actions
    # ============================================================
    print("=== 7. Add dashboard actions ===")
    print(add_dashboard_action(
        dashboard_name="Overview", action_type="filter",
        source_sheet="SaleMap", target_sheet="SalesbyProduct",
        fields=["State/Province"], event_type="on-select",
    ))
    print(add_dashboard_action(
        dashboard_name="Overview", action_type="highlight",
        source_sheet="SaleMap", target_sheet="SalesbySegment",
        fields=["State/Province"], event_type="on-select",
    ))
    print()

    # ============================================================
    # 8. Save
    # ============================================================
    print("=== 8. Save ===")
    print(save_workbook(output))
    print()

    print("INTEGRATION TEST PASSED!")
    print(f"Open {output} in Tableau Desktop to verify.")


if __name__ == "__main__":
    main()
