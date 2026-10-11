from hashlib import sha256
from zipfile import ZipFile, ZipInfo

import pytest
from lxml import etree

from cwtwb.cli import main
from cwtwb.conversion import convert_workbook, load_document_file, read_workbook

XML = b"""<?xml version="1.0" encoding="utf-8"?>
<?source test?><!--before--><workbook xmlns:u="urn:test" version="18.1">
  <datasources><datasource name="ds"><column name="[Metric]" caption="Metric"><calculation formula="SUM([Sales])"/></column></datasource></datasources>
  <worksheets><worksheet name="Chart"><table><rows>[Metric]</rows></table></worksheet></worksheets>
  <dashboards><dashboard name="Main"><zones><zone id="1" x="20"/></zones></dashboard></dashboards>
  <!--keep--><u:unknown u:flag="yes">mixed<b/>tail</u:unknown>
  <thumbnails><thumbnail>abc</thumbnail></thumbnails>
</workbook><!--after--><?end done?>"""


def canonical(path):
    return etree.tostring(read_workbook(path).tree, method="c14n", with_comments=True)


@pytest.mark.parametrize("suffix", [".yaml", ".yml", ".json"])
def test_native_roundtrip_and_edits(tmp_path, suffix):
    source = tmp_path / "source.twb"
    source.write_bytes(XML)
    definition = tmp_path / ("book" + suffix)
    convert_workbook(source, definition)
    output = tmp_path / "rebuilt.twb"
    assert main(["run", str(definition), "--out", str(output)]) == 0
    assert canonical(source) == canonical(output)
    assert source.read_bytes() == XML
    # Edit actual human-readable formula and geometry values in either format.
    content = definition.read_text(encoding="utf-8").replace(
        "SUM([Sales])", "AVG([Sales])"
    )
    content = content.replace("'20'", "'40'").replace('"20"', '"40"')
    definition.write_text(content, encoding="utf-8")
    edited = tmp_path / "edited.twb"
    convert_workbook(definition, edited)
    root = etree.parse(str(edited)).getroot()
    assert root.find(".//calculation").get("formula") == "AVG([Sales])"
    assert root.find(".//zone").get("x") == "40"
    assert root.find("thumbnails") is not None
    root.find(".//calculation").set("formula", "SUM([Sales])")
    root.find(".//zone").set("x", "20")
    assert etree.tostring(root.getroottree(), method="c14n") == canonical(source)


@pytest.fixture
def package(tmp_path):
    source = tmp_path / "source.twbx"
    xml = XML.replace(
        b'<datasource name="ds">',
        b'<datasource name="ds"><connection class="hyper" dbname="data.hyper"/>',
    )
    with ZipFile(source, "w") as archive:
        archive.writestr("book.twb", xml)
        archive.writestr("data.hyper", b"fixture-data")
        archive.writestr("Extensions/unknown.bin", b"unknown-resource")
    return source


def test_package_yaml_json_package(tmp_path, package):
    first = tmp_path / "one" / "book.yaml"
    second = tmp_path / "two" / "book.json"
    output = tmp_path / "rebuilt.twbx"
    convert_workbook(package, first)
    convert_workbook(first, second)
    # The second definition must be independent of the original and first output.
    package.unlink()
    first.unlink()
    convert_workbook(second, output)
    with ZipFile(output) as archive:
        assert archive.read("data.hyper") == b"fixture-data"
        assert archive.read("Extensions/unknown.bin") == b"unknown-resource"
    assert canonical(second) == canonical(output)


def test_package_twb_package_keeps_unreferenced_assets(tmp_path, package):
    output = tmp_path / "unpacked" / "book.twb"
    convert_workbook(package, output)
    package.unlink()
    rebuilt = tmp_path / "rebuilt.twbx"
    convert_workbook(output, rebuilt)
    book = read_workbook(rebuilt)
    assert set(book.resources.values()) == {b"fixture-data", b"unknown-resource"}
    ref = book.tree.find(".//connection").get("dbname")
    assert ref in book.resources


def test_resource_tampering_and_existing_outputs(tmp_path, package):
    definition = tmp_path / "book.yaml"
    convert_workbook(package, definition)
    with pytest.raises(FileExistsError):
        convert_workbook(package, definition)
    record = load_document_file(definition)["resources"][0]
    (tmp_path / record["file"]).write_bytes(b"changed")
    output = tmp_path / "broken.twbx"
    with pytest.raises(ValueError, match="hash mismatch"):
        convert_workbook(definition, output)
    assert not output.exists()


@pytest.mark.parametrize("name", ["../escape.bin", "/absolute.bin", "C:/file", "a\\b"])
def test_unsafe_archive_paths(tmp_path, name):
    source = tmp_path / "bad.twbx"
    with ZipFile(source, "w") as archive:
        archive.writestr("book.twb", XML)
        info = ZipInfo("entry")
        info.filename = name  # Prevent Windows ZipInfo from normalizing backslashes.
        archive.writestr(info, b"bad")
    with pytest.raises(ValueError, match="Unsafe"):
        convert_workbook(source, tmp_path / "bad.yaml")
    assert not (tmp_path / "bad.yaml").exists()


def test_strict_document_validation(tmp_path):
    source = tmp_path / "source.twb"
    source.write_bytes(XML)
    definition = tmp_path / "book.yaml"
    convert_workbook(source, definition)
    original = definition.read_text(encoding="utf-8")
    for content, message in [
        (original + "format_version: 1\n", "Duplicate"),
        (original.replace("format_version: 1", "format_version: 99"), "version"),
        (original + "typo: true\n", "Unknown"),
        (original.replace("x: '20'", "x: 20"), "string"),
    ]:
        definition.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            convert_workbook(definition, tmp_path / "bad.twb")
    definition.write_text(original, encoding="utf-8")
    assert main(["run", str(definition), "--dry-run"]) == 0


def test_missing_external_resource_fails_packaging(tmp_path):
    source = tmp_path / "missing.twb"
    source.write_text(
        '<workbook><connection class="hyper" dbname="missing.hyper"/></workbook>'
    )
    result = convert_workbook(source, tmp_path / "book.yaml")
    assert result["warnings"]
    with pytest.raises(ValueError, match="complete TWBX"):
        convert_workbook(source, tmp_path / "book.twbx")


def test_absolute_external_file_is_localized(tmp_path):
    data = tmp_path / "source.csv"
    data.write_bytes(b"x\n1\n")
    source = tmp_path / "source.twb"
    root = etree.Element("workbook")
    etree.SubElement(root, "connection", {"class": "textscan", "filename": str(data)})
    source.write_bytes(etree.tostring(root))
    output = tmp_path / "book.twbx"
    convert_workbook(source, output)
    book = read_workbook(output)
    ref = book.tree.find("connection").get("filename")
    assert sha256(book.resources[ref]).digest() == sha256(data.read_bytes()).digest()


def test_dtd_rejected_and_input_not_overwritten(tmp_path):
    source = tmp_path / "source.twb"
    source.write_text('<!DOCTYPE workbook [<!ENTITY x "x">]><workbook>&x;</workbook>')
    with pytest.raises(ValueError, match="DTD"):
        convert_workbook(source, tmp_path / "bad.yaml")
    with pytest.raises(ValueError, match="different"):
        convert_workbook(source, source, force=True)


@pytest.mark.parametrize("input_suffix", [".twb", ".twbx", ".yaml", ".json"])
@pytest.mark.parametrize("output_suffix", [".twb", ".twbx", ".yaml", ".json"])
def test_all_format_pairs(tmp_path, package, input_suffix, output_suffix):
    source = tmp_path / ("input" + input_suffix)
    convert_workbook(package, source)
    output = tmp_path / ("output" + output_suffix)
    assert main(["convert", str(source), "--out", str(output)]) == 0
    result = read_workbook(output)
    assert set(result.resources.values()) == {b"fixture-data", b"unknown-resource"}
    assert result.tree.find("thumbnails") is not None
    assert result.tree.find(".//calculation").get("formula") == "SUM([Sales])"


def test_stateless_mcp_conversion(tmp_path):
    from cwtwb import TWBEditor
    from cwtwb.mcp.app import get_editor, set_editor
    from cwtwb.mcp_server import convert_workbook as convert_tool

    editor = TWBEditor("")
    set_editor(editor)
    source = tmp_path / "source.twb"
    source.write_bytes(XML)
    result = convert_tool(str(source), str(tmp_path / "workbook.yaml"))
    assert result["representation"] == "native-xml-tree"
    assert get_editor() is editor


def test_nested_workbook_resource_paths(tmp_path):
    source = tmp_path / "nested.twbx"
    xml = XML.replace(
        b'<datasource name="ds">',
        b'<datasource name="ds"><connection class="hyper" dbname="data.hyper"/>',
    )
    with ZipFile(source, "w") as archive:
        archive.writestr("nested/book.twb", xml)
        archive.writestr("nested/data.hyper", b"data")
    twb = tmp_path / "unpacked.twb"
    convert_workbook(source, twb)
    result = read_workbook(twb)
    assert result.tree.find(".//connection").get("dbname") in result.resources


def test_duplicate_json_and_recursive_yaml_rejected(tmp_path):
    definition = tmp_path / "bad.json"
    definition.write_text('{"format": "a", "format": "b"}')
    with pytest.raises(ValueError, match="Duplicate"):
        read_workbook(definition)
    definition = tmp_path / "bad.yaml"
    definition.write_text("""format: cwtwb-native
format_version: 1
representation: native-xml-tree
workbook_entry: book.twb
resources: []
document:
  root: &root
    tag: workbook
    children: [*root]
""")
    with pytest.raises(ValueError, match="Recursive"):
        read_workbook(definition)
