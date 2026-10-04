"""Extend continuous date domains without adding fabricated source rows."""

from lxml import etree

PERIOD_TYPES = {"year", "quarter", "month", "week", "day", "hour", "minute", "second"}


def configure_worksheet_time_series(
    editor,
    worksheet_name: str,
    field: str,
    periods: int,
    period_type: str = "year",
    calculations_on_densified_marks: bool = True,
) -> str:
    """Extend a date field's displayed domain and configure densified-mark calculations.

    ``field`` accepts a public date field or date expression already on a continuous
    worksheet shelf, such as ``YEARTRUNC(Order Date)``. Tableau's extension binds
    the base date column, while the shelf retains its existing date instance.
    Repeated calls update the same field; other extended date fields are preserved.
    """
    if isinstance(periods, bool) or not isinstance(periods, int) or periods < 1:
        raise ValueError("periods must be a positive integer")
    if not isinstance(period_type, str) or period_type not in PERIOD_TYPES:
        raise ValueError("Unsupported time-series period_type")
    if not isinstance(calculations_on_densified_marks, bool):
        raise ValueError("calculations_on_densified_marks must be boolean")  # noqa: TRY004
    if not isinstance(field, str) or not field.strip():
        raise ValueError("field must be a nonempty date expression")
    worksheet = editor._find_worksheet(worksheet_name)
    instance = editor.field_registry.parse_expression(field)
    info = editor.field_registry._find_field(instance.column_local_name)
    if info.datatype not in {"date", "datetime"}:
        raise ValueError("Time-series extension requires a date or datetime field")
    table = worksheet.find("table")
    view = table.find("view") if table is not None else None
    if view is None:
        raise ValueError("Worksheet has no configured view")
    datasource_name = editor._datasource.get("name")
    dependencies = next(
        (
            d
            for d in view.findall("datasource-dependencies")
            if d.get("datasource") == datasource_name
        ),
        None,
    )
    shelves = " ".join(table.findtext(tag, "") for tag in ("rows", "cols"))
    continuous = (
        []
        if dependencies is None
        else [
            c
            for c in dependencies.findall("column-instance")
            if c.get("column") == info.local_name
            and c.get("type") == "quantitative"
            and editor.field_registry.resolve_full_reference(c.get("name")) in shelves
        ]
    )
    if not continuous:
        raise ValueError(
            "Time-series extension requires the date field on a continuous shelf"
        )
    # Validate all inputs and bindings before modifying the document.
    manifest = editor.root.find("document-format-change-manifest")
    if manifest is None:
        manifest = etree.Element("document-format-change-manifest")
        editor.root.insert(0, manifest)
    for feature in ("ExtendTimeSeries", "AllowCalculationsForDensifiedMarks"):
        if manifest.find(feature) is None:
            etree.SubElement(manifest, feature)
    extension = table.find("extend-time-series")
    if extension is None:
        extension = etree.Element("extend-time-series")
        # Native schema places extension before later formatting/forecast options.
        successor = next(
            (
                child
                for child in table
                if child.tag
                in {
                    "consider-zeros-empty",
                    "percentages",
                    "mark-labels",
                    "annotations",
                    "page-trail",
                    "trail-overrides",
                    "tooltip-style",
                    "forecast-options",
                }
            ),
            None,
        )
        if successor is None:
            table.append(extension)
        else:
            successor.addprevious(extension)
    reference = editor.field_registry.resolve_full_reference(info.local_name)
    column = next(
        (
            c
            for c in extension.findall("extended-column")
            if c.get("column") == reference
        ),
        None,
    )
    if column is None:
        column = etree.SubElement(extension, "extended-column", column=reference)
    column.set("num-periods", str(periods))
    column.set("period-type", period_type)
    calculations = view.find("calcs-on-densified-marks")
    if calculations is None:
        calculations = etree.SubElement(view, "calcs-on-densified-marks")
    calculations.set("value", str(calculations_on_densified_marks).lower())
    return f"Extended '{worksheet_name}' date domain by {periods} {period_type} periods"
