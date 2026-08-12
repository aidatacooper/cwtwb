"""Lightweight validation for Tableau function calls in calculations.

This module deliberately validates only identifiers used as function calls.
It is not a complete Tableau formula parser and does not replace Tableau
Desktop or Tableau Cloud semantic validation.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache

from .config import TABLEAU_FUNCTIONS_JSON

_FUNCTION_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_NON_FUNCTION_KEYWORDS = frozenset(
    {
        "AND",
        "CASE",
        "ELSE",
        "ELSEIF",
        "END",
        "FALSE",
        "FIXED",
        "IF",
        "IN",
        "INCLUDE",
        "EXCLUDE",
        "NOT",
        "NULL",
        "OR",
        "THEN",
        "TRUE",
        "WHEN",
    }
)


@dataclass(frozen=True)
class FormulaValidationIssue:
    """One unknown function call found in a Tableau calculation."""

    function_name: str
    position: int
    suggestion: str | None
    message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class FormulaValidationResult:
    """Structured result for a lightweight Tableau function check."""

    valid: bool
    issues: tuple[FormulaValidationIssue, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
            "boundary": (
                "Function-name validation only; Tableau runtime semantics are not checked."
            ),
        }


@lru_cache(maxsize=1)
def valid_tableau_function_names() -> frozenset[str]:
    """Load the packaged Tableau function catalog as upper-case names."""

    with TABLEAU_FUNCTIONS_JSON.open(encoding="utf-8") as handle:
        entries = json.load(handle)
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).upper()
        if name and " " not in name:
            names.add(name)
        # The packaged catalog groups RANK, RUNNING, and WINDOW table
        # calculations in a single record. Extract their individual calls
        # from the catalog text instead of maintaining a second hand list.
        syntax = str(entry.get("syntax", ""))
        code_spans = re.findall(
            r"`([^`]+)`",
            "\n".join(str(entry.get(key, "")) for key in ("description", "notes")),
        )
        for catalog_code in (syntax, *code_spans):
            names.update(
                match.group(1).upper()
                for match in _FUNCTION_CALL_RE.finditer(catalog_code)
            )
    return frozenset(names)


def _mask_non_code(formula: str) -> str:
    """Mask strings, field references, and comments while preserving offsets."""

    chars = list(formula)
    index = 0
    length = len(chars)
    while index < length:
        char = chars[index]

        if char == "[":
            end = index + 1
            while end < length:
                if chars[end] == "]":
                    end += 1
                    break
                end += 1
            for pos in range(index, end):
                chars[pos] = " "
            index = end
            continue

        if char in {"'", '"'}:
            quote = char
            end = index + 1
            while end < length:
                if chars[end] == quote:
                    if end + 1 < length and chars[end + 1] == quote:
                        end += 2
                        continue
                    end += 1
                    break
                end += 1
            for pos in range(index, end):
                chars[pos] = " "
            index = end
            continue

        if char == "/" and index + 1 < length and chars[index + 1] == "/":
            end = formula.find("\n", index + 2)
            if end == -1:
                end = length
            for pos in range(index, end):
                chars[pos] = " "
            index = end
            continue

        if char == "/" and index + 1 < length and chars[index + 1] == "*":
            closing = formula.find("*/", index + 2)
            end = length if closing == -1 else closing + 2
            for pos in range(index, end):
                chars[pos] = " "
            index = end
            continue

        index += 1
    return "".join(chars)


def _suggest(function_name: str) -> str | None:
    matches = difflib.get_close_matches(
        function_name,
        sorted(valid_tableau_function_names()),
        n=1,
        cutoff=0.6,
    )
    return matches[0] if matches else None


def validate_formula_functions(formula: str) -> FormulaValidationResult:
    """Report identifiers called as functions but absent from the catalog."""

    valid_names = valid_tableau_function_names()
    masked = _mask_non_code(formula or "")
    issues: list[FormulaValidationIssue] = []
    seen: set[str] = set()
    for match in _FUNCTION_CALL_RE.finditer(masked):
        name = match.group(1).upper()
        if name in valid_names or name in _NON_FUNCTION_KEYWORDS or name in seen:
            continue
        seen.add(name)
        suggestion = _suggest(name)
        message = f"Unknown Tableau function {name}()."
        if suggestion:
            message += f" Did you mean {suggestion}()?"
        issues.append(
            FormulaValidationIssue(
                function_name=name,
                position=match.start(1),
                suggestion=suggestion,
                message=message,
            )
        )
    return FormulaValidationResult(valid=not issues, issues=tuple(issues))


def assert_valid_formula_functions(formula: str, field_name: str = "") -> None:
    """Raise ``ValueError`` when a formula contains unknown function calls."""

    result = validate_formula_functions(formula)
    if result.valid:
        return
    prefix = f"Calculated field '{field_name}': " if field_name else ""
    details = " ".join(issue.message for issue in result.issues)
    raise ValueError(
        f"{prefix}{details} Function-name validation can be bypassed with "
        "validate_formula=False when using a newer Tableau function not yet in the catalog."
    )
