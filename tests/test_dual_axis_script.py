import os
from pathlib import Path
from cwtwb.twb_editor import TWBEditor

def main():
    template_path = Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"
    editor = TWBEditor(template_path)
    
    editor.add_worksheet("Lollipop Horizontal")
    editor.configure_dual_axis(
        "Lollipop Horizontal",
        columns=["SUM(Sales)", "SUM(Sales)"],
        rows=["Category"],
        dual_axis_shelf="columns",
        mark_type_1="Bar",
        mark_type_2="Circle",
        color_1="SUM(Sales)",
        color_2="SUM(Sales)",
    )
    
    os.makedirs("output", exist_ok=True)
    editor.save("output/test_lollipop.twb")
    print("Generated output/test_lollipop.twb")

if __name__ == "__main__":
    main()
