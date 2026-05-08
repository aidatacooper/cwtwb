"""Field registry and reference name mapping.

Maps user-friendly field names (e.g. Sales) to TWB internal references
(e.g. [Sales (Orders)]), and parses field expressions
(e.g. SUM(Sales) -> [sum:Sales (Orders):qk]).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional


# ---------- Aggregation / Date-part -> TWB derivation mapping ----------

_DERIVATION_MAP: dict[str, str] = {
    "SUM": "Sum",
    "AVG": "Avg",
    "COUNT": "Count",
    "COUNTD": "CountD",
    "MIN": "Min",
    "MAX": "Max",
    "MEDIAN": "Median",
    "ATTR": "Attr",
    "YEAR": "Year",
    "QUARTER": "Quarter",
    "MONTH": "Month",
    "DAY": "Day",
    "WEEK": "Week",
    "WEEKDAY": "Weekday",
    "MY": "MY",
    "DAYTRUNC": "Day-Trunc",
}

# Derivation abbreviations (used for column-instance name generation)
_DERIVATION_ABBR: dict[str, str] = {
    "None": "none",
    "User": "usr",
    "Sum": "sum",
    "Avg": "avg",
    "Count": "cnt",
    "CountD": "cntd",
    "Min": "min",
    "Max": "max",
    "Median": "med",
    "Attr": "attr",
    "Year": "yr",
    "Quarter": "qr",
    "Month": "mn",
    "Day": "day",
    "Week": "wk",
    "Weekday": "wd",
    "MY": "my",
    "Day-Trunc": "tdy",
}

# Temporal derivations (result type is ordinal key)
_TEMPORAL_DERIVATIONS = {"Year", "Quarter", "Month", "Day", "Week", "Weekday", "MY"}

# Expression regex: FUNC(field) or bare field
_EXPR_RE = re.compile(
    r"^([A-Z]+)\((.+)\)$"  # FUNC(field)
)

logger = logging.getLogger(__name__)


@dataclass
class FieldInfo:
    """Complete metadata for a single field."""

    display_name: str       # User-visible name, e.g. Sales
    local_name: str         # TWB internal name, e.g. [Sales (Orders)]
    datatype: str           # real / string / integer / date / boolean
    role: str               # dimension / measure
    field_type: str         # nominal / quantitative / ordinal
    is_calculated: bool = False


@dataclass
class ColumnInstance:
    """All attributes of a column-instance, used for XML generation."""

    column_local_name: str   # e.g. [Sales (Orders)]
    derivation: str          # e.g. Sum / None
    instance_name: str       # e.g. [sum:Sales (Orders):qk]
    pivot: str = "key"
    ci_type: str = ""        # nominal / quantitative / ordinal


class FieldRegistry:
    """Field name -> TWB internal reference mapping table."""

    def __init__(self, datasource_name: str, allow_unknown_fields: bool = False):
        """Initialize registry state for one datasource namespace."""
        self.datasource_name = datasource_name
        self.allow_unknown_fields = allow_unknown_fields
        self._fields: dict[str, FieldInfo] = {}

    def set_unknown_field_policy(self, *, allow_unknown_fields: bool) -> None:
        """Control whether unknown fields can be auto-registered."""

        self.allow_unknown_fields = allow_unknown_fields

    # ---- Registration ----

    def register(
        self,
        display_name: str,
        local_name: str,
        datatype: str,
        role: str,
        field_type: str,
        is_calculated: bool = False,
    ) -> None:
        """Register one field and its Tableau metadata in the lookup table."""
        self._fields[display_name] = FieldInfo(
            display_name=display_name,
            local_name=local_name,
            datatype=datatype,
            role=role,
            field_type=field_type,
            is_calculated=is_calculated,
        )

    def unregister(self, display_name: str) -> None:
        """Remove a field mapping if it exists."""
        self._fields.pop(display_name, None)

    def remove(self, display_name: str) -> None:
        """Alias of unregister() kept for API readability."""
        self._fields.pop(display_name, None)

    # ---- Queries ----

    def get(self, display_name: str) -> Optional[FieldInfo]:
        """Return field metadata by display name, or None when unknown."""
        return self._fields.get(display_name)

    def all_fields(self) -> list[FieldInfo]:
        """Return all registered fields in insertion order."""
        return list(self._fields.values())

    def dimensions(self) -> list[FieldInfo]:
        """Return only fields declared as dimensions."""
        return [f for f in self._fields.values() if f.role == "dimension"]

    def measures(self) -> list[FieldInfo]:
        """Return only fields declared as measures."""
        return [f for f in self._fields.values() if f.role == "measure"]

    # ---- Expression parsing ----

    def parse_expression(self, expr: str) -> ColumnInstance:
        """Parse a user expression into a ColumnInstance.

        Supported formats:
          - "SUM(Sales)"        -> derivation=Sum, field=Sales
          - "Category"          -> derivation=None, field=Category
          - "YEAR(Order Date)"  -> derivation=Year, field=Order Date
        """
        m = _EXPR_RE.match(expr.strip())
        if m:
            func_name = m.group(1).upper()
            field_name = m.group(2).strip()
            derivation = _DERIVATION_MAP.get(func_name)
            if derivation is None:
                raise ValueError(
                    f"Unsupported aggregation function: {func_name}. "
                    f"Supported: {', '.join(_DERIVATION_MAP.keys())}"
                )
        else:
            field_name = expr.strip()
            derivation = "None"

        # Look up the field
        fi = self._find_field(field_name)

        # Calculated measures use derivation="User" (abbr: usr).
        # Calculated dimensions (boolean, nominal) keep derivation="None" so they
        # are treated as plain dimension values rather than user-aggregated expressions.
        if fi.is_calculated and fi.role == "measure" and derivation == "None":
            derivation = "User"

        # Determine type suffix
        if derivation in ("None", "User"):
            ci_type = fi.field_type   # nominal / quantitative — preserve field's own type
        elif derivation in _TEMPORAL_DERIVATIONS:
            ci_type = "ordinal"
        elif derivation == "Day-Trunc":
            ci_type = "quantitative"
        else:
            ci_type = "quantitative"

        # Type suffix abbreviation
        type_suffix = {"nominal": "nk", "quantitative": "qk", "ordinal": "ok"}[
            ci_type
        ]

        # Derivation abbreviation
        deriv_abbr = _DERIVATION_ABBR[derivation]

        instance_name = f"[{deriv_abbr}:{fi.local_name.strip('[]')}:{type_suffix}]"

        return ColumnInstance(
            column_local_name=fi.local_name,
            derivation=derivation if derivation != "None" else "None",
            instance_name=instance_name,
            ci_type=ci_type,
        )

    def default_view_expression(self, expr: str) -> str:
        """Return the default Tableau view binding for a field expression.

        Bare, non-calculated measures are promoted to SUM(...) so chart builders
        can treat raw measures as aggregated values without the caller having to
        spell out the aggregation every time.
        """

        text = str(expr).strip()
        if not text:
            return ""

        ci = self.parse_expression(text)
        if ci.derivation != "None":
            return text

        fi = self._find_field(text)
        if fi.role == "measure" and not fi.is_calculated:
            return f"SUM({text})"
        return text

    def resolve_full_reference(self, instance_name: str) -> str:
        """Generate a fully-qualified reference with datasource prefix.

        e.g. [federated.xxx].[sum:Sales (Orders):qk]
        """
        return f"[{self.datasource_name}].{instance_name}"

    # ---- Internal methods ----

    def _find_field(self, name: str) -> FieldInfo:
        """Find a field by display name, with exact and fuzzy matching.
        Unknown fields raise by default to avoid silent mapping mistakes.
        Set ``allow_unknown_fields=True`` to keep legacy auto-registration behavior.
        """
        # Exact match
        if name in self._fields:
            return self._fields[name]

        # Case-insensitive match
        name_lower = name.lower()
        for k, v in self._fields.items():
            if k.lower() == name_lower:
                return v

        if not self.allow_unknown_fields:
            examples = ", ".join(sorted(self._fields.keys())[:10])
            if len(self._fields) > 10:
                examples += ", ..."
            raise KeyError(
                f"Unknown field '{name}'. Register the field before use, "
                f"or enable allow_unknown_fields for compatibility. "
                f"Known fields: {examples or '(none)'}."
            )

        # Legacy compatibility mode: dynamic registration with heuristics.
        guessed_role = "dimension"
        guessed_datatype = "string"
        guessed_type = "nominal"

        lower_name = name.lower()
        if any(kw in lower_name for kw in ["sales", "profit", "discount", "quantity", "amount", "cost", "id"]):
            guessed_role = "measure"
            guessed_datatype = "real"
            guessed_type = "quantitative"

        self.register(
            display_name=name,
            local_name=f"[{name}]",
            datatype=guessed_datatype,
            role=guessed_role,
            field_type=guessed_type,
            is_calculated=False,
        )
        logger.warning(
            "Auto-registered unknown field '%s' (role=%s, datatype=%s, type=%s).",
            name,
            guessed_role,
            guessed_datatype,
            guessed_type,
        )
        return self._fields[name]
