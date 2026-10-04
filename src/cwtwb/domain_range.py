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
        # Tableau completes the source date domain even when a discrete
        # datepart, rather than an exact date, is used on the shelves.
        # Numeric aggregations of a date are not domain-completion evidence.
        date_derivations = {
            "None",
            "Attribute",
            "Year",
            "Quarter",
            "Month",
            "Week",
            "Weekday",
            "Day",
            "MY",
            "Day-Trunc",
            "Month-Trunc",
            "Quarter-Trunc",
            "Year-Trunc",
        }
        used_date = dependencies is not None and any(
            instance.get("column") == ci.column_local_name
            and instance.get("derivation") in date_derivations
            for instance in dependencies.findall("column-instance")
        )
        if not used_date:
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
