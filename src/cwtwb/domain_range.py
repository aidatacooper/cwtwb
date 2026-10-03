"""Native worksheet full-range completion for discrete date fields."""

from lxml import etree


def configure_worksheet_domain_range(
    editor, worksheet_name: str, fields: list[str]
) -> str:
    """Replace native show-full-range fields; an empty list disables completion."""
    table = editor._find_worksheet(worksheet_name).find("table")
    if table is None or table.find("view") is None:
        raise ValueError(f"Worksheet '{worksheet_name}' has no configured view.")
    refs = []
    for field in fields:
        ci = editor.field_registry.parse_expression(field)
        source = editor._datasource.find(f"column[@name='{ci.column_local_name}']")
        if source is None or source.get("datatype") not in {"date", "datetime"}:
            raise ValueError("Full domain range requires date or datetime fields.")
        if ci.derivation != "None" or ci.ci_type != "ordinal":
            raise ValueError(
                "Full domain range requires discrete exact-date fields; use '[Field]'."
            )
        ds_name = editor._datasource.get("name", "")
        dependencies = table.find(
            f"view/datasource-dependencies[@datasource='{ds_name}']"
        )
        if (
            dependencies is None
            or dependencies.find(f"column-instance[@name='{ci.instance_name}']") is None
        ):
            raise ValueError(f"Field '{field}' must be present in the worksheet view.")
        ref = f"[{ds_name}].{ci.column_local_name}"
        if ref not in refs:
            refs.append(ref)
    existing = table.find("show-full-range")
    if existing is not None:
        table.remove(existing)
    if refs:
        full_range = etree.SubElement(table, "show-full-range")
        for ref in refs:
            etree.SubElement(full_range, "column").text = ref
    return f"Configured full domain range on '{worksheet_name}' for {len(refs)} fields"
