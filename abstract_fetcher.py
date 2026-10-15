"""Abstract Fetcher UAGro. Python 3.10+; solo biblioteca estándar."""
from __future__ import annotations

import csv
import html
import json
import os
import posixpath
import queue
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree as ET

EXTRA_COLUMNS = ["Original_Title", "Matched_Title", "DOI", "Abstract", "Abstract_Source",
                 "URL", "Match_Score", "Status", "Query_Errors"]


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(value or "")))).strip()


def normalized(value):
    text = unicodedata.normalize("NFKD", clean(value).lower())
    return " ".join(re.findall(r"[^\W_]+", "".join(c for c in text if not unicodedata.combining(c))))


def similarity(a, b):
    a, b = normalized(a), normalized(b)
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def read_table(path):
    """Lee CSV UTF-8/Windows o primera hoja XLSX, sin depender de Excel instalado."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        data = path.read_bytes()
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252")
        import io
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        matrix = list(csv.reader(io.StringIO(text, newline=""), dialect))
    elif path.suffix.lower() == ".xlsx":
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(path) as z:
            strings = []
            if "xl/sharedStrings.xml" in z.namelist():
                root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                strings = ["".join(n.itertext()) for n in root.findall("s:si", ns)]
            workbook = ET.fromstring(z.read("xl/workbook.xml"))
            sheet = workbook.find("s:sheets/s:sheet", ns)
            if sheet is None:
                raise ValueError("El Excel no tiene hojas.")
            rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            target = next((r.get("Target") for r in rels if r.get("Id") == rid), None)
            if not target:
                raise ValueError("No se pudo localizar la primera hoja.")
            member = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            root = ET.fromstring(z.read(member))
            matrix = []
            for row in root.findall("s:sheetData/s:row", ns):
                values = {}
                for cell in row.findall("s:c", ns):
                    letters = re.match(r"[A-Z]+", cell.get("r", "A1")).group()
                    index = 0
                    for letter in letters:
                        index = index * 26 + ord(letter) - 64
                    if index > 16384:
                        raise ValueError("Columna de Excel inválida.")
                    val = cell.findtext("s:v", "", ns)
                    if cell.get("t") == "s":
                        val = strings[int(val)] if val else ""
                    elif cell.get("t") == "inlineStr":
                        node = cell.find("s:is", ns)
                        val = "".join(node.itertext()) if node is not None else ""
                    values[index - 1] = val
                matrix.append([values.get(i, "") for i in range(max(values, default=-1) + 1)])
    else:
        raise ValueError("Selecciona un archivo .xlsx o .csv. Para .xls, guárdalo primero como .xlsx.")
    matrix = [r for r in matrix if any(str(v).strip() for v in r)]
    if len(matrix) < 2:
        raise ValueError("El archivo debe contener encabezados y al menos una referencia.")
    headers = [str(v).strip() for v in matrix[0]]
    if not all(headers) or len(headers) != len(set(headers)):
        raise ValueError("Los encabezados deben tener nombres únicos y no estar vacíos.")
    if not any(normalized(h) in ("title", "titulo") for h in headers):
        raise ValueError("Falta la columna Title o Título en la primera fila.")
    rows = [dict(zip(headers, r + [""] * max(0, len(headers) - len(r)))) for r in matrix[1:]]
    return rows


def title_of(row):
    return str(next((v for k, v in row.items() if normalized(k) in ("title", "titulo")), "")).strip()


def write_results(path, rows):
    """Guardado atómico. Prefija fórmulas para abrir textos externos en Excel."""
    if not rows:
        return
    path = Path(path)
    keys = list(dict.fromkeys(k for row in rows for k in row))
    temp = path.with_name(path.name + ".tmp")
    def safe(value):
        value = str(value or "")
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
    try:
        with temp.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows({k: safe(v) for k, v in row.items()} for row in rows)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class Cancelled(Exception):
    pass


@dataclass
class Candidate:
    title: str = ""
    abstract: str = ""
    doi: str = ""
    url: str = ""
    source: str = ""


def parse_pubmed(data):
    root = ET.fromstring(data)
    error = root.findtext(".//ERROR")
    if error:
        raise ValueError(error)
    result = []
    for record in root.findall(".//PubmedArticle"):
        article = record.find("MedlineCitation/Article")
        if article is None:
            continue
        title_node = article.find("ArticleTitle")
        title = clean("".join(title_node.itertext())) if title_node is not None else ""
        pieces = []
        for node in article.findall("Abstract/AbstractText"):
            label = node.get("Label") or node.get("NlmCategory", "")
            label = label if label != "UNASSIGNED" else ""
            pieces.append((label + ": " if label else "") + clean("".join(node.itertext())))
        doi = next((clean(n.text) for n in record.findall("PubmedData/ArticleIdList/ArticleId")
                    if n.get("IdType") == "doi"), "")
        pmid = record.findtext("MedlineCitation/PMID", "")
        result.append(Candidate(title, " ".join(pieces), doi,
                                f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "PubMed"))
    return result


class Client:
    def __init__(self, email, s2_key="", stop=None):
        self.email = email
        self.s2_key = s2_key
        self.stop = stop or threading.Event()
        self.last_request = 0

    def pause(self, seconds):
        if self.stop.wait(max(0, seconds)):
            raise Cancelled()

    def get(self, base, params, headers=None, xml=False):
        url = base + "?" + urllib.parse.urlencode(params)
        all_headers = {"User-Agent": f"UAGro-AbstractFetcher/2.0 (mailto:{self.email})"}
        all_headers.update(headers or {})
        for attempt in range(3):
            self.pause(0.4 - (time.monotonic() - self.last_request))
            self.last_request = time.monotonic()
            try:
                request = urllib.request.Request(url, headers=all_headers)
                with urllib.request.urlopen(request, timeout=20) as response:
                    data = response.read()
                if self.stop.is_set():
                    raise Cancelled()
                return data if xml else json.loads(data)
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise RuntimeError(f"HTTP {exc.code}") from None
                delay = exc.headers.get("Retry-After", "")
                self.pause(min(float(delay), 20) if delay.isdigit() else 2 ** (attempt + 1))
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise RuntimeError("No se pudo conectar después de 3 intentos") from None
                self.pause(2 ** (attempt + 1))

    def pubmed(self, title):
        base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        common = {"db": "pubmed", "email": self.email, "tool": "UAGroAbstractFetcher"}
        query_title = title.replace('"', " ")
        for term in (f'"{query_title}"[Title]', title):
            data = self.get(base + "esearch.fcgi", {**common, "term": term, "retmax": 3, "retmode": "json"})
            if data.get("error"):
                raise ValueError("Error de búsqueda de PubMed")
            ids = data.get("esearchresult", {}).get("idlist", [])
            if ids:
                data = self.get(base + "efetch.fcgi", {**common, "id": ",".join(ids), "retmode": "xml"}, xml=True)
                return parse_pubmed(data)
        return []

    def crossref(self, title):
        data = self.get("https://api.crossref.org/works", {
            "query.bibliographic": title, "rows": 3, "mailto": self.email})
        return [Candidate(clean(" ".join(item.get("title") or [])), clean(item.get("abstract")),
                          item.get("DOI", ""), item.get("URL", ""), "Crossref")
                for item in data.get("message", {}).get("items", [])]

    def europepmc(self, title):
        query_title = title.replace('"', " ")
        for query in (f'TITLE:"{query_title}"', title):
            data = self.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", {
                "query": query, "format": "json", "resultType": "core", "pageSize": 3})
            if data.get("errCode") or data.get("error"):
                raise ValueError("Error de búsqueda de Europe PMC")
            items = data.get("resultList", {}).get("result", [])
            if items:
                return [Candidate(clean(i.get("title")), clean(i.get("abstractText")), i.get("doi", ""),
                                  f"https://europepmc.org/abstract/{i.get('source', '')}/{i.get('id', '')}",
                                  "Europe PMC") for i in items]
        return []

    def semantic(self, title):
        if not self.s2_key:
            return []
        data = self.get("https://api.semanticscholar.org/graph/v1/paper/search", {
            "query": title, "limit": 3, "fields": "title,abstract,externalIds,url"},
            {"x-api-key": self.s2_key})
        return [Candidate(clean(i.get("title")), clean(i.get("abstract")),
                          (i.get("externalIds") or {}).get("DOI", ""), i.get("url", ""), "Semantic Scholar")
                for i in data.get("data", [])]

    def resolve(self, row):
        title = title_of(row)
        output = dict(row)
        output.update({k: "" for k in EXTRA_COLUMNS})
        output["Original_Title"] = title
        if not title:
            output["Status"] = "Sin título"
            return output
        best, score, errors = None, 0.0, []
        for name, search in [("PubMed", self.pubmed), ("Crossref", self.crossref),
                             ("Europe PMC", self.europepmc), ("Semantic Scholar", self.semantic)]:
            if self.stop.is_set():
                raise Cancelled()
            try:
                candidates = search(title)
            except Cancelled:
                raise
            except Exception as exc:
                # No registra claves ni URLs de solicitudes en los resultados.
                errors.append(f"{name}: {str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__}")
                continue
            valid = sorted(((similarity(title, c.title), c) for c in candidates), key=lambda x: x[0], reverse=True)
            for current_score, candidate in valid:
                if current_score < 0.88:
                    continue
                if best is None or current_score > score or candidate.abstract:
                    best, score = candidate, current_score
                if candidate.abstract:
                    break
            if best and best.abstract:
                break
        if best:
            output.update(Matched_Title=best.title, DOI=best.doi, Abstract=best.abstract,
                          Abstract_Source=best.source, URL=best.url, Match_Score=f"{score:.3f}",
                          Status="Resumen recuperado" if best.abstract else "Sin resumen público")
        else:
            output["Status"] = "Sin coincidencia aceptada"
        output["Query_Errors"] = " | ".join(errors)
        return output


def main():
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Abstract Fetcher · UAGro")
            self.geometry("1100x760")
            self.minsize(850, 640)
            self.configure(bg="#f3f5f9")
            self.rows, self.results = [], []
            self.stop = threading.Event()
            self.events = queue.Queue()
            self.running = False
            self.protocol("WM_DELETE_WINDOW", self.close)
            style = ttk.Style(self)
            style.theme_use("clam")
            style.configure("TFrame", background="#f3f5f9")
            style.configure("TLabel", background="#f3f5f9", font=("Segoe UI", 10))
            style.configure("TButton", font=("Segoe UI", 10), padding=8)
            style.configure("Accent.TButton", background="#71304b", foreground="white")
            style.configure("Treeview", rowheight=29, font=("Segoe UI", 10))
            wrap = ttk.Frame(self, padding=22)
            wrap.pack(fill="both", expand=True)
            ttk.Label(wrap, text="Buscador de resúmenes científicos", font=("Segoe UI", 21, "bold"),
                      foreground="#532339").pack(anchor="w")
            ttk.Label(wrap, text="Carga tus referencias · Recupera resúmenes · Exporta los resultados").pack(anchor="w", pady=(5, 16))
            cfg = ttk.Frame(wrap)
            cfg.pack(fill="x")
            ttk.Label(cfg, text="Correo de contacto:").grid(row=0, column=0, sticky="w")
            self.email = ttk.Entry(cfg, width=33)
            self.email.insert(0, "igallardo@uagro.mx")
            self.email.grid(row=0, column=1, padx=(8, 20), sticky="ew")
            ttk.Label(cfg, text="Clave Semantic Scholar (opcional):").grid(row=0, column=2)
            self.key = ttk.Entry(cfg, show="*", width=25)
            self.key.grid(row=0, column=3, padx=8, sticky="ew")
            cfg.columnconfigure(1, weight=1)
            cfg.columnconfigure(3, weight=1)
            bar = ttk.Frame(wrap)
            bar.pack(fill="x", pady=16)
            self.load_btn = ttk.Button(bar, text="1. Cargar Excel / CSV", command=self.load)
            self.load_btn.pack(side="left")
            self.start_btn = ttk.Button(bar, text="2. Buscar resúmenes", command=self.start, style="Accent.TButton", state="disabled")
            self.start_btn.pack(side="left", padx=8)
            self.stop_btn = ttk.Button(bar, text="Detener", command=self.cancel, state="disabled")
            self.stop_btn.pack(side="left")
            self.export_btn = ttk.Button(bar, text="Guardar copia CSV", command=self.export, state="disabled")
            self.export_btn.pack(side="right")
            self.filename = tk.StringVar(value="Selecciona un archivo con una columna Title o Título.")
            ttk.Label(wrap, textvariable=self.filename).pack(anchor="w")
            self.progress = ttk.Progressbar(wrap, mode="determinate")
            self.progress.pack(fill="x", pady=(12, 6))
            self.status = tk.StringVar(value="Listo. Se consultan PubMed, Crossref y Europe PMC.")
            ttk.Label(wrap, textvariable=self.status).pack(anchor="w", pady=(0, 12))
            table_frame = ttk.Frame(wrap)
            table_frame.pack(fill="both", expand=True)
            self.tree = ttk.Treeview(table_frame, columns=("number", "title", "source", "status"), show="headings", height=9)
            for col, title, width in [("number", "N.º", 55), ("title", "Título", 510), ("source", "Fuente", 120), ("status", "Estado", 190)]:
                self.tree.heading(col, text=title)
                self.tree.column(col, width=width, stretch=col in ("title", "status"))
            scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
            self.tree.configure(yscrollcommand=scroll.set)
            self.tree.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            self.tree.bind("<<TreeviewSelect>>", self.detail)
            detail_header = ttk.Frame(wrap)
            detail_header.pack(fill="x", pady=(12, 4))
            ttk.Label(detail_header, text="Detalle de la referencia seleccionada", font=("Segoe UI", 10, "bold")).pack(side="left")
            ttk.Button(detail_header, text="Abrir artículo", command=self.open_article).pack(side="right")
            self.preview = scrolledtext.ScrolledText(wrap, height=8, wrap="word", font=("Segoe UI", 10), relief="flat", padx=10, pady=10)
            self.preview.pack(fill="x")
            self.preview.configure(state="disabled")
            ttk.Label(wrap, text="Se conservan solo resúmenes recuperados. La similitud del título es orientativa: revisa las coincidencias.",
                      foreground="#626a79", wraplength=1000).pack(anchor="w", pady=(12, 0))
            self.after(100, self.poll)

        def load(self):
            path = filedialog.askopenfilename(filetypes=[("Referencias", "*.xlsx *.csv")])
            if not path:
                return
            try:
                rows = read_table(path)
            except Exception as exc:
                messagebox.showerror("No se pudo abrir", str(exc))
                return
            self.rows, self.results = rows, []
            self.input_path = Path(path)
            self.tree.delete(*self.tree.get_children())
            for i, row in enumerate(rows):
                self.tree.insert("", "end", iid=str(i), values=(i + 1, title_of(row), "", "Pendiente"))
            self.filename.set(f"{Path(path).name} · {len(rows)} referencias")
            self.status.set("Archivo cargado. Pulsa Buscar resúmenes y elige dónde guardar el CSV.")
            self.progress["value"] = 0
            self.start_btn.configure(state="normal")
            self.export_btn.configure(state="disabled")
            self.detail()

        def start(self):
            email = self.email.get().strip()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                messagebox.showerror("Correo requerido", "Escribe un correo de contacto válido para las consultas.")
                return
            path = filedialog.asksaveasfilename(title="Guardar resultados automáticamente", defaultextension=".csv",
                                              initialfile=self.input_path.stem + "_con_resumenes.csv",
                                              filetypes=[("CSV para Excel", "*.csv")])
            if not path:
                return
            if Path(path).resolve() == self.input_path.resolve():
                messagebox.showerror("Elige otro nombre", "El archivo de salida debe ser distinto al original.")
                return
            try:
                # Comprueba escritura sin modificar un archivo de resultados existente.
                import tempfile
                with tempfile.TemporaryFile(dir=Path(path).parent):
                    pass
            except OSError as exc:
                messagebox.showerror("No se puede guardar", str(exc))
                return
            self.results = []
            self.stop.clear()
            self.running = True
            self.progress.configure(maximum=len(self.rows), value=0)
            for child in self.tree.get_children():
                self.tree.set(child, "source", "")
                self.tree.set(child, "status", "Pendiente")
            for control in (self.load_btn, self.start_btn, self.email, self.key, self.export_btn):
                control.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.output_path = Path(path)
            self.status.set("Iniciando consultas. Necesitas conexión a Internet.")
            threading.Thread(target=self.worker, args=(email, self.key.get().strip(), path), daemon=True).start()

        def worker(self, email, key, path):
            results = []
            try:
                client = Client(email, key, self.stop)
                for i, row in enumerate(self.rows):
                    if self.stop.is_set():
                        break
                    self.events.put(("searching", i))
                    result = client.resolve(row)
                    results.append(result)
                    self.events.put(("row", i, result))
                    write_results(path, results)
                self.events.put(("done", self.stop.is_set()))
            except Cancelled:
                self.events.put(("done", True))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        def poll(self):
            try:
                while True:
                    event = self.events.get_nowait()
                    if event[0] == "searching":
                        self.status.set(f"Buscando referencia {event[1] + 1} de {len(self.rows)}…")
                    elif event[0] == "row":
                        _, i, result = event
                        self.results.append(result)
                        self.tree.item(str(i), values=(i + 1, result["Original_Title"], result["Abstract_Source"], result["Status"]))
                        self.tree.see(str(i))
                        self.progress["value"] = len(self.results)
                        self.detail()
                    else:
                        self.running = False
                        for control in (self.load_btn, self.start_btn, self.email, self.key):
                            control.configure(state="normal")
                        self.stop_btn.configure(state="disabled")
                        self.export_btn.configure(state="normal" if self.results else "disabled")
                        found = sum(bool(r["Abstract"]) for r in self.results)
                        errored = sum(bool(r["Query_Errors"]) for r in self.results)
                        prefix = "Detenido" if event[0] == "done" and event[1] else "Terminado"
                        self.status.set(f"{prefix}: {len(self.results)}/{len(self.rows)} procesadas · {found} con resumen · {errored} con errores de consulta.")
                        if event[0] == "error":
                            self.status.set("Proceso interrumpido. Puedes guardar una copia de los resultados disponibles.")
                            messagebox.showerror("Proceso interrumpido", event[1] + "\n\nLos resultados disponibles permanecen en la ventana.")
                        elif self.results:
                            messagebox.showinfo("Resultados guardados", f"{found} resúmenes recuperados.\n\nCSV guardado en:\n{self.output_path}")
            except queue.Empty:
                pass
            self.after(100, self.poll)

        def selected(self):
            selected = self.tree.selection()
            if not selected:
                return None
            index = int(selected[0])
            return self.results[index] if index < len(self.results) else None

        def detail(self, _event=None):
            result = self.selected()
            text = "Selecciona una referencia para ver su resumen y los datos recuperados."
            if result:
                text = (f"Título original: {result['Original_Title']}\nTítulo encontrado: {result['Matched_Title']}\n"
                        f"Fuente: {result['Abstract_Source']} | Similitud del título: {result['Match_Score']} | DOI: {result['DOI']}\n"
                        f"Estado: {result['Status']}\n\n{result['Abstract'] or 'No se recuperó un resumen público.'}")
                if result["Query_Errors"]:
                    text += "\n\nIncidencias: " + result["Query_Errors"]
            self.preview.configure(state="normal")
            self.preview.delete("1.0", "end")
            self.preview.insert("1.0", text)
            self.preview.configure(state="disabled")

        def open_article(self):
            result = self.selected()
            if result and str(result.get("URL", "")).startswith("https://"):
                webbrowser.open(result["URL"])
            else:
                messagebox.showinfo("Sin enlace", "Selecciona un resultado que tenga un enlace recuperado.")

        def export(self):
            path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="resumenes_copia.csv", filetypes=[("CSV", "*.csv")])
            if not path:
                return
            if Path(path).resolve() == self.input_path.resolve():
                messagebox.showerror("Elige otro nombre", "No sobrescribas el archivo original.")
                return
            try:
                write_results(path, self.results)
                messagebox.showinfo("Guardado", path)
            except Exception as exc:
                messagebox.showerror("No se pudo guardar", str(exc))

        def cancel(self):
            self.stop.set()
            self.stop_btn.configure(state="disabled")
            self.status.set("Deteniendo… una solicitud en curso puede tardar hasta 20 segundos.")

        def close(self):
            if self.running:
                self.cancel()
                messagebox.showinfo("Deteniendo", "Espera a que termine la solicitud actual y después cierra la ventana. Se conservan las referencias terminadas.")
                return
            self.destroy()

    App().mainloop()


if __name__ == "__main__":
    main()
