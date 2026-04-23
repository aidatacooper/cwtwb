
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cwtwb.server import generate_layout_json
from cwtwb.twb_editor import TWBEditor

def test_new_layout_flow():
    project_root = Path(__file__).parent.parent
    template = str(project_root / 'templates' / 'twb' / 'superstore.twb')
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

if __name__ == '__main__':
    test_new_layout_flow()
