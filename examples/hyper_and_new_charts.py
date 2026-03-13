"""Advanced chart example with optional Hyper connection switching.

This example stays in the advanced support tier. It demonstrates chart patterns
such as Scatterplot, Heatmap, Tree Map, and Bubble Chart without implying that
recipe-level charts are part of the default SDK promise.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tableauhyperapi import Connection, HyperException, HyperProcess, Telemetry

from cwtwb import TWBEditor
from cwtwb.config import REFERENCES_DIR


HYPER_FILE = REFERENCES_DIR / "Sample - EU Superstore.hyper"
PREFERRED_ORDERS_TABLE = "Orders_4A2273C4362E41DEA7258D5051022F80"


def _resolve_orders_table_name(hyper_path: Path) -> str:
    """Resolve the physical Orders table name from a Hyper extract."""
    try:
        with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
            with Connection(endpoint=hyper.endpoint, database=str(hyper_path)) as connection:
                for schema_name in connection.catalog.get_schema_names():
                    for table_name in connection.catalog.get_table_names(schema_name):
                        if str(table_name.schema_name.name) != '"Extract"':
                            continue
                        raw_table_name = str(table_name.name).strip('"')
                        if raw_table_name.startswith("Orders_"):
                            return raw_table_name
    except HyperException:
        return PREFERRED_ORDERS_TABLE
    raise ValueError(f"Could not find an Orders_* table in Hyper extract: {hyper_path}")


def main():
    output_path = Path(__file__).parent.parent / "output" / "hyper_and_new_charts.twb"

    print("Initializing Editor...")
    editor = TWBEditor("")  # uses built-in default template from references/

    if HYPER_FILE.exists():
        table_name = _resolve_orders_table_name(HYPER_FILE)
        print(f"Switching to Hyper extract: {HYPER_FILE.name}")
        editor.set_hyper_connection(str(HYPER_FILE), table_name=table_name)
    else:
        print("Hyper extract not found. Continuing with the template datasource.")

    print("Generating Scatterplot...")
    editor.add_worksheet("Scatterplot Example")
    editor.configure_chart(
        "Scatterplot Example",
        mark_type="Scatterplot",
        columns=["SUM(Sales)"],
        rows=["SUM(Profit)"],
        color="Category",
        detail="Customer Name",
    )

    print("Generating Heatmap...")
    editor.add_worksheet("Heatmap Example")
    editor.configure_chart(
        "Heatmap Example",
        mark_type="Heatmap",
        columns=["Sub-Category"],
        rows=["Region"],
        color="SUM(Sales)",
        label="SUM(Sales)",
    )

    print("Generating Tree Map...")
    editor.add_worksheet("Tree Map Example")
    editor.configure_chart(
        "Tree Map Example",
        mark_type="Tree Map",
        size="SUM(Sales)",
        color="SUM(Profit)",
        label="Sub-Category",
    )

    print("Generating Bubble Chart...")
    editor.add_worksheet("Bubble Chart Example")
    editor.configure_chart(
        "Bubble Chart Example",
        mark_type="Bubble Chart",
        size="SUM(Sales)",
        color="Category",
        label="Category",
    )

    print("Creating Dashboard...")
    editor.add_dashboard(
        dashboard_name="New Advanced Charts Overview",
        worksheet_names=[
            "Scatterplot Example",
            "Heatmap Example",
            "Tree Map Example",
            "Bubble Chart Example",
        ],
        layout="grid-2x2",
    )

    output_path.parent.mkdir(exist_ok=True)
    editor.save(str(output_path))
    print(f"Successfully generated visualization to: {output_path}")
    print("You can open this .twb file with Tableau Desktop to verify the results.")


if __name__ == "__main__":
    main()
