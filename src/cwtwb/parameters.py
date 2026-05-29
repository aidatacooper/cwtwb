"""Parameter management mixin for TWBEditor.

Handles adding parameters and parameter dependencies.
"""

from __future__ import annotations

import copy
from typing import Optional

from lxml import etree


class ParametersMixin:
    """Mixin providing parameter management methods for TWBEditor."""

    def add_parameter(
        self,
        name: str,
        datatype: str = "real",
        default_value: str = "0",
        domain_type: str = "range",
        min_value: str = "",
        max_value: str = "",
        granularity: str = "",
        allowed_values: Optional[list[str]] = None,
        default_format: str = "",
        internal_name: Optional[str] = None,
        alias: Optional[str] = None,
        allowed_aliases: Optional[dict[str, str]] = None,
    ) -> str:
        """Add a parameter to the workbook.

        Parameters live in a special `<datasource name='Parameters'>` node.
        They can be referenced in calculated field formulas as
        `[Parameters].[ParameterName]`.

        Args:
            name: Display name for the parameter, e.g. "Target Profit".
            datatype: Data type: real/integer/string/date/boolean.
            default_value: Default/current value.
            domain_type: "range" or "list".
            min_value: Minimum value (range mode).
            max_value: Maximum value (range mode).
            granularity: Step size (range mode).
            allowed_values: List of allowed values (list mode).
            default_format: Optional Tableau number format string.
            internal_name: Optional explicit internal name, e.g. "[Parameter 4]".
                If not provided, auto-generated as "[Parameter N]".
            alias: Optional column-level alias (displayed in data pane).
            allowed_aliases: Optional dict mapping allowed_values to their aliases,
                e.g. {"1": "Sales Metrics", "2": "Order Details"}.

        Returns:
            Confirmation message.
        """
        # Find or create Parameters datasource
        datasources = self.root.find("datasources")
        if datasources is None:
            datasources = etree.SubElement(self.root, "datasources")

        params_ds = None
        for ds in datasources.findall("datasource"):
            if ds.get("name") == "Parameters":
                params_ds = ds
                break

        if params_ds is None:
            params_ds = etree.Element("datasource")
            params_ds.set("hasconnection", "false")
            params_ds.set("inline", "true")
            params_ds.set("name", "Parameters")
            params_ds.set("version", "18.1")
            aliases_el = etree.SubElement(params_ds, "aliases")
            aliases_el.set("enabled", "yes")
            # Insert as the FIRST datasource (Tableau convention)
            datasources.insert(0, params_ds)

        # Use provided internal name or auto-generate
        if internal_name is None:
            param_counter = len(params_ds.findall("column")) + 1
            internal_name = f"[Parameter {param_counter}]"

        # Create column element
        col = etree.Element("column")
        if alias:
            col.set("alias", alias)
        col.set("caption", name)
        col.set("datatype", datatype)
        if default_format:
            col.set("default-format", default_format)
        col.set("name", internal_name)
        col.set("param-domain-type", domain_type)
        col.set("role", "measure")
        col.set("type", "quantitative" if datatype != "boolean" else "nominal")
        if datatype in ("string", "boolean"):
            col.set("datatype-customized", "true")
        # For string parameters, value must be quoted: '"Shipping"'
        if datatype == "string" and not default_value.startswith('"'):
            col.set("value", f'"{default_value}"')
        else:
            col.set("value", default_value)

        # Add calculation (default value formula)
        calc = etree.SubElement(col, "calculation")
        calc.set("class", "tableau")
        if datatype == "string" and not default_value.startswith('"'):
            calc.set("formula", f'"{default_value}"')
        else:
            calc.set("formula", default_value)

        if domain_type == "range":
            range_el = etree.SubElement(col, "range")
            if granularity:
                range_el.set("granularity", granularity)
            if max_value:
                range_el.set("max", max_value)
            if min_value:
                range_el.set("min", min_value)
        elif domain_type == "list" and allowed_values:
            # Add aliases child if any aliases provided
            if allowed_aliases:
                col_aliases = etree.SubElement(col, "aliases")
                for val, al in allowed_aliases.items():
                    a = etree.SubElement(col_aliases, "alias")
                    key_val = f'"{val}"' if datatype == "string" else val
                    a.set("key", key_val)
                    a.set("value", al)
            members = etree.SubElement(col, "members")
            for v in allowed_values:
                member = etree.SubElement(members, "member")
                if allowed_aliases and v in allowed_aliases:
                    member.set("alias", allowed_aliases[v])
                # String member values must be quoted in Tableau XML
                if datatype == "string":
                    member.set("value", f'"{v}"')
                else:
                    member.set("value", v)

        params_ds.append(col)

        # Track the parameter for later reference (filter zones, paramctrl zones)
        if not hasattr(self, "_parameters"):
            self._parameters = {}
        self._parameters[name] = {
            "internal_name": internal_name,
            "datatype": datatype,
            "domain_type": domain_type,
        }

        return f"Added parameter '{name}' (type={datatype}, domain={domain_type}, default={default_value})"

    def _add_parameter_deps(self, view: etree._Element) -> None:
        """Add Parameters datasource-dependencies to a view element.
        
        Creates a <datasource-dependencies datasource='Parameters'> block
        containing column definitions for all tracked parameters.
        """
        if not self._parameters:
            return
            
        # Check if already exists
        for existing in view.findall("datasource-dependencies"):
            if existing.get("datasource") == "Parameters":
                return  # Already present
        
        # Find Parameters datasource in root
        params_ds = None
        for ds in self.root.findall(".//datasource"):
            if ds.get("name") == "Parameters":
                params_ds = ds
                break
        if params_ds is None:
            return
        
        # Create deps element
        param_deps = etree.Element("datasource-dependencies")
        param_deps.set("datasource", "Parameters")
        
        # Copy column definitions from Parameters datasource
        for col in params_ds.findall("column"):
            col_copy = copy.deepcopy(col)
            param_deps.append(col_copy)
        
        # Insert after mapsources but before main datasource-dependencies
        # Schema: datasources → mapsources → datasource-dependencies
        ms = view.find("mapsources")
        if ms is not None:
            ms.addnext(param_deps)
        else:
            ds_el = view.find("datasources")
            if ds_el is not None:
                ds_el.addnext(param_deps)
            else:
                agg = view.find("aggregation")
                if agg is not None:
                    agg.addprevious(param_deps)
                else:
                    view.append(param_deps)
