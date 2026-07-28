"""Reproduce Donna Coles case C: null-safe averages with Tableau densification."""

from pathlib import Path

from cwtwb.twb_editor import TWBEditor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = PROJECT_ROOT / "src" / "cwtwb" / "references"
OUTPUT_DIR = (
    PROJECT_ROOT
    / "backup"
    / "experiments"
    / "donnacoles-pilot-v1"
    / "showcase"
)
OUTPUT_FILE = OUTPUT_DIR / "null-safe-average-with-domain-completion.twbx"


def build_showcase() -> Path:
    editor = TWBEditor(REFERENCE_DIR / "superstore.twb")
    editor.add_hierarchy(
        "Location Hierarchy",
        ["Region", "State/Province", "City"],
    )
    editor.add_calculated_field(
        "#Orders",
        "ZN(COUNTD([Order ID]))",
        datatype="integer",
        internal_name="[Calculation_NullSafeOrders]",
    )
    editor.add_worksheet("Null-safe Average")
    editor.configure_chart(
        "Null-safe Average",
        mark_type="Square",
        columns=["WEEKDAY(Order Date)"],
        rows=["Category", "Sub-Category"],
        color="#Orders",
        label="#Orders",
    )
    editor.enable_domain_completion("Null-safe Average")
    editor.configure_subtotals(
        "Null-safe Average",
        measure_fields=["#Orders"],
        aggregation="Average",
        subtotal_fields=["Sub-Category"],
        label="Avg.",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    editor.save(OUTPUT_FILE)
    return OUTPUT_FILE


if __name__ == "__main__":
    print(build_showcase())
