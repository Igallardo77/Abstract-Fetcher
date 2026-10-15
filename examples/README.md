# Example Search and Screening Results

[Download screening.xlsx](screening.xlsx)

This workbook was provided by the repository owner as an example of search results and a subsequent literature screening workflow. The original Excel file was uploaded without an extension; it is stored here as `screening.xlsx`. Its contents and binary data have been preserved.

## Workbook contents

| Worksheet | Purpose |
| --- | --- |
| `protocol` | Review protocol and operational definitions |
| `search_log` | Search sources, queries, record counts, requests, and dates |
| `raw_records` | Retrieved bibliographic records, including title and abstract fields |
| `duplicates_exact` | Records identified as exact duplicates and the retained record keys |
| `automation_excluded` | Records excluded during automated processing |
| `screening` | Study identifiers, bibliographic data, and screening fields |
| `extraction` | Study-level data extraction fields |
| `prisma_counts` | Counts organized by review stage |
| `consistency_log` | Logged corrections to screening decisions and related fields |

The example concerns immersive virtual reality and gambling research. Worksheet names, field names, and data are retained as provided.

## How this example relates to Abstract Fetcher

Abstract Fetcher retrieves abstracts and bibliographic metadata and exports a CSV table. This Excel workbook illustrates a broader workflow that also includes screening, extraction, and review reporting.

To reuse its article titles as input to the desktop application:

1. Open the workbook in Excel or another compatible spreadsheet application.
2. Select the `raw_records` worksheet.
3. Save that worksheet as a UTF-8 CSV file, retaining the `title` column.
4. Load the CSV into Abstract Fetcher.

The application accepts `title`, `Title`, or `Título` as the title column. When a workbook is loaded directly, only its first worksheet is read. For this example, export the relevant worksheet as CSV before searching.

## File integrity

- File size: 1,323,128 bytes.
- SHA-256: `bb190485ba619da93613dd9b540eece625304537459fd991cb34fef928cf49d8`.
