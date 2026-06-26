"""Backward-compatible resource module for older imports.

Resources now live in ``cwtwb.mcp.app``. This shim keeps imports like
``cwtwb.mcp.resources`` working for tests and external callers.
"""

from .app import (
    read_dashboard_authoring_contract,
    read_dataset_profile,
    read_profiles_index,
    read_skill,
    read_skills_index,
    read_tableau_functions,
)

__all__ = [
    "read_tableau_functions",
    "read_skills_index",
    "read_skill",
    "read_dashboard_authoring_contract",
    "read_profiles_index",
    "read_dataset_profile",
]
