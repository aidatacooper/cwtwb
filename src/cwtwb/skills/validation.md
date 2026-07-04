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
| **REST API semantic** (`validate_workbook_api`, level=`semantic`) | Full semantic validation | Yes | Tableau Cloud June 2026+ / Server 2026.2+ |
| **Upload** (`upload_workbook`) | Publishes + Tableau Cloud parses it | Yes | Tableau Cloud/Server |

### Which to use?

- **Quick check during development**: use local XSD (no server needed)
- **Before shipping to production**: use REST API semantic validation
- **When you need a visual preview**: use `upload_workbook` + `screenshot_workbook`

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

Use `env_path` when credentials live outside the MCP server's launch
environment:

```
validate_workbook_api(twb_path, validation_level="semantic", env_path="project/.env")
```

### Option C: Upload + screenshot (visual confirmation)
```
1. save_workbook(path)
2. upload_workbook(twb_path)        - publish to Tableau Cloud
3. screenshot_workbook(workbook_id) - capture view image
4. Report result to human
```

## Pre-flight

- **Local XSD**: no configuration needed
- **REST API validation**: requires Tableau credentials from environment variables, explicit `env_path`, `TABLEAU_ENV_FILE`, a workbook sibling `.env`, cwd `.env`, project `.env`, or home `.env` + `pip install 'cwtwb[validate]'`
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
