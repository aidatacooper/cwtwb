"""Advanced chart example with optional Hyper connection switching.

This example stays in the advanced support tier. It demonstrates chart patterns
such as Scatterplot, Heatmap, Tree Map, and Bubble Chart without implying that
recipe-level charts are part of the default SDK promise.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cwtwb import TWBEditor


def _find_sample_hyper(project_root: Path) -> Path | None:
    bundle_dir = project_root / "templates" / "viz" / "Tableau Advent Calendar.twb 个文件"
    if not bundle_dir.exists():
        return None
    candidates = sorted(bundle_dir.rglob("*.hyper"))
    return candidates[0] if candidates else None


def main():
    project_root = Path(__file__).parent.parent
    template_path = project_root / "templates" / "twb" / "superstore.twb"
    output_path = project_root / "output" / "hyper_and_new_charts.twb"

    print("Initializing Editor...")
    editor = TWBEditor(str(template_path) if template_path.exists() else None)

    hyper_path = _find_sample_hyper(project_root)
    if hyper_path is not None:
        print(f"Switching to Hyper extract: {hyper_path.name}")
        editor.set_hyper_connection(
            str(hyper_path),
            table_name="Orders_4A2273C4362E41DEA7258D5051022F80",
        )
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
