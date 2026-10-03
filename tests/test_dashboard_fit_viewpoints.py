import pytest
from cwtwb import TWBEditor


@pytest.mark.parametrize(
    "fit,zoom",
    [("width", "fit-width"), ("height", "fit-height"), ("entire", "entire-view")],
)
def test_dashboard_fit_binds_native_worksheet_viewpoint(fit, zoom):
    editor = TWBEditor("")
    editor.add_worksheet("Summary")
    editor.configure_chart("Summary", mark_type="Text", label="SUM(Sales)")
    editor.add_dashboard(
        "Dashboard", layout={"type": "worksheet", "name": "Summary", "fit": fit}
    )
    viewpoint = editor.root.find(
        "windows/window[@name='Dashboard']/viewpoints/viewpoint[@name='Summary']/zoom"
    )
    assert viewpoint.get("type") == zoom
