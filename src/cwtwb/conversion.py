"""Reversible native workbook documents, independent of TWBEditor sanitization.

This is a structural interchange format, not a simplified Tableau semantic DSL.
Unknown XML is represented exactly like known XML, never discarded. Binary
resources remain files. Conversion does not execute or validate Tableau queries.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import posixpath
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from lxml import etree

FORMAT = "cwtwb-native"
VERSION = 1
SUFFIXES = {".twb", ".twbx", ".yaml", ".yml", ".json"}


class WorkbookFormatError(ValueError):
    """An input document cannot be converted without ambiguity or content loss."""


class StrictLoader(yaml.SafeLoader):
    """Reject duplicate keys rather than silently accepting the last value."""


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkbookFormatError(f"Duplicate key: {key}")
        result[key] = value
    return result


def _mapping(loader, node):
    loader.flatten_mapping(node)
    return _pairs(
        (loader.construct_object(k), loader.construct_object(v)) for k, v in node.value
    )


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_document_file(path: str | Path) -> dict:
    source = Path(path)
    content = source.read_text(encoding="utf-8-sig")
    value = (
        json.loads(content, object_pairs_hook=_pairs)
        if source.suffix.lower() == ".json"
        else yaml.load(content, Loader=StrictLoader)
    )
    if not isinstance(value, dict):
        raise WorkbookFormatError("Document must be a mapping.")
    return value


def _keys(value: Any, allowed: set[str], required: set[str], where: str) -> dict:
    if not isinstance(value, dict):
        raise WorkbookFormatError(f"{where} must be a mapping.")
    if set(value) - allowed:
        raise WorkbookFormatError(f"Unknown keys in {where}: {set(value) - allowed}")
    if required - set(value):
        raise WorkbookFormatError(f"Missing keys in {where}: {required - set(value)}")
    return value


def _string(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise WorkbookFormatError(
            f"{where} must be a string (quote numeric and boolean XML values)."
        )
    return value


def _safe_name(name: str) -> str:
    _string(name, "Resource name")
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or ":" in name
        or path.is_absolute()
        or any(p in {"..", ".", ""} for p in name.split("/"))
    ):
        raise WorkbookFormatError(f"Unsafe package path: {name!r}")
    return name


def _encode_node(node, parent_ns=None) -> dict:
    if isinstance(node, etree._Comment):
        result = {"kind": "comment", "text": node.text or ""}
    elif isinstance(node, etree._ProcessingInstruction):
        result = {"kind": "instruction", "target": node.target, "text": node.text or ""}
    elif isinstance(node.tag, str):
        result = {"tag": node.tag}
        namespaces = {
            k or "": v for k, v in node.nsmap.items() if (parent_ns or {}).get(k) != v
        }
        if namespaces:
            result["namespaces"] = namespaces
        if node.attrib:
            result["attributes"] = dict(node.attrib)
        if node.text is not None:
            result["text"] = node.text
        if len(node):
            result["children"] = [_encode_node(child, node.nsmap) for child in node]
    else:
        raise WorkbookFormatError(
            "Entity nodes are not supported; resolve the DTD before converting."
        )
    if node.tail is not None:
        result["tail"] = node.tail
    return result


def _decode_node(value: dict, ancestors: set[int] | None = None):
    ancestors = set() if ancestors is None else ancestors
    if id(value) in ancestors:
        raise WorkbookFormatError("Recursive YAML aliases are not supported.")
    ancestors = ancestors | {id(value)}
    _keys(
        value,
        {
            "tag",
            "kind",
            "target",
            "namespaces",
            "attributes",
            "text",
            "tail",
            "children",
        },
        set(),
        "XML node",
    )
    kind = value.get("kind", "element")
    if kind == "element":
        _keys(
            value,
            {"tag", "namespaces", "attributes", "text", "tail", "children"},
            {"tag"},
            "element",
        )
        ns = value.get("namespaces", {})
        attrs = value.get("attributes", {})
        if not isinstance(ns, dict) or not isinstance(attrs, dict):
            raise WorkbookFormatError("namespaces and attributes must be mappings.")
        node = etree.Element(
            _string(value["tag"], "tag"),
            nsmap={
                (_string(k, "namespace prefix") or None): _string(v, "namespace URI")
                for k, v in ns.items()
            },
        )
        for key, val in attrs.items():
            node.set(_string(key, "attribute name"), _string(val, "attribute value"))
        children = value.get("children", [])
        if not isinstance(children, list):
            raise WorkbookFormatError("children must be a list.")
        for child in children:
            node.append(_decode_node(child, ancestors))
        if "text" in value:
            node.text = _string(value["text"], "text")
    elif kind == "comment":
        _keys(value, {"kind", "text", "tail"}, {"text"}, "comment")
        node = etree.Comment(_string(value["text"], "comment text"))
    elif kind == "instruction":
        _keys(
            value, {"kind", "target", "text", "tail"}, {"target", "text"}, "instruction"
        )
        node = etree.ProcessingInstruction(
            _string(value["target"], "target"), _string(value["text"], "text")
        )
    else:
        raise WorkbookFormatError(f"Unsupported node kind: {kind}")
    if "tail" in value:
        node.tail = _string(value["tail"], "tail")
    return node


def _parse_xml(data: bytes):
    parser = etree.XMLParser(
        remove_blank_text=False,
        strip_cdata=False,
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
    )
    tree = etree.parse(io.BytesIO(data), parser)
    if tree.docinfo.doctype:
        raise WorkbookFormatError(
            "DTD-bearing workbooks are unsupported; no output was written."
        )
    if tree.getroot().tag != "workbook":
        raise WorkbookFormatError("Expected a Tableau <workbook> root.")
    return tree


def _xml_document(tree) -> dict:
    root = tree.getroot()
    before = list(root.itersiblings(preceding=True))[::-1]
    after = list(root.itersiblings())
    return {
        "root": _encode_node(root),
        "before": [_encode_node(n) for n in before],
        "after": [_encode_node(n) for n in after],
    }


def _tree(document: dict):
    _keys(document, {"root", "before", "after"}, {"root"}, "document")
    root = _decode_node(document["root"])
    if root.tag != "workbook":
        raise WorkbookFormatError("Expected a workbook root.")
    for key in ("before", "after"):
        values = document.get(key, [])
        if not isinstance(values, list):
            raise WorkbookFormatError(f"{key} must be a list.")
        nodes = [_decode_node(v) for v in values]
        if any(
            not isinstance(n, (etree._Comment, etree._ProcessingInstruction))
            for n in nodes
        ):
            raise WorkbookFormatError(
                "Only comments/instructions are allowed outside the workbook root."
            )
        for node in nodes if key == "before" else reversed(nodes):
            (root.addprevious if key == "before" else root.addnext)(node)
    tree = root.getroottree()
    # Validate generated XML syntax without invoking sanitization or cloud services.
    _parse_xml(etree.tostring(tree, encoding="utf-8", xml_declaration=True))
    return tree


@dataclass
class WorkbookDocument:
    tree: Any
    workbook_entry: str
    resources: dict[str, bytes] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _resource_records(records, directory: Path) -> dict[str, bytes]:
    if not isinstance(records, list):
        raise WorkbookFormatError("resources must be a list.")
    result = {}
    for item in records:
        _keys(
            item,
            {"archive_path", "file", "sha256"},
            {"archive_path", "file", "sha256"},
            "resource",
        )
        name = _safe_name(item["archive_path"])
        if name.casefold() in {n.casefold() for n in result}:
            raise WorkbookFormatError(f"Duplicate resource: {name}")
        source = directory / _safe_name(item["file"])
        if not source.resolve().is_relative_to(directory.resolve()):
            raise WorkbookFormatError(f"Resource escapes document directory: {source}")
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise WorkbookFormatError(
                f"Resource hash mismatch: {source}. Update sha256 after an intentional edit."
            )
        result[name] = data
    return result


def _file_references(tree):
    for node in tree.getroot().iter():
        if not isinstance(node.tag, str):
            continue
        if node.tag == "connection" and node.get("class") in {
            "hyper",
            "textscan",
            "excel-direct",
        }:
            attr = "dbname" if node.get("class") == "hyper" else "filename"
            if node.get(attr):
                yield (
                    node,
                    attr,
                    posixpath.join(
                        node.get("directory", "").replace("\\", "/"),
                        node.get(attr).replace("\\", "/"),
                    ),
                )
        elif (
            node.tag == "zone" and node.get("type-v2") == "bitmap" and node.get("param")
        ):
            yield node, "param", node.get("param").replace("\\", "/")


def _collect_local_files(book: WorkbookDocument, directory: Path):
    for node, attr, reference in _file_references(book.tree):
        source = Path(reference)
        source = source if source.is_absolute() else directory / source
        if not source.is_file():
            book.warnings.append(f"External resource not found: {reference}")
            continue
        data = source.read_bytes()
        if (
            not Path(reference).is_absolute()
            and ".." not in PurePosixPath(reference).parts
        ):
            name = _safe_name(reference)
        else:
            name = f"Data/{hashlib.sha256(data).hexdigest()[:16]}/{source.name}"
            node.set(attr, name)
            if node.tag == "connection" and "directory" in node.attrib:
                node.set("directory", "")
            book.warnings.append(f"Localized external resource: {reference} -> {name}")
        if name in book.resources and book.resources[name] != data:
            raise WorkbookFormatError(f"Conflicting resource: {name}")
        book.resources[name] = data


def read_workbook(source: str | Path) -> WorkbookDocument:
    source = Path(source).resolve()
    suffix = source.suffix.lower()
    if suffix not in SUFFIXES:
        raise WorkbookFormatError(f"Unsupported input format: {suffix}")
    if suffix == ".twbx":
        with zipfile.ZipFile(source) as archive:
            names = [
                _safe_name(i.orig_filename)
                for i in archive.infolist()
                if not i.is_dir()
            ]
            if len({n.casefold() for n in names}) != len(names):
                raise WorkbookFormatError("Duplicate or case-colliding archive entries.")
            workbooks = [n for n in names if n.lower().endswith(".twb")]
            if len(workbooks) != 1:
                raise WorkbookFormatError(
                    "TWBX must contain exactly one TWB; selection would be ambiguous."
                )
            entry = workbooks[0]
            book = WorkbookDocument(
                _parse_xml(archive.read(entry)),
                entry,
                {n: archive.read(n) for n in names if n != entry},
            )
        for _, _, ref in _file_references(book.tree):
            if not _resolve_resource(book, ref):
                book.warnings.append(f"External resource not bundled: {ref}")
        return book
    if suffix == ".twb":
        book = WorkbookDocument(_parse_xml(source.read_bytes()), source.name)
        manifest = source.with_name(source.name + ".resources.json")
        if manifest.exists():
            payload = load_document_file(manifest)
            _keys(
                payload,
                {"format", "format_version", "resources", "workbook_sha256"},
                {"format", "format_version", "resources", "workbook_sha256"},
                "resource manifest",
            )
            if payload["format"] != FORMAT or payload["format_version"] != VERSION:
                raise WorkbookFormatError("Unsupported resource manifest version.")
            book.resources = _resource_records(payload["resources"], source.parent)
            # XML is deliberately editable; a changed hash is informational.
            if (
                payload["workbook_sha256"]
                != hashlib.sha256(source.read_bytes()).hexdigest()
            ):
                book.warnings.append(
                    "TWB edited since resource manifest was written; resources retained."
                )
        _collect_local_files(book, source.parent)
        return book
    payload = load_document_file(source)
    _keys(
        payload,
        {
            "format",
            "format_version",
            "representation",
            "workbook_entry",
            "document",
            "resources",
        },
        {
            "format",
            "format_version",
            "representation",
            "workbook_entry",
            "document",
            "resources",
        },
        "workbook definition",
    )
    if (
        payload["format"] != FORMAT
        or type(payload["format_version"]) is not int
        or payload["format_version"] != VERSION
    ):
        raise WorkbookFormatError("Unsupported workbook format/version.")
    if payload["representation"] != "native-xml-tree":
        raise WorkbookFormatError("Unsupported representation; expected native-xml-tree.")
    entry = _safe_name(payload["workbook_entry"])
    if not entry.lower().endswith(".twb"):
        raise WorkbookFormatError("workbook_entry must end in .twb.")
    book = WorkbookDocument(
        _tree(payload["document"]),
        entry,
        _resource_records(payload["resources"], source.parent),
    )
    if entry.casefold() in {n.casefold() for n in book.resources}:
        raise WorkbookFormatError("Resource conflicts with workbook entry.")
    for _, _, ref in _file_references(book.tree):
        if not _resolve_resource(book, ref):
            book.warnings.append(f"External resource not bundled: {ref}")
    return book


def _resolve_resource(book: WorkbookDocument, reference: str) -> str | None:
    if reference in book.resources:
        return reference
    candidate = posixpath.normpath(
        posixpath.join(posixpath.dirname(book.workbook_entry), reference)
    )
    return candidate if candidate in book.resources else None


def _asset_records(book, output):
    records, writes = [], {}
    for name, data in book.resources.items():
        digest = hashlib.sha256(data).hexdigest()
        relative = f"{output.name}.assets/{digest}/{PurePosixPath(name).name}"
        records.append({"archive_path": name, "file": relative, "sha256": digest})
        writes[output.parent / relative] = data
    return records, writes


def _commit(writes: dict[Path, bytes], output: Path, force: bool, protected: Path):
    staged = []
    try:
        for target, data in writes.items():
            if target.resolve() == protected:
                raise WorkbookFormatError("Input and output must be different files.")
            if not target.resolve().is_relative_to(output.parent.resolve()):
                raise WorkbookFormatError(f"Output escapes destination directory: {target}")
            if target.exists():
                if target == output and not force:
                    raise FileExistsError(f"Output exists: {target}. Use --force.")
                # Only the owned resource manifest can be replaced with --force.
                if (
                    target != output
                    and target.read_bytes() != data
                    and not (force and target.name == output.name + ".resources.json")
                ):
                    raise FileExistsError(
                        f"Conflicting resource already exists: {target}"
                    )
        for target, data in writes.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=target.parent, prefix=".cwtwb-", delete=False
            ) as handle:
                handle.write(data)
                staged.append((Path(handle.name), target))
        # Commit the primary document last so it never references unstaged assets.
        for temp, target in sorted(staged, key=lambda pair: pair[1] == output):
            os.replace(temp, target)
    finally:
        for temp, _ in staged:
            temp.unlink(missing_ok=True)


def convert_workbook(
    input_path: str | Path, output_path: str | Path, *, force: bool = False
) -> dict:
    """Convert TWB/TWBX/YAML/JSON without opening a stateful editor.

    Output suffix selects the format. YAML/JSON expose the native XML tree;
    resource files are copied alongside the document and hashes are checked.
    """
    source, output = Path(input_path).resolve(), Path(output_path).resolve()
    if output.suffix.lower() not in SUFFIXES:
        raise WorkbookFormatError(f"Unsupported output format: {output.suffix}")
    if source == output:
        raise WorkbookFormatError("Input and output must be different files.")
    if output.exists() and not force:
        raise FileExistsError(f"Output exists: {output}. Use --force.")
    book = read_workbook(source)
    suffix = output.suffix.lower()
    writes = {}
    if suffix in {".yaml", ".yml", ".json"}:
        records, writes = _asset_records(book, output)
        payload = {
            "format": FORMAT,
            "format_version": VERSION,
            "representation": "native-xml-tree",
            "workbook_entry": book.workbook_entry,
            "document": _xml_document(book.tree),
            "resources": records,
        }
        content = (
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            if suffix == ".json"
            else yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=110)
        )
        writes[output] = content.encode("utf-8")
    elif suffix == ".twbx":
        missing = [w for w in book.warnings if w.startswith("External resource")]
        if missing:
            raise WorkbookFormatError("Cannot produce a complete TWBX: " + "; ".join(missing))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                book.workbook_entry,
                etree.tostring(book.tree, encoding="utf-8", xml_declaration=True),
            )
            for name, data in book.resources.items():
                archive.writestr(name, data)
        writes[output] = buf.getvalue()
    else:
        records, writes = _asset_records(book, output)
        replacements = {item["archive_path"]: item["file"] for item in records}
        # Preserve all assets, including unknown extension files. Update exact
        # XML path references, not substrings in formulas or rich text.
        for node, attr, reference in list(_file_references(book.tree)):
            resource = _resolve_resource(book, reference)
            if resource:
                node.set(attr, replacements[resource])
                if node.tag == "connection" and "directory" in node.attrib:
                    node.set("directory", "")
        for node in book.tree.getroot().iter():
            if not isinstance(node.tag, str):
                continue
            for key, value in list(node.attrib.items()):
                if key not in {
                    "filename",
                    "dbname",
                    "param",
                    "file",
                    "path",
                    "src",
                    "href",
                }:
                    continue
                resource = _resolve_resource(book, value)
                if resource:
                    node.set(key, replacements[resource])
        data = etree.tostring(book.tree, encoding="utf-8", xml_declaration=True)
        writes[output] = data
        if records:
            records = [dict(item, archive_path=item["file"]) for item in records]
            manifest = {
                "format": FORMAT,
                "format_version": VERSION,
                "resources": records,
                "workbook_sha256": hashlib.sha256(data).hexdigest(),
            }
            writes[output.with_name(output.name + ".resources.json")] = (
                json.dumps(manifest, indent=2) + "\n"
            ).encode()
        elif output.with_name(output.name + ".resources.json").exists():
            raise WorkbookFormatError(
                "Destination has an existing resource manifest; choose a fresh output name."
            )
    _commit(writes, output, force, source)
    return {
        "input": str(source),
        "output": str(output),
        "representation": "native-xml-tree",
        "resources": len(book.resources),
        "warnings": book.warnings,
        "validation": "XML structure only; Tableau calculation/interaction validation was not run.",
    }
