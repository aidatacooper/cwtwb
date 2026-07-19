"""Tests for .twbx (Tableau Packaged Workbook) support.

Covers:
- Opening a .twbx file and parsing its embedded .twb
- Saving as .twbx (round-trip: keeps extracts + images)
- Saving a .twbx source as a plain .twb
- Opening a plain .twb, saving as .twbx (no bundled files)
- Modifying worksheets inside a .twbx, then re-saving
- create_workbook / open_workbook MCP tools with .twbx paths

Run manually:
    pytest tests/test_twbx_support.py -v
"""

from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.twb_editor import TWBEditor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TWBX_FILE = (
    Path(__file__).parent.parent
    / "tests"
    / "fixtures"
    / "Customer Support Case Demo #VOTD.twbx"
)
TWB_FILE = (
    Path(__file__).parent.parent / "src" / "cwtwb" / "references" / "superstore.twb"
)

pytestmark = pytest.mark.skipif(
    not TWBX_FILE.exists(),
    reason=f"Reference .twbx not found: {TWBX_FILE}",
)


@pytest.fixture
def twbx_editor():
    """TWBEditor opened from the reference .twbx (no content cleared)."""
    return TWBEditor.open_existing(TWBX_FILE)


# ---------------------------------------------------------------------------
# 1. Open
# ---------------------------------------------------------------------------

class TestTwbxOpen:
    def test_opens_without_error(self, twbx_editor):
        assert twbx_editor is not None

    def test_twbx_source_recorded(self, twbx_editor):
        assert twbx_editor._twbx_source == TWBX_FILE

    def test_inner_twb_name_detected(self, twbx_editor):
        assert twbx_editor._twbx_twb_name is not None
        assert twbx_editor._twbx_twb_name.endswith(".twb")

    def test_fields_parseable(self, twbx_editor):
        fields_text = twbx_editor.list_fields()
        assert "Dimensions" in fields_text or "Measures" in fields_text

    def test_worksheets_preserved(self, twbx_editor):
        worksheets = twbx_editor.list_worksheets()
        assert len(worksheets) > 0, "Expected existing worksheets to be loaded"

    def test_xml_root_is_workbook(self, twbx_editor):
        assert twbx_editor.root.tag == "workbook"


# ---------------------------------------------------------------------------
# 2. Save as .twbx  (round-trip)
# ---------------------------------------------------------------------------

class TestSaveAsTwbx:
    def test_produces_zip_file(self, twbx_editor, tmp_path):
        out = tmp_path / "out.twbx"
        twbx_editor.save(out)
        assert zipfile.is_zipfile(out)

    def test_inner_twb_entry_present(self, twbx_editor, tmp_path):
        out = tmp_path / "out.twbx"
        twbx_editor.save(out)
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        assert any(n.endswith(".twb") for n in names)

    def test_inner_twb_name_matches_original(self, twbx_editor, tmp_path):
        out = tmp_path / "out.twbx"
        twbx_editor.save(out)
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        assert twbx_editor._twbx_twb_name in names

    def test_extracts_bundled(self, twbx_editor, tmp_path):
        """Data extracts from the source .twbx must be carried over."""
        out = tmp_path / "out.twbx"
        twbx_editor.save(out)
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        assert any(n.endswith(".hyper") or n.endswith(".tde") for n in names), (
            f"Expected a .hyper/.tde extract in the output .twbx, got: {names}"
        )

    def test_images_bundled(self, twbx_editor, tmp_path):
        """Image assets from the source .twbx must be carried over."""
        out = tmp_path / "out.twbx"
        twbx_editor.save(out)
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        assert any(
            n.lower().endswith((".svg", ".png", ".jpg", ".jpeg"))
            for n in names
        ), f"Expected an image asset in the output .twbx, got: {names}"

    def test_inner_twb_is_valid_xml(self, twbx_editor, tmp_path):
        out = tmp_path / "out.twbx"
        twbx_editor.save(out)
        with zipfile.ZipFile(out) as zf:
            twb_bytes = zf.read(twbx_editor._twbx_twb_name)
        root = ET.fromstring(twb_bytes)
        assert root.tag == "workbook"

    def test_file_size_reasonable(self, twbx_editor, tmp_path):
        out = tmp_path / "out.twbx"
        twbx_editor.save(out)
        # Must be at least as large as the .hyper extract alone
        assert out.stat().st_size > 100_000


# ---------------------------------------------------------------------------
# 3. Save .twbx source as plain .twb
# ---------------------------------------------------------------------------

class TestSaveAsTwb:
    def test_produces_plain_xml_file(self, twbx_editor, tmp_path):
        out = tmp_path / "out.twb"
        twbx_editor.save(out)
        # Must not be a ZIP
        assert not zipfile.is_zipfile(out)

    def test_plain_twb_is_valid_xml(self, twbx_editor, tmp_path):
        out = tmp_path / "out.twb"
        twbx_editor.save(out)
        root = ET.parse(out).getroot()
        assert root.tag == "workbook"

    def test_plain_twb_has_content(self, twbx_editor, tmp_path):
        out = tmp_path / "out.twb"
        twbx_editor.save(out)
        assert out.stat().st_size > 10_000


# ---------------------------------------------------------------------------
# 4. Plain .twb → save as .twbx (no bundled files)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not TWB_FILE.exists(), reason=f"superstore.twb not found: {TWB_FILE}")
class TestTwbSourceSaveAsTwbx:
    def test_plain_to_twbx_is_zip(self, tmp_path):
        editor = TWBEditor(TWB_FILE)
        out = tmp_path / "converted.twbx"
        editor.save(out)
        assert zipfile.is_zipfile(out)

    def test_plain_to_twbx_inner_name_from_output(self, tmp_path):
        editor = TWBEditor(TWB_FILE)
        out = tmp_path / "converted.twbx"
        editor.save(out)
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        # When no source .twbx, inner name is derived from output filename
        assert "converted.twb" in names

    def test_plain_to_twbx_bundles_external_data(self, tmp_path):
        """External data files are bundled when converting .twb to .twbx."""
        editor = TWBEditor(TWB_FILE)
        out = tmp_path / "converted.twbx"
        editor.save(out)
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        # TWB entry should be present
        assert "converted.twb" in names
        # External data file (Excel) should also be bundled
        assert any(n.endswith((".xls", ".xlsx", ".csv", ".hyper")) for n in names), \
            f"Expected external data file in TWBX, got: {names}"


# ---------------------------------------------------------------------------
# 5. Modify worksheets inside a .twbx, then re-save
# ---------------------------------------------------------------------------

class TestTwbxModifyAndResave:
    def test_add_calculated_field_survives_twbx_roundtrip(self, twbx_editor, tmp_path):
        twbx_editor.add_calculated_field("Test Calc TWBX", "1 + 1")
        out = tmp_path / "modified.twbx"
        twbx_editor.save(out)

        # Re-open the saved .twbx and check the field is there
        reloaded = TWBEditor.open_existing(out)
        fields_text = reloaded.list_fields()
        assert "Test Calc TWBX" in fields_text

    def test_add_worksheet_survives_twbx_roundtrip(self, tmp_path):
        editor = TWBEditor.open_existing(TWBX_FILE)
        editor.add_worksheet("My New Sheet")
        out = tmp_path / "with_sheet.twbx"
        editor.save(out)

        reloaded = TWBEditor.open_existing(out)
        assert "My New Sheet" in reloaded.list_worksheets()


# ---------------------------------------------------------------------------
# 6. MCP tool integration
# ---------------------------------------------------------------------------

class TestMcpToolsTwbx:
    def test_open_workbook_accepts_twbx(self):
        from cwtwb.mcp.tools_workbook import open_workbook
        result = open_workbook(str(TWBX_FILE))
        assert "Workbook opened" in result

    def test_create_workbook_accepts_twbx(self):
        from cwtwb.mcp.tools_workbook import create_workbook
        result = create_workbook(str(TWBX_FILE))
        assert "Workbook created" in result

    def test_save_workbook_as_twbx(self, tmp_path):
        from cwtwb.mcp.tools_workbook import open_workbook, save_workbook
        open_workbook(str(TWBX_FILE))
        out = str(tmp_path / "mcp_out.twbx")
        result = save_workbook(out)
        assert "Saved" in result
        assert zipfile.is_zipfile(out)

    def test_save_workbook_as_twb_from_twbx(self, tmp_path):
        from cwtwb.mcp.tools_workbook import open_workbook, save_workbook
        open_workbook(str(TWBX_FILE))
        out = str(tmp_path / "mcp_out.twb")
        result = save_workbook(out)
        assert "Saved" in result
        assert not zipfile.is_zipfile(out)
