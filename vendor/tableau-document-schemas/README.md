# Tableau Document Schemas
[![Tableau Supported](https://img.shields.io/badge/Support%20Level-Tableau%20Supported-53bd92.svg)](https://www.tableau.com/support-levels-it-and-developer-tools)

Official XML Schema Definition (XSD) files for Tableau document formats.

## Overview

This repository contains machine-readable schema definitions (XSD) for the Tableau workbook format (TWB) alongside conceptual information not covered by the XSD. Formally published in February 2026, these files represent an officially-supported baseline for the TWB format.

## What's a TWB? What's an XSD?
- **TWB (Tableau Workbook)**: An XML document describing a Tableau workbook, including its worksheets, dashboards, and stories.
- **XSD (XML Schema Definition)**: The W3C-recommended method for describing and validating the content and structure of XML documents.

The schemas in this repository provide a reference for developers and agents to build and validate TWBs against an official standard.

## Getting Started & Usage

### Directory Structure
Schema are organized into folders by Tableau version using the naming convention `YYYY_R`, where `YYYY` is the year, and `R` is the release number for that year.

**Example:**
```
schemas
└───2026_1
    └───twb_2026.1.0.xsd    # Tableau Workbook schema for version 2026.1
```

### Version Compatibility
When creating or modifying a TWB, ensure that the `original-version` and `version` attributes of the `<workbook>` element correspond with the version of the XSD you are using for validation. Note that the version strings don't match exactly, but correspond like below:
- TWB version string: `26.1`
- XSD file: `twb_2026.1.0.xsd`

**Example:**
```
<workbook original-version='26.1'
    source-build='0.0.0 (0000.0.0.0)'
    source-platform='win'
    version='26.1'
    xmlns:user='http://www.tableausoftware.com/xml/user'
>
```

### Manifest by version
The `<document-format-change-manifest>` element has historically included a list of features used by the workbook, used by Tableau to determine version compatibility between the TWB and the software that's opening it.

To make direct workbook authoring simpler, inside of the `<document-format-change-manifest>` element, use a single `<ManifestByVersion />` element instead. This replaces the complex manual listing of individual features in the document manifest.

If you use `<ManifestByVersion />` like this, the TWB will be version-compatible with Tableau software that has an equal or greater version. Versions of Tableau lower than the TWB's version will not be able to load the TWB.

**Example:**
```
<workbook original-version='26.1' source-build='0.0.0 (0000.0.0.0)' source-platform='win' version='26.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
    <document-format-change-manifest>
        <ManifestByVersion />
    </document-format-change-manifest>
```

## Validating a TWB against the XSD
To validate your Tableau Workbook (TWB) against the official schema (XSD), use any standard XML validation tool. Since a TWB file is natively XML, you simply point your XML validator to the TWB and the corresponding XSD from this repository.

## Important notes

### Syntatic versus semantic validation
The XSD is used for structural (syntactic) validation of a workbook. Successful syntactic validation can't guarantee that a workbook will open in Tableau (semantic validation).

### The XSD offers a baseline for syntactic validation
The schemas provide a reference for building a structurally-compliant TWB and don't cover the validation of some content. For example, some of the things that aren't validated when using the XSD are:
- attributes in connection elements
- calculated field contents, like function names and object references
- references to other named workbook contents, like tab names

You can locate XML elements that aren't validated by searching the XSD for `processContents="skip"`.

### Support limitations
Tableau technical support doesn't cover:
- **XML validation.** This includes XML validators, the process of XML validation, or XML validator claims that the XML isn't valid.
- **Semantic validation failure.** This means that an XML validator claims the XML is valid, but the workbook XML fails to load in a Tableau product.

### No TWBX Support
The schemas do not support building or validating packaged workbook files (TWBX).

## Contributing
See the **Contributing** tab.