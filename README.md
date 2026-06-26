# cwtwb

<p align="center">
  <img src="https://raw.githubusercontent.com/imgwho/cwtwb/main/docs/assets/readme/logo.png" alt="Datacooper logo" width="220" />
</p>

> Tableau workbook engineering for reproducible `.twb` / `.twbx` generation, validation, and migration.

<p align="center">
  <img src="https://raw.githubusercontent.com/imgwho/cwtwb/main/docs/assets/readme/hero.png" alt="cwtwb hero image" width="1200" />
</p>

**cwtwb** is a Python toolkit and Model Context Protocol (MCP) server for building Tableau Desktop workbooks from code or agent tool calls.

It is meant to be a **workbook engineering layer**, not a conversational analytics agent. The focus is reproducibility, inspectability, and safe automation in local workflows, scripts, and CI.

The `cw` in `cwtwb` comes from `Cooper Wenhua`.


**Author:** Cooper Wenhua &lt;imgwho@gmail.com&gt;

[Website](https://datacooper.com) · [Source](https://github.com/imgwho/cwtwb) · [Changelog](https://github.com/imgwho/cwtwb/blob/main/CHANGELOG.md)

[![Website](https://img.shields.io/badge/Website-datacooper.com-0A7CFF?style=flat-square)](https://datacooper.com)
[![Source](https://img.shields.io/badge/Source-GitHub-181717?style=flat-square)](https://github.com/imgwho/cwtwb)
[![License](https://img.shields.io/badge/License-AGPL--3.0--or--later-green?style=flat-square)](https://github.com/imgwho/cwtwb/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square)](https://www.python.org/)

[![Star History Chart](https://api.star-history.com/svg?repos=imgwho/cwtwb&type=Date)](https://star-history.com/#imgwho/cwtwb&Date)

[Try the example workflow](examples/scripts/demo_all_supported_charts.py) · [Read the guide](https://github.com/imgwho/cwtwb/blob/main/docs/guide.md)

## Quick Start

### Install

```bash
pip install cwtwb
```

If you want the bundled Hyper-backed example too:

```bash
pip install "cwtwb[examples]"
```

If you want cloud validation (upload to Tableau Cloud/Server):

```bash
pip install "cwtwb[validate]"
```

### Run As An MCP Server

```bash
uvx cwtwb
```

The short form above remains the simplest option and is the default config shown in this repository.

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

If you prefer an explicit script name, these equivalent launch styles also work:

```bash
uvx --from cwtwb cwtwb-mcp
python -m cwtwb.mcp_server
```

For client-specific details and the full reference, see [https://github.com/imgwho/cwtwb/blob/main/docs/guide.md](https://github.com/imgwho/cwtwb/blob/main/docs/guide.md).

## Highlights

| Area | What you get |
|---|---|
| Workbook authoring | Generate `.twb` / `.twbx` files from templates or from scratch |
| Chart building | Build bar, line, pie, map, KPI, and dual-axis workbooks |
| Safety | Validate structure, Tableau XSD (2026.1/2026.2), and REST API semantic validation before publishing |
| Cloud validation | REST API syntactic/semantic validation + upload to Tableau Cloud/Server with optional screenshot |
| Migration | Repoint existing workbooks to new data sources with explicit steps |
| MCP support | Drive workbook workflows from Claude, Cursor, VSCode, or other MCP clients |

## See It In Action

This GIF shows the MCP tool flow that builds a dashboard step by step.

<p align="center">
  <img src="https://raw.githubusercontent.com/imgwho/cwtwb/main/docs/assets/readme/output_compressed.gif" alt="cwtwb demo GIF" width="1200" />
</p>

## Architecture

```
                            Interfaces
  ┌───────────────────────────────────────────────────────────────┐
  │  ┌──────────────────────────┐  ┌───────────────────────────┐  │
  │  │        MCP Server        │  │      Python Library       │  │
  │  │  tools_workbook          │  │  from cwtwb.twb_editor    │  │
  │  │  tools_validate          │  │  import TWBEditor         │  │
  │  │                          │  │                           │  │
  │  │                          │  │  editor.add_...()         │  │
  │  │                          │  │  editor.configure_...()   │  │
  │  │                          │  │  editor.validate_schema() │  │
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
  │       validate_schema()  ·  save()                            │
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
                                  ▼
  ┌───────────────────────────────────────────────────────────────┐
  │               Cloud Validation (optional)                    │
  │    validate_workbook → REST API semantic validation          │
  │    upload_workbook   → Tableau Cloud/Server publish          │
  │    screenshot_workbook → capture view for visual check       │
  └───────────────────────────────────────────────────────────────┘
```

## Validation

cwtwb provides four levels of workbook validation:

| Level | Description | Requires |
|---|---|---|
| **1. Local XSD** | Validate against the official Tableau TWB XSD schema (version-aware: 2026.1 or 2026.2) | None (built-in) |
| **2. REST API Syntactic** | Validate XML syntax via Tableau Cloud REST API | `.env` + Tableau Cloud 2026.2+ |
| **3. REST API Semantic** | Full semantic validation — guarantees the workbook opens in Tableau | `.env` + Tableau Cloud 2026.2+ |
| **4. Upload + Screenshot** | Publish to Tableau Cloud/Server and capture a view image | `.env` + `pip install "cwtwb[validate]"` |

```python
# Level 1 — Local XSD (in-memory, no save required)
result = editor.validate_schema()
print(result.to_text())

# Level 3 — REST API semantic validation
from cwtwb.validate.uploader import TableauUploader
uploader = TableauUploader()
result = uploader.validate("output.twb", validation_level="semantic")

# Save with automatic REST API validation (enforced when .env is configured)
editor.save("output.twb")  # runs local XSD + REST API semantic validation
```

```bash
# MCP tools
validate_workbook(twb_path="output.twb")                             # REST API validation
upload_workbook(twb_path="output.twb")                               # Cloud upload
screenshot_workbook(workbook_id="...", view_name="Sheet 1")          # Visual check
```

## FAQ

### What is the difference between `.twb` and `.twbx`?

`.twb` is the workbook XML. `.twbx` is the packaged version that bundles the workbook together with extracts and images.

### Does `validate_workbook` save files?

No. `validate_workbook()` validates via the Tableau Cloud REST API (requires `.env` configuration). It does not write output. `save_workbook()` is the tool that writes files.

### What validation does `save()` perform?

`save()` runs local XSD validation automatically. If `.env` is configured and the Tableau server supports it (Cloud 2026.2+ / Server 2026.2+), REST API semantic validation is also enforced — this guarantees the workbook will open in Tableau. If `.env` is not configured, only local XSD validation runs.

### What is `upload_workbook` for?

`upload_workbook` uploads a `.twb` to Tableau Cloud/Server to verify it is structurally valid. Upload success means Tableau Cloud/Server can parse the workbook. Requires `pip install "cwtwb[validate]"` and a `.env` file with Tableau credentials (see `.env.example`).

### How do I set up Tableau Cloud/Server validation?

1. Install: `pip install "cwtwb[validate]"`
2. Copy `.env.example` to `.env`
3. Fill in your Tableau Cloud/Server PAT credentials
4. `save_workbook` will automatically run REST API semantic validation
5. Or call `validate_workbook` directly for validation without saving

### When should I use `uvx cwtwb` versus `python -m cwtwb.mcp_server`?

Use `uvx cwtwb` for the normal MCP workflow. Use `python -m cwtwb.mcp_server` for local testing without `uvx`.

For backward compatibility, `uvx --from cwtwb cwtwb-mcp`, `python -m cwtwb.server`, and `python -m cwtwb.mcp` continue to work.

### Where is the full guide?

See [the online guide](https://github.com/imgwho/cwtwb/blob/main/docs/guide.md).

## Documentation

- [Guide](https://github.com/imgwho/cwtwb/blob/main/docs/guide.md)
- [Changelog](https://github.com/imgwho/cwtwb/blob/main/CHANGELOG.md)

## License

AGPL-3.0-or-later
