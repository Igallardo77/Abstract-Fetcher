import csv
import io
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from abstract_fetcher import Candidate, Cancelled, Client, clean, parse_pubmed, read_table, similarity, title_of, write_results


class Tables(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_csv_accents_multiline_and_optional_index(self):
        p = self.folder / "refs.csv"
        p.write_text('Título;Autor\n"Análisis de datos\npara salud";Iván\n', encoding="utf-8-sig")
        rows = read_table(p)
        self.assertEqual(rows[0]["Autor"], "Iván")
        self.assertIn("para salud", title_of(rows[0]))

    def test_windows_encoding(self):
        p = self.folder / "refs.csv"
        p.write_bytes('Title,Autor\nDatos,Iván\n'.encode("cp1252"))
        self.assertEqual(read_table(p)[0]["Autor"], "Iván")

    def test_empty_title_retained(self):
        p = self.folder / "refs.csv"
        p.write_text('Index,Title\n1,\n2,Example\n')
        self.assertEqual(len(read_table(p)), 2)

    def test_invalid_header(self):
        p = self.folder / "refs.csv"
        p.write_text('Autor,DOI\nIvan,123\n')
        with self.assertRaisesRegex(ValueError, "Title"):
            read_table(p)

    def test_duplicate_headers(self):
        p = self.folder / "refs.csv"
        p.write_text('Title,Title\none,two\n')
        with self.assertRaisesRegex(ValueError, "únicos"):
            read_table(p)

    def test_xlsx_first_sheet_relationship_and_sparse_cells(self):
        p = self.folder / "refs.xlsx"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Refs" sheetId="7" r:id="rId7"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId7" Target="/xl/worksheets/sheet7.xml"/></Relationships>')
            z.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Title</t></si><si><r><t>Análisis </t></r><r><t>clínico</t></r></si></sst>')
            z.writestr("xl/worksheets/sheet7.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Index</t></is></c><c r="B1" t="s"><v>0</v></c><c r="C1" t="inlineStr"><is><t>Notas</t></is></c></row><row r="2"><c r="A2"><v>1</v></c><c r="B2" t="s"><v>1</v></c></row></sheetData></worksheet>')
        row = read_table(p)[0]
        self.assertEqual(row, {"Index": "1", "Title": "Análisis clínico", "Notas": ""})

    def test_output_roundtrip_and_formula(self):
        p = self.folder / "out.csv"
        rows = [{"Title": "Árboles, agua", "Abstract": "Línea 1\nLínea 2", "Original": "=1+1"}]
        write_results(p, rows)
        self.assertTrue(p.read_bytes().startswith(b"\xef\xbb\xbf"))
        with p.open(encoding="utf-8-sig", newline="") as f:
            out = list(csv.DictReader(f))[0]
        self.assertEqual(out["Abstract"], rows[0]["Abstract"])
        self.assertEqual(out["Original"], "'=1+1")
        self.assertFalse((self.folder / "out.csv.tmp").exists())

    def test_atomic_save_preserves_previous_on_error(self):
        p = self.folder / "out.csv"
        p.write_text("previous results")
        with patch("abstract_fetcher.os.replace", side_effect=PermissionError("Archivo abierto")):
            with self.assertRaises(PermissionError):
                write_results(p, [{"Title": "Data"}])
        self.assertEqual(p.read_text(), "previous results")
        self.assertFalse((self.folder / "out.csv.tmp").exists())


class ParsingAndSearch(unittest.TestCase):
    def test_cleanup_and_similarity(self):
        self.assertEqual(clean("<p>Data &amp; AI</p>\n  Methods"), "Data & AI Methods")
        self.assertEqual(similarity("ANÁLISIS: clínico.", "Analisis clinico"), 1)
        self.assertEqual(similarity("", "a"), 0)

    def test_pubmed_structured_abstract(self):
        xml = b'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article><ArticleTitle>Study of <i>data</i></ArticleTitle><Abstract><AbstractText Label="METHODS">We used <b>AI</b>.</AbstractText><AbstractText NlmCategory="RESULTS">Useful findings.</AbstractText></Abstract></Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.1/test</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>'
        candidate = parse_pubmed(xml)[0]
        self.assertEqual(candidate.title, "Study of data")
        self.assertEqual(candidate.abstract, "METHODS: We used AI. RESULTS: Useful findings.")
        self.assertEqual(candidate.doi, "10.1/test")

    def client(self):
        client = Client("test@example.org")
        client.pubmed = lambda title: []
        client.crossref = lambda title: []
        client.europepmc = lambda title: []
        client.semantic = lambda title: []
        return client

    def test_wrong_first_candidate_rejected(self):
        c = self.client()
        c.pubmed = lambda t: [Candidate("Unrelated research", "Wrong abstract", source="PubMed"),
                              Candidate(t, "Correct abstract", source="PubMed")]
        c.crossref = lambda t: self.fail("Should stop after accepted abstract")
        row = c.resolve({"Title": "Neural networks for water quality", "Index": "9"})
        self.assertEqual(row["Abstract"], "Correct abstract")
        self.assertEqual(row["Index"], "9")
        self.assertEqual(row["Match_Score"], "1.000")

    def test_no_fabricated_abstract(self):
        row = self.client().resolve({"Title": "Some real study"})
        self.assertEqual(row["Abstract"], "")
        self.assertEqual(row["Status"], "Sin coincidencia aceptada")

    def test_europepmc_is_in_loop_and_keeps_provenance_consistent(self):
        c = self.client()
        c.crossref = lambda t: [Candidate(t, "", "10.1/crossref", "crossref-url", "Crossref")]
        c.europepmc = lambda t: [Candidate(t, "Recovered summary", "10.1/europe", "europe-url", "Europe PMC")]
        row = c.resolve({"Title": "Some real study"})
        self.assertEqual((row["Abstract_Source"], row["DOI"], row["URL"]), ("Europe PMC", "10.1/europe", "europe-url"))

    def test_europepmc_requests_core(self):
        c = Client("test@example.org")
        with patch.object(c, "get", return_value={"resultList": {"result": [{"title": "Study", "abstractText": "Summary", "source": "MED", "id": "1"}]}}) as get:
            self.assertEqual(c.europepmc("Study")[0].abstract, "Summary")
            self.assertEqual(get.call_args.args[1]["resultType"], "core")

    def test_errors_are_recorded_and_fallback_continues(self):
        c = self.client()
        def failed(_):
            raise RuntimeError("HTTP 503")
        c.pubmed = failed
        c.crossref = lambda t: [Candidate(t, "Found", source="Crossref")]
        row = c.resolve({"Title": "Some real study"})
        self.assertIn("PubMed: HTTP 503", row["Query_Errors"])
        self.assertEqual(row["Abstract"], "Found")

    def test_no_title_does_not_search(self):
        c = self.client()
        c.pubmed = lambda t: self.fail("Should not search")
        self.assertEqual(c.resolve({"Title": ""})["Status"], "Sin título")

    def test_metadata_without_abstract(self):
        c = self.client()
        c.pubmed = lambda t: [Candidate(t, doi="10.1/meta", source="PubMed")]
        row = c.resolve({"Title": "Some real study"})
        self.assertEqual(row["Abstract"], "")
        self.assertEqual(row["Status"], "Sin resumen público")

    def test_cancellation(self):
        event = threading.Event()
        event.set()
        c = Client("test@example.org", stop=event)
        with self.assertRaises(Cancelled):
            c.resolve({"Title": "A study"})

    def test_retries_http_429(self):
        c = Client("test@example.org")
        failure = urllib.error.HTTPError("https://example.org", 429, "Limited", {}, None)
        with patch("urllib.request.urlopen", side_effect=[failure, io.BytesIO(b'{"ok": true}')]) as request, patch.object(c, "pause"):
            self.assertEqual(c.get("https://example.org", {}), {"ok": True})
            self.assertEqual(request.call_count, 2)

    def test_http_400_not_retried(self):
        c = Client("test@example.org")
        failure = urllib.error.HTTPError("https://example.org", 400, "Bad request", {}, None)
        with patch("urllib.request.urlopen", side_effect=failure) as request, patch.object(c, "pause"):
            with self.assertRaisesRegex(RuntimeError, "400"):
                c.get("https://example.org", {})
            self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
