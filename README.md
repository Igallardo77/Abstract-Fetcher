# Abstract Fetcher

**A desktop application for retrieving scientific article abstracts and bibliographic metadata from a list of references.**

Abstract Fetcher helps researchers enrich Excel or CSV reference lists without searching for each article manually. It searches PubMed, Crossref, and Europe PMC, checks title similarity, and exports the retrieved records to a CSV file that can be opened in Excel. Semantic Scholar is available as an optional additional source.

Developed for **Dr. Iván Gallardo Bernal**, Universidad Autónoma de Guerrero (UAGro).

> The documentation is in English. The current application interface and result status labels are in Spanish.

## Abstract

Abstract Fetcher is a Python desktop application designed to support the enrichment of scientific reference lists with publicly accessible abstracts and bibliographic metadata. The application accepts Excel and CSV files containing article titles and queries PubMed, Crossref, Europe PMC, and, optionally, Semantic Scholar. Retrieved candidates are compared with the input titles using normalized string similarity, and records below a predefined threshold are rejected. Accepted records provide the available title, abstract, DOI, source, and URL, while query failures and missing information are explicitly recorded. A graphical interface supports file selection, progress monitoring, abstract inspection, cancellation, and CSV export. Background processing keeps the interface responsive, and incremental saving preserves completed results. The application does not synthesize abstracts or infer unavailable study findings. It provides a practical aid for reference preparation and preliminary literature organization, while requiring manual verification of article identity and retrieved content before scholarly use.

**Keywords:** abstract retrieval; bibliographic metadata; scientific references; PubMed; Crossref; Europe PMC; Python; desktop application.

## Code explanation

The application separates file handling, source queries, title matching, and interface updates. A background worker processes references, while a queue passes progress and results to the graphical interface. Results are saved after each completed reference.

See **[CODE_EXPLANATION.md](CODE_EXPLANATION.md)** for a plain-English walkthrough of the main functions, data flow, error handling, and Windows build process.

## Features

- Load references from `.xlsx` or `.csv` files.
- Search PubMed, Crossref, and Europe PMC sequentially.
- Optionally enable Semantic Scholar with your own API key.
- Retrieve article titles, abstracts, DOIs, source names, and record URLs when available.
- Compare requested titles with returned candidates before accepting a match.
- View progress and inspect individual abstracts in the desktop interface.
- Open the selected article record in your browser.
- Save results automatically after each completed reference.
- Stop processing while keeping completed results.
- Preserve the original input file and its non-result columns.
- Record source-level query failures for review.
- Run using Python's standard library, without pandas, Biopython, or an Excel installation.

**The application never generates placeholder abstracts.** If no abstract is retrieved, the abstract field remains empty.

## How it works

1. Load your reference list and enter a contact email address.
2. Click **Buscar resúmenes** and choose an output CSV file.
3. For each title, the application queries PubMed, then Crossref, then Europe PMC. It stops searching that reference once an accepted candidate contains an abstract. If configured, Semantic Scholar is queried last.
4. For each query, it compares up to three returned candidates with the requested title. Candidates with a normalized title similarity below **0.88** are rejected.
5. Results are saved after each completed reference. Select a row to inspect the retrieved abstract, provenance, similarity score, and query errors.

Title similarity uses Python's `SequenceMatcher` after normalization. **The score is a text similarity measure, not a probability that the article is correct.** Review accepted matches before using them in research.

## Requirements

- Python **3.10 or newer**, including Tcl/Tk, to run from source.
- An Internet connection to query the literature databases.
- A contact email address for identifying requests to the services.
- Optional: a Semantic Scholar API key.

On Windows, enable **Add Python to PATH** and include Tcl/Tk when installing Python from [python.org](https://www.python.org/downloads/windows/).

## Run the application

Download and extract the project, then run:

```bash
python abstract_fetcher.py
```

On Windows, you can also double-click **ABRIR_APP.bat**. If `dist/AbstractFetcher.exe` exists, the launcher opens it; otherwise it tries to run the Python source.

The main interface controls are:

| Button | Action |
| --- | --- |
| Cargar Excel / CSV | Load a reference list |
| Buscar resúmenes | Start searching and select the output file |
| Detener | Stop processing after the active request responds |
| Guardar copia CSV | Save a separate copy of the available results |
| Abrir artículo | Open the selected result URL |

## Input format

The first row must contain unique, non-empty column names. A column named **Title** or **Título** is required; capitalization does not matter. An **Index** column is optional.

```csv
Index,Title
1,"A guide to deep learning in healthcare"
2,"Attention Is All You Need"
```

- Excel: only the **first worksheet** is read. Use `.xlsx`; convert older `.xls` files first.
- CSV: comma, semicolon, and tab separators are detected automatically. UTF-8 and Windows-1252 encodings are supported.
- Prefer plain-text titles. Excel formula cells require a cached value saved by Excel.
- An example file is provided as `referencias_ejemplo.csv`.

## Output fields

The output retains the input columns and adds or replaces the following result fields:

| Field | Description |
| --- | --- |
| `Original_Title` | Title submitted for searching |
| `Matched_Title` | Title returned by the selected source |
| `DOI` | DOI from the selected record, if available |
| `Abstract` | Retrieved abstract, or an empty field |
| `Abstract_Source` | Source of the selected record, including metadata-only results |
| `URL` | Link to the selected record |
| `Match_Score` | Normalized title similarity, from 0 to 1 |
| `Status` | Retrieval outcome; labels are currently in Spanish |
| `Query_Errors` | Query failures encountered while processing this reference |

| Status label | Meaning |
| --- | --- |
| Resumen recuperado | An abstract was retrieved |
| Sin resumen público | A matching record was found, but no abstract was retrieved |
| Sin coincidencia aceptada | No returned candidate met the matching threshold |
| Sin título | The input reference has no title |

Existing input columns with the names of result fields are replaced in the output. The original input file is not modified.

The CSV is saved with a UTF-8 byte-order mark for Excel compatibility. Text beginning with spreadsheet formula characters is prefixed with an apostrophe during export.

## Build a Windows executable

On a Windows computer with Python installed, double-click:

```text
CREAR_EXE_WINDOWS.bat
```

The script creates an isolated build environment, installs PyInstaller, runs the automated tests, and builds:

```text
dist/AbstractFetcher.exe
```

You can distribute the generated executable to a compatible Windows computer without installing Python there. Internet access is still required for searching. Build and verify the executable on Windows before distributing it. No precompiled Windows binary is included in this source project.

## Reliability and limitations

- Title matching does not independently verify authors, publication year, or article version. Short titles and translated titles require particular care.
- Missing abstracts do not prove that an article has no abstract. The source may not expose it, the query may fail, or no candidate may pass the similarity threshold.
- Metadata and abstract fields come from the selected source record; earlier candidates are not merged into that record.
- The application retrieves abstracts and metadata. It does not download full-text articles, summarize papers, or perform a systematic literature review.
- Queries use timeouts and retry transient connection errors and selected HTTP errors. A stop request may need to wait for an active network request to finish.
- A new search starts from the first reference; interrupted searches cannot currently be resumed.
- Keep the output CSV closed in Excel while processing. If saving fails, available results remain in the window and can be saved using **Guardar copia CSV**.

## Privacy and service access

Titles are sent to the databases being queried. The contact email identifies the application requests. Input and output files are handled locally. A Semantic Scholar key entered in the window is used for requests and is not saved by the application.

Review each provider's terms and abstract reuse conditions before redistributing retrieved content.

## Tests and validation

Run the deterministic tests from the project directory:

```bash
python -m unittest discover -s tests -v
```

The 20 tests cover CSV/XLSX reading, structured abstracts, title matching, source provenance, empty results, query errors, retries, cancellation, and atomic CSV writing. They use local fixtures and mocked responses rather than live services.

Live responses from PubMed, Crossref, and Europe PMC were also checked during development. The abstract and DOI for *A guide to deep learning in healthcare* were successfully retrieved from Europe PMC. These checks do not guarantee availability or correctness for every reference.

The tests were run on Linux. Windows GUI rendering and executable compilation have not yet been verified.

## Project files

| File | Purpose |
| --- | --- |
| `abstract_fetcher.py` | Desktop interface, source clients, matching, and export |
| `ABRIR_APP.bat` | Windows launcher |
| `CREAR_EXE_WINDOWS.bat` | Windows executable build script |
| `referencias_ejemplo.csv` | Example input |
| `tests/test_app.py` | Automated tests |
| `LEEME.md` | Spanish usage instructions |

## Documentation

- [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25499/)
- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
- [Europe PMC REST API](https://europepmc.org/RestfulWebService)
- [Semantic Scholar API](https://www.semanticscholar.org/product/api)
- [PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html)
