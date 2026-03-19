"""Shared configuration constants for cwtwb.

This module provides path constants and configuration used across
the cwtwb package. Extracted to avoid circular imports between
twb_editor.py and server.py.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path


def _generate_uuid() -> str:
    """Generate an uppercase UUID string: {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}."""
    return "{" + str(uuid.uuid4()).upper() + "}"

# Directory containing reference files (templates, XLS data, function definitions)
REFERENCES_DIR = Path(__file__).parent / "references"

# Path to the default Superstore template
DEFAULT_TEMPLATE = REFERENCES_DIR / "empty_template.twb"

# Path to the Tableau functions JSON
TABLEAU_FUNCTIONS_JSON = REFERENCES_DIR / "tableau_all_functions.json"

# Directory containing skill files for AI agents
SKILLS_DIR = Path(__file__).parent / "skills"

# Directory containing authoring contract templates for AI agents
CONTRACTS_DIR = Path(__file__).parent / "contracts"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = PROJECT_ROOT / "examples"
DEFAULT_PROFILE_DIRS = (
    EXAMPLES_DIR / "profiles",
    EXAMPLES_DIR / "agentic_mcp_authoring" / "profiles",
)


def get_profile_dirs() -> list[Path]:
    """Return configured external dataset profile directories.

    Search order:
    1. Directories from CWTWB_PROFILE_DIR (os.pathsep-separated)
    2. Repository example profile directories (if present)
    """

    dirs: list[Path] = []
    env_value = os.environ.get("CWTWB_PROFILE_DIR", "").strip()
    if env_value:
        for raw in env_value.split(os.pathsep):
            raw = raw.strip()
            if raw:
                dirs.append(Path(raw))

    for path in DEFAULT_PROFILE_DIRS:
        if path not in dirs:
            dirs.append(path)

    return dirs


def iter_profile_files() -> list[Path]:
    """Return all discovered dataset profile files from configured directories."""

    files: list[Path] = []
    for directory in get_profile_dirs():
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            if path not in files:
                files.append(path)
    return files


def find_profile_path(profile_name: str) -> Path | None:
    """Find one dataset profile JSON file by stem across configured directories."""

    for path in iter_profile_files():
        if path.stem == profile_name:
            return path
    return None
