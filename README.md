# cwtwb

<p align="center">
  <img src="https://raw.githubusercontent.com/imgwho/cwtwb/master/docs/assets/readme/logo.png" alt="Datacooper logo" width="220" />
</p>

> Tableau workbook engineering for reproducible `.twb` / `.twbx` generation, validation, and migration.

<p align="center">
  <img src="https://raw.githubusercontent.com/imgwho/cwtwb/master/docs/assets/readme/hero.png" alt="cwtwb hero image" width="1200" />
</p>

**cwtwb** is a Python toolkit and Model Context Protocol (MCP) server for building Tableau Desktop workbooks from code or agent tool calls.

It is meant to be a **workbook engineering layer**, not a conversational analytics agent. The focus is reproducibility, inspectability, and safe automation in local workflows, scripts, and CI.

The `cw` in `cwtwb` comes from `Cooper Wenhua`.

Latest update (`0.18.9`): release refresh for a republish after the previous `0.18.8` artifacts already existed on PyPI.

**Author:** Cooper Wenhua &lt;imgwho@gmail.com&gt;

[Website](https://datacooper.com) · [Source](https://github.com/imgwho/cwtwb) · [Changelog](https://github.com/imgwho/cwtwb/blob/master/CHANGELOG.md)

[![Website](https://img.shields.io/badge/Website-datacooper.com-0A7CFF?style=flat-square)](https://datacooper.com)
[![Source](https://img.shields.io/badge/Source-GitHub-181717?style=flat-square)](https://github.com/imgwho/cwtwb)
[![License](https://img.shields.io/badge/License-AGPL--3.0--or--later-green?style=flat-square)](https://github.com/imgwho/cwtwb/blob/master/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square)](https://www.python.org/)

[![Star History Chart](https://api.star-history.com/svg?repos=imgwho/cwtwb&type=Date)](https://star-history.com/#imgwho/cwtwb&Date)

[Try the example workflow](examples/scripts/demo_all_supported_charts.py) · [Read the guide](https://github.com/imgwho/cwtwb/blob/master/docs/guide.md)

## Quick Start

### Install

```bash
pip install cwtwb
```

If you want the bundled Hyper-backed example too:

```bash
pip install "cwtwb[examples]"
```

### Run As An MCP Server

```bash
uvx cwtwb
```

Add the server to your MCP client with the same command. For example:

```json
{
  "mcpServers": {
    "cwtwb": {
      "command": "uvx",
      "args": ["cwtwb"]
    }
  }
}
```

For Claude Code:

```bash
claude mcp add cwtwb -- uvx cwtwb
```

For VSCode, add `cwtwb` to your workspace or user `mcp.json` and use `uvx cwtwb` as the command.

For client-specific details and the full reference, see [https://github.com/imgwho/cwtwb/blob/master/docs/guide.md](https://github.com/imgwho/cwtwb/blob/master/docs/guide.md).

## Highlights

| Area | What you get |
|---|---|
| Workbook authoring | Generate `.twb` / `.twbx` files from templates or from scratch |
| Chart building | Build bar, line, pie, map, KPI, and dual-axis workbooks |
| Safety | Validate structure and Tableau XSD before publishing |
| Migration | Repoint existing workbooks to new data sources with explicit steps |
| MCP support | Drive workbook workflows from Claude, Cursor, VSCode, or other MCP clients |

## See It In Action

This GIF shows the MCP tool flow that builds a dashboard step by step.

<p align="center">
  <img src="https://raw.githubusercontent.com/imgwho/cwtwb/master/docs/assets/readme/output_compressed.gif" alt="cwtwb demo GIF" width="1200" />
</p>

## Architecture

```
                            Interfaces
  ┌───────────────────────────────────────────────────────────────┐
  │  ┌──────────────────────────┐  ┌───────────────────────────┐  │
  │  │        MCP Server        │  │      Python Library       │  │
  │  │  tools_workbook          │  │  from cwtwb.twb_editor    │  │
  │  │                          │  │  import TWBEditor         │  │
  │  │                          │  │                           │  │
  │  │                          │  │  editor.add_...()         │  │
  │  │                          │  │  editor.configure_...()   │  │
  │  │  (Claude / Cursor /      │  │  editor.save(...)         │  │
  │  │   VSCode / Claude Code)  │  │                           │  │
  │  └─────────────┬────────────┘  └──────────────┬────────────┘  │
  │                └──────────────┬────────────────┘               │
  └─────────────────────────────  ┼  ─────────────────────────────┘
                                  ▼
  ┌───────────────────────────────────────────────────────────────┐
  │                          TWBEditor                            │
  │       ParametersMixin  ·  ConnectionsMixin                    │
  │       ChartsMixin      ·  DashboardsMixin                     │
  └──────────┬──────────────────┬──────────────────┬─────────────┘
             ▼                  ▼                  ▼
  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────────┐
  │  Chart Builders  │  │  Dashboard   │  │  Analysis &          │
  │                  │  │  System      │  │  Migration           │
  │  Basic  DualAxis │  │              │  │                      │
  │  Pie    Text     │  │  layouts     │  │  migration.py        │
  │  Map    Recipes  │  │  actions     │  │  twb_analyzer.py     │
  │                  │  │  dependencies│  │  capability_registry │
  └────────┬─────────┘  └──────┬───────┘  └──────────┬───────────┘
           └───────────────────┼──────────────────────┘
                               ▼
  ┌───────────────────────────────────────────────────────────────┐
  │                     XML Engine  (lxml)                        │
  │    template.twb/.twbx  →  patch  →  validate  →  save        │
  └───────────────────────────────┬───────────────────────────────┘
                                  ▼
                      output.twb  /  output.twbx
```

## FAQ

### What is the difference between `.twb` and `.twbx`?

`.twb` is the workbook XML. `.twbx` is the packaged version that bundles the workbook together with extracts and images.

### Does `validate_workbook` save files?

No. `validate_workbook()` checks the workbook in memory or on disk, but it does not write output. `save_workbook()` is the tool that writes files.

### When should I use `uvx cwtwb` versus `python -m cwtwb.mcp`?

Use `uvx cwtwb` for the normal MCP workflow. Use `python -m cwtwb.mcp` for local testing without `uvx`.

### Where is the full guide?

See [the online guide](https://github.com/imgwho/cwtwb/blob/master/docs/guide.md).

## Documentation

- [Guide](https://github.com/imgwho/cwtwb/blob/master/docs/guide.md)
- [Changelog](https://github.com/imgwho/cwtwb/blob/master/CHANGELOG.md)

## License

AGPL-3.0-or-later
