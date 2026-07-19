
import sys
from pathlib import Path
import yaml
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cwtwb.server import generate_layout_json, generate_layout_yaml
from cwtwb.twb_editor import TWBEditor

def test_new_layout_flow():
    project_root = Path(__file__).parent.parent
    template = str(project_root / 'src' / 'cwtwb' / 'references' / 'superstore.twb')
    json_out = str(project_root / 'output' / 'test_layout.json')
    twb_out = str(project_root / 'output' / 'test_layout.twb')
    
    # 1. Simulate AI calling the layout generator tool
    layout_tree = {
        'type': 'container',
        'direction': 'vertical',
        'layout_strategy': 'distribute-evenly',
        'children': [{'type': 'worksheet', 'name': 'Demo Chart'}]
    }
    ascii_art = '''
+------------+
| Demo Chart |
+------------+
'''
    print('Testing generate_layout_json...')
    res = generate_layout_json(json_out, layout_tree, ascii_art)
    print(res)
    
    # Check if JSON file was created
    assert Path(json_out).exists()
    
    # 2. Simulate the Editor logic
    print('\nTesting TWBEditor logic with output json...')
    editor = TWBEditor(template)
    editor.clear_worksheets()
    editor.add_worksheet('Demo Chart')
    
    # Test passing the json file path 
    editor.add_dashboard('Test Dash', worksheet_names=['Demo Chart'], layout=json_out)
    editor.save(twb_out)
    
    assert Path(twb_out).exists()
    print(f'Great success! Tested end to end. Output saved to: {twb_out}')


def test_generate_layout_json_rejects_non_dsl_schema(tmp_path):
    json_out = tmp_path / "invalid_layout.json"
    invalid_layout_tree = {
        "type": "dashboard",
        "children": [
            {
                "type": "zone",
                "position": {"x": 0, "y": 0, "w": 100, "h": 50},
                "children": [{"type": "worksheet", "name": "Demo Chart"}],
            }
        ],
    }

    result = generate_layout_json(str(json_out), invalid_layout_tree, "")

    assert "Failed to generate layout JSON" in result
    assert "not a supported add_dashboard layout DSL" in result
    assert not json_out.exists()


def test_generate_layout_json_writes_yaml_when_requested(tmp_path):
    yaml_out = tmp_path / "valid_layout.yaml"
    layout_tree = {
        "type": "container",
        "direction": "horizontal",
        "children": [
            {"type": "worksheet", "name": "Summary", "fixed_size": 240},
            {"type": "worksheet", "name": "Detail", "weight": 1},
        ],
    }

    result = generate_layout_json(str(yaml_out), layout_tree, "Summary | Detail")

    assert "Layout file successfully written to:" in result
    assert yaml_out.exists()

    loaded = yaml.safe_load(yaml_out.read_text(encoding="utf-8"))
    assert loaded["layout_schema"]["type"] == "container"
    assert loaded["layout_schema"]["direction"] == "horizontal"
    assert loaded["_ascii_layout_preview"] == ["Summary | Detail"]


def test_generate_layout_yaml_writes_yaml_and_normalizes_suffix(tmp_path):
    yaml_out = tmp_path / "valid_layout"
    layout_tree = {
        "type": "container",
        "direction": "vertical",
        "children": [
            {"type": "worksheet", "name": "Top", "fixed_size": 100},
            {"type": "worksheet", "name": "Bottom", "weight": 1},
        ],
    }

    result = generate_layout_yaml(str(yaml_out), layout_tree, "Top / Bottom")

    normalized_path = yaml_out.with_suffix(".yaml")
    assert "Layout file successfully written to:" in result
    assert normalized_path.exists()

    loaded = yaml.safe_load(normalized_path.read_text(encoding="utf-8"))
    assert loaded["layout_schema"]["direction"] == "vertical"
    assert loaded["_ascii_layout_preview"] == ["Top / Bottom"]

if __name__ == '__main__':
    test_new_layout_flow()
