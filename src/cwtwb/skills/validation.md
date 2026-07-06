---
name: Workbook Validation
description: Validate and/or upload .twb files with local XSD checks, REST API semantic validation, and optional Tableau Cloud screenshots.
phase: 5
prerequisites: formatting (workbook should be saved first)
---

# Workbook Validation Skill

## Your Role

You are a **quality assurance agent**. After generating a Tableau workbook,
validate it to confirm it will open in Tableau. Choose the right validation
level for the situation.

## Validation Levels

| Level | What it checks | Guarantees opening? | Requires |
|-------|---------------|---------------------|----------|
| **Local XSD** (`validate_workbook`) | XML structure against official schema | No | Nothing (built-in) |
| **REST API syntactic** (`validate_workbook_api`, level=`syntactic`) | Same as XSD, via Tableau Cloud | No | Tableau Cloud/Server 2026.2+ |
| **REST API semantic** (`validate_workbook_api`, level=`semantic`) | Full semantic validation without publishing | Yes | Tableau Cloud June 2026+ / Server 2026.2+ |
| **Upload** (`upload_workbook`) | Publishes + Tableau Cloud parses it | Yes | Tableau Cloud/Server |

### Which to use?

- **Quick check during development**: use local XSD (no server needed)
- **Before shipping to production**: use `validate_workbook_api(..., validation_level="semantic")`
- **When you need a visual preview, workbook_id, or publish evidence**: use `upload_workbook` + `screenshot_workbook`
- **When validating `.twbx` packaging**: use `upload_workbook`; `validate_workbook_api` accepts `.twb` only

## Workflow

### Option A: Local XSD validation (fast, no server)
```
1. save_workbook(path)
2. validate_workbook(file_path)  - local XSD check
   -> PASS: XML structure is valid
   -> FAIL: fix XML issues and retry
```

### Option B: REST API semantic validation (definitive)
```
1. save_workbook(path)
2. validate_workbook_api(twb_path, validation_level="semantic")
   -> valid=true: workbook will open in Tableau
   -> valid=false: read errors, fix and retry
```

This is the default cloud validation path for `.twb` files. It is lighter than
upload_workbook because it does not publish or store the workbook on Tableau
Cloud/Server.

Use `env_path` when credentials live outside the MCP server's launch
environment:

```
validate_workbook_api(twb_path, validation_level="semantic", env_path="project/.env")
```

Do not edit MCP server configuration just to switch Tableau credentials for a
single workbook. Pass `env_path` on the tool call; it takes priority over
process environment variables.

### Option C: Upload + screenshot (publish/visual confirmation only)
```
1. save_workbook(path)
2. upload_workbook(twb_path, env_path="project/.env")        - publish to Tableau Cloud
3. screenshot_workbook(workbook_id, env_path="project/.env") - capture view image
4. Report result to human
```

Use this path only when the user explicitly asks for upload/publish evidence,
a visual screenshot, a workbook_id, or `.twbx` package validation. Do not use
upload_workbook as the default substitute for validate_workbook_api.

## Pre-flight

- **Local XSD**: no configuration needed
- **REST API validation**: requires Tableau credentials from explicit `env_path`, environment variables, `TABLEAU_ENV_FILE`, a workbook sibling `.env`, cwd `.env`, project `.env`, or home `.env` + `pip install 'cwtwb[validate]'`
- **Upload**: same as REST API validation
- If not configured, tool returns a clear error message

## Error Handling

| Error | Action |
|-------|--------|
| PAT not configured | Tell human to create `.env` from `.env.example` |
| 401 Unauthorized | Check PAT name/secret and site content URL |
| 404 Validation endpoint not found | Server doesn't support validation API (needs 2026.2+) |
| 400 Validation failed | Read error messages, fix workbook, retry |
| 500 Server error | Check .twbx internal file structure |
