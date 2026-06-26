"""Backward-compatible wrapper for ``python -m cwtwb.mcp``."""

from ..mcp_server import main


if __name__ == "__main__":
    main()
