from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from .. import __version__
from ..config import SKILLS_DIR, TABLEAU_FUNCTIONS_JSON, get_profile_dirs
from ..validator import _resolve_schema_dir
from .common import emit


def status(args: Any) -> int:
    payload = {
        "version": __version__,
        "python": sys.version.split()[0],
        "cwd": str(Path.cwd()),
        "package_dir": str(Path(__file__).resolve().parents[1]),
        "skills_dir": str(SKILLS_DIR),
        "tableau_functions_json": str(TABLEAU_FUNCTIONS_JSON),
        "schema_dir": str(_resolve_schema_dir()),
        "profile_dirs": [str(path) for path in get_profile_dirs()],
        "stdin_is_tty": sys.stdin.isatty(),
    }
    if args.json:
        emit(payload, as_json=True)
        return 0
    lines = [
        f"cwtwb {payload['version']}",
        f"Python: {payload['python']}",
        f"Working directory: {payload['cwd']}",
        f"Package directory: {payload['package_dir']}",
        f"Schema directory: {payload['schema_dir']}",
        f"Skills directory: {payload['skills_dir']}",
    ]
    emit("\n".join(lines))
    return 0


def doctor(args: Any) -> int:
    checks = []
    schema_dir = _resolve_schema_dir()
    checks.append({
        "name": "schema_dir",
        "ok": schema_dir.is_dir(),
        "detail": str(schema_dir),
    })
    checks.append({
        "name": "skills_dir",
        "ok": SKILLS_DIR.is_dir(),
        "detail": str(SKILLS_DIR),
    })
    checks.append({
        "name": "tableau_functions_json",
        "ok": TABLEAU_FUNCTIONS_JSON.exists(),
        "detail": str(TABLEAU_FUNCTIONS_JSON),
    })
    checks.append({
        "name": "mcp_default_entry",
        "ok": True,
        "detail": "Use `uvx cwtwb` for MCP clients; use `cwtwb mcp` for explicit stdio server startup.",
    })
    checks.append({
        "name": "interactive_entry",
        "ok": True,
        "detail": "`cwtwb` with no args prints help when stdin is a TTY and starts MCP when stdin is piped.",
    })
    if os.getenv("CWTWB_MODE"):
        checks.append({
            "name": "CWTWB_MODE",
            "ok": os.getenv("CWTWB_MODE") in {"cli", "mcp"},
            "detail": os.getenv("CWTWB_MODE"),
        })
    payload = {"ok": all(check["ok"] for check in checks), "checks": checks}
    if args.json:
        emit(payload, as_json=True)
        return 0 if payload["ok"] else 1
    lines = ["cwtwb doctor"]
    for check in checks:
        marker = "PASS" if check["ok"] else "FAIL"
        lines.append(f"{marker}  {check['name']}: {check['detail']}")
    emit("\n".join(lines))
    return 0 if payload["ok"] else 1
