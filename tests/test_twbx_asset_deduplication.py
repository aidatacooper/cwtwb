from __future__ import annotations

from pathlib import Path
import zipfile

from cwtwb.twb_editor import TWBEditor


TWB_FILE = Path(__file__).parent.parent / "src" / "cwtwb" / "references" / "superstore.twb"


def test_roundtrip_does_not_duplicate_bundled_data(tmp_path, monkeypatch):
    data_file = tmp_path / "orders.csv"
    data_file.write_text("Order ID,Sales\nA,10\n", encoding="utf-8")

    source = tmp_path / "source.twbx"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(TWB_FILE, "source.twb")
        archive.write(data_file, data_file.name)

    editor = TWBEditor.open_existing(source)
    monkeypatch.setattr(editor, "_collect_external_data_files", lambda: [data_file])

    output = tmp_path / "roundtrip.twbx"
    editor.save(output, validate=False)

    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()

    assert names.count(data_file.name) == 1
    assert len(names) == len(set(names))
