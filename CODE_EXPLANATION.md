# Code Explanation

This guide explains `abstract_fetcher.py` in plain English. The program takes a list of article titles, searches external literature databases, and saves the retrieved abstracts and metadata.

## 1. The overall workflow

The application performs the following steps:

1. The user selects an Excel or CSV file.
2. The program reads each reference and identifies its title.
3. A background worker searches the available databases in sequence.
4. The program compares each candidate title with the requested title.
5. It keeps an accepted record, including its abstract if available.
6. It sends the result to the interface and saves completed results to a CSV file.

For example, the input title `A guide to deep learning in healthcare` can lead to a matching database record with an abstract, DOI, and URL. If no suitable record is found, the output preserves the original reference and records the outcome without inventing a summary.

## 2. Main components

| Component | Responsibility |
| --- | --- |
| `clean()` | Remove markup, decode HTML entities, and normalize whitespace |
| `normalized()` | Prepare text for title comparisons |
| `similarity()` | Calculate how similar two normalized titles are |
| `read_table()` | Read references from CSV or the first Excel worksheet |
| `title_of()` | Find the value in a `Title` or `Título` column |
| `write_results()` | Write results to a CSV file using an atomic replacement |
| `Candidate` | Hold a single source record in a common format |
| `parse_pubmed()` | Extract candidate records from PubMed XML |
| `Client` | Send requests, query sources, and resolve a reference |
| `Cancelled` | Signal a user-requested stop |
| `main()` and its nested `App` class | Create and operate the desktop interface |

## 3. Reading the reference list

`read_table(path)` checks the file extension to select the reader.

For CSV files, it tries UTF-8 first and falls back to Windows-1252. It detects comma, semicolon, or tab separators and uses Python's CSV parser, which supports quoted fields and line breaks inside cells.

For Excel files, it opens the `.xlsx` file as a ZIP archive and reads the XML inside it. It resolves the first worksheet through the workbook relationships and reads shared strings, inline strings, and stored cell values. This avoids requiring Excel, pandas, or openpyxl.

The reader checks that the file has a header row and at least one reference. Headers must be unique and non-empty. A title column is required; an index column is optional. Formula cells depend on a cached value previously saved by Excel.

Each input row becomes a Python dictionary. Its keys are the column names and its values are the cell contents.

## 4. Cleaning and comparing titles

`clean()` removes HTML/XML-style tags, decodes entities such as `&amp;`, and replaces repeated whitespace with single spaces.

`normalized()` additionally converts text to lowercase, removes accent marks, and reduces punctuation to a normalized sequence of words.

`similarity()` passes the normalized titles to `SequenceMatcher`. It returns a score between 0 and 1. A score of 1 means that the normalized strings are identical.

The matching threshold is **0.88**. A lower-scoring candidate is rejected even if it contains an abstract. This reduces incorrect matches, but it is not a full bibliographic identity check: authors, publication years, and versions are not independently verified.

## 5. Representing a source record

The `Candidate` dataclass gives all sources the same record structure:

```python
Candidate(title, abstract, doi, url, source)
```

This means that the selection logic does not need to handle a different data structure for every database. Missing values remain empty.

## 6. Querying the databases

The `Client` class contains the source-specific methods:

| Method | What it does |
| --- | --- |
| `pubmed()` | Search PubMed by title, then use a broader query if no IDs are found; fetch returned records as XML |
| `crossref()` | Search Crossref bibliographic metadata and read available titles, DOIs, abstracts, and URLs |
| `europepmc()` | Search Europe PMC using a title query and request `resultType=core` to include available abstracts |
| `semantic()` | Query Semantic Scholar when the user provides an API key |

Each query asks for up to three candidates. `parse_pubmed()` preserves section labels in structured abstracts, such as `METHODS` and `RESULTS`, and extracts a DOI when present in the record.

The shared `get()` method builds an HTTPS request, identifies the application, applies a timeout, and parses JSON or returns XML bytes as needed. It spaces requests and retries transient failures up to three attempts. Selected HTTP errors, including rate limiting and temporary server failures, receive retries; ordinary client errors do not.

## 7. Resolving one reference

`Client.resolve(row)` coordinates the search for a single input row.

It copies the input fields, initializes the result fields, and obtains the title. A missing title produces a `Sin título` status without sending a search request.

For a non-empty title, it tries PubMed, Crossref, Europe PMC, and optional Semantic Scholar. Within each source's returned candidates, it compares titles and rejects scores below 0.88. When an accepted candidate contains an abstract, it selects that record and stops searching the reference.

If accepted candidates contain only metadata, it keeps a candidate without an abstract. If none passes the threshold, it records that no match was accepted. Source query failures are collected in `Query_Errors`, and later sources can still be tried.

The selected record supplies its own title, abstract, DOI, URL, and source. The program does not combine identifiers from unrelated candidates. The original title remains available separately.

## 8. Keeping the interface responsive

`main()` defines a Tkinter `App` class and starts its event loop.

The interface handles file selection, email and optional API-key entry, a progress bar, a results table, an abstract preview, and export controls.

Network searches run in a separate thread through `worker()`. The worker never directly modifies Tkinter widgets. Instead, it places events in a thread-safe queue. The interface's `poll()` method checks that queue every 100 milliseconds and updates the window on the main thread.

This separation lets the user inspect the window and request cancellation while searches are in progress.

## 9. Cancellation and saving

The Stop button sets a `threading.Event`. The client checks it between operations and during its controlled pauses. If cancellation is detected, a `Cancelled` exception stops the worker cleanly. An active network request must first return or time out.

After each completed reference, `write_results()` writes the collected results to a temporary CSV and then replaces the destination file. If replacement fails, for example because Excel has locked the destination, the previously saved destination remains intact. Results already delivered to the interface can still be exported to another file.

The CSV uses UTF-8 with a byte-order mark. Potential spreadsheet formula text is prefixed with an apostrophe. Starting another search processes the list from the beginning; the current application has no resume mechanism.

## 10. Windows executable scripts

`ABRIR_APP.bat` opens an existing executable or runs the Python source.

`CREAR_EXE_WINDOWS.bat` checks Python and Tkinter, creates a build environment, installs PyInstaller, runs the test suite, and packages the application as `dist/AbstractFetcher.exe`.

The build must be performed and checked on Windows. A precompiled executable is not included in this source project.

## 11. Tests and interpretation

`tests/test_app.py` contains 20 deterministic tests using local fixtures and mocked HTTP responses. They verify file reading, structured abstract parsing, matching, source provenance, missing information, query errors, retries, cancellation, and atomic writing.

The tests do not prove that every external service will always respond or that every matched title identifies the intended article. Review retrieved records before using them in a manuscript or evidence synthesis.
