import pytest
from pathlib import Path
from lxml import etree
import shutil

from cwtwb.twb_editor import TWBEditor


@pytest.fixture
def tmp_superstore(tmp_path):
    src = Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"
    dst = tmp_path / "superstore_tmp.twb"
    shutil.copy(src, dst)
    return dst


def test_declarative_json_dashboard(tmp_superstore, tmp_path):
    """Test generating a dashboard with extremely complex declarative nesting."""
    editor = TWBEditor(tmp_superstore)
    editor.clear_worksheets()
    
    # Generate mock worksheets
    charts = ["D_Sales", "D_Profit", "D_Discount", "D_Quantity", "Main Chart", "Line Trend"]
    for c in charts:
        editor.add_worksheet(c)
        editor.configure_chart(c, mark_type="Bar", rows=["Ship Mode"], columns=["SUM(Sales)"])
        
    # Extremely complex layout matching (similar to c.2 replica)
    layout = {
        "type": "container",
        "direction": "vertical",
        "children": [
            {
                "type": "container",
                "direction": "horizontal",
                "fixed_size": 100,
                "style": {"bg_color": "#ff0000"},
                "children": [
                    {"type": "text", "text": "MY AWESOME DASHBOARD", "font_size": "24", "bold": True, "fixed_size": 300},
                    {"type": "text", "text": "Logo Area", "weight": 1}
                ]
            },
            {
                "type": "container",
                "direction": "horizontal",
                "weight": 1,
                "children": [
                    {
                        "type": "container",
                        "direction": "vertical",
                        "fixed_size": 250,
                        "layout_strategy": "distribute-evenly",
                        "children": [
                            {"type": "worksheet", "name": "D_Sales"},
                            {"type": "worksheet", "name": "D_Profit"},
                            {"type": "worksheet", "name": "D_Discount"},
                            {"type": "worksheet", "name": "D_Quantity"},
                        ]
                    },
                    {
                        "type": "container",
                        "direction": "vertical",
                        "weight": 2,
                        "children": [
                            {"type": "worksheet", "name": "Main Chart", "weight": 2},
                            {"type": "worksheet", "name": "Line Trend", "weight": 1}
                        ]
                    }
                ]
            }
        ]
    }
    
    # 3. Add Dashboard
    msg = editor.add_dashboard(
        "Complex JSON Dash", 
        width=1400, 
        height=900, 
        layout=layout,
        worksheet_names=charts # Pass for validation
    )
    
    assert "Created dashboard 'Complex JSON Dash'" in msg
    
    # Check tree directly for generated XML structures
    db = editor.root.find(".//dashboards/dashboard[@name='Complex JSON Dash']")
    assert db is not None
    
    # Check that sizing-mode="fixed" is applied
    size_el = db.find("size")
    assert size_el is not None
    assert size_el.get("sizing-mode") == "fixed"
    
    zones = db.find("zones")
    assert zones is not None
    
    # The wrapper's child zone should be vertically oriented
    root_zone = zones.find("zone")
    assert root_zone.get("param") == "vert"
    
    # It should have exactly two horizontal children inside
    child_zones = list(root_zone.findall("zone"))
    assert len(child_zones) == 2
    assert child_zones[0].get("param") == "horz"
    assert child_zones[1].get("param") == "horz"
    
    # Check height absolute proportion logic (Top header is fixed 100px of 900px, 11% -> 11111 height)
    h_top = int(child_zones[0].get("h"))
    h_remaining = int(child_zones[1].get("h"))
    assert h_top > 10000 and h_top < 12000 # ~11%
    assert h_remaining > 88000 and h_remaining < 89000 # ~89%
    
    # Optional: Save and print location for manual visual sanity check
    out_path = tmp_path / "test_nested_dashboard.twb"
    editor.save(out_path)
    print(f"\\nSaved declarative Layout TWB to {out_path}")


def test_fallback_basic_layouts(tmp_superstore):
    """Test that classic simple string layout still generates correct JSON internally."""
    editor = TWBEditor(tmp_superstore)
    editor.clear_worksheets()
    
    editor.add_worksheet("S1")
    editor.add_worksheet("S2")
    
    # Test built in horizontal
    editor.add_dashboard("Dash Horz", layout="horizontal", worksheet_names=["S1", "S2"])
    db_h = editor.root.find(".//dashboards/dashboard[@name='Dash Horz']")
    rz_h = db_h.find("zones/zone")
    assert rz_h.get("param") == "horz"
    assert len(list(rz_h.findall("zone"))) == 2
    
    # Test built in vertical
    editor.add_dashboard("Dash Vert", layout="vertical", worksheet_names=["S1", "S2"])
    db_v = editor.root.find(".//dashboards/dashboard[@name='Dash Vert']")
    rz_v = db_v.find("zones/zone")
    assert rz_v.get("param") == "vert"
    assert len(list(rz_v.findall("zone"))) == 2


def test_legacy_nested_layout_aliases_render_worksheets(tmp_superstore):
    """Legacy type=horizontal/vertical object layouts should not render empty zones."""
    editor = TWBEditor(tmp_superstore)
    editor.clear_worksheets()

    sheets = [
        "Sidebar",
        "Header",
        "KPI_Impressions",
        "KPI_Clicks",
        "KPI_ConversionRate",
        "KPI_CPC",
        "KPI_Profit",
        "KPI_ROI",
        "Chart_TargetAudience",
        "Chart_ActivityType",
        "Chart_Visibility",
        "Chart_WeekdayWeekNo",
        "Chart_RankedChannel",
        "Chart_Channel",
        "Chart_TrafficSource",
    ]
    for sheet in sheets:
        editor.add_worksheet(sheet)
        editor.configure_chart(sheet, mark_type="Bar", rows=["Ship Mode"], columns=["SUM(Sales)"])

    layout = {
        "type": "horizontal",
        "name": "Dashboard_Root",
        "children": [
            {"name": "Sidebar", "type": "worksheet", "weight": 0.06},
            {
                "type": "vertical",
                "name": "Main_Content_Area",
                "weight": 0.94,
                "children": [
                    {"name": "Header", "type": "worksheet", "weight": 0.08},
                    {
                        "type": "vertical",
                        "name": "KPI_Grid",
                        "weight": 0.32,
                        "children": [
                            {
                                "type": "horizontal",
                                "name": "KPI_Row_1",
                                "children": [
                                    {"name": "KPI_Impressions", "type": "worksheet", "weight": 0.333},
                                    {"name": "KPI_Clicks", "type": "worksheet", "weight": 0.333},
                                    {"name": "KPI_ConversionRate", "type": "worksheet", "weight": 0.334},
                                ],
                            },
                            {
                                "type": "horizontal",
                                "name": "KPI_Row_2",
                                "children": [
                                    {"name": "KPI_CPC", "type": "worksheet", "weight": 0.333},
                                    {"name": "KPI_Profit", "type": "worksheet", "weight": 0.333},
                                    {"name": "KPI_ROI", "type": "worksheet", "weight": 0.334},
                                ],
                            },
                        ],
                    },
                    {
                        "type": "horizontal",
                        "name": "Middle_Analysis_Row",
                        "weight": 0.25,
                        "children": [
                            {"name": "Chart_TargetAudience", "type": "worksheet", "weight": 0.25},
                            {"name": "Chart_ActivityType", "type": "worksheet", "weight": 0.25},
                            {"name": "Chart_Visibility", "type": "worksheet", "weight": 0.25},
                            {"name": "Chart_WeekdayWeekNo", "type": "worksheet", "weight": 0.25},
                        ],
                    },
                    {
                        "type": "horizontal",
                        "name": "Bottom_Detail_Row",
                        "weight": 0.35,
                        "children": [
                            {"name": "Chart_RankedChannel", "type": "worksheet", "weight": 0.6},
                            {"name": "Chart_Channel", "type": "worksheet", "weight": 0.2},
                            {"name": "Chart_TrafficSource", "type": "worksheet", "weight": 0.2},
                        ],
                    },
                ],
            },
        ],
    }

    editor.add_dashboard(
        "Legacy Nested Dashboard",
        width=1400,
        height=1000,
        layout=layout,
        worksheet_names=sheets,
    )

    listed = {dashboard["name"]: dashboard["worksheets"] for dashboard in editor.list_dashboards()}
    assert listed["Legacy Nested Dashboard"] == sheets

    db = editor.root.find(".//dashboards/dashboard[@name='Legacy Nested Dashboard']")
    root_zone = db.find("zones/zone")
    assert root_zone.get("type-v2") == "layout-flow"
    assert root_zone.get("param") == "horz"
    assert len(root_zone.findall(".//zone[@name]")) == len(sheets)
    assert root_zone.findall(".//zone[@type-v2='layout-flow'][@param='vert']")
    assert root_zone.findall(".//zone[@type-v2='layout-flow'][@param='horz']")


def test_unknown_layout_node_type_raises(tmp_superstore):
    editor = TWBEditor(tmp_superstore)
    editor.clear_worksheets()
    editor.add_worksheet("Sheet A")

    with pytest.raises(ValueError, match="Unsupported dashboard layout node type 'mystery'"):
        editor.add_dashboard(
            "Invalid Layout",
            worksheet_names=["Sheet A"],
            layout={
                "type": "mystery",
                "children": [{"type": "worksheet", "name": "Sheet A"}],
            },
        )
