"""Reorder workbook children into the order the official Tableau TWB XSD declares.

Tableau Desktop's DOM loader enforces ordered XSD sequences. A workbook whose
children are in the wrong order fails to load even when it is otherwise well
formed and every structural contract check passes.

Hand-maintaining the allowed order per container does not scale and is easy to
get subtly wrong (``Groups-G`` is a schema group name, the element is
``group``). This module derives the order from the vendored official schema
instead, so the rules cannot drift from the schema.

The reorder is conservative: a container is only touched when every one of its
children is known to a single candidate content model, which keeps unknown or
newer elements untouched.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from lxml import etree

XS = "{http://www.w3.org/2001/XMLSchema}"
_MODEL_TAGS = {f"{XS}sequence", f"{XS}choice", f"{XS}all"}


def _schema_path(version: str | None) -> Path | None:
    """Resolve the vendored XSD for a workbook version, mirroring validator.py."""
    try:
        from .validator import _resolve_schema_path
    except Exception:  # pragma: no cover - validator is part of the package
        return None
    try:
        path = _resolve_schema_path(version)
    except Exception:
        return None
    return path if path.exists() else None


@lru_cache(maxsize=8)
def _order_index(xsd_path: str) -> dict[str, tuple[tuple[str, ...], ...]]:
    """Map element name -> every candidate ordered child-name list in the XSD."""
    document = etree.parse(xsd_path)
    groups: dict[str, list] = {}
    complex_types: dict[str, list] = {}
    elements: dict[str, list] = {}

    for node in document.iter():
        if node.tag == f"{XS}group" and node.get("name"):
            groups.setdefault(node.get("name"), []).append(list(node))
        elif node.tag == f"{XS}complexType" and node.get("name"):
            complex_types.setdefault(node.get("name"), []).append(list(node))
        elif node.tag == f"{XS}element" and node.get("name"):
            # Nested element declarations (inside sequences, groups and inline
            # complexTypes) describe the same content model as top-level ones,
            # so index every declaration, not just the document root's.
            elements.setdefault(node.get("name"), []).append(
                (node.get("type"), list(node))
            )

    def expand(nodes, seen):
        """Expand a content model into alternative ordered name sequences.

        Returns a list of sequences because ``xs:choice`` introduces genuine
        alternatives: the schema allows *either* branch, not both concatenated.
        Flattening a choice into one sequence would invent an order that the
        schema never declares.
        """
        # Start with a single empty alternative; each node extends it.
        alternatives: list[list[str]] = [[]]
        for node in nodes:
            if node.tag in _MODEL_TAGS or node.tag in {
                f"{XS}complexType",
                f"{XS}complexContent",
                f"{XS}extension",
                f"{XS}restriction",
            }:
                if node.tag == f"{XS}choice":
                    # Each branch is an independent alternative.
                    branches = [expand([child], seen) for child in node]
                    merged: list[list[str]] = []
                    for branch in branches:
                        for base in alternatives:
                            for option in branch:
                                merged.append(base + option)
                    alternatives = merged or alternatives
                else:
                    sub = expand(list(node), seen)
                    if sub:
                        alternatives = [base + option for base in alternatives for option in sub]
            elif node.tag == f"{XS}group" and node.get("ref"):
                name = node.get("ref")
                if name in seen:
                    continue
                sub: list[list[str]] = []
                for body in groups.get(name, []):
                    sub.extend(expand(body, seen | {name}))
                if sub:
                    alternatives = [base + option for base in alternatives for option in sub]
            elif node.tag == f"{XS}element":
                name = node.get("name") or node.get("ref")
                if name:
                    alternatives = [base + [name] for base in alternatives]
        return alternatives
        # de-duplicate while preserving first occurrence
        seen_names: set[str] = set()
        deduped: list[str] = []
        for name in out:
            if name not in seen_names:
                seen_names.add(name)
                deduped.append(name)
        return deduped

    index: dict[str, tuple[tuple[str, ...], ...]] = {}
    for name, definitions in elements.items():
        orders: list[tuple[str, ...]] = []
        for type_attr, inline in definitions:
            if type_attr:
                for body in complex_types.get(type_attr, []):
                    orders.extend(tuple(alt) for alt in expand(body, set()))
            else:
                orders.extend(tuple(alt) for alt in expand(inline, set()))
        # de-duplicate alternatives while preserving order
        seen_orders: set[tuple[str, ...]] = set()
        unique: list[tuple[str, ...]] = []
        for order in orders:
            if order and order not in seen_orders:
                seen_orders.add(order)
                unique.append(order)
        if unique:
            index[name] = tuple(unique)
    return index


def canonical_child_order(
    tag: str, version: str | None = None
) -> tuple[str, ...] | None:
    """Return the XSD child order for ``tag``, or None when it is ambiguous."""
    path = _schema_path(version)
    if path is None:
        return None
    index = _order_index(str(path))
    orders = index.get(tag)
    if not orders:
        return None
    if len(orders) == 1:
        return orders[0]
    # Multiple definitions exist for this tag. Prefer the shortest model that
    # still covers the caller's children; the caller decides feasibility.
    return None


def _best_order(
    tag: str, present: set[str], version: str | None
) -> tuple[str, ...] | None:
    """Return the child order for ``tag``, requiring consensus.

    A tag can be declared in several places with different content models. To
    stay safe we only reorder when every candidate model that can accept the
    present children agrees on their relative order; otherwise the container is
    left untouched.
    """
    path = _schema_path(version)
    if path is None:
        return None
    orders = _order_index(str(path)).get(tag)
    if not orders:
        return None
    induced: list[tuple[str, ...]] = []
    for order in orders:
        if not present.issubset(set(order)):
            continue
        induced.append(tuple(name for name in order if name in present))
    if not induced:
        return None
    first = induced[0]
    if any(other != first for other in induced[1:]):
        return None
    return first


def reorder_to_schema(root: etree._Element, version: str | None = None) -> list[str] | None:
    """Stably reorder children of every element to the XSD-declared order.

    Returns the list of element tags that were reordered. Containers whose
    children include anything unknown to the schema are left untouched.
    Returns ``None`` when the vendored schema is unavailable, so callers can
    fall back to hardcoded rules instead of assuming nothing needed moving.
    """
    if _schema_path(version) is None:
        return None
    changed: list[str] = []
    for parent in root.iter():
        if not isinstance(parent.tag, str):
            continue  # comments and processing instructions
        children = list(parent)
        if len(children) < 2:
            continue
        if any(not isinstance(child.tag, str) for child in children):
            continue  # comments and processing instructions: leave alone
        present = {child.tag for child in children}
        order = _best_order(parent.tag, present, version)
        if order is None:
            continue
        position = {name: i for i, name in enumerate(order)}
        keyed = sorted(range(len(children)), key=lambda i: position[children[i].tag])
        if keyed == list(range(len(children))):
            continue
        for child in children:
            parent.remove(child)
        for i in keyed:
            parent.append(children[i])
        changed.append(parent.tag)
    return changed
