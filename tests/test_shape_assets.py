"""Two synthetic PNG icons exercise native shape palette and asset contracts."""

import base64
import struct
import zlib

import pytest
from lxml import etree

from cwtwb import TWBEditor
from cwtwb.shape_assets import set_shape_palette


def icon(path, red):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes([0, red, 0, 0, 255])))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(data)
    return str(path)


def test_embeds_category_icons_and_replaces_palette_idempotently(tmp_path):
    e = TWBEditor("")
    csv = tmp_path / "data.csv"
    csv.write_text("Category,Value\nA,1\nB,2\n", encoding="utf-8")
    e.set_csv_connection(str(csv))
    images = {"A": icon(tmp_path / "a.png", 100), "B": icon(tmp_path / "b.png", 200)}
    set_shape_palette(e, "Category", images)
    set_shape_palette(e, "Category", images)
    shapes = e.root.findall("external/shapes/shape")
    assert len(shapes) == 2
    assert {n.get("name") for n in shapes} == {"Custom/a.png", "Custom/b.png"}
    for n in shapes:
        assert (
            base64.b64decode(n.text)
            == (tmp_path / n.get("name").split("/")[-1]).read_bytes()
        )
    encoding = e._datasource.xpath("style/style-rule/encoding[@attr='shape']")
    assert len(encoding) == 1 and encoding[0].get("field") == "[none:Category:nk]"
    assert encoding[0].xpath("map/bucket/text()") == ['"A"', '"B"']
    e.add_worksheet("Icons")
    e.configure_layered_chart(
        "Icons", rows=["Category"], panes=[{"mark_type": "Shape", "shape": "Category"}]
    )
    assert e.root.xpath("//worksheet[@name='Icons']/table/panes/pane/encodings/shape")


def test_rejects_bad_assets_palette_and_measures_without_mutation(tmp_path):
    e = TWBEditor("")
    e.add_calculated_field(
        "Category", "'A'", datatype="string", role="dimension", field_type="nominal"
    )
    good = icon(tmp_path / "good.png", 100)
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a PNG")
    before = etree.tostring(e.root)
    for field, paths, palette in [
        ("Category", {}, "Custom"),
        ("Category", {"A": str(bad)}, "Custom"),
        ("Category", {"A": good}, "../escape"),
        ("Sales", {"A": good}, "Custom"),
    ]:
        with pytest.raises(ValueError):
            set_shape_palette(e, field, paths, palette)
        assert etree.tostring(e.root) == before


def test_rejects_same_name_different_images(tmp_path):
    e = TWBEditor("")
    e.add_calculated_field(
        "Category", "'A'", datatype="string", role="dimension", field_type="nominal"
    )
    first = icon(tmp_path / "icon.png", 100)
    other = tmp_path / "other"
    other.mkdir()
    second = icon(other / "icon.png", 200)
    set_shape_palette(e, "Category", {"A": first})
    before = etree.tostring(e.root)
    with pytest.raises(ValueError, match="already uses"):
        set_shape_palette(e, "Category", {"A": second})
    assert etree.tostring(e.root) == before
