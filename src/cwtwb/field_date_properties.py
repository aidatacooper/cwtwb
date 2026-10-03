"""Native date field properties shared by existing and future worksheets."""

from lxml import etree


def set_field_fiscal_year_start(editor, field: str, month: int) -> str:
    """Set a date field's fiscal start month and update existing dependency copies."""
    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("Fiscal start month must be an integer from 1 to 12")
    info = editor.field_registry._find_field(field)
    if info.datatype not in {"date", "datetime"}:
        raise ValueError("Fiscal year properties require a date or datetime field")
    datasource = editor._datasource
    column = next(
        (c for c in datasource.findall("column") if c.get("name") == info.local_name),
        None,
    )
    if column is None:
        column = etree.Element(
            "column",
            name=info.local_name,
            datatype=info.datatype,
            role=info.role,
            type=info.field_type,
        )
        anchor = next(
            (
                datasource.find(tag)
                for tag in (
                    "column-instance",
                    "group",
                    "layout",
                    "style",
                    "semantic-values",
                    "date-options",
                    "object-graph",
                )
                if datasource.find(tag) is not None
            ),
            None,
        )
        if anchor is None:
            datasource.append(column)
        else:
            anchor.addprevious(column)
    column.set("fiscal-year-start", str(month))
    name = datasource.get("name")
    for dependencies in editor.root.findall(".//datasource-dependencies"):
        if dependencies.get("datasource") == name:
            for existing in dependencies.findall("column"):
                if existing.get("name") == info.local_name:
                    existing.set("fiscal-year-start", str(month))
    return f"Set fiscal year start for '{field}' to month {month}"
